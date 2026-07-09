"""
Утилиты для debug-режима: безопасное логирование конфига и HTTP-тел.

Единственная ответственность: вспомогательные функции для debug-логов
без бизнес-логики и без утечки чувствительных данных.
"""

import logging
import re

from server.config import config as cfg

logger = logging.getLogger('flowlink.debug')

# Регулярка для маскировки паролей в JSON-строках.
# Ищет "password":"значение" и заменяет значение на "***".
_PASSWORD_RE = re.compile(r'"password"\s*:\s*"[^"]*"')


_USERNAME_RE = re.compile(r'"username"\s*:\s*"[^"]*"')


def mask_sensitive(body_str: str) -> str:
    """
    Маскирует чувствительные поля в JSON-строке для безопасного логирования.

    Заменяет "password":"значение" и "username":"значение" на "***".
    """
    body_str = _PASSWORD_RE.sub('"password":"***"', body_str)
    body_str = _USERNAME_RE.sub('"username":"***"', body_str)
    return body_str


def truncate(text: str, max_len: int = 2000) -> str:
    """
    Обрезает строку до max_len символов, добавляя '... (truncated)'.

    Используется для предотвращения раздувания логов большими JSON-ответами.
    """
    if len(text) > max_len:
        return text[:max_len] + '... (truncated)'
    return text


def log_config_state():
    """Выводит текущее состояние конфига в debug-лог (без паролей)."""
    data = cfg.load_config()
    proxies = data.get('proxies', [])
    masks = data.get('masks', [])
    logger.debug('Конфиг после сохранения: %d прокси, %d масок', len(proxies), len(masks))
    for p in proxies:
        logger.debug('  прокси %s — %s:%s (вкл: %s)',
                     p.get('proxyId', '?'), p.get('host', '?'),
                     p.get('port', '?'), p.get('enabled', True))
    for m in masks:
        logger.debug('  маска %s — %s', m.get('maskId', '?'), m.get('pattern', '?'))


def log_startup_config():
    """Выводит конфиг при старте сервера в debug-лог."""
    config_data = cfg.load_config()
    proxies = config_data.get('proxies', [])
    masks = config_data.get('masks', [])
    logger.debug('Загружено прокси: %d', len(proxies))
    for p in proxies:
        logger.debug('  прокси %s — %s:%s (включён: %s)',
                     p.get('proxyId', '?'), p.get('host', '?'),
                     p.get('port', '?'), p.get('enabled', True))
    logger.debug('Загружено масок: %d', len(masks))
    for m in masks:
        logger.debug('  маска %s — %s → прокси %s',
                     m.get('maskId', '?'), m.get('pattern', '?'),
                     m.get('proxyId', '?'))
