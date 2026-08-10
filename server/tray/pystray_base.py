"""
Базовый pystray-бэкенд системного трей.

Общая логика для Linux и macOS: pystray иконка + tkinter popup-меню.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import TYPE_CHECKING, Any, Dict

from server.tray.menu import build_menu_items, load_icon
from server.tray.popup import FlowLinkPopup

if TYPE_CHECKING:
    # type: ignore[reportMissingImports] — pystray опциональная зависимость
    # (не установлен в dev-среде); импорт нужен только для аннотаций типов
    import pystray  # type: ignore[reportMissingImports]


# Слишком много атрибутов: класс хранит состояние иконки и popup-меню,
# разделение нецелесообразно.
class PystrayTray:  # pylint: disable=too-many-instance-attributes
    """
    Базовый класс pystray-бэкенда для Linux и macOS.

    Создаёт иконку через pystray и показывает кастомное tkinter popup-меню
    при клике. Подклассы передают имя логгера и отображаемое имя платформы.

    Args:
        callbacks: Словарь с коллбэками (stop, autostart_getter, и т.д.).
        platform_name: Имя платформы для логов и иконки (например 'Linux').
    """

    def __init__(self, callbacks: Dict[str, Any], platform_name: str) -> None:
        """Инициализация базового трей-бэкенда."""
        self._callbacks = callbacks
        self._platform_name = platform_name
        self._logger = logging.getLogger(f'flowlink.tray.{platform_name.lower()}')
        self._icon = None
        self._popup = FlowLinkPopup()
        self._tk_root = None
        self._tk_thread = None
        # Защита от дублей popup (аналог _popup_open в win32.py)
        self._popup_open = False

    @property
    def tk_root(self):
        """Возвращает корневой Tk трея (или None)."""
        return self._tk_root

    @property
    def popup(self):
        """Возвращает popup-меню трея (или None)."""
        return self._popup

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
            # Ленивый импорт: pystray/Pillow — опциональные зависимости;
            # модуль не установлен в dev-среде (см. TYPE_CHECKING выше)
            # pylint: disable=import-outside-toplevel — ленивый импорт
            import pystray  # type: ignore[reportMissingImports]
            from PIL import Image  # pylint: disable=import-outside-toplevel  # ленивый импорт: Pillow — опциональная зависимость
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

            # pystray.Icon — значение (backend().Icon), а не класс-тип:
            # pyright не принимает его в аннотациях (reportInvalidTypeForm),
            # поэтому параметры типизируются как Any.
            def on_click(icon: Any, item: Any) -> None:
                """Обработчик клика по пункту меню."""
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
        """Показывает popup-меню при позиции курсора.

        Защищён от дублей и исключений: повторный клик по иконке
        не создаст второй popup, а ошибка рендера не уронит
        обработчик клика pystray (аналог _safe_show_popup в win32).
        Перед построением меню передаёт tk_root в callbacks —
        иначе «Выбрать браузер...» молча выходит (см. menu.py).
        """
        if not self._tk_root:
            return
        if self._popup_open:
            self._logger.debug(
                'Tray %s: popup уже показывается — пропуск',
                self._platform_name,
            )
            return

        self._popup_open = True
        try:
            # Передаём tk_root и popup в callbacks для диалогов выбора
            # браузера и индикатора загрузки в статусбаре
            # (аналог win32.py: callbacks['tk_root'] = self._tk_root).
            self._callbacks['tk_root'] = self._tk_root
            self._callbacks['popup'] = self._popup
            items = build_menu_items(
                self._callbacks, self.stop,
                f'Tray {self._platform_name}',
            )
            self._popup.show(items=items)
        except (tk.TclError, KeyError, TypeError, ValueError,
                OSError, RuntimeError) as e:
            self._logger.error(
                'Tray %s: ошибка показа popup: %s',
                self._platform_name, e, exc_info=True,
            )
        finally:
            self._popup_open = False
