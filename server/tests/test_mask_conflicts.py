"""Тесты логики конфликтов масок между прокси.

Проверяют:
  - convert_wildcard_to_regex — конвертация wildcard в regex.
  - wildcard_intersects — пересечение двух wildcard-паттернов.
  - compute_conflict_groups — построение транзитивных групп конфликта.
  - validate_config — правило «не более одного включённого прокси в группе».
"""

import unittest

from server.services.mask_conflicts import (
    compute_conflict_groups,
    convert_wildcard_to_regex,
    validate_config,
    wildcard_intersects,
)


class TestConvertWildcardToRegex(unittest.TestCase):
    """Тесты конвертации wildcard-паттерна в регулярное выражение."""

    def test_simple_wildcard(self):
        """Звёздочка превращается в .*"""
        self.assertEqual(convert_wildcard_to_regex('*.example.com'), '.*\\.example\\.com')

    def test_question_mark(self):
        """Вопросительный знак превращается в точку."""
        self.assertEqual(convert_wildcard_to_regex('a?c'), 'a.c')

    def test_special_chars_escaped(self):
        """Спецсимволы regex экранируются."""
        self.assertEqual(convert_wildcard_to_regex('a.b+c'), 'a\\.b\\+c')

    def test_collapses_multiple_stars(self):
        """Повторяющиеся звёздочки схлопываются в одну."""
        self.assertEqual(convert_wildcard_to_regex('a**b'), 'a.*b')

    def test_non_string_returns_empty(self):
        """Не-строка возвращает пустую строку."""
        # type: ignore[reportArgumentType] — намеренно передаём не-строки для проверки обработки
        self.assertEqual(convert_wildcard_to_regex(None), '')  # type: ignore[reportArgumentType]
        self.assertEqual(convert_wildcard_to_regex(123), '')  # type: ignore[reportArgumentType]


class TestWildcardIntersects(unittest.TestCase):
    """Тесты проверки пересечения двух wildcard-паттернов."""

    def test_identical_patterns(self):
        """Идентичные паттерны пересекаются."""
        self.assertTrue(wildcard_intersects('*.example.com', '*.example.com'))

    def test_substring_containment(self):
        """Один паттерн содержит другой."""
        self.assertTrue(wildcard_intersects('*.example.com', '*.sub.example.com'))

    def test_disjoint_patterns(self):
        """Непересекающиеся паттерны."""
        self.assertFalse(wildcard_intersects('*.google.com', '*.yandex.ru'))

    def test_all_wildcard_intersects_everything(self):
        """Паттерн из одних звёздочек пересекается со всем."""
        self.assertTrue(wildcard_intersects('*', '*.example.com'))

    def test_non_string_returns_false(self):
        """Не-строка не пересекается."""
        # type: ignore[reportArgumentType] — намеренно передаём не-строки
        # для проверки обработки
        self.assertFalse(
            wildcard_intersects(None, '*.example.com'),  # type: ignore[reportArgumentType]
        )
        self.assertFalse(
            wildcard_intersects('*.example.com', None),  # type: ignore[reportArgumentType]
        )


class TestComputeConflictGroups(unittest.TestCase):
    """Тесты построения транзитивных групп конфликта."""

    def _proxy(self, pid):
        return {'proxyId': pid, 'host': '1.2.3.4', 'port': 8080, 'isEnabled': True}

    def _mask(self, mid, pid, pattern):
        return {'maskId': mid, 'proxyId': pid, 'pattern': pattern}

    def test_no_conflicts(self):
        """Прокси с непересекающимися масками не образуют групп."""
        proxies = [self._proxy('p1'), self._proxy('p2')]
        masks = [
            self._mask('m1', 'p1', '*.google.com'),
            self._mask('m2', 'p2', '*.yandex.ru'),
        ]
        self.assertEqual(compute_conflict_groups(proxies, masks), [])

    def test_two_proxies_conflict(self):
        """Два прокси с пересекающимися масками — одна группа."""
        proxies = [self._proxy('p1'), self._proxy('p2')]
        masks = [
            self._mask('m1', 'p1', '*.example.com'),
            self._mask('m2', 'p2', '*.sub.example.com'),
        ]
        groups = compute_conflict_groups(proxies, masks)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0], {'p1', 'p2'})

    def test_transitive_group(self):
        """Транзитивность: A-B и B-C объединяют всех троих."""
        proxies = [self._proxy('p1'), self._proxy('p2'), self._proxy('p3')]
        masks = [
            self._mask('m1', 'p1', '*.example.com'),
            self._mask('m2', 'p2', '*.sub.example.com'),
            self._mask('m3', 'p3', '*.deep.sub.example.com'),
        ]
        groups = compute_conflict_groups(proxies, masks)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0], {'p1', 'p2', 'p3'})

    def test_two_separate_groups(self):
        """Две независимые группы конфликта."""
        proxies = [self._proxy('p1'), self._proxy('p2'), self._proxy('p3'), self._proxy('p4')]
        masks = [
            self._mask('m1', 'p1', '*.google.com'),
            self._mask('m2', 'p2', '*.mail.google.com'),
            self._mask('m3', 'p3', '*.yandex.ru'),
            self._mask('m4', 'p4', '*.mail.yandex.ru'),
        ]
        groups = compute_conflict_groups(proxies, masks)
        self.assertEqual(len(groups), 2)

    def test_masks_within_same_proxy_not_conflict(self):
        """Маски одного прокси не создают конфликт (группа из одного не образуется)."""
        proxies = [self._proxy('p1')]
        masks = [
            self._mask('m1', 'p1', '*.google.com'),
            self._mask('m2', 'p1', '*.mail.google.com'),
        ]
        self.assertEqual(compute_conflict_groups(proxies, masks), [])

    def test_proxy_without_masks_ignored(self):
        """Прокси без масок не попадает в группы."""
        proxies = [self._proxy('p1'), self._proxy('p2')]
        masks = [
            self._mask('m1', 'p1', '*.example.com'),
        ]
        self.assertEqual(compute_conflict_groups(proxies, masks), [])


class TestValidateConfig(unittest.TestCase):
    """Тесты валидации конфига на конфликты включённых прокси."""

    def _proxy(self, pid, enabled=True, label=None):
        return {
            'proxyId': pid,
            'host': '1.2.3.4',
            'port': 8080,
            'isEnabled': enabled,
            'label': label,
        }

    def _mask(self, mid, pid, pattern):
        return {'maskId': mid, 'proxyId': pid, 'pattern': pattern}

    def test_no_conflicts(self):
        """Нет конфликтов — пустой список ошибок."""
        proxies = [self._proxy('p1'), self._proxy('p2')]
        masks = [
            self._mask('m1', 'p1', '*.google.com'),
            self._mask('m2', 'p2', '*.yandex.ru'),
        ]
        self.assertEqual(validate_config(proxies, masks), [])

    def test_conflict_between_enabled_proxies(self):
        """Два включённых конфликтующих прокси — ошибка."""
        proxies = [self._proxy('p1', label='Прокси 1'), self._proxy('p2', label='Прокси 2')]
        masks = [
            self._mask('m1', 'p1', '*.example.com'),
            self._mask('m2', 'p2', '*.sub.example.com'),
        ]
        errors = validate_config(proxies, masks)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['proxyId'], 'p1')
        self.assertEqual(errors[0]['conflictingProxyId'], 'p2')
        self.assertEqual(errors[0]['proxyLabel'], 'Прокси 1')
        self.assertEqual(errors[0]['conflictingProxyLabel'], 'Прокси 2')

    def test_conflict_with_disabled_proxy_allowed(self):
        """Конфликт с выключенным прокси допустим — нет ошибки."""
        proxies = [self._proxy('p1', enabled=True), self._proxy('p2', enabled=False)]
        masks = [
            self._mask('m1', 'p1', '*.example.com'),
            self._mask('m2', 'p2', '*.sub.example.com'),
        ]
        self.assertEqual(validate_config(proxies, masks), [])

    def test_identical_masks_conflict(self):
        """Идентичные маски у двух включённых прокси — конфликт."""
        proxies = [self._proxy('p1'), self._proxy('p2')]
        masks = [
            self._mask('m1', 'p1', '*.example.com'),
            self._mask('m2', 'p2', '*.example.com'),
        ]
        errors = validate_config(proxies, masks)
        self.assertEqual(len(errors), 1)

    def test_masks_within_same_proxy_no_conflict(self):
        """Маски одного прокси не создают конфликт."""
        proxies = [self._proxy('p1')]
        masks = [
            self._mask('m1', 'p1', '*.google.com'),
            self._mask('m2', 'p1', '*.mail.google.com'),
        ]
        self.assertEqual(validate_config(proxies, masks), [])


if __name__ == '__main__':
    unittest.main()
