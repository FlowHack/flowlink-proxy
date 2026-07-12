"""
macOS бэкенд системного трей через pystray.

Единственная ответственность: иконка в трее через pystray
с кастомным tkinter popup-меню при клике.

Используется ТОЛЬКО на macOS. На других платформах не импортируется.
"""

from server.tray.pystray_base import PystrayTray


class MacosTray(PystrayTray):
    """macOS-бэкенд системного трей для FlowLink Proxy."""

    def __init__(self, callbacks):
        super().__init__(callbacks, platform_name='macOS')
