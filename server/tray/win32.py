"""
Win32 бэкенд системного трей через ctypes.

Единственная ответственность: создание и управление иконкой в трее
и borderless popup-окном через Win32 API (ctypes).

Используется ТОЛЬКО на Windows. На других платформах не импортируется.
"""

import ctypes
import ctypes.wintypes as wt
import logging
import os
import threading
import tkinter as tk

from server.tray.popup import FlowLinkPopup
from server.tray.menu import build_menu_items

logger = logging.getLogger('flowlink.tray.win32')

# ───── Константы Win32 ─────
WM_APP = 0x8000
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_DESTROY = 0x0002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004
NOTIFYICON_VERSION_4 = 4
TRAY_CALLBACK = WM_APP + 1

# ───── Win32 API ─────
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_shell32 = ctypes.windll.shell32

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
)


class _NOTIFYICONDATAW(ctypes.Structure):
    """Структура NOTIFYICONDATAW для Shell_NotifyIconW."""
    _fields_ = [
        ('cbSize', wt.DWORD),
        ('hWnd', wt.HWND),
        ('uID', wt.UINT),
        ('uFlags', wt.UINT),
        ('uCallbackMessage', wt.UINT),
        ('hIcon', wt.HICON),
        ('szTip', wt.WCHAR * 128),
        ('dwState', wt.DWORD),
        ('dwStateMask', wt.DWORD),
        ('szInfo', wt.WCHAR * 256),
        ('uTimeout', wt.UINT),
        ('szInfoTitle', wt.WCHAR * 64),
        ('dwInfoFlags', wt.DWORD),
    ]


class _NOTIFYICONIDENTIFIER(ctypes.Structure):
    """Идентификатор иконки для Shell_NotifyIconGetRect."""
    _fields_ = [
        ('cbSize', wt.DWORD),
        ('hWnd', wt.HWND),
        ('uID', wt.UINT),
    ]


class _POINT(ctypes.Structure):
    """Точка (x, y) для GetCursorPos."""
    _fields_ = [('x', wt.LONG), ('y', wt.LONG)]


class Win32Tray:
    """
    Win32-бэкенд системного трей для FlowLink Proxy.

    Создаёт иконку в трее через Shell_NotifyIconW и borderless
    popup-окно через tkinter при правом клике.

    Args:
        callbacks: Словарь с коллбэками (stop, autostart_getter, и т.д.).
    """

    _ICON_PATH = 'icons/icon.png'
    _UID = 1

    def __init__(self, callbacks):
        self._callbacks = callbacks
        self._hwnd = None
        self._wndproc = None
        self._popup = FlowLinkPopup()
        self._tk_root = None
        self._tk_thread = None

    def start(self):
        """Запускает трей-иконку в отдельном потоке."""
        self._tk_thread = threading.Thread(
            target=self._run_tk, daemon=True,
        )
        self._tk_thread.start()

    def stop(self):
        """Останавливает трей и закрывает окно."""
        if self._hwnd:
            try:
                _user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
            except OSError as e:
                logger.warning(
                    'Tray Win32: не удалось отправить WM_DESTROY: %s',
                    e,
                )

    def refresh_menu(self):
        """Обновляет popup-меню (вызывается при изменении конфига)."""
        # Popup рендерит свежее состояние при каждом открытии

    def _run_tk(self):
        """Запускает tkinter mainloop в отдельном потоке."""
        try:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()
            self._popup.set_tk_root(self._tk_root)
            self._create_tray_icon()
            self._tk_root.mainloop()
        except tk.TclError as e:
            logger.error('Tray Win32: ошибка tkinter: %s', e)
        except OSError as e:
            logger.error('Tray Win32: системная ошибка: %s', e)

    def _create_tray_icon(self):
        """Создаёт иконку в системном трее Windows."""
        try:
            self._wndproc = WNDPROC(self._wnd_proc)
            self._hwnd = self._create_message_window()
            self._add_icon()
            logger.info('Tray Win32: иконка создана')
        except OSError as e:
            logger.error(
                'Tray Win32: ошибка создания иконки: %s', e,
            )

    def _create_message_window(self):
        """
        Создаёт скрытое message-only окно для приёма сообщений трей.

        Returns:
            HWND — хэндл созданного окна.

        Raises:
            OSError: Не удалось зарегистрировать класс или создать окно.
        """
        wc = wt.WNDCLASS()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = _kernel32.GetModuleHandleW(None)
        wc.lpszClassName = 'FlowLinkTrayMsg'
        wc.hCursor = _user32.LoadCursorW(0, 32512)  # IDC_ARROW

        atom = _user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            raise ctypes.WinError()

        hwnd = _user32.CreateWindowExW(
            0, wc.lpszClassName, 'FlowLink Tray',
            0, 0, 0, 0, 0,
            wt.HWND(-3),  # HWND_MESSAGE
            None,
            _kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()
        return hwnd

    def _add_icon(self):
        """Добавляет иконку в системный трей."""
        from server.utils import get_resource_dir
        icon_path = os.path.join(
            get_resource_dir(), self._ICON_PATH,
        )
        hicon = _user32.LoadImageW(
            0, icon_path, 1, 0, 0, 0x00000010,
        )
        if not hicon:
            logger.warning(
                'Tray Win32: иконка %s не найдена', icon_path,
            )
            hicon = _user32.LoadIconW(0, 32512)  # IDI_APPLICATION

        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = self._UID
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = TRAY_CALLBACK
        nid.hIcon = hicon
        nid.szTip = 'FlowLink Proxy'

        ok = _shell32.Shell_NotifyIconW(
            NIM_ADD, ctypes.byref(nid),
        )
        if not ok:
            raise ctypes.WinError()

        nid.uVersion = NOTIFYICON_VERSION_4
        _shell32.Shell_NotifyIconW(
            NIM_SETVERSION, ctypes.byref(nid),
        )

    def _remove_icon(self):
        """Удаляет иконку из трея."""
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = self._UID
        _shell32.Shell_NotifyIconW(
            NIM_DELETE, ctypes.byref(nid),
        )

    def _get_icon_rect(self):
        """
        Возвращает позицию иконки трей на экране.

        Returns:
            Кортеж (left, top, right, bottom) или None при ошибке.
        """
        ident = _NOTIFYICONIDENTIFIER()
        ident.cbSize = ctypes.sizeof(
            _NOTIFYICONIDENTIFIER,
        )
        ident.hWnd = self._hwnd
        ident.uID = self._UID

        rect = wt.RECT()
        hr = _shell32.Shell_NotifyIconGetRect(
            ctypes.byref(ident), ctypes.byref(rect),
        )
        if hr != 0:
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def _get_cursor_pos(self):
        """Возвращает текущую позицию курсора."""
        pt = _POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _show_popup(self):
        """Показывает popup-меню в позиции иконки трей."""
        rect = self._get_icon_rect()
        if rect:
            x = rect[0]
            y = rect[1] - 8
        else:
            x, y = self._get_cursor_pos()
            y -= 280

        items = build_menu_items(
            self._callbacks, self.stop, 'Tray Win32',
        )

        if self._tk_root:
            self._popup.show(x=x, y=y, items=items)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Обработчик сообщений окна трей."""
        if msg == TRAY_CALLBACK:
            event = lparam & 0xFFFF
            if event in (WM_RBUTTONUP, WM_LBUTTONDBLCLK):
                self._tk_root.after(0, self._show_popup)
                return 0
            if event == WM_LBUTTONUP:
                self._tk_root.after(0, self._show_popup)
                return 0
        elif msg == WM_DESTROY:
            self._remove_icon()
            _user32.PostQuitMessage(0)
            return 0
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)
