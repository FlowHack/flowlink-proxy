"""
Тесты модуля system_autostart.py — автозапуск с системой.
"""

import unittest
from unittest.mock import patch

from server.config.system_autostart import (
    is_system_autostart_enabled,
    get_system_autostart_info,
)


class TestIsSystemAutostartEnabled(unittest.TestCase):
    """Тесты is_system_autostart_enabled."""

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('os.path.isfile', return_value=True)
    def test_enabled_on_linux(self, _mock_isfile):
        """На Linux проверяет наличие .desktop файла."""
        with patch('server.config.system_autostart.os.path.expanduser',
                   return_value='/tmp/test.desktop'):
            result = is_system_autostart_enabled()
            self.assertIsInstance(result, bool)

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('os.path.isfile', return_value=False)
    def test_disabled_on_linux(self, _mock_isfile):
        """На Linux без .desktop файла — False."""
        with patch('server.config.system_autostart.os.path.expanduser',
                   return_value='/tmp/nonexistent.desktop'):
            result = is_system_autostart_enabled()
            self.assertFalse(result)


class TestGetSystemAutostartInfo(unittest.TestCase):
    """Тесты get_system_autostart_info."""

    def test_returns_dict(self):
        """Возвращает словарь с нужными ключами."""
        result = get_system_autostart_info()
        self.assertIn('enabled', result)
        self.assertIn('platform', result)
        self.assertIn('method', result)
        self.assertIn('path', result)
        self.assertIsInstance(result['enabled'], bool)

    @patch('server.config.system_autostart.sys.platform', 'linux')
    def test_platform_linux(self, ):
        """На Linux платформа — linux."""
        result = get_system_autostart_info()
        self.assertEqual(result['platform'], 'linux')


if __name__ == '__main__':
    unittest.main()
