"""
SOCKS5 клиент на чистом asyncio + struct (без внешних зависимостей).

Поддерживает:
- Аутентификацию username/password (метод 0x02)
- Прямое соединение без auth (метод 0x00)
- Доменные имена (ATYP 0x03) и IPv4 (ATYP 0x01)
- CONNECT-команду
"""

import asyncio
import logging
import socket
import struct

from server.protocols.base import ProxyError, ProxyProtocol

logger = logging.getLogger('flowlink.socks5')

SOCKS5_VERSION = 0x05
CMD_CONNECT = 0x01
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03

METHOD_NO_AUTH = 0x00
METHOD_USERPASS = 0x02
METHOD_NO_ACCEPTABLE = 0xFF

USERPASS_VERSION = 0x01
USERPASS_SUCCESS = 0x00

SOCKS5_RSV = 0x00
SOCKS5_SUCCESS = 0x00


class Socks5Error(ProxyError):
    """Ошибка SOCKS5 соединения."""
    pass


class Socks5Protocol(ProxyProtocol):
    """Реализация SOCKS5 прокси-протокола."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._host = config.get('host', '')
        self._port = config.get('port', 0)
        self._username = config.get('username', '')
        self._password = config.get('password', '')

    async def connect(
        self,
        target_host: str,
        target_port: int,
        timeout: float = 10,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Устанавливает SOCKS5-туннель до target_host:target_port.

        Args:
            target_host: Целевой хост для CONNECT.
            target_port: Целевой порт для CONNECT.
            timeout: Таймаут на всё соединение.

        Returns:
            (reader, writer) — асинхронный поток для передачи данных.

        Raises:
            Socks5Error: при ошибке handshake или таймауте.
        """
        try:
            reader, writer = await asyncio.wait_for(
                self._do_connect(target_host, target_port),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise Socks5Error(f'Таймаут {timeout}с при подключении к SOCKS5 {self._host}:{self._port}')
        return reader, writer

    async def ping(self, timeout: float = 5) -> bool:
        """
        Проверяет доступность SOCKS5-прокси (TCP + handshake без CONNECT).

        Returns True, если прокси ответил на handshake, иначе False.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=timeout,
            )
        except (OSError, ConnectionError, asyncio.TimeoutError):
            return False

        try:
            await self._handshake(reader, writer)
            return True
        except ProxyError:
            return False
        finally:
            writer.close()

    async def _handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """
        SOCKS5 method negotiation + аутентификация.

        Протокол:
          1. Клиент шлёт [ver=0x05, n_methods, methods...]
          2. Сервер отвечает [ver, chosen_method]
          3. Если chosen_method == 0x02 — клиент шлёт [up_ver=0x01, user_len, user, pass_len, pass]
          4. Сервер отвечает [up_ver, status] (0x00 = успех)

        Вызывает Socks5Error при ошибке.
        """
        # Шаг 1: отправляем список поддерживаемых методов аутентификации
        has_auth = bool(self._username and self._password)
        methods = [METHOD_NO_AUTH]
        if has_auth:
            methods.append(METHOD_USERPASS)

        msg = struct.pack('!BB', SOCKS5_VERSION, len(methods)) + bytes(methods)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('SOCKS5 >>> handshake: %s', msg.hex(' '))
        writer.write(msg)
        await writer.drain()

        # Шаг 2: читаем ответ сервера — выбранный метод
        resp = await reader.readexactly(2)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug('SOCKS5 <<< handshake: %s', resp.hex(' '))
        ver, method = struct.unpack('!BB', resp)
        if ver != SOCKS5_VERSION:
            raise Socks5Error(f'Неверная версия SOCKS: {ver}')

        # Шаг 3: если сервер выбрал username/password — отправляем учётные данные
        if method == METHOD_USERPASS and has_auth:
            username_bytes = self._username.encode()
            password_bytes = self._password.encode()
            auth_msg = (
                struct.pack('!B', USERPASS_VERSION) +
                struct.pack('!B', len(username_bytes)) +
                username_bytes +
                struct.pack('!B', len(password_bytes)) +
                password_bytes
            )
            logger.debug('SOCKS5 >>> auth: ***')
            writer.write(auth_msg)
            await writer.drain()

            # Шаг 4: читаем статус аутентификации
            auth_resp = await reader.readexactly(2)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('SOCKS5 <<< auth: %s', auth_resp.hex(' '))
            up_ver, up_status = struct.unpack('!BB', auth_resp)
            if up_status != USERPASS_SUCCESS:
                writer.close()
                raise Socks5Error('Ошибка аутентификации SOCKS5: неверный логин/пароль')

        elif method == METHOD_NO_AUTH:
            pass

        elif method == METHOD_NO_ACCEPTABLE:
            raise Socks5Error('SOCKS5: нет приемлемого метода аутентификации')

    async def _do_connect(
        self,
        target_host: str,
        target_port: int,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Внутренняя логика SOCKS5 CONNECT (без внешнего таймаута).

        Формат CONNECT-запроса:
          [ver=0x05, cmd=0x01, rsv=0x00, atyp, dst_addr, dst_port]

        atyp (address type):
          0x01 — IPv4 (4 байта)
          0x03 — доменное имя (1 байт длины + имя)

        Ответ сервера:
          [ver, rep, rsv, atyp, bind_addr, bind_port]
        """
        reader: asyncio.StreamReader
        writer: asyncio.StreamWriter

        # Шаг 1: TCP-подключение к прокси
        try:
            reader, writer = await asyncio.open_connection(self._host, self._port)
        except (OSError, ConnectionError) as e:
            raise Socks5Error(f'Не удалось подключиться к {self._host}:{self._port}: {e}')

        try:
            # Шаг 2: method negotiation + authentication
            await self._handshake(reader, writer)

            # Шаг 3: определяем тип адреса (IPv4 или домен)
            try:
                addr_bytes = socket.inet_aton(target_host)
                atyp = ATYP_IPV4
            except OSError:
                atyp = ATYP_DOMAIN
                target_host_bytes = target_host.encode()
                addr_bytes = bytes([len(target_host_bytes)]) + target_host_bytes

            # Шаг 4: отправляем CONNECT-запрос
            connect_msg = (
                struct.pack('!BBB', SOCKS5_VERSION, CMD_CONNECT, SOCKS5_RSV) +
                struct.pack('!B', atyp) +
                addr_bytes +
                struct.pack('!H', target_port)
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('SOCKS5 >>> connect (%s:%d): %s', target_host, target_port, connect_msg.hex(' '))
            writer.write(connect_msg)
            await writer.drain()

            # Шаг 5: читаем ответ на CONNECT (4 байта заголовка)
            header = await reader.readexactly(4)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('SOCKS5 <<< connect reply header: %s', header.hex(' '))
            ver, rep, rsv, atyp_resp = struct.unpack('!BBBB', header)
            if ver != SOCKS5_VERSION:
                raise Socks5Error(f'Неверная версия SOCKS в ответе: {ver}')

            # Шаг 6: проверяем код ответа
            if rep != SOCKS5_SUCCESS:
                errors = {
                    0x01: 'General SOCKS server failure',
                    0x02: 'Connection not allowed by ruleset',
                    0x03: 'Network unreachable',
                    0x04: 'Host unreachable',
                    0x05: 'Connection refused',
                    0x06: 'TTL expired',
                    0x07: 'Command not supported',
                    0x08: 'Address type not supported',
                }
                error_msg = errors.get(rep, f'Unknown error {rep}')
                raise Socks5Error(f'SOCKS5 CONNECT отказан: {error_msg}')

            # Шаг 7: пропускаем bind address (нас не интересует)
            if atyp_resp == ATYP_IPV4:
                await reader.readexactly(4 + 2)  # IPv4 (4) + port (2)
            elif atyp_resp == ATYP_DOMAIN:
                domain_len = (await reader.readexactly(1))[0]
                await reader.readexactly(domain_len + 2)  # domain + port
            else:
                await reader.readexactly(16 + 2)  # IPv6 (16) + port (2)

        except (OSError, ConnectionError, asyncio.IncompleteReadError) as e:
            writer.close()
            raise Socks5Error(f'Ошибка SOCKS5: {e}')

        return reader, writer
