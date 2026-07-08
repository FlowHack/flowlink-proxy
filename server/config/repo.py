"""
Низкоуровневый репозиторий для config.json.

Единственная ответственность: чтение и запись JSON-файла конфигурации.
Без шифрования, без бизнес-логики.
"""

import json
import logging
import os
import sys

logger = logging.getLogger('flowlink.config_repo')

# Путь к файлу конфигурации.
# В режиме PyInstaller (.frozen) — рядом с исполняемым файлом,
# иначе — в текущей рабочей директории.
if getattr(sys, 'frozen', False):
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'config.json')
else:
    CONFIG_FILE = 'config.json'

# Конфиг по умолчанию, создаётся при первом запуске
DEFAULT_CONFIG = {
    'proxies': [],
    'masks': [],
    'isEnabled': True,
}


def _get_config_path() -> str:
    """Возвращает путь к файлу config.json."""
    return CONFIG_FILE


def load_raw(config_path: str | None = None) -> dict:
    """Читает и возвращает содержимое config.json. Если файла нет — создаёт с настройками по умолчанию."""
    path = config_path or CONFIG_FILE
    if not os.path.exists(path):
        logger.info(f'Файл конфигурации {path} не найден, создаю с настройками по умолчанию')
        save_raw(DEFAULT_CONFIG, config_path=path)
        return dict(DEFAULT_CONFIG)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f'Конфигурация загружена из {path}: {len(data.get("proxies", []))} прокси, {len(data.get("masks", []))} масок')
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f'Ошибка чтения {path}: {e}')
        raise RuntimeError(f'Ошибка загрузки {path}: {e}')


def save_raw(data: dict, config_path: str | None = None):
    """Записывает словарь в config.json."""
    path = config_path or CONFIG_FILE
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f'Конфигурация сохранена в {path}')
    except OSError as e:
        logger.error(f'Ошибка записи {path}: {e}')
        raise
