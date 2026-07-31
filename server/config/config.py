"""
Сервисный слой конфигурации FlowLink Proxy.

Загружает/сохраняет конфиг через repo, шифрует/расшифровывает пароли.
Предоставляет доступ к полям конфига (get_all_proxies, get_all_masks, is_enabled).
isEnabled хранится ТОЛЬКО в памяти — расширение управляет им через POST /api/enabled.
Единственная ответственность: управление конфигурацией с шифрованием.
"""

from __future__ import annotations

import copy
import logging
import time

from server.config import crypto
from server.config import repo as config_repo
from server.config.repo import load_raw, save_raw

try:
    # cryptography — runtime зависимость
    from cryptography.exceptions import \
        CryptographyException  # type: ignore[reportAttributeAccessIssue]; type: ignore[reportAttributeAccessIssue]
except ImportError:
    CryptographyException = Exception  # type: ignore[misc]  # fallback для сред без cryptography

logger = logging.getLogger('flowlink.config')

_CACHE: dict = {}
_CACHE_TIME: dict[str, float] = {}
_CACHE_TTL: float = 1.0

# Глобальный флаг включения хранится только в памяти (не в config.json)
# По умолчанию True — расширение при старте пришлёт актуальное состояние
_STATE: dict = {'enabled': True}


def _cache_key() -> str:
    """Возвращает путь к файлу конфига как ключ кэша."""
    return config_repo.CONFIG_FILE


def _crypto_field(
    value: str,
    operation: str,
    proxy_id: str,
    field_name: str,
    *,
    encrypt: bool = False,
) -> str:
    """Шифрует или расшифровывает одно поле прокси (username/password).

    При ошибке логирует предупреждение/ошибку и возвращает пустую строку,
    чтобы не прерывать обработку остальных прокси.

    Args:
        value: Значение поля для шифрования/дешифрования.
        operation: Описание операции для сообщения об ошибке.
        proxy_id: Идентификатор прокси (для логирования).
        field_name: Имя поля (для логирования).
        encrypt: True для шифрования, False для дешифрования.

    Returns:
        Зашифрованное/расшифрованное значение или пустая строка при ошибке.
    """
    try:
        return crypto.encrypt(value) if encrypt else crypto.decrypt(value)
    except (ValueError, OSError, CryptographyException, ImportError) as e:
        level = logger.error if encrypt else logger.warning
        level(
            'Ошибка %s для прокси %s, поле %s: %s',
            operation, proxy_id, field_name, e,
        )
        return ''


def _load_cached() -> dict:
    """Загружает конфиг с кэшированием на _CACHE_TTL секунд."""
    key = _cache_key()
    now = time.monotonic()
    if key in _CACHE and now - _CACHE_TIME.get(key, 0) < _CACHE_TTL:
        return _CACHE[key]
    _CACHE[key] = load_raw()
    _CACHE_TIME[key] = now
    return _CACHE[key]


def invalidate_cache() -> None:
    """Сбрасывает кэш после сохранения."""
    key = _cache_key()
    _CACHE.pop(key, None)
    _CACHE_TIME.pop(key, None)


def _decrypt_proxies(data: dict) -> dict:
    """Расшифровывает username/password у всех прокси."""
    for proxy in data.get('proxies', []):
        if proxy.get('username'):
            proxy['username'] = _crypto_field(
                proxy['username'], 'расшифровки имени',
                proxy.get('proxyId', '?'), 'username',
            )
        if proxy.get('password'):
            proxy['password'] = _crypto_field(
                proxy['password'], 'расшифровки пароля',
                proxy.get('proxyId', '?'), 'password',
            )
    return data


def load_config(force: bool = False) -> dict:
    """Загружает конфиг и расшифровывает username/password."""
    data = load_raw() if force else _load_cached()
    return _decrypt_proxies(copy.deepcopy(data))


def set_enabled(val: bool) -> None:
    """Устанавливает глобальный флаг включения (только в памяти)."""
    _STATE['enabled'] = bool(val)
    logger.info(
        'Глобальный переключатель: %s',
        'включён' if _STATE['enabled'] else 'выключен'
    )


def save_config(data: dict) -> None:
    """Шифрует username/password и сохраняет конфиг.
    isEnabled НЕ пишется в файл — хранится только в памяти."""
    to_save = {
        'proxies': [],
        'masks': data.get('masks', []),
    }

    for proxy in data.get('proxies', []):
        proxy_copy = dict(proxy)
        if proxy_copy.get('username'):
            proxy_copy['username'] = _crypto_field(
                proxy_copy['username'], 'шифрования имени',
                proxy_copy.get('proxyId', '?'), 'username',
                encrypt=True,
            )
        if proxy_copy.get('password'):
            proxy_copy['password'] = _crypto_field(
                proxy_copy['password'], 'шифрования пароля',
                proxy_copy.get('proxyId', '?'), 'password',
                encrypt=True,
            )
        to_save['proxies'].append(proxy_copy)

    proxy_count = len(to_save['proxies'])
    mask_count = len(to_save['masks'])
    logger.info(
        'Конфигурация сохранена: %d прокси, %d масок',
        proxy_count, mask_count
    )
    invalidate_cache()
    try:
        save_raw(to_save)
    except OSError as e:
        logger.error(
            'Не удалось записать конфиг на диск: %s. '
            'Убедитесь, что диск не переполнен.', e,
        )
        raise


def get_all_proxies() -> list:
    """Возвращает список всех прокси из конфига (с расшифрованными паролями)."""
    return load_config().get('proxies', [])


def get_all_masks() -> list:
    """Возвращает список всех масок из конфига."""
    return load_config().get('masks', [])


def is_enabled() -> bool:
    """Возвращает глобальный флаг включения/выключения прокси (из памяти)."""
    return _STATE['enabled']


def inject_proxies(data: dict) -> int:
    """
    Дописывает прокси и маски в config.json, не перезаписывая существующие.

    Используется для инъекции фиктивных прокси в debug-режиме (флаг --count-proxy).
    Не шифрует пароли — фиктивные прокси не требуют шифрования.

    Args:
        data: Словарь с ключами 'proxies' (список прокси) и 'masks' (список масок).

    Returns:
        Количество добавленных прокси.
    """
    try:
        existing = _load_cached()
    except (OSError, RuntimeError):
        existing = {'proxies': [], 'masks': []}

    existing_proxies = existing.get('proxies', [])
    existing_masks = existing.get('masks', [])

    new_proxies = data.get('proxies', [])
    new_masks = data.get('masks', [])

    merged = {
        'proxies': existing_proxies + new_proxies,
        'masks': existing_masks + new_masks,
    }

    invalidate_cache()
    save_raw(merged)

    proxy_count = len(merged['proxies'])
    mask_count = len(merged['masks'])
    logger.info(
        'Инъекция прокси: добавлено %d прокси и %d масок '
        '(всего: %d прокси, %d масок)',
        len(new_proxies), len(new_masks), proxy_count, mask_count,
    )
    return len(new_proxies)
