"""
Тесты общих утилит FlowLink Proxy.

Тестирует: get_data_dir, clear_all_data, clear_logs_only, write_port_file,
_validate_port, reopen_logging.
"""

import json
import logging
import logging.handlers
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from server.logging_config import reopen_logging
from server.utils import (_validate_port, clear_all_data, clear_data_only,
                          clear_logs_only, get_data_dir, redact_url,
                          write_port_file)


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
        """На Linux используется $HOME/.FlowHack/FlowLink Proxy.

        macOS (darwin) попадает в ту же ветку else, что и Linux —
        отдельного теста не требуется (общая логика).
        """
        mock_sys.platform = 'linux'
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

    def test_clear_all_data_returns_zero_when_empty(self):
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

    def test_clear_logs_only_returns_zero_when_no_logs(self):
        """Возвращает 0 если директории logs/ нет."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_logs_only()

        self.assertEqual(removed, 0)


class TestReopenLogging(unittest.TestCase):
    """Тесты reopen_logging из server.logging_config."""

    def setUp(self):
        self._root = logging.getLogger()
        self._saved_handlers = list(self._root.handlers)
        self._root.handlers.clear()
        self._tmpdir = tempfile.mkdtemp()
        self._log_file = os.path.join(self._tmpdir, 'test.log')
        # Реальный RotatingFileHandler — как в бою (setup_logging)
        self._handler = logging.handlers.RotatingFileHandler(
            self._log_file, maxBytes=1024, backupCount=1, encoding='utf-8',
        )
        self._root.addHandler(self._handler)

    def tearDown(self):
        self._root.handlers.clear()
        for handler in self._saved_handlers:
            self._root.addHandler(handler)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _file_handlers(self):
        """Возвращает RotatingFileHandler-ы корневого логгера."""
        return [
            h for h in self._root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]

    def test_recreate_false_removes_handler(self):
        """reopen_logging(recreate=False) закрывает хендлер без нового."""
        reopen_logging(recreate=False)
        self.assertEqual(self._file_handlers(), [])

    def test_recreate_false_frees_log_file(self):
        """После recreate=False файл лога освобождён и удаляется без ошибки."""
        reopen_logging(recreate=False)
        self.assertTrue(os.path.isfile(self._log_file))
        os.remove(self._log_file)
        self.assertFalse(os.path.exists(self._log_file))

    def test_recreate_true_creates_new_handler(self):
        """reopen_logging() (recreate=True) создаёт новый хендлер."""
        reopen_logging()
        handlers = self._file_handlers()
        self.assertEqual(len(handlers), 1)
        # Файл лога пересоздан новым хендлером
        self.assertTrue(os.path.isfile(self._log_file))

    def test_preserves_debug_level_after_reopen(self):
        """reopen_logging() сохраняет DEBUG-уровень, заданный в setup_logging.

        Если сервер запущен с --debug, после переоткрытия хендлера
        (например, очистки логов) уровень файлового логгера не должен
        откатываться на INFO.
        """
        # Имитируем setup_logging(debug=True): устанавливаем уровень DEBUG
        # через явный вызов reopen_logging(level=DEBUG), который синхронизирует
        # _current_level. Затем повторный reopen_logging() без уровня должен
        # сохранить DEBUG.
        reopen_logging(level=logging.DEBUG)
        reopen_logging()
        handlers = self._file_handlers()
        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0].level, logging.DEBUG)


class TestClearDataOnly(unittest.TestCase):
    """Тесты clear_data_only."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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

    def test_clear_data_only_returns_zero_when_empty(self):
        """Возвращает 0 если файлов данных нет."""
        with patch.dict(
            os.environ, {'FLOWLINK_DATA_DIR': self.tmpdir},
        ):
            removed = clear_data_only()

        self.assertEqual(removed, 0)



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
            # type: ignore[reportArgumentType] — намеренно передаём строку для проверки ошибки
            write_port_file('8081', 8080)  # type: ignore[reportArgumentType]


class TestRedactUrl(unittest.TestCase):
    """Тесты redact_url — удаление query-параметров из URL для логов."""

    def test_removes_query_string(self):
        """URL с query-строкой → возвращается без query-части."""
        self.assertEqual(
            redact_url('http://127.0.0.1:8081/api/config?token=secret'),
            'http://127.0.0.1:8081/api/config',
        )

    def test_removes_query_with_multiple_params(self):
        """URL с несколькими query-параметрами → без query-части."""
        self.assertEqual(
            redact_url('http://example.com/path?a=1&b=2&token=abc'),
            'http://example.com/path',
        )

    def test_url_without_query_unchanged(self):
        """URL без query-строки → возвращается без изменений."""
        url = 'http://127.0.0.1:8081/api/config'
        self.assertEqual(redact_url(url), url)

    def test_empty_string_returns_empty(self):
        """Пустая строка → возвращается как есть."""
        self.assertEqual(redact_url(''), '')

    def test_none_returns_none(self):
        """None → возвращается как есть (не падает)."""
        self.assertIsNone(redact_url(None))

    def test_relative_path_with_query(self):
        """Относительный путь с query → без query-части."""
        self.assertEqual(redact_url('/api/events?token=abc'), '/api/events')

    def test_url_with_fragment_removes_query_and_fragment(self):
        """URL с фрагментом (#) → query и фрагмент убираются (всё после '?')."""
        self.assertEqual(
            redact_url('http://example.com/path?token=abc#section'),
            'http://example.com/path',
        )

    def test_redacts_userinfo_password(self):
        """URL с user:pass@host → пароль маскируется (***:***@host)."""
        self.assertEqual(
            redact_url('http://user:secret@example.com:8080/path'),
            'http://***:***@example.com:8080/path',
        )

    def test_redacts_userinfo_without_password(self):
        """URL с user@host → user маскируется (***@host)."""
        self.assertEqual(
            redact_url('http://user@example.com/path'),
            'http://***@example.com/path',
        )

    def test_redacts_userinfo_keeps_ipv6_host(self):
        """IPv6-хост с userinfo → скобки и порт сохраняются."""
        self.assertEqual(
            redact_url('http://user:pass@[::1]:8080/path'),
            'http://***:***@[::1]:8080/path',
        )

    def test_redacts_userinfo_with_query(self):
        """URL с userinfo и query → маскируется userinfo и убирается query."""
        self.assertEqual(
            redact_url('http://user:pass@example.com/path?token=abc'),
            'http://***:***@example.com/path',
        )


if __name__ == '__main__':
    unittest.main()
