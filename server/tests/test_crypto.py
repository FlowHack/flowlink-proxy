"""
Тесты обработки исключений и краевых случаев crypto.py.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from server.config import crypto as crypto_mod


class TestCryptoExceptions(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_key_file = crypto_mod.KEY_FILE
        crypto_mod.KEY_FILE = os.path.join(self.tmpdir, '.flowlink.key')

    def tearDown(self):
        crypto_mod.KEY_FILE = self.orig_key_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_encrypt_without_crypto_raises(self):
        """Без cryptography → ImportError"""
        with patch.object(crypto_mod, 'HAS_CRYPTO', False):
            with self.assertRaises(ImportError):
                crypto_mod.encrypt('secret')

    def test_decrypt_without_crypto_raises(self):
        """Без cryptography → ImportError"""
        with patch.object(crypto_mod, 'HAS_CRYPTO', False):
            with self.assertRaises(ImportError):
                crypto_mod.decrypt('cipher')

    def test_encrypt_empty_string(self):
        """Пустая строка → пустая строка"""
        self.assertEqual(crypto_mod.encrypt(''), '')

    def test_decrypt_empty_string(self):
        """Пустая строка → пустая строка"""
        self.assertEqual(crypto_mod.decrypt(''), '')

    def test_encrypt_decrypt_roundtrip(self):
        """Шифрование-дешифрование работает"""
        original = 'my_secret_password'
        encrypted = crypto_mod.encrypt(original)
        decrypted = crypto_mod.decrypt(encrypted)
        self.assertEqual(original, decrypted)

    def test_decrypt_invalid_b64(self):
        """Невалидный base64 → исключение (перехватывается в config)"""
        with self.assertRaises(Exception):
            crypto_mod.decrypt('!!!not_base64!!!')

    def test_decrypt_invalid_ciphertext(self):
        """Повреждённый шифротекст → исключение"""
        with self.assertRaises(Exception):
            crypto_mod.decrypt('YWJjZGVmZ2hpamtsbW5vcA==')

    def test_key_file_wrong_size_recreates(self):
        """Файл ключа неверного размера → создаётся новый"""
        with open(crypto_mod.KEY_FILE, 'wb') as f:
            f.write(b'tooshort')
        key = crypto_mod._load_or_create_key()
        self.assertEqual(len(key), 32)
        with open(crypto_mod.KEY_FILE, 'rb') as f:
            self.assertEqual(len(f.read()), 32)
