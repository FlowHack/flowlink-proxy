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
        # Сбрасываем кэш ключей при подмене путей, чтобы он не «протекал»
        # между тестами (кэш привязан к содержимому, но файлы меняются).
        crypto_mod.reset_key_cache()

    def tearDown(self):
        crypto_mod.reset_key_cache()
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

    @unittest.skipUnless(crypto_mod.HAS_CRYPTO, 'Требуется библиотека cryptography')
    def test_encrypt_decrypt_roundtrip(self):
        """Шифрование-дешифрование работает корректно"""
        original = 'my_secret_password'
        encrypted = crypto_mod.encrypt(original)
        decrypted = crypto_mod.decrypt(encrypted)
        self.assertEqual(original, decrypted)

    @unittest.skipUnless(crypto_mod.HAS_CRYPTO, 'Требуется библиотека cryptography')
    def test_encrypt_decrypt_unicode(self):
        """Шифрование-дешифрование Unicode-строки"""
        original = 'пароль_кириллица_🔑'
        encrypted = crypto_mod.encrypt(original)
        decrypted = crypto_mod.decrypt(encrypted)
        self.assertEqual(original, decrypted)

    @unittest.skipUnless(crypto_mod.HAS_CRYPTO, 'Требуется библиотека cryptography')
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
        # _load_salt — internal: проверка fallback-логики при коррупции файла
        loaded_salt = crypto_mod._load_salt()  # pylint: disable=protected-access
        self.assertEqual(loaded_salt, test_salt)

    def test_legacy_salt_used_when_no_file(self):
        """При отсутствии файла соли используется legacy-соль"""
        # _load_salt — internal: проверка fallback-логики при отсутствии файла
        loaded_salt = crypto_mod._load_salt()  # pylint: disable=protected-access
        # _LEGACY_SALT — internal: проверка значения константы
        self.assertEqual(loaded_salt, crypto_mod._LEGACY_SALT)  # pylint: disable=protected-access

    def test_corrupt_salt_file_uses_legacy(self):
        """Повреждённый файл соли → fallback на legacy-соль"""
        with open(crypto_mod.SALT_FILE, 'wb') as f:
            f.write(b'short')
        # _load_salt — internal: проверка fallback-логики при коррупции файла
        loaded_salt = crypto_mod._load_salt()  # pylint: disable=protected-access
        # _LEGACY_SALT — internal: проверка значения константы
        self.assertEqual(loaded_salt, crypto_mod._LEGACY_SALT)  # pylint: disable=protected-access

    def test_save_salt_creates_file(self):
        """_save_salt создаёт файл соли"""
        test_salt = os.urandom(32)
        # _save_salt — internal: проверка записи соли в файл
        crypto_mod._save_salt(test_salt)  # pylint: disable=protected-access
        self.assertTrue(os.path.exists(crypto_mod.SALT_FILE))
        with open(crypto_mod.SALT_FILE, 'rb') as f:
            self.assertEqual(f.read(), test_salt)

    @unittest.skipUnless(crypto_mod.HAS_CRYPTO, 'Требуется библиотека cryptography')
    def test_multiple_encryptions_different_ciphertexts(self):
        """Два шифрования одной строки дают разный шифротекст (разный IV)"""
        text = 'same_password'
        enc1 = crypto_mod.encrypt(text)
        enc2 = crypto_mod.encrypt(text)
        self.assertNotEqual(enc1, enc2)
        # Но расшифровываются одинаково
        self.assertEqual(crypto_mod.decrypt(enc1), text)
        self.assertEqual(crypto_mod.decrypt(enc2), text)


class TestDerivedKeyCache(unittest.TestCase):
    """Тесты кэша производного ключа PBKDF2 и мастер-ключа."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.orig_key_file = crypto_mod.KEY_FILE
        self.orig_salt_file = crypto_mod.SALT_FILE
        crypto_mod.KEY_FILE = os.path.join(self.tmpdir, '.flowlink.key')
        crypto_mod.SALT_FILE = os.path.join(self.tmpdir, '.flowlink.salt')
        crypto_mod.reset_key_cache()
        # Инициализируем ключ и соль в изолированной директории
        crypto_mod.load_or_create_key()
        crypto_mod._save_salt(os.urandom(32))  # pylint: disable=protected-access  # internal: фиксируем уникальную соль

    def tearDown(self):
        crypto_mod.reset_key_cache()
        crypto_mod.KEY_FILE = self.orig_key_file
        crypto_mod.SALT_FILE = self.orig_salt_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    def test_derive_key_cached(self):
        """Второй вызов _derive_key с той же парой (ключ, соль) не выполняет PBKDF2"""
        master = crypto_mod.load_or_create_key()
        with patch.object(
            crypto_mod, 'pbkdf2_hmac', return_value=b'derived-key',
        ) as mock_pbkdf2:
            first = crypto_mod._derive_key(master)  # pylint: disable=protected-access  # internal: проверка кэша
            second = crypto_mod._derive_key(master)  # pylint: disable=protected-access
        self.assertEqual(first, second)
        self.assertEqual(mock_pbkdf2.call_count, 1)

    def test_reset_key_cache(self):
        """После reset_key_cache PBKDF2 выполняется заново"""
        master = crypto_mod.load_or_create_key()
        with patch.object(
            crypto_mod, 'pbkdf2_hmac', return_value=b'derived-key',
        ) as mock_pbkdf2:
            crypto_mod._derive_key(master)  # pylint: disable=protected-access
            crypto_mod.reset_key_cache()
            crypto_mod._derive_key(master)  # pylint: disable=protected-access
        self.assertEqual(mock_pbkdf2.call_count, 2)

    def test_cache_invalidated_on_salt_change(self):
        """Смена соли через _save_salt инвалидирует кэш производного ключа"""
        master = crypto_mod.load_or_create_key()
        with patch.object(
            crypto_mod, 'pbkdf2_hmac', return_value=b'derived-key',
        ) as mock_pbkdf2:
            crypto_mod._derive_key(master)  # pylint: disable=protected-access
            crypto_mod._save_salt(os.urandom(32))  # pylint: disable=protected-access
            crypto_mod._derive_key(master)  # pylint: disable=protected-access
        self.assertEqual(mock_pbkdf2.call_count, 2)

    def test_cache_invalidated_on_key_recreate(self):
        """Пересоздание ключа (повреждённый файл) инвалидирует кэш"""
        with patch.object(
            crypto_mod, 'pbkdf2_hmac', return_value=b'derived-key',
        ) as mock_pbkdf2:
            old_master = crypto_mod.load_or_create_key()
            crypto_mod._derive_key(old_master)  # pylint: disable=protected-access
            # Повреждаем файл ключа — при загрузке создаётся новый ключ
            with open(crypto_mod.KEY_FILE, 'wb') as f:
                f.write(b'tooshort')
            new_master = crypto_mod.load_or_create_key()
            self.assertNotEqual(new_master, old_master)
            crypto_mod._derive_key(new_master)  # pylint: disable=protected-access
        self.assertEqual(mock_pbkdf2.call_count, 2)
