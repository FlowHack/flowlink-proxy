"""
Управление автозапуском браузера FlowLink Proxy.

Единственная ответственность: чтение/запись настройки autostart_browser
в файл .flowlink-settings и обнаружение скриптов запуска.

Формат .flowlink-settings (совместим с bash source и batch for /f):
  # комментарий
  autostart_browser=true

Скрипты запуска ищутся в нескольких директориях для поддержки
различных способов установки (standalone, dev, mixed-ОС).
"""

import logging
import os
import sys

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.autostart')

# Имя файла настроек рядом с config.json в data-директории
_SETTINGS_FILENAME = '.flowlink-settings'

# Путь к файлу настроек (переменная модуля, подменяется в тестах)
SETTINGS_FILE = os.path.join(get_data_dir(), _SETTINGS_FILENAME)

# Ключ настройки автозапуска браузера
_KEY_AUTOSTART_BROWSER = 'autostart_browser'

# Значение по умолчанию — True (браузер запускается вместе с бэкендом)
_DEFAULT_AUTOSTART_BROWSER = True

# Имена скриптов запуска, которые ищем рядом с бэкендом
_LAUNCH_SCRIPT_NAMES = [
    'FlowLink Proxy.bat',
    'FlowLink Proxy.sh',
    'FlowLink Proxy Source.sh',
]


def _parse_settings(content: str) -> dict:
    """
    Парсит содержимое .flowlink-settings в словарь.

    Формат: строки вида key=value (без кавычек).
    Комментарии: строки, начинающиеся с #.
    Пустые строки пропускаются.

    Args:
        content: Текстовое содержимое файла настроек.

    Returns:
        Словарь {key: value_string} с_STRIP=True.
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


def _format_settings(settings: dict) -> str:
    """
    Форматирует словарь настроек в текст для файла.

    Args:
        settings: Словарь {key: value}.

    Returns:
        Текст в формате key=value, разделённый переносами строк.
    """
    lines = []
    for key, value in settings.items():
        lines.append(f'{key}={value}')
    return '\n'.join(lines) + '\n'


def get_autostart_browser() -> bool:
    """
    Возвращает текущее значение настройки autostart_browser.

    Reads:
        .flowlink-settings в data-директории.

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
        settings = _parse_settings(content)
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

    Файл .flowlink-settings совместим с bash source и batch for /f,
    что позволяет скриптам запуска читать значение без Python.

    Args:
        value: True — браузер запускается автоматически.
               False — автозапуск браузера отключён.

    Raises:
        OSError: Не удалось записать файл настроек.
    """
    path = SETTINGS_FILE

    # Читаем существующие настройки, чтобы сохранить другие ключи
    existing = {}
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing = _parse_settings(f.read())
        except OSError as e:
            logger.warning('Не удалось прочитать %s перед записью: %s', path, e)

    existing[_KEY_AUTOSTART_BROWSER] = 'true' if value else 'false'
    content = _format_settings(existing)

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


def _get_search_dirs() -> list[str]:
    """
    Возвращает список директорий для поиска скриптов запуска.

    Проверяет:
    1. Директория рядом с исполняемым файлом (standalone / frozen build).
    2. Текущая рабочая директория (python -m server).
    3. Поддиректория scripts/ относительно рабочей директории.
    4. Директория рядом с исходным файлом __main__.py (dev-режим).
    """
    dirs = []

    # 1. Рядом с исполняемым файлом (standalone exe / frozen build)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if exe_dir not in dirs:
            dirs.append(exe_dir)

    # 2. Текущая рабочая директория
    cwd = os.getcwd()
    if cwd not in dirs:
        dirs.append(cwd)

    # 3. Поддиректория scripts/
    scripts_dir = os.path.join(cwd, 'scripts')
    if os.path.isdir(scripts_dir) and scripts_dir not in dirs:
        dirs.append(scripts_dir)

    # 4. Директория рядом с __main__.py (dev-режим)
    main_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '__main__.py'),
    )
    main_dir = os.path.dirname(main_file)
    if os.path.isfile(main_file) and main_dir not in dirs:
        dirs.append(main_dir)

    # 5. Поддиректория scripts/ относительно dev-директории
    if os.path.isfile(main_file):
        dev_scripts = os.path.join(main_dir, '..', 'scripts')
        dev_scripts = os.path.normpath(dev_scripts)
        if os.path.isdir(dev_scripts) and dev_scripts not in dirs:
            dirs.append(dev_scripts)

    return dirs


def find_launch_scripts() -> dict[str, list[str]]:
    """
    Ищет скрипты запуска во всех возможных директориях.

    Возвращает словарь {имя_скрипта: [список_путей]}.
    Скрипт считается найденным, если файл существует и доступен для чтения.

    Returns:
        Словарь вида:
        {
            'FlowLink Proxy.bat': ['/path/to/FlowLink Proxy.bat'],
            'FlowLink Proxy.sh': ['/path/to/FlowLink Proxy.sh'],
            'FlowLink Proxy Source.sh': [],
        }
    """
    search_dirs = _get_search_dirs()
    result = {name: [] for name in _LAUNCH_SCRIPT_NAMES}

    for search_dir in search_dirs:
        for script_name in _LAUNCH_SCRIPT_NAMES:
            script_path = os.path.join(search_dir, script_name)
            if os.path.isfile(script_path):
                # Избегаем дубликатов (один и тот же файл через разные пути)
                real_path = os.path.realpath(script_path)
                already_found = any(
                    os.path.realpath(p) == real_path
                    for p in result[script_name]
                )
                if not already_found:
                    result[script_name].append(script_path)
                    logger.debug(
                        'Найден скрипт запуска: %s', script_path,
                    )

    total_found = sum(len(paths) for paths in result.values())
    if total_found == 0:
        logger.info(
            'Скрипты запуска не найдены в директориях: %s',
            ', '.join(search_dirs),
        )
    else:
        logger.debug(
            'Найдено скриптов запуска: %d (%s)',
            total_found,
            ', '.join(
                f'{name} ({len(paths)})'
                for name, paths in result.items()
                if paths
            ),
        )

    return result


def any_launch_script_found() -> bool:
    """
    Проверяет, найден ли хотя бы один скрипт запуска.

    Returns:
        True если найден хотя бы один скрипт запуска.
    """
    scripts = find_launch_scripts()
    return any(len(paths) > 0 for paths in scripts.values())


def get_autostart_status() -> dict:
    """
    Возвращает полный статус автозапуска браузера для API-ответа.

    Returns:
        Словарь:
        {
            "autostartBrowser": bool,      # текущее значение настройки
            "launchScriptsFound": bool,     # найден ли хотя бы один скрипт
            "launchScripts": {              # найденные скрипты по именам
                "FlowLink Proxy.bat": ["/path/to/script.bat"],
                ...
            }
        }
    """
    scripts = find_launch_scripts()
    found = any(len(paths) > 0 for paths in scripts.values())
    return {
        'autostartBrowser': get_autostart_browser(),
        'launchScriptsFound': found,
        'launchScripts': scripts,
    }
