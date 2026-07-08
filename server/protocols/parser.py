"""
Парсинг HTTP CONNECT и plain HTTP запросов.

Содержит regex и функции для разбора входящих запросов прокси.
Единственная ответственность: парсинг протокола.
"""

import asyncio
import logging
import re

logger = logging.getLogger('flowlink.protocol_parser')

RE_CONNECT = re.compile(rb'^CONNECT\s+(?:\[([^\]]+)\]|([^\s:]+?)):(\d+)\s+HTTP/\d\.\d')
RE_HTTP = re.compile(rb'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+https?://([^\s/]+)(:\d+)?(/[^\s]*)\s+HTTP/\d\.\d')


def parse_connect(first_line: bytes) -> tuple[str, int] | None:
    """Парсит CONNECT host:port HTTP/1.x, возвращает (host, port) или None."""
    match = RE_CONNECT.match(first_line)
    if not match:
        return None
    host_bytes = match.group(1) if match.group(1) is not None else match.group(2)
    host = host_bytes.decode(errors='replace')
    port = int(match.group(3))
    return host, port


def parse_http(first_line: bytes) -> tuple[str, str, int, str, str] | None:
    """Парсит plain HTTP запрос, возвращает (method, host, port, path, relative_line) или None."""
    match = RE_HTTP.match(first_line)
    if not match:
        return None
    method = match.group(1).decode()
    host = match.group(2).decode()
    port_str = match.group(3)
    path = match.group(4).decode()
    port = int(port_str[1:]) if port_str else 80
    relative_line = f'{method} {path} HTTP/1.1\r\n'.encode()
    return method, host, port, path, relative_line


async def skip_headers(reader: asyncio.StreamReader):
    """Читает и пропускает все HTTP-заголовки до пустой строки."""
    while True:
        line = await reader.readline()
        if not line or line == b'\r\n':
            break
