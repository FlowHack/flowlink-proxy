"""
Тесты обработки исключений и краевых случаев config.py.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from server.config import config as cfg
from server.config import crypto as crypto_mod
from server.config import repo as config_repo


class TestConfigExceptions(unittest.TestCase):
    """Тесты обработки исключений и краевых случаев config.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_config_file = config_repo.CONFIG_FILE
        config_repo.CONFIG_FILE = os.path.join(self.tmpdir, 'config.json')
        self.orig_enabled = cfg.is_enabled()

    def tearDown(self):
        cfg.set_enabled(self.orig_enabled)
        config_repo.CONFIG_FILE = self.orig_config_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_load_empty_config_creates_default(self):
        """При отсутствии config.json создаётся конфиг по умолчанию"""
        data = cfg.load_config()
        self.assertEqual(data['proxies'], [])
        self.assertEqual(data['masks'], [])

    def test_load_corrupted_json_raises(self):
        """Битый JSON в config.json → RuntimeError"""
        with open(config_repo.CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write('{broken json')
        with self.assertRaises(RuntimeError):
            cfg.load_config()

    def test_load_empty_file_raises(self):
        """Пустой config.json → RuntimeError"""
        with open(config_repo.CONFIG_FILE, 'w', encoding='utf-8') as f:
            f.write('')
        with self.assertRaises(RuntimeError):
            cfg.load_config()

    def test_save_and_load_roundtrip(self):
        """Сохранение и загрузка конфига"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.2.3.4', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
            ],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': '.*'}],
        }
        with patch.object(crypto_mod, 'encrypt', return_value='encrypted'):
            cfg.save_config(data)
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 1)
        self.assertEqual(len(loaded['masks']), 1)

    def test_save_with_encrypt_error(self):
        """Ошибка шифрования при сохранении не убивает процесс"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.2.3.4', 'port': 1080,
                 'username': 'user', 'password': 'pass', 'isEnabled': True},
            ],
            'masks': [],
        }
        with patch.object(crypto_mod, 'encrypt', side_effect=Exception('AES failed')):
            cfg.save_config(data)

    def test_load_with_decrypt_error(self):
        """Ошибка расшифровки username/password → пустая строка, процесс не падает"""
        data = {
            'proxies': [{'proxyId': 'p1', 'host': '1.2.3.4', 'port': 1080,
                         'username': 'bad_cipher', 'password': 'bad_cipher', 'isEnabled': True}],
            'masks': [],
        }
        config_repo.save_raw(data)
        with patch.object(crypto_mod, 'decrypt', side_effect=Exception('Decrypt failed')):
            loaded = cfg.load_config()
        self.assertEqual(loaded['proxies'][0].get('username', None), '')

    def test_proxy_without_ids_in_config(self):
        """Прокси без proxyId не ломает загрузку"""
        data = {
            'proxies': [{'host': 'no-id', 'port': 1111}],
            'masks': [],
        }
        config_repo.save_raw(data)
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 1)


class TestConfigEnabled(unittest.TestCase):
    """Тесты глобального флага включения (isEnabled)."""

    def setUp(self):
        self.orig_enabled = cfg.is_enabled()

    def tearDown(self):
        cfg.set_enabled(self.orig_enabled)

    def test_is_enabled_default(self):
        """По умолчанию isEnabled = True"""
        cfg.set_enabled(True)
        self.assertTrue(cfg.is_enabled())

    def test_set_enabled_false(self):
        """set_enabled(False) → is_enabled() = False"""
        cfg.set_enabled(False)
        self.assertFalse(cfg.is_enabled())

    def test_set_enabled_true(self):
        """set_enabled(True) → is_enabled() = True"""
        cfg.set_enabled(False)
        cfg.set_enabled(True)
        self.assertTrue(cfg.is_enabled())

    def test_toggle_enabled(self):
        """Многократное переключение isEnabled"""
        for expected in [False, True, False, True, False]:
            cfg.set_enabled(expected)
            self.assertEqual(cfg.is_enabled(), expected)

    def test_is_enabled_not_in_config_file(self):
        """isEnabled НЕ записывается в config.json"""
        config_repo.save_raw({'proxies': [], 'masks': []})
        cfg.set_enabled(False)
        loaded = config_repo.load_raw()
        self.assertNotIn('isEnabled', loaded)
