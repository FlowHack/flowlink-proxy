"""
Тесты общих утилит FlowLink Proxy.

Тестирует: get_data_dir, clear_all_data, write_port_file, _validate_port.
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from server.utils import (
    _validate_port,
    clear_all_data,
    clear_data_only,
    clear_logs_only,
    ensure_extension_dir,
    get_crx_path,
    get_data_dir,
    get_extension_dir,
    write_port_file,
)


class TestGetDataDirEnvVar(unittest.TestCase):
    """Тесты get_data_dir с переменной окружения FLOWLINK_DATA_DIR."""

    @patch.dict(os.environ, {'FLOWLINK_DATA_DIR': '/tmp/test-flowlink-data'})
    @patch('os.makedirs')
    def test_env_var_takes_priority(self, _mock_makedirs):
        """FLOWLINK_DATA_DIR имеет приоритет над другими источниками."""
        result = get_data_dir()
        self.assertEqual(result, '/tmp/test-flowlink-data')
        _mock_makedirs.assert_called_once_with(
            '/tmp/test-flowlink-data', exist_ok=True,
        )

    @patch.dict(os.environ, {'FLOWLINK_DATA_DIR': '/tmp/test-data'})
    @patch('os.makedirs')
    def test_env_var_relative_path_resolved(self, _mock_makedirs):
        """Относительный путь в env var преобразуется в абсолютный."""
        result = get_data_dir()
        self.assertTrue(os.path.isabs(result))


class TestGetDataDirPlatform(unittest.TestCase):
    """Тесты get_data_dir для разных платформ."""

    @patch.dict(os.environ, {}, clear=True)
    @patch('os.makedirs')
    @patch('server.utils.sys')
    def test_linux_uses_home(self, mock_sys, _mock_makedirs):
        """На Linux/macOS используется $HOME/.FlowHack/FlowLink Proxy."""
        mock_sys.platform = 'linux'
        mock_sys.frozen = False
        result = get_data_dir()
        home = os.path.expanduser('~')
        self.assertEqual(
            result, os.path.join(home, '.FlowHack', 'FlowLink Proxy'),
        )

    @patch.dict(os.environ, {}, clear=True)
    @patch('os.makedirs')
    @patch('server.utils.sys')
    def test_macos_uses_home(self, mock_sys, _mock_makedirs):
        """На macOS используется $HOME/.FlowHack/FlowLink Proxy."""
        mock_sys.platform = 'darwin'
        mock_sys.frozen = False
        result = get_data_dir()
        home = os.path.expanduser('~')
        self.assertEqual(
            result, os.path.join(home, '.FlowHack', 'FlowLink Proxy'),
        )

    @patch.dict(os.environ, {'APPDATA': 'C:\\Users\\test\\AppData\\Roaming'})
    @patch('os.makedirs')
    @patch('server.utils.sys')
    def test_windows_uses_appdata(self, mock_sys, _mock_makedirs):
        """На Windows используется %APPDATA%\\FlowHack\\FlowLink Proxy."""
        mock_sys.platform = 'win32'
        mock_sys.frozen = False
        result = get_data_dir()
        expected = os.path.join(
            'C:\\Users\\test\\AppData\\Roaming',
            'FlowHack', 'FlowLink Proxy',
        )
        self.assertEqual(result, expected)

    @patch.dict(os.environ, {}, clear=True)
    @patch('os.makedirs')
    @patch('server.utils.sys')
    def test_windows_no_appdata_fallback(self, mock_sys, _mock_makedirs):
        """На Windows без APPDATA — fallback на $HOME/.FlowHack/FlowLink Proxy."""
        mock_sys.platform = 'win32'
        mock_sys.frozen = False
        result = get_data_dir()
        home = os.path.expanduser('~')
        self.assertEqual(
            result, os.path.join(home, '.FlowHack', 'FlowLink Proxy'),
        )


class TestGetDataDirCreatesDir(unittest.TestCase):
    """Тесты создания директории в get_data_dir."""

    def test_creates_directory_if_not_exists(self):
        """get_data_dir создаёт директорию, если она не существует."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, 'new-data-dir')
            with patch.dict(
                os.environ, {'FLOWLINK_DATA_DIR': test_dir},
            ):
                result = get_data_dir()
                self.assertEqual(result, test_dir)
                self.assertTrue(os.path.isdir(test_dir))

    def test_existing_directory_not_removed(self):
        """get_data_dir не удаляет существующую директорию."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.txt')
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write('test')
            with patch.dict(
                os.environ, {'FLOWLINK_DATA_DIR': tmpdir},
            ):
                get_data_dir()
                self.assertTrue(os.path.isfile(test_file))


class TestClearAllData(unittest.TestCase):
    """Тесты clear_all_data."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_removes_known_files(self):
        """Удаляет все известные файлы данных."""
        files = [
            'config.json', '.flowlink.key', '.flowlink.salt',
            '.flowlink-settings', '.flowlink-port',
        ]
        for filename in files:
            filepath = os.path.join(self.tmpdir, filename)
            with open(filepath, 'w', encoding='utf-8') as fh:
                fh.write('test')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_all_data()

        self.assertEqual(removed, 5)  # 5 файлов (logs/ не было)
        for filename in files:
            self.assertFalse(
                os.path.exists(os.path.join(self.tmpdir, filename)),
            )

    def test_removes_logs_directory(self):
        """Удаляет содержимое директории logs/ и пересоздаёт пустую."""
        logs_dir = os.path.join(self.tmpdir, 'logs')
        os.makedirs(logs_dir)
        log_path = os.path.join(logs_dir, 'FlowLink Proxy.log')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('log data')
        old_log_path = os.path.join(logs_dir, 'FlowLink Proxy.log.1')
        with open(old_log_path, 'w', encoding='utf-8') as f:
            f.write('old log')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_all_data()

        self.assertTrue(removed >= 1)
        # Содержимое удалено, но директория пересоздана пустой
        self.assertTrue(os.path.isdir(logs_dir))
        self.assertEqual(os.listdir(logs_dir), [])

    def test_recreates_logs_directory(self):
        """Пересоздаёт пустую директорию logs/ после удаления."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            clear_all_data()

        logs_dir = os.path.join(self.tmpdir, 'logs')
        self.assertTrue(os.path.isdir(logs_dir))

    def test_returns_zero_when_empty(self):
        """Возвращает 0 если файлов данных нет."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_all_data()

        self.assertEqual(removed, 0)

    def test_preserves_unknown_files(self):
        """Не удаляет файлы, не входящие в список данных."""
        unknown = os.path.join(self.tmpdir, 'my-custom-file.txt')
        with open(unknown, 'w', encoding='utf-8') as f:
            f.write('keep me')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            clear_all_data()

        self.assertTrue(os.path.isfile(unknown))


class TestClearLogsOnly(unittest.TestCase):
    """Тесты clear_logs_only."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_removes_only_logs(self):
        """Удаляет только директорию logs/."""
        logs_dir = os.path.join(self.tmpdir, 'logs')
        os.makedirs(logs_dir)
        log_path = os.path.join(logs_dir, 'test.log')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('log data')

        config_path = os.path.join(self.tmpdir, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('{}')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_logs_only()

        self.assertEqual(removed, 1)
        # Логи удалены, конфиг остался
        self.assertFalse(os.path.exists(log_path))
        self.assertTrue(os.path.isfile(config_path))

    def test_recreates_empty_logs_dir(self):
        """Пересоздаёт пустую директорию logs/."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            clear_logs_only()

        logs_dir = os.path.join(self.tmpdir, 'logs')
        self.assertTrue(os.path.isdir(logs_dir))

    def test_returns_zero_when_no_logs(self):
        """Возвращает 0 если директории logs/ нет."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_logs_only()

        self.assertEqual(removed, 0)


class TestClearDataOnly(unittest.TestCase):
    """Тесты clear_data_only."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_removes_data_files(self):
        """Удаляет файлы данных."""
        files = [
            'config.json', '.flowlink.key', '.flowlink.salt',
            '.flowlink-settings', '.flowlink-port',
        ]
        for filename in files:
            filepath = os.path.join(self.tmpdir, filename)
            with open(filepath, 'w', encoding='utf-8') as fh:
                fh.write('test')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_data_only()

        self.assertEqual(removed, 5)
        for filename in files:
            self.assertFalse(
                os.path.exists(os.path.join(self.tmpdir, filename)),
            )

    def test_preserves_logs(self):
        """Не удаляет директорию logs/."""
        logs_dir = os.path.join(self.tmpdir, 'logs')
        os.makedirs(logs_dir)
        log_path = os.path.join(logs_dir, 'test.log')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('log data')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            clear_data_only()

        self.assertTrue(os.path.isfile(log_path))

    def test_returns_zero_when_empty(self):
        """Возвращает 0 если файлов данных нет."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_data_only()

        self.assertEqual(removed, 0)

    def test_preserves_unknown_files(self):
        """Не удаляет файлы, не входящие в список данных."""
        unknown = os.path.join(self.tmpdir, 'my-custom.txt')
        with open(unknown, 'w', encoding='utf-8') as f:
            f.write('keep me')

        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            clear_data_only()

        self.assertTrue(os.path.isfile(unknown))


class TestValidatePort(unittest.TestCase):
    """Тесты _validate_port."""

    def test_valid_port(self):
        """Валидный порт проходит проверку."""
        self.assertEqual(_validate_port(8080, 'test'), 8080)

    def test_port_min_boundary(self):
        """Порт 1 (минимум) проходит проверку."""
        self.assertEqual(_validate_port(1, 'test'), 1)

    def test_port_max_boundary(self):
        """Порт 65535 (максимум) проходит проверку."""
        self.assertEqual(_validate_port(65535, 'test'), 65535)

    def test_port_zero_raises(self):
        """Порт 0 вызывает ValueError."""
        with self.assertRaises(ValueError):
            _validate_port(0, 'test')

    def test_port_negative_raises(self):
        """Отрицательный порт вызывает ValueError."""
        with self.assertRaises(ValueError):
            _validate_port(-1, 'test')

    def test_port_too_large_raises(self):
        """Порт > 65535 вызывает ValueError."""
        with self.assertRaises(ValueError):
            _validate_port(70000, 'test')

    def test_non_int_raises_type_error(self):
        """Не-int порт вызывает TypeError."""
        with self.assertRaises(TypeError):
            _validate_port('8080', 'test')

    def test_none_raises_type_error(self):
        """None порт вызывает TypeError."""
        with self.assertRaises(TypeError):
            _validate_port(None, 'test')


class TestWritePortFile(unittest.TestCase):
    """Тесты write_port_file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_port_file(self):
        """Записывает JSON-файл с портами."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            write_port_file(8081, 8080)

        port_file = os.path.join(self.tmpdir, '.flowlink-port')
        self.assertTrue(os.path.isfile(port_file))
        with open(port_file, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['api_port'], 8081)
        self.assertEqual(data['proxy_port'], 8080)

    def test_invalid_port_raises(self):
        """Невалидный порт вызывает ValueError."""
        with self.assertRaises(ValueError):
            write_port_file(70000, 8080)

    def test_non_int_port_raises(self):
        """Не-int порт вызывает TypeError."""
        with self.assertRaises(TypeError):
            write_port_file('8081', 8080)  # type: ignore[reportArgumentType]


class TestEnsureExtensionDir(unittest.TestCase):
    """Тесты ensure_extension_dir — стабильная копия расширения в data-директории."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def _make_source(self):
        """Создаёт исходную папку расширения с manifest.json."""
        src = os.path.join(self.tmpdir, 'src-extension')
        os.makedirs(os.path.join(src, 'subdir'), exist_ok=True)
        with open(os.path.join(src, 'manifest.json'), 'w', encoding='utf-8') as f:
            f.write('{}')
        with open(os.path.join(src, 'subdir', 'file.js'), 'w', encoding='utf-8') as f:
            f.write('// test')
        return src

    @patch('server.utils.get_extension_dir')
    def test_copies_source_to_data_dir(self, mock_get_extension_dir):
        """Копирует содержимое источника в <data_dir>/extension."""
        src = self._make_source()
        mock_get_extension_dir.return_value = src

        with patch.dict(os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir}):
            result = ensure_extension_dir()

        expected = os.path.join(self.tmpdir, 'extension')
        self.assertEqual(result, expected)
        self.assertTrue(os.path.isfile(os.path.join(expected, 'manifest.json')))
        self.assertTrue(os.path.isfile(os.path.join(expected, 'subdir', 'file.js')))

    @patch('server.utils.get_extension_dir', return_value=None)
    def test_returns_none_when_source_missing(self, _mock_get_extension_dir):
        """Если источник не найден — возвращается None."""
        with patch.dict(os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir}):
            result = ensure_extension_dir()
        self.assertIsNone(result)
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, 'extension')))

    @patch('server.utils.shutil.copytree', side_effect=OSError('disk full'))
    @patch('server.utils.get_extension_dir')
    def test_returns_none_on_copy_error(self, mock_get_extension_dir, _mock_copytree):
        """При ошибке копирования возвращается None."""
        src = self._make_source()
        mock_get_extension_dir.return_value = src

        with patch.dict(os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir}):
            result = ensure_extension_dir()
        self.assertIsNone(result)


class TestGetCrxPath(unittest.TestCase):
    """Тесты get_crx_path — приоритет стабильной копии расширения."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    @patch('server.utils.ensure_extension_dir')
    def test_stable_copy_has_priority(self, mock_ensure):
        """Стабильная копия из ensure_extension_dir имеет приоритет."""
        stable = os.path.join(self.tmpdir, 'extension')
        mock_ensure.return_value = stable
        self.assertEqual(get_crx_path(), stable)

    @patch('server.utils.ensure_extension_dir', return_value=None)
    @patch('server.utils.os.path.isfile', return_value=True)
    def test_falls_back_to_crx_when_no_copy(self, _mock_isfile, _mock_ensure):
        """Без стабильной копии ищется CRX-файл."""
        with patch.dict(os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir}):
            result = get_crx_path()
        assert result is not None
        self.assertTrue(result.endswith('.crx'))

    @patch('server.utils.ensure_extension_dir', return_value=None)
    @patch('server.utils.os.path.isfile', return_value=False)
    def test_returns_none_when_nothing_found(self, _mock_isfile, _mock_ensure):
        """Ничего не найдено — возвращается None."""
        with patch.dict(os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir}):
            result = get_crx_path()
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
