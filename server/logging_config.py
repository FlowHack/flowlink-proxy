"""
Настройка логирования для FlowLink Proxy.

Единственная ответственность: конфигурация логгера (консоль + файл с ротацией).
"""

import logging
import logging.handlers
import os
import sys


def setup_logging(debug: bool = False):
    """Настраивает корневой логгер: консоль (INFO/DEBUG) + файл с ротацией (DEBUG)."""
    level = logging.DEBUG if debug else logging.INFO
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Консоль: INFO+
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Файл: DEBUG+ с ротацией
    try:
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(os.path.abspath(sys.executable))
            log_dir = os.path.join(base, 'logs')
        else:
            base = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'FlowLink Proxy.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_242_880, backupCount=3, encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as e:
        logger = logging.getLogger('flowlink')
        logger.warning(f'Не удалось создать папку логов: {e}')
