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
import ipaddress
from ipaddress import ip_address

from server.protocols import ProxyError, get_protocol
from server.services.pipe import pipe, pipe_http_request, pipe_http_response
from server.utils import proxy_addr, redact_url, safe_close_writer

logger = logging.getLogger('flowlink.tunnel')

# Трекинг ВСЕХ соединений через прокси-сервер (SOCKS5 + direct).
# При изменении правил маршрутизации соединения принудительно закрываются,
# чтобы Chrome переподключился и получил актуальную маршрутизацию.
_all_writers: set[asyncio.StreamWriter] = set()

# Трекинг активных SOCKS5-туннелей: proxy_id -> список remote_writer
_active_tunnels: dict[str, list[asyncio.StreamWriter]] = {}

# Трекинг клиентских (браузерных) соединений: proxy_id -> set[client_writer].
# Нужен для принудительного закрытия keep-alive CONNECT-туннелей браузера
# при выключении прокси или изменении правил маршрутизации.
_client_writers: dict[str, set[asyncio.StreamWriter]] = {}


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


def register_client_writer(proxy_id: str, writer: asyncio.StreamWriter) -> None:
    """Регистрирует клиентский writer для отслеживания keep-alive туннеля.

    Args:
        proxy_id: Идентификатор прокси (или None для direct-соединения).
        writer: asyncio StreamWriter клиентского соединения.
    """
    if proxy_id not in _client_writers:
        _client_writers[proxy_id] = set()
    _client_writers[proxy_id].add(writer)


def unregister_client_writer(proxy_id: str, writer: asyncio.StreamWriter) -> None:
    """Удаляет клиентский writer из отслеживаемых при завершении туннеля.

    Args:
        proxy_id: Идентификатор прокси.
        writer: asyncio StreamWriter клиентского соединения для удаления.
    """
    writers = _client_writers.get(proxy_id)
    if writers:
        writers.discard(writer)
        if not writers:
            _client_writers.pop(proxy_id, None)


def close_tunnels_for_proxy(proxy_id: str) -> None:
    """Принудительно закрывает все активные туннели указанного прокси.

    Закрывает и upstream-соединения (к SOCKS5-прокси), и клиентские
    keep-alive CONNECT-туннели браузера, чтобы Chrome переподключился
    и получил актуальную маршрутизацию.

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

    # Закрываем клиентские keep-alive туннели браузера
    client_writers = _client_writers.pop(proxy_id, set())
    for cw in client_writers:
        try:
            cw.close()
        except OSError as e:
            logger.debug('Туннель: ошибка закрытия клиентского writer '
                         'прокси %s: %s', proxy_id, e)


def close_all_proxy_tunnels() -> None:
    """Закрывает все активные прокси-туннели (при глобальном выключении)."""
    for pid in list(_active_tunnels.keys()):
        close_tunnels_for_proxy(pid)


def close_all_connections() -> None:
    """Закрывает ВСЕ соединения через прокси-сервер (прокси + direct).

    Очищает все трекеры: _all_writers (все удалённые соединения),
    _active_tunnels (SOCKS5-туннели по proxy_id) и _client_writers
    (клиентские keep-alive туннели браузера).
    """
    for w in list(_all_writers):
        try:
            w.close()
        except OSError as e:
            logger.debug('Туннель: ошибка закрытия writer при глобальном '
                         'закрытии соединений: %s', e)
    _all_writers.clear()
    _active_tunnels.clear()

    # Закрываем все клиентские keep-alive туннели браузера
    for cw in list(_client_writers.values()):
        for writer in cw:
            try:
                writer.close()
            except OSError as e:
                logger.debug('Туннель: ошибка закрытия клиентского writer '
                             'при глобальном закрытии соединений: %s', e)
    _client_writers.clear()


async def _send_error(
    client_writer: asyncio.StreamWriter,
    url: str,
    message: str,
) -> None:
    """Логирует предупреждение и отправляет 502 Bad Gateway клиенту.

    Args:
        client_writer: Поток записи клиенту для отправки ответа.
        url: URL запроса, для которого формируется ошибка (используется в логе).
        message: Текст сообщения об ошибке.

    Returns:
        None.
    """
    logger.warning('%s для %s', message, redact_url(url))
    try:
        client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
        await client_writer.drain()
    except (OSError, ConnectionError) as e:
        logger.debug('Не удалось отправить 502 клиенту (%s): %s', redact_url(url), e)


def _is_blocked_address(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Проверяет, является ли адрес заблокированным для SSRF-защиты.

    Args:
        addr: IP-адрес для проверки.

    Returns:
        True, если адрес заблокирован, False в противном случае.
    """
    broadcast_addr = ip_address('255.255.255.255')
    return (
        addr.is_private or addr.is_loopback or addr.is_link_local
        or addr.is_unspecified or addr == broadcast_addr
        or (addr.version == 6 and addr.ipv4_mapped is not None)
        or addr.is_multicast or addr.is_reserved
    )


async def validate_target(host: str, port: int) -> list[str]:
    """
    Проверяет, что целевой хост не является приватным/локальным IP (SSRF-защита).

    Разрешает доменное имя вручную и отклоняет запросы к:
      - 127.0.0.0/8 (loopback)
      - 10.0.0.0/8 (private)
      - 172.16.0.0/12 (private)
      - 192.168.0.0/16 (private)
      - 169.254.0.0/16 (link-local)
      - ::1 (IPv6 loopback)
      - 0.0.0.0 и :: (unspecified — ведут на localhost)
      - 255.255.255.255 (ограниченный broadcast)
      - IPv4-mapped IPv6 (например, ::ffff:127.0.0.1)
      - multicast и reserved адреса

    Args:
        host: Целевой хост (IP или домен).
        port: Целевой порт.

    Returns:
        Список проверенных IP-адресов, разрешенных для подключения.

    Raises:
        ValueError: если хост резолвится в приватный/локальный/недопустимый IP.
    """
    loop = asyncio.get_running_loop()
    try:
        addrs = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ValueError(f'Не удалось разрешить {host}: {e}') from e
    except (UnicodeError, OverflowError) as e:
        raise ValueError(f'Некорректный хост или порт: {host}:{port} — {e}') from e

    # 255.255.255.255 — ограниченный broadcast: у него все флаги
    # ipaddress равны False, но адрес указывает на локальный стек.
    validated_ips = []

    for _, _, _, _, sockaddr in addrs:
        ip = sockaddr[0]
        try:
            addr = ip_address(ip)
            if _is_blocked_address(addr):
                raise ValueError(
                    f'SSRF заблокирован: {host} резолвится в недопустимый адрес {ip}'
                )
            validated_ips.append(ip)
        except ValueError as e:
            if 'SSRF' in str(e):
                raise
            continue  # невалидный IP — пропускаем

    if not validated_ips:
        raise ValueError(f'SSRF заблокирован: {host} не имеет допустимых IP-адресов')
    return validated_ips


async def _establish_remote(
    target_host: str,
    target_port: int,
    proxy: dict | None = None,
    timeout: float = 10,
    validated_ip: str | None = None,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Создаёт соединение до цели через прокси (если proxy) или напрямую.

    Args:
        target_host: Целевой хост (IP или домен).
        target_port: Целевой порт.
        proxy: Конфигурация прокси. Если None — прямое соединение.
        timeout: Таймаут установки соединения, секунд.
        validated_ip: Предварительно проверенный IP-адрес (для прямого соединения).

    Returns:
        Кортеж (reader, writer) для обмена данными с целью.

    Raises:
        ProxyError: при ошибке SOCKS5-соединения через прокси.
        TimeoutError/OSError: при недоступности цели или истечении таймаута.
    """
    if proxy:
        proto = get_protocol(proxy)
        return await proto.connect(target_host, target_port, timeout=timeout)
    if validated_ip:
        return await asyncio.wait_for(
            asyncio.open_connection(validated_ip, target_port),
            timeout=timeout,
        )
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
    """Логирует и отправляет 502 при ошибке туннеля.

    Args:
        client_writer: Поток записи клиенту для отправки 502.
        url: URL запроса (для логов и сообщения об ошибке).
        proxy_addr_str: Описание прокси (например, 'proxy 1.2.3.4:8080').
        error: Перехваченное исключение.
        prefix: Дополнительный префикс к сообщению (например, 'CONNECT ').

    Returns:
        None. Все ошибки логируются внутри и наружу не пробрасываются.
    """
    safe_url = redact_url(url)
    if isinstance(error, ProxyError):
        msg = f'{prefix}Ошибка SOCKS5 для {safe_url} через {proxy_addr_str}: {error}'
        await _send_error(client_writer, url, msg)
    elif isinstance(error, (asyncio.TimeoutError, OSError, ConnectionError)):
        msg = (f'{prefix}Ошибка соединения для {safe_url} '
               f'через {proxy_addr_str}: {error}')
        await _send_error(client_writer, url, msg)
    else:
        logger.error(
            '%sНеожиданная ошибка для %s через %s: %s',
            prefix, safe_url, proxy_addr_str, error,
        )
        msg = f'{prefix}Ошибка для {safe_url} через {proxy_addr_str}: {error}'
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
        validated_ips = None
        if not proxy:
            validated_ips = await validate_target(target_host, target_port)
        remote_reader, remote_writer = await _establish_remote(
            target_host=target_host,
            target_port=target_port,
            proxy=proxy,
            validated_ip=validated_ips[0] if validated_ips else None,
        )

        _all_writers.add(remote_writer)
        if proxy_id:
            register_tunnel(proxy_id, remote_writer)
            register_client_writer(proxy_id, _client_writer)

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
                unregister_client_writer(proxy_id, _client_writer)
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
    # Значения по умолчанию на случай ошибки ДО yield в _tunnel_context:
    # тогда proxy_addr_str/target_host/target_port не присваиваются,
    # но используются в except-блоке.
    proxy_addr_str = proxy_addr(proxy, 'direct')
    target_host, target_port = target
    try:
        async with _tunnel_context(
            client, target, url, proxy,
        ) as (remote_reader, remote_writer, proxy_addr_str):
            client_reader, client_writer = client

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
    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError) as e:
        # Ошибка соединения уже обработана внутри _tunnel_context
        # (клиенту отправлен 502). Здесь перехватываем перевыброшенную
        # ошибку, чтобы не логировать её как неожиданную в proxy.py.
        # Ошибки ПОСЛЕ yield (обрыв при передаче данных) не проходят через
        # except генератора — логируем их здесь на debug-уровне.
        logger.debug(
            'Туннель %s:%s через %s прерван: %s',
            target_host, target_port, proxy_addr_str, e,
        )


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
    except (ProxyError, asyncio.TimeoutError, OSError, ConnectionError) as e:
        # Ошибка соединения уже обработана внутри _tunnel_context
        # (клиенту отправлен 502). Здесь перехватываем перевыброшенную
        # ошибку, чтобы не логировать её как неожиданную в proxy.py.
        # Ошибки ПОСЛЕ yield (обрыв при передаче данных) не проходят через
        # except генератора — логируем их здесь на debug-уровне.
        logger.debug(
            'HTTP-туннель для %s прерван: %s',
            redact_url(url), e,
        )
