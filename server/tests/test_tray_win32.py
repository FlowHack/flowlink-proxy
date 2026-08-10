# pylint: disable=protected-access  # тест проверяет внутреннюю логику Win32Tray
# pylint: disable=invalid-name  # стандартные имена unittest-хуков setUpModule/tearDownModule
# pylint: disable=too-few-public-methods  # классы-заглушки Win32-структур и моков
"""
Тесты восстановления трей-окна в Win32-бэкенде (server/tray/win32.py).

Тестирует:
- _handle_wm_destroy: пересоздание окна и иконки при WM_DESTROY
  без shutdown-флага (мок RegisterClassW/CreateWindowExW).
- _create_message_window: повторная регистрация класса
  с ERROR_CLASS_ALREADY_EXISTS не считается ошибкой.
- Пропуск пересоздания при невалидном контексте (tk_root разрушен).

Модуль win32.py доступен только на Windows (ctypes.windll,
ctypes.wintypes, ctypes.WINFUNCTYPE). Для запуска тестов на любой
платформе Windows-only API подменяются совместимыми заглушками
ДО импорта модуля.
"""

import ctypes
import sys
import types
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

# Флаг: выполнялась ли подмена Windows-only ctypes API (не-Windows).
_INJECTED = False
# Any: модуль win32.py импортируется в setUpModule; до этого момента
# атрибуты модуля недоступны (pyright не знает тип глобала).
_WIN32_MODULE: Any = None


def _make_fake_wintypes():
    """Создаёт фейковый модуль ctypes.wintypes на реальных ctypes-типах.

    Реальные ctypes-типы обязательны: структуры (_WNDCLASS и т.д.)
    валидируют поля при определении класса, MagicMock не подойдёт.
    """
    # Any: у types.ModuleType нет объявленных атрибутов, а мы динамически
    # задаём типы wintypes (кейс динамических атрибутов ctypes)
    fake: Any = types.ModuleType('ctypes.wintypes')

    class _RECT(ctypes.Structure):
        """Прямоугольник для Shell_NotifyIconGetRect."""
        _fields_ = [
            ('left', ctypes.c_long),
            ('top', ctypes.c_long),
            ('right', ctypes.c_long),
            ('bottom', ctypes.c_long),
        ]

    fake.RECT = _RECT
    fake.HWND = ctypes.c_void_p
    fake.HINSTANCE = ctypes.c_void_p
    fake.HICON = ctypes.c_void_p
    fake.HANDLE = ctypes.c_void_p
    fake.UINT = ctypes.c_uint
    fake.DWORD = ctypes.c_uint
    fake.LONG = ctypes.c_long
    fake.WCHAR = ctypes.c_wchar
    fake.LPCWSTR = ctypes.c_wchar_p
    fake.WPARAM = ctypes.c_size_t
    fake.LPARAM = ctypes.c_ssize_t
    return fake


def setUpModule():
    """Подготавливает окружение и импортирует win32-модуль."""
    # global обязателен: подмена Windows-only ctypes API (wintypes,
    # WINFUNCTYPE, windll) выполняется ДО импорта win32-модуля, чтобы
    # его модульный код (ctypes.windll и т.д.) отработал на любой ОС
    global _INJECTED, _WIN32_MODULE  # pylint: disable=global-statement  # динамическая подмена ctypes до импорта модуля

    if sys.platform != 'win32':
        # ctypes.wintypes и ctypes.WINFUNCTYPE отсутствуют на не-Windows.
        if not hasattr(ctypes, 'wintypes'):
            fake_wintypes = _make_fake_wintypes()
            sys.modules['ctypes.wintypes'] = fake_wintypes
            # type: ignore[reportAttributeAccessIssue] — runtime-атрибут ctypes,
            # существует только на Windows; pyright его не знает
            ctypes.wintypes = fake_wintypes  # type: ignore[reportAttributeAccessIssue]
        if not hasattr(ctypes, 'WINFUNCTYPE'):
            # Достаточно совместимый аналог для определения WNDPROC
            # type: ignore[reportAttributeAccessIssue] — runtime-атрибут ctypes,
            # существует только на Windows; pyright его не знает
            ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE  # type: ignore[reportAttributeAccessIssue]
        # ctypes.windll отсутствует на не-Windows — подменяем моком
        _windll = MagicMock()
        _windll.user32 = MagicMock()
        _windll.kernel32 = MagicMock()
        _windll.shell32 = MagicMock()
        # type: ignore[reportAttributeAccessIssue] — runtime-атрибут ctypes,
        # существует только на Windows; pyright его не знает
        ctypes.windll = _windll  # type: ignore[reportAttributeAccessIssue]
        _INJECTED = True

    from server.tray import win32 as win32_module  # pylint: disable=import-outside-toplevel
    _WIN32_MODULE = win32_module


def tearDownModule():
    """Восстанавливает ctypes после тестов (только при подмене)."""
    if _INJECTED:
        for name in ('windll', 'wintypes', 'WINFUNCTYPE'):
            if hasattr(ctypes, name):
                delattr(ctypes, name)
        sys.modules.pop('ctypes.wintypes', None)


class TestHandleWmDestroy(unittest.TestCase):
    """Тесты пересоздания окна и иконки в _handle_wm_destroy."""

    def setUp(self):
        """Создаёт трей с валидным контекстом и старым hwnd."""
        self.tray = _WIN32_MODULE.Win32Tray(callbacks={})
        # Старое (уничтоженное) окно, от которого пересоздаёмся
        self.tray._hwnd = 5555  # pylint: disable=protected-access  # internal: симуляция старого окна
        self.tray._tk_root = MagicMock()  # pylint: disable=protected-access  # internal: живой mainloop
        self.tray._tk_root_valid = True  # pylint: disable=protected-access  # internal: флаг живости
        self.tray._shutting_down = False  # pylint: disable=protected-access  # internal: без shutdown

    def test_recreates_window_and_icon(self):
        """WM_DESTROY без shutdown-флага пересоздаёт окно и иконку."""
        with patch.object(
            _WIN32_MODULE.Win32Tray, '_create_message_window',
            return_value=9999,
        ) as mock_create, patch.object(
            _WIN32_MODULE.Win32Tray, '_add_icon',
        ) as mock_add, patch.object(
            _WIN32_MODULE, '_shell32',
        ) as mock_shell32:
            result = self.tray._handle_wm_destroy()  # pylint: disable=protected-access  # internal: тестируем обработчик

        self.assertEqual(result, 0)
        # _hwnd обновлён на handle нового окна
        self.assertEqual(self.tray._hwnd, 9999)
        mock_create.assert_called_once()
        mock_add.assert_called_once()
        # «Висячая» иконка старого окна удалена (NIM_DELETE = 2)
        delete_calls = [
            c for c in mock_shell32.Shell_NotifyIconW.call_args_list
            if c.args and c.args[0] == _WIN32_MODULE.NIM_DELETE
        ]
        self.assertTrue(
            delete_calls,
            'NIM_DELETE для старой иконки не был вызван',
        )

    def test_skips_recreation_when_tk_invalid(self):
        """При невалидном tk_root (умирающий поток) пересоздание пропускается."""
        self.tray._tk_root_valid = False  # pylint: disable=protected-access  # internal: симуляция смерти mainloop
        with patch.object(
            _WIN32_MODULE.Win32Tray, '_create_message_window',
        ) as mock_create, patch.object(
            _WIN32_MODULE.Win32Tray, '_add_icon',
        ) as mock_add:
            result = self.tray._handle_wm_destroy()  # pylint: disable=protected-access  # internal: тестируем обработчик

        self.assertEqual(result, 0)
        self.assertEqual(self.tray._hwnd, 5555)
        mock_create.assert_not_called()
        mock_add.assert_not_called()

    def test_shutting_down_removes_icon_and_quits(self):
        """При shutdown-флаге иконка удаляется и отправляется PostQuitMessage."""
        self.tray._shutting_down = True  # pylint: disable=protected-access  # internal: симуляция остановки
        with patch.object(
            _WIN32_MODULE.Win32Tray, '_remove_icon',
        ) as mock_remove, patch.object(
            _WIN32_MODULE, '_user32',
        ) as mock_user32, patch.object(
            _WIN32_MODULE.Win32Tray, '_create_message_window',
        ) as mock_create:
            result = self.tray._handle_wm_destroy()  # pylint: disable=protected-access  # internal: тестируем обработчик

        self.assertEqual(result, 0)
        mock_remove.assert_called_once()
        mock_user32.PostQuitMessage.assert_called_once_with(0)
        mock_create.assert_not_called()


class TestCreateMessageWindow(unittest.TestCase):
    """Тесты _create_message_window: повторная регистрация класса."""

    def setUp(self):
        """Создаёт трей с живым WNDPROC-колбэком."""
        self.tray = _WIN32_MODULE.Win32Tray(callbacks={})
        self.tray._wndproc = _WIN32_MODULE.WNDPROC(  # pylint: disable=protected-access  # internal: колбэк для класса окна
            self.tray._wnd_proc,
        )

    def _patch_winapi(self):
        """Подменяет Win32 API моками для _create_message_window.

        Returns:
            Кортеж (mock_user32, mock_kernel32).
        """
        patcher_user32 = patch.object(_WIN32_MODULE, '_user32')
        patcher_kernel32 = patch.object(_WIN32_MODULE, '_kernel32')
        mock_user32 = patcher_user32.start()
        mock_kernel32 = patcher_kernel32.start()
        self.addCleanup(patcher_user32.stop)
        self.addCleanup(patcher_kernel32.stop)
        return mock_user32, mock_kernel32

    def test_class_already_exists_is_tolerated(self):
        """ERROR_CLASS_ALREADY_EXISTS не считается ошибкой, окно создаётся."""
        mock_user32, mock_kernel32 = self._patch_winapi()
        mock_user32.LoadCursorW.return_value = 0
        mock_kernel32.GetModuleHandleW.return_value = 1000
        # Регистрация класса «не удалась» — класс уже существует
        mock_user32.RegisterClassW.return_value = 0
        mock_kernel32.GetLastError.return_value = (
            _WIN32_MODULE.ERROR_CLASS_ALREADY_EXISTS
        )
        mock_user32.CreateWindowExW.return_value = 4242
        mock_user32.RegisterWindowMessageW.return_value = 0xC000

        hwnd = self.tray._create_message_window()  # pylint: disable=protected-access  # internal: тестируем создание окна

        self.assertEqual(hwnd, 4242)
        self.assertEqual(self.tray._taskbar_msg_id, 0xC000)
        # Окно создаётся даже при повторной регистрации класса
        mock_user32.CreateWindowExW.assert_called_once()

    def test_other_class_error_raises(self):
        """Ошибка RegisterClassW отличная от ALREADY_EXISTS — OSError."""
        mock_user32, mock_kernel32 = self._patch_winapi()
        mock_user32.LoadCursorW.return_value = 0
        mock_kernel32.GetModuleHandleW.return_value = 1000
        mock_user32.RegisterClassW.return_value = 0
        # ERROR_ACCESS_DENIED — любая другая ошибка
        mock_kernel32.GetLastError.return_value = 5

        with self.assertRaises(OSError):
            self.tray._create_message_window()  # pylint: disable=protected-access  # internal: тестируем создание окна

        # Окно не создаётся при фатальной ошибке регистрации класса
        mock_user32.CreateWindowExW.assert_not_called()


if __name__ == '__main__':
    unittest.main()
