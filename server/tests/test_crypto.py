"""
Тесты обработки исключений и краевых случаев crypto.py.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from server.config import crypto as crypto_mod


class TestCryptoExceptions(unittest.TestCase):
    """Тесты обработки исключений и краевых случаев crypto.py."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_key_file = crypto_mod.KEY_FILE
        self.orig_salt_file = crypto_mod.SALT_FILE
        crypto_mod.KEY_FILE = os.path.join(self.tmpdir, '.flowlink.key')
        crypto_mod.SALT_FILE = os.path.join(self.tmpdir, '.flowlink.salt')

    def tearDown(self):
        crypto_mod.KEY_FILE = self.orig_key_file
        crypto_mod.SALT_FILE = self.orig_salt_file
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
        """Шифрование-дешифрование работает корректно"""
        original = 'my_secret_password'
        encrypted = crypto_mod.encrypt(original)
        decrypted = crypto_mod.decrypt(encrypted)
        self.assertEqual(original, decrypted)

    def test_encrypt_decrypt_unicode(self):
        """Шифрование-дешифрование Unicode-строки"""
        original = 'пароль_кириллица_🔑'
        encrypted = crypto_mod.encrypt(original)
        decrypted = crypto_mod.decrypt(encrypted)
        self.assertEqual(original, decrypted)

    def test_encrypt_decrypt_long_string(self):
        """Шифрование-дешифрование длинной строки (10 КБ)"""
        original = 'x' * 10240
        encrypted = crypto_mod.encrypt(original)
        decrypted = crypto_mod.decrypt(encrypted)
        self.assertEqual(original, decrypted)

    def test_decrypt_invalid_b64(self):
        """Невалидный base64 → исключение"""
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
        key = crypto_mod.load_or_create_key()
        self.assertEqual(len(key), 32)
        with open(crypto_mod.KEY_FILE, 'rb') as f:
            self.assertEqual(len(f.read()), 32)

    def test_salt_file_created_on_new_key(self):
        """При создании нового ключа генерируется соль"""
        key = crypto_mod.load_or_create_key()
        self.assertEqual(len(key), 32)
        self.assertTrue(os.path.exists(crypto_mod.SALT_FILE))
        with open(crypto_mod.SALT_FILE, 'rb') as f:
            salt = f.read()
        self.assertEqual(len(salt), 32)

    def test_salt_loaded_from_file(self):
        """Соль загружается из файла"""
        test_salt = os.urandom(32)
        with open(crypto_mod.SALT_FILE, 'wb') as f:
            f.write(test_salt)
        loaded_salt = crypto_mod._load_salt()
        self.assertEqual(loaded_salt, test_salt)

    def test_legacy_salt_used_when_no_file(self):
        """При отсутствии файла соли используется legacy-соль"""
        loaded_salt = crypto_mod._load_salt()
        self.assertEqual(loaded_salt, crypto_mod._LEGACY_SALT)

    def test_corrupt_salt_file_uses_legacy(self):
        """Повреждённый файл соли → fallback на legacy-соль"""
        with open(crypto_mod.SALT_FILE, 'wb') as f:
            f.write(b'short')
        loaded_salt = crypto_mod._load_salt()
        self.assertEqual(loaded_salt, crypto_mod._LEGACY_SALT)

    def test_save_salt_creates_file(self):
        """_save_salt создаёт файл соли"""
        test_salt = os.urandom(32)
        crypto_mod._save_salt(test_salt)
        self.assertTrue(os.path.exists(crypto_mod.SALT_FILE))
        with open(crypto_mod.SALT_FILE, 'rb') as f:
            self.assertEqual(f.read(), test_salt)

    def test_multiple_encryptions_different_ciphertexts(self):
        """Два шифрования одной строки дают разный шифротекст (разный IV)"""
        text = 'same_password'
        enc1 = crypto_mod.encrypt(text)
        enc2 = crypto_mod.encrypt(text)
        self.assertNotEqual(enc1, enc2)
        # Но расшифровываются одинаково
        self.assertEqual(crypto_mod.decrypt(enc1), text)
        self.assertEqual(crypto_mod.decrypt(enc2), text)
