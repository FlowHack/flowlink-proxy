"""
Детекция операционной системы для выбора бэкенда трей-иконки.

Единственная ответственность: определение платформы и доступности компонентов.
"""

import sys


def is_windows():
    """Проверяет, запущен ли на Windows."""
    return sys.platform == 'win32'


def is_linux():
    """Проверяет, запущен ли на Linux."""
    return sys.platform == 'linux'


def is_macos():
    """Проверяет, запущен ли на macOS."""
    return sys.platform == 'darwin'


def has_pystray():
    """Проверяет, доступен ли pystray."""
    try:
        # Runtime-проверка: нужен для выбора бэкенда трей
        import pystray  # pylint: disable=import-outside-toplevel,unused-import
        return True
    except ImportError:
        return False


def has_pil():
    """Проверяет, доступен ли Pillow (нужен для иконки)."""
    try:
        # Runtime-проверка: нужен для иконки трея
        from PIL import Image  # pylint: disable=import-outside-toplevel,unused-import
        return True
    except ImportError:
        return False


def has_tkinter():
    """Проверяет, доступен ли tkinter (нужен для popup-меню)."""
    try:
        # Runtime-проверка: нужен для popup-меню
        import tkinter  # pylint: disable=import-outside-toplevel,unused-import
        return True
    except ImportError:
        return False


def get_backend_info():
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
