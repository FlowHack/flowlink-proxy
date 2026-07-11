"""
System tray icon для Windows-сборки (.exe).

Единственная ответственность: иконка в системном трее с контекстным меню.
Работает только в PyInstaller-сборке (sys.frozen), пропускается при dev-запуске.
"""

import logging
import os
import threading
import webbrowser

from server.utils import clear_all_data, get_data_dir, get_resource_dir

logger = logging.getLogger('flowlink.tray')

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None

try:
    import pystray
    from pystray import MenuItem as item
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    pystray = None
    item = None

# Tkinter для диалогов подтверждения (опционально)
try:
    import tkinter as _tk
    from tkinter import messagebox as _messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False
    _tk = None
    _messagebox = None

# Иконка лежит в папке icons/icon.png
_ICON_PATH = 'icons/icon.png'


def _show_confirm(title: str, message: str) -> bool:
    """
    Показывает диалог подтверждения (Да/Нет).

    Использует tkinter.messagebox. Если tkinter недоступен — возвращает True
    (разрешаем действие без диалога, чтобы не блокировать пользователя).

    Returns:
        True если пользователь нажал 'Да', False если 'Нет' или ошибка.
    """
    if not HAS_TKINTER:
        logger.warning('tkinter недоступен, пропускаю диалог подтверждения')
        return True
    try:
        root = _tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        result = _messagebox.askyesno(title, message, parent=root)
        root.destroy()
        return bool(result)
    except (_tk.TclError, RuntimeError) as e:
        logger.error('Ошибка диалога подтверждения: %s', e)
        return False


def _show_info(title: str, message: str) -> None:
    """
    Показывает информационное сообщение.

    Использует tkinter.messagebox. Если tkinter недоступен — логирует сообщение.
    """
    if not HAS_TKINTER:
        logger.info('%s: %s', title, message)
        return
    try:
        root = _tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        _messagebox.showinfo(title, message, parent=root)
        root.destroy()
    except (_tk.TclError, RuntimeError) as e:
        logger.error('Ошибка диалога информации: %s', e)


def _load_icon_image(size: int = 64):
    """
    Загружает icons/icon.png.

    Для .exe (frozen) — иконка распакована PyInstaller'ом в sys._MEIPASS/icons/.
    Для исходников — ищет в текущей директории.
    """
    if not HAS_PIL:
        return None
    base = get_resource_dir()
    icon_path = os.path.join(base, _ICON_PATH)

    if os.path.exists(icon_path):
        img = Image.open(icon_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img.resize((size, size), Image.Resampling.LANCZOS)
    logger.warning('Иконка %s не найдена, создаю заглушку', icon_path)
    return Image.new('RGBA', (size, size), (45, 105, 165, 255))


def _open_logs_dir() -> None:
    """Открывает папку с логами в проводнике."""
    base = get_data_dir()
    logs_dir = os.path.join(base, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    webbrowser.open(f'file://{os.path.normpath(logs_dir)}')


def start_tray(stop_callback) -> object | None:
    """
    Запускает иконку в системном трее в отдельном потоке.

    Args:
        stop_callback: вызывается при выборе 'Выход'.

    Returns:
        Экземпляр pystray.Icon или None при ошибке.
    """
    if not HAS_PYSTRAY:
        logger.warning('pystray не установлен, иконка в трее недоступна')
        return None

    icon_image = _load_icon_image()
    if icon_image is None:
        logger.error('Pillow не установлен, иконка в трее недоступна')
        return None

    def on_exit(_icon, _item):
        logger.info('Tray: выбран Выход')
        _icon.stop()
        stop_callback()

    def on_open_logs(_icon, _item):
        logger.info('Tray: открытие папки логов')
        _open_logs_dir()

    def on_clear_data(_icon, _item):
        logger.info('Tray: запрос на очистку всех данных приложения')
        if not _show_confirm(
            'Очистка данных',
            'Все данные FlowLink Proxy будут удалены:\n'
            '• конфигурация прокси и масок\n'
            '• ключи шифрования\n'
            '• настройки автозапуска\n'
            '• логи\n\n'
            'Продолжить?',
        ):
            logger.info('Tray: очистка данных отменена пользователем')
            return
        removed = clear_all_data()
        logger.info('Tray: удалено %d элементов данных', removed)
        _show_info(
            'Очистка завершена',
            f'Удалено элементов данных: {removed}\n\n'
            'Рекомендуется перезапуск сервера\n'
            'для полного сброса состояния.',
        )

    menu = (
        item('Посмотреть лог', on_open_logs),
        item('Очистить все данные', on_clear_data),
        item('Выход', on_exit),
    )

    icon = pystray.Icon('flowlink-proxy', icon_image, 'FlowLink Proxy', menu)

    def _run():
        try:
            icon.run()
        except (OSError, RuntimeError) as e:
            logger.error('Tray: ошибка: %s', e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return icon
