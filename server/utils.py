"""
Общие утилиты FlowLink Proxy.

Единственная ответственность: вспомогательные функции общего назначения.
"""

import os
import sys


def get_data_dir() -> str:
    """
    Возвращает базовую директорию для хранения данных приложения.

    В режиме PyInstaller (.frozen) — рядом с исполняемым файлом.
    Иначе — текущая рабочая директория.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.getcwd()


def get_resource_dir() -> str:
    """
    Возвращает директорию ресурсов (иконки, и т.д.).

    В режиме PyInstaller (.frozen) — sys._MEIPASS (временная папка с распакованными ресурсами).
    Иначе — текущая рабочая директория.
    """
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(sys.executable))
    return os.getcwd()
