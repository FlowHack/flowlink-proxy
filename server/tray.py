"""
System tray icon для Windows-сборки (.exe).

Единственная ответственность: иконка в системном трее с контекстным меню.
Работает только в PyInstaller-сборке (sys.frozen), пропускается при dev-запуске.
"""

import logging
import os
import threading
import webbrowser

from server.utils import get_data_dir, get_resource_dir

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

# Иконка лежит в папке icons/icon.png
_ICON_PATH = 'icons/icon.png'


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

    menu = (
        item('Посмотреть лог', on_open_logs),
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
