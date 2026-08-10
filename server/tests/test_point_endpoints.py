"""
Тесты точечных эндпоинтов прокси и масок (Фаза 1 оптимизации).
"""

import asyncio
import unittest

from server.config import config as cfg
from server.config import repo as config_repo
from server.servers.handlers import (handle_delete_mask, handle_delete_proxy,
                                     handle_patch_mask,
                                     handle_patch_proxy,
                                     handle_patch_proxy_enabled,
                                     handle_post_mask, handle_post_proxy)
from server.services.router import MaskRouter
from server.tests.base import TempConfigMixin


def _make_router() -> MaskRouter:
    """Создаёт роутер с пустым конфигом."""
    router = MaskRouter()
    router.refresh()
    return router


class TestHandlePostProxy(TempConfigMixin, unittest.TestCase):
    """Тесты POST /api/proxies."""

    def setUp(self):
        super().setUp()
        self.router = _make_router()

    def test_post_proxy_success(self):
        """Успешное добавление прокси"""
        result = asyncio.run(handle_post_proxy(
            {'host': '1.1.1.1', 'port': 1080, 'label': 'test'}, self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertIn('proxy', result)
        self.assertEqual(result['proxy']['host'], '1.1.1.1')
        self.assertEqual(result['proxy']['port'], 1080)
        self.assertTrue(result['proxy']['isEnabled'])
        # Проверяем сохранение
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 1)

    def test_post_proxy_duplicate(self):
        """Дубликат host:port → 422"""
        asyncio.run(handle_post_proxy(
            {'host': '1.1.1.1', 'port': 1080}, self.router,
        ))
        result = asyncio.run(handle_post_proxy(
            {'host': '1.1.1.1', 'port': 1080}, self.router,
        ))
        self.assertEqual(result[1], 422)

    def test_post_proxy_invalid_port(self):
        """Невалидный port → 400"""
        result = asyncio.run(handle_post_proxy(
            {'host': '1.1.1.1', 'port': 99999}, self.router,
        ))
        self.assertEqual(result[1], 400)

    def test_post_proxy_missing_host(self):
        """Отсутствует host → 400"""
        result = asyncio.run(handle_post_proxy(
            {'port': 1080}, self.router,
        ))
        self.assertEqual(result[1], 400)

    def test_post_proxy_non_dict(self):
        """Не-словарь → 400"""
        result = asyncio.run(
            # type: ignore[reportArgumentType] — намеренно передаём строку для проверки ошибки
            handle_post_proxy('bad', self.router),  # type: ignore[reportArgumentType]
        )
        assert isinstance(result, tuple)
        self.assertEqual(result[1], 400)


class TestHandlePatchProxy(TempConfigMixin, unittest.TestCase):
    """Тесты PATCH /api/proxy/{id}."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [],
        })
        cfg.invalidate_cache()
        self.router = _make_router()

    def test_patch_proxy_success(self):
        """Успешное обновление полей"""
        result = asyncio.run(handle_patch_proxy(
            'p1', {'host': '2.2.2.2', 'port': 9090, 'label': 'new'}, self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertEqual(result['proxy']['host'], '2.2.2.2')
        self.assertEqual(result['proxy']['port'], 9090)
        loaded = cfg.load_config()
        self.assertEqual(loaded['proxies'][0]['host'], '2.2.2.2')

    def test_patch_proxy_not_found(self):
        """Несуществующий прокси → 404"""
        result = asyncio.run(handle_patch_proxy(
            'nope', {'host': '2.2.2.2', 'port': 9090}, self.router,
        ))
        self.assertEqual(result[1], 404)

    def test_patch_proxy_duplicate(self):
        """Дубликат host:port (другой прокси) → 422"""
        config_repo.save_raw({
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True},
                {'proxyId': 'p2', 'host': '3.3.3.3', 'port': 1080, 'isEnabled': True},
            ],
            'masks': [],
        })
        cfg.invalidate_cache()
        result = asyncio.run(handle_patch_proxy(
            'p1', {'host': '3.3.3.3', 'port': 1080}, self.router,
        ))
        self.assertEqual(result[1], 422)


class TestHandlePatchProxyEnabled(TempConfigMixin, unittest.TestCase):
    """Тесты PATCH /api/proxy/{id}/enabled."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [],
        })
        cfg.invalidate_cache()
        self.router = _make_router()

    def test_disable_proxy(self):
        """Выключение прокси"""
        result = asyncio.run(handle_patch_proxy_enabled(
            'p1', {'enabled': False}, self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertFalse(result['enabled'])
        loaded = cfg.load_config()
        self.assertFalse(loaded['proxies'][0]['isEnabled'])

    def test_enable_proxy(self):
        """Включение прокси"""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': False}],
            'masks': [],
        })
        cfg.invalidate_cache()
        result = asyncio.run(handle_patch_proxy_enabled(
            'p1', {'enabled': True}, self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertTrue(result['enabled'])

    def test_enable_not_found(self):
        """Несуществующий прокси → 404"""
        result = asyncio.run(handle_patch_proxy_enabled(
            'nope', {'enabled': True}, self.router,
        ))
        self.assertEqual(result[1], 404)

    def test_missing_enabled_field(self):
        """Отсутствует поле enabled → 400"""
        result = asyncio.run(handle_patch_proxy_enabled(
            'p1', {}, self.router,
        ))
        self.assertEqual(result[1], 400)

    def test_enable_conflict(self):
        """Включение прокси с конфликтом масок → 422"""
        config_repo.save_raw({
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': False},
                {'proxyId': 'p2', 'host': '2.2.2.2', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
            ],
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'pattern': '*.com', 'regexString': '.*\\.com'},
                {'maskId': 'm2', 'proxyId': 'p2', 'pattern': '*.com', 'regexString': '.*\\.com'},
            ],
        })
        cfg.invalidate_cache()
        result = asyncio.run(handle_patch_proxy_enabled(
            'p1', {'enabled': True}, self.router,
        ))
        self.assertEqual(result[1], 422)


class TestHandleDeleteProxy(TempConfigMixin, unittest.TestCase):
    """Тесты DELETE /api/proxy/{id}."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'pattern': '*.com',
                       'regexString': '.*\\.com'}],
        })
        cfg.invalidate_cache()
        self.router = _make_router()

    def test_delete_proxy_success(self):
        """Удаление прокси и связанных масок"""
        result = asyncio.run(handle_delete_proxy('p1', self.router))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 0)
        self.assertEqual(len(loaded['masks']), 0)

    def test_delete_proxy_not_found(self):
        """Несуществующий прокси → 404"""
        result = asyncio.run(handle_delete_proxy('nope', self.router))
        self.assertEqual(result[1], 404)


class TestHandlePostMask(TempConfigMixin, unittest.TestCase):
    """Тесты POST /api/masks."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [],
        })
        cfg.invalidate_cache()
        self.router = _make_router()

    def test_post_mask_success(self):
        """Успешное добавление маски"""
        result = asyncio.run(handle_post_mask(
            {'pattern': '*.com', 'regexString': '.*\\.com', 'proxyId': 'p1'},
            self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertIn('mask', result)
        self.assertEqual(result['mask']['proxyId'], 'p1')
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['masks']), 1)

    def test_post_mask_missing_pattern(self):
        """Отсутствует pattern → 400"""
        result = asyncio.run(handle_post_mask(
            {'proxyId': 'p1'}, self.router,
        ))
        self.assertEqual(result[1], 400)

    def test_post_mask_proxy_not_found(self):
        """Несуществующий proxyId → 400"""
        result = asyncio.run(handle_post_mask(
            {'pattern': '*.com', 'proxyId': 'nope'}, self.router,
        ))
        self.assertEqual(result[1], 400)

    def test_post_mask_conflict(self):
        """Конфликт масок → 422"""
        config_repo.save_raw({
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
                {'proxyId': 'p2', 'host': '2.2.2.2', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
            ],
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'pattern': '*.com',
                 'regexString': '.*\\.com'},
            ],
        })
        cfg.invalidate_cache()
        result = asyncio.run(handle_post_mask(
            {'pattern': '*.com', 'regexString': '.*\\.com', 'proxyId': 'p2'},
            self.router,
        ))
        self.assertEqual(result[1], 422)


class TestHandlePatchMask(TempConfigMixin, unittest.TestCase):
    """Тесты PATCH /api/mask/{id}."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'pattern': '*.com',
                       'regexString': '.*\\.com'}],
        })
        cfg.invalidate_cache()
        self.router = _make_router()

    def test_patch_mask_success(self):
        """Успешное обновление маски"""
        result = asyncio.run(handle_patch_mask(
            'm1', {'pattern': '*.org', 'regexString': '.*\\.org'}, self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertEqual(result['mask']['pattern'], '*.org')
        loaded = cfg.load_config()
        self.assertEqual(loaded['masks'][0]['pattern'], '*.org')

    def test_patch_mask_not_found(self):
        """Несуществующая маска → 404"""
        result = asyncio.run(handle_patch_mask(
            'nope', {'pattern': '*.org'}, self.router,
        ))
        self.assertEqual(result[1], 404)

    def test_patch_mask_recomputes_regex_without_regex_string(self):
        """Изменение pattern без regexString пересчитывает regexString на сервере"""
        result = asyncio.run(handle_patch_mask(
            'm1', {'pattern': '*.org'}, self.router,
        ))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        self.assertEqual(result['mask']['pattern'], '*.org')
        # regexString должен быть пересчитан из нового паттерна
        self.assertEqual(result['mask']['regexString'], '.*\\.org')
        loaded = cfg.load_config()
        self.assertEqual(loaded['masks'][0]['regexString'], '.*\\.org')


class TestHandleDeleteMask(TempConfigMixin, unittest.TestCase):
    """Тесты DELETE /api/mask/{id}."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'pattern': '*.com',
                       'regexString': '.*\\.com'}],
        })
        cfg.invalidate_cache()
        self.router = _make_router()

    def test_delete_mask_success(self):
        """Успешное удаление маски"""
        result = asyncio.run(handle_delete_mask('m1', self.router))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['masks']), 0)

    def test_delete_mask_not_found(self):
        """Несуществующая маска → 404"""
        result = asyncio.run(handle_delete_mask('nope', self.router))
        self.assertEqual(result[1], 404)
