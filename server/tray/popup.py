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

import logging
import threading
import tkinter as tk
from queue import Queue, Empty

logger = logging.getLogger('flowlink.tray.popup')


class PopupColors:
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

    def __init__(self):
        self._root = None
        self._popup = None
        self._queue = Queue()
        self._build_lock = threading.Lock()
        self._polling_active = False

    def set_tk_root(self, root):
        """
        Устанавливает корневой Tk (для интеграции с внешним mainloop).

        Args:
            root: Экземпляр tk.Tk().
        """
        self._root = root

    def thread_safe(self, func):
        """
        Безопасно выполняет функцию в потоке tkinter.

        Args:
            func: Callable без аргументов.
        """
        self._queue.put(func)
        if self._root and not self._polling_active:
            self._polling_active = True
            self._root.after(50, self._poll_queue)

    def _poll_queue(self):
        """Очищает очередь сообщений и выполняет функции."""
        try:
            while True:
                func = self._queue.get_nowait()
                func()
        except Empty:
            pass
        if self._root and self._polling_active:
            self._root.after(100, self._poll_queue)

    def show(self, x=None, y=None, items=None):
        """
        Показывает popup-меню в указанной позиции.

        Args:
            x: Координата X (экранная). Если None — центр по горизонтали.
            y: Координата Y (экранная). Если None — над курсором.
            items: Список элементов меню (см. _build_items).
        """
        with self._build_lock:
            self.dismiss()
            self._create_popup(x, y, items or [])

    def dismiss(self):
        """Закрывает popup-меню, если оно открыто."""
        self._polling_active = False
        if self._popup:
            try:
                self._popup.grab_release()
            except tk.TclError:
                logger.debug('grab_release: окно уже уничтожено')
            try:
                self._popup.destroy()
            except tk.TclError:
                logger.debug('destroy: окно уже уничтожено')
            self._popup = None

    def _create_popup(self, x, y, items):
        """Создаёт и отображает popup-окно."""
        if not self._root:
            logger.error('Tk root не установлен — popup невозможен')
            return

        self._popup = tk.Toplevel(self._root)
        self._popup.overrideredirect(True)
        self._popup.attributes('-topmost', True)
        self._popup.configure(bg=PopupColors.BG)

        # Ширина popup
        width = 220
        # Высота вычисляется динамически
        height = self.calc_height(items)

        # Позиционирование
        if x is None:
            x = self._root.winfo_pointerx() - width // 2
        if y is None:
            y = self._root.winfo_pointery() - height - 8

        # Не выходит за экран
        sw = self._popup.winfo_screenwidth()
        sh = self._popup.winfo_screenheight()
        x = max(0, min(x, sw - width - 4))
        y = max(0, min(y, sh - height - 4))

        self._popup.geometry(f'{width}x{height}+{x}+{y}')

        # Строим содержимое
        self._build_items(items)

        # Автозакрытие при потере фокуса
        self._popup.bind('<FocusOut>', lambda _e: self.dismiss())
        self._popup.after(50, self._popup.grab_set)

        # Плавное появление
        self._fade_in()

    @staticmethod
    def calc_height(items):
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

    def _build_items(self, items):
        """Строит элементы меню."""
        if not self._popup:
            return

        # Верхний padding
        tk.Frame(self._popup, bg=PopupColors.BG, height=4).pack(fill='x')

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
        tk.Frame(self._popup, bg=PopupColors.BG, height=4).pack(fill='x')

    def _add_header(self, text):
        """Добавляет заголовок в меню."""
        lbl = tk.Label(
            self._popup,
            text=text,
            bg=PopupColors.BG,
            fg=PopupColors.ACCENT,
            font=('Segoe UI', 11, 'bold'),
            anchor='w',
            padx=12,
            pady=(4, 2),
        )
        lbl.pack(fill='x')

    def _add_menu_item(self, text, icon='', command=None, color=None):
        """Добавляет пункт меню."""
        frame = tk.Frame(self._popup, bg=PopupColors.BG, cursor='hand2')
        frame.pack(fill='x', padx=4)

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
            icon_lbl.pack(side='left', padx=(4, 0))

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
        def on_enter(_event, fr=frame):
            for child in fr.winfo_children():
                child.configure(bg=PopupColors.SURFACE_HOVER)
            fr.configure(bg=PopupColors.SURFACE_HOVER)

        def on_leave(_event, fr=frame):
            for child in fr.winfo_children():
                child.configure(bg=PopupColors.BG)
            fr.configure(bg=PopupColors.BG)

        def on_click(_event, cmd=command):
            if cmd:
                cmd()
            self.dismiss()

        for widget in [frame] + frame.winfo_children():
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
            widget.bind('<Button-1>', on_click)

    def _add_check_item(self, text, icon='', checked=False, command=None):
        """Добавляет пункт с чекбоксом."""
        frame = tk.Frame(self._popup, bg=PopupColors.BG, cursor='hand2')
        frame.pack(fill='x', padx=4)

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
            icon_lbl.pack(side='left', padx=(4, 0))

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
        def on_enter(_event, fr=frame):
            for child in fr.winfo_children():
                child.configure(bg=PopupColors.SURFACE_HOVER)
            fr.configure(bg=PopupColors.SURFACE_HOVER)

        def on_leave(_event, fr=frame):
            for child in fr.winfo_children():
                child.configure(bg=PopupColors.BG)
            fr.configure(bg=PopupColors.BG)

        def on_click(_event, cmd=command):
            if cmd:
                cmd()
            self.dismiss()

        for widget in [frame] + frame.winfo_children():
            widget.bind('<Enter>', on_enter)
            widget.bind('<Leave>', on_leave)
            widget.bind('<Button-1>', on_click)

    def _add_separator(self):
        """Добавляет разделитель."""
        frame = tk.Frame(self._popup, bg=PopupColors.BG, height=10)
        frame.pack(fill='x')
        frame.pack_propagate(False)
        tk.Frame(frame, bg=PopupColors.BORDER, height=1).pack(
            fill='x', padx=8, pady=4,
        )

    def _fade_in(self, alpha=0.0):
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
