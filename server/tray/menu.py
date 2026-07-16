"""
Общая логика построения меню и загрузки иконки для всех трей-бэкендов.

Единственная ответственность: дедупликация кода между
Linux, macOS и Win32 трей-модулями.
"""

from __future__ import annotations

import types
from typing import Any, Callable, Dict, List, Optional

import logging
import os
import webbrowser

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.tray.menu')

_ICON_PATH = os.path.join('icons', 'icon.png')
_DEFAULT_ICON_SIZE = (64, 64)


def load_icon(
    pil_image: types.ModuleType,
    logger_name: str = 'flowlink.tray',
    force_fallback: bool = False,
) -> Any:
    """
    Загружает иконку трей из файла.

    Если файл иконки не найден или force_fallback=True — создаёт
    дефолтную: красный круг с «FLP» (16×16, масштабируется до 64×64).

    Args:
        pil_image: Модуль PIL.Image (передаётся вызывающим кодом).
        logger_name: Имя логгера для предупреждений.
        force_fallback: Принудительно использовать дефолтную иконку.

    Returns:
        PIL.Image (64x64 RGBA).
    """
    icon_logger = logging.getLogger(logger_name)
    # Ленивый импорт: избегает циклических зависимостей
    from server.utils import get_resource_dir  # pylint: disable=import-outside-toplevel
    icon_path = os.path.normpath(
        os.path.join(get_resource_dir(), _ICON_PATH),
    )

    if not force_fallback and os.path.exists(icon_path):
        img = pil_image.open(icon_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img.resize(_DEFAULT_ICON_SIZE, pil_image.Resampling.LANCZOS)

    if force_fallback:
        icon_logger.info(
            '%s: --test-fallback-icon, пропуск %s',
            logger_name, icon_path,
        )
    else:
        icon_logger.warning(
            '%s: иконка %s не найдена, создание дефолтной',
            logger_name, icon_path,
        )
    return _create_fallback_icon(pil_image)


def _create_fallback_icon(pil_image: types.ModuleType) -> Any:
    """
    Создаёт дефолтную иконку: красный круг с «FLP».

    Args:
        pil_image: Модуль PIL.Image.

    Returns:
        PIL.Image (16x16 RGBA, масштабируется до 64x64).
    """
    import PIL.ImageDraw as _draw  # pylint: disable=import-outside-toplevel
    import PIL.ImageFont as _font  # pylint: disable=import-outside-toplevel

    size = 16
    img = pil_image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = _draw.Draw(img)

    draw.ellipse([1, 1, size - 2, size - 2], fill=(231, 76, 60, 255))

    try:
        font = _font.truetype('arial.ttf', 7)
    except OSError:
        try:
            font = _font.truetype(
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 7,
            )
        except OSError:
            font = _font.load_default()

    bbox = draw.textbbox((0, 0), 'FLP', font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - 1
    draw.text((tx, ty), 'FLP', fill=(0, 0, 0, 255), font=font)

    return img.resize(_DEFAULT_ICON_SIZE, pil_image.Resampling.LANCZOS)


def get_autostart_state(callbacks: Dict[str, Any], logger_name: str = 'flowlink.tray') -> bool:
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


def safe_open_folder(path: str, label: str, log: logging.Logger) -> None:
    """Безопасно открывает папку в файловом менеджере."""
    try:
        os.makedirs(path, exist_ok=True)
        webbrowser.open(f'file://{os.path.normpath(path)}')
    except OSError as exc:
        log.error(
            '%s: не удалось открыть %s (%s): %s',
            'Tray', label, path, exc,
        )


def _get_system_autostart_state(callbacks: Dict[str, Any], logger_name: str) -> bool:
    """Безопасно читает текущее состояние системного автозапуска."""
    if not callbacks.get('system_autostart_getter'):
        return False
    try:
        return callbacks['system_autostart_getter']()
    except (OSError, TypeError, AttributeError) as e:
        logging.getLogger(logger_name).error(
            '%s: ошибка чтения system_autostart: %s', logger_name, e,
        )
        return False


def build_menu_items(callbacks: Dict[str, Any], stop_fn: Callable[[], None], logger_name: str = 'flowlink.tray') -> List[Dict[str, Any]]:
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
            system_autostart_getter: Callable → bool — чтение системного автозапуска.
            system_autostart_setter: Callable(bool) — запись системного автозапуска.
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
    system_autostart_enabled = _get_system_autostart_state(callbacks, logger_name)

    def _safe_open_folder(path: str, label: str) -> None:
        """Безопасно открывает папку в файловом менеджере."""
        safe_open_folder(path, label, log)

    def _open_logs() -> None:
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

    def _clear_logs() -> None:
        log.info('Tray: очистка логов')
        if callbacks.get('clear_logs'):
            try:
                callbacks['clear_logs']()
            except OSError as exc:
                log.error('Tray: ошибка очистки логов: %s', exc)

    def _open_data() -> None:
        log.info('Tray: открытие папки данных')
        try:
            data_dir = get_data_dir()
        except OSError as exc:
            log.error('Tray: get_data_dir() ошибка: %s', exc)
            return
        _safe_open_folder(data_dir, 'данные')

    def _clear_data() -> None:
        log.info('Tray: очистка всех данных')
        if callbacks.get('clear_data'):
            try:
                callbacks['clear_data']()
            except OSError as exc:
                log.error(
                    'Tray: ошибка очистки данных: %s', exc,
                )

    def _toggle_autostart() -> None:
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

    def _toggle_system_autostart() -> None:
        new_val = not system_autostart_enabled
        log.info(
            'Tray: автозапуск с системой → %s',
            'включён' if new_val else 'выключен',
        )
        if callbacks.get('system_autostart_setter'):
            try:
                callbacks['system_autostart_setter'](new_val)
            except OSError as exc:
                log.error(
                    'Tray: ошибка записи system_autostart: %s', exc,
                )

    def _exit() -> None:
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
        {
            'type': 'check',
            'text': 'Запуск с системой',
            'icon': '\U0001f50a',
            'checked': system_autostart_enabled,
            'command': _toggle_system_autostart,
        },
        {'type': 'separator'},
        {
            'type': 'item', 'text': 'Выход',
            'icon': '\u274c', 'color': '#e74c3c',
            'command': _exit,
        },
    ]
