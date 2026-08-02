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
    try:
        proxy = cfg.get_proxy_by_id(proxy_id)
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка загрузки конфига для пинга: %s', e)
        return {'alive': False, 'latency': None,
                'error': 'Не удалось загрузить конфигурацию. Проверьте подключение к бэкенду.'}

    if not proxy:
        return {'alive': False, 'latency': None, 'error': 'Прокси не найден'}

    start = time.monotonic()
    try:
        proto = get_protocol(proxy)
    except ValueError as e:
        logger.warning('Неизвестный тип прокси %s: %s', proxy.get('proxyId'), e)
        return {'alive': False, 'latency': None, 'error': f'Неизвестный тип прокси: {e}'}

    alive = await proto.ping(timeout=5)

    if not alive:
        return {'alive': False, 'latency': None}

    latency = int((time.monotonic() - start) * 1000)
    return {'alive': True, 'latency': latency}
