"""
Fallback-бэкенд трей через pystray с нативным меню.

Используется когда tkinter недоступен или передан флаг --no-tkinter.
В отличие от popup.py (tkinter безрамочное окно), здесь используется
стандартное контекстное меню pystray с символами ✓/✗ для чекбоксов.
"""

from __future__ import annotations

import logging
import threading
import types
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)
from typing import TYPE_CHECKING

from server.tray.menu import (
    load_icon,
    get_autostart_state,
    safe_open_folder,
)
from server.utils import get_data_dir

if TYPE_CHECKING:
    import pystray  # type: ignore[reportMissingImports]

logger = logging.getLogger('flowlink.tray.fallback')


def _make_actions(
    callbacks: Dict[str, Any],
    autostart_enabled: List[bool],
    system_autostart_enabled: List[bool],
    log: logging.Logger,
    refresh_fn: Callable[[pystray.Icon], None],
) -> Dict[str, Callable[[pystray.Icon], None]]:
    """Создаёт обработчики действий меню."""

    def open_logs(_icon: pystray.Icon) -> None:
        log.info('Fallback: открытие папки логов')
        if callbacks.get('log_dir_getter'):
            try:
                log_dir = callbacks['log_dir_getter']()
            except (OSError, TypeError) as exc:
                log.error('Fallback: log_dir_getter() ошибка: %s', exc)
                return
            if log_dir:
                safe_open_folder(log_dir, 'логи', log)

    def clear_logs(_icon: pystray.Icon) -> None:
        log.info('Fallback: очистка логов')
        if callbacks.get('clear_logs'):
            try:
                callbacks['clear_logs']()
            except OSError as exc:
                log.error('Fallback: ошибка очистки логов: %s', exc)

    def open_data(_icon: pystray.Icon) -> None:
        log.info('Fallback: открытие папки данных')
        try:
            data_dir = get_data_dir()
        except OSError as exc:
            log.error('Fallback: get_data_dir() ошибка: %s', exc)
            return
        safe_open_folder(data_dir, 'данные', log)

    def clear_data(_icon: pystray.Icon) -> None:
        log.info('Fallback: очистка всех данных')
        if callbacks.get('clear_data'):
            try:
                callbacks['clear_data']()
            except OSError as exc:
                log.error('Fallback: ошибка очистки данных: %s', exc)

    def toggle_autostart(icon: pystray.Icon) -> None:
        autostart_enabled[0] = not autostart_enabled[0]
        log.info(
            'Fallback: автозапуск браузера → %s',
            'включён' if autostart_enabled[0] else 'выключен',
        )
        if callbacks.get('autostart_setter'):
            try:
                callbacks['autostart_setter'](autostart_enabled[0])
            except (OSError, TypeError) as exc:
                log.error('Fallback: ошибка записи autostart: %s', exc)
        refresh_fn(icon)

    def toggle_system_autostart(icon: pystray.Icon) -> None:
        system_autostart_enabled[0] = not system_autostart_enabled[0]
        log.info(
            'Fallback: запуск с системой → %s',
            'включён' if system_autostart_enabled[0] else 'выключен',
        )
        if callbacks.get('system_autostart_setter'):
            try:
                callbacks['system_autostart_setter'](
                    system_autostart_enabled[0],
                )
            except (OSError, TypeError) as exc:
                log.error(
                    'Fallback: ошибка записи system_autostart: %s',
                    exc,
                )
        refresh_fn(icon)

    def exit_app(_icon: pystray.Icon) -> None:
        log.info('Fallback: выбран Выход')
        if callbacks.get('stop'):
            callbacks['stop']()

    return {
        'open_logs': open_logs,
        'clear_logs': clear_logs,
        'open_data': open_data,
        'clear_data': clear_data,
        'toggle_autostart': toggle_autostart,
        'toggle_system_autostart': toggle_system_autostart,
        'exit': exit_app,
    }


def _build_menu(
    pystray_mod: types.ModuleType,
    actions: Dict[str, Callable[[pystray.Icon], None]],
    autostart_enabled: List[bool],
    system_autostart_enabled: List[bool],
) -> pystray.Menu:
    """Строит pystray Menu с символами ✓/✗ в тексте (без нативных чекбоксов)."""
    mark_as = '\u2713' if autostart_enabled[0] else '\u2717'
    mark_sys = '\u2713' if system_autostart_enabled[0] else '\u2717'
    return pystray_mod.Menu(
        pystray_mod.MenuItem(
            '\U0001f4dc Посмотреть логи', actions['open_logs'],
        ),
        pystray_mod.MenuItem(
            '\U0001f5d1\ufe0f Очистить логи', actions['clear_logs'],
        ),
        pystray_mod.MenuItem(
            '\U0001f4c2 Посмотреть данные', actions['open_data'],
        ),
        pystray_mod.MenuItem(
            '\u26a0\ufe0f Очистить данные', actions['clear_data'],
        ),
        pystray_mod.Menu.SEPARATOR,
        pystray_mod.MenuItem(
            f'{mark_as} Автозапуск браузера',
            actions['toggle_autostart'],
        ),
        pystray_mod.MenuItem(
            f'{mark_sys} Запуск с системой',
            actions['toggle_system_autostart'],
        ),
        pystray_mod.Menu.SEPARATOR,
        pystray_mod.MenuItem(
            '\u274c Выход', actions['exit'],
        ),
    )


def start_pystray_fallback(callbacks: Dict[str, Any]) -> Optional[pystray.Icon]:
    """
    Запускает pystray с нативным меню (без tkinter).

    Args:
        callbacks: Словарь с коллбэками.

    Returns:
        pystray.Icon или None при ошибке.
    """
    try:
        # Ленивый импорт: pystray/Pillow — опциональные зависимости
        import pystray  # type: ignore[reportMissingImports]  # pylint: disable=import-outside-toplevel
        from PIL import Image  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        logger.error('Fallback: pystray/Pillow не установлены: %s', e)
        return None

    log = logger
    autostart_enabled = [
        get_autostart_state(callbacks, 'flowlink.tray.fallback'),
    ]

    # Чтение состояния системного автозапуска
    system_autostart_enabled = [False]
    if callbacks.get('system_autostart_getter'):
        try:
            system_autostart_enabled[0] = (
                callbacks['system_autostart_getter']()
            )
        except (OSError, TypeError, AttributeError) as exc:
            log.error(
                'Fallback: ошибка чтения system_autostart: %s', exc,
            )

    def _refresh_menu(icon: pystray.Icon) -> None:
        """Обновляет меню иконки (для перерисовки чекбоксов)."""
        try:
            icon.menu = _build_menu(
                pystray, actions, autostart_enabled,
                system_autostart_enabled,
            )
            icon.update_menu()
        except (RuntimeError, OSError) as exc:
            log.debug('Fallback: update_menu: %s', exc)

    actions = _make_actions(
        callbacks, autostart_enabled, system_autostart_enabled,
        log, _refresh_menu,
    )

    icon_image = load_icon(
        Image, 'Tray Fallback',
        force_fallback=callbacks.get('test_fallback_icon', False),
    )
    if icon_image is None:
        log.error('Fallback: не удалось загрузить иконку')
        return None

    icon = pystray.Icon(
        'flowlink-proxy', icon_image,
        'FlowLink Proxy', menu=_build_menu(
            pystray, actions, autostart_enabled,
            system_autostart_enabled,
        ),
    )

    thread = threading.Thread(target=icon.run, daemon=True)
    thread.start()
    log.info('Fallback: pystray трей запущен (tkinter отключён)')
    return icon
