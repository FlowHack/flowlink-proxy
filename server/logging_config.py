"""
Настройка логирования для FlowLink Proxy.

Единственная ответственность: конфигурация логгера (консоль + файл с ротацией).
"""

import logging
import logging.handlers
import os
import sys


def reopen_logging(recreate: bool = True, level: int = logging.INFO) -> None:
    """
    Переоткрывает файловый хендлер логгера.

    Закрывает старый RotatingFileHandler и удаляет его из корневого логгера.
    При recreate=True создаёт новый хендлер с теми же параметрами; при
    recreate=False пропускает создание нового хендлера — файл лога
    освобождается и может быть удалён без ошибки [WinError 32].

    Args:
        recreate: Создавать ли новый хендлер после закрытия старого.
            False нужно для очистки логов: файл лога освобождается
            до удаления, а новый хендлер создаётся после (в finally).
        level: Уровень логирования для нового хендлера.
    """
    root = logging.getLogger()
    log_file = None
    old_handler = None

    # Ищем существующий RotatingFileHandler
    for handler in root.handlers[:]:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            old_handler = handler
            # type: ignore[attr-defined] — baseFilename назначается в runtime
            # в FileHandler.__init__, pyright не видит его в стабах stdlib
            log_file = handler.baseFilename  # type: ignore[attr-defined]
            break

    if old_handler is None:
        logger = logging.getLogger('flowlink')
        logger.warning(
            'reopen_logging: RotatingFileHandler не найден, '
            'переоткрытие не требуется',
        )
        return

    log_file = old_handler.baseFilename
    if log_file is None:
        logger = logging.getLogger('flowlink')
        logger.warning(
            'reopen_logging: baseFilename равен None, '
            'переоткрытие невозможно',
        )
        return

    # Закрываем и удаляем старый хендлер
    try:
        old_handler.close()
    except OSError as e:
        logger = logging.getLogger('flowlink')
        logger.warning(
            'reopen_logging: ошибка при закрытии хендлера: %s', e,
        )
    root.removeHandler(old_handler)

    # При recreate=False не создаём новый хендлер — файл лога остаётся
    # освобождённым для удаления (очистка логов).
    if not recreate:
        return

    # Создаём новый хендлер с теми же параметрами
    try:
        log_dir = os.path.dirname(log_file)
        os.makedirs(log_dir, exist_ok=True)
        fmt = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        new_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_242_880, backupCount=3, encoding='utf-8',
        )
        # Ограничиваем доступ к файлу лога: только владелец (0600)
        try:
            os.chmod(log_file, 0o600)
        except NotImplementedError:
            # На Windows os.chmod для прав доступа не поддерживается — пропускаем
            logging.getLogger('flowlink').debug(
                'reopen_logging: os.chmod не поддерживается, пропускаю'
            )
        new_handler.setLevel(level)
        new_handler.setFormatter(fmt)
        root.addHandler(new_handler)
        logger = logging.getLogger('flowlink')
        logger.info(
            'Логгер переоткрыт: %s', log_file,
        )
    except OSError as e:
        logger = logging.getLogger('flowlink')
        logger.error(
            'reopen_logging: не удалось создать новый хендлер: %s', e,
        )


def setup_logging(debug: bool = False) -> None:
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
        # Ленивый импорт для избежания циклической зависимости:
        # server.utils лениво импортирует logging_config (reopen_logging).
        # cyclic-import подавляется: pylint учитывает и локальные импорты
        # в графе циклических зависимостей, поэтому разрыв цикла возможен
        # только через исключение ребра из графа.
        from server.utils import (  # pylint: disable=import-outside-toplevel,cyclic-import
            get_data_dir
        )
        base = get_data_dir()
        log_dir = os.path.join(base, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'FlowLink Proxy.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_242_880, backupCount=3, encoding='utf-8',
        )
        # Ограничиваем доступ к файлу лога: только владелец (0600),
        # т.к. лог может содержать чувствительные данные запросов
        try:
            os.chmod(log_file, 0o600)
        except NotImplementedError:
            # На Windows os.chmod для прав доступа не поддерживается — пропускаем
            logging.getLogger('flowlink').debug(
                'setup_logging: os.chmod не поддерживается, пропускаю'
            )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as e:
        logger = logging.getLogger('flowlink')
        logger.warning('Не удалось создать папку логов: %s', e)
