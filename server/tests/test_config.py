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

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_config_file = config_repo.CONFIG_FILE
        config_repo.CONFIG_FILE = os.path.join(self.tmpdir, 'config.json')

    def tearDown(self):
        config_repo.CONFIG_FILE = self.orig_config_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_load_empty_config_creates_default(self):
        """При отсутствии config.json создаётся конфиг по умолчанию"""
        data = cfg.load_config()
        self.assertEqual(data['proxies'], [])
        self.assertEqual(data['masks'], [])
        self.assertTrue(data['isEnabled'])

    def test_load_corrupted_json_raises(self):
        """Битый JSON в config.json → RuntimeError"""
        with open(config_repo.CONFIG_FILE, 'w') as f:
            f.write('{broken json')
        with self.assertRaises(RuntimeError):
            cfg.load_config()

    def test_load_empty_file_raises(self):
        """Пустой config.json → RuntimeError"""
        with open(config_repo.CONFIG_FILE, 'w') as f:
            f.write('')
        with self.assertRaises(RuntimeError):
            cfg.load_config()

    def test_save_and_load_roundtrip(self):
        """Сохранение и загрузка конфига"""
        data = {
            'proxies': [{'proxyId': 'p1', 'host': '1.2.3.4', 'port': 1080, 'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': '.*'}],
            'isEnabled': True,
        }
        with patch.object(crypto_mod, 'encrypt', return_value='encrypted'):
            cfg.save_config(data)
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 1)
        self.assertEqual(len(loaded['masks']), 1)

    def test_save_with_encrypt_error(self):
        """Ошибка шифрования при сохранении не убивает процесс"""
        data = {
            'proxies': [{'proxyId': 'p1', 'host': '1.2.3.4', 'port': 1080, 'username': 'user', 'password': 'pass', 'isEnabled': True}],
            'masks': [],
            'isEnabled': True,
        }
        with patch.object(crypto_mod, 'encrypt', side_effect=Exception('AES failed')):
            try:
                cfg.save_config(data)
            except Exception:
                self.fail('save_config не должен бросать исключение при ошибке encrypt')

    def test_load_with_decrypt_error(self):
        """Ошибка расшифровки username/password → пустая строка, процесс не падает"""
        data = {
            'proxies': [{'proxyId': 'p1', 'host': '1.2.3.4', 'port': 1080,
                         'username': 'bad_cipher', 'password': 'bad_cipher', 'isEnabled': True}],
            'masks': [],
            'isEnabled': True,
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
            'isEnabled': True,
        }
        config_repo.save_raw(data)
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 1)
