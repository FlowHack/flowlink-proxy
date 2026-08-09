"""
Тесты модуля autostart.py — управление автозапуском браузера.
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from server.config.autostart import (format_settings, get_autostart_browser,
                                     parse_settings, set_autostart_browser)
from server.servers.handlers import (handle_get_autostart_browser,
                                     handle_post_autostart_browser)


class _TempSettingsMixin(unittest.TestCase):
    """
    Миксин: setUp/tearDown + подмена SETTINGS_FILE через mock.patch.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mock_settings_file(self, path):
        """Подменяет SETTINGS_FILE на тестовый путь."""
        self._patcher = patch(
            'server.config.autostart.SETTINGS_FILE', path,
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)


class TestParseSettings(unittest.TestCase):
    """Тесты парсинга содержимого .flowlink-settings."""

    def test_parse_empty(self):
        """Пустой контент возвращает пустой словарь."""
        self.assertEqual(parse_settings(''), {})

    def test_parse_single_key(self):
        """Одна строка key=value."""
        result = parse_settings('autostart_browser=true')
        self.assertEqual(result, {'autostart_browser': 'true'})

    def test_parse_with_comments(self):
        """Комментарии (#) пропускаются."""
        content = '# comment\nautostart_browser=false\n# another comment'
        result = parse_settings(content)
        self.assertEqual(result, {'autostart_browser': 'false'})

    def test_parse_multiple_keys(self):
        """Несколько строк key=value."""
        content = 'autostart_browser=true\nother_key=123'
        result = parse_settings(content)
        self.assertEqual(result, {
            'autostart_browser': 'true',
            'other_key': '123',
        })

    def test_parse_whitespace_handling(self):
        """Пробелы вокруг = и по краям строки удаляются."""
        result = parse_settings('  autostart_browser = false  ')
        self.assertEqual(result, {'autostart_browser': 'false'})

    def test_parse_blank_lines(self):
        """Пустые строки пропускаются."""
        content = '\n\nautostart_browser=true\n\n'
        result = parse_settings(content)
        self.assertEqual(result, {'autostart_browser': 'true'})

    def test_parse_line_without_equals(self):
        """Строка без = пропускается."""
        result = parse_settings('invalid_line\nautostart_browser=true')
        self.assertEqual(result, {'autostart_browser': 'true'})


class TestFormatSettings(unittest.TestCase):
    """Тесты форматирования словаря настроек в текст."""

    def test_format_single(self):
        """Одна настройка."""
        result = format_settings({'autostart_browser': 'true'})
        self.assertEqual(result, 'autostart_browser=true\n')

    def test_format_multiple(self):
        """Несколько настроек."""
        result = format_settings({
            'autostart_browser': 'false',
            'other': 'value',
        })
        lines = result.strip().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertIn('autostart_browser=false', lines)
        self.assertIn('other=value', lines)

    def test_format_empty(self):
        """Пустой словарь."""
        result = format_settings({})
        self.assertEqual(result, '\n')


class TestGetAutostartBrowser(_TempSettingsMixin):
    """Тесты чтения настройки autostart_browser."""

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


class TestSetAutostartBrowser(_TempSettingsMixin):
    """Тесты записи настройки autostart_browser."""

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


class TestHandleGetAutostartBrowser(_TempSettingsMixin):
    """Тесты handle_get_autostart_browser handler."""

    def test_returns_dict_with_expected_keys(self):
        """Handler возвращает словарь с нужными ключами."""
        # Подменяем SETTINGS_FILE, чтобы handler не читал реальный файл пользователя
        self._mock_settings_file(os.path.join(self.tmpdir, '.flowlink-settings'))
        result = handle_get_autostart_browser()
        self.assertIn('autostartBrowser', result)
        self.assertIsInstance(result['autostartBrowser'], bool)


class TestHandlePostAutostartBrowser(_TempSettingsMixin):
    """Тесты handle_post_autostart_browser handler."""

    def test_set_false(self):
        """POST с autostartBrowser=false выключает автозапуск."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        result = asyncio.run(
            handle_post_autostart_browser({'autostartBrowser': False}),
        )
        if isinstance(result, tuple):
            result = result[0]
        self.assertTrue(result['success'])
        self.assertFalse(result['autostartBrowser'])

    def test_set_true(self):
        """POST с autostartBrowser=true включает автозапуск."""
        path = os.path.join(self.tmpdir, '.flowlink-settings')
        self._mock_settings_file(path)
        result = asyncio.run(
            handle_post_autostart_browser({'autostartBrowser': True}),
        )
        if isinstance(result, tuple):
            result = result[0]
        self.assertTrue(result['success'])
        self.assertTrue(result['autostartBrowser'])

    def test_missing_field(self):
        """POST без autostartBrowser возвращает ошибку."""
        # Ошибка-ветка handler'а читает autostart_browser через get_autostart_browser
        # (см. handlers.py) — подменяем SETTINGS_FILE, чтобы не читать реальный файл.
        self._mock_settings_file(os.path.join(self.tmpdir, '.flowlink-settings'))
        result = asyncio.run(
            handle_post_autostart_browser({}),
        )
        if isinstance(result, tuple):
            result = result[0]
        self.assertIn('error', result)

    def test_non_dict_input(self):
        """POST с не-словарём возвращает ошибку."""
        # type: ignore[reportArgumentType] — намеренно передаём не-словарь для проверки ошибки
        # Ошибка-ветка handler'а читает autostart_browser через get_autostart_browser
        # (см. handlers.py) — подменяем SETTINGS_FILE, чтобы не читать реальный файл.
        self._mock_settings_file(os.path.join(self.tmpdir, '.flowlink-settings'))
        result = asyncio.run(
            handle_post_autostart_browser('not a dict'),  # type: ignore[reportArgumentType]
        )
        if isinstance(result, tuple):
            result = result[0]
        self.assertIn('error', result)
