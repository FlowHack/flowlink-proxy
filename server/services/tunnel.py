"""
Установка туннелей через SOCKS5 или напрямую.

Содержит 2 публичные функции (tunnel_connect, tunnel_http) и вспомогательные
приватные функции. Единственная ответственность: установка и обслуживание туннелей.
"""

import asyncio
import logging
import socket
from ipaddress import ip_address

from server.protocols import ProxyError, get_protocol
from server.services.pipe import pipe, pipe_http_request, pipe_http_response

logger = logging.getLogger('flowlink.tunnel')

# Трекинг ВСЕХ соединений через прокси-сервер (SOCKS5 + direct).
# При изменении правил маршрутизации соединения принудительно закрываются,
# чтобы Chrome переподключился и получил актуальную маршрутизацию.
_all_writers: set[asyncio.StreamWriter] = set()

# Трекинг активных SOCKS5-туннелей: proxy_id -> список remote_writer
_active_tunnels: dict[str, list[asyncio.StreamWriter]] = {}


def register_tunnel(proxy_id: str, writer: asyncio.StreamWriter):
    """Регистрирует remote writer для отслеживания активного туннеля."""
    if proxy_id not in _active_tunnels:
        _active_tunnels[proxy_id] = []
    _active_tunnels[proxy_id].append(writer)


def unregister_tunnel(proxy_id: str, writer: asyncio.StreamWriter):
    """Удаляет writer из отслеживаемых при штатном завершении туннеля."""
    writers = _active_tunnels.get(proxy_id)
    if writers:
        try:
            writers.remove(writer)
        except ValueError:
            pass
        if not writers:
            _active_tunnels.pop(proxy_id, None)


def close_tunnels_for_proxy(proxy_id: str):
    """Принудительно закрывает все активные туннели указанного прокси."""
    writers = _active_tunnels.pop(proxy_id, [])
    for w in writers:
        try:
            w.close()
        except OSError:
            pass
        _all_writers.discard(w)


def close_all_proxy_tunnels():
    """Закрывает все активные прокси-туннели (при глобальном выключении)."""
    for pid in list(_active_tunnels.keys()):
        close_tunnels_for_proxy(pid)


def close_all_connections():
    """Закрывает ВСЕ соединения через прокси-сервер (прокси + direct)."""
    for w in list(_all_writers):
        try:
            w.close()
        except OSError:
            pass
    _all_writers.clear()
    _active_tunnels.clear()


async def _send_error(
    client_writer: asyncio.StreamWriter,
    url: str,
    message: str,
):
    """Логирует предупреждение и отправляет 502 Bad Gateway клиенту."""
    logger.warning('%s для %s', message, url)
    try:
        client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
        await client_writer.drain()
    except (OSError, ConnectionError):
        pass


async def validate_target(host: str, port: int):
    """
    Проверяет, что целевой хост не является приватным/локальным IP (SSRF-защита).

    Разрешает доменное имя вручную и отклоняет запросы к:
      - 127.0.0.0/8 (loopback)
      - 10.0.0.0/8 (private)
      - 172.16.0.0/12 (private)
      - 192.168.0.0/16 (private)
      - 169.254.0.0/16 (link-local)
      - ::1 (IPv6 loopback)

    Args:
        host: Целевой хост (IP или домен).
        port: Целевой порт.

    Raises:
        ValueError: если хост резолвится в приватный IP.
    """
    loop = asyncio.get_running_loop()
    try:
        addrs = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f'Не удалось разрешить {host}: {e}') from e

    for _, _, _, _, sockaddr in addrs:
        ip = sockaddr[0]
        try:
            addr = ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                raise ValueError(f'SSRF blocked: {host} resolves to private IP {ip}')
        except ValueError as e:
            if 'SSRF blocked' in str(e):
                raise
            continue  # невалидный IP — пропускаем


async def _establish_remote(
    target_host: str,
    target_port: int,
    proxy: dict | None = None,
    timeout: float = 10,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Создаёт соединение до цели через прокси (если proxy) или напрямую."""
    if proxy:
        proto = get_protocol(proxy)
        return await proto.connect(target_host, target_port, timeout=timeout)
    return await asyncio.wait_for(
        asyncio.open_connection(target_host, target_port),
        timeout=timeout,
    )


async def _handle_tunnel_error(
    client_writer: asyncio.StreamWriter,
    url: str,
    proxy_addr: str,
    error: Exception,
    prefix: str = '',
):
    """Логирует и отправляет 502 при ошибке туннеля."""
    if isinstance(error, ProxyError):
        msg = f'{prefix}Ошибка SOCKS5 для {url} через {proxy_addr}: {error}'
        await _send_error(client_writer, url, msg)
    elif isinstance(error, (asyncio.TimeoutError, OSError, ConnectionError)):
        msg = f'{prefix}Ошибка соединения для {url} через {proxy_addr}: {error}'
        await _send_error(client_writer, url, msg)
    else:
        logger.error(
            '%sНеожиданная ошибка для %s через %s: %s',
            prefix, url, proxy_addr, error,
        )
        msg = f'{prefix}Ошибка для {url} через {proxy_addr}: {error}'
        await _send_error(client_writer, url, msg)


async def tunnel_connect(
    client: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    target: tuple[str, int],
    url: str,
    proxy: dict | None = None,
):
    """Устанавливает HTTPS-туннель через SOCKS5 (если proxy) или напрямую."""
    client_reader, client_writer = client
    target_host, target_port = target
    proxy_addr = f'{proxy["host"]}:{proxy.get("port", 0)}' if proxy else 'direct'
    proxy_id = proxy.get('proxyId') if proxy else None
    remote_writer = None
    try:
        remote_reader, remote_writer = await _establish_remote(
            target_host=target_host,
            target_port=target_port,
            proxy=proxy,
        )

        _all_writers.add(remote_writer)
        if proxy_id:
            register_tunnel(proxy_id, remote_writer)

        client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await client_writer.drain()

        logger.debug(
            'Туннель %s:%s через %s установлен, начало передачи данных',
            target_host, target_port, proxy_addr,
        )
        await pipe(client_reader, client_writer, remote_reader, remote_writer)
        logger.debug(
            'Туннель %s:%s через %s завершён',
            target_host, target_port, proxy_addr,
        )
    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError) as e:
        await _handle_tunnel_error(client_writer, url, proxy_addr, e)
    finally:
        if remote_writer:
            _all_writers.discard(remote_writer)
            if proxy_id:
                unregister_tunnel(proxy_id, remote_writer)


async def tunnel_http(
    client: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    target: tuple[str, int],
    url: str,
    relative_line: bytes,
    proxy: dict | None = None,
):
    """Пересылает plain HTTP запрос через SOCKS5 (если proxy) или напрямую."""
    client_reader, client_writer = client
    target_host, target_port = target
    proxy_addr = f'{proxy["host"]}:{proxy.get("port", 0)}' if proxy else 'direct'
    proxy_id = proxy.get('proxyId') if proxy else None
    remote_writer = None
    try:
        remote_reader, remote_writer = await _establish_remote(
            target_host=target_host,
            target_port=target_port,
            proxy=proxy,
        )

        _all_writers.add(remote_writer)
        if proxy_id:
            register_tunnel(proxy_id, remote_writer)

        remote_writer.write(relative_line)
        logger.debug(
            'HTTP-запрос %s отправлен через %s, ожидание ответа',
            url, proxy_addr,
        )
        await pipe_http_request(client_reader, remote_writer)
        await pipe_http_response(remote_reader, client_writer)
    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError) as e:
        await _handle_tunnel_error(client_writer, url, proxy_addr, e, prefix='HTTP ')
    finally:
        if remote_writer:
            _all_writers.discard(remote_writer)
            if proxy_id:
                unregister_tunnel(proxy_id, remote_writer)
