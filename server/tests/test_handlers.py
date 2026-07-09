"""
Тесты обработчиков API-эндпоинтов handlers.py.
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from server.config import config as cfg
from server.config import repo as config_repo
from server.servers.handlers import (_extract_masks_dict,
                                     _extract_proxies_dict, handle_get_config,
                                     handle_get_status, handle_get_version)
from server.services.router import MaskRouter


class TestExtractHelpers(unittest.TestCase):
    """Тесты вспомогательных функций извлечения данных."""

    def test_extract_proxies_dict_normal(self):
        """Извлечение словаря прокси из данных"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080},
                {'proxyId': 'p2', 'host': '2.2.2.2', 'port': 9090},
            ]
        }
        result = _extract_proxies_dict(data)
        self.assertEqual(len(result), 2)
        self.assertIn('p1', result)
        self.assertIn('p2', result)

    def test_extract_proxies_dict_skips_none_id(self):
        """Прокси без proxyId пропускаются"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080},
                {'host': 'no-id', 'port': 9090},
            ]
        }
        result = _extract_proxies_dict(data)
        self.assertEqual(len(result), 1)
        self.assertIn('p1', result)

    def test_extract_proxies_dict_empty(self):
        """Пустой список прокси"""
        data = {'proxies': []}
        result = _extract_proxies_dict(data)
        self.assertEqual(result, {})

    def test_extract_proxies_dict_no_key(self):
        """Нет ключа proxies в данных"""
        data = {}
        result = _extract_proxies_dict(data)
        self.assertEqual(result, {})

    def test_extract_masks_dict_normal(self):
        """Извлечение словаря масок из данных"""
        data = {
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'},
                {'maskId': 'm2', 'proxyId': 'p2', 'regexString': r'\.org'},
            ]
        }
        result = _extract_masks_dict(data)
        self.assertEqual(len(result), 2)
        self.assertIn('m1', result)
        self.assertIn('m2', result)

    def test_extract_masks_dict_skips_none_id(self):
        """Маски без maskId пропускаются"""
        data = {
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'},
                {'proxyId': 'p1', 'regexString': r'\.org'},
            ]
        }
        result = _extract_masks_dict(data)
        self.assertEqual(len(result), 1)


class TestHandleGetConfig(unittest.TestCase):
    """Тесты handle_get_config."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_config_file = config_repo.CONFIG_FILE
        config_repo.CONFIG_FILE = os.path.join(self.tmpdir, 'config.json')
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}],
        })

    def tearDown(self):
        config_repo.CONFIG_FILE = self.orig_config_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_handle_get_config_returns_data(self):
        """GET /api/config возвращает данные с isEnabled"""
        result = handle_get_config()
        self.assertIn('proxies', result)
        self.assertIn('masks', result)
        self.assertIn('isEnabled', result)
        self.assertIsInstance(result['isEnabled'], bool)

    def test_handle_get_config_includes_isEnabled(self):
        """GET /api/config инжектит isEnabled из памяти"""
        cfg.set_enabled(False)
        result = handle_get_config()
        self.assertFalse(result['isEnabled'])


class TestHandleGetStatus(unittest.TestCase):
    """Тесты handle_get_status."""

    def test_handle_get_status_running(self):
        """GET /api/status возвращает статус running"""
        result = handle_get_status(debug=False)
        self.assertEqual(result['status'], 'running')
        self.assertFalse(result['debug'])
        self.assertFalse(result['needUpdate'])

    def test_handle_get_status_debug(self):
        """GET /api/status с debug=True"""
        result = handle_get_status(debug=True)
        self.assertTrue(result['debug'])

    def test_handle_get_status_need_update(self):
        """GET /api/status с need_update=True"""
        result = handle_get_status(debug=False, need_update=True)
        self.assertTrue(result['needUpdate'])


class TestHandleGetVersion(unittest.TestCase):
    """Тесты handle_get_version."""

    def test_handle_get_version_returns_string(self):
        """GET /api/version возвращает строку версии"""
        result = handle_get_version()
        self.assertIn('version', result)
        self.assertIsInstance(result['version'], str)
