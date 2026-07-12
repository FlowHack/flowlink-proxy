"""
Кастомный системный трей FlowLink Proxy.

Предоставляет иконку в системном трее с кастомным стилизованным popup-меню
в тёмной теме (в стиле расширения).

Архитектура:
- Windows: ctypes-бэкенд (Win32 API) + tkinter popup
- Linux: pystray-бэкенд + tkinter popup
- macOS: pystray-бэкенд + tkinter popup
- Fallback: pystray + нативное меню (когда tkinter недоступен или --no-tkinter)

Threading:
- tkinter mainloop запускается в фоновом daemon-потоке
  (обязательно для tkinter — он не thread-safe)
- asyncio event loop работает в главном потоке (серверы)
- Связь: queue.Queue + root.after() polling
"""

import logging
import sys

from server.tray.platform import (
    is_windows,
    is_linux,
    is_macos,
    has_tkinter,
)

logger = logging.getLogger('flowlink.tray')


def start_tray(callbacks, no_tkinter=False):
    """
    Запускает системный трей с кастомным popup-меню.

    Функция определяет платформу и выбирает подходящий бэкенд:
    - Windows: Win32 ctypes-бэкенд (полный контроль над иконкой)
    - Linux/macOS: pystray-бэкенд (стандартная иконка)

    Popup-меню рендерится через tkinter на всех платформах
    для единообразного вида. Если tkinter недоступен или
    передан флаг no_tkinter, используется pystray с нативным
    меню (пункты с ✓/✗ символами).

    Args:
        callbacks: Словарь с коллбэками:
            stop: Вызывается при выборе «Выход» в меню.
            autostart_getter: Callable → bool.
            autostart_setter: Callable(bool).
            log_dir_getter: Callable → str.
            data_dir_getter: Callable → str.
            clear_logs: Callable. Очищает только логи.
            clear_data: Callable. Очищает все данные.
        no_tkinter: Если True, принудительно использует pystray
            fallback (нужно для отладки без tkinter).

    Returns:
        Объект трей-иконки (platform-dependent) или None при ошибке.
    """
    if no_tkinter or not has_tkinter():
        reason = '--no-tkinter' if no_tkinter else 'tkinter недоступен'
        logger.info(
            'Fallback на pystray (%s) — нативное меню', reason,
        )
        return _start_pystray_fallback(callbacks)

    if is_windows():
        return _start_win32_tray(callbacks)
    if is_linux():
        return _start_linux_tray(callbacks)
    if is_macos():
        return _start_macos_tray(callbacks)
    logger.warning('Неподдерживаемая платформа: %s', sys.platform)
    return None


def _start_win32_tray(callbacks):
    """Запуск трей через Win32 ctypes на Windows."""
    try:
        from server.tray.win32 import Win32Tray
    except ImportError:
        logger.error('Win32: модуль win32.py не найден')
        return None

    try:
        tray = Win32Tray(callbacks)
        tray.start()
        return tray
    except (OSError, RuntimeError) as e:
        logger.error('Ошибка запуска Win32 трея: %s', e)
        return None


def _start_linux_tray(callbacks):
    """Запуск трей через pystray на Linux."""
    try:
        from server.tray.linux import LinuxTray
    except ImportError:
        logger.error(
            'Linux: модуль linux.py не найден или '
            'pystray/Pillow не установлены',
        )
        return None

    try:
        tray = LinuxTray(callbacks)
        tray.start()
        return tray
    except (ImportError, OSError, RuntimeError) as e:
        logger.error('Ошибка запуска Linux трея: %s', e)
        return None


def _start_macos_tray(callbacks):
    """Запуск трей через pystray на macOS."""
    try:
        from server.tray.macos import MacosTray
    except ImportError:
        logger.error(
            'macOS: модуль macos.py не найден или '
            'pystray/Pillow не установлены',
        )
        return None

    try:
        tray = MacosTray(callbacks)
        tray.start()
        return tray
    except (ImportError, OSError, RuntimeError) as e:
        logger.error('Ошибка запуска macOS трея: %s', e)
        return None


def _start_pystray_fallback(callbacks):
    """Запуск pystray с нативным меню (без tkinter)."""
    try:
        from server.tray.fallback import start_pystray_fallback
    except ImportError as e:
        logger.error('Fallback: модуль fallback.py не найден: %s', e)
        return None

    try:
        return start_pystray_fallback(callbacks)
    except (ImportError, OSError, RuntimeError) as e:
        logger.error('Ошибка запуска fallback трея: %s', e)
        return None
