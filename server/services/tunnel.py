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


async def _send_error(
    client_writer: asyncio.StreamWriter,
    url: str,
    message: str,
):
    """Логирует предупреждение и отправляет 502 Bad Gateway клиенту."""
    logger.warning(f'{message} для {url}')
    try:
        client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
        await client_writer.drain()
    except Exception:
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
        raise ValueError(f'Не удалось разрешить {host}: {e}')

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
        await _send_error(client_writer, url, f'{prefix}Ошибка SOCKS5 для {url} через {proxy_addr}: {error}')
    elif isinstance(error, (asyncio.TimeoutError, OSError, ConnectionError)):
        await _send_error(client_writer, url, f'{prefix}Ошибка соединения для {url} через {proxy_addr}: {error}')
    else:
        logger.error(f'{prefix}Неожиданная ошибка для {url} через {proxy_addr}: {error}')
        await _send_error(client_writer, url, f'{prefix}Ошибка для {url} через {proxy_addr}: {error}')


async def tunnel_connect(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target_host: str,
    target_port: int,
    url: str,
    proxy: dict | None = None,
):
    """Устанавливает HTTPS-туннель через SOCKS5 (если proxy) или напрямую."""
    proxy_addr = f'{proxy["host"]}:{proxy.get("port", 0)}' if proxy else 'direct'
    try:
        remote_reader, remote_writer = await _establish_remote(
            target_host=target_host,
            target_port=target_port,
            proxy=proxy,
        )

        client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        await client_writer.drain()

        logger.debug(f'Туннель {target_host}:{target_port} через {proxy_addr} установлен, начало передачи данных')
        await pipe(client_reader, client_writer, remote_reader, remote_writer)
        logger.debug(f'Туннель {target_host}:{target_port} через {proxy_addr} завершён')
    except Exception as e:
        await _handle_tunnel_error(client_writer, url, proxy_addr, e)


async def tunnel_http(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    target_host: str,
    target_port: int,
    url: str,
    relative_line: bytes,
    proxy: dict | None = None,
):
    """Пересылает plain HTTP запрос через SOCKS5 (если proxy) или напрямую."""
    proxy_addr = f'{proxy["host"]}:{proxy.get("port", 0)}' if proxy else 'direct'
    try:
        remote_reader, remote_writer = await _establish_remote(
            target_host=target_host,
            target_port=target_port,
            proxy=proxy,
        )

        remote_writer.write(relative_line)
        logger.debug(f'HTTP-запрос {url} отправлен через {proxy_addr}, ожидание ответа')
        await pipe_http_request(client_reader, remote_writer)
        await pipe_http_response(remote_reader, client_writer)
    except Exception as e:
        await _handle_tunnel_error(client_writer, url, proxy_addr, e, prefix='HTTP ')
