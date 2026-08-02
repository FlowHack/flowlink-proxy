"""
Тесты модуля system_autostart.py — автозапуск с системой.
"""

import unittest
from unittest.mock import patch

from server.config.system_autostart import (get_system_autostart_info,
                                            is_system_autostart_enabled)


class TestIsSystemAutostartEnabled(unittest.TestCase):
    """Тесты is_system_autostart_enabled."""

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('os.path.isfile', return_value=True)
    def test_enabled_on_linux(self, _mock_isfile):
        """На Linux наличие .desktop файла включает автозапуск."""
        with patch('server.config.system_autostart.os.path.expanduser',
                   return_value='/tmp/test.desktop'):
            result = is_system_autostart_enabled()
            self.assertTrue(result)

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
        """Возвращает словарь с нужными ключами и корректным значением enabled."""
        result = get_system_autostart_info()
        self.assertIn('enabled', result)
        self.assertIn('platform', result)
        self.assertIn('method', result)
        self.assertIn('path', result)
        self.assertIsInstance(result['enabled'], bool)

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('os.path.isfile', return_value=True)
    def test_returns_dict_enabled_when_desktop_exists(self, _mock_isfile):
        """Наличие .desktop файла отражается в значении enabled=True."""
        with patch('server.config.system_autostart.os.path.expanduser',
                   return_value='/tmp/test.desktop'):
            result = get_system_autostart_info()
            self.assertTrue(result['enabled'])

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('os.path.isfile', return_value=False)
    def test_returns_dict_disabled_when_no_desktop(self, _mock_isfile):
        """Отсутствие .desktop файла отражается в значении enabled=False."""
        with patch('server.config.system_autostart.os.path.expanduser',
                   return_value='/tmp/nonexistent.desktop'):
            result = get_system_autostart_info()
            self.assertFalse(result['enabled'])

    @patch('server.config.system_autostart.sys.platform', 'linux')
    def test_platform_linux(self, ):
        """На Linux платформа — linux."""
        result = get_system_autostart_info()
        self.assertEqual(result['platform'], 'linux')


if __name__ == '__main__':
    unittest.main()
