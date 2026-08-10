"""
Тесты модуля i18n.py — локализация бэкенда (RU/EN/SR).

Покрывает: нормализацию языка, установку/чтение языка,
инициализацию gettext, функцию перевода _() и эндпоинты
/api/language (handle_get_language / handle_post_language).
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from server.config import autostart
from server.i18n import (_normalize_language, _read_stored_language,
                         get_language, init_i18n, set_language)
from server.servers.handlers import handle_get_language, handle_post_language

# Импорт функции перевода на верхнем уровне (для тестов _())
from server.i18n import _ as translate  # pylint: disable=redefined-builtin


class TestNormalizeLanguage(unittest.TestCase):
    """Тесты нормализации кода языка."""

    def test_ru(self):
        """'ru' нормализуется в 'ru'."""
        self.assertEqual(_normalize_language('ru'), 'ru')

    def test_ru_region(self):
        """'ru-RU' и 'ru_RU' нормализуются в 'ru'."""
        self.assertEqual(_normalize_language('ru-RU'), 'ru')
        self.assertEqual(_normalize_language('ru_RU'), 'ru')

    def test_en(self):
        """'en' нормализуется в 'en'."""
        self.assertEqual(_normalize_language('en'), 'en')

    def test_sr(self):
        """'sr' нормализуется в 'sr'."""
        self.assertEqual(_normalize_language('sr'), 'sr')

    def test_unknown_falls_back_to_ru(self):
        """Неизвестный язык нормализуется в 'ru' (по умолчанию)."""
        self.assertEqual(_normalize_language('de'), 'ru')
        self.assertEqual(_normalize_language('fr-FR'), 'ru')

    def test_empty_falls_back_to_ru(self):
        """Пустой/None язык нормализуется в 'ru'."""
        self.assertEqual(_normalize_language(''), 'ru')
        self.assertEqual(_normalize_language(None), 'ru')

    def test_uppercase(self):
        """Верхний регистр нормализуется в нижний."""
        self.assertEqual(_normalize_language('EN'), 'en')
        self.assertEqual(_normalize_language('SR'), 'sr')


class TestSetGetLanguage(unittest.TestCase):
    """Тесты установки и чтения текущего языка."""

    def tearDown(self):
        # Сбрасываем язык к умолчанию после каждого теста
        set_language('ru')

    def test_set_language_returns_normalized(self):
        """set_language возвращает нормализованный код."""
        self.assertEqual(set_language('en'), 'en')
        self.assertEqual(set_language('sr'), 'sr')

    def test_get_language_after_set(self):
        """get_language возвращает установленный язык."""
        set_language('en')
        self.assertEqual(get_language(), 'en')
        set_language('sr')
        self.assertEqual(get_language(), 'sr')

    def test_set_unknown_falls_back(self):
        """set_language с неизвестным языком сбрасывает к 'ru'."""
        set_language('de')
        self.assertEqual(get_language(), 'ru')


class TestTranslation(unittest.TestCase):
    """Тесты функции перевода _()."""

    def tearDown(self):
        set_language('ru')

    def test_ru_returns_original(self):
        """На русском _() возвращает исходную строку."""
        set_language('ru')
        self.assertEqual(translate('Выход'), 'Выход')

    def test_en_translates(self):
        """На английском _() переводит строку."""
        set_language('en')
        self.assertEqual(translate('Выход'), 'Exit')

    def test_sr_translates(self):
        """На сербском _() переводит строку."""
        set_language('sr')
        self.assertEqual(translate('Выход'), 'Izlaz')

    def test_unknown_string_returns_original(self):
        """Неизвестная строка возвращается без изменений."""
        set_language('en')
        self.assertEqual(translate('Неизвестная строка'), 'Неизвестная строка')


class TestInitI18n(unittest.TestCase):
    """Тесты инициализации локализации."""

    def tearDown(self):
        set_language('ru')

    def test_init_with_lang(self):
        """init_i18n(lang) устанавливает указанный язык."""
        init_i18n('en')
        self.assertEqual(get_language(), 'en')

    def test_init_without_lang_reads_stored(self):
        """init_i18n() без аргумента читает сохранённый язык."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = os.path.join(tmpdir, '.flowlink-settings')
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write('language=en\n')
            with patch('server.i18n.get_data_dir', return_value=tmpdir):
                init_i18n()
                self.assertEqual(get_language(), 'en')


class TestReadStoredLanguage(unittest.TestCase):
    """Тесты чтения сохранённого языка из .flowlink-settings."""

    def test_reads_language(self):
        """Читает язык из файла настроек."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = os.path.join(tmpdir, '.flowlink-settings')
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write('language=sr\n')
            with patch('server.i18n.get_data_dir', return_value=tmpdir):
                self.assertEqual(_read_stored_language(), 'sr')

    def test_missing_file_returns_default(self):
        """Отсутствующий файл возвращает язык по умолчанию."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('server.i18n.get_data_dir', return_value=tmpdir):
                self.assertEqual(_read_stored_language(), 'ru')

    def test_invalid_language_returns_default(self):
        """Некорректный язык в файле возвращает язык по умолчанию."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = os.path.join(tmpdir, '.flowlink-settings')
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write('language=de\n')
            with patch('server.i18n.get_data_dir', return_value=tmpdir):
                self.assertEqual(_read_stored_language(), 'ru')


class TestLanguageEndpoints(unittest.TestCase):
    """Тесты эндпоинтов /api/language."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._patcher = patch(
            'server.config.autostart.SETTINGS_FILE',
            os.path.join(self.tmpdir, '.flowlink-settings'),
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        set_language('ru')

    def test_get_language(self):
        """GET /api/language возвращает текущий язык."""
        result = handle_get_language()
        self.assertIn('language', result)
        self.assertEqual(result['language'], 'ru')

    def test_post_language_valid(self):
        """POST /api/language с валидным языком сохраняет его."""
        result = asyncio.run(handle_post_language({'language': 'en'}))
        # При успехе возвращается dict (не tuple)
        if isinstance(result, tuple):
            self.fail('Ожидался dict, получен tuple')
        self.assertTrue(result['success'])
        self.assertEqual(result['language'], 'en')
        # Проверяем, что язык сохранён в настройках
        self.assertEqual(autostart.get_language(), 'en')

    def test_post_language_missing_field(self):
        """POST /api/language без поля language возвращает 400."""
        result = asyncio.run(handle_post_language({}))
        self.assertEqual(result[1], 400)

    def test_post_language_invalid(self):
        """POST /api/language с неподдерживаемым языком возвращает 400."""
        result = asyncio.run(handle_post_language({'language': 'de'}))
        self.assertEqual(result[1], 400)

    def test_post_language_empty(self):
        """POST /api/language с пустой строкой возвращает 400."""
        result = asyncio.run(handle_post_language({'language': '  '}))
        self.assertEqual(result[1], 400)


if __name__ == '__main__':
    unittest.main()
