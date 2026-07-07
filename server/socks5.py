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


class Socks5Error(Exception):
    """Ошибка SOCKS5 соединения."""
    pass


async def _recv_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    data = await reader.readexactly(n)
    return data


async def socks5_connect(
    proxy_host: str,
    proxy_port: int,
    target_host: str,
    target_port: int,
    username: str = '',
    password: str = '',
    timeout: float = 10.0
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """
    Устанавливает SOCKS5-туннель до target_host:target_port через прокси.

    Args:
        proxy_host: IP или домен SOCKS5-прокси.
        proxy_port: Порт SOCKS5-прокси.
        target_host: Целевой хост для CONNECT.
        target_port: Целевой порт для CONNECT.
        username: Имя пользователя (если нужна auth).
        password: Пароль (если нужна auth).
        timeout: Таймаут на всё соединение.

    Returns:
        (reader, writer) — асинхронный поток для передачи данных.

    Raises:
        Socks5Error: при ошибке handshake.
        asyncio.TimeoutError: при превышении таймаута.
    """
    try:
        return await asyncio.wait_for(
            _do_socks5_connect(proxy_host, proxy_port, target_host, target_port, username, password),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        raise Socks5Error(f'Таймаут {timeout}с при подключении к SOCKS5 {proxy_host}:{proxy_port}')


async def _do_socks5_connect(
    proxy_host: str,
    proxy_port: int,
    target_host: str,
    target_port: int,
    username: str = '',
    password: str = ''
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:

    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    try:
        reader, writer = await asyncio.open_connection(proxy_host, proxy_port)
    except (OSError, ConnectionError) as e:
        raise Socks5Error(f'Не удалось подключиться к {proxy_host}:{proxy_port}: {e}')

    try:
        has_auth = bool(username and password)
        methods = [METHOD_NO_AUTH]
        if has_auth:
            methods.append(METHOD_USERPASS)

        msg = struct.pack('!BB', SOCKS5_VERSION, len(methods)) + bytes(methods)
        writer.write(msg)
        await writer.drain()

        ver, method = struct.unpack('!BB', await _recv_exact(reader, 2))
        logger.debug(f'SOCKS5 handshake: предложены методы={methods}, сервер выбрал={method}')
        if ver != SOCKS5_VERSION:
            raise Socks5Error(f'Неверная версия SOCKS: {ver}')

        if method == METHOD_USERPASS and has_auth:
            username_bytes = username.encode()
            password_bytes = password.encode()
            logger.debug(f'SOCKS5 auth: username="{username}" password_len={len(password)}')
            auth_msg = (
                struct.pack('!B', USERPASS_VERSION) +
                struct.pack('!B', len(username_bytes)) +
                username_bytes +
                struct.pack('!B', len(password_bytes)) +
                password_bytes
            )
            writer.write(auth_msg)
            await writer.drain()

            up_ver, up_status = struct.unpack('!BB', await _recv_exact(reader, 2))
            logger.debug(f'SOCKS5 auth response: status={up_status}')
            if up_status != USERPASS_SUCCESS:
                raise Socks5Error('Ошибка аутентификации SOCKS5: неверный логин/пароль')

        elif method == METHOD_NO_AUTH:
            pass

        elif method == METHOD_NO_ACCEPTABLE:
            raise Socks5Error('SOCKS5: нет приемлемого метода аутентификации')

        target_host_bytes = target_host.encode()

        if target_host_bytes and all(c in b'.' or 48 <= c <= 57 for c in target_host_bytes) and target_host_bytes[0] != 0:
            atyp = ATYP_IPV4
            try:
                addr_bytes = socket.inet_aton(target_host)
            except OSError:
                atyp = ATYP_DOMAIN
                addr_bytes = bytes([len(target_host_bytes)]) + target_host_bytes
        else:
            atyp = ATYP_DOMAIN
            addr_bytes = bytes([len(target_host_bytes)]) + target_host_bytes

        connect_msg = (
            struct.pack('!BBB', SOCKS5_VERSION, CMD_CONNECT, SOCKS5_RSV) +
            struct.pack('!B', atyp) +
            addr_bytes +
            struct.pack('!H', target_port)
        )
        writer.write(connect_msg)
        await writer.drain()

        header = await _recv_exact(reader, 4)
        ver, rep, rsv, atyp_resp = struct.unpack('!BBBB', header)
        if ver != SOCKS5_VERSION:
            raise Socks5Error(f'Неверная версия SOCKS в ответе: {ver}')

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

        if atyp_resp == ATYP_IPV4:
            await _recv_exact(reader, 4 + 2)
        elif atyp_resp == ATYP_DOMAIN:
            domain_len = (await _recv_exact(reader, 1))[0]
            await _recv_exact(reader, domain_len + 2)
        else:
            await _recv_exact(reader, 16 + 2)

    except (OSError, ConnectionError, asyncio.IncompleteReadError) as e:
        writer.close()
        raise Socks5Error(f'Ошибка SOCKS5: {e}')

    return reader, writer
