"""
Сервисный слой конфигурации FlowLink Proxy.

Загружает/сохраняет конфиг через repo, шифрует/расшифровывает пароли.
Предоставляет доступ к полям конфига (get_all_proxies, get_all_masks, is_enabled).
isEnabled хранится ТОЛЬКО в памяти — расширение управляет им через POST /api/enabled.
Единственная ответственность: управление конфигурацией с шифрованием.
"""

import copy
import logging
import time

from server.config import crypto
from server.config.repo import load_raw, save_raw

logger = logging.getLogger('flowlink.config')

_CACHE: dict = {}
_CACHE_TIME: dict[str, float] = {}
_CACHE_TTL: float = 1.0

# Глобальный флаг включения хранится только в памяти (не в config.json)
# По умолчанию True — расширение при старте пришлёт актуальное состояние
_ENABLED: bool = True


def _cache_key() -> str:
    """Возвращает путь к файлу конфига как ключ кэша."""
    from server.config.repo import CONFIG_FILE
    return CONFIG_FILE


def _load_cached() -> dict:
    """Загружает конфиг с кэшированием на _CACHE_TTL секунд."""
    key = _cache_key()
    now = time.monotonic()
    if key in _CACHE and now - _CACHE_TIME.get(key, 0) < _CACHE_TTL:
        return _CACHE[key]
    _CACHE[key] = load_raw()
    _CACHE_TIME[key] = now
    return _CACHE[key]


def _invalidate_cache():
    """Сбрасывает кэш после сохранения."""
    key = _cache_key()
    _CACHE.pop(key, None)
    _CACHE_TIME.pop(key, None)


def _decrypt_proxies(data: dict) -> dict:
    """Расшифровывает username/password у всех прокси."""
    for proxy in data.get('proxies', []):
        if proxy.get('username'):
            try:
                proxy['username'] = crypto.decrypt(proxy['username'])
            except Exception as e:
                logger.warning('Ошибка расшифровки имени пользователя для прокси %s: %s', proxy.get('proxyId', '?'), e)
                proxy['username'] = ''
        if proxy.get('password'):
            try:
                proxy['password'] = crypto.decrypt(proxy['password'])
            except Exception as e:
                logger.warning('Ошибка расшифровки пароля для прокси %s: %s', proxy.get('proxyId', '?'), e)
                proxy['password'] = ''
    return data


def load_config(force: bool = False) -> dict:
    """Загружает конфиг и расшифровывает username/password."""
    data = load_raw() if force else _load_cached()
    return _decrypt_proxies(copy.deepcopy(data))


def set_enabled(val: bool):
    """Устанавливает глобальный флаг включения (только в памяти)."""
    global _ENABLED
    _ENABLED = bool(val)
    logger.info('Глобальный переключатель: %s', 'включён' if _ENABLED else 'выключен')


def save_config(data: dict):
    """Шифрует username/password и сохраняет конфиг.
    isEnabled НЕ пишется в файл — хранится только в памяти."""
    to_save = {
        'proxies': [],
        'masks': data.get('masks', []),
    }

    for proxy in data.get('proxies', []):
        proxy_copy = dict(proxy)
        if proxy_copy.get('username'):
            try:
                proxy_copy['username'] = crypto.encrypt(proxy_copy['username'])
            except Exception as e:
                logger.error(f'Ошибка шифрования имени пользователя для прокси {proxy_copy.get("proxyId", "?")}: {e}')
                proxy_copy['username'] = ''
        if proxy_copy.get('password'):
            try:
                proxy_copy['password'] = crypto.encrypt(proxy_copy['password'])
            except Exception as e:
                logger.error(f'Ошибка шифрования пароля для прокси {proxy_copy.get("proxyId", "?")}: {e}')
                proxy_copy['password'] = ''
        to_save['proxies'].append(proxy_copy)

    proxy_count = len(to_save['proxies'])
    mask_count = len(to_save['masks'])
    logger.info(f'Конфигурация сохранена: {proxy_count} прокси, {mask_count} масок')
    _invalidate_cache()
    save_raw(to_save)


def get_all_proxies() -> list:
    """Возвращает список всех прокси из конфига (с расшифрованными паролями)."""
    return load_config().get('proxies', [])


def get_all_masks() -> list:
    """Возвращает список всех масок из конфига."""
    return load_config().get('masks', [])


def is_enabled() -> bool:
    """Возвращает глобальный флаг включения/выключения прокси (из памяти)."""
    return _ENABLED
