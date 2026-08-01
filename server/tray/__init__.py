"""
Кастомный системный трей FlowLink Proxy.

Предоставляет иконку в системном трее с кастомным стилизованным popup-меню
в тёмной теме (в стиле расширения).

Архитектура:
- Windows: ctypes-бэкенд (Win32 API) + tkinter popup
- Linux: pystray-бэкенд + tkinter popup
- macOS: pystray-бэкенд + tkinter popup
- Fallback: pystray + нативное меню (когда tkinter недоступен или --no-tkinter)

Цепочка fallback для Windows:
1. Win32 ctypes + tkinter popup (полный функционал)
2. pystray + tkinter popup (если Win32 не удался)
3. pystray + нативное меню (если tkinter недоступен)

Threading:
- tkinter mainloop запускается в фоновом daemon-потоке
  (обязательно для tkinter — он не thread-safe)
- asyncio event loop работает в главном потоке (серверы)
- Связь: queue.Queue + root.after() polling
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, Optional

from server.tray.platform import has_tkinter, is_linux, is_macos, is_windows

logger = logging.getLogger('flowlink.tray')


def start_tray(callbacks: Dict[str, Any], no_tkinter: bool = False) -> Optional[Any]:
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
        return _start_win32_tray_with_fallback(callbacks)
    if is_linux():
        return _start_linux_tray(callbacks)
    if is_macos():
        return _start_macos_tray(callbacks)
    logger.warning('Неподдерживаемая платформа: %s', sys.platform)
    return None


def _start_win32_tray_with_fallback(callbacks: Dict[str, Any]) -> Optional[Any]:
    """
    Запуск Win32 трей с цепочкой fallback.

    Порядок:
    1. Win32 ctypes + tkinter popup
    2. pystray + tkinter popup
    3. pystray + нативное меню

    Импорт модуля ловит ImportError (модуль не собран).
    Запуск ловит OSError/RuntimeError (Win32 API).
    Проверка hwnd ловит случай, когда поток трей упал.
    """
    tray = _start_win32_tray(callbacks)
    if tray:
        return tray

    logger.info(
        'Win32 трей недоступен, попытка pystray + tkinter...',
    )
    tray = _start_pystray_with_tkinter(callbacks)
    if tray:
        return tray

    logger.info(
        'pystray + tkinter недоступен, fallback на '
        'pystray + нативное меню...',
    )
    tray = _start_pystray_fallback(callbacks)
    if tray:
        return tray

    logger.critical(
        'Все трей-бэкенды недоступны (Win32, pystray+tkinter, '
        'pystray+native). Системный трей не будет отображён.',
    )
    return None


def _start_pystray_with_tkinter(callbacks: Dict[str, Any]) -> Optional[Any]:
    """Запуск pystray с нативным меню (если tkinter есть)."""
    try:
        # Ленивый импорт: модуль fallback подключается только при
        # необходимости (pystray может быть не установлен)
        from server.tray.fallback import \
            start_pystray_fallback  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        logger.error(
            'pystray+tkinter: модуль fallback.py не найден: %s', e,
        )
        return None

    try:
        return start_pystray_fallback(callbacks)
    except (ImportError, OSError) as e:
        logger.error(
            'pystray+tkinter: ошибка запуска: %s', e,
        )
        return None
    except RuntimeError as e:
        logger.error(
            'pystray+tkinter: runtime ошибка: %s', e,
        )
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: логируем и не роняем трей
        logger.error(
            'pystray+tkinter: непредвиденная ошибка: %s', e,
            exc_info=True,
        )
        return None


def _init_win32_tray(callbacks: Dict[str, Any]) -> Optional[Any]:
    """
    Импорт, создание, запуск и ожидание Win32Tray.

    Ловит:
    - ImportError: модуль win32.py не найден
    - OSError/RuntimeError: системные ошибки
    - ValueError/TypeError: некорректные аргументы
    - AttributeError: отсутствует _icon_ready
    """
    try:
        # Ленивый импорт: платформо-зависимый бэкенд
        from server.tray.win32 import \
            Win32Tray  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        logger.error('Win32: модуль win32.py не найден: %s', e)
        return None

    try:
        tray = Win32Tray(callbacks)
        tray.start()
    except (TypeError, ValueError, OSError, RuntimeError) as e:
        logger.error(
            'Win32: ошибка создания/запуска: %s', e,
        )
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: логируем и не роняем трей
        logger.error(
            'Win32: непредвиденная ошибка при создании '
            'или запуске: %s', e, exc_info=True,
        )
        return None

    # Ждём до 2 секунд пока поток создаст иконку
    # Внутренний атрибут Win32Tray (публичного API нет) — событие
    # инициализации иконки в фоновом потоке.
    try:
        ready = tray._icon_ready.wait(timeout=2.0)  # pylint: disable=protected-access
    except AttributeError as e:
        logger.error(
            'Win32: tray не имеет _icon_ready: %s', e,
        )
        return None

    if not ready:
        logger.warning(
            'Win32: поток трей не завершил '
            'инициализацию за 2 сек',
        )
        return None

    return tray


def _start_win32_tray(callbacks: Dict[str, Any]) -> Optional[Any]:
    """
    Запуск трей через Win32 ctypes на Windows.

    Использует _init_win32_tray для импорта, создания и запуска.
    Затем проверяет hwnd.
    """
    tray = _init_win32_tray(callbacks)
    if tray is None:
        return None

    try:
        # Внутренний атрибут Win32Tray — публичного API для HWND нет.
        if tray._hwnd:  # pylint: disable=protected-access
            return tray
    except AttributeError as e:
        logger.error(
            'Win32: tray не имеет _hwnd: %s', e,
        )

    logger.warning(
        'Win32: hwnd не установлен, fallback на pystray',
    )
    return None


def _start_linux_tray(callbacks: Dict[str, Any]) -> Optional[Any]:
    """Запуск трей через pystray на Linux."""
    try:
        # Ленивый импорт: платформо-зависимый бэкенд
        from server.tray.linux import \
            LinuxTray  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        logger.error(
            'Linux: модуль linux.py не найден или '
            'pystray/Pillow не установлены: %s', e,
        )
        return None

    try:
        tray = LinuxTray(callbacks)
        tray.start()
        return tray
    except (ImportError, OSError) as e:
        logger.error('Ошибка запуска Linux трея: %s', e)
        return None
    except RuntimeError as e:
        logger.error(
            'Linux: runtime ошибка запуска трея: %s', e,
        )
        return None
    except (TypeError, ValueError) as e:
        logger.error(
            'Linux: некорректные аргументы трея: %s', e,
        )
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: логируем и не роняем трей
        logger.error(
            'Linux: непредвиденная ошибка трея: %s', e,
            exc_info=True,
        )
        return None


def _start_macos_tray(callbacks: Dict[str, Any]) -> Optional[Any]:
    """Запуск трей через pystray на macOS."""
    try:
        # Ленивый импорт: платформо-зависимый бэкенд
        from server.tray.macos import \
            MacosTray  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        logger.error(
            'macOS: модуль macos.py не найден или '
            'pystray/Pillow не установлены: %s', e,
        )
        return None

    try:
        tray = MacosTray(callbacks)
        tray.start()
        return tray
    except (ImportError, OSError) as e:
        logger.error('Ошибка запуска macOS трея: %s', e)
        return None
    except RuntimeError as e:
        logger.error(
            'macOS: runtime ошибка запуска трея: %s', e,
        )
        return None
    except (TypeError, ValueError) as e:
        logger.error(
            'macOS: некорректные аргументы трея: %s', e,
        )
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: логируем и не роняем трей
        logger.error(
            'macOS: непредвиденная ошибка трея: %s', e,
            exc_info=True,
        )
        return None


def _start_pystray_fallback(callbacks: Dict[str, Any]) -> Optional[Any]:
    """Запуск pystray с нативным меню (без tkinter)."""
    try:
        # Ленивый импорт: pystray может быть не установлен
        from server.tray.fallback import \
            start_pystray_fallback  # pylint: disable=import-outside-toplevel
    except ImportError as e:
        logger.error('Fallback: модуль fallback.py не найден: %s', e)
        return None

    try:
        return start_pystray_fallback(callbacks)
    except ImportError as e:
        logger.error(
            'Fallback: pystray/Pillow не установлены: %s', e,
        )
        return None
    except OSError as e:
        logger.error('Ошибка запуска fallback трея: %s', e)
        return None
    except RuntimeError as e:
        logger.error(
            'Fallback: runtime ошибка запуска трея: %s', e,
        )
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: логируем и не роняем трей
        logger.error(
            'Fallback: непредвиденная ошибка трея: %s', e,
            exc_info=True,
        )
        return None
