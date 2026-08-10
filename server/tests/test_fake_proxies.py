"""
Тесты модуля генерации фиктивных прокси (fake_proxies.py) и инъекции (config.py).
"""

import os
import tempfile
import unittest

from server.config import config as cfg
from server.config import repo as config_repo
from server.services.fake_proxies import (_random_id, _random_ip,
                                          _random_port,
                                          generate_fake_proxies)


class TestRandomId(unittest.TestCase):
    """Тесты генерации уникальных идентификаторов."""

    def test_random_id_length(self):
        """ID содержит 12 hex-символов."""
        rid = _random_id()
        self.assertEqual(len(rid), 12)

class TestRandomIp(unittest.TestCase):
    """Тесты генерации IP-адресов."""

    def test_ip_in_test_range(self):
        """IP находится в диапазоне 198.51.100.X."""
        for i in range(10):
            ip = _random_ip(i)
            parts = ip.split('.')
            self.assertEqual(parts[0], '198')
            self.assertEqual(parts[1], '51')
            self.assertEqual(parts[2], '100')

    def test_ip_not_zero(self):
        """Последний октет никогда не равен 0."""
        for i in range(260):
            ip = _random_ip(i)
            last_octet = int(ip.rsplit('.', maxsplit=1)[-1])
            self.assertNotEqual(last_octet, 0)

    def test_ip_sequential(self):
        """Последние октеты идут по порядку (1, 2, 3...)."""
        for i in range(5):
            ip = _random_ip(i)
            last_octet = int(ip.rsplit('.', maxsplit=1)[-1])
            self.assertEqual(last_octet, i + 1)


class TestRandomPort(unittest.TestCase):
    """Тесты генерации портов."""

    def test_port_in_range(self):
        """Порт в диапазоне 10000–65000."""
        for _ in range(200):
            port = _random_port()
            self.assertGreaterEqual(port, 10000)
            self.assertLessEqual(port, 65000)


class TestGenerateFakeProxies(unittest.TestCase):
    """Тесты основной функции generate_fake_proxies."""

    def test_returns_dict_with_proxies_and_masks(self):
        """Возвращает словарь с ключами 'proxies' и 'masks'."""
        result = generate_fake_proxies(3)
        self.assertIn('proxies', result)
        self.assertIn('masks', result)

    def test_correct_count(self):
        """Количество прокси и масок соответствует count."""
        result = generate_fake_proxies(5)
        self.assertEqual(len(result['proxies']), 5)
        self.assertEqual(len(result['masks']), 5)

    def test_count_one(self):
        """count=1 корректно работает."""
        result = generate_fake_proxies(1)
        self.assertEqual(len(result['proxies']), 1)
        self.assertEqual(len(result['masks']), 1)

    def test_count_zero_raises(self):
        """count=0 вызывает ValueError."""
        with self.assertRaises(ValueError):
            generate_fake_proxies(0)

    def test_count_negative_raises(self):
        """Отрицательный count вызывает ValueError."""
        with self.assertRaises(ValueError):
            generate_fake_proxies(-5)

    def test_proxy_fields_complete(self):
        """У каждого прокси есть все обязательные поля."""
        result = generate_fake_proxies(2)
        required_fields = {'proxyId', 'host', 'port', 'username', 'password', 'label', 'isEnabled'}
        for proxy in result['proxies']:
            self.assertTrue(
                required_fields.issubset(proxy.keys()),
                f'Отсутствуют поля: {required_fields - proxy.keys()}',
            )

    def test_proxy_id_prefix(self):
        """proxyId начинается с 'fake-'."""
        result = generate_fake_proxies(3)
        for proxy in result['proxies']:
            self.assertTrue(proxy['proxyId'].startswith('fake-'))

    def test_mask_id_prefix(self):
        """maskId начинается с 'fake-mask-'."""
        result = generate_fake_proxies(3)
        for mask in result['masks']:
            self.assertTrue(mask['maskId'].startswith('fake-mask-'))

    def test_mask_references_valid_proxy(self):
        """Каждая маска ссылается на существующий прокси."""
        result = generate_fake_proxies(3)
        proxy_ids = {p['proxyId'] for p in result['proxies']}
        for mask in result['masks']:
            self.assertIn(mask['proxyId'], proxy_ids)

    def test_mask_fields_complete(self):
        """У каждой маски есть maskId, proxyId, regexString."""
        result = generate_fake_proxies(3)
        for mask in result['masks']:
            self.assertIn('maskId', mask)
            self.assertIn('proxyId', mask)
            self.assertIn('regexString', mask)

    def test_mask_regex_format(self):
        """regexString маски начинается с '*.' и заканчивается '.test'."""
        result = generate_fake_proxies(3)
        for mask in result['masks']:
            self.assertTrue(mask['regexString'].startswith('*.'))
            self.assertTrue(mask['regexString'].endswith('.test'))

    def test_all_proxy_ids_unique(self):
        """Все proxyId уникальны."""
        result = generate_fake_proxies(10)
        ids = [p['proxyId'] for p in result['proxies']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_mask_ids_unique(self):
        """Все maskId уникальны."""
        result = generate_fake_proxies(10)
        ids = [m['maskId'] for m in result['masks']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_ips_unique(self):
        """Все IP-адреса уникальны (при count <= 254)."""
        result = generate_fake_proxies(10)
        ips = [p['host'] for p in result['proxies']]
        self.assertEqual(len(ips), len(set(ips)))

    def test_proxies_enabled_by_default(self):
        """Все фиктивные прокси включены по умолчанию."""
        result = generate_fake_proxies(5)
        for proxy in result['proxies']:
            self.assertTrue(proxy['isEnabled'])

    def test_label_format(self):
        """label содержит номер прокси."""
        result = generate_fake_proxies(3)
        for i, proxy in enumerate(result['proxies']):
            self.assertIn(str(i + 1), proxy['label'])

    def test_large_count(self):
        """Генерация 100 прокси работает без ошибок."""
        result = generate_fake_proxies(100)
        self.assertEqual(len(result['proxies']), 100)
        self.assertEqual(len(result['masks']), 100)

    def test_each_call_generates_different_data(self):
        """Два вызова generate_fake_proxies генерируют разные данные."""
        r1 = generate_fake_proxies(3)
        r2 = generate_fake_proxies(3)
        ids1 = {p['proxyId'] for p in r1['proxies']}
        ids2 = {p['proxyId'] for p in r2['proxies']}
        self.assertTrue(ids1.isdisjoint(ids2))


class TestInjectProxies(unittest.TestCase):
    """Тесты инъекции прокси в конфиг."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_config_file = config_repo.CONFIG_FILE
        config_repo.CONFIG_FILE = os.path.join(self.tmpdir, 'config.json')

    def tearDown(self):
        config_repo.CONFIG_FILE = self.orig_config_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_inject_adds_to_existing(self):
        """Инъекция добавляет прокси к существующим."""
        config_repo.save_raw({
            'proxies': [{'proxyId': 'existing', 'host': '1.1.1.1', 'port': 1080}],
            'masks': [{'maskId': 'em1', 'proxyId': 'existing', 'regexString': '.*'}],
        })
        fake_data = generate_fake_proxies(2)
        count = cfg.inject_proxies(fake_data)
        self.assertEqual(count, 2)
        loaded = config_repo.load_raw()
        self.assertEqual(len(loaded['proxies']), 3)
        self.assertEqual(len(loaded['masks']), 3)

    def test_inject_empty_config(self):
        """Инъекция в пустой конфиг."""
        fake_data = generate_fake_proxies(3)
        count = cfg.inject_proxies(fake_data)
        self.assertEqual(count, 3)
        loaded = config_repo.load_raw()
        self.assertEqual(len(loaded['proxies']), 3)

    def test_inject_preserves_existing_proxies(self):
        """Инъекция не удаляет существующие прокси."""
        config_repo.save_raw({
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080},
                {'proxyId': 'p2', 'host': '2.2.2.2', 'port': 2080},
            ],
            'masks': [],
        })
        fake_data = generate_fake_proxies(1)
        cfg.inject_proxies(fake_data)
        loaded = config_repo.load_raw()
        proxy_ids = [p['proxyId'] for p in loaded['proxies']]
        self.assertIn('p1', proxy_ids)
        self.assertIn('p2', proxy_ids)
        self.assertEqual(len(loaded['proxies']), 3)

    def test_inject_preserves_existing_masks(self):
        """Инъекция не удаляет существующие маски."""
        config_repo.save_raw({
            'proxies': [],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': '.*'}],
        })
        fake_data = generate_fake_proxies(1)
        cfg.inject_proxies(fake_data)
        loaded = config_repo.load_raw()
        self.assertEqual(len(loaded['masks']), 2)

    def test_inject_returns_count(self):
        """inject_proxies возвращает количество добавленных прокси."""
        fake_data = generate_fake_proxies(7)
        count = cfg.inject_proxies(fake_data)
        self.assertEqual(count, 7)

    def test_inject_multiple_times(self):
        """Многократная инъекция накапливает прокси."""
        for _ in range(3):
            fake_data = generate_fake_proxies(2)
            cfg.inject_proxies(fake_data)
        loaded = config_repo.load_raw()
        self.assertEqual(len(loaded['proxies']), 6)
        self.assertEqual(len(loaded['masks']), 6)

    def test_injected_proxies_visible_in_load_config(self):
        """Инъецированные прокси видны через load_config()."""
        fake_data = generate_fake_proxies(2)
        cfg.inject_proxies(fake_data)
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 2)

    def test_injected_proxies_not_encrypted(self):
        """Инъецированные прокси не шифруются (пароли в открытом виде)."""
        fake_data = generate_fake_proxies(1)
        cfg.inject_proxies(fake_data)
        raw = config_repo.load_raw()
        password = raw['proxies'][0].get('password', '')
        self.assertTrue(password.startswith('fake-pass-'))
