"""
Утилиты для debug-режима: безопасное логирование конфига и HTTP-тел.

Единственная ответственность: вспомогательные функции для debug-логов
без бизнес-логики и без утечки чувствительных данных.
"""

from __future__ import annotations

import logging
import re

from server.config import config as cfg

logger = logging.getLogger('flowlink.debug')

# Регулярка для маскировки паролей в JSON-строках.
# Ищет "password":"значение" и заменяет значение на "***".
# Учитывает экранированные кавычки внутри значения (\").
_PASSWORD_RE = re.compile(r'"password"\s*:\s*"(?:[^"\\]|\\.)*"')


_USERNAME_RE = re.compile(r'"username"\s*:\s*"(?:[^"\\]|\\.)*"')


# Дополнительные чувствительные поля, которые маскируются в логах.
# Покрывает токены, ключи API и заголовки авторизации.
_SENSITIVE_FIELDS = (
    'token',
    'api_key',
    'apikey',
    'access_token',
    'authorization',
    'secret',
)


def _mask_field(body_str: str, field: str) -> str:
    """Маскирует значение поля field в JSON-строке.

    Args:
        body_str: Исходная JSON-строка.
        field: Имя поля для маскировки (без кавычек).

    Returns:
        Строка с замаскированным значением поля.
    """
    pattern = re.compile(
        rf'"{re.escape(field)}"\s*:\s*"(?:[^"\\]|\\.)*"',
        re.IGNORECASE,
    )
    return pattern.sub(f'"{field}":"***"', body_str)


def mask_sensitive(body_str: str) -> str:
    """
    Маскирует чувствительные поля в JSON-строке для безопасного логирования.

    Заменяет "password", "username" и другие секретные поля (token,
    api_key, access_token, authorization, secret) на "***". Учитывает
    экранированные кавычки внутри значений.
    """
    body_str = _PASSWORD_RE.sub('"password":"***"', body_str)
    body_str = _USERNAME_RE.sub('"username":"***"', body_str)
    for field in _SENSITIVE_FIELDS:
        body_str = _mask_field(body_str, field)
    return body_str


def truncate(text: str, max_len: int = 2000) -> str:
    """
    Обрезает строку до max_len символов, добавляя '... (обрезано)'.

    Используется для предотвращения раздувания логов большими JSON-ответами.
    """
    if len(text) > max_len:
        return text[:max_len] + '... (обрезано)'
    return text


def log_config_state(is_startup: bool = False) -> None:
    """Выводит текущее состояние конфига в debug-лог (без паролей).

    Args:
        is_startup: Если True — выводит начальное сообщение при старте сервера.
            Если False — выводит сообщение после сохранения конфига.
    """
    data = cfg.load_config()
    proxies = data.get('proxies', [])
    masks = data.get('masks', [])

    if is_startup:
        logger.debug('Загружено прокси: %d', len(proxies))
    else:
        logger.debug('Конфиг после сохранения: %d прокси, %d масок', len(proxies), len(masks))

    for p in proxies:
        logger.debug('  прокси %s — %s:%s (включён: %s)',
                     p.get('proxyId', '?'), p.get('host', '?'),
                     p.get('port', '?'), p.get('isEnabled', True))

    logger.debug('Загружено масок: %d', len(masks))
    for m in masks:
        if is_startup:
            logger.debug('  маска %s — %s → прокси %s',
                         m.get('maskId', '?'), m.get('pattern', '?'),
                         m.get('proxyId', '?'))
        else:
            logger.debug('  маска %s — %s', m.get('maskId', '?'), m.get('pattern', '?'))
