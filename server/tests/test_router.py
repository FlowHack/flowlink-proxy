"""
Тесты обработки исключений и краевых случаев router.py.
"""

import unittest

from server.config import config
from server.config import repo as config_repo
from server.services.router import MaskRouter
from server.tests.base import TempConfigMixin


class TestRouterExceptions(TempConfigMixin, unittest.TestCase):
    """Тесты обработки исключений и краевых случаев router.py."""

    def setUp(self):
        super().setUp()
        config.set_enabled(True)
        config_repo.save_raw({
            'proxies': [
                {'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
                {'proxyId': 'p2', 'host': '10.0.0.2', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': False},
            ],
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'},
                {'maskId': 'm2', 'proxyId': 'p2', 'regexString': r'\.test\.com'},
            ],
            'isEnabled': True,
        })

    def test_route_matching_url(self):
        """URL совпадает с маской → возвращается прокси"""
        router = MaskRouter()
        result = router.route('https://www.example.com/page')
        self.assertIsNotNone(result)
        self.assertEqual(result['host'], '10.0.0.1')  # type: ignore[reportOptionalSubscript]

    def test_route_non_matching_url(self):
        """URL не совпадает → None"""
        router = MaskRouter()
        result = router.route('https://www.other.com/page')
        self.assertIsNone(result)

    def test_route_disabled_proxy_skipped(self):
        """Выключенный прокси пропускается"""
        router = MaskRouter()
        result = router.route('https://www.test.com/page')
        self.assertIsNone(result)

    def test_route_global_disable(self):
        """Глобальное выключение → все маршруты игнорируются"""
        config.set_enabled(False)
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'}],
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNone(result)

    def test_route_corrupted_regex_skipped(self):
        """Битая regex-маска → пропускается, роутер не падает"""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [
                {'maskId': 'm_bad', 'proxyId': 'p1', 'regexString': r'[invalid'},
                {'maskId': 'm_good', 'proxyId': 'p1', 'regexString': r'\.example\.com'},
            ],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNotNone(result)

    def test_route_nonexistent_proxy_skipped(self):
        """Маска ссылается на несуществующий прокси → пропускается"""
        config_repo.save_raw({
            'proxies': [],
            'masks': [{'maskId': 'm_orphan', 'proxyId': 'ghost', 'regexString': r'\.example\.com'}],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNone(result)

    def test_route_empty_masks(self):
        """Пустой список масок → None"""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNone(result)

    def test_route_empty_proxies(self):
        """Пустой список прокси → None"""
        config_repo.save_raw({
            'proxies': [],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'}],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNone(result)

    def test_proxy_without_id_skipped(self):
        """Прокси без proxyId → пропускается, роутер не падает"""
        config_repo.save_raw({
            'proxies': [
                {'host': 'no-id', 'port': 1111, 'username': '', 'password': '', 'isEnabled': True},
                {'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
            ],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'}],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNotNone(result)

    def test_mask_without_proxy_id_skipped(self):
        """Маска без proxyId → пропускается"""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [
                {'maskId': 'm_no_pid', 'regexString': r'\.example\.com'},
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.other\.com'},
            ],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.other.com/')
        self.assertIsNotNone(result)

    def test_route_refresh(self):
        """refresh() загружает новые маски"""
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNotNone(result)

        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.changed\.com'}],
            'isEnabled': True,
        })
        router.refresh()
        result_old = router.route('https://www.example.com/')
        result_new = router.route('https://www.changed.com/')
        self.assertIsNone(result_old)
        self.assertIsNotNone(result_new)

    def test_route_multiple_masks_first_match_wins(self):
        """Несколько масок — первое совпадение определяет прокси"""
        config_repo.save_raw({
            'proxies': [
                {'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
                {'proxyId': 'p2', 'host': '10.0.0.2', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
            ],
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'},
                {'maskId': 'm2', 'proxyId': 'p2', 'regexString': r'\.example\.com'},
            ],
            'isEnabled': True,
        })
        router = MaskRouter()
        result = router.route('https://www.example.com/')
        self.assertIsNotNone(result)
        # Первый прокси, чья маска совпала
        self.assertEqual(result['proxyId'], 'p1')  # type: ignore[reportOptionalSubscript]

    def test_route_long_url(self):
        """Очень длинный URL (10 КБ) не вызывает ReDoS"""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'}],
            'isEnabled': True,
        })
        router = MaskRouter()
        long_path = 'a' * 10240
        result = router.route(f'https://www.example.com/{long_path}')
        self.assertIsNotNone(result)

    def test_route_special_chars_in_url(self):
        """URL со спецсимволами (query params, fragment)"""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '10.0.0.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.example\.com'}],
            'isEnabled': True,
        })
        router = MaskRouter()
        url = 'https://www.example.com/path?a=1&b=2#section'
        result = router.route(url)
        self.assertIsNotNone(result)
