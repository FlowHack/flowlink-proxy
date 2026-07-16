"""
Модуль шифрования AES-GCM для хранения паролей прокси.

Генерирует мастер-ключ при первом запуске (.flowlink.key),
шифрует/расшифровывает username/password для config.json.
Использует уникальную соль PBKDF2 для каждого ключа (.flowlink.salt).

Требуется библиотека cryptography (pip install cryptography).
"""

from __future__ import annotations

import base64
import logging
import os
from hashlib import pbkdf2_hmac

from server.utils import get_data_dir

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    AESGCM = None
    HAS_CRYPTO = False

logger = logging.getLogger('flowlink.crypto')

# Директория для хранения файлов ключей и соли
_DATA_DIR = get_data_dir()

# Путь к файлу мастер-ключа
KEY_FILE = os.path.join(_DATA_DIR, '.flowlink.key')
# Путь к файлу соли PBKDF2
SALT_FILE = os.path.join(_DATA_DIR, '.flowlink.salt')
# Количество итераций PBKDF2 для выведения ключа шифрования
PBKDF2_ITERATIONS = 600_000
# Константная соль для обратной совместимости со старыми ключами
_LEGACY_SALT = b'flowlink_proxy_salt_v1'


def _check_crypto() -> None:
    """Проверяет наличие библиотеки cryptography. Вызывает ImportError, если её нет."""
    if not HAS_CRYPTO:
        logger.error('Библиотека cryptography не установлена')
        raise ImportError(
            'Требуется библиотека cryptography. '
            'Установите: pip install cryptography'
        )


def load_or_create_key() -> bytes:
    """
    Загружает мастер-ключ из KEY_FILE или создаёт новый (32 байта).

    Если файл существует, но имеет неверный размер — перезаписывает.
    Устанавливает права 600 на файл ключа для безопасности.
    """
    try:
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'rb') as f:
                key = f.read()
                if len(key) == 32:
                    logger.debug('Мастер-ключ загружен из %s', KEY_FILE)
                    return key
            logger.warning(
                'Файл ключа %s имеет неверный размер (%d байт), создаю новый',
                KEY_FILE, len(key)
            )

        key = os.urandom(32)
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
        # Генерируем уникальную соль для нового ключа
        _save_salt(os.urandom(32))
        try:
            os.chmod(KEY_FILE, 0o600)
        except NotImplementedError:
            logger.debug('chmod не поддерживается на этой платформе (Windows)')
        except OSError as e:
            logger.warning('Не удалось установить права на %s: %s', KEY_FILE, e)
        logger.info('Создан новый мастер-ключ шифрования: %s', KEY_FILE)
        return key
    except OSError as e:
        logger.error(
            'Не удалось получить доступ к файлу ключа %s: %s. '
            'Убедитесь, что у программы есть права на запись в '
            'директорию данных.', KEY_FILE, e
        )
        raise


def _load_salt() -> bytes:
    """
    Загружает соль PBKDF2 из файла.

    Если файл соли существует — используем уникальную соль.
    Если нет — используем константную соль (обратная совместимость со старыми ключами).
    """
    try:
        if os.path.exists(SALT_FILE):
            with open(SALT_FILE, 'rb') as f:
                salt = f.read()
                if len(salt) == 32:
                    return salt
            logger.warning('Файл соли повреждён, используется legacy-соль')
    except OSError as e:
        logger.warning('Не удалось прочитать файл соли %s: %s', SALT_FILE, e)
    return _LEGACY_SALT


def _save_salt(salt: bytes) -> None:
    """
    Сохраняет соль PBKDF2 в файл.

    Устанавливает права 600 для безопасности.
    """
    with open(SALT_FILE, 'wb') as f:
        f.write(salt)
    try:
        os.chmod(SALT_FILE, 0o600)
    except (NotImplementedError, OSError):
        logger.debug('Не удалось установить права на %s', SALT_FILE)


def _derive_key(master_key: bytes) -> bytes:
    """
    Выводит 256-битный ключ AES из мастер-ключа через PBKDF2-HMAC-SHA256.

    PBKDF2 замедляет перебор в случае компрометации зашифрованных данных,
    делая атаку по словарю практически нереализуемой.
    Использует уникальную соль из файла или legacy-соль для обратной совместимости.
    """
    salt = _load_salt()
    derived = pbkdf2_hmac('sha256', master_key, salt, PBKDF2_ITERATIONS, dklen=32)
    logger.debug(
        'Ключ шифрования получен через PBKDF2 (%d итераций)',
        PBKDF2_ITERATIONS
    )
    return derived


def encrypt(plaintext: str) -> str:
    """
    Шифрует строку AES-256-GCM.

    Формат: base64(iv (12 байт) + ciphertext + auth_tag (16 байт)).
    GCM обеспечивает аутентифицированное шифрование —
    целостность данных проверяется при расшифровке.
    При первом вызове генерирует уникальную соль PBKDF2.
    """
    if not plaintext:
        return ''

    _check_crypto()
    # Если соли нет — генерируем и сохраняем (для новых установок)
    if not os.path.exists(SALT_FILE):
        _save_salt(os.urandom(32))
    master_key = load_or_create_key()
    aes_key = _derive_key(master_key)
    aesgcm = AESGCM(aes_key)

    # 96-битный IV (nonce) для AES-GCM — генерируется случайно каждый раз
    iv = os.urandom(12)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
    encrypted = base64.b64encode(iv + ciphertext).decode()
    logger.debug(
        'Данные зашифрованы AES-GCM (%d байт в base64)',
        len(encrypted)
    )
    return encrypted


def decrypt(ciphertext_b64: str) -> str:
    """
    Расшифровывает строку, зашифрованную encrypt().

    Ожидает base64-формат: iv (12) + ciphertext + auth_tag (16).
    GCM автоматически проверяет аутентификацию — повреждённые данные вызовут исключение.
    """
    if not ciphertext_b64:
        return ''

    _check_crypto()
    try:
        master_key = load_or_create_key()
        aes_key = _derive_key(master_key)
        aesgcm = AESGCM(aes_key)

        raw = base64.b64decode(ciphertext_b64)
        # Первые 12 байт — IV, остальное — ciphertext + GCM auth tag (16 байт)
        iv, ciphertext = raw[:12], raw[12:]
        plaintext = aesgcm.decrypt(iv, ciphertext, None).decode()
        return plaintext
    except Exception as e:
        logger.error('Ошибка расшифровки данных: %s', e)
        raise
