"""
Обработчики API-эндпоинтов FlowLink Proxy.

Каждая функция обрабатывает один эндпоинт.
Единственная ответственность: бизнес-логика API.
"""

import logging

from server.config import config as cfg
from server.services.debug import log_config_state
from server.services.events import emit_event
from server.services.ping import ping_proxy
from server.services.router import MaskRouter
from server.services.tunnel import (close_all_connections,
                                    close_all_proxy_tunnels,
                                    close_tunnels_for_proxy)
from server.version import __version__ as server_version

logger = logging.getLogger('flowlink.api')


def _extract_proxies_dict(data: dict) -> dict:
    """
    Извлекает словарь прокси из данных конфигурации.

    Args:
        data: словарь с ключом 'proxies' (список прокси).

    Returns:
        Словарь {proxyId: proxy_dict} без proxyId равных None.
    """
    return {p['proxyId']: p for p in data.get('proxies', []) if p.get('proxyId')}


def _extract_masks_dict(data: dict) -> dict:
    """
    Извлекает словарь масок из данных конфигурации.

    Args:
        data: словарь с ключом 'masks' (список масок).

    Returns:
        Словарь {maskId: mask_dict} без maskId равных None.
    """
    return {m['maskId']: m for m in data.get('masks', []) if m.get('maskId')}


def _close_tunnels_on_config_change(
    old_proxies: dict,
    new_proxies: dict,
) -> bool:
    """
    Закрывает туннели при изменении статуса или адреса прокси.

    Возвращает True, если нужен полный сброс всех соединений
    (хотя бы один прокси был включён).
    """
    needs_full_flush = False
    for pid, old_p in old_proxies.items():
        new_p = new_proxies.get(pid)
        if new_p is None:
            logger.info('Прокси %s удалён, закрытие туннелей', pid[:8])
            close_tunnels_for_proxy(pid)
        elif old_p.get('isEnabled', True) and not new_p.get('isEnabled', True):
            logger.info('Прокси %s выключен, закрытие туннелей', pid[:8])
            close_tunnels_for_proxy(pid)
        elif not old_p.get('isEnabled', True) and new_p.get('isEnabled', True):
            logger.info('Прокси %s включён, сброс соединений', pid[:8])
            needs_full_flush = True
        elif (old_p.get('host') != new_p.get('host')
              or old_p.get('port') != new_p.get('port')):
            logger.info('Прокси %s изменил адрес, закрытие туннелей', pid[:8])
            close_tunnels_for_proxy(pid)
    return needs_full_flush


def _log_config_changes(
    old_proxies: dict,
    new_proxies: dict,
    old_masks: dict,
    new_masks: dict,
) -> None:
    """Логирует добавленные, изменённые и удалённые прокси и маски."""
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
    for mid, m in new_masks.items():
        if mid not in old_masks:
            logger.info(
                'Добавлена маска %s для прокси %s',
                m.get('regexString', '?'), m.get('proxyId', '?'),
            )
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
    old_proxies = _extract_proxies_dict(old_data)
    old_masks = _extract_masks_dict(old_data)

    if not isinstance(data, dict):
        raise ValueError('Тело запроса должно быть JSON-объектом')

    cfg.save_config(data)

    new_proxies = _extract_proxies_dict(data)
    new_masks = _extract_masks_dict(data)

    # Закрываем туннели при любом изменении конфига (прокси или маски)
    # чтобы Chrome переподключился с актуальной маршрутизацией
    needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies)
    if needs_full_flush or old_masks != new_masks:
        close_all_connections()

    router.refresh()

    _log_config_changes(old_proxies, new_proxies, old_masks, new_masks)
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


async def handle_post_enabled(data: dict, router: MaskRouter) -> dict:
    """POST /api/enabled — устанавливает глобальный флаг включения."""
    if not isinstance(data, dict) or 'enabled' not in data:
        raise ValueError('Требуется поле "enabled" (true/false)')
    enabled = bool(data['enabled'])
    cfg.set_enabled(enabled)
    router.refresh()
    if enabled:
        logger.info('Глобальное включение: закрытие всех соединений для перемаршрутизации')
        close_all_connections()
    else:
        logger.info('Глобальное выключение: закрытие всех прокси-туннелей')
        close_all_proxy_tunnels()
    await emit_event('config_changed', {})
    return {'success': True, 'enabled': cfg.is_enabled()}


async def handle_ping(proxy_id: str, peername: tuple) -> tuple[dict, int]:
    """POST /api/ping — пингует прокси."""
    if not proxy_id:
        logger.warning('API: POST /api/ping без proxyId от %s', peername)
        return {'error': 'proxyId required'}, 400

    result = await ping_proxy(proxy_id)
    proxy = next((p for p in cfg.get_all_proxies() if p.get('proxyId') == proxy_id), None)
    if proxy:
        addr = f"{proxy.get('host', '?')}:{proxy.get('port', '?')}"
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
