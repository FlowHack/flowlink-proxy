"""
Тесты модуля tray/platform.py.

Тестирует: is_windows, is_linux, is_macos, has_pystray, has_pil,
has_tkinter, get_backend_info.
"""

import sys
import unittest
from unittest.mock import patch

from server.tray.platform import (get_backend_info, has_pil, has_pystray,
                                  has_tkinter, is_linux, is_macos, is_windows)


class TestIsPlatform(unittest.TestCase):
    """Тесты определения платформы через sys.platform."""

    @patch.object(sys, 'platform', 'win32')
    def test_windows(self):
        """is_windows возвращает True на Windows."""
        self.assertTrue(is_windows())

    @patch.object(sys, 'platform', 'linux')
    def test_linux(self):
        """is_linux возвращает True на Linux."""
        self.assertTrue(is_linux())

    @patch.object(sys, 'platform', 'darwin')
    def test_macos(self):
        """is_macos возвращает True на macOS."""
        self.assertTrue(is_macos())

    @patch.object(sys, 'platform', 'linux')
    def test_windows_false_on_linux(self):
        """is_windows возвращает False на Linux."""
        self.assertFalse(is_windows())

    @patch.object(sys, 'platform', 'win32')
    def test_linux_false_on_windows(self):
        """is_linux возвращает False на Windows."""
        self.assertFalse(is_linux())

    @patch.object(sys, 'platform', 'linux')
    def test_macos_false_on_linux(self):
        """is_macos возвращает False на Linux."""
        self.assertFalse(is_macos())


class TestHasModules(unittest.TestCase):
    """Тесты проверки доступности модулей."""

    @unittest.skipUnless(
        has_tkinter(), 'tkinter не установлен на этой платформе',
    )
    def test_has_tkinter_true(self):
        """has_tkinter возвращает True если tkinter доступен."""
        self.assertTrue(has_tkinter())

    def test_has_pystray_returns_bool(self):
        """has_pystray возвращает bool."""
        result = has_pystray()
        self.assertIsInstance(result, bool)

    def test_has_pil_returns_bool(self):
        """has_pil возвращает bool."""
        result = has_pil()
        self.assertIsInstance(result, bool)

    @patch('builtins.__import__', side_effect=ImportError)
    def test_has_tkinter_false_when_import_fails(self, _mock_import):
        """has_tkinter возвращает False при ошибке импорта."""
        self.assertFalse(has_tkinter())


class TestGetBackendInfo(unittest.TestCase):
    """Тесты get_backend_info."""

    @patch.object(sys, 'platform', 'linux')
    def test_keys(self):
        """get_backend_info возвращает все ожидаемые ключи."""
        info = get_backend_info()
        expected_keys = {
            'platform', 'is_windows', 'is_linux', 'is_macos',
            'has_pystray', 'has_pil', 'has_tkinter',
        }
        self.assertEqual(set(info.keys()), expected_keys)

    @patch.object(sys, 'platform', 'linux')
    def test_platform_value(self):
        """get_backend_info содержит текущую платформу."""
        info = get_backend_info()
        self.assertEqual(info['platform'], 'linux')
        self.assertTrue(info['is_linux'])
        self.assertFalse(info['is_windows'])
        self.assertFalse(info['is_macos'])

    @patch.object(sys, 'platform', 'linux')
    def test_has_tkinter_always_present(self):
        """get_backend_info содержит has_tkinter."""
        info = get_backend_info()
        self.assertIn('has_tkinter', info)
        self.assertIsInstance(info['has_tkinter'], bool)


if __name__ == '__main__':
    unittest.main()
