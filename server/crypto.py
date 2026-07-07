"""
Модуль шифрования AES-GCM для хранения паролей прокси.

Генерирует мастер-ключ при первом запуске (.flowlink.key),
шифрует/расшифровывает username/password для config.json.

Требуется библиотека cryptography (pip install cryptography).
"""

import base64
import os
import sys
from hashlib import pbkdf2_hmac

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    AESGCM = None
    HAS_CRYPTO = False


if getattr(sys, 'frozen', False):
    KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), '.flowlink.key')
else:
    KEY_FILE = '.flowlink.key'
PBKDF2_ITERATIONS = 600_000
SALT = b'flowlink_proxy_2024'


def _check_crypto():
    if not HAS_CRYPTO:
        raise ImportError(
            'Требуется библиотека cryptography. '
            'Установите: pip install cryptography'
        )


def _load_or_create_key() -> bytes:
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
            if len(key) == 32:
                return key

    key = os.urandom(32)
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    os.chmod(KEY_FILE, 0o600)
    return key


def _derive_key(master_key: bytes) -> bytes:
    return pbkdf2_hmac('sha256', master_key, SALT, PBKDF2_ITERATIONS, dklen=32)


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ''

    _check_crypto()
    master_key = _load_or_create_key()
    aes_key = _derive_key(master_key)
    aesgcm = AESGCM(aes_key)

    iv = os.urandom(12)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
    return base64.b64encode(iv + ciphertext).decode()


def decrypt(ciphertext_b64: str) -> str:
    if not ciphertext_b64:
        return ''

    _check_crypto()
    master_key = _load_or_create_key()
    aes_key = _derive_key(master_key)
    aesgcm = AESGCM(aes_key)

    raw = base64.b64decode(ciphertext_b64)
    iv, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(iv, ciphertext, None).decode()
