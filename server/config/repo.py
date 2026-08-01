"""
Низкоуровневый репозиторий для config.json.

Единственная ответственность: чтение и запись JSON-файла конфигурации.
Без шифрования, без бизнес-логики.
"""

import json
import logging
import os

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.config_repo')

# Путь к файлу конфигурации.
CONFIG_FILE = os.path.join(get_data_dir(), 'config.json')

# Конфиг по умолчанию, создаётся при первом запуске
# isEnabled хранится только в памяти (config.py), не в файле
DEFAULT_CONFIG = {
    'proxies': [],
    'masks': [],
}


def load_raw(config_path: str | None = None) -> dict:
    """Читает и возвращает содержимое config.json.
    Если файла нет — создаёт с настройками по умолчанию."""
    path = config_path or CONFIG_FILE
    if not os.path.exists(path):
        logger.info(
            'Файл конфигурации %s не найден, создаю с настройками по умолчанию',
            path
        )
        save_raw(DEFAULT_CONFIG, config_path=path)
        return dict(DEFAULT_CONFIG)

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            proxies = len(data.get('proxies', []))
            masks = len(data.get('masks', []))
            logger.debug(
                'Конфигурация загружена из %s: %d прокси, %d масок',
                path, proxies, masks
            )
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error('Ошибка чтения %s: %s', path, e)
        raise RuntimeError(f'Ошибка загрузки {path}: {e}') from e


def save_raw(data: dict, config_path: str | None = None) -> None:
    """Записывает словарь в config.json атомарно.

    Сначала пишет во временный файл, затем переименовывает через os.replace.
    Это гарантирует, что при сбое посреди записи config.json не останется
    повреждённым (полузаписанным).
    """
    path = config_path or CONFIG_FILE
    tmp_path = f'{path}.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        logger.debug('Конфигурация сохранена в %s', path)
    except OSError as e:
        logger.error('Ошибка записи %s: %s', path, e)
        # Пытаемся убрать временный файл, если он остался
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
