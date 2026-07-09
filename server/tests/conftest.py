"""
Общие фикстуры для тестов.
"""

import json
import os
import tempfile


def create_temp_config(config_data: dict) -> str:
    """Создаёт временный config.json и возвращает путь к нему."""
    tmpdir = tempfile.mkdtemp()
    config_path = os.path.join(tmpdir, 'config.json')
    if config_data is not None:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
    return config_path
