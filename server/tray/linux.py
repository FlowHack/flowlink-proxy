"""
Linux бэкенд системного трей через pystray.

Единственная ответственность: иконка в трее через pystray
с кастомным tkinter popup-меню при клике.

Используется ТОЛЬКО на Linux. На других платформах не импортируется.
"""

from server.tray.pystray_base import PystrayTray


class LinuxTray(PystrayTray):
    """Linux-бэкенд системного трей для FlowLink Proxy."""

    def __init__(self, callbacks):
        super().__init__(callbacks, platform_name='Linux')
