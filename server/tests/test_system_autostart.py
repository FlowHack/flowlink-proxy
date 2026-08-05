"""
Тесты модуля system_autostart.py — автозапуск с системой.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from server.config.system_autostart import (_get_autostart_path,
                                            _get_executable_info,
                                            get_system_autostart_info,
                                            is_system_autostart_enabled,
                                            set_system_autostart_enabled)


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


class _FakeWinreg:  # pylint: disable=invalid-name
    # camelCase-имена методов (OpenKey/SetValueEx/DeleteValue) обязаны
    # совпадать с публичным API реального winreg, который они подменяют.
    """Фейковый winreg: контекстный ключ и запись вызовов SetValueEx/DeleteValue."""

    HKEY_CURRENT_USER = 'HKCU'
    KEY_SET_VALUE = 0x0002
    REG_SZ = 1

    def __init__(self):
        self.set_value_ex = Mock()
        self.delete_value = Mock()

    def OpenKey(self, _key, _subkey, *_args):
        """Открывает ключ реестра — всегда возвращает себя как контекстный ключ."""
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def SetValueEx(self, key, name, reserved, value_type, value):
        """Записывает вызов SetValueEx в mock для последующих проверок."""
        self.set_value_ex(key, name, reserved, value_type, value)

    def DeleteValue(self, key, name):
        """Записывает вызов DeleteValue в mock для последующих проверок."""
        self.delete_value(key, name)


class TestSetSystemAutostartEnabledLinux(unittest.TestCase):
    """set_system_autostart_enabled на Linux (.desktop файл)."""

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('server.config.system_autostart._get_executable_info',
           return_value=('/opt/flowlink/flowlink', ['--daemon']))
    def test_enabled_creates_desktop_with_exec_and_chmod(self, _mock_exe):
        """Включение создаёт .desktop файл с Exec= и правами 755."""
        with tempfile.TemporaryDirectory() as tmpdir:
            desktop_path = os.path.join(tmpdir, 'flowlink-proxy.desktop')
            with patch('server.config.system_autostart.os.path.expanduser',
                       return_value=desktop_path):
                result = set_system_autostart_enabled(True)
            self.assertTrue(result)
            self.assertTrue(os.path.isfile(desktop_path))
            with open(desktop_path, encoding='utf-8') as f:
                content = f.read()
            self.assertIn('Exec="/opt/flowlink/flowlink" --daemon', content)
            self.assertIn('Name=FlowLink Proxy', content)
            mode = os.stat(desktop_path).st_mode & 0o777
            self.assertEqual(mode, 0o755)

    @patch('server.config.system_autostart.sys.platform', 'linux')
    def test_disabled_removes_desktop_file(self):
        """Отключение удаляет существующий .desktop файл."""
        with tempfile.TemporaryDirectory() as tmpdir:
            desktop_path = os.path.join(tmpdir, 'flowlink-proxy.desktop')
            with open(desktop_path, 'w', encoding='utf-8') as f:
                f.write('[Desktop Entry]\n')
            with patch('server.config.system_autostart.os.path.expanduser',
                       return_value=desktop_path):
                result = set_system_autostart_enabled(False)
            self.assertTrue(result)
            self.assertFalse(os.path.exists(desktop_path))

    @patch('server.config.system_autostart.sys.platform', 'linux')
    @patch('server.config.system_autostart.os.makedirs',
           side_effect=OSError('нет места на диске'))
    def test_enabled_oserror_returns_false(self, _mock_makedirs):
        """OSError при записи на Linux → False."""
        with patch('server.config.system_autostart.os.path.expanduser',
                   return_value='/tmp/autostart/flowlink-proxy.desktop'):
            result = set_system_autostart_enabled(True)
        self.assertFalse(result)


class TestSetSystemAutostartEnabledWindows(unittest.TestCase):
    """set_system_autostart_enabled на Windows (реестр winreg)."""

    @patch('server.config.system_autostart.sys.platform', 'win32')
    @patch('server.config.system_autostart._get_executable_info',
           return_value=('C:\\FlowLink\\flowlink.exe', []))
    def test_enabled_calls_set_value_ex(self, _mock_exe):
        """Включение вызывает winreg.SetValueEx с командой запуска."""
        fake = _FakeWinreg()
        with patch.dict('sys.modules', {'winreg': fake}):
            result = set_system_autostart_enabled(True)
        self.assertTrue(result)
        fake.set_value_ex.assert_called_once_with(
            fake, 'FlowLink Proxy', 0, fake.REG_SZ,
            '"C:\\FlowLink\\flowlink.exe"',
        )

    @patch('server.config.system_autostart.sys.platform', 'win32')
    @patch('server.config.system_autostart._get_executable_info',
           return_value=('C:\\FlowLink\\flowlink.exe', []))
    def test_disabled_calls_delete_value(self, _mock_exe):
        """Отключение вызывает winreg.DeleteValue."""
        fake = _FakeWinreg()
        with patch.dict('sys.modules', {'winreg': fake}):
            result = set_system_autostart_enabled(False)
        self.assertTrue(result)
        fake.delete_value.assert_called_once_with(fake, 'FlowLink Proxy')

    @patch('server.config.system_autostart.sys.platform', 'win32')
    def test_windows_oserror_returns_false(self):
        """OSError при работе с реестром → False."""
        class _BrokenWinreg(_FakeWinreg):
            def OpenKey(self, _key, _subkey, *_args):
                raise OSError('доступ запрещён')
        with patch.dict('sys.modules', {'winreg': _BrokenWinreg()}):
            result = set_system_autostart_enabled(True)
        self.assertFalse(result)


class TestSetSystemAutostartEnabledMacos(unittest.TestCase):
    """set_system_autostart_enabled на macOS (launchd plist)."""

    @patch('server.config.system_autostart.sys.platform', 'darwin')
    @patch('server.config.system_autostart._get_executable_info',
           return_value=('/opt/flowlink/flowlink', ['--daemon']))
    def test_enabled_creates_plist_with_program_arguments(self, _mock_exe):
        """Включение создаёт plist с ProgramArguments и RunAtLoad."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plist_path = os.path.join(tmpdir, 'com.flowlink.proxy.plist')
            with patch('server.config.system_autostart.os.path.expanduser',
                       return_value=plist_path):
                result = set_system_autostart_enabled(True)
            self.assertTrue(result)
            self.assertTrue(os.path.isfile(plist_path))
            with open(plist_path, encoding='utf-8') as f:
                content = f.read()
            self.assertIn('<key>ProgramArguments</key>', content)
            self.assertIn('<string>/opt/flowlink/flowlink</string>', content)
            self.assertIn('<string>--daemon</string>', content)
            self.assertIn('<key>RunAtLoad</key>', content)

    @patch('server.config.system_autostart.sys.platform', 'darwin')
    def test_disabled_removes_plist(self):
        """Отключение удаляет существующий plist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plist_path = os.path.join(tmpdir, 'com.flowlink.proxy.plist')
            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0"?>')
            with patch('server.config.system_autostart.os.path.expanduser',
                       return_value=plist_path):
                result = set_system_autostart_enabled(False)
            self.assertTrue(result)
            self.assertFalse(os.path.exists(plist_path))


class TestGetExecutableInfo(unittest.TestCase):
    """Тесты _get_executable_info в frozen и не-frozen режимах."""

    def test_non_frozen_returns_module_args(self):
        """Без sys.frozen возвращает (python, ['-m', 'server'])."""
        exe, args = _get_executable_info()
        self.assertEqual(exe, sys.executable)
        self.assertEqual(args, ['-m', 'server'])

    @patch.object(sys, 'frozen', True, create=True)
    def test_frozen_returns_no_args(self):
        """С sys.frozen возвращает (exe, []) без аргументов."""
        exe, args = _get_executable_info()
        self.assertEqual(exe, sys.executable)
        self.assertEqual(args, [])


class TestGetAutostartPath(unittest.TestCase):
    """Тесты _get_autostart_path для разных платформ."""

    @patch('server.config.system_autostart.sys.platform', 'win32')
    def test_windows_returns_registry_key(self):
        """На win32 возвращает ключ реестра Run."""
        self.assertEqual(
            _get_autostart_path(),
            r'Software\Microsoft\Windows\CurrentVersion\Run',
        )

    @patch('server.config.system_autostart.sys.platform', 'darwin')
    @patch('server.config.system_autostart.os.path.expanduser',
           return_value='/Users/u/Library/LaunchAgents/com.flowlink.proxy.plist')
    def test_macos_returns_launch_agents_plist(self, _mock_expanduser):
        """На darwin возвращает путь к plist в LaunchAgents."""
        self.assertEqual(
            _get_autostart_path(),
            '/Users/u/Library/LaunchAgents/com.flowlink.proxy.plist',
        )


if __name__ == '__main__':
    unittest.main()
