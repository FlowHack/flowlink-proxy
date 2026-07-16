"""
Детекция операционной системы для выбора бэкенда трей-иконки.

Единственная ответственность: определение платформы и доступности компонентов.
"""

from __future__ import annotations

from typing import Any, Dict

import logging
import sys

logger = logging.getLogger('flowlink.tray')


def is_windows() -> bool:
    """Проверяет, запущен ли на Windows."""
    return sys.platform == 'win32'


def is_linux() -> bool:
    """Проверяет, запущен ли на Linux."""
    return sys.platform == 'linux'


def is_macos() -> bool:
    """Проверяет, запущен ли на macOS."""
    return sys.platform == 'darwin'


def has_pystray() -> bool:
    """Проверяет, доступен ли pystray."""
    try:
        # Runtime-проверка: нужен для выбора бэкенда трей.
        import pystray  # pylint: disable=import-outside-toplevel,unused-import
        return True
    except ImportError:
        # pystray не установлен — штатный случай
        return False
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # В headless CI (GitHub Actions) import pystray бросает
        # Xlib.error.DisplayNameError при отсутствии X-дисплея.
        # Ловим display-ошибки Xlib, остальное — пробрасываем.
        try:
            from Xlib.error import DisplayError  # pylint: disable=import-outside-toplevel
            if isinstance(exc, DisplayError):
                logger.debug('pystray: Xlib display-ошибка (headless?): %s', exc)
                return False
        except ImportError:
            pass
        logger.warning('pystray: неожиданная ошибка при импорте: %s', exc)
        return False


def has_pil() -> bool:
    """Проверяет, доступен ли Pillow (нужен для иконки)."""
    try:
        # Runtime-проверка: нужен для иконки трея
        from PIL import Image  # pylint: disable=import-outside-toplevel,unused-import
        return True
    except ImportError:
        return False


def has_tkinter() -> bool:
    """Проверяет, доступен ли tkinter (нужен для popup-меню)."""
    try:
        # Runtime-проверка: нужен для popup-меню
        import tkinter  # pylint: disable=import-outside-toplevel,unused-import
        return True
    except ImportError:
        return False


def get_backend_info() -> Dict[str, Any]:
    """
    Возвращает информацию о доступных бэкендах трей.

    Returns:
        Словарь с флагами доступности каждого компонента.
    """
    return {
        'platform': sys.platform,
        'is_windows': is_windows(),
        'is_linux': is_linux(),
        'is_macos': is_macos(),
        'has_pystray': has_pystray(),
        'has_pil': has_pil(),
        'has_tkinter': has_tkinter(),
    }
