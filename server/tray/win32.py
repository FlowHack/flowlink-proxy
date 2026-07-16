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
_user32 = ctypes.windll.user32  # type: ignore[reportAttributeAccessIssue]
_kernel32 = ctypes.windll.kernel32  # type: ignore[reportAttributeAccessIssue]
_shell32 = ctypes.windll.shell32  # type: ignore[reportAttributeAccessIssue]

WNDPROC = ctypes.WINFUNCTYPE(  # type: ignore[reportAttributeAccessIssue]
    ctypes.c_long, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM,
)


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
        self._hwnd = None
        self._wndproc = None
        self._popup = FlowLinkPopup()
        self._tk_root = None
        self._tk_thread = None
        self._icon_ready = threading.Event()
        self._shutting_down = False
        self._taskbar_msg_id = 0
        self._fallback_icon_path = None

    def start(self):
        """Запускает трей-иконку в отдельном потоке."""
        self._tk_thread = threading.Thread(
            target=self._run_tk, daemon=True,
        )
        self._tk_thread.start()

    def stop(self):
        """Останавливает трей и закрывает окно."""
        self._shutting_down = True
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
            logger.debug('Tray Win32: инициализация tkinter...')
            try:
                self._tk_root = tk.Tk()
            except tk.TclError as e:
                logger.error(
                    'Tray Win32: Tcl/Tk ошибка инициализации: %s. '
                    'Возможно, не найдены библиотеки tcl/tk.', e,
                )
                return
            except RuntimeError as e:
                logger.error(
                    'Tray Win32: Tcl runtime не найден: %s. '
                    'PyInstaller мог не упаковать Tcl/Tk файлы.', e,
                )
                return
            except OSError as e:
                logger.error(
                    'Tray Win32: системная ошибка при создании Tk: %s', e,
                )
                return

            logger.debug('Tray Win32: tkinter создан, withdraw...')
            try:
                self._tk_root.withdraw()
            except tk.TclError as e:
                logger.error(
                    'Tray Win32: ошибка withdraw(): %s', e,
                )
                return

            self._popup.set_tk_root(self._tk_root)

            logger.debug('Tray Win32: создание иконки в трее...')
            try:
                self._create_tray_icon()
            except OSError as e:
                logger.error(
                    'Tray Win32: ошибка создания иконки: %s', e,
                )
                return
            except (ValueError, TypeError) as e:
                logger.error(
                    'Tray Win32: ошибка аргументов при создании '
                    'иконки: %s', e,
                )
                return

            if not self._hwnd:
                logger.error(
                    'Tray Win32: hwnd не установлен после '
                    '_create_tray_icon',
                )
                return

            self._icon_ready.set()
            logger.debug('Tray Win32: запуск mainloop...')

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
        except Exception as e:  # pylint: disable=broad-exception-caught
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
        logger.debug(
            'Tray Win32: WM_TASKBAR_CREATED = %d',
            self._taskbar_msg_id,
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
        _shell32.Shell_NotifyIconW(
            NIM_SETVERSION, ctypes.byref(nid),
        )

    def _create_fallback_icon(self):
        """
        Создаёт дефолтную иконку (красный круг + «FLP») через Pillow.

        Сохраняет .ico во временный файл и загружает через LoadImageW.
        Путь к temp-файлу сохраняется для удаления в _remove_icon().

        Returns:
            HICON или 0 при ошибке.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont  # pylint: disable=import-outside-toplevel
        except ImportError:
            logger.warning(
                'Tray Win32: Pillow недоступен для дефолтной иконки',
            )
            return 0

        try:
            import tempfile  # pylint: disable=import-outside-toplevel

            size = 16
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Красный круг
            draw.ellipse(
                [1, 1, size - 2, size - 2],
                fill=(231, 76, 60, 255),
            )

            # Текст «FLP»
            try:
                font = ImageFont.truetype('arial.ttf', 7)
            except OSError:
                try:
                    font = ImageFont.truetype(
                        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                        7,
                    )
                except OSError:
                    font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), 'FLP', font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (size - tw) // 2
            ty = (size - th) // 2 - 1
            draw.text((tx, ty), 'FLP', fill=(0, 0, 0, 255), font=font)

            # Сохраняем во временный .ico
            tmp = tempfile.NamedTemporaryFile(
                suffix='.ico', delete=False,
            )
            img.save(tmp, format='ICO')
            tmp.close()
            self._fallback_icon_path = tmp.name

            hicon = _user32.LoadImageW(
                0, tmp.name, 1, 0, 0, 0x00000010,
            )
            if hicon:
                logger.info(
                    'Tray Win32: дефолтная иконка создана (%s)',
                    tmp.name,
                )
            return hicon
        except Exception as e:  # pylint: disable=broad-exception-caught
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
                logger.debug(
                    'Tray Win32: удалён temp-файл иконки %s',
                    self._fallback_icon_path,
                )
            except OSError:
                pass
            self._fallback_icon_path = None

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

            items = build_menu_items(
                self._callbacks, self.stop, 'Tray Win32',
            )

            if self._tk_root:
                self._popup.show(x=x, y=y, items=items)
        except tk.TclError as e:
            logger.warning(
                'Tray Win32: ошибка tkinter в _show_popup: %s', e,
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(
                'Tray Win32: ошибка данных меню: %s', e,
            )
        except OSError as e:
            logger.error(
                'Tray Win32: системная ошибка в _show_popup: %s', e,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                'Tray Win32: непредвиденная ошибка в _show_popup: %s',
                e, exc_info=True,
            )

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """
        Обработчик сообщений окна трей.

        Вызывается Windows в контексте потока, создавшего окно.
        НЕ должен пробрасывать исключения — иначе краш mainloop.
        """
        try:
            if msg == TRAY_CALLBACK:
                event = lparam & 0xFFFF
                if event in (WM_RBUTTONUP, WM_LBUTTONDBLCLK):
                    self._tk_root.after(0, self._show_popup)  # type: ignore[reportOptionalMemberAccess]
                    return 0
                if event == WM_LBUTTONUP:
                    self._tk_root.after(0, self._show_popup)  # type: ignore[reportOptionalMemberAccess]
                    return 0
            elif msg == WM_DESTROY:
                if self._shutting_down:
                    logger.debug(
                        'Tray Win32: WM_DESTROY (shutdown), '
                        'удаление иконки',
                    )
                    self._remove_icon()
                    _user32.PostQuitMessage(0)
                    return 0
                logger.warning(
                    'Tray Win32: WM_DESTROY получен без '
                    'shutdown-флага, игнорируется',
                )
                return 0
            elif self._taskbar_msg_id and msg == self._taskbar_msg_id:
                logger.info(
                    'Tray Win32: WM_TASKBAR_CREATED — '
                    'пересоздание иконки',
                )
                try:
                    self._add_icon()
                except OSError as e:
                    logger.error(
                        'Tray Win32: ошибка пересоздания '
                        'иконки: %s', e,
                    )
                return 0
        except AttributeError as e:
            logger.error(
                'Tray Win32: _wnd_proc — атрибут не найден: %s', e,
            )
        except RuntimeError as e:
            logger.error(
                'Tray Win32: _wnd_proc — runtime ошибка: %s', e,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                'Tray Win32: _wnd_proc — непредвиденная ошибка: %s',
                e, exc_info=True,
            )

        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)
