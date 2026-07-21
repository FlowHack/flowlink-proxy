"""
Кастомное popup-меню системного трей на tkinter.

Единственная ответственность: рендеринг тёмного контекстного меню
в стиле расширения FlowLink Proxy.

Особенности:
- Тёмная тема (цвета совпадают с popup расширения)
- Пункты с иконками (Unicode-символы)
- Чекбоксы с динамическим состоянием
- Разделители
- Hover-эффекты
- Автозакрытие при потере фокуса
- Позиционирование относительно иконки трей
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import logging
import threading
import tkinter as tk
from queue import Queue, Empty

logger = logging.getLogger('flowlink.tray.popup')


class PopupColors:  # pylint: disable=too-few-public-methods
    """Цвета popup-меню (совпадают с popup.css расширения)."""
    BG = '#0d0d1a'
    SURFACE = '#1a1a2e'
    SURFACE_HOVER = '#222244'
    BORDER = '#2a2a4a'
    TEXT = '#e0e0e0'
    TEXT_SECONDARY = '#999999'
    TEXT_MUTED = '#666666'
    ACCENT = '#e74c3c'
    ACCENT_HOVER = '#c0392b'
    GREEN = '#2ecc71'


class FlowLinkPopup:
    """
    Кастомное popup-меню для системного трей.

    Создаёт borderless tkinter-окно с тёмной темой.
    Поддерживает пункты меню, чекбоксы, разделители.

    Использование:
        popup = FlowLinkPopup()
        popup.show(x=100, y=200, items=[...])
    """

    def __init__(self) -> None:
        self._root = None
        self._popup = None
        self._queue = Queue()
        self._build_lock = threading.Lock()
        self._polling_active = False

    def set_tk_root(self, root: tk.Tk) -> None:
        """
        Устанавливает корневой Tk (для интеграции с внешним mainloop).

        Args:
            root: Экземпляр tk.Tk().
        """
        self._root = root

    def _safe_destroy(self) -> None:
        """Безопасно уничтожает popup-окно (вызывается при ошибке)."""
        if self._popup:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None

    def get_popup_hwnd(self) -> int:
        """Возвращает HWND popup-окна для Win32 API."""
        if self._popup and self._popup.winfo_exists():
            return self._popup.winfo_id()
        return 0

    def thread_safe(self, func: Callable[[], None]) -> None:
        """
        Безопасно выполняет функцию в потоке tkinter.

        Args:
            func: Callable без аргументов.
        """
        self._queue.put(func)
        if self._root and not self._polling_active:
            self._polling_active = True
            self._root.after(50, self._poll_queue)

    def _poll_queue(self) -> None:
        """Очищает очередь сообщений и выполняет функции."""
        try:
            while True:
                func = self._queue.get_nowait()
                try:
                    func()
                except tk.TclError as e:
                    logger.debug(
                        'Popup: ошибка tkinter в callback: %s', e,
                    )
                except (OSError, RuntimeError, ValueError) as e:
                    logger.error(
                        'Popup: ошибка в callback из очереди: %s',
                        e, exc_info=True,
                    )
        except Empty:
            pass
        if self._root and self._polling_active:
            try:
                self._root.after(100, self._poll_queue)
            except tk.TclError:
                logger.debug(
                    'Popup: не удалось запланировать _poll_queue',
                )

    def show(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        items: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Показывает popup-меню в указанной позиции.

        Args:
            x: Координата X (экранная). Если None — центр по горизонтали.
            y: Координата Y (экранная). Если None — над курсором.
            items: Список элементов меню (см. _build_items).
        """
        self._show_popup_impl(x, y, items)

    def _show_popup_impl(
        self,
        x: Optional[int],
        y: Optional[int],
        items: Optional[List[Dict[str, Any]]],
    ) -> None:
        """Внутренняя логика показа popup-меню."""
        logger.debug(
            'Popup: show() вход x=%s y=%s items=%s',
            x, y, len(items) if items else 0,
        )
        try:
            logger.debug('Popup: show() — ожидание _build_lock')
            with self._build_lock:
                logger.debug('Popup: show() — _build_lock получен')
                self.dismiss()
                logger.debug('Popup: show() — dismiss() завершён')
                self._create_popup(x, y, items or [])
                logger.debug('Popup: show() _create_popup завершён')
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter при показе: %s', e,
            )
        except (TypeError, ValueError) as e:
            logger.error(
                'Popup: некорректные аргументы: %s', e,
            )
        except (OSError, RuntimeError) as e:
            logger.error(
                'Popup: непредвиденная ошибка при показе: %s',
                e, exc_info=True,
            )

    def dismiss(self) -> None:
        """Закрывает popup-меню, если оно открыто."""
        logger.debug('Popup: dismiss() вход')
        self._polling_active = False
        try:
            if self._popup is not None:
                try:
                    if self._popup.winfo_exists():
                        try:
                            self._popup.grab_release()
                        except tk.TclError as e:
                            logger.debug('Popup: dismiss() — TclError при grab_release: %s', e)
                except tk.TclError:
                    logger.debug('Popup: dismiss() — окно уже уничтожено, пропускаю grab_release')
                try:
                    if self._popup.winfo_exists():
                        self._popup.destroy()
                except tk.TclError:
                    logger.debug('Popup: dismiss() — окно уже уничтожено, пропускаю destroy')
        except (OSError, RuntimeError, ValueError) as e:
            logger.error('Popup: dismiss() — критическая ошибка: %s', e, exc_info=True)
        finally:
            self._popup = None
            logger.debug('Popup: dismiss() выход, _popup=None')

    def _create_popup(
        self,
        x: Optional[int],
        y: Optional[int],
        items: List[Dict[str, Any]],
    ) -> None:
        """Создаёт и отображает popup-окно."""
        logger.debug(
            'Popup: _create_popup() вход x=%s y=%s items=%s',
            x, y, len(items),
        )
        if not self._root:
            logger.error(
                'Tk root не установлен — popup невозможен',
            )
            return

        try:
            self._popup = tk.Toplevel(self._root)
        except tk.TclError as e:
            logger.error(
                'Popup: не удалось создать Toplevel: %s', e,
            )
            return
        except RuntimeError as e:
            logger.error(
                'Popup: runtime ошибка при создании '
                'Toplevel: %s', e,
            )
            return

        logger.debug('Popup: _create_popup() Toplevel создан')

        try:
            self._popup.overrideredirect(True)
            self._popup.attributes('-topmost', True)
            self._popup.configure(bg=PopupColors.BG)
            self._popup.focus_force()
            self._popup.grab_set()
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка настройки окна: %s', e,
            )
            self._safe_destroy()
            return

        self._configure_popup(x, y, items)

    def _configure_popup(
        self,
        x: Optional[int],
        y: Optional[int],
        items: List[Dict[str, Any]],
    ) -> None:
        """Позиционирует окно, строит содержимое, запускает анимацию."""
        if not self._popup or not self._root:
            return

        # Ширина popup
        width = 220
        # Высота вычисляется динамически
        height = self.calc_height(items)

        # Позиционирование
        if x is None:
            x = (
                self._root.winfo_pointerx()
                - width // 2
            )
        if y is None:
            y = (
                self._root.winfo_pointery()
                - height - 8
            )

        # Не выходит за экран
        try:
            sw = self._popup.winfo_screenwidth()
            sh = self._popup.winfo_screenheight()
        except tk.TclError as e:
            logger.warning(
                'Popup: не удалось получить размер '
                'экрана: %s', e,
            )
            sw, sh = 1920, 1080
        x = max(0, min(x, sw - width - 4))
        y = max(0, min(y, sh - height - 4))

        try:
            self._popup.geometry(
                f'{width}x{height}+{x}+{y}',
            )
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка установки geometry: %s', e,
            )
            self._safe_destroy()
            return

        logger.debug(
            'Popup: _configure_popup() geometry '
            '%sx%s+%s+%s',
            width, height, x, y,
        )

        # Строим содержимое
        try:
            self._build_items(items)
        except (TypeError, ValueError) as e:
            logger.error(
                'Popup: ошибка построения элементов: %s',
                e,
            )
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter при построении: '
                '%s', e,
            )

        logger.debug(
            'Popup: _configure_popup() '
            '_build_items завершён',
        )

        # Автозакрытие при потере фокуса
        try:
            def _bind_focus_out() -> None:
                if (
                    self._popup
                    and self._popup.winfo_exists()
                ):
                    self._popup.bind(
                        '<FocusOut>',
                        lambda _e: self.dismiss(),
                    )

            self._popup.after(100, _bind_focus_out)
        except tk.TclError as e:
            logger.warning(
                'Popup: не удалось установить '
                'grab: %s', e,
            )

        logger.debug(
            'Popup: _configure_popup() '
            'grab_set выполнен',
        )

        # Плавное появление
        self._fade_in()

    @staticmethod
    def calc_height(items: List[Dict[str, Any]]) -> int:
        """Вычисляет высоту popup на основе количества элементов."""
        item_height = 32  # высота одного пункта
        separator_height = 10  # высота разделителя
        padding = 8  # верхний + нижний padding

        height = padding
        for item in items:
            if item.get('type') == 'separator':
                height += separator_height
            else:
                height += item_height
        height += padding
        return max(height, 40)

    def _build_items(self, items: List[Dict[str, Any]]) -> None:
        """Строит элементы меню."""
        if not self._popup:
            return

        try:
            # Верхний padding
            tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, height=4,
            ).pack(fill='x')

            for item in items:
                item_type = item.get('type', 'item')

                if item_type == 'separator':
                    self._add_separator()
                elif item_type == 'item':
                    self._add_menu_item(
                        text=item.get('text', ''),
                        icon=item.get('icon', ''),
                        command=item.get('command'),
                        color=item.get('color'),
                    )
                elif item_type == 'check':
                    self._add_check_item(
                        text=item.get('text', ''),
                        icon=item.get('icon', ''),
                        checked=item.get('checked', False),
                        command=item.get('command'),
                    )
                elif item_type == 'header':
                    self._add_header(item.get('text', ''))

            # Нижний padding
            tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, height=4,
            ).pack(fill='x')
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter при построении: %s', e,
            )
        except (TypeError, ValueError, KeyError) as e:
            logger.error(
                'Popup: ошибка данных при построении: %s', e,
            )

    def _add_header(self, text: str) -> None:
        """Добавляет заголовок в меню."""
        lbl = tk.Label(
            self._popup,
            text=text,
            bg=PopupColors.BG,
            fg=PopupColors.ACCENT,
            font=('Segoe UI', 11, 'bold'),
            anchor='w',
            padx=12,
            pady=(4, 2),  # type: ignore[reportArgumentType]
        )
        lbl.pack(fill='x')

    def _add_menu_item(
        self,
        text: str,
        icon: str = '',
        command: Optional[Callable[[], None]] = None,
        color: Optional[str] = None,
    ) -> None:
        """Добавляет пункт меню."""
        try:
            frame = tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, cursor='hand2',
            )
            frame.pack(fill='x', padx=4, pady=(0, 6))

            # Иконка
            if icon:
                icon_lbl = tk.Label(
                    frame,
                    text=icon,
                    bg=PopupColors.BG,
                    fg=color or PopupColors.ACCENT,
                    font=('Segoe UI', 12),
                    width=2,
                    anchor='center',
                )
                icon_lbl.pack(side='left', padx=(4, 4))

            # Текст
            fg = color or PopupColors.TEXT
            text_lbl = tk.Label(
                frame,
                text=text,
                bg=PopupColors.BG,
                fg=fg,
                font=('Segoe UI', 10),
                anchor='w',
            )
            text_lbl.pack(side='left', fill='x', expand=True, padx=4, pady=6)

            # Hover + клик
            def on_enter(
                _event: tk.Event[tk.Tk],
                fr: tk.Frame = frame,
            ) -> None:
                for child in fr.winfo_children():
                    child.configure(
                        bg=PopupColors.SURFACE_HOVER,  # type: ignore[reportCallIssue]
                    )
                fr.configure(
                    bg=PopupColors.SURFACE_HOVER,  # type: ignore[reportCallIssue]
                )

            def on_leave(
                _event: tk.Event[tk.Tk],
                fr: tk.Frame = frame,
            ) -> None:
                for child in fr.winfo_children():
                    child.configure(
                        bg=PopupColors.BG,  # type: ignore[reportCallIssue]
                    )
                fr.configure(bg=PopupColors.BG)

            def on_click(
                _event: tk.Event[tk.Tk],
                cmd: Optional[Callable[[], None]] = command,
            ) -> None:
                logger.info('Popup: клик по пункту меню')
                if cmd:
                    try:
                        cmd()
                    except (OSError, ValueError, RuntimeError) as e:
                        logger.error(
                            'Popup: ошибка при выполнении '
                            'команды: %s',
                            e, exc_info=True,
                        )
                self.dismiss()

            for widget in [frame] + frame.winfo_children():
                widget.bind('<Enter>', on_enter)  # type: ignore[reportArgumentType]
                widget.bind('<Leave>', on_leave)  # type: ignore[reportArgumentType]
                widget.bind('<Button-1>', on_click)  # type: ignore[reportArgumentType]
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter в _add_menu_item: %s', e,
            )
        except (TypeError, ValueError) as e:
            logger.error(
                'Popup: ошибка данных в _add_menu_item: %s', e,
            )

    def _add_check_item(
        self,
        text: str,
        icon: str = '',
        checked: bool = False,
        command: Optional[Callable[[], None]] = None,
    ) -> None:
        """Добавляет пункт с чекбоксом."""
        try:
            frame = tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, cursor='hand2',
            )
            frame.pack(fill='x', padx=4, pady=(0, 6))

            # Иконка
            if icon:
                icon_lbl = tk.Label(
                    frame,
                    text=icon,
                    bg=PopupColors.BG,
                    fg=PopupColors.ACCENT,
                    font=('Segoe UI', 12),
                    width=2,
                    anchor='center',
                )
                icon_lbl.pack(side='left', padx=(4, 4))

            # Текст
            text_lbl = tk.Label(
                frame,
                text=text,
                bg=PopupColors.BG,
                fg=PopupColors.TEXT,
                font=('Segoe UI', 10),
                anchor='w',
            )
            text_lbl.pack(side='left', fill='x', expand=True, padx=4, pady=6)

            # Чекбокс
            mark = '\u2713' if checked else ''
            check_lbl = tk.Label(
                frame,
                text=mark,
                bg=PopupColors.BG,
                fg=PopupColors.GREEN if checked else PopupColors.BG,
                font=('Segoe UI', 12, 'bold'),
                width=2,
                anchor='center',
            )
            check_lbl.pack(side='right', padx=(0, 8))

            # Hover + клик
            def on_enter(
                _event: tk.Event[tk.Tk],
                fr: tk.Frame = frame,
            ) -> None:
                for child in fr.winfo_children():
                    child.configure(
                        bg=PopupColors.SURFACE_HOVER,  # type: ignore[reportCallIssue]
                    )
                fr.configure(
                    bg=PopupColors.SURFACE_HOVER,  # type: ignore[reportCallIssue]
                )

            def on_leave(
                _event: tk.Event[tk.Tk],
                fr: tk.Frame = frame,
            ) -> None:
                for child in fr.winfo_children():
                    child.configure(
                        bg=PopupColors.BG,  # type: ignore[reportCallIssue]
                    )
                fr.configure(bg=PopupColors.BG)

            def on_click(
                _event: tk.Event[tk.Tk],
                cmd: Optional[Callable[[], None]] = command,
            ) -> None:
                logger.info('Popup: клик по пункту с чекбоксом')
                if cmd:
                    try:
                        cmd()
                    except (OSError, ValueError, RuntimeError) as e:
                        logger.error(
                            'Popup: ошибка при выполнении '
                            'команды: %s',
                            e, exc_info=True,
                        )
                self.dismiss()

            for widget in [frame] + frame.winfo_children():
                widget.bind('<Enter>', on_enter)  # type: ignore[reportArgumentType]
                widget.bind('<Leave>', on_leave)  # type: ignore[reportArgumentType]
                widget.bind('<Button-1>', on_click)  # type: ignore[reportArgumentType]
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter в _add_check_item: %s', e,
            )
        except (TypeError, ValueError) as e:
            logger.error(
                'Popup: ошибка данных в _add_check_item: %s', e,
            )

    def _add_separator(self) -> None:
        """Добавляет разделитель."""
        try:
            frame = tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, height=10,
            )
            frame.pack(fill='x')
            frame.pack_propagate(False)
            tk.Frame(frame, bg=PopupColors.BORDER, height=1).pack(  # type: ignore[reportCallIssue]
                fill='x', padx=8, pady=4,
            )
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter в _add_separator: %s', e,
            )

    def _fade_in(self, alpha: float = 0.0) -> None:
        """
        Плавное появление (fadeIn).

        Рекурсивно увеличивает прозрачность окна от 0.0 до 1.0
        с шагом 0.1 и интервалом 15мс. Если окно было закрыто
        во время анимации — корректно завершается (TclError).
        """
        logger.debug('Popup: _fade_in() alpha=%s', alpha)
        if not self._popup:
            return
        try:
            if alpha <= 1.0:
                self._popup.attributes('-alpha', alpha)
                self._popup.after(
                    15, lambda: self._fade_in(alpha + 0.1),
                )
            else:
                self._popup.attributes('-alpha', 1.0)
        except tk.TclError:
            logger.debug(
                '_fade_in: окно закрылось во время анимации '
                '(alpha=%.1f)', alpha,
            )
        except RuntimeError as e:
            logger.debug(
                '_fade_in: runtime ошибка (alpha=%.1f): %s',
                alpha, e,
            )
