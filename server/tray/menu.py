"""
Общая логика построения меню и загрузки иконки для всех трей-бэкендов.

Единственная ответственность: дедупликация кода между
Linux, macOS и Win32 трей-модулями.
"""

import logging
import os
import webbrowser

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.tray.menu')

_ICON_PATH = 'icons/icon.png'
_DEFAULT_ICON_SIZE = (64, 64)
_DEFAULT_ICON_COLOR = (45, 105, 165, 255)


def load_icon(pil_image, logger_name='flowlink.tray'):
    """
    Загружает иконку трей из файла.

    Если файл иконки не найден — создаёт заглушку синего цвета.

    Args:
        pil_image: Модуль PIL.Image (передаётся вызывающим кодом).
        logger_name: Имя логгера для предупреждений.

    Returns:
        PIL.Image (64x64 RGBA).
    """
    icon_logger = logging.getLogger(logger_name)
    from server.utils import get_resource_dir
    icon_path = os.path.join(get_resource_dir(), _ICON_PATH)

    if os.path.exists(icon_path):
        img = pil_image.open(icon_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img.resize(_DEFAULT_ICON_SIZE, pil_image.Resampling.LANCZOS)

    icon_logger.warning(
        '%s: иконка %s не найдена', logger_name, icon_path,
    )
    return pil_image.new(
        'RGBA', _DEFAULT_ICON_SIZE, _DEFAULT_ICON_COLOR,
    )


def get_autostart_state(callbacks, logger_name='flowlink.tray'):
    """
    Безопасно читает текущее состояние автозапуска.

    Args:
        callbacks: Словарь коллбэков (может содержать autostart_getter).
        logger_name: Имя логгера для ошибок.

    Returns:
        bool — текущее значение автозапуска (False при ошибке).
    """
    if not callbacks.get('autostart_getter'):
        return False
    try:
        return callbacks['autostart_getter']()
    except (OSError, TypeError, AttributeError) as e:
        logging.getLogger(logger_name).error(
            '%s: ошибка чтения autostart: %s', logger_name, e,
        )
        return False


def safe_open_folder(path, label, log):
    """Безопасно открывает папку в файловом менеджере."""
    try:
        os.makedirs(path, exist_ok=True)
        webbrowser.open(f'file://{os.path.normpath(path)}')
    except OSError as exc:
        log.error(
            '%s: не удалось открыть %s (%s): %s',
            'Tray', label, path, exc,
        )


def build_menu_items(callbacks, stop_fn, logger_name='flowlink.tray'):
    """
    Строит список пунктов меню для popup.

    Используется всеми трей-бэкендами (Linux, macOS, Win32).

    Каждый пункт меню — словарь с ключами:
      type: 'item' | 'check' | 'separator' | 'header'
      text: Отображаемый текст
      icon: Unicode-символ (опционально)
      command: Callable, вызываемый при клике
      color: Цвет текста (для 'item') или галочки (для 'check')

    Замыкания внутри формируются динамически и привязаны к callbacks
    на момент построения меню. Autostart читается один раз —
    popup пересоздаётся при каждом открытии.

    Args:
        callbacks: Словарь коллбэков:
            stop: Callable — остановка сервера.
            autostart_getter: Callable → bool — чтение настройки.
            autostart_setter: Callable(bool) — запись настройки.
            log_dir_getter: Callable → str — путь к папке логов.
            data_dir_getter: Callable → str — путь к папке данных.
            clear_logs: Callable — очистка логов.
            clear_data: Callable — очистка данных.
        stop_fn: Callable — остановка трей-иконки (вызывается
            перед callbacks['stop'] для корректного завершения).
        logger_name: Имя логгера для сообщений об ошибках.

    Returns:
        Список словарей с описанием пунктов меню.
    """
    log = logging.getLogger(logger_name)
    autostart_enabled = get_autostart_state(callbacks, logger_name)

    def _safe_open_folder(path, label):
        """Безопасно открывает папку в файловом менеджере."""
        safe_open_folder(path, label, log)

    def _open_logs():
        log.info('Tray: открытие папки логов')
        if callbacks.get('log_dir_getter'):
            try:
                log_dir = callbacks['log_dir_getter']()
            except (OSError, TypeError) as exc:
                log.error(
                    'Tray: log_dir_getter() ошибка: %s', exc,
                )
                return
            if log_dir:
                _safe_open_folder(log_dir, 'логи')

    def _clear_logs():
        log.info('Tray: очистка логов')
        if callbacks.get('clear_logs'):
            try:
                callbacks['clear_logs']()
            except OSError as exc:
                log.error('Tray: ошибка очистки логов: %s', exc)

    def _open_data():
        log.info('Tray: открытие папки данных')
        try:
            data_dir = get_data_dir()
        except OSError as exc:
            log.error('Tray: get_data_dir() ошибка: %s', exc)
            return
        _safe_open_folder(data_dir, 'данные')

    def _clear_data():
        log.info('Tray: очистка всех данных')
        if callbacks.get('clear_data'):
            try:
                callbacks['clear_data']()
            except OSError as exc:
                log.error(
                    'Tray: ошибка очистки данных: %s', exc,
                )

    def _toggle_autostart():
        new_val = not autostart_enabled
        log.info(
            'Tray: автозапуск браузера → %s',
            'включён' if new_val else 'выключен',
        )
        if callbacks.get('autostart_setter'):
            try:
                callbacks['autostart_setter'](new_val)
            except OSError as exc:
                log.error(
                    'Tray: ошибка записи autostart: %s', exc,
                )

    def _exit():
        log.info('Tray: выбран Выход')
        stop_fn()
        if callbacks.get('stop'):
            callbacks['stop']()

    return [
        {
            'type': 'item', 'text': 'Посмотреть логи',
            'icon': '\U0001f4dc', 'command': _open_logs,
        },
        {
            'type': 'item', 'text': 'Очистить логи',
            'icon': '\U0001f5d1\ufe0f', 'command': _clear_logs,
        },
        {
            'type': 'item', 'text': 'Посмотреть данные',
            'icon': '\U0001f4c2', 'command': _open_data,
        },
        {
            'type': 'item', 'text': 'Очистить данные',
            'icon': '\u26a0\ufe0f', 'command': _clear_data,
        },
        {'type': 'separator'},
        {
            'type': 'check',
            'text': 'Автозапуск браузера',
            'icon': '\U0001f310',
            'checked': autostart_enabled,
            'command': _toggle_autostart,
        },
        {'type': 'separator'},
        {
            'type': 'item', 'text': 'Выход',
            'icon': '\u274c', 'color': '#e74c3c',
            'command': _exit,
        },
    ]
