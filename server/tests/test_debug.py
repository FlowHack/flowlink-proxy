"""
Тесты утилит debug-режима: безопасное логирование HTTP-тел.

Проверяет маскировку чувствительных полей (password, username, token,
api_key, access_token, authorization, secret) в JSON-строках, а также
функцию truncate для ограничения размера логов.
"""

import unittest

from server.services.debug import mask_sensitive, truncate


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


if __name__ == '__main__':
    unittest.main()
