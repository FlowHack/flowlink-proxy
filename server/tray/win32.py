"""
Win32 бэкенд системного трей через ctypes.

Единственная ответственность: создание и управление иконкой в трее
и borderless popup-окном через Win32 API (ctypes).

Используется ТОЛЬКО на Windows. На других платформах не импортируется.
"""
# Файл целиком состоит из обёрток над Win32 API через ctypes.
# Все подавления обоснованы спецификой Win32 API и НЕ дублируются
# в других файлах проекта:
#   invalid-name — имена полей Win32 структур (cbSize, hWnd и т.д.)
#   no-member    — ctypes.wintypes не содержит WNDCLASS, определён
#                  вручную как _WNDCLASS
#   use-implicit-booleaness — сравнение HRESULT hr != 0 вместо
#                 (hr) — явное сравнение с S_OK читаемее для Win32 API
#   attribute-defined-outside-init — ctypes.Structure определяет
#                  поля через _fields_, а присваивает вне __init__
#   too-few-public-methods — ctypes data-классы (0 публичных методов)
#   import-outside-toplevel — ленивый импорт get_resource_dir
#                  для отложенной инициализации пути к иконке
# pylint: disable=invalid-name,no-member
# pylint: disable=use-implicit-booleaness-not-comparison-to-zero
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-few-public-methods,too-many-instance-attributes
# pylint: disable=import-outside-toplevel

import ctypes
import ctypes.wintypes as wt
import logging
import os
import threading
import tkinter as tk

from server.tray.menu import build_menu_items
from server.tray.popup import FlowLinkPopup

logger = logging.getLogger('flowlink.tray.win32')

# ───── Crash-safe диагностика удалена ─────

# ───── Константы Win32 ─────
WM_APP = 0x8000
WM_RBUTTONUP = 0x0205
WM_RBUTTONDBLCLK = 0x0206
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
_user32 = ctypes.windll.user32  # type: ignore[reportAttributeAccessIssue]
_kernel32 = ctypes.windll.kernel32  # type: ignore[reportAttributeAccessIssue]
_shell32 = ctypes.windll.shell32  # type: ignore[reportAttributeAccessIssue]

WNDPROC = ctypes.WINFUNCTYPE(  # type: ignore[reportAttributeAccessIssue]
    ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
)
# c_long (32-bit) → c_ssize_t (pointer-sized): LRESULT — 64-бит на Win64.

# Модульный список для предотвращения GC ctypes-колбэков.
# Win32 хранит raw-указатель на WNDPROC; если Python соберёт мусор — краш.
_KEEP_ALIVE_WNDPROCS: list = []


class _WNDCLASS(ctypes.Structure):
    """Структура WNDCLASS для RegisterClassW."""
    _fields_ = [
        ('style', wt.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wt.HINSTANCE),
        ('hIcon', wt.HICON),
        ('hCursor', wt.HANDLE),
        ('hbrBackground', wt.HANDLE),
        ('lpszMenuName', wt.LPCWSTR),
        ('lpszClassName', wt.LPCWSTR),
    ]


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

    _ICON_PATH = os.path.join('icons', 'icon.ico')
    _UID = 1

    def __init__(self, callbacks):
        self._callbacks = callbacks
        self._stop = self.stop
        self._hwnd = None
        self._wndproc = None
        self._popup = FlowLinkPopup()
        self._tk_root = None
        self._tk_thread = None
        self._icon_ready = threading.Event()
        self._shutting_down = False
        self._taskbar_msg_id = 0
        self._fallback_icon_path = None
        self._popup_open = False
        self._pending_popup = False
        self._popup_timer_id = None
        self._tk_root_valid = False

    @property
    def tk_root(self):
        """Возвращает корневой Tk трея (или None)."""
        return self._tk_root

    @property
    def popup(self):
        """Возвращает popup-меню трея (или None)."""
        return self._popup

    def start(self):
        """Запускает трей-иконку в отдельном потоке."""
        self._tk_thread = threading.Thread(
            target=self._run_tk, daemon=True,
        )
        self._tk_thread.start()

    def stop(self):
        """Останавливает трей и закрывает окно."""
        self._shutting_down = True
        # Отменяем таймер проверки флага popup
        if self._popup_timer_id and self._tk_root:
            try:
                self._tk_root.after_cancel(self._popup_timer_id)
            except tk.TclError:
                pass
            self._popup_timer_id = None
        if self._hwnd:
            try:
                _user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
            except OSError as e:
                logger.warning(
                    'Tray Win32: не удалось отправить WM_DESTROY: %s',
                    e,
                )
        # Если процесс не завершился за 3 секунды — принудительный выход
        if self._tk_root:
            try:
                self._tk_root.after(3000, os._exit, 0)
            except tk.TclError:
                # Если tkinter уже недоступен — выходим немедленно
                os._exit(0)
        else:
            # Если tk_root нет — выходим немедленно
            os._exit(0)

    def refresh_menu(self):
        """Обновляет popup-меню (вызывается при изменении конфига)."""
        # Popup рендерит свежее состояние при каждом открытии

    def _init_tk(self) -> bool:  # pylint: disable=too-many-statements
        """
        Инициализирует tkinter root и withdraw.

        Returns:
            True при успехе, False при ошибке.
        """
        try:
            self._tk_root = tk.Tk()
        except tk.TclError as e:
            logger.error(
                'Tray Win32: Tcl/Tk ошибка инициализации: %s. '
                'Возможно, не найдены библиотеки tcl/tk.', e,
            )
            return False
        except RuntimeError as e:
            logger.error(
                'Tray Win32: Tcl runtime не найден: %s. '
                'PyInstaller мог не упаковать Tcl/Tk файлы.', e,
            )
            return False
        except OSError as e:
            logger.error(
                'Tray Win32: системная ошибка при создании Tk: %s', e,
            )
            return False

        # НЕМЕДЛЕННО скрываем окно — до того, как Windows зарегистрирует
        # его в таскбаре. Порядок критичен:
        # 1. Сначала -toolwindow (Tk установит WS_EX_TOOLWINDOW при создании окна)
        # 2. Потом withdraw (скрывает окно)
        # 3. Потом Win32 API для гарантии
        try:
            self._tk_root.attributes('-toolwindow', True)
        except tk.TclError as e:
            logger.error(
                'Tray Win32: ошибка установки -toolwindow: %s', e,
            )

        try:
            self._tk_root.withdraw()
        except tk.TclError as e:
            logger.error(
                'Tray Win32: ошибка withdraw(): %s', e,
            )
            return False

        # Даём Tk обработать withdraw до применения Win32 стилей
        try:
            self._tk_root.update_idletasks()
        except tk.TclError as e:
            logger.error(
                'Tray Win32: ошибка update_idletasks(): %s', e,
            )

        try:
            hwnd = self._tk_root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            # Используем модульные алиасы Win32-функций (см. строки 61-63):
            # так короче и не нужны type: ignore для pyright на Linux.
            ex_style = _user32.GetWindowLongPtrW(
                hwnd, GWL_EXSTYLE,
            )
            logger.debug(
                'Tray Win32: HWND=%s, EX_STYLE до=0x%X '
                '(APPWINDOW=%s, TOOLWINDOW=%s)',
                hwnd, ex_style,
                bool(ex_style & WS_EX_APPWINDOW),
                bool(ex_style & WS_EX_TOOLWINDOW),
            )
            ex_style &= ~WS_EX_APPWINDOW
            ex_style |= WS_EX_TOOLWINDOW
            _user32.SetWindowLongPtrW(
                hwnd, GWL_EXSTYLE, ex_style,
            )
            _user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
            )
            # Проверяем, применились ли стили
            ex_style_after = _user32.GetWindowLongPtrW(
                hwnd, GWL_EXSTYLE,
            )
            logger.debug(
                'Tray Win32: EX_STYLE после=0x%X '
                '(APPWINDOW=%s, TOOLWINDOW=%s)',
                ex_style_after,
                bool(ex_style_after & WS_EX_APPWINDOW),
                bool(ex_style_after & WS_EX_TOOLWINDOW),
            )
        except (OSError, AttributeError, tk.TclError, ValueError):
            pass  # Если не сработало — не критично

        # Повторный withdraw для гарантии
        try:
            self._tk_root.withdraw()
        except tk.TclError as e:
            logger.error(
                'Tray Win32: ошибка повторного withdraw(): %s', e,
            )

        self._popup.set_tk_root(self._tk_root)
        self._tk_root_valid = True
        return True

    def _init_tray_icon(self) -> bool:
        """
        Создаёт иконку в трее.

        Returns:
            True при успехе, False при ошибке.
        """
        try:
            self._create_tray_icon()
        except OSError as e:
            logger.error(
                'Tray Win32: ошибка создания иконки: %s', e,
            )
            return False
        except (ValueError, TypeError) as e:
            logger.error(
                'Tray Win32: ошибка аргументов при создании '
                'иконки: %s', e,
            )
            return False

        if not self._hwnd:
            logger.error(
                'Tray Win32: hwnd не установлен после '
                '_create_tray_icon',
            )
            return False
        return True

    def _run_mainloop(self) -> None:
        """Запускает tkinter mainloop с обработкой ошибок."""
        self._icon_ready.set()
        if self._tk_root is None:
            logger.error('Tray Win32: tk_root не установлен')
            return
        try:
            self._popup_timer_id = self._tk_root.after(
                50, self._poll_popup_flag,
            )
        except tk.TclError as e:
            logger.warning(
                'Tray Win32: не удалось запустить '
                '_poll_popup_flag: %s', e,
            )
        try:
            self._tk_root.mainloop()
        except tk.TclError as e:
            logger.error(
                'Tray Win32: ошибка mainloop: %s', e,
            )
        except OSError as e:
            logger.error(
                'Tray Win32: системная ошибка в mainloop: %s', e,
            )
        except (KeyboardInterrupt, SystemExit):  # pylint: disable=try-except-raise
            # Пробрасываем наверх — эти исключения не должны
            # глотаться в mainloop
            raise
        except RuntimeError as e:
            logger.error(
                'Tray Win32: критическая ошибка mainloop: %s',
                e, exc_info=True,
            )
        finally:
            pass

    def _run_tk(self):
        """
        Запускает tkinter mainloop в отдельном потоке.

        Порядок исключений (от конкретного к общему):
        1. tk.TclError — ошибки Tcl/Tk (нет дисплея, интерпретатор)
        2. RuntimeError — Tcl runtime не найден (PyInstaller)
        3. OSError — системные ошибки (DLL не найдена, память)
        4. ImportError — модуль _tkinter не может быть загружен
        5. ValueError / TypeError — некорректные аргументы
        6. Exception — последний рубец (всё остальное)
        """
        try:
            if not self._init_tk():
                return
            if not self._init_tray_icon():
                return
            self._run_mainloop()
        except ImportError as e:
            logger.error(
                'Tray Win32: модуль не найден: %s', e,
            )
        except ValueError as e:
            logger.error(
                'Tray Win32: некорректное значение: %s', e,
            )
        except TypeError as e:
            logger.error(
                'Tray Win32: некорректный тип аргумента: %s', e,
            )
        except (OSError, tk.TclError, RuntimeError) as e:
            logger.error(
                'Tray Win32: непредвиденная ошибка в потоке трей: %s',
                e, exc_info=True,
            )
        finally:
            self._icon_ready.set()

    def _create_tray_icon(self):
        """
        Создаёт иконку в системном трее Windows.

        Raises:
            OSError: Не удалось зарегистрировать класс, создать окно
                или добавить иконку.
            ValueError: Некорректные данные в структуре.
        """
        try:
            self._wndproc = WNDPROC(self._wnd_proc)
        except (TypeError, ValueError) as e:
            logger.error(
                'Tray Win32: ошибка создания WNDPROC回调а: %s', e,
            )
            raise

        # Сохраняем в модульный список, чтобы GC не собрал callback.
        _KEEP_ALIVE_WNDPROCS.append(self._wndproc)

        try:
            self._hwnd = self._create_message_window()
        except OSError as e:
            logger.error(
                'Tray Win32: ошибка создания message-окна: %s', e,
            )
            raise

        self._add_icon()
        logger.info('Tray Win32: иконка создана')

    def _create_message_window(self):
        """
        Создаёт скрытое message-only окно для приёма сообщений трей.

        Returns:
            HWND — хэндл созданного окна.

        Raises:
            OSError: Не удалось зарегистрировать класс или создать окно.
        """
        wc = _WNDCLASS()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = _kernel32.GetModuleHandleW(None)
        wc.lpszClassName = 'FlowLinkTrayMsg'
        wc.hCursor = _user32.LoadCursorW(0, 32512)  # IDC_ARROW

        atom = _user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            raise ctypes.WinError()  # type: ignore[reportAttributeAccessIssue]

        hwnd = _user32.CreateWindowExW(
            0, wc.lpszClassName, 'FlowLink Tray',
            0, 0, 0, 0, 0,
            wt.HWND(-3),  # HWND_MESSAGE
            None,
            _kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise ctypes.WinError()  # type: ignore[reportAttributeAccessIssue]

        # Регистрируем WM_TASKBAR_CREATED для пересоздания иконки
        self._taskbar_msg_id = _user32.RegisterWindowMessageW(
            'TaskbarCreated',
        )

        return hwnd

    def _add_icon(self):
        """
        Добавляет иконку в системный трей.

        Если файл иконки не найден — создаёт дефолтную (красный
        круг + FLP). Если и Pillow недоступен — системная иконка.
        Если Shell_NotifyIconW не удался — поднимает OSError.
        """
        from server.utils import get_resource_dir

        hicon = 0
        force_fallback = self._callbacks.get('test_fallback_icon', False)

        if not force_fallback:
            icon_path = os.path.normpath(
                os.path.join(get_resource_dir(), self._ICON_PATH),
            )
            hicon = _user32.LoadImageW(
                0, icon_path, 1, 0, 0, 0x00000010,
            )
            if not hicon:
                logger.warning(
                    'Tray Win32: иконка %s не найдена, '
                    'попытка создать дефолтную', icon_path,
                )
        else:
            logger.info(
                'Tray Win32: --test-fallback-icon, '
                'пропуск icon.ico',
            )

        if not hicon:
            hicon = self._create_fallback_icon()
        if not hicon:
            logger.warning(
                'Tray Win32: дефолтная иконка не создана, '
                'используется системная',
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
            raise ctypes.WinError()  # type: ignore[reportAttributeAccessIssue]

        nid.uVersion = NOTIFYICON_VERSION_4
        ok = _shell32.Shell_NotifyIconW(
            NIM_SETVERSION, ctypes.byref(nid),
        )
        if not ok:
            logger.warning(
                'Tray Win32: NIM_SETVERSION не удался '
                '(NOTIFYICON_VERSION_4) — события мыши '
                'могут работать некорректно',
            )

    def _draw_fallback_image(self, draw, font):
        """Рисует красный круг с текстом FLP на изображении."""
        size = 16
        draw.ellipse(
            [1, 1, size - 2, size - 2],
            fill=(231, 76, 60, 255),
        )
        bbox = draw.textbbox((0, 0), 'FLP', font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx, ty = (size - tw) // 2, (size - th) // 2 - 1
        draw.text((tx, ty), 'FLP', fill=(0, 0, 0, 255), font=font)

    def _load_fallback_font(self):
        """Загружает шрифт для дефолтной иконки."""
        from PIL import ImageFont  # pylint: disable=import-outside-toplevel
        try:
            return ImageFont.truetype('arial.ttf', 7)
        except OSError:
            try:
                return ImageFont.truetype(
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    7,
                )
            except OSError:
                return ImageFont.load_default()

    def _create_fallback_icon(self):
        """
        Создаёт дефолтную иконку (красный круг + «FLP») через Pillow.

        Сохраняет .ico во временный файл и загружает через LoadImageW.
        Путь к temp-файлу сохраняется для удаления в _remove_icon().

        Returns:
            HICON или 0 при ошибке.
        """
        try:
            from PIL import (Image,  # pylint: disable=import-outside-toplevel
                             ImageDraw)
        except ImportError:
            logger.warning(
                'Tray Win32: Pillow недоступен для дефолтной иконки',
            )
            return 0

        try:
            import tempfile  # pylint: disable=import-outside-toplevel

            img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            font = self._load_fallback_font()
            self._draw_fallback_image(draw, font)

            # Сохраняем во временный .ico
            with tempfile.NamedTemporaryFile(
                suffix='.ico', delete=False,
            ) as tmp:
                img.save(tmp, format='ICO')
                self._fallback_icon_path = tmp.name

            hicon = _user32.LoadImageW(
                0, self._fallback_icon_path, 1, 0, 0, 0x00000010,
            )
            if hicon:
                logger.info(
                    'Tray Win32: дефолтная иконка создана (%s)',
                    self._fallback_icon_path,
                )
            return hicon
        except (OSError, AttributeError) as e:
            logger.warning(
                'Tray Win32: ошибка создания дефолтной иконки: %s',
                e,
            )
            return 0

    def _remove_icon(self):
        """Удаляет иконку из трея и очищает temp-файл дефолтной иконки."""
        nid = _NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = self._UID
        _shell32.Shell_NotifyIconW(
            NIM_DELETE, ctypes.byref(nid),
        )
        if self._fallback_icon_path:
            try:
                os.unlink(self._fallback_icon_path)
            except OSError:
                pass
            self._fallback_icon_path = None

        # Удаляем callback из модульного списка после удаления иконки
        if self._wndproc in _KEEP_ALIVE_WNDPROCS:
            _KEEP_ALIVE_WNDPROCS.remove(self._wndproc)

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

    def _poll_popup_flag(self) -> None:
        """
        Tkinter-таймер, проверяющий флаг _pending_popup.

        Вызывается из mainloop каждые 50ms. Если флаг установлен —
        сбрасывает его и вызывает _safe_show_popup.
        Это безопасная альтернатива after(0, ...) из Win32 callback'а,
        которая вызывала SEH-исключение в Tcl/Tk DLL.
        """
        if self._pending_popup:
            self._pending_popup = False
            self._safe_show_popup()
        if not self._shutting_down and self._tk_root is not None:
            try:
                self._popup_timer_id = self._tk_root.after(
                    50, self._poll_popup_flag,
                )
            except (tk.TclError, RuntimeError, OSError):
                # ошибка планирования – игнорируем
                pass

    def _safe_show_popup(self) -> None:
        """
        Безопасная обёртка для _show_popup.

        Ловит ВСЕ исключения — callback не должен крашить
        tkinter mainloop. Даже если _show_popup выбросит
        исключение, которое не поймано — этот метод его поймает.
        """
        # Проверяем флаг вместо winfo_exists() — безопаснее
        if self._popup_open:
            return
        if not self._tk_root_valid:
            return

        self._popup_open = True
        try:
            if self._popup is not None:
                self._popup.dismiss()
            self._show_popup()
        except (tk.TclError, KeyError, TypeError, ValueError,
                OSError, RuntimeError) as e:
            logger.error('Tray Win32: _safe_show_popup — ошибка: '
                         '%s', e, exc_info=True)
        finally:
            self._popup_open = False

    def _show_popup(self):
        """
        Показывает popup-меню в позиции иконки трей.

        Ловит все исключения — callback не должен крашить
        mainloop.
        """
        try:
            rect = self._get_icon_rect()
            if rect:
                x = rect[0]
                y = rect[1] - 8
            else:
                x, y = self._get_cursor_pos()
                y -= 280

            # Передаём tk_root и popup в callbacks для диалогов выбора
            # браузера и индикатора загрузки в статусбаре
            self._callbacks['tk_root'] = self._tk_root
            self._callbacks['popup'] = self._popup
            items = build_menu_items(
                self._callbacks, self._stop, 'Tray Win32',
            )

            if self._tk_root:
                self._popup.show(x=x, y=y, items=items)
                # Устанавливаем popup-окно как foreground.
                # НЕ используем self._hwnd (message-only окно) —
                # SetForegroundWindow на HWND_MESSAGE вызывает краш.
                try:
                    popup_hwnd = self._popup.get_popup_hwnd()
                    if popup_hwnd:
                        hwnd_popup = ctypes.c_void_p(popup_hwnd)
                        _user32.SetForegroundWindow(hwnd_popup)
                        _user32.BringWindowToTop(hwnd_popup)
                except (OSError, AttributeError, tk.TclError, ValueError) as e:
                    logger.debug(
                        'Tray Win32: не удалось установить foreground '
                        'popup-окна: %s', e,
                    )
            else:
                logger.warning('Tray Win32: _show_popup — tk_root is None')
        except (tk.TclError, KeyError, TypeError, ValueError,
                OSError, RuntimeError) as e:
            logger.error(
                '_show_popup: ошибка: %s: %s',
                type(e).__name__, e, exc_info=True,
            )

    def _handle_tray_callback(self, event):
        """Обрабатывает событие трей (правый/левый клик)."""
        # При двойном клике левой кнопкой не открываем popup
        if event == WM_LBUTTONDBLCLK:
            return 0
        # WM_MOUSEMOVE (0x200) — нормальное событие от NOTIFYICON_VERSION_4,
        # возникает при движении мыши над иконкой трея. Игнорируем.
        if event == 0x200:
            return 0
        if event not in (WM_RBUTTONUP, WM_RBUTTONDBLCLK,
                         WM_LBUTTONDBLCLK, WM_LBUTTONUP):
            logger.debug('Tray Win32: _handle_tray_callback: неизвестное событие 0x%X', event)
            return None
        # ВАЖНО: не вызываем self._tk_root.winfo_exists() или любые
        # другие Tcl/Tk функции из Win32 callback'а — это реентерабельный
        # вход в Tcl/Tk интерпретатор, который вызывает SEH-исключение
        # (access violation) на некоторых версиях Windows.
        # Вместо этого используем флаг _tk_root_valid, который
        # устанавливается из mainloop-потока.
        if not self._tk_root_valid:
            logger.warning('Tray Win32: _handle_tray_callback: tk_root невалиден, возврат 0')
            return 0
        # Не открываем popup, если он уже открыт
        if self._popup_open:
            return 0
        # НЕ вызываем SetForegroundWindow на self._hwnd — это message-only
        # окно (HWND_MESSAGE), и SetForegroundWindow на нём вызывает
        # SEH-исключение (access violation) на некоторых версиях Windows.
        # Вместо этого SetForegroundWindow вызывается на самом popup-окне
        # внутри _show_popup, после его создания.
        #
        # НЕ используем after(0, ...) для вызова _safe_show_popup —
        # вызов after() изнутри Win32 callback'а (_wnd_proc) рекурсивно
        # входит в Tcl/Tk интерпретатор, что вызывает SEH-исключение
        # (access violation) в Tcl/Tk DLL.
        # Вместо этого устанавливаем флаг _pending_popup, который
        # проверяется tkinter-таймером _poll_popup_flag() в нормальном
        # контексте mainloop.
        self._pending_popup = True
        return 0

    def _handle_wm_destroy(self):
        """Обрабатывает WM_DESTROY."""
        if self._shutting_down:
            try:
                self._remove_icon()
            except (OSError, RuntimeError) as e:
                logger.error(
                    'Tray Win32: ошибка удаления иконки: %s', e,
                )
            _user32.PostQuitMessage(0)
            return 0
        logger.warning(
            'Tray Win32: WM_DESTROY получен без shutdown-флага, '
            'пересоздаю иконку',
        )
        # Пересоздаём иконку — окно было уничтожено внешне
        try:
            self._add_icon()
        except (OSError, RuntimeError) as e:
            logger.error(
                'Tray Win32: не удалось пересоздать иконку: %s',
                e, exc_info=True,
            )
        return 0

    def _handle_taskbar_created(self):
        """Обрабатывает WM_TASKBAR_CREATED — пересоздание иконки."""
        logger.info(
            'Tray Win32: WM_TASKBAR_CREATED — пересоздание иконки',
        )
        try:
            self._add_icon()
        except OSError as e:
            logger.error(
                'Tray Win32: ошибка пересоздания иконки: %s', e,
            )
        return 0

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """
        Обработчик сообщений окна трей.

        Вызывается Windows в контексте потока, создавшего окно.
        НЕ должен пробрасывать исключения — иначе краш mainloop.
        """
        # msg=0x8001 (TRAY_CALLBACK) — нормальные callback-события от иконки
        # трея (движение мыши, ховер). msg=0x24/0x81/0x83/0x1 — стандартные
        # сообщения Windows при создании окна. Не логируем их — только спам.
        if msg not in (TRAY_CALLBACK, 0x24, 0x81, 0x83, 0x1):
            logger.debug('Tray Win32: _wnd_proc: msg=0x%X', msg)
        try:
            if msg == TRAY_CALLBACK:
                result = self._handle_tray_callback(lparam & 0xFFFF)
                if result is not None:
                    return result
            elif msg == WM_DESTROY:
                return self._handle_wm_destroy()
            elif self._taskbar_msg_id and msg == self._taskbar_msg_id:
                return self._handle_taskbar_created()
        except (AttributeError, OSError, tk.TclError,
                RuntimeError) as e:
            logger.error(
                '_wnd_proc: ошибка: %s: %s',
                type(e).__name__, e, exc_info=True,
            )

        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)
