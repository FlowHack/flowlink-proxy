"""
Обработчики API-эндпоинтов FlowLink Proxy.

Каждая функция обрабатывает один эндпоинт.
Единственная ответственность: бизнес-логика API.
"""

import logging
import uuid

from server.config import autostart, browser_config
from server.config import config as cfg
from server.config import system_autostart
from server.services.debug import log_config_state
from server.services.events import emit_event
from server.services.mask_conflicts import convert_wildcard_to_regex, validate_config
from server.services.ping import ping_proxy
from server.services.router import MaskRouter
from server.services.tunnel import (close_all_connections,
                                    close_all_proxy_tunnels,
                                    close_tunnels_for_proxy)
from server.i18n import _
from server.utils import proxy_addr
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
            'error': _('Не удалось загрузить конфигурацию'),
            'isEnabled': cfg.is_enabled(),
        }


async def handle_post_config(data: dict, router: MaskRouter) -> dict | tuple[dict, int]:
    """POST /api/config — обновляет конфигурацию и перезагружает маршруты.

    Перед сохранением проверяет конфликты масок: в группе конфликтующих
    прокси может быть включён только один. При конфликте возвращает
    HTTP 422 с деталями.
    """
    try:
        old_data = cfg.load_config()
        old_proxies = _extract_proxies_dict(old_data)
        old_masks = _extract_masks_dict(old_data)

        if not isinstance(data, dict):
            return {'error': _('Тело запроса должно быть JSON-объектом')}, 400

        new_proxies = data.get('proxies', [])
        new_masks = data.get('masks', [])

        # Валидация конфликтов масок: не более одного включённого прокси
        # в каждой группе конфликта.
        conflicts = validate_config(new_proxies, new_masks)
        if conflicts:
            conflict = conflicts[0]
            message = _(
                'Маски прокси "{proxy_label}" и "{conflicting_label}" '
                'пересекаются. Включён может быть только один из них.'
            ).format(
                proxy_label=conflict['proxyLabel'],
                conflicting_label=conflict['conflictingProxyLabel'],
            )
            logger.warning(
                'Конфликт масок при сохранении конфига: %s',
                message,
            )
            return {'error': message, 'conflict': conflict}, 422

        cfg.save_config(data)

        # Обновляем lastActiveProxyId: если ровно один прокси включён —
        # запоминаем его, иначе сбрасываем.
        _update_last_active_proxy(new_proxies)

        new_proxies_dict = _extract_proxies_dict(data)
        new_masks_dict = _extract_masks_dict(data)

        needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies_dict)
        if needs_full_flush or old_masks != new_masks_dict:
            close_all_connections()

        router.refresh()

        _log_config_changes(old_proxies, new_proxies_dict, old_masks, new_masks_dict)
        log_config_state()

        await emit_event('config_changed', {})

        return {'success': True}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка сохранения конфига: %s', e)
        return {'error': _('Не удалось сохранить конфигурацию')}, 500


def _update_last_active_proxy(proxies: list) -> None:
    """Обновляет lastActiveProxyId по списку прокси.

    Если включён ровно один прокси — запоминаем его id.
    Если включено несколько или ни одного — сбрасываем.
    """
    enabled_ids = [
        p.get('proxyId') for p in proxies
        if p.get('proxyId') and p.get('isEnabled', True)
    ]
    if len(enabled_ids) == 1:
        cfg.set_last_active_proxy(enabled_ids[0])
    else:
        cfg.set_last_active_proxy(None)


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
            'error': _('Не удалось загрузить конфигурацию'),
            'debug': debug,
            'needUpdate': need_update,
        }


def handle_get_version() -> dict:
    """GET /api/version — возвращает версию сервера."""
    return {'version': server_version}


async def handle_post_enabled(data: dict, router: MaskRouter) -> dict | tuple[dict, int]:
    """POST /api/enabled — устанавливает глобальный флаг включения."""
    try:
        if not isinstance(data, dict) or 'enabled' not in data:
            return {'error': _('Требуется поле "enabled" (true/false)')}, 400
        if not isinstance(data['enabled'], bool):
            return {'error': _('Поле "enabled" должно быть булевым (true/false)')}, 400
        enabled = data['enabled']
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
            'error': _('Не удалось переключить состояние'),
            'enabled': cfg.is_enabled(),
        }, 500


async def handle_ping(proxy_id: str, peername: tuple) -> tuple[dict, int]:
    """POST /api/ping — пингует прокси."""
    if not proxy_id:
        logger.warning('API: POST /api/ping без proxyId от %s', peername)
        return {'error': _('Требуется proxyId')}, 400

    result = await ping_proxy(proxy_id)
    proxy = cfg.get_proxy_by_id(proxy_id)
    addr = proxy_addr(proxy, proxy_id)
    if result.get('alive'):
        logger.info('Пинг %s: %s мс', addr, result['latency'])
    else:
        err = result.get('error')
        err_kind = result.get('errorKind')
        if err:
            logger.warning('Пинг %s: недоступен — %s (тип: %s)', addr, err, err_kind)
        else:
            logger.warning('Пинг %s: недоступен (тип: %s)', addr, err_kind)

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
            'error': _('Не удалось прочитать настройку'),
        }


async def handle_post_autostart_browser(data: dict) -> dict | tuple[dict, int]:
    """POST /api/autostart-browser — обновляет настройку автозапуска браузера."""
    try:
        if not isinstance(data, dict) or 'autostartBrowser' not in data:
            return {'error': _('Требуется поле "autostartBrowser" (true/false)')}, 400
        if not isinstance(data['autostartBrowser'], bool):
            return {'error': _('Поле "autostartBrowser" должно быть булевым (true/false)')}, 400
        value = data['autostartBrowser']
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
            'error': _(
                'Не удалось сохранить настройку. Проверьте права на запись. '
                'Если проблема повторяется, обратитесь в поддержку: '
                'flowlink.proxy@atomicmail.io'
            ),
            'autostartBrowser': autostart.get_autostart_browser(),
        }, 500
    except (ValueError, TypeError) as e:
        logger.warning('Неверный запрос autostart_browser: %s', e)
        return {
            'error': str(e),
            'autostartBrowser': autostart.get_autostart_browser(),
        }, 400


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
            'error': _('Не удалось прочитать статус автозапуска'),
        }


async def handle_post_system_autostart(data: dict) -> dict | tuple[dict, int]:
    """POST /api/system-autostart — включает/отключает автозапуск с системой."""
    try:
        if not isinstance(data, dict) or 'enabled' not in data:
            return {'error': _('Требуется поле "enabled" (true/false)')}, 400
        if not isinstance(data['enabled'], bool):
            return {'error': _('Поле "enabled" должно быть булевым (true/false)')}, 400
        value = data['enabled']
        result = system_autostart.set_system_autostart_enabled(value)
        if not result:
            return {
                'error': _('Не удалось изменить настройку автозапуска системы'),
                'enabled': system_autostart.is_system_autostart_enabled(),
            }, 500
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
        }, 400
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка записи system_autostart: %s', e)
        return {
            'error': _('Не удалось изменить настройку автозапуска'),
            'enabled': system_autostart.is_system_autostart_enabled(),
        }, 500


# --- Эндпоинты браузера ---


def handle_post_validate_browser(data: dict) -> tuple[dict, int]:
    """POST /api/validate-browser — валидирует путь к браузеру без сохранения."""
    try:
        if not isinstance(data, dict) or 'browserPath' not in data:
            return {'error': _('Требуется поле "browserPath"')}, 400
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
            'error': _('Не удалось прочитать путь браузера'),
        }


async def handle_post_browser_path(data: dict) -> tuple[dict, int]:
    """POST /api/browser-path — сохраняет путь к браузеру (с валидацией)."""
    try:
        if not isinstance(data, dict) or 'browserPath' not in data:
            raise ValueError(_('Требуется поле "browserPath"'))
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
            'error': _('Не удалось сохранить путь браузера'),
            'browserPath': browser_config.get_browser_path(),
        }, 500


def handle_get_detected_browsers() -> dict:
    """GET /api/detected-browsers — список обнаруженных браузеров."""
    try:
        browsers = browser_config.auto_detect_browsers()
        return {'browsers': browsers}
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка автопоиска браузеров: %s', e)
        return {'browsers': [], 'error': _('Ошибка автопоиска')}


def handle_get_browser_config() -> dict:
    """GET /api/browser-config — полная конфигурация браузера."""
    try:
        config = browser_config.get_browser_config()
        return config
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка чтения browser_config: %s', e)
        return {
            'browserPath': '',
            'autostartBrowser': True,
            'parallelLaunch': False,
            'error': _('Не удалось прочитать конфигурацию браузера'),
        }


# --- Точечные эндпоинты прокси и масок (Фаза 1 оптимизации) ---


def _validate_proxy_fields(data: dict) -> tuple[dict, int] | None:
    """Валидирует поля прокси из запроса.

    Возвращает None при успехе или (ошибка, код) при неудаче.
    """
    host = data.get('host')
    port = data.get('port')
    username = data.get('username')
    password = data.get('password')
    label = data.get('label')

    if not isinstance(host, str) or not host.strip():
        return {'error': _('Требуется поле "host" (строка)')}, 400
    if not isinstance(port, int) or not 1 <= port <= 65535:
        return {'error': _('Поле "port" должно быть целым числом от 1 до 65535')}, 400
    if username is not None and not isinstance(username, str):
        return {'error': _('Поле "username" должно быть строкой')}, 400
    if password is not None and not isinstance(password, str):
        return {'error': _('Поле "password" должно быть строкой')}, 400
    if label is not None and not isinstance(label, str):
        return {'error': _('Поле "label" должно быть строкой')}, 400
    return None


def _find_duplicate_proxy(
    proxies: list,
    host: str,
    port: int,
    exclude_id: str | None = None,
) -> dict | None:
    """Ищет прокси с тем же host:port, исключая указанный proxyId."""
    for p in proxies:
        if p.get('host') == host and p.get('port') == port:
            if exclude_id is None or p.get('proxyId') != exclude_id:
                return p
    return None


def _conflict_error(conflicts: list) -> tuple[dict, int]:
    """Формирует ответ 422 при конфликте масок."""
    conflict = conflicts[0]
    message = _(
        'Маски прокси "{proxy_label}" и "{conflicting_label}" '
        'пересекаются. Включён может быть только один из них.'
    ).format(
        proxy_label=conflict['proxyLabel'],
        conflicting_label=conflict['conflictingProxyLabel'],
    )
    logger.warning('Конфликт масок: %s', message)
    return {'error': message, 'conflict': conflict}, 422


async def handle_post_proxy(  # pylint: disable=too-many-locals  # обработчик точечного добавления прокси: валидация, конфликты, туннели
    data: dict, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """POST /api/proxies — добавляет один прокси."""
    try:
        if not isinstance(data, dict):
            return {'error': _('Тело запроса должно быть JSON-объектом')}, 400

        validation = _validate_proxy_fields(data)
        if validation is not None:
            return validation

        host = data['host'].strip()
        port = data['port']
        username = data.get('username', '')
        password = data.get('password', '')
        label = data.get('label', '')

        old_data = cfg.load_config()
        old_proxies = _extract_proxies_dict(old_data)
        old_masks = _extract_masks_dict(old_data)

        proxies = old_data.get('proxies', [])
        if _find_duplicate_proxy(proxies, host, port):
            return {'error': _('Прокси с таким host:port уже существует')}, 422

        new_proxy = {
            'proxyId': uuid.uuid4().hex,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'label': label,
            'isEnabled': True,
        }
        proxies.append(new_proxy)
        new_data = {
            'proxies': proxies,
            'masks': old_data.get('masks', []),
        }

        # Валидация конфликтов масок для нового включённого прокси
        conflicts = validate_config(new_data['proxies'], new_data['masks'])
        if conflicts:
            return _conflict_error(conflicts)

        cfg.save_config(new_data)
        _update_last_active_proxy(new_data['proxies'])

        new_proxies_dict = _extract_proxies_dict(new_data)
        needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies_dict)
        # При выключении прокси дополнительно закрываем ВСЕ соединения,
        # чтобы гарантированно разорвать клиентские keep-alive туннели браузера
        # и заставить его переподключиться по актуальным правилам маршрутизации.
        if needs_full_flush or old_masks != _extract_masks_dict(new_data):
            close_all_connections()

        router.refresh()
        _log_config_changes(old_proxies, new_proxies_dict, old_masks, _extract_masks_dict(new_data))
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True, 'proxy': new_proxy}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка добавления прокси: %s', e)
        return {'error': _('Не удалось добавить прокси')}, 500


async def handle_patch_proxy(  # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches  # обработчик обновления прокси: валидация, конфликты, туннели
    proxy_id: str, data: dict, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """PATCH /api/proxy/{id} — обновляет поля прокси."""
    try:
        if not isinstance(data, dict):
            return {'error': _('Тело запроса должно быть JSON-объектом')}, 400

        old_data = cfg.load_config()
        old_proxies = _extract_proxies_dict(old_data)
        old_masks = _extract_masks_dict(old_data)

        proxies = old_data.get('proxies', [])
        idx = next((i for i, p in enumerate(proxies) if p.get('proxyId') == proxy_id), None)
        if idx is None:
            return {'error': _('Прокси не найден')}, 404

        current = proxies[idx]
        host = data.get('host', current.get('host'))
        port = data.get('port', current.get('port'))
        if not isinstance(host, str) or not host.strip():
            return {'error': _('Требуется поле "host" (строка)')}, 400
        if not isinstance(port, int) or not 1 <= port <= 65535:
            return {'error': _('Поле "port" должно быть целым числом от 1 до 65535')}, 400

        if _find_duplicate_proxy(proxies, host, port, exclude_id=proxy_id):
            return {'error': _('Прокси с таким host:port уже существует')}, 422

        updated = dict(current)
        updated['host'] = host
        updated['port'] = port
        if 'username' in data:
            if not isinstance(data['username'], str):
                return {'error': _('Поле "username" должно быть строкой')}, 400
            updated['username'] = data['username']
        if 'password' in data:
            if not isinstance(data['password'], str):
                return {'error': _('Поле "password" должно быть строкой')}, 400
            updated['password'] = data['password']
        if 'label' in data:
            if not isinstance(data['label'], str):
                return {'error': _('Поле "label" должно быть строкой')}, 400
            updated['label'] = data['label']
        proxies[idx] = updated

        new_data = {'proxies': proxies, 'masks': old_data.get('masks', [])}
        cfg.save_config(new_data)
        _update_last_active_proxy(proxies)

        new_proxies_dict = _extract_proxies_dict(new_data)
        needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies_dict)
        # При выключении прокси дополнительно закрываем ВСЕ соединения,
        # чтобы гарантированно разорвать клиентские keep-alive туннели браузера
        # и заставить его переподключиться по актуальным правилам маршрутизации.
        if needs_full_flush or old_masks != _extract_masks_dict(new_data):
            close_all_connections()

        router.refresh()
        _log_config_changes(old_proxies, new_proxies_dict, old_masks, _extract_masks_dict(new_data))
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True, 'proxy': updated}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка обновления прокси: %s', e)
        return {'error': _('Не удалось обновить прокси')}, 500


async def handle_patch_proxy_enabled(
    proxy_id: str, data: dict, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """PATCH /api/proxy/{id}/enabled — переключает активность прокси."""
    try:
        if not isinstance(data, dict) or 'enabled' not in data:
            return {'error': _('Требуется поле "enabled" (true/false)')}, 400
        if not isinstance(data['enabled'], bool):
            return {'error': _('Поле "enabled" должно быть булевым (true/false)')}, 400
        enabled = data['enabled']

        old_data = cfg.load_config()
        old_proxies = _extract_proxies_dict(old_data)
        old_masks = _extract_masks_dict(old_data)

        proxies = old_data.get('proxies', [])
        idx = next((i for i, p in enumerate(proxies) if p.get('proxyId') == proxy_id), None)
        if idx is None:
            return {'error': _('Прокси не найден')}, 404

        proxies[idx]['isEnabled'] = enabled
        new_data = {'proxies': proxies, 'masks': old_data.get('masks', [])}

        # При включении проверяем конфликты масок
        if enabled:
            conflicts = validate_config(proxies, new_data['masks'])
            if conflicts:
                return _conflict_error(conflicts)

        cfg.save_config(new_data)
        _update_last_active_proxy(proxies)

        new_proxies_dict = _extract_proxies_dict(new_data)
        needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies_dict)
        # При выключении прокси дополнительно закрываем ВСЕ соединения,
        # чтобы гарантированно разорвать клиентские keep-alive туннели браузера
        # и заставить его переподключиться по актуальным правилам маршрутизации.
        if not enabled or needs_full_flush or old_masks != _extract_masks_dict(new_data):
            close_all_connections()

        router.refresh()
        _log_config_changes(old_proxies, new_proxies_dict, old_masks, _extract_masks_dict(new_data))
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True, 'enabled': enabled}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка переключения прокси: %s', e)
        return {'error': _('Не удалось переключить прокси')}, 500


async def handle_delete_proxy(
    proxy_id: str, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """DELETE /api/proxy/{id} — удаляет прокси и связанные маски."""
    try:
        old_data = cfg.load_config()
        old_proxies = _extract_proxies_dict(old_data)
        old_masks = _extract_masks_dict(old_data)

        proxies = old_data.get('proxies', [])
        if not any(p.get('proxyId') == proxy_id for p in proxies):
            return {'error': _('Прокси не найден')}, 404

        proxies = [p for p in proxies if p.get('proxyId') != proxy_id]
        masks = [m for m in old_data.get('masks', []) if m.get('proxyId') != proxy_id]
        new_data = {'proxies': proxies, 'masks': masks}

        cfg.save_config(new_data)
        _update_last_active_proxy(proxies)

        new_proxies_dict = _extract_proxies_dict(new_data)
        needs_full_flush = _close_tunnels_on_config_change(old_proxies, new_proxies_dict)
        if needs_full_flush or old_masks != _extract_masks_dict(new_data):
            close_all_connections()

        router.refresh()
        _log_config_changes(old_proxies, new_proxies_dict, old_masks, _extract_masks_dict(new_data))
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка удаления прокси: %s', e)
        return {'error': _('Не удалось удалить прокси')}, 500


async def handle_post_mask(  # pylint: disable=too-many-return-statements  # обработчик добавления маски: валидация, конфликты
    data: dict, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """POST /api/masks — добавляет маску."""
    try:
        if not isinstance(data, dict):
            return {'error': _('Тело запроса должно быть JSON-объектом')}, 400

        pattern = data.get('pattern')
        proxy_id = data.get('proxyId')
        if not isinstance(pattern, str) or not pattern.strip():
            return {'error': _('Требуется поле "pattern" (строка)')}, 400
        if not isinstance(proxy_id, str) or not proxy_id:
            return {'error': _('Требуется поле "proxyId"')}, 400

        # regexString обязателен для маршрутизации; если не передан —
        # генерируем из wildcard-паттерна на сервере.
        regex_string = data.get('regexString', '')
        if not isinstance(regex_string, str) or not regex_string.strip():
            regex_string = convert_wildcard_to_regex(pattern)

        old_data = cfg.load_config()
        old_masks = _extract_masks_dict(old_data)

        proxies = old_data.get('proxies', [])
        if not any(p.get('proxyId') == proxy_id for p in proxies):
            return {'error': _('Прокси не найден')}, 400

        masks = old_data.get('masks', [])
        new_mask = {
            'maskId': uuid.uuid4().hex,
            'pattern': pattern,
            'regexString': regex_string,
            'proxyId': proxy_id,
        }
        masks.append(new_mask)
        new_data = {'proxies': proxies, 'masks': masks}

        # Валидация конфликтов масок
        conflicts = validate_config(proxies, masks)
        if conflicts:
            return _conflict_error(conflicts)

        cfg.save_config(new_data)

        new_masks_dict = _extract_masks_dict(new_data)
        if old_masks != new_masks_dict:
            close_all_connections()

        router.refresh()
        _log_config_changes({}, {}, old_masks, new_masks_dict)
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True, 'mask': new_mask}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка добавления маски: %s', e)
        return {'error': _('Не удалось добавить маску')}, 500


async def handle_patch_mask(
    mask_id: str, data: dict, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """PATCH /api/mask/{id} — обновляет паттерн маски."""
    try:
        if not isinstance(data, dict):
            return {'error': _('Тело запроса должно быть JSON-объектом')}, 400
        pattern = data.get('pattern')
        if not isinstance(pattern, str) or not pattern.strip():
            return {'error': _('Требуется поле "pattern" (строка)')}, 400

        old_data = cfg.load_config()
        old_masks = _extract_masks_dict(old_data)

        masks = old_data.get('masks', [])
        idx = next((i for i, m in enumerate(masks) if m.get('maskId') == mask_id), None)
        if idx is None:
            return {'error': _('Маска не найдена')}, 404

        masks[idx]['pattern'] = pattern
        # regexString обязателен для маршрутизации; если не передан —
        # пересчитываем из нового wildcard-паттерна на сервере.
        regex_string = data.get('regexString', '')
        if not isinstance(regex_string, str) or not regex_string.strip():
            regex_string = convert_wildcard_to_regex(pattern)
        masks[idx]['regexString'] = regex_string
        new_data = {'proxies': old_data.get('proxies', []), 'masks': masks}

        conflicts = validate_config(new_data['proxies'], masks)
        if conflicts:
            return _conflict_error(conflicts)

        cfg.save_config(new_data)

        new_masks_dict = _extract_masks_dict(new_data)
        if old_masks != new_masks_dict:
            close_all_connections()

        router.refresh()
        _log_config_changes({}, {}, old_masks, new_masks_dict)
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True, 'mask': masks[idx]}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка обновления маски: %s', e)
        return {'error': _('Не удалось обновить маску')}, 500


async def handle_delete_mask(
    mask_id: str, router: MaskRouter,
) -> dict | tuple[dict, int]:
    """DELETE /api/mask/{id} — удаляет маску."""
    try:
        old_data = cfg.load_config()
        old_masks = _extract_masks_dict(old_data)

        masks = old_data.get('masks', [])
        # Проверяем существование маски до удаления
        if not any(m.get('maskId') == mask_id for m in masks):
            return {'error': _('Маска не найдена')}, 404

        masks = [m for m in masks if m.get('maskId') != mask_id]
        new_data = {'proxies': old_data.get('proxies', []), 'masks': masks}

        cfg.save_config(new_data)

        new_masks_dict = _extract_masks_dict(new_data)
        if old_masks != new_masks_dict:
            close_all_connections()

        router.refresh()
        _log_config_changes({}, {}, old_masks, new_masks_dict)
        log_config_state()
        await emit_event('config_changed', {})
        return {'success': True}
    except (OSError, RuntimeError, ImportError, ValueError) as e:
        logger.error('Ошибка удаления маски: %s', e)
        return {'error': _('Не удалось удалить маску')}, 500


def handle_get_language() -> dict:
    """GET /api/language — возвращает текущий язык интерфейса."""
    return {'language': autostart.get_language()}


async def handle_post_language(data: dict) -> dict | tuple[dict, int]:
    """POST /api/language — устанавливает язык интерфейса бэкенда."""
    try:
        if not isinstance(data, dict) or 'language' not in data:
            return {'error': _('Требуется поле "language"')}, 400
        if not isinstance(data['language'], str) or not data['language'].strip():
            return {'error': _('Поле "language" должно быть непустой строкой')}, 400

        value = data['language']
        normalized = autostart.set_language(value)

        # Применяем язык к gettext-локализации.
        # Ленивый импорт: избегаем потенциальной циклической зависимости
        # между handlers и i18n при инициализации.
        from server.i18n import set_language as i18n_set_language  # pylint: disable=import-outside-toplevel
        i18n_set_language(normalized)

        await emit_event('language_changed', {
            'language': normalized,
        })
        return {
            'success': True,
            'language': normalized,
        }
    except ValueError as e:
        logger.warning('Неверный запрос language: %s', e)
        return {'error': str(e)}, 400
    except OSError as e:
        logger.error('Ошибка сохранения language: %s', e)
        return {
            'error': _(
                'Не удалось сохранить настройку. Проверьте права на запись.'
            ),
            'language': autostart.get_language(),
        }, 500
