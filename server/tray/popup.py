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

# pylint: disable=too-many-lines
# Файл содержит большой UI-класс FlowLinkPopup (построение меню, тултипы,
# hover-эффекты, анимация, статусбар загрузки). Разбиение на подклассы
# нецелесообразно: все методы тесно связаны общим состоянием
# (self._popup, self._tooltip_label), а порог C0302 (1000 строк) уже
# превышен с учётом нового статусбара загрузки.

from __future__ import annotations

import logging
import threading
import tkinter as tk
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional

from server.ui.theme import ThemeColors as PopupColors

logger = logging.getLogger('flowlink.tray.popup')


class FlowLinkPopup:  # pylint: disable=too-many-instance-attributes  # состояние виджетов и флагов UI
    """
    Кастомное popup-меню для системного трей.

    Создаёт borderless tkinter-окно с тёмной темой.
    Поддерживает пункты меню, чекбоксы, разделители,
    статусбар с инлайн-подсказками (тултипами).

    Использование:
        popup = FlowLinkPopup()
        popup.show(x=100, y=200, items=[...])
    """

    def __init__(self) -> None:
        """Инициализирует кастомное popup-меню.

        Создаёт пустую очередь задач и подготавливает внутреннее
        состояние для отложенного создания tkinter-окна.
        """
        self._root = None
        self._popup = None
        self._queue = Queue()
        self._build_lock = threading.Lock()
        self._polling_active = False
        self._focus_out_after_id: Optional[str] = None
        self._command_running: bool = False
        # Статусбар для тултипов (инлайн-подсказок)
        self._tooltip_label: Optional[tk.Label] = None
        self._tooltip_text = ''

    def set_tk_root(self, root: tk.Tk) -> None:
        """
        Устанавливает корневой Tk (для интеграции с внешним mainloop).

        Args:
            root: Экземпляр tk.Tk().
        """
        self._root = root

    def _is_click_outside_popup(self, x_root: int, y_root: int) -> bool:
        """Проверяет, находится ли точка вне геометрии popup-окна.

        Если popup закрыт, уничтожен или геометрия неизвестна
        (width/height <= 1) — возвращает False (считать клик вне
        меню небезопасно, чтобы не закрывать ничего лишнего).

        Args:
            x_root: Экранная координата X клика.
            y_root: Экранная координата Y клика.

        Returns:
            True, если точка вне прямоугольника popup-окна.
        """
        if not self._popup:
            return False
        try:
            if not self._popup.winfo_exists():
                return False
            width = self._popup.winfo_width()
            height = self._popup.winfo_height()
            # Окно ещё не отрисовано (геометрия неизвестна) — не считаем клик внешним
            if width <= 1 or height <= 1:
                return False
            x0 = self._popup.winfo_rootx()
            y0 = self._popup.winfo_rooty()
            x1 = x0 + width
            y1 = y0 + height
            return not (x0 <= x_root <= x1 and y0 <= y_root <= y1)
        except tk.TclError as e:
            logger.debug(
                'Popup: ошибка при проверке клика вне меню: %s', e,
            )
            return False

    def _on_global_click(self, event: tk.Event[tk.Tk]) -> None:
        """Глобальный обработчик клика, привязанный к popup-окну.

        Обработчик вешается через bind_all на popup-окно: благодаря
        grab_set() клики вне меню направляются в popup-окно, и этот
        обработчик получает их первым. Клики по пунктам меню
        обрабатываются раньше (bind на виджетах), поэтому сюда
        попадают только клики вне геометрии меню.

        Закрывает popup, если клик произошёл вне его геометрии.
        Во время выполнения команды меню клик игнорируется,
        чтобы не закрыть popup раньше времени.

        Args:
            event: Событие tkinter с координатами x_root/y_root.
        """
        if self._command_running:
            return
        if self._is_click_outside_popup(event.x_root, event.y_root):
            logger.debug('Popup: закрыто по клику вне меню')
            self.dismiss()

    def _safe_destroy(self) -> None:
        """Безопасно уничтожает popup-окно (вызывается при ошибке)."""
        if self._popup:
            try:
                self._popup.destroy()
            except tk.TclError as e:
                logger.debug('Popup: _safe_destroy — окно уже уничтожено: %s', e)
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
            logger.debug('Popup: очередь событий пуста — завершение цикла')
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
            with self._build_lock:
                self.dismiss()
                self._create_popup(x, y, items or [])
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
        self._polling_active = False
        # Очищаем статусбар тултипа
        self._hide_tooltip()
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

    def _create_popup(
        self,
        x: Optional[int],
        y: Optional[int],
        items: List[Dict[str, Any]],
    ) -> None:
        """Создаёт и отображает popup-окно."""
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

        # Пытаемся скрыть окно из панели задач через tkinter API
        # (должно сработать на Windows, если tkinter поддерживает)
        try:
            self._popup.attributes('-toolwindow', True)
        except tk.TclError as e:
            logger.debug('Popup: не удалось применить toolwindow-стиль: %s', e)

        self._apply_toolwindow_style()

        try:
            self._popup.overrideredirect(True)
            self._popup.attributes('-topmost', True)
            self._popup.configure(bg=PopupColors.BG)
            self._popup.focus_force()
            # grab_set() направляет все клики вне меню в popup-окно,
            # где их перехватывает bind_all('<Button-1>', _on_global_click)
            self._popup.grab_set()
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка настройки окна: %s', e,
            )
            self._safe_destroy()
            return

        self._configure_popup(x, y, items)
        logger.debug(
            'Popup: меню открыто (%s пунктов)',
            len(items) if items else 0,
        )

    def _apply_toolwindow_style(self) -> None:
        """Скрывает popup из панели задач Windows через Win32 API.

        Toplevel по умолчанию может иметь WS_EX_APPWINDOW,
        что приводит к появлению иконки «перо» в таскбаре.
        Применяем WS_EX_TOOLWINDOW сразу после создания окна.
        Ленивый импорт ctypes — Win32-специфичный код.
        """
        if not self._popup:
            return
        try:
            # ленивый импорт ctypes — Win32-специфичный код
            import ctypes  # pylint: disable=import-outside-toplevel
            hwnd = self._popup.winfo_id()
            gwl_exstyle = -20
            ws_ex_appwindow = 0x00040000
            ws_ex_toolwindow = 0x00000080
            ws_ex_noactivate = 0x08000000
            swp_framechanged = 0x0020
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            swp_nozorder = 0x0004
            swp_noactivate = 0x0010
            # type: ignore[reportAttributeAccessIssue] нужен,
            # т.к. pyright на Linux не распознаёт ctypes.windll
            ex_style = (
                ctypes.windll.user32.GetWindowLongPtrW(  # type: ignore[reportAttributeAccessIssue]
                    hwnd, gwl_exstyle,
                )
            )
            ex_style &= ~ws_ex_appwindow
            ex_style |= ws_ex_toolwindow
            ex_style |= ws_ex_noactivate
            ctypes.windll.user32.SetWindowLongPtrW(  # type: ignore[reportAttributeAccessIssue]
                hwnd, gwl_exstyle, ex_style,
            )
            ctypes.windll.user32.SetWindowPos(  # type: ignore[reportAttributeAccessIssue]
                hwnd, 0, 0, 0, 0, 0,
                swp_framechanged | swp_nomove
                | swp_nosize | swp_nozorder | swp_noactivate,
            )
            logger.debug(
                'Popup: WS_EX_TOOLWINDOW применён к Toplevel '
                '(HWND=%s)', hwnd,
            )
        except (OSError, AttributeError, tk.TclError, ValueError):
            logger.debug(
                'Popup: не удалось применить WS_EX_TOOLWINDOW '
                'к popup-окну — иконка может появиться в таскбаре',
            )

    def _calc_y_position(
        self,
        y: Optional[int],
        height: int,
    ) -> int:
        """
        Вычисляет Y-координату для popup.

        Если y=None — пытается расположить над курсором,
        при нехватке места — под курсором, в крайнем случае —
        прижимает к нижнему краю экрана.

        Args:
            y: Исходная Y-координата (или None).
            height: Высота popup.

        Returns:
            Y-координата до экранного клампинга.
        """
        if y is not None:
            return y

        try:
            # self._popup может быть None вне жизненного цикла окна
            sh = self._popup.winfo_screenheight()  # type: ignore[reportOptionalMemberAccess]
        except tk.TclError:
            sh = 1080
        # self._root может быть None до вызова show()
        pointer_y = self._root.winfo_pointery()  # type: ignore[union-attr]
        above_y = pointer_y - height - 8
        if above_y >= 0:
            return above_y

        below_y = pointer_y + 8
        if below_y + height <= sh:
            return below_y

        # Не влезает целиком — прижимаем к нижнему краю,
        # чтобы кнопка "Выход" была гарантированно видна
        return sh - height - 4

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

        # Позиционирование по X
        if x is None:
            x = (
                self._root.winfo_pointerx()
                - width // 2
            )

        # Позиционирование по Y (с учётом границ экрана)
        y = self._calc_y_position(y, height)

        # Границы экрана для X
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

        # Строим содержимое ДО geometry
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

        # После построения — получаем реальные размеры
        try:
            self._popup.update_idletasks()
            real_w = self._popup.winfo_reqwidth()
            real_h = self._popup.winfo_reqheight()
        except tk.TclError:
            real_w, real_h = width, height

        # Высота окна резервирует место под многострочный тултип
        # (до 3 строк): calc_height включает высоту статусбара, поэтому
        # при появлении перенесённого текста подсказки пункты меню
        # не сжимаются и не перекрываются.
        real_h = max(real_h, self.calc_height(items))

        # Пересчитываем Y с учётом реальной высоты окна, чтобы кнопка
        # «Выход» гарантированно помещалась на экране (real_h может
        # оказаться больше расчётной height из-за переноса текста).
        try:
            # self._popup может быть None вне жизненного цикла окна
            sh = self._popup.winfo_screenheight()  # type: ignore[reportOptionalMemberAccess]
        except tk.TclError:
            sh = 1080
        y = max(0, min(y, sh - real_h - 4))

        # Устанавливаем geometry с реальными размерами
        try:
            self._popup.geometry(
                f'{real_w}x{real_h}+{x}+{y}',
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
            real_w, real_h, x, y,
        )

        # Автозакрытие при потере фокуса
        try:
            def _bind_focus_out() -> None:
                """Привязывает обработчики закрытия меню.

                Если команда ещё выполняется или popup не существует,
                обработчики не устанавливаются. Иначе:
                - при потере фокуса окно автоматически закрывается;
                - глобальный перехват кликов (bind_all на popup-окно)
                  закрывает меню при клике вне его геометрии.
                """
                if self._command_running:
                    return
                if (
                    self._popup
                    and self._popup.winfo_exists()
                ):
                    self._popup.bind(
                        '<FocusOut>',
                        lambda _e: self.dismiss(),
                    )
                    # Перехватываем клики, направленные в popup-окно
                    # через grab_set(). Клики по пунктам меню обрабатываются
                    # раньше (bind на виджетах), поэтому сюда попадают
                    # только клики вне геометрии меню.
                    # add='+' сохраняет существующие глобальные биндинги.
                    self._popup.bind_all(
                        '<Button-1>',
                        self._on_global_click,  # type: ignore[reportArgumentType]
                        add='+',
                    )

            self._focus_out_after_id = self._popup.after(
                100, _bind_focus_out,
            )
        except tk.TclError as e:
            logger.warning(
                'Popup: не удалось установить '
                'обработчики закрытия меню: %s', e,
            )

        # Плавное появление
        self._fade_in()

    @staticmethod
    def calc_height(items: List[Dict[str, Any]]) -> int:
        """Вычисляет высоту popup на основе количества элементов."""
        item_height = 28  # высота одного пункта (уменьшено)
        separator_height = 8  # высота разделителя (уменьшено)
        padding = 6  # верхний + нижний padding (3+3) — совпадает с _build_items
        # Статусбар для тултипов: резервируем место под многострочный
        # текст (до 3 строк). Метка создаётся с height=3 (фиксированные
        # 3 строки, измерено ~53px) плюс разделитель под ней (~3px).
        # При переносе текста пункты меню не сжимаются и не перекрываются.
        statusbar_height = 56

        height = padding
        for item in items:
            if item.get('type') == 'separator':
                height += separator_height
            else:
                height += item_height
        height += padding
        height += statusbar_height
        return max(height, 40)

    def _build_items(self, items: List[Dict[str, Any]]) -> None:
        """Строит элементы меню."""
        if not self._popup:
            return

        try:
            # Верхний padding
            # stubs tkinter не знают runtime-аргументы конструктора
            tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, height=3,
            ).pack(fill='x')

            # Статусбар для тултипов (верхняя строка).
            # Перенос строки включён через wraplength: текст подсказки
            # переносится на несколько строк вместо обрезания.
            # justify='left' выравнивает перенесённые строки по левому краю,
            # padx=6 — компактный левый отступ.
            # height=3 резервирует фиксированные 3 строки: окно строится
            # сразу с учётом многострочного тултипа, пункты меню при
            # появлении подсказки не сжимаются и не перекрываются
            # (высота метки не меняется динамически).
            self._tooltip_label = tk.Label(
                self._popup,
                text='',
                bg=PopupColors.BG,
                fg=PopupColors.TEXT_MUTED,
                font=('Segoe UI', 9),
                anchor='w',
                justify='left',
                padx=6,
                pady=3,
                height=3,
                wraplength=200,
            )
            self._tooltip_label.pack(
                fill='x', side='top', padx=4, pady=(2, 0),
            )

            # Разделитель под статусбаром
            # stubs tkinter не знают runtime-аргументы конструктора
            tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BORDER, height=1,
            ).pack(fill='x', padx=8, pady=(1, 1))

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
                        tooltip=item.get('tooltip'),
                    )
                elif item_type == 'check':
                    self._add_check_item(
                        text=item.get('text', ''),
                        icon=item.get('icon', ''),
                        checked=item.get('checked', False),
                        command=item.get('command'),
                        tooltip=item.get('tooltip'),
                    )
                elif item_type == 'header':
                    self._add_header(
                        text=item.get('text', ''),
                        icon=item.get('icon', ''),
                        color=item.get('color'),
                        tooltip=item.get('tooltip'),
                    )

            # Нижний padding
            # stubs tkinter не знают runtime-аргументы конструктора
            tk.Frame(  # type: ignore[reportCallIssue]
                self._popup, bg=PopupColors.BG, height=3,
            ).pack(fill='x')
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter при построении: %s', e,
            )
        except (TypeError, ValueError, KeyError) as e:
            logger.error(
                'Popup: ошибка данных при построении: %s', e,
            )

    def _add_header(
        self,
        text: str,
        icon: str = '',
        color: Optional[str] = None,
        tooltip: Optional[str] = None,
    ) -> None:
        """Добавляет заголовок в меню.

        Args:
            text: Текст заголовка.
            icon: Unicode-иконка (опционально).
            color: Цвет текста (опционально, по умолчанию акцентный).
            tooltip: Инлайн-подсказка в статусбаре (опционально).
        """
        try:
            frame = tk.Frame(  # type: ignore[reportCallIssue]  # pyright не знает tkinter
                self._popup, bg=PopupColors.BG,
            )
            frame.pack(fill='x', padx=4, pady=(2, 2))

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

            lbl = tk.Label(
                frame,
                text=text,
                bg=PopupColors.BG,
                fg=color or PopupColors.ACCENT,
                font=('Segoe UI', 9, 'bold'),
                anchor='w',
                padx=12,
                pady=4,
            )
            lbl.pack(side='left', fill='x', expand=True, padx=4)

            if tooltip:
                self._bind_tooltip(frame, tooltip)
                self._bind_tooltip(lbl, tooltip)
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter в _add_header: %s', e,
            )
        except (TypeError, ValueError) as e:
            logger.error(
                'Popup: ошибка данных в _add_header: %s', e,
            )

    def _execute_menu_command(self, cmd: Optional[Callable[[], None]]) -> None:
        """Выполняет команду пункта меню с корректным закрытием popup.

        Порядок действий важен:
        1. Устанавливаем _command_running — глобальный клик игнорируется.
        2. Отменяем отложенный биндинг FocusOut (after), чтобы он
           не сработал во время выполнения команды.
        3. Освобождаем grab и снимаем FocusOut с popup (если открыт).
        4. Закрываем popup ДО выполнения команды: команда может
           блокировать mainloop (например, wait_variable в диалоге),
           и меню не должно оставаться открытым на время её работы.
        5. Выполняем команду с перехватом ошибок.
        6. В finally сбрасываем _command_running.

        Args:
            cmd: Обработчик команды пункта меню (может быть None).
        """
        self._command_running = True
        # Отменяем отложенный биндинг FocusOut (after(100, ...)),
        # чтобы он не перевесился заново во время работы команды
        if self._focus_out_after_id is not None:
            try:
                if self._popup is not None:
                    self._popup.after_cancel(
                        self._focus_out_after_id,
                    )
            except (tk.TclError, ValueError) as e:
                logger.debug('Popup: не удалось отменить after_cancel: %s', e)
            self._focus_out_after_id = None
        try:
            if self._popup and self._popup.winfo_exists():
                self._popup.grab_release()
                self._popup.unbind('<FocusOut>')
        except tk.TclError as e:
            logger.debug('Popup: TclError при grab_release: %s', e)
        # Закрываем меню ДО запуска команды, чтобы блокирующие команды
        # (диалоги с wait_variable) не оставляли меню на экране
        logger.debug('Popup: меню закрыто по выбору пункта')
        self.dismiss()
        try:
            if cmd:
                cmd()
        except (OSError, ValueError, RuntimeError, tk.TclError) as e:
            logger.error(
                'Popup: ошибка при выполнении '
                'команды: %s',
                e, exc_info=True,
            )
        finally:
            self._command_running = False

    def _build_item_row(
        self,
        text: str,
        icon: str = '',
        command: Optional[Callable[[], None]] = None,
        color: Optional[str] = None,
        tooltip: Optional[str] = None,
    ) -> tk.Frame:
        """Строит базовую строку пункта меню: frame, иконка, текст, hover/клик.

        Общий каркас для обычных пунктов и пунктов с чекбоксом (DRY).
        Возвращает frame, к которому вызывающий метод может добавить
        дополнительные виджеты (например, чекбокс справа).

        Args:
            text: Текст пункта.
            icon: Unicode-иконка (опционально).
            command: Обработчик клика (опционально).
            color: Цвет текста (опционально).
            tooltip: Инлайн-подсказка в статусбаре (опционально).

        Returns:
            tk.Frame — построенная строка пункта меню.
        """
        frame = tk.Frame(  # type: ignore[reportCallIssue]  # pyright не знает tkinter
            self._popup, bg=PopupColors.BG, cursor='hand2',
        )
        frame.pack(fill='x', padx=4, pady=(0, 2))

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
        text_lbl.pack(side='left', fill='x', expand=True, padx=4, pady=4)

        # Hover + клик
        def on_enter(
            _event: tk.Event[tk.Tk],
            fr: tk.Frame = frame,
        ) -> None:
            """Подсвечивает пункт меню при наведении курсора."""
            for child in fr.winfo_children():
                child.configure(
                    # configure() принимает любые runtime-атрибуты
                    bg=PopupColors.SURFACE_HOVER,  # type: ignore[reportCallIssue]
                )
            fr.configure(
                # configure() принимает любые runtime-атрибуты
                bg=PopupColors.SURFACE_HOVER,  # type: ignore[reportCallIssue]
            )

        def on_leave(
            _event: tk.Event[tk.Tk],
            fr: tk.Frame = frame,
        ) -> None:
            """Возвращает фон пункта меню при уходе курсора."""
            for child in fr.winfo_children():
                child.configure(
                    # configure() принимает любые runtime-атрибуты
                    bg=PopupColors.BG,  # type: ignore[reportCallIssue]
                )
            fr.configure(bg=PopupColors.BG)

        def on_click(
            _event: tk.Event[tk.Tk],
            cmd: Optional[Callable[[], None]] = command,
        ) -> None:
            """Обрабатывает клик по пункту меню.

            Закрывает popup ДО выполнения команды и запускает
            команду через общий метод _execute_menu_command.
            """
            logger.debug('Popup: клик по пункту меню')
            self._execute_menu_command(cmd)

        for widget in [frame] + frame.winfo_children():
            # bind() в runtime принимает любой callable
            widget.bind('<Enter>', on_enter)  # type: ignore[reportArgumentType]
            # bind() в runtime принимает любой callable
            widget.bind('<Leave>', on_leave)  # type: ignore[reportArgumentType]
            # bind() в runtime принимает любой callable
            widget.bind('<Button-1>', on_click)  # type: ignore[reportArgumentType]
            # Тултип: показываем мгновенно при наведении,
            # прячем при уходе курсора (add='+' сохраняет hover-биндинги)
            self._bind_tooltip(widget, tooltip)

        return frame

    def _add_menu_item(
        self,
        text: str,
        icon: str = '',
        command: Optional[Callable[[], None]] = None,
        color: Optional[str] = None,
        tooltip: Optional[str] = None,
    ) -> None:
        """Добавляет пункт меню.

        Args:
            text: Текст пункта.
            icon: Unicode-иконка (опционально).
            command: Обработчик клика (опционально).
            color: Цвет текста (опционально).
            tooltip: Инлайн-подсказка в статусбаре (опционально).
        """
        try:
            self._build_item_row(
                text=text,
                icon=icon,
                command=command,
                color=color,
                tooltip=tooltip,
            )
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
        tooltip: Optional[str] = None,
    ) -> None:
        """Добавляет пункт с чекбоксом.

        Args:
            text: Текст пункта.
            icon: Unicode-иконка (опционально).
            checked: Состояние чекбокса.
            command: Обработчик клика (опционально).
            tooltip: Инлайн-подсказка в статусбаре (опционально).
        """
        try:
            frame = self._build_item_row(
                text=text,
                icon=icon,
                command=command,
                tooltip=tooltip,
            )

            # Чекбокс (справа от текста)
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
            frame = tk.Frame(  # type: ignore[reportCallIssue]  # pyright не знает tkinter
                self._popup, bg=PopupColors.BG, height=4,
            )
            frame.pack(fill='x')
            frame.pack_propagate(False)
            # stubs tkinter не знают runtime-аргументы конструктора
            tk.Frame(frame, bg=PopupColors.BORDER, height=1).pack(  # type: ignore[reportCallIssue]
                fill='x', padx=8, pady=1,
            )
        except tk.TclError as e:
            logger.error(
                'Popup: ошибка tkinter в _add_separator: %s', e,
            )

    def _show_tooltip(self, text: str) -> None:
        """Показывает инлайн-подсказку в статусбаре мгновенно.

        Текст отображается сразу при наведении курсора на пункт,
        без задержки — при быстром движении мыши статусбар
        просто обновляется новым текстом.

        Args:
            text: Текст подсказки.
        """
        self._tooltip_text = text
        self._display_tooltip()

    def _display_tooltip(self) -> None:
        """Отображает накопленный текст тултипа в статусбаре."""
        if self._tooltip_label is None or self._popup is None:
            return
        try:
            if not self._popup.winfo_exists():
                return
            self._tooltip_label.configure(text=self._tooltip_text)
        except tk.TclError:
            logger.debug(
                'Popup: статусбар тултипа недоступен — пропуск',
            )

    def _hide_tooltip(self) -> None:
        """Скрывает подсказку и очищает статусбар."""
        self._tooltip_text = ''
        if self._tooltip_label is not None:
            try:
                self._tooltip_label.configure(text='')
            except tk.TclError as e:
                logger.debug('Popup: не удалось скрыть тултип: %s', e)

    def show_loading(self, text: str) -> None:
        """
        Показывает текст состояния загрузки в статусбаре popup.

        Переиспользует механизм тултипа (_tooltip_text + _tooltip_label),
        но выделяет текст акцентным цветом, чтобы пользователь видел,
        что выполняется длительная операция (например, запуск браузера).

        Вызывается ТОЛЬКО из mainloop-потока.

        Args:
            text: Текст состояния загрузки (например, «Запуск браузера...»).
        """
        self._tooltip_text = text
        if self._tooltip_label is None or self._popup is None:
            return
        try:
            if not self._popup.winfo_exists():
                return
            self._tooltip_label.configure(
                text=text, fg=PopupColors.ACCENT,
            )
        except tk.TclError:
            logger.debug(
                'Popup: статусбар загрузки недоступен — пропуск',
            )

    def hide_loading(self) -> None:
        """
        Возвращает статусбар в штатный режим после завершения загрузки.

        Очищает текст и сбрасывает цвет на стандартный приглушённый.
        Безопасен при уже уничтоженном popup-окне (TclError).

        Вызывается ТОЛЬКО из mainloop-потока.
        """
        if self._tooltip_label is not None:
            try:
                self._tooltip_label.configure(fg=PopupColors.TEXT_MUTED)
            except tk.TclError as e:
                logger.debug('Popup: не удалось скрыть индикатор загрузки: %s', e)
        self._hide_tooltip()

    def _bind_tooltip(
        self,
        widget: Any,
        tooltip: Optional[str],
    ) -> None:
        """Привязывает показ/скрытие тултипа к виджету пункта меню.

        Использует add='+', чтобы не перезаписывать существующие
        hover-биндинги (подсветку фона). Показ — мгновенно при
        наведении, скрытие — при уходе курсора.

        Args:
            widget: Виджет пункта (frame или его label).
            tooltip: Текст подсказки (None — биндинг не ставится).
        """
        if not tooltip:
            return
        try:
            # bind() в runtime принимает любой callable
            widget.bind(  # type: ignore[reportArgumentType]
                '<Enter>',
                lambda _e, t=tooltip: self._show_tooltip(t),
                add='+',
            )
            # bind() в runtime принимает любой callable
            widget.bind(  # type: ignore[reportArgumentType]
                '<Leave>',
                lambda _e: self._hide_tooltip(),
                add='+',
            )
        except tk.TclError as e:
            logger.debug(
                'Popup: не удалось привязать тултип: %s', e,
            )

    def _fade_in(self, alpha: float = 0.0) -> None:
        """
        Плавное появление (fadeIn).

        Рекурсивно увеличивает прозрачность окна от 0.0 до 1.0
        с шагом 0.1 и интервалом 15мс. Если окно было закрыто
        во время анимации — корректно завершается (TclError).
        """
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
