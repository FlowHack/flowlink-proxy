"""
Установка туннелей через SOCKS5 или напрямую.

Содержит 2 публичные функции (tunnel_connect, tunnel_http) и вспомогательные
приватные функции. Единственная ответственность: установка и обслуживание туннелей.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from ipaddress import ip_address

from server.protocols import ProxyError, get_protocol
from server.services.pipe import pipe, pipe_http_request, pipe_http_response
from server.utils import proxy_addr, safe_close_writer

logger = logging.getLogger('flowlink.tunnel')

# Трекинг ВСЕХ соединений через прокси-сервер (SOCKS5 + direct).
# При изменении правил маршрутизации соединения принудительно закрываются,
# чтобы Chrome переподключился и получил актуальную маршрутизацию.
_all_writers: set[asyncio.StreamWriter] = set()

# Трекинг активных SOCKS5-туннелей: proxy_id -> список remote_writer
_active_tunnels: dict[str, list[asyncio.StreamWriter]] = {}


def register_tunnel(proxy_id: str, writer: asyncio.StreamWriter) -> None:
    """Регистрирует remote writer для отслеживания активного туннеля.

    Args:
        proxy_id: Идентификатор прокси.
        writer: asyncio StreamWriter удалённого соединения.
    """
    if proxy_id not in _active_tunnels:
        _active_tunnels[proxy_id] = []
    _active_tunnels[proxy_id].append(writer)


def unregister_tunnel(proxy_id: str, writer: asyncio.StreamWriter) -> None:
    """Удаляет writer из отслеживаемых при штатном завершении туннеля.

    Args:
        proxy_id: Идентификатор прокси.
        writer: asyncio StreamWriter удалённого соединения для удаления.
    """
    writers = _active_tunnels.get(proxy_id)
    if writers:
        try:
            writers.remove(writer)
        except ValueError:
            logger.debug(
                'Туннель: writer не найден в списке активных туннелей '
                'для прокси %s',
                proxy_id,
            )
        if not writers:
            _active_tunnels.pop(proxy_id, None)


def close_tunnels_for_proxy(proxy_id: str) -> None:
    """Принудительно закрывает все активные туннели указанного прокси.

    Args:
        proxy_id: Идентификатор прокси, чьи туннели нужно закрыть.
    """
    writers = _active_tunnels.pop(proxy_id, [])
    for w in writers:
        try:
            w.close()
        except OSError as e:
            logger.debug('Туннель: ошибка закрытия writer прокси %s: %s',
                         proxy_id, e)
        _all_writers.discard(w)


def close_all_proxy_tunnels() -> None:
    """Закрывает все активные прокси-туннели (при глобальном выключении)."""
    for pid in list(_active_tunnels.keys()):
        close_tunnels_for_proxy(pid)


def close_all_connections() -> None:
    """Закрывает ВСЕ соединения через прокси-сервер (прокси + direct).

    Очищает оба трекера: _all_writers (все удалённые соединения)
    и _active_tunnels (SOCKS5-туннели по proxy_id).
    """
    for w in list(_all_writers):
        try:
            w.close()
        except OSError as e:
            logger.debug('Туннель: ошибка закрытия writer при глобальном '
                         'закрытии соединений: %s', e)
    _all_writers.clear()
    _active_tunnels.clear()


async def _send_error(
    client_writer: asyncio.StreamWriter,
    url: str,
    message: str,
) -> None:
    """Логирует предупреждение и отправляет 502 Bad Gateway клиенту."""
    logger.warning('%s для %s', message, url)
    try:
        client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
        await client_writer.drain()
    except (OSError, ConnectionError) as e:
        logger.debug('Не удалось отправить 502 клиенту (%s): %s', url, e)


async def validate_target(host: str, port: int) -> None:
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
    except (UnicodeError, OverflowError) as e:
        raise ValueError(f'Некорректный хост или порт: {host}:{port} — {e}') from e

    for _, _, _, _, sockaddr in addrs:
        ip = sockaddr[0]
        try:
            addr = ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                raise ValueError(f'SSRF заблокирован: {host} резолвится в приватный IP {ip}')
        except ValueError as e:
            if 'SSRF' in str(e):
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
    proxy_addr_str: str,
    error: Exception,
    prefix: str = '',
) -> None:
    """Логирует и отправляет 502 при ошибке туннеля."""
    if isinstance(error, ProxyError):
        msg = f'{prefix}Ошибка SOCKS5 для {url} через {proxy_addr_str}: {error}'
        await _send_error(client_writer, url, msg)
    elif isinstance(error, (asyncio.TimeoutError, OSError, ConnectionError)):
        msg = (f'{prefix}Ошибка соединения для {url} '
               f'через {proxy_addr_str}: {error}')
        await _send_error(client_writer, url, msg)
    else:
        logger.error(
            '%sНеожиданная ошибка для %s через %s: %s',
            prefix, url, proxy_addr_str, error,
        )
        msg = f'{prefix}Ошибка для {url} через {proxy_addr_str}: {error}'
        await _send_error(client_writer, url, msg)


@asynccontextmanager
async def _tunnel_context(
    client: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    target: tuple[str, int],
    url: str,
    proxy: dict | None = None,
    prefix: str = '',
) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter, str]]:
    """Контекстный менеджер для lifecycle туннеля (SOCKS5 или direct).

    Обеспечивает:
    - Установку удалённого соединения (через прокси или напрямую)
    - Регистрацию в трекерах (_all_writers, _active_tunnels)
    - Обработку ошибок соединения (ProxyError, TimeoutError, OSError)
    - Автоматическую очистку при завершении (finally)

    Args:
        client: Кортеж (reader, writer) клиента.
        target: Кортеж (host, port) целевого сервера.
        url: URL запроса (для логирования).
        proxy: Конфиг прокси или None для direct-соединения.
        prefix: Префикс для сообщений об ошибках.

    Yields:
        Кортеж (remote_reader, remote_writer, proxy_addr).

    Raises:
        ProxyError, asyncio.TimeoutError, OSError, ConnectionError:
            при ошибке установки или передачи данных.
    """
    _client_writer = client[1]
    target_host, target_port = target
    proxy_addr_str = proxy_addr(proxy, 'direct')
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

        yield remote_reader, remote_writer, proxy_addr_str

    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError, ValueError) as e:
        # Ошибка ДО первого yield: asynccontextmanager требует, чтобы
        # первый __anext__ дошёл до yield. Если исключение проглотить,
        # __aenter__ бросит RuntimeError "generator didn't yield".
        # Поэтому после отправки 502 клиенту — перевыбрасываем ошибку.
        await _handle_tunnel_error(_client_writer, url, proxy_addr_str, e, prefix)
        raise
    finally:
        if remote_writer:
            _all_writers.discard(remote_writer)
            if proxy_id:
                unregister_tunnel(proxy_id, remote_writer)
            # Закрываем удалённый writer в ЛЮБОМ случае. Если клиент оборвал
            # соединение до pipe (writer.write/drain упали), remote_writer уже
            # удалён из трекеров, но остаётся открытым — без закрытия это
            # утечка TCP-соединения. safe_close_writer идемпотентен:
            # повторное закрытие уже закрытого writer безопасно.
            safe_close_writer(remote_writer)


async def tunnel_connect(
    client: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    target: tuple[str, int],
    url: str,
    proxy: dict | None = None,
) -> None:
    """Устанавливает HTTPS-туннель через SOCKS5 (если proxy) или напрямую."""
    try:
        async with _tunnel_context(
            client, target, url, proxy,
        ) as (remote_reader, remote_writer, proxy_addr_str):
            client_reader, client_writer = client
            target_host, target_port = target

            client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await client_writer.drain()

            logger.debug(
                'Туннель %s:%s через %s установлен, начало передачи данных',
                target_host, target_port, proxy_addr_str,
            )
            await pipe(client_reader, client_writer, remote_reader, remote_writer)
            logger.debug(
                'Туннель %s:%s через %s завершён',
                target_host, target_port, proxy_addr_str,
            )
    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError):
        # Ошибка соединения уже обработана внутри _tunnel_context
        # (клиенту отправлен 502). Здесь перехватываем перевыброшенную
        # ошибку, чтобы не логировать её как неожиданную в proxy.py.
        pass


async def tunnel_http(
    client: tuple[asyncio.StreamReader, asyncio.StreamWriter],
    target: tuple[str, int],
    url: str,
    relative_line: bytes,
    proxy: dict | None = None,
) -> None:
    """Пересылает plain HTTP запрос через SOCKS5 (если proxy) или напрямую."""
    try:
        async with _tunnel_context(
            client, target, url, proxy, prefix='HTTP ',
        ) as (remote_reader, remote_writer, proxy_addr_str):
            client_reader, client_writer = client

            remote_writer.write(relative_line)
            logger.debug(
                'HTTP-запрос %s отправлен через %s, ожидание ответа',
                url, proxy_addr_str,
            )
            await pipe_http_request(client_reader, remote_writer)
            await pipe_http_response(remote_reader, client_writer)
    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError):
        # Ошибка соединения уже обработана внутри _tunnel_context
        # (клиенту отправлен 502). Здесь перехватываем перевыброшенную
        # ошибку, чтобы не логировать её как неожиданную в proxy.py.
        pass
