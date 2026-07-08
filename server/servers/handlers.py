"""
Обработчики API-эндпоинтов FlowLink Proxy.

Каждая функция обрабатывает один эндпоинт.
Единственная ответственность: бизнес-логика API.
"""

import logging

from server.config import config as cfg
from server.services.ping import ping_proxy
from server.services.router import MaskRouter
from server.services.debug import log_config_state
from server.services.events import emit_event
from server.version import __version__ as server_version

logger = logging.getLogger('flowlink.api')


def _diff_proxies(old_proxies: dict, new_proxies: dict):
    """Логирует добавленные, изменённые и удалённые прокси."""
    for pid, p in new_proxies.items():
        addr = f'{p["host"]}:{p["port"]}'
        if pid not in old_proxies:
            logger.info('Добавлен прокси %s', addr)
        else:
            old = old_proxies[pid]
            if old.get('host') != p['host'] or old.get('port') != p['port']:
                logger.info('Изменён прокси %s', addr)
    for pid, p in old_proxies.items():
        if pid not in new_proxies:
            logger.info('Удалён прокси %s', p['host'] + ':' + str(p['port']))


def _diff_masks(old_masks: dict, new_masks: dict):
    """Логирует добавленные и удалённые маски."""
    for mid, m in new_masks.items():
        if mid not in old_masks:
            logger.info('Добавлена маска %s для прокси %s', m.get('regexString', '?'), m.get('proxyId', '?'))
    for mid, m in old_masks.items():
        if mid not in new_masks:
            logger.info('Удалена маска %s', m.get('regexString', '?'))


def handle_get_config() -> dict:
    """GET /api/config — возвращает текущую конфигурацию (с isEnabled из памяти)."""
    data = cfg.load_config()
    data['isEnabled'] = cfg.is_enabled()
    return data


async def handle_post_config(data: dict, router: MaskRouter) -> dict:
    """POST /api/config — обновляет конфигурацию и перезагружает маршруты."""
    old_data = cfg.load_config()
    old_proxies = {}
    for p in old_data.get('proxies', []):
        pid = p.get('proxyId')
        if pid:
            old_proxies[pid] = p
    old_masks = {}
    for m in old_data.get('masks', []):
        mid = m.get('maskId')
        if mid:
            old_masks[mid] = m

    if not isinstance(data, dict):
        raise ValueError('Тело запроса должно быть JSON-объектом')

    # Если в данных есть isEnabled — применяем отдельно (хранится в памяти)
    if 'isEnabled' in data:
        cfg.set_enabled(data['isEnabled'])

    cfg.save_config(data)
    router.refresh()

    new_proxies = {p['proxyId']: p for p in data.get('proxies', []) if p.get('proxyId')}
    new_masks = {m['maskId']: m for m in data.get('masks', []) if m.get('maskId')}
    _diff_proxies(old_proxies, new_proxies)
    _diff_masks(old_masks, new_masks)
    log_config_state()

    await emit_event('config_changed', {})

    return {'success': True}


def handle_get_status(debug: bool, need_update: bool = False) -> dict:
    """GET /api/status — возвращает статус gateway."""
    return {
        'isEnabled': cfg.is_enabled(),
        'proxiesCount': len(cfg.get_all_proxies()),
        'masksCount': len(cfg.get_all_masks()),
        'status': 'running',
        'debug': debug,
        'needUpdate': need_update,
    }


def handle_get_version() -> dict:
    """GET /api/version — возвращает версию сервера."""
    return {'version': server_version}


def handle_post_enabled(data: dict, router: MaskRouter) -> dict:
    """POST /api/enabled — устанавливает глобальный флаг включения."""
    if not isinstance(data, dict) or 'enabled' not in data:
        raise ValueError('Требуется поле "enabled" (true/false)')
    cfg.set_enabled(bool(data['enabled']))
    router.refresh()
    return {'success': True, 'enabled': cfg.is_enabled()}


async def handle_ping(proxy_id: str, peername: tuple) -> tuple[dict, int]:
    """POST /api/ping — пингует прокси."""
    if not proxy_id:
        logger.warning('API: POST /api/ping без proxyId от %s', peername)
        return {'error': 'proxyId required'}, 400

    result = await ping_proxy(proxy_id)
    proxy = next((p for p in cfg.get_all_proxies() if p.get('proxyId') == proxy_id), None)
    if proxy:
        addr = '{}:{}'.format(proxy.get('host', '?'), proxy.get('port', '?'))
    else:
        addr = proxy_id
    if result.get('alive'):
        logger.info('Пинг %s: %s мс', addr, result['latency'])
    else:
        err = result.get('error')
        if err:
            logger.warning('Пинг %s: недоступен — %s', addr, err)
        else:
            logger.warning('Пинг %s: недоступен', addr)

    return result, 200
