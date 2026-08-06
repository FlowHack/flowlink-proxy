"""
Парсинг HTTP CONNECT и plain HTTP запросов.

Содержит regex и функции для разбора входящих запросов прокси.
Единственная ответственность: парсинг протокола.
"""

import asyncio
import logging
import re

logger = logging.getLogger('flowlink.protocol_parser')

RE_CONNECT = re.compile(
    rb'^CONNECT\s+(?:\[([^\]]+)\]|([^\s:]+?)):(\d+)\s+HTTP/\d\.\d'
)
RE_HTTP = re.compile(
    rb'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)'
    rb'\s+(https?)://([^\s/]+)(/[^\s]*)\s+HTTP/\d\.\d'
)
# Максимальное количество заголовков (защита от slowloris)
_MAX_HEADER_LINES = 100
# Таймаут на чтение всех заголовков (секунды)
_HEADER_TIMEOUT = 5.0


def parse_connect(first_line: bytes) -> tuple[str, int] | None:
    """Парсит CONNECT host:port HTTP/1.x, возвращает (host, port) или None."""
    match = RE_CONNECT.match(first_line)
    if not match:
        return None
    host_bytes = match.group(1) if match.group(1) is not None else match.group(
        2
    )
    host = host_bytes.decode(errors='replace')
    port = int(match.group(3))
    return host, port


def parse_http(first_line: bytes) -> tuple[str, str, int, str, bytes] | None:
    """Парсит plain HTTP запрос, возвращает (method, host, port, path,
    relative_line) или None.

    Порт определяется по схеме (http→80, https→443), если он не указан
    явно в URL. Явный порт в формате host:port или [ipv6]:port
    имеет приоритет над значением по умолчанию.
    """
    match = RE_HTTP.match(first_line)
    if not match:
        return None
    method = match.group(1).decode()
    scheme = match.group(2).decode()
    host_port = match.group(3).decode()
    path = match.group(4).decode()

    # Разделяем host и необязательный порт. IPv6-адреса заключены
    # в квадратные скобки: [::1]:8080.
    if host_port.startswith('['):
        end = host_port.find(']')
        host = host_port[1:end] if end != -1 else host_port
        port_str = host_port[end + 1:] if end != -1 else ''
        port = int(port_str[1:]) if port_str.startswith(':') else None
    elif ':' in host_port:
        host, port_str = host_port.rsplit(':', 1)
        port = int(port_str) if port_str.isdigit() else None
    else:
        host = host_port
        port = None

    # Порт по умолчанию зависит от схемы: http→80, https→443
    if port is None:
        port = 443 if scheme == 'https' else 80

    relative_line = f'{method} {path} HTTP/1.1\r\n'.encode()
    return method, host, port, path, relative_line


async def skip_headers(reader: asyncio.StreamReader) -> None:
    """
    Читает и пропускает все HTTP-заголовки до пустой строки.

    Защита от slowloris-атаки:
    - Таймаут на общее время чтения заголовков (_HEADER_TIMEOUT).
    - Ограничение на количество заголовков (_MAX_HEADER_LINES).
    """
    try:
        for _ in range(_MAX_HEADER_LINES):
            line = await asyncio.wait_for(
                reader.readline(), timeout=_HEADER_TIMEOUT
            )
            if not line or line == b'\r\n':
                return
        logger.warning(
            'Превышено максимальное количество заголовков (%d)',
            _MAX_HEADER_LINES
        )
    except asyncio.TimeoutError:
        logger.warning(
            'Таймаут чтения HTTP-заголовков (%.1f сек)', _HEADER_TIMEOUT
        )
