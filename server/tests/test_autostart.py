"""
Тесты модуля autostart.py — управление автозапуском браузера.
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from server.config.autostart import (
    _parse_settings,
    _format_settings,
    SETTINGS_FILE,
    get_autostart_browser,
    set_autostart_browser,
    find_launch_scripts,
    any_launch_script_found,
    get_autostart_status,
)
from server.servers.handlers import (
    handle_get_autostart_browser,
    handle_post_autostart_browser,
)


class TestParseSettings(unittest.TestCase):
    """Тесты парсинга содержимого .flowlink-settings."""

    def test_parse_empty(self):
        """Пустой контент возвращает пустой словарь."""
        self.assertEqual(_parse_settings(''), {})

    def test_parse_single_key(self):
        """Одна строка key=value."""
        result = _parse_settings('autostart_browser=true')
        self.assertEqual(result, {'autostart_browser': 'true'})

    def test_parse_with_comments(self):
        """Комментарии (#) пропускаются."""
        content = '# comment\nautostart_browser=false\n# another comment'
        result = _parse_settings(content)
        self.assertEqual(result, {'autostart_browser': 'false'})

    def test_parse_multiple_keys(self):
        """Несколько строк key=value."""
        content = 'autostart_browser=true\nother_key=123'
        result = _parse_settings(content)
        self.assertEqual(result, {
            'autostart_browser': 'true',
            'other_key': '123',
        })

    def test_parse_whitespace_handling(self):
        """Пробелы вокруг = и по краям строки удаляются."""
        result = _parse_settings('  autostart_browser = false  ')
        self.assertEqual(result, {'autostart_browser': 'false'})

    def test_parse_blank_lines(self):
        """Пустые строки пропускаются."""
        content = '\n\nautostart_browser=true\n\n'
        result = _parse_settings(content)
        self.assertEqual(result, {'autostart_browser': 'true'})

    def test_parse_line_without_equals(self):
        """Строка без = пропускается."""
        result = _parse_settings('invalid_line\nautostart_browser=true')
        self.assertEqual(result, {'autostart_browser': 'true'})


class TestFormatSettings(unittest.TestCase):
    """Тесты форматирования словаря настроек в текст."""

    def test_format_single(self):
        """Одна настройка."""
        result = _format_settings({'autostart_browser': 'true'})
        self.assertEqual(result, 'autostart_browser=true\n')

    def test_format_multiple(self):
        """Несколько настроек."""
        result = _format_settings({
            'autostart_browser': 'false',
            'other': 'value',
        })
        lines = result.strip().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertIn('autostart_browser=false', lines)
        self.assertIn('other=value', lines)

    def test_format_empty(self):
        """Пустой словарь."""
        result = _format_settings({})
        self.assertEqual(result, '\n')


class TestGetAutostartBrowser(unittest.TestCase):
    """Тесты чтения настройки autostart_browser."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_settings = SETTINGS_FILE

    def tearDown(self):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = self._orig_settings
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _mock_settings_file(self, path):
        """Подменяет SETTINGS_FILE на тестовый путь."""
        import server.config.autostart as mod
        mod.SETTINGS_FILE = path

    def test_default_when_no_file(self):
        """По умолчанию True, если файл настроек не существует."""
        self._mock_settings_file(os.path.join(self.tmpdir, 'nonexistent'))
        self.assertTrue(get_autostart_browser())

    def test_read_true(self):
        """Чтение autostart_browser=true."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=true\n')
        self._mock_settings_file(path)
        self.assertTrue(get_autostart_browser())

    def test_read_false(self):
        """Чтение autostart_browser=false."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=false\n')
        self._mock_settings_file(path)
        self.assertFalse(get_autostart_browser())

    def test_read_yes_value(self):
        """Чтение autostart_browser=yes (альтернативное значение)."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=yes\n')
        self._mock_settings_file(path)
        self.assertTrue(get_autostart_browser())

    def test_read_no_value(self):
        """Чтение autostart_browser=no (альтернативное значение)."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=no\n')
        self._mock_settings_file(path)
        self.assertFalse(get_autostart_browser())

    def test_read_unrecognized_value(self):
        """Нераспознанное значение возвращает default (True)."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=maybe\n')
        self._mock_settings_file(path)
        self.assertTrue(get_autostart_browser())

    def test_read_with_comments(self):
        """Чтение с комментариями и пустыми строками."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('# FlowLink settings\n\nautostart_browser=false\n')
        self._mock_settings_file(path)
        self.assertFalse(get_autostart_browser())


class TestSetAutostartBrowser(unittest.TestCase):
    """Тесты записи настройки autostart_browser."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_settings = SETTINGS_FILE

    def tearDown(self):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = self._orig_settings
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _mock_settings_file(self, path):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = path

    def test_set_false_creates_file(self):
        """Запись false создаёт файл с autostart_browser=false."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        set_autostart_browser(False)
        self.assertTrue(os.path.isfile(path))
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('autostart_browser=false', content)

    def test_set_true_creates_file(self):
        """Запись true создаёт файл с autostart_browser=true."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        set_autostart_browser(True)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('autostart_browser=true', content)

    def test_set_preserves_other_keys(self):
        """Запись сохраняет другие ключи в файле."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=true\nother_key=value\n')
        self._mock_settings_file(path)
        set_autostart_browser(False)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('autostart_browser=false', content)
        self.assertIn('other_key=value', content)

    def test_roundtrip(self):
        """Затем чтение — проверка консистентности."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        set_autostart_browser(False)
        self.assertFalse(get_autostart_browser())
        set_autostart_browser(True)
        self.assertTrue(get_autostart_browser())


class TestFindLaunchScripts(unittest.TestCase):
    """Тесты поиска скриптов запуска."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch('server.config.autostart._get_search_dirs')
    def test_finds_bat_in_search_dir(self, mock_dirs):
        """Находит .bat файл в директории поиска."""
        mock_dirs.return_value = [self.tmpdir]
        bat_path = os.path.join(self.tmpdir, 'FlowLink Proxy.bat')
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
        result = find_launch_scripts()
        self.assertEqual(len(result['FlowLink Proxy.bat']), 1)
        self.assertEqual(len(result['FlowLink Proxy.sh']), 0)

    @patch('server.config.autostart._get_search_dirs')
    def test_finds_sh_in_search_dir(self, mock_dirs):
        """Находит .sh файл в директории поиска."""
        mock_dirs.return_value = [self.tmpdir]
        sh_path = os.path.join(self.tmpdir, 'FlowLink Proxy.sh')
        with open(sh_path, 'w', encoding='utf-8') as f:
            f.write('#!/bin/bash\n')
        result = find_launch_scripts()
        self.assertEqual(len(result['FlowLink Proxy.sh']), 1)

    @patch('server.config.autostart._get_search_dirs')
    def test_finds_source_sh(self, mock_dirs):
        """Находит FlowLink Proxy Source.sh."""
        mock_dirs.return_value = [self.tmpdir]
        path = os.path.join(self.tmpdir, 'FlowLink Proxy Source.sh')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('#!/bin/bash\n')
        result = find_launch_scripts()
        self.assertEqual(len(result['FlowLink Proxy Source.sh']), 1)

    @patch('server.config.autostart._get_search_dirs')
    def test_no_scripts_found(self, mock_dirs):
        """Нет скриптов — все списки пусты."""
        mock_dirs.return_value = [self.tmpdir]
        result = find_launch_scripts()
        for paths in result.values():
            self.assertEqual(paths, [])

    @patch('server.config.autostart._get_search_dirs')
    def test_deduplication(self, mock_dirs):
        """Один и тот же файл не дублируется при разных путях."""
        # Создаём две директории, указывающие на один файл через symlink
        dir1 = os.path.join(self.tmpdir, 'dir1')
        dir2 = os.path.join(self.tmpdir, 'dir2')
        os.makedirs(dir1)
        os.makedirs(dir2)
        bat_path = os.path.join(self.tmpdir, 'FlowLink Proxy.bat')
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
        # Симлинки из обеих директорий на один файл
        os.symlink(bat_path, os.path.join(dir1, 'FlowLink Proxy.bat'))
        os.symlink(bat_path, os.path.join(dir2, 'FlowLink Proxy.bat'))
        mock_dirs.return_value = [dir1, dir2]
        result = find_launch_scripts()
        self.assertEqual(len(result['FlowLink Proxy.bat']), 1)


class TestAnyLaunchScriptFound(unittest.TestCase):
    """Тесты any_launch_script_found."""

    def test_returns_false_when_empty(self):
        """Возвращает False, когда скриптов нет."""
        with patch('server.config.autostart.find_launch_scripts') as mock:
            mock.return_value = {
                'FlowLink Proxy.bat': [],
                'FlowLink Proxy.sh': [],
                'FlowLink Proxy Source.sh': [],
            }
            self.assertFalse(any_launch_script_found())

    def test_returns_true_when_found(self):
        """Возвращает True, когда хотя бы один скрипт найден."""
        with patch('server.config.autostart.find_launch_scripts') as mock:
            mock.return_value = {
                'FlowLink Proxy.bat': ['/path/to/bat'],
                'FlowLink Proxy.sh': [],
                'FlowLink Proxy Source.sh': [],
            }
            self.assertTrue(any_launch_script_found())


class TestGetAutostartStatus(unittest.TestCase):
    """Тесты get_autostart_status — полный ответ API."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_settings = SETTINGS_FILE

    def tearDown(self):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = self._orig_settings
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _mock_settings_file(self, path):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = path

    @patch('server.config.autostart._get_search_dirs')
    def test_status_with_scripts(self, mock_dirs):
        """Статус с найденными скриптами."""
        mock_dirs.return_value = [self.tmpdir]
        bat_path = os.path.join(self.tmpdir, 'FlowLink Proxy.bat')
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
        settings_path = os.path.join(self.tmpdir, '.flowlink-settings')
        with open(settings_path, 'w', encoding='utf-8') as f:
            f.write('autostart_browser=true\n')
        self._mock_settings_file(settings_path)
        result = get_autostart_status()
        self.assertTrue(result['autostartBrowser'])
        self.assertTrue(result['launchScriptsFound'])
        self.assertIn('FlowLink Proxy.bat', result['launchScripts'])

    @patch('server.config.autostart._get_search_dirs')
    def test_status_without_scripts(self, mock_dirs):
        """Статус без найденных скриптов."""
        mock_dirs.return_value = [self.tmpdir]
        settings_path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(settings_path)
        result = get_autostart_status()
        self.assertFalse(result['launchScriptsFound'])


class TestHandleGetAutostartBrowser(unittest.TestCase):
    """Тесты handle_get_autostart_browser handler."""

    def setUp(self):
        self._orig_settings = SETTINGS_FILE

    def tearDown(self):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = self._orig_settings

    def test_returns_dict_with_expected_keys(self):
        """Handler возвращает словарь с нужными ключами."""
        result = handle_get_autostart_browser()
        self.assertIn('autostartBrowser', result)
        self.assertIn('launchScriptsFound', result)
        self.assertIn('launchScripts', result)
        self.assertIsInstance(result['autostartBrowser'], bool)
        self.assertIsInstance(result['launchScriptsFound'], bool)


class TestHandlePostAutostartBrowser(unittest.TestCase):
    """Тесты handle_post_autostart_browser handler."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_settings = SETTINGS_FILE

    def tearDown(self):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = self._orig_settings
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def _mock_settings_file(self, path):
        import server.config.autostart as mod
        mod.SETTINGS_FILE = path

    def test_set_false(self):
        """POST с autostartBrowser=false выключает автозапуск."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        result = asyncio.run(
            handle_post_autostart_browser({'autostartBrowser': False}),
        )
        self.assertTrue(result['success'])
        self.assertFalse(result['autostartBrowser'])

    def test_set_true(self):
        """POST с autostartBrowser=true включает автозапуск."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        result = asyncio.run(
            handle_post_autostart_browser({'autostartBrowser': True}),
        )
        self.assertTrue(result['success'])
        self.assertTrue(result['autostartBrowser'])

    def test_missing_field(self):
        """POST без autostartBrowser возвращает ошибку."""
        result = asyncio.run(
            handle_post_autostart_browser({}),
        )
        self.assertIn('error', result)

    def test_non_dict_input(self):
        """POST с не-словарём возвращает ошибку."""
        result = asyncio.run(
            handle_post_autostart_browser('not a dict'),
        )
        self.assertIn('error', result)


if __name__ == '__main__':
    unittest.main()
