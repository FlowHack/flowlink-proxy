"""
Mock-SOCKS5 сервер для тестирования и разработки.

Запускается в dev-режиме (--dev) на случайном свободном порту.
Выполняет полный SOCKS5 handshake, но не туннелирует данные —
возвращает успешный CONNECT и эхо-обмен (для проверки ping).

Единственная ответственность: тестовый SOCKS5 сервер.
"""

import asyncio
import logging
import socket
import struct

from server.protocols.socks5_constants import (
    ATYP_IPV4,
    CMD_CONNECT,
    METHOD_NO_ACCEPTABLE,
    METHOD_NO_AUTH,
    METHOD_USERPASS,
    SOCKS5_RSV,
    SOCKS5_SUCCESS,
    SOCKS5_VERSION,
    USERPASS_SUCCESS,
    USERPASS_VERSION,
)

logger = logging.getLogger('flowlink.mock_socks5')


class MockSocks5Server:  # pylint: disable=too-many-instance-attributes
    # 10 атрибутов — конфигурируемый тестовый сервер с матрицей режимов отказов
    # (reject_methods/reject_connect/require_userpass/reject_userpass и т.д.);
    # разбиение на подклассы усложнило бы использование в тестах.
    """
    Тестовый SOCKS5-сервер для проверки ping/connect без внешнего прокси.

    Протокол:
      1. Принимает TCP-соединение
      2. Method negotiation (NO AUTH или USERPASS — настраивается)
      3. CONNECT-запрос — всегда успех
      4. Возвращает bind address (0.0.0.0:0)
      5. Соединение висит открытым (проверка ping)
    """

    def __init__(  # pylint: disable=too-many-arguments
        # 8 параметров — полная матрица конфигурации тестового сервера,
        # сведение их в словарь снизило бы наглядность вызова в тестах.
        self,
        host: str = '127.0.0.1',
        port: int = 0,
        *,
        reject_methods: bool = False,
        reject_connect: bool = False,
        require_userpass: bool = False,
        reject_userpass: bool = False,
        username: str = 'user',
        password: str = 'pass',
    ):
        """
        Инициализирует тестовый SOCKS5-сервер.

        Args:
            host: Адрес для прослушивания.
            port: Порт (0 — случайный свободный).
            reject_methods: Если True — отвечает отказом (0xFF)
                на method negotiation (не поддерживает NO AUTH).
            reject_connect: Если True — отвечает ошибкой CONNECT
                (код 0x01 — general failure).
            require_userpass: Если True — принимает только USERPASS
                (метод 0x02) и проверяет учётные данные клиента.
            reject_userpass: Если True — отвечает отказом (0xFF), когда
                клиент предлагает USERPASS (модель сервера только с NO AUTH).
            username: Ожидаемый логин при require_userpass=True.
            password: Ожидаемый пароль при require_userpass=True.
        """
        self._host = host
        self._port = port
        self._reject_methods = reject_methods
        self._reject_connect = reject_connect
        self._require_userpass = require_userpass
        self._reject_userpass = reject_userpass
        self._username = username
        self._password = password
        self._server: asyncio.AbstractServer | None = None
        self._actual_port: int = 0

    @property
    def port(self) -> int:
        """Фактический порт, на котором слушает сервер."""
        return self._actual_port

    async def start(self):
        """Запускает сервер на указанном хосте:порту."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )
        self._actual_port = self._server.sockets[0].getsockname()[1]
        logger.info(
            'Mock-SOCKS5 сервер запущен на %s:%d',
            self._host, self._actual_port
        )

    async def stop(self):
        """Останавливает сервер."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info('Mock-SOCKS5 сервер остановлен')

    async def _handle_client(  # pylint: disable=too-many-branches,too-many-locals,too-many-return-statements,too-many-statements
        # Линейный handshake SOCKS5 (negotiation → USERPASS → CONNECT → эхо)
        # с конфигурируемыми отказами: ветвления и ранние return — это и есть
        # проверяемая логика, декомпозиция ухудшила бы читаемость.
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Обрабатывает одно SOCKS5-соединение."""
        try:
            # Шаг 1: method negotiation
            ver, nmethods = struct.unpack('!BB', await reader.readexactly(2))
            if ver != SOCKS5_VERSION:
                return
            methods = await reader.readexactly(nmethods)

            # Если настроен отказ на method negotiation — отвечаем 0xFF
            if self._reject_methods:
                writer.write(
                    struct.pack('!BB', SOCKS5_VERSION, METHOD_NO_ACCEPTABLE)
                )
                await writer.drain()
                return

            # Сервер не поддерживает USERPASS (только NO AUTH):
            # при запросе USERPASS отвечаем 0xFF (NO ACCEPTABLE)
            if self._reject_userpass and METHOD_USERPASS in methods:
                writer.write(
                    struct.pack('!BB', SOCKS5_VERSION, METHOD_NO_ACCEPTABLE)
                )
                await writer.drain()
                return

            # Сервер требует USERPASS-аутентификацию
            if self._require_userpass:
                if METHOD_USERPASS not in methods:
                    writer.write(
                        struct.pack(
                            '!BB', SOCKS5_VERSION, METHOD_NO_ACCEPTABLE
                        )
                    )
                    await writer.drain()
                    return
                writer.write(
                    struct.pack('!BB', SOCKS5_VERSION, METHOD_USERPASS)
                )
                await writer.drain()

                # Шаг 1.5: USERPASS sub-negotiation —
                # [0x01, user_len, user, pass_len, pass]
                auth_ver, user_len = struct.unpack(
                    '!BB', await reader.readexactly(2)
                )
                if auth_ver != USERPASS_VERSION:
                    return
                user = await reader.readexactly(user_len)
                pass_len = (await reader.readexactly(1))[0]
                password = await reader.readexactly(pass_len)
                if (
                    user == self._username.encode()
                    and password == self._password.encode()
                ):
                    writer.write(
                        struct.pack(
                            '!BB', USERPASS_VERSION, USERPASS_SUCCESS
                        )
                    )
                    await writer.drain()
                else:
                    # Статус 0x01 — отказ в аутентификации
                    writer.write(struct.pack('!BB', USERPASS_VERSION, 0x01))
                    await writer.drain()
                    return
            else:
                if METHOD_NO_AUTH not in methods:
                    writer.write(
                        struct.pack(
                            '!BB', SOCKS5_VERSION, METHOD_NO_ACCEPTABLE
                        )
                    )
                    await writer.drain()
                    return
                writer.write(
                    struct.pack('!BB', SOCKS5_VERSION, METHOD_NO_AUTH)
                )
                await writer.drain()

            # Шаг 2: CONNECT
            header = await reader.readexactly(4)
            ver, cmd, _rsv, atyp = struct.unpack('!BBBB', header)
            if cmd != CMD_CONNECT:
                return

            if atyp == ATYP_IPV4:
                await reader.readexactly(4 + 2)
            elif atyp == 0x03:
                domain_len = (await reader.readexactly(1))[0]
                await reader.readexactly(domain_len + 2)
            else:
                await reader.readexactly(16 + 2)

            # Шаг 3: успех или отказ CONNECT
            if self._reject_connect:
                # Код 0x01 — general failure
                reply = (
                    struct.pack(
                        '!BBBB', SOCKS5_VERSION, 0x01, SOCKS5_RSV, ATYP_IPV4
                    ) + socket.inet_aton('0.0.0.0') +
                    struct.pack('!H', 0)
                )
            else:
                reply = (
                    struct.pack(
                        '!BBBB', SOCKS5_VERSION, SOCKS5_SUCCESS, SOCKS5_RSV,
                        ATYP_IPV4
                    ) + socket.inet_aton('0.0.0.0') +
                    struct.pack('!H', 0)
                )
            writer.write(reply)
            await writer.drain()

            # Шаг 4: держим соединение открытым для проверки ping
            # Просто ждём, пока клиент закроет
            try:
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
                    # Эхо — отправляем обратно (для проверки передачи)
                    writer.write(data)
                    await writer.drain()
            except (OSError, ConnectionError) as e:
                logger.debug('Mock SOCKS5: ошибка в цикле эха: %s', e)

        except (asyncio.IncompleteReadError, ConnectionError, OSError) as e:
            logger.debug(
                'Mock SOCKS5: ошибка чтения или разрыва соединения: %s', e
            )
        finally:
            try:
                writer.close()
            except (OSError, ConnectionError) as e:
                logger.debug('Mock SOCKS5: ошибка закрытия writer: %s', e)
