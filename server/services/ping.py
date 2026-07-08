"""
Проверка доступности SOCKS5 прокси (ping).

Единственная ответственность: поиск прокси по ID, замер latency, возврат результата.
"""

import logging
import time

from server.config import config as cfg
from server.protocols import get_protocol

logger = logging.getLogger('flowlink.ping')


async def ping_proxy(proxy_id: str) -> dict:
    """
    Пингует прокси по его proxyId.

    Ищет прокси в конфиге, выполняет handshake (через протокольную фабрику)
    и замеряет время отклика.

    Returns:
        Словарь с полями: alive (bool), latency (int | None), error (str | None).
    """
    proxies = cfg.get_all_proxies()
    proxy = None
    for p in proxies:
        if p.get('proxyId') == proxy_id:
            proxy = p
            break

    if not proxy:
        return {'alive': False, 'latency': None, 'error': 'Proxy not found'}

    start = time.monotonic()
    proto = get_protocol(proxy)
    alive = await proto.ping(timeout=5)

    if not alive:
        return {'alive': False, 'latency': None}

    latency = int((time.monotonic() - start) * 1000)
    return {'alive': True, 'latency': latency}
