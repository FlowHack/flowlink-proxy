"""Единый модуль кастомных tkinter-диалогов в стиле FlowLink Proxy.

Предоставляет функции show_info(), ask_yes_no(), show_item_picker()
для отображения кастомных модальных диалогов поверх основного окна.
Все виджеты стилизованы в тёмной теме FlowLink Proxy.
"""

import logging
import os
import sys
import tkinter as tk
from typing import Any, Callable, Optional

from server.ui.theme import ThemeColors

logger = logging.getLogger('flowlink.ui.dialogs')


def _get_resource_dir() -> str:
    """Возвращает директорию ресурсов (иконки и т.д.)."""
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', None) or os.path.dirname(
            os.path.abspath(sys.executable),
        )
    return os.getcwd()


def _set_window_icon(window: tk.Tk | tk.Toplevel) -> None:
    """Устанавливает иконку проекта на окно.

    Для Windows используется .ico (iconbitmap).
    Для Linux/macOS используется .png (iconphoto).
    При ошибке иконка не устанавливается (без падения).
    """
    try:
        resource_dir = _get_resource_dir()
        if sys.platform == 'win32':
            ico_path = os.path.join(resource_dir, 'icons', 'icon.ico')
            if os.path.isfile(ico_path):
                window.iconbitmap(ico_path)
        else:
            # Linux/macOS — iconphoto поддерживает PNG
            ico_path = os.path.join(resource_dir, 'icons', 'icon.png')
            if os.path.isfile(ico_path):
                img = tk.PhotoImage(file=ico_path)
                window.iconphoto(True, img)
    except (tk.TclError, Exception):  # pylint: disable=broad-except
        # Иконка не критична — пропускаем
        pass


def _get_or_create_root(title: str) -> tk.Tk:
    """Создаёт новый корневой Tk() для диалога (fallback).

    Используется только когда parent_root не передан (нет трея).

    Args:
        title: Заголовок окна.

    Returns:
        Новый скрытый tk.Tk.
    """
    root = tk.Tk()
    root.withdraw()
    root.title(title)
    _set_window_icon(root)
    return root


def _center_window(window: tk.Toplevel, width: int, height: int) -> None:
    """Центрирует окно на экране.

    Args:
        window: Окно для центрирования.
        width: Ширина окна.
        height: Высота окна.
    """
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f'{width}x{height}+{x}+{y}')


def _make_button(
    parent: tk.Widget,
    text: str,
    command: Optional[Callable[[], None]] = None,
    primary: bool = False,
) -> tk.Label:
    """Создаёт кастомную кнопку в стиле FlowLink Proxy.

    Args:
        parent: Родительский виджет.
        text: Текст кнопки.
        command: Функция, вызываемая при клике.
        primary: Если True — кнопка с акцентным цветом.

    Returns:
        Label-виджет, стилизованный под кнопку.
    """
    bg = ThemeColors.ACCENT if primary else ThemeColors.SURFACE
    fg = '#ffffff' if primary else ThemeColors.TEXT
    hover_bg = ThemeColors.ACCENT_HOVER if primary else ThemeColors.SURFACE_HOVER

    font_size = ThemeColors.FONT_SIZE_NORMAL
    font_weight = 'bold' if primary else 'normal'
    btn = tk.Label(
        parent,
        text=text,
        font=(ThemeColors.FONT_FAMILY[0], font_size, font_weight),
        bg=bg,
        fg=fg,
        padx=20,
        pady=6,
        cursor='hand2',
    )

    def _on_enter(event: Optional[tk.Event] = None) -> None:  # pylint: disable=unused-argument
        btn.configure(bg=hover_bg)

    def _on_leave(event: Optional[tk.Event] = None) -> None:  # pylint: disable=unused-argument
        btn.configure(bg=bg)

    def _on_click(event: Optional[tk.Event] = None) -> None:  # pylint: disable=unused-argument
        if command:
            command()

    btn.bind('<Enter>', _on_enter)
    btn.bind('<Leave>', _on_leave)
    btn.bind('<Button-1>', _on_click)

    return btn


def _make_item_row(
    parent: tk.Widget,
    label: str,
    subtitle: str,
    command: Optional[Callable[[], None]] = None,
) -> tk.Frame:
    """Создаёт кликабельную строку элемента списка.

    Args:
        parent: Родительский виджет.
        label: Основной текст (название).
        subtitle: Дополнительный текст (путь).
        command: Функция при клике.

    Returns:
        Frame с элементами строки.
    """
    row = tk.Frame(parent, bg=ThemeColors.SURFACE, cursor='hand2')

    # Основной текст
    lbl = tk.Label(
        row,
        text=label,
        font=(ThemeColors.FONT_FAMILY[0], ThemeColors.FONT_SIZE_NORMAL, 'bold'),
        bg=ThemeColors.SURFACE,
        fg=ThemeColors.TEXT,
        anchor='w',
        padx=12,
        pady='6 0',  # type: ignore[reportArgumentType]
    )
    lbl.pack(fill='x')

    # Подпись (путь)
    sub = tk.Label(
        row,
        text=subtitle,
        font=(ThemeColors.FONT_FAMILY[0], ThemeColors.FONT_SIZE_SMALL),
        bg=ThemeColors.SURFACE,
        fg=ThemeColors.TEXT_SECONDARY,
        anchor='w',
        padx=12,
        pady='0 6',  # type: ignore[reportArgumentType]
    )
    sub.pack(fill='x')

    # Разделитель
    sep = tk.Frame(row, height=1, bg=ThemeColors.BORDER)
    sep.pack(fill='x')

    def _on_enter(event: Optional[tk.Event] = None) -> None:  # pylint: disable=unused-argument
        row.configure(bg=ThemeColors.SURFACE_HOVER)
        lbl.configure(bg=ThemeColors.SURFACE_HOVER)
        sub.configure(bg=ThemeColors.SURFACE_HOVER)

    def _on_leave(event: Optional[tk.Event] = None) -> None:  # pylint: disable=unused-argument
        row.configure(bg=ThemeColors.SURFACE)
        lbl.configure(bg=ThemeColors.SURFACE)
        sub.configure(bg=ThemeColors.SURFACE)

    def _on_click(event: Optional[tk.Event] = None) -> None:  # pylint: disable=unused-argument
        if command:
            command()

    row.bind('<Enter>', _on_enter)
    row.bind('<Leave>', _on_leave)
    row.bind('<Button-1>', _on_click)
    lbl.bind('<Button-1>', _on_click)
    sub.bind('<Button-1>', _on_click)

    return row


def show_info(  # pylint: disable=too-many-locals,too-many-statements
    title: str,
    message: str,
    buttons: Optional[list[dict[str, Any]]] = None,
    parent_root: Optional[tk.Tk] = None,
) -> Optional[str]:
    """Показывает кастомный диалог в стиле FlowLink Proxy.

    Args:
        title: Заголовок окна.
        message: Текст сообщения.
        buttons: Список кнопок. Каждая кнопка — словарь:
            {'text': str, 'action': callable, 'primary': bool}.
            Если None — создаётся одна кнопка 'OK'.
        parent_root: Существующий Tk() для привязки диалога.
            Если передан — используется wait_window (работает в mainloop трея).
            Если None — создаётся новый Tk() со своим mainloop.

    Returns:
        'closed' если окно закрыто без выбора, иначе None.
    """
    if buttons is None:
        buttons = [{'text': 'OK', 'primary': True}]

    result = {'value': 'closed'}

    owns_root = parent_root is None
    root = parent_root if parent_root is not None else _get_or_create_root(title)

    # Создаём диалоговое окно
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.configure(bg=ThemeColors.BG)
    dialog.overrideredirect(False)
    dialog.resizable(False, False)
    dialog.attributes('-topmost', True)
    _set_window_icon(dialog)

    # Основной контейнер с рамкой
    outer = tk.Frame(dialog, bg=ThemeColors.BORDER, padx=1, pady=1)
    outer.pack(fill='both', expand=True)

    # Внутренний контейнер
    inner = tk.Frame(outer, bg=ThemeColors.BG)
    inner.pack(fill='both', expand=True, padx=0, pady=0)

    # Заголовок
    title_lbl = tk.Label(
        inner,
        text=title,
        font=(ThemeColors.FONT_FAMILY[0], ThemeColors.FONT_SIZE_TITLE, 'bold'),
        bg=ThemeColors.BG,
        fg=ThemeColors.ACCENT,
        anchor='w',
        padx=16,
        pady='12 4',  # type: ignore[reportArgumentType]
    )
    title_lbl.pack(fill='x')

    # Разделитель под заголовком
    title_sep = tk.Frame(inner, height=1, bg=ThemeColors.BORDER)
    title_sep.pack(fill='x', padx=16)

    # Текст сообщения
    msg_lbl = tk.Label(
        inner,
        text=message,
        font=(ThemeColors.FONT_FAMILY[0], ThemeColors.FONT_SIZE_NORMAL),
        bg=ThemeColors.BG,
        fg=ThemeColors.TEXT,
        anchor='w',
        justify='left',
        padx=16,
        pady='12 16',  # type: ignore[reportArgumentType]
    )
    msg_lbl.pack(fill='x')

    # Контейнер для кнопок
    btn_frame = tk.Frame(inner, bg=ThemeColors.BG)
    btn_frame.pack(fill='x', padx=16, pady='0 12')

    # Создаём кнопки
    for btn_data in buttons:
        text = btn_data.get('text', 'OK')
        primary = btn_data.get('primary', False)

        def _make_action(b_data: dict) -> Callable[[], None]:
            def _action() -> None:
                action = b_data.get('action')
                if action:
                    action()
                result['value'] = b_data.get('text', 'OK')
                dialog.destroy()
                if owns_root:
                    root.quit()
            return _action

        btn = _make_button(
            btn_frame,
            text=text,
            command=_make_action(btn_data),
            primary=primary,
        )
        btn.pack(side='right', padx='4 0')

    # Центрируем окно
    dialog.update_idletasks()
    width = max(400, dialog.winfo_reqwidth())
    height = dialog.winfo_reqheight()
    _center_window(dialog, width, height)

    # Модальность
    dialog.grab_set()
    dialog.focus_force()

    # Обработка закрытия окна
    def _on_close() -> None:
        result['value'] = 'closed'
        dialog.destroy()
        if owns_root:
            root.quit()

    dialog.protocol('WM_DELETE_WINDOW', _on_close)

    # Ожидаем закрытия диалога
    if owns_root:
        root.mainloop()
        root.destroy()
    else:
        root.wait_window(dialog)

    return result['value']


def ask_yes_no(
    title: str,
    message: str,
    yes_text: str = 'Да',
    no_text: str = 'Нет',
) -> bool:
    """Показывает диалог с вопросом (Да/Нет).

    Args:
        title: Заголовок окна.
        message: Текст вопроса.
        yes_text: Текст на кнопке 'Да'.
        no_text: Текст на кнопке 'Нет'.

    Returns:
        True если нажата 'Да', False если 'Нет' или закрыто.
    """
    result = {'value': False}

    def _on_yes() -> None:
        result['value'] = True

    def _on_no() -> None:
        result['value'] = False

    buttons = [
        {'text': no_text, 'action': _on_no, 'primary': False},
        {'text': yes_text, 'action': _on_yes, 'primary': True},
    ]

    show_info(title, message, buttons=buttons)
    return result['value']


def show_item_picker(  # pylint: disable=too-many-locals,too-many-statements,too-many-arguments,too-many-positional-arguments
    title: str,
    message: str,
    items: list[dict[str, Any]],
    on_select: Callable[[dict[str, Any]], None],
    allow_manual: bool = True,
    on_manual: Optional[Callable[[], None]] = None,
    parent_root: Optional[tk.Tk] = None,
) -> None:
    """Показывает диалог со списком элементов для выбора.

    Args:
        title: Заголовок окна.
        message: Текст над списком.
        items: Список элементов. Каждый элемент — словарь с ключами:
            'label' (str), 'subtitle' (str), и любыми доп. данными.
        on_select: Функция, вызываемая при выборе элемента.
            Принимает словарь элемента.
        allow_manual: Если True — показывает кнопку 'Указать вручную'.
        on_manual: Функция, вызываемая после закрытия диалога,
            если нажата кнопка 'Указать вручную'.
        parent_root: Существующий Tk() для привязки диалога.
            Если передан — используется wait_window (работает в mainloop трея).
            Если None — создаётся новый Tk() со своим mainloop.
    """
    owns_root = parent_root is None
    root = parent_root if parent_root is not None else _get_or_create_root(title)

    # Создаём диалоговое окно
    dialog = tk.Toplevel(root)
    dialog.title(title)
    dialog.configure(bg=ThemeColors.BG)
    dialog.overrideredirect(False)
    dialog.resizable(False, False)
    dialog.attributes('-topmost', True)
    _set_window_icon(dialog)

    # Основной контейнер с рамкой
    outer = tk.Frame(dialog, bg=ThemeColors.BORDER, padx=1, pady=1)
    outer.pack(fill='both', expand=True)

    # Внутренний контейнер
    inner = tk.Frame(outer, bg=ThemeColors.BG)
    inner.pack(fill='both', expand=True)

    # Заголовок
    title_lbl = tk.Label(
        inner,
        text=title,
        font=(ThemeColors.FONT_FAMILY[0], ThemeColors.FONT_SIZE_TITLE, 'bold'),
        bg=ThemeColors.BG,
        fg=ThemeColors.ACCENT,
        anchor='w',
        padx=16,
        pady='12 4',  # type: ignore[reportArgumentType]
    )
    title_lbl.pack(fill='x')

    # Разделитель
    title_sep = tk.Frame(inner, height=1, bg=ThemeColors.BORDER)
    title_sep.pack(fill='x', padx=16)

    # Текст сообщения
    if message:
        msg_lbl = tk.Label(
            inner,
            text=message,
            font=(ThemeColors.FONT_FAMILY[0], ThemeColors.FONT_SIZE_NORMAL),
            bg=ThemeColors.BG,
            fg=ThemeColors.TEXT_SECONDARY,
            anchor='w',
            justify='left',
            padx=16,
            pady='8 4',  # type: ignore[reportArgumentType]
        )
        msg_lbl.pack(fill='x')

    # Контейнер для списка (с прокруткой если много элементов)
    list_container = tk.Frame(inner, bg=ThemeColors.BG)
    list_container.pack(fill='both', expand=True, padx=8, pady='4 8')

    canvas = tk.Canvas(list_container, bg=ThemeColors.BG, highlightthickness=0)
    scrollbar = tk.Scrollbar(list_container, orient='vertical', command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=ThemeColors.BG)

    scrollable_frame.bind(
        '<Configure>',
        lambda e: canvas.configure(scrollregion=canvas.bbox('all')),  # pylint: disable=undefined-variable
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)

    # Добавляем элементы списка
    for item in items:
        def _make_item_action(itm: dict) -> Callable[[], None]:
            def _action() -> None:
                on_select(itm)
                dialog.destroy()
                if owns_root:
                    root.quit()
            return _action

        row = _make_item_row(
            scrollable_frame,
            label=item.get('label', ''),
            subtitle=item.get('subtitle', ''),
            command=_make_item_action(item),
        )
        row.pack(fill='x')

    # Если элементов много — показываем скроллбар
    if len(items) > 8:
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
    else:
        canvas.pack(side='left', fill='both', expand=True)

    # Нижняя панель с кнопками
    bottom_frame = tk.Frame(inner, bg=ThemeColors.BG)
    bottom_frame.pack(fill='x', padx=16, pady='0 12')

    # Кнопка "Указать вручную"
    if allow_manual:
        manual_result = {'clicked': False}

        def _on_manual() -> None:
            manual_result['clicked'] = True
            dialog.destroy()
            if owns_root:
                root.quit()

        manual_btn = _make_button(
            bottom_frame,
            text='Указать вручную',
            command=_on_manual,
            primary=False,
        )
        manual_btn.pack(side='left')

    # Кнопка "Отмена"
    def _on_cancel() -> None:
        dialog.destroy()
        if owns_root:
            root.quit()

    cancel_btn = _make_button(
        bottom_frame,
        text='Отмена',
        command=_on_cancel,
        primary=False,
    )
    cancel_btn.pack(side='right')

    # Отображаем окно и центрируем его.
    # ВАЖНО: geometry ДО deiconify — иначе на withdrawn root
    # окно маппится с вырожденным размером (обрезок 1.5см×0.5см).
    dialog.update_idletasks()
    width = max(480, dialog.winfo_reqwidth())
    # Высота рассчитывается по количеству элементов: ~44px на строку + ~120px overhead
    content_height = len(items) * 44 + 120
    height = min(500, max(200, content_height))
    _center_window(dialog, width, height)
    dialog.deiconify()
    dialog.update()

    # Модальность
    try:
        dialog.grab_set()
    except tk.TclError as e:
        logger.warning('Диалог: не удалось установить grab: %s', e)
    dialog.focus_force()

    # Обработка закрытия окна
    def _on_close() -> None:
        dialog.destroy()
        if owns_root:
            root.quit()

    dialog.protocol('WM_DELETE_WINDOW', _on_close)

    # Ожидаем закрытия диалога
    if owns_root:
        root.mainloop()
        root.destroy()
    else:
        root.wait_window(dialog)

    # Если нажали "Указать вручную" — вызываем коллбэк
    if allow_manual and manual_result.get('clicked') and on_manual:
        on_manual()
