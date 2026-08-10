"""
Локализация бэкенда FlowLink Proxy (gettext).

Единственная ответственность: управление языком интерфейса бэкенда
и предоставление функции перевода _().

Язык хранится в .flowlink-settings (ключ language) и применяется
к сообщениям об ошибках, диалогам и меню системного трея.

Использование:
  from server.i18n import _, set_language, get_language
  message = _('Не удалось сохранить настройку')
"""

from __future__ import annotations

import gettext
import logging
import os

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.i18n')

# Поддерживаемые языки (код -> имя для отображения)
SUPPORTED_LANGUAGES = {
    'ru': 'Русский',
    'en': 'English',
    'sr': 'Srpski',
}

# Язык по умолчанию
DEFAULT_LANGUAGE = 'ru'

# Путь к каталогу переводов (server/locales)
_LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locales')

# Текущий язык (кэш)
# pylint: disable=invalid-name  # модульный кэш текущего языка, не константа
_current_language = DEFAULT_LANGUAGE


def _identity(msg: str) -> str:
    """Заглушка перевода до инициализации gettext."""
    return msg


# Текущая функция перевода (gettext)
_translate = _identity


def _normalize_language(lang: str | None) -> str:
    """Нормализует код языка до поддерживаемого значения."""
    if not lang:
        return DEFAULT_LANGUAGE
    normalized = lang.lower().strip()
    # Принимаем 'ru', 'ru-RU', 'ru_RU' и т.д.
    base = normalized.split('-')[0].split('_')[0]
    return base if base in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def _load_translation(lang: str) -> gettext.NullTranslations:
    """Загружает перевод для указанного языка.

    Если .mo-файл отсутствует — возвращает NullTranslations (без перевода).
    """
    try:
        if not os.path.isdir(_LOCALES_DIR):
            return gettext.NullTranslations()
        translation = gettext.translation(
            'messages',
            localedir=_LOCALES_DIR,
            languages=[lang],
            fallback=True,
        )
        return translation
    except OSError as e:
        logger.warning('Не удалось загрузить перевод для %s: %s', lang, e)
        return gettext.NullTranslations()


def set_language(lang: str | None) -> str:
    """Устанавливает язык интерфейса бэкенда.

    Args:
        lang: код языка ('ru', 'en', 'sr') или None для сброса к умолчанию.

    Returns:
        Нормализованный код установленного языка.
    """
    # pylint: disable=global-statement  # обновление модульного кэша языка
    global _current_language, _translate
    normalized = _normalize_language(lang)
    _current_language = normalized
    translation = _load_translation(normalized)
    _translate = translation.gettext
    logger.info('Язык интерфейса: %s', normalized)
    return normalized


def get_language() -> str:
    """Возвращает текущий язык интерфейса бэкенда."""
    return _current_language


def init_i18n(lang: str | None = None) -> str:
    """Инициализирует локализацию при старте бэкенда.

    Если lang не передан — читает сохранённый язык из .flowlink-settings.

    Returns:
        Нормализованный код установленного языка.
    """
    if lang is None:
        lang = _read_stored_language()
    return set_language(lang)


def _read_stored_language() -> str:
    """Читает сохранённый язык из .flowlink-settings."""
    settings_file = os.path.join(get_data_dir(), '.flowlink-settings')
    try:
        if not os.path.isfile(settings_file):
            return DEFAULT_LANGUAGE
        with open(settings_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                if key.strip() == 'language':
                    return _normalize_language(value.strip())
    except OSError as e:
        logger.warning('Не удалось прочитать язык из %s: %s', settings_file, e)
    return DEFAULT_LANGUAGE


def _(message: str) -> str:
    """Переводит строку на текущий язык интерфейса."""
    return _translate(message)
