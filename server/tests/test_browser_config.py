"""
Тесты модуля browser_config.py — обнаружение и запуск браузера.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from server.config.browser_config import (auto_detect_browsers,
                                          get_browser_config, get_browser_path,
                                          launch_browser, save_browser_path,
                                          validate_browser_path,
                                          validate_browser_path_detailed)


class _TempSettingsMixin(unittest.TestCase):
    """
    Миксин: setUp/tearDown + подмена SETTINGS_FILE через mock.patch.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_settings(self, content=''):
        """Подменяет SETTINGS_FILE на тестовый файл."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        self._patcher = patch(
            'server.config.autostart.SETTINGS_FILE', path,
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)
        return path


class TestAutoDetectBrowsers(unittest.TestCase):
    """Тесты автопоиска браузеров."""

    def test_returns_list(self):
        """Возвращает список."""
        result = auto_detect_browsers()
        self.assertIsInstance(result, list)

    def test_each_item_has_name_and_path(self):
        """Каждый элемент содержит name и path."""
        result = auto_detect_browsers()
        for item in result:
            self.assertIn('name', item)
            self.assertIn('path', item)
            self.assertIsInstance(item['name'], str)
            self.assertIsInstance(item['path'], str)


class TestValidateBrowserPath(unittest.TestCase):
    """Тесты валидации пути к браузеру."""

    def test_empty_path_invalid(self):
        """Пустой путь невалиден."""
        self.assertFalse(validate_browser_path(''))

    def test_none_invalid(self):
        """None невалиден."""
        # type: ignore[reportArgumentType] — намеренно передаём None для проверки валидации
        self.assertFalse(validate_browser_path(None))  # type: ignore[reportArgumentType]

    def test_nonexistent_file_invalid(self):
        """Несуществующий файл невалиден."""
        self.assertFalse(validate_browser_path('/nonexistent/browser'))

    def test_existing_file_valid(self):
        """Существующий файл валиден."""
        with tempfile.NamedTemporaryFile() as f:
            self.assertTrue(validate_browser_path(f.name))


class TestValidateBrowserPathDetailed(unittest.TestCase):
    """Тесты расширенной валидации пути к браузеру."""

    def test_empty_path(self):
        """Пустой путь — невалидно."""
        result = validate_browser_path_detailed('')
        self.assertFalse(result['valid'])
        self.assertIn('пуст', result['error'])

    def test_none_path(self):
        """None — невалидно."""
        # type: ignore[reportArgumentType] — намеренно передаём None для проверки валидации
        result = validate_browser_path_detailed(None)  # type: ignore[reportArgumentType]
        self.assertFalse(result['valid'])

    def test_whitespace_only(self):
        """Только пробелы — невалидно."""
        result = validate_browser_path_detailed('   ')
        self.assertFalse(result['valid'])

    def test_nonexistent_file(self):
        """Несуществующий файл — невалидно."""
        result = validate_browser_path_detailed('/nonexistent/browser')
        self.assertFalse(result['valid'])
        self.assertIn('не найден', result['error'])

    def test_directory_path(self):
        """Путь к директории — невалидно."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_browser_path_detailed(tmpdir)
            self.assertFalse(result['valid'])
            self.assertIn('директории', result['error'])

    def test_non_executable_extension(self):
        """Файл с расширением .txt — невалидно."""
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            result = validate_browser_path_detailed(f.name)
            self.assertFalse(result['valid'])
            self.assertIn('расширением', result['error'])

    def test_image_extension(self):
        """Файл .png — невалидно."""
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            result = validate_browser_path_detailed(f.name)
            self.assertFalse(result['valid'])

    def test_script_extension(self):
        """Файл .py — невалидно (не браузер)."""
        with tempfile.NamedTemporaryFile(suffix='.py') as f:
            result = validate_browser_path_detailed(f.name)
            self.assertFalse(result['valid'])

    def test_executable_file_valid(self):
        """Исполняемый файл без подозрительного расширения — валидно."""
        with tempfile.NamedTemporaryFile(suffix='.bin') as f:
            os.chmod(f.name, 0o755)
            result = validate_browser_path_detailed(f.name)
            self.assertTrue(result['valid'])
            self.assertIsNone(result['error'])

    def test_returns_warnings_list(self):
        """Возвращает список предупреждений."""
        with tempfile.NamedTemporaryFile(suffix='.bin') as f:
            os.chmod(f.name, 0o755)
            result = validate_browser_path_detailed(f.name)
            self.assertIsInstance(result['warnings'], list)


class TestGetBrowserPath(_TempSettingsMixin):
    """Тесты чтения пути к браузеру."""

    def test_default_empty(self):
        """По умолчанию пустая строка."""
        self._mock_settings()
        self.assertEqual(get_browser_path(), '')

    def test_reads_path(self):
        """Читает путь из файла."""
        self._mock_settings('browser_path=/usr/bin/google-chrome\n')
        self.assertEqual(get_browser_path(), '/usr/bin/google-chrome')


class TestSaveBrowserPath(_TempSettingsMixin):
    """Тесты сохранения пути к браузеру."""

    def test_saves_path(self):
        """Сохраняет путь в файл."""
        self._mock_settings()
        save_browser_path('/usr/bin/chromium')
        self.assertEqual(get_browser_path(), '/usr/bin/chromium')

    def test_preserves_other_keys(self):
        """Сохраняет другие ключи."""
        path = self._mock_settings('autostart_browser=true\n')
        save_browser_path('/usr/bin/chromium')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('autostart_browser=true', content)
        self.assertIn('browser_path=/usr/bin/chromium', content)


class TestGetBrowserConfig(_TempSettingsMixin):
    """Тесты get_browser_config."""

    def test_returns_expected_keys(self):
        """Возвращает ожидаемые ключи."""
        self._mock_settings()
        config = get_browser_config()
        self.assertIn('browserPath', config)
        self.assertIn('autostartBrowser', config)
        self.assertIn('parallelLaunch', config)


class TestLaunchBrowser(unittest.TestCase):
    """Тесты запуска браузера с флагом --proxy-server."""

    @patch('server.config.browser_config.subprocess.Popen')
    @patch('server.config.browser_config.is_browser_running', return_value=False)
    @patch('server.config.browser_config.validate_browser_path', return_value=True)
    def test_launch_basic_proxy_flag(self, _mock_validate, _mock_running,
                                     mock_popen):
        """Базовый запуск: браузер получает --proxy-server=127.0.0.1:8080."""
        result = launch_browser('/usr/bin/chrome')
        self.assertTrue(result)
        kwargs = mock_popen.call_args[1]
        args = kwargs['args']
        self.assertEqual(args[0], '/usr/bin/chrome')
        self.assertEqual(len(args), 2)
        self.assertIn('--proxy-server=127.0.0.1:8080', args)
        # stdout/stderr перенаправляются в DEVNULL
        self.assertEqual(kwargs['stdout'], subprocess.DEVNULL)
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)

    @patch('server.config.browser_config.subprocess.Popen')
    @patch('server.config.browser_config.is_browser_running', return_value=False)
    @patch('server.config.browser_config.validate_browser_path', return_value=True)
    def test_launch_custom_proxy_port(self, _mock_validate, _mock_running,
                                      mock_popen):
        """Кастомный порт прокси попадает в --proxy-server."""
        result = launch_browser('/usr/bin/chrome', proxy_port=9090)
        self.assertTrue(result)
        args = mock_popen.call_args[1]['args']
        self.assertIn('--proxy-server=127.0.0.1:9090', args)

    @patch('server.config.browser_config.subprocess.Popen')
    @patch('server.config.browser_config.validate_browser_path', return_value=False)
    def test_launch_invalid_path(self, _mock_validate, mock_popen):
        """Невалидный путь к браузеру возвращает False, процесс не запускается."""
        result = launch_browser('/nonexistent/browser')
        self.assertFalse(result)
        mock_popen.assert_not_called()

    @patch(
        'server.config.browser_config.subprocess.Popen',
        side_effect=OSError('permission denied'),
    )
    @patch('server.config.browser_config.is_browser_running', return_value=False)
    @patch('server.config.browser_config.validate_browser_path', return_value=True)
    def test_launch_os_error(self, _mock_validate, _mock_running, _mock_popen):
        """Ошибка запуска subprocess возвращает False."""
        result = launch_browser('/usr/bin/chrome')
        self.assertFalse(result)

    @patch('server.config.browser_config.subprocess.Popen')
    @patch('server.config.browser_config.is_browser_running', return_value=False)
    @patch('server.config.browser_config.validate_browser_path', return_value=True)
    def test_launch_has_no_extension_and_cdp_flags(self, _mock_validate,
                                                   _mock_running, mock_popen):
        """В аргументах нет --user-data-dir, --load-extension и CDP-флагов."""
        result = launch_browser('/usr/bin/chrome', proxy_port=8080)
        self.assertTrue(result)
        args = mock_popen.call_args[1]['args']
        self.assertFalse(any('--user-data-dir' in a for a in args))
        self.assertFalse(any('--load-extension' in a for a in args))
        self.assertFalse(any('--disable-extensions-except' in a for a in args))
        self.assertFalse(any('--remote-debugging-port' in a for a in args))
        self.assertFalse(any('--remote-allow-origins' in a for a in args))
        self.assertFalse(any('--no-first-run' in a for a in args))
        self.assertFalse(any('--no-default-browser-check' in a for a in args))

    @patch('server.config.browser_config.subprocess.Popen')
    @patch('server.config.browser_config.is_browser_running', return_value=True)
    @patch('server.config.browser_config.validate_browser_path', return_value=True)
    def test_launch_already_running(self, _mock_validate, _mock_running,
                                    mock_popen):
        """Запущенный браузер: возврат 'already_running', Popen не вызывается."""
        result = launch_browser('/usr/bin/chrome')
        self.assertEqual(result, 'already_running')
        mock_popen.assert_not_called()
