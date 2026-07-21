"""
Управление настройкой автозапуска браузера FlowLink Proxy.

Единственная ответственность: чтение/запись настройки autostart_browser
в файл .flowlink-settings.

Формат .flowlink-settings (совместим с bash source и batch for /f):
  autostart_browser=true
  browser_path=/usr/bin/google-chrome
"""

import logging
import os

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.autostart')

_SETTINGS_FILENAME = '.flowlink-settings'

SETTINGS_FILE = os.path.join(get_data_dir(), _SETTINGS_FILENAME)

_KEY_AUTOSTART_BROWSER = 'autostart_browser'

_DEFAULT_AUTOSTART_BROWSER = True


def parse_settings(content: str) -> dict:
    """
    Парсит содержимое .flowlink-settings в словарь.

    Формат: строки вида key=value (без кавычек).
    Комментарии: строки, начинающиеся с #.
    Пустые строки пропускаются.
    """
    settings = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        settings[key.strip()] = value.strip()
    return settings


def format_settings(settings: dict) -> str:
    """Форматирует словарь настроек в текст для файла."""
    lines = []
    for key, value in settings.items():
        lines.append(f'{key}={value}')
    return '\n'.join(lines) + '\n'


def get_autostart_browser() -> bool:
    """
    Возвращает текущее значение настройки autostart_browser.

    Returns:
        True если браузер должен запускаться автоматически (по умолчанию).
        False если автозапуск браузера отключён.
    """
    path = SETTINGS_FILE
    if not os.path.isfile(path):
        return _DEFAULT_AUTOSTART_BROWSER

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        settings = parse_settings(content)
        raw = settings.get(_KEY_AUTOSTART_BROWSER, '').lower()
        if raw in ('true', '1', 'yes', 'on'):
            return True
        if raw in ('false', '0', 'no', 'off'):
            return False
        return _DEFAULT_AUTOSTART_BROWSER
    except OSError as e:
        logger.warning(
            'Не удалось прочитать %s: %s. Используется значение по умолчанию.',
            path, e,
        )
        return _DEFAULT_AUTOSTART_BROWSER


def set_autostart_browser(value: bool) -> None:
    """
    Устанавливает настройку autostart_browser и записывает в файл.

    Args:
        value: True — браузер запускается автоматически.
               False — автозапуск браузера отключён.

    Raises:
        OSError: Не удалось записать файл настроек.
    """
    path = SETTINGS_FILE

    existing = {}
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing = parse_settings(f.read())
        except OSError as e:
            logger.warning('Не удалось прочитать %s перед записью: %s', path, e)

    existing[_KEY_AUTOSTART_BROWSER] = 'true' if value else 'false'
    content = format_settings(existing)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(
            'Автозапуск браузера: %s',
            'включён' if value else 'выключен',
        )
    except OSError as e:
        logger.error(
            'Не удалось записать %s: %s. '
            'Изменение не будет применено при следующем запуске.', path, e,
        )
        raise


# ─── Загрузка расширения при запуске браузера ───


_KEY_EXT_ENABLED = 'ext_enabled'
_DEFAULT_EXT_ENABLED = False


def get_ext_enabled() -> bool:
    """
    Возвращает, включена ли загрузка расширения при запуске браузера.

    Returns:
        True если расширение должно загружаться, иначе False.
    """
    path = SETTINGS_FILE
    if not os.path.isfile(path):
        return _DEFAULT_EXT_ENABLED
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = parse_settings(f.read())
        val = settings.get(_KEY_EXT_ENABLED, str(_DEFAULT_EXT_ENABLED)).lower()
        return val in ('true', '1', 'yes', 'on')
    except OSError as e:
        logger.warning('Не удалось прочитать ext_enabled: %s', e)
        return _DEFAULT_EXT_ENABLED


def set_ext_enabled(value: bool) -> None:
    """
    Устанавливает флаг загрузки расширения.

    Args:
        value: True — загружать расширение, False — не загружать.

    Raises:
        OSError: Не удалось записать файл настроек.
    """
    path = SETTINGS_FILE
    existing = {}
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing = parse_settings(f.read())
        except OSError as e:
            logger.warning('Не удалось прочитать %s перед записью: %s', path, e)

    existing[_KEY_EXT_ENABLED] = str(value).lower()
    content = format_settings(existing)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(
            'Загрузка расширения при запуске браузера: %s',
            'включена' if value else 'выключена',
        )
    except OSError as e:
        logger.error('Не удалось записать ext_enabled: %s', e)
        raise
