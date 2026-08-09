"""
Тесты утилит debug-режима: безопасное логирование HTTP-тел.

Проверяет маскировку чувствительных полей (password, username, token,
api_key, access_token, authorization, secret) в JSON-строках, а также
функцию truncate для ограничения размера логов.
"""

import unittest
from unittest.mock import patch

from server.services.debug import (log_config_state, mask_sensitive,
                                   truncate)


class TestMaskSensitive(unittest.TestCase):
    """Тесты mask_sensitive — маскировка секретных полей в JSON-строках."""

    def test_masks_password(self):
        """Поле password → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"password":"secret123"}'),
            '{"password":"***"}',
        )

    def test_masks_username(self):
        """Поле username → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"username":"admin"}'),
            '{"username":"***"}',
        )

    def test_masks_password_and_username(self):
        """Одновременно маскируются password и username."""
        self.assertEqual(
            mask_sensitive('{"username":"admin","password":"pass"}'),
            '{"username":"***","password":"***"}',
        )

    def test_masks_token(self):
        """Поле token → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"token":"abc123"}'),
            '{"token":"***"}',
        )

    def test_masks_api_key(self):
        """Поле api_key → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"api_key":"key123"}'),
            '{"api_key":"***"}',
        )

    def test_masks_access_token(self):
        """Поле access_token → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"access_token":"tok"}'),
            '{"access_token":"***"}',
        )

    def test_masks_authorization(self):
        """Поле authorization → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"authorization":"Bearer xyz"}'),
            '{"authorization":"***"}',
        )

    def test_masks_secret(self):
        """Поле secret → значение заменяется на ***."""
        self.assertEqual(
            mask_sensitive('{"secret":"s"}'),
            '{"secret":"***"}',
        )

    def test_masks_escaped_quotes_in_value(self):
        """Значение с экранированными кавычками → маскируется."""
        result = mask_sensitive('{"password":"has \\"escaped\\" quote"}')
        self.assertIn('"password":"***"', result)

    def test_masks_backslash_in_value(self):
        """Значение с бэкслешем внутри (pass\\word) → маскируется целиком."""
        result = mask_sensitive(r'{"password":"pass\word"}')
        self.assertEqual(result, '{"password":"***"}')

    def test_masks_trailing_backslash_in_value(self):
        """Значение с завершающим бэкслешем → маскируется целиком."""
        result = mask_sensitive(r'{"password":"trailing\\"}')
        self.assertEqual(result, '{"password":"***"}')

    def test_does_not_mask_normal_fields(self):
        """Обычные поля не изменяются."""
        self.assertEqual(
            mask_sensitive('{"normal":"value"}'),
            '{"normal":"value"}',
        )

    def test_empty_string_returns_empty(self):
        """Пустая строка → возвращается как есть."""
        self.assertEqual(mask_sensitive(''), '')

    def test_case_insensitive_field_match(self):
        """Поле в другом регистре (Token) → маскируется (имя приводится к нижнему регистру)."""
        self.assertEqual(
            mask_sensitive('{"Token":"abc"}'),
            '{"token":"***"}',
        )

    def test_masks_capitalized_password(self):
        """Поле Password (заглавная P) → маскируется (IGNORECASE)."""
        self.assertEqual(
            mask_sensitive('{"Password":"secret123"}'),
            '{"password":"***"}',
        )

    def test_masks_uppercase_password(self):
        """Поле PASSWORD (верхний регистр) → маскируется (IGNORECASE)."""
        self.assertEqual(
            mask_sensitive('{"PASSWORD":"secret123"}'),
            '{"password":"***"}',
        )

    def test_masks_capitalized_username(self):
        """Поле Username (заглавная U) → маскируется (IGNORECASE)."""
        self.assertEqual(
            mask_sensitive('{"Username":"admin"}'),
            '{"username":"***"}',
        )


class TestTruncate(unittest.TestCase):
    """Тесты truncate — ограничение размера строки для логов."""

    def test_short_text_unchanged(self):
        """Короткая строка → возвращается без изменений."""
        self.assertEqual(truncate('короткий текст'), 'короткий текст')

    def test_long_text_truncated(self):
        """Длинная строка → обрезается с пометкой."""
        text = 'x' * 3000
        result = truncate(text, max_len=2000)
        self.assertEqual(len(result), 2000 + len('... (обрезано)'))
        self.assertTrue(result.endswith('... (обрезано)'))

    def test_custom_max_len(self):
        """Пользовательский max_len → обрезка по нему."""
        result = truncate('abcdefghij', max_len=5)
        self.assertEqual(result, 'abcde... (обрезано)')

    def test_exact_max_len_not_truncated(self):
        """Строка ровно max_len → не обрезается."""
        text = 'x' * 2000
        self.assertEqual(truncate(text, max_len=2000), text)


class TestLogConfigState(unittest.TestCase):
    """Тесты log_config_state — логирование конфига без паролей."""

    def _config(self, with_secrets: bool = False) -> dict:
        """Формирует тестовый конфиг.

        Args:
            with_secrets: Добавить password/token в данные прокси.

        Returns:
            Словарь конфига с proxies и masks.
        """
        proxy = {
            'proxyId': 'p1',
            'host': '10.0.0.1',
            'port': 8080,
            'isEnabled': True,
        }
        if with_secrets:
            proxy['password'] = 'supersecretpass'
            proxy['token'] = 'supersecrettoken'
        return {
            'proxies': [proxy],
            'masks': [
                {'maskId': 'm1', 'pattern': '*.example.com', 'proxyId': 'p1'},
            ],
        }

    def test_startup_logs_config(self):
        """is_startup=True → в debug-лог пишется загрузка конфига с прокси."""
        with (
            patch(
                'server.services.debug.cfg.load_config',
                return_value=self._config(),
            ),
            self.assertLogs('flowlink.debug', level='DEBUG') as cm,
        ):
            log_config_state(is_startup=True)

        text = '\n'.join(cm.output)
        self.assertIn('Загружено прокси: 1', text)
        self.assertIn('p1', text)
        self.assertIn('10.0.0.1', text)
        self.assertIn('8080', text)

    def test_not_startup_logs_config(self):
        """is_startup=False → пишется «Конфиг после сохранения» с числом масок."""
        with (
            patch(
                'server.services.debug.cfg.load_config',
                return_value=self._config(),
            ),
            self.assertLogs('flowlink.debug', level='DEBUG') as cm,
        ):
            log_config_state(is_startup=False)

        text = '\n'.join(cm.output)
        self.assertIn('Конфиг после сохранения: 1 прокси, 1 масок', text)
        self.assertIn('Загружено масок: 1', text)
        self.assertIn('m1', text)

    def test_sensitive_data_not_in_log(self):
        """Пароль и токен не попадают в лог (безопасное логирование)."""
        with (
            patch(
                'server.services.debug.cfg.load_config',
                return_value=self._config(with_secrets=True),
            ),
            self.assertLogs('flowlink.debug', level='DEBUG') as cm,
        ):
            log_config_state(is_startup=False)

        text = '\n'.join(cm.output)
        self.assertNotIn('supersecretpass', text)
        self.assertNotIn('supersecrettoken', text)

    def test_empty_config_logs_zero_counts(self):
        """Пустой конфиг → логируются нулевые счётчики (без падения)."""
        with (
            patch(
                'server.services.debug.cfg.load_config',
                return_value={'proxies': [], 'masks': []},
            ),
            self.assertLogs('flowlink.debug', level='DEBUG') as cm,
        ):
            log_config_state(is_startup=True)

        text = '\n'.join(cm.output)
        self.assertIn('Загружено прокси: 0', text)
        self.assertIn('Загружено масок: 0', text)


if __name__ == '__main__':
    unittest.main()
