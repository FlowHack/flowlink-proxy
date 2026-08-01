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
    METHOD_NO_AUTH,
    SOCKS5_RSV,
    SOCKS5_SUCCESS,
    SOCKS5_VERSION,
)

logger = logging.getLogger('flowlink.mock_socks5')


class MockSocks5Server:
    """
    Тестовый SOCKS5-сервер для проверки ping/connect без внешнего прокси.

    Протокол:
      1. Принимает TCP-соединение
      2. Method negotiation (только NO AUTH)
      3. CONNECT-запрос — всегда успех
      4. Возвращает bind address (0.0.0.0:0)
      5. Соединение висит открытым (проверка ping)
    """

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 0,
        *,
        reject_methods: bool = False,
        reject_connect: bool = False,
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
        """
        self._host = host
        self._port = port
        self._reject_methods = reject_methods
        self._reject_connect = reject_connect
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
        logger.info('Mock-SOCKS5 сервер запущен на %s:%d', self._host, self._actual_port)

    async def stop(self):
        """Останавливает сервер."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info('Mock-SOCKS5 сервер остановлен')

    async def _handle_client(  # pylint: disable=too-many-branches  # ветвления по шагам SOCKS5-протокола и конфигурируемым отказам
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Обрабатывает одно SOCKS5-соединение."""
        try:
            # Шаг 1: method negotiation — всегда NO AUTH
            ver, nmethods = struct.unpack('!BB', await reader.readexactly(2))
            if ver != SOCKS5_VERSION:
                return
            methods = await reader.readexactly(nmethods)
            if METHOD_NO_AUTH not in methods:
                writer.write(struct.pack('!BB', SOCKS5_VERSION, 0xFF))
                await writer.drain()
                return

            # Если настроен отказ на method negotiation — отвечаем 0xFF
            if self._reject_methods:
                writer.write(struct.pack('!BB', SOCKS5_VERSION, 0xFF))
                await writer.drain()
                return

            writer.write(struct.pack('!BB', SOCKS5_VERSION, METHOD_NO_AUTH))
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
                    struct.pack('!BBBB', SOCKS5_VERSION, 0x01, SOCKS5_RSV, ATYP_IPV4) +
                    socket.inet_aton('0.0.0.0') +
                    struct.pack('!H', 0)
                )
            else:
                reply = (
                    struct.pack('!BBBB', SOCKS5_VERSION, SOCKS5_SUCCESS, SOCKS5_RSV, ATYP_IPV4) +
                    socket.inet_aton('0.0.0.0') +
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
            logger.debug('Mock SOCKS5: ошибка чтения или разрыва соединения: %s', e)
        finally:
            try:
                writer.close()
            except (OSError, ConnectionError) as e:
                logger.debug('Mock SOCKS5: ошибка закрытия writer: %s', e)
