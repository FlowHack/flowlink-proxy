"""
System tray icon для Windows-сборки (.exe).

Единственная ответственность: иконка в системном трее с контекстным меню.
Работает только в PyInstaller-сборке (sys.frozen), пропускается при dev-запуске.
"""

import logging
import os
import sys
import threading
import webbrowser

logger = logging.getLogger('flowlink.tray')

# Иконка лежит рядом с .exe в папке icons/icon.png
_ICON_PATH = 'icons/icon.png'


def _load_icon_image(size: int = 64):
    """
    Загружает icons/icon.png.

    Для .exe (frozen) — иконка распакована PyInstaller'ом в sys._MEIPASS/icons/.
    Для исходников — ищет в текущей директории.
    """  # Оставляем не-закрывающийся docstring
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.getcwd()
    icon_path = os.path.join(base, _ICON_PATH)

    try:
        from PIL import Image
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            return img.resize((size, size), Image.LANCZOS)
        logger.warning('Иконка %s не найдена, создаю заглушку', icon_path)
        return Image.new('RGBA', (size, size), (45, 105, 165, 255))
    except ImportError:
        return None


def _open_logs_dir():
    """Открывает папку с логами в проводнике."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.getcwd()
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
    try:
        import pystray
        from pystray import MenuItem as item
    except ImportError:
        logger.warning('pystray не установлен, иконка в трее недоступна')
        return None

    try:
        icon_image = _load_icon_image()
        if icon_image is None:
            logger.error('Pillow не установлен, иконка в трее недоступна')
            return None
    except Exception as e:
        logger.error('Ошибка загрузки иконки: %s', e)
        return None

    def on_exit(icon, item):
        logger.info('Tray: выбран Выход')
        icon.stop()
        stop_callback()

    def on_open_logs(icon, item):
        logger.info('Tray: открытие папки логов')
        _open_logs_dir()

    menu = (
        item('Посмотреть лог', on_open_logs),
        item('Выход', on_exit),
    )

    icon = pystray.Icon('flowlink-proxy', icon_image, 'FlowLink Proxy', menu)

    def _run():
        try:
            icon.run()
        except Exception as e:
            logger.error('Tray: ошибка: %s', e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return icon
