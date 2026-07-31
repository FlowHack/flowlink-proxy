"""
Обработчики API-эндпоинтов FlowLink Proxy.

Каждая функция обрабатывает один эндпоинт.
Единственная ответственность: бизнес-логика API.
"""

import logging

from server.config import autostart, browser_config
from server.config import config as cfg
from server.config import system_autostart
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
    """Извлекает словарь прокси из данных конфигурации."""
    return {p['proxyId']: p for p in data.get('proxies', []) if p.get('proxyId')}


def _extract_masks_dict(data: dict) -> dict:
    """Извлекает словарь масок из данных конфигурации."""
    return {m['maskId']: m for m in data.get('masks', []) if m.get('maskId')}


def _close_tunnels_on_config_change(
    old_proxies: dict,
    new_proxies: dict,
) -> bool:
    """
    Закрывает туннели при изменении статуса или адреса прокси.

    Возвращает True, если нужен полный сброс всех соединений.
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
    """GET /api/config — возвращает текущую конфигурацию."""
    try:
        data = cfg.load_config()
        data['isEnabled'] = cfg.is_enabled()
        return data
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка загрузки конфига: %s', e)
        return {
            'error': 'Не удалось загрузить конфигурацию',
            'isEnabled': cfg.is_enabled(),
        }


async def handle_post_config(data: dict, router: MaskRouter) -> dict:
    """POST /api/config — обновляет конфигурацию и перезагружает маршруты."""
    try:
        old_data = cfg.load_config()
        old_proxies = _extract_proxies_dict(old_data)
        old_masks = _extract_masks_dict(old_data)

        if not isinstance(data, dict):
            raise ValueError('Тело запроса должно быть JSON-объектом')

        cfg.save_config(data)

        new_proxies = _extract_proxies_dict(data)
        new_masks = _extract_masks_dict(data)

        needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies)
        if needs_full_flush or old_masks != new_masks:
            close_all_connections()

        router.refresh()

        _log_config_changes(old_proxies, new_proxies, old_masks, new_masks)
        log_config_state()

        await emit_event('config_changed', {})

        return {'success': True}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка сохранения конфига: %s', e)
        return {'error': 'Не удалось сохранить конфигурацию'}


def handle_get_status(debug: bool, need_update: bool = False) -> dict:
    """GET /api/status — возвращает статус gateway."""
    try:
        return {
            'isEnabled': cfg.is_enabled(),
            'proxiesCount': len(cfg.get_all_proxies()),
            'masksCount': len(cfg.get_all_masks()),
            'status': 'running',
            'debug': debug,
            'needUpdate': need_update,
        }
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка получения статуса: %s', e)
        return {
            'isEnabled': cfg.is_enabled(),
            'proxiesCount': 0, 'masksCount': 0,
            'status': 'error',
            'error': 'Не удалось загрузить конфигурацию',
            'debug': debug,
            'needUpdate': need_update,
        }


def handle_get_version() -> dict:
    """GET /api/version — возвращает версию сервера."""
    return {'version': server_version}


async def handle_post_enabled(data: dict, router: MaskRouter) -> dict:
    """POST /api/enabled — устанавливает глобальный флаг включения."""
    try:
        if not isinstance(data, dict) or 'enabled' not in data:
            raise ValueError('Требуется поле "enabled" (true/false)')
        enabled = bool(data['enabled'])
        cfg.set_enabled(enabled)
        router.refresh()
        if enabled:
            logger.info(
                'Глобальное включение: закрытие всех соединений для перемаршрутизации',
            )
            close_all_connections()
        else:
            logger.info('Глобальное выключение: закрытие всех прокси-туннелей')
            close_all_proxy_tunnels()
        await emit_event('config_changed', {})
        return {'success': True, 'enabled': cfg.is_enabled()}
    except (OSError, RuntimeError, ValueError) as e:
        logger.error('Ошибка переключения состояния: %s', e)
        return {
            'error': 'Не удалось переключить состояние',
            'enabled': cfg.is_enabled(),
        }


async def handle_ping(proxy_id: str, peername: tuple) -> tuple[dict, int]:
    """POST /api/ping — пингует прокси."""
    if not proxy_id:
        logger.warning('API: POST /api/ping без proxyId от %s', peername)
        return {'error': 'Требуется proxyId'}, 400

    result = await ping_proxy(proxy_id)
    proxy = next(
        (p for p in cfg.get_all_proxies() if p.get('proxyId') == proxy_id),
        None,
    )
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


# --- Эндпоинты автозапуска браузера ---


def handle_get_autostart_browser() -> dict:
    """GET /api/autostart-browser — настройка автозапуска браузера."""
    try:
        return {
            'autostartBrowser': autostart.get_autostart_browser(),
        }
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка чтения autostart_browser: %s', e)
        return {
            'autostartBrowser': autostart.get_autostart_browser(),
            'error': 'Не удалось прочитать настройку',
        }


async def handle_post_autostart_browser(data: dict) -> dict:
    """POST /api/autostart-browser — обновляет настройку автозапуска браузера."""
    try:
        if not isinstance(data, dict) or 'autostartBrowser' not in data:
            raise ValueError('Требуется поле "autostartBrowser" (true/false)')
        value = bool(data['autostartBrowser'])
        autostart.set_autostart_browser(value)
        await emit_event('autostart_browser_changed', {
            'autostartBrowser': value,
        })
        return {
            'success': True,
            'autostartBrowser': value,
        }
    except OSError as e:
        logger.error('Ошибка сохранения autostart_browser: %s', e)
        return {
            'error': 'Не удалось сохранить настройку. '
                     'Проверьте права на запись. '
                     'Если проблема повторяется, обратитесь в поддержку: '
                     'flowlink.proxy@atomicmail.io',
            'autostartBrowser': autostart.get_autostart_browser(),
        }
    except (ValueError, TypeError) as e:
        logger.warning('Неверный запрос autostart_browser: %s', e)
        return {
            'error': str(e),
            'autostartBrowser': autostart.get_autostart_browser(),
        }


# --- Эндпоинты системного автозапуска ---


def handle_get_system_autostart() -> dict:
    """GET /api/system-autostart — информация о системном автозапуске."""
    try:
        return system_autostart.get_system_autostart_info()
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка чтения system_autostart: %s', e)
        return {
            'enabled': False,
            'platform': 'unknown',
            'method': 'unknown',
            'path': '',
            'error': 'Не удалось прочитать статус автозапуска',
        }


async def handle_post_system_autostart(data: dict) -> dict:
    """POST /api/system-autostart — включает/отключает автозапуск с системой."""
    try:
        if not isinstance(data, dict) or 'enabled' not in data:
            raise ValueError('Требуется поле "enabled" (true/false)')
        value = bool(data['enabled'])
        result = system_autostart.set_system_autostart_enabled(value)
        if not result:
            return {
                'error': 'Не удалось изменить настройку автозапуска системы',
                'enabled': system_autostart.is_system_autostart_enabled(),
            }
        await emit_event('system_autostart_changed', {
            'enabled': value,
        })
        return {
            'success': True,
            'enabled': value,
        }
    except (ValueError, TypeError) as e:
        logger.warning('Неверный запрос system_autostart: %s', e)
        return {
            'error': str(e),
            'enabled': system_autostart.is_system_autostart_enabled(),
        }
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка записи system_autostart: %s', e)
        return {
            'error': 'Не удалось изменить настройку автозапуска',
            'enabled': system_autostart.is_system_autostart_enabled(),
        }


# --- Эндпоинты браузера ---


def handle_post_validate_browser(data: dict) -> tuple[dict, int]:
    """POST /api/validate-browser — валидирует путь к браузеру без сохранения."""
    try:
        if not isinstance(data, dict) or 'browserPath' not in data:
            return {'error': 'Требуется поле "browserPath"'}, 400
        path = str(data['browserPath']).strip()
        result = browser_config.validate_browser_path_detailed(path)
        return result, 200
    except (ValueError, TypeError) as e:
        logger.warning('Неверный запрос validate-browser: %s', e)
        return {'error': str(e)}, 400


def handle_get_browser_path() -> dict:
    """GET /api/browser-path — текущий путь к браузеру."""
    try:
        return {
            'browserPath': browser_config.get_browser_path(),
        }
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка чтения browser_path: %s', e)
        return {
            'browserPath': '',
            'error': 'Не удалось прочитать путь браузера',
        }


async def handle_post_browser_path(data: dict) -> tuple[dict, int]:
    """POST /api/browser-path — сохраняет путь к браузеру (с валидацией)."""
    try:
        if not isinstance(data, dict) or 'browserPath' not in data:
            raise ValueError('Требуется поле "browserPath"')
        path = str(data['browserPath']).strip()

        # Расширенная валидация перед сохранением
        validation = browser_config.validate_browser_path_detailed(path)
        if not validation['valid']:
            logger.warning('Невалидный путь к браузеру: %s — %s', path, validation['error'])
            return {
                'error': validation['error'],
                'browserPath': browser_config.get_browser_path(),
                'validationFailed': True,
            }, 422

        browser_config.save_browser_path(path)
        await emit_event('browser_config_changed', {
            'browserPath': path,
        })
        return {
            'success': True,
            'browserPath': path,
        }, 200
    except (ValueError, TypeError) as e:
        logger.warning('Неверный запрос browser_path: %s', e)
        return {
            'error': str(e),
            'browserPath': browser_config.get_browser_path(),
        }, 400
    except OSError as e:
        logger.error('Ошибка записи browser_path: %s', e)
        return {
            'error': 'Не удалось сохранить путь браузера',
            'browserPath': browser_config.get_browser_path(),
        }, 500


def handle_get_detected_browsers() -> dict:
    """GET /api/detected-browsers — список обнаруженных браузеров."""
    try:
        browsers = browser_config.auto_detect_browsers()
        return {'browsers': browsers}
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка автопоиска браузеров: %s', e)
        return {'browsers': [], 'error': 'Ошибка автопоиска'}


def handle_get_browser_config() -> dict:
    """GET /api/browser-config — полная конфигурация браузера."""
    try:
        config = browser_config.get_browser_config()
        detected = browser_config.auto_detect_browsers()
        config['detectedBrowsers'] = detected
        return config
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка чтения browser_config: %s', e)
        return {
            'browserPath': '',
            'autostartBrowser': True,
            'parallelLaunch': False,
            'detectedBrowsers': [],
            'error': 'Не удалось прочитать конфигурацию браузера',
        }
