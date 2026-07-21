"""
Базовый pystray-бэкенд системного трей.

Общая логика для Linux и macOS: pystray иконка + tkinter popup-меню.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Any, Dict, TYPE_CHECKING

from server.tray.popup import FlowLinkPopup
from server.tray.menu import load_icon, build_menu_items

if TYPE_CHECKING:
    import pystray  # type: ignore[reportMissingImports]


class PystrayTray:
    """
    Базовый класс pystray-бэкенда для Linux и macOS.

    Создаёт иконку через pystray и показывает кастомное tkinter popup-меню
    при клике. Подклассы передают имя логгера и отображаемое имя платформы.

    Args:
        callbacks: Словарь с коллбэками (stop, autostart_getter, и т.д.).
        platform_name: Имя платформы для логов и иконки (например 'Linux').
    """

    def __init__(self, callbacks: Dict[str, Any], platform_name: str) -> None:
        self._callbacks = callbacks
        self._platform_name = platform_name
        self._logger = logging.getLogger(f'flowlink.tray.{platform_name.lower()}')
        self._icon = None
        self._popup = FlowLinkPopup()
        self._tk_root = None
        self._tk_thread = None

    def start(self) -> None:
        """Запускает трей в отдельном потоке."""
        self._tk_thread = threading.Thread(
            target=self._run, daemon=True,
        )
        self._tk_thread.start()

    def stop(self) -> None:
        """Останавливает трей."""
        if self._icon:
            try:
                self._icon.stop()
            except RuntimeError as e:
                self._logger.debug(
                    'Tray %s: остановка иконки: %s',
                    self._platform_name, e,
                )

    def refresh_menu(self) -> None:
        """Обновляет popup-меню (вызывается при изменении конфига)."""
        # Popup рендерит свежее состояние при каждом открытии

    def _run(self) -> None:
        """Запускает pystray + tkinter в отдельном потоке."""
        try:
            # Ленивый импорт: pystray/Pillow — опциональные зависимости
            import pystray  # type: ignore[reportMissingImports]  # pylint: disable=import-outside-toplevel
            from PIL import Image  # pylint: disable=import-outside-toplevel
        except ImportError as e:
            self._logger.error(
                'Tray %s: импорт pystray/Pillow не удался: %s',
                self._platform_name, e,
            )
            return

        try:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            self._popup.set_tk_root(self._tk_root)

            threading.Thread(
                target=self._tk_root.mainloop, daemon=True,
            ).start()

            icon_image = load_icon(
                Image, f'Tray {self._platform_name}',
                force_fallback=self._callbacks.get(
                    'test_fallback_icon', False,
                ),
            )
            if icon_image is None:
                self._logger.error(
                    'Tray %s: не удалось загрузить иконку',
                    self._platform_name,
                )
                return

            def on_click(icon: pystray.Icon, item: pystray.MenuItem) -> None:
                del icon, item
                self._show_popup()

            self._icon = pystray.Icon(
                'flowlink-proxy', icon_image,
                'FlowLink Proxy', menu=pystray.Menu(on_click),
            )
            self._icon.run()
        except tk.TclError as e:
            self._logger.error(
                'Tray %s: ошибка tkinter: %s', self._platform_name, e,
            )
        except OSError as e:
            self._logger.error(
                'Tray %s: системная ошибка: %s', self._platform_name, e,
            )
        except RuntimeError as e:
            self._logger.error(
                'Tray %s: ошибка потока: %s', self._platform_name, e,
            )

    def _show_popup(self) -> None:
        """Показывает popup-меню при позиции курсора."""
        if not self._tk_root:
            return
        items = build_menu_items(
            self._callbacks, self.stop, f'Tray {self._platform_name}',
        )
        self._popup.show(items=items)
