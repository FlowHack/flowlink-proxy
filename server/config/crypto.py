"""
Модуль шифрования AES-GCM для хранения паролей прокси.

Генерирует мастер-ключ при первом запуске (.flowlink.key),
шифрует/расшифровывает username/password для config.json.
Использует уникальную соль PBKDF2 для каждого ключа (.flowlink.salt).

Требуется библиотека cryptography (pip install cryptography).
"""

from __future__ import annotations

import base64
import binascii
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

# Кэш производного ключа AES: (master_key, salt) -> derived_key.
# PBKDF2 с 600 000 итераций выполняется только при первом обращении
# к конкретной паре (ключ, соль); повторные вызовы берут результат из кэша.
_DERIVED_KEY_CACHE: dict[tuple[bytes, bytes], bytes] = {}

# Кэш мастер-ключа: содержимое .flowlink.key (32 байта) или None.
# Избавляет от чтения файла при каждом encrypt/decrypt.
_MASTER_KEY_CACHE: bytes | None = None


def reset_key_cache() -> None:
    """Очищает кэши мастер-ключа и производного ключа.

    Вызывается при изменении соли, пересоздании мастер-ключа или
    помещении ключа в карантин, а также в тестах при подмене
    KEY_FILE/SALT_FILE, чтобы кэш не «протекал» между тестами.
    """
    # pylint: disable=global-statement  # сброс модульного кэша ключей
    global _MASTER_KEY_CACHE
    _DERIVED_KEY_CACHE.clear()
    _MASTER_KEY_CACHE = None


def _check_crypto() -> None:
    """Проверяет наличие библиотеки cryptography. Вызывает ImportError, если её нет."""
    if not HAS_CRYPTO:
        logger.error('Библиотека cryptography не установлена')
        raise ImportError(
            'Требуется библиотека cryptography. '
            'Установите: pip install cryptography'
        )


def _quarantine_corrupt_key(corrupt_key: bytes) -> None:
    """
    Перемещает повреждённый файл ключа в карантин (с суффиксом .corrupt).

    Сохраняет повреждённые данные для возможного ручного восстановления,
    не удаляя их безвозвратно.

    Args:
        corrupt_key: Содержимое повреждённого файла ключа.
    """
    # Ключ уходит в карантин — кэши мастер-ключа и производного ключа невалидны
    reset_key_cache()
    try:
        quarantine_path = f'{KEY_FILE}.corrupt'
        with open(quarantine_path, 'wb') as f:
            f.write(corrupt_key)
        logger.warning('Повреждённый ключ сохранён в карантин: %s', quarantine_path)
    except OSError as e:
        logger.error('Не удалось сохранить повреждённый ключ в карантин: %s', e)


def load_or_create_key() -> bytes:
    """
    Загружает мастер-ключ из KEY_FILE или создаёт новый (32 байта).

    Если файл существует, но имеет неверный размер — помещает его в карантин
    и создаёт новый ключ. Устанавливает права 600 на файл ключа для безопасности.
    Результат кэшируется в _MASTER_KEY_CACHE: при повторных вызовах файл
    не читается, если содержимое ключа не изменилось.
    """
    # pylint: disable=global-statement  # обновление модульного кэша ключей
    global _MASTER_KEY_CACHE
    try:
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'rb') as f:
                key = f.read()
                if len(key) == 32:
                    cached_master = _MASTER_KEY_CACHE
                    if cached_master is not None and cached_master == key:
                        logger.debug('Мастер-ключ загружен из кэша')
                        return cached_master
                    _MASTER_KEY_CACHE = key
                    logger.debug('Мастер-ключ загружен из %s', KEY_FILE)
                    return key
            # Повреждённый ключ: не перезаписываем молча, а помещаем в карантин.
            # Иначе все зашифрованные пароли станут нечитаемыми без возможности восстановления.
            _quarantine_corrupt_key(key)
            logger.error(
                'Файл ключа %s повреждён (размер %d байт вместо 32). '
                'Ключ перемещён в карантин, создан новый. '
                'Зашифрованные пароли потребуют повторного ввода.',
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
        _MASTER_KEY_CACHE = key
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
    Соль изменилась — сбрасываем кэш производного ключа.
    """
    reset_key_cache()
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
    Результат кэшируется по паре (master_key, salt) — PBKDF2 выполняется
    только при первом обращении к конкретной паре.
    """
    salt = _load_salt()
    cache_key = (master_key, salt)
    cached = _DERIVED_KEY_CACHE.get(cache_key)
    if cached is not None:
        logger.debug('Ключ шифрования получен из кэша PBKDF2')
        return cached
    derived = pbkdf2_hmac('sha256', master_key, salt, PBKDF2_ITERATIONS, dklen=32)
    _DERIVED_KEY_CACHE[cache_key] = derived
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
    assert AESGCM is not None
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
    assert AESGCM is not None
    try:
        master_key = load_or_create_key()
        aes_key = _derive_key(master_key)
        aesgcm = AESGCM(aes_key)

        raw = base64.b64decode(ciphertext_b64)
        # Первые 12 байт — IV, остальное — ciphertext + GCM auth tag (16 байт)
        iv, ciphertext = raw[:12], raw[12:]
        plaintext = aesgcm.decrypt(iv, ciphertext, None).decode()
        return plaintext
    except UnicodeDecodeError as e:
        # Расшифровано, но не является валидной UTF-8 строкой
        logger.error(
            'Ошибка расшифровки данных: неверная кодировка: %s',
            e, exc_info=True,
        )
        raise
    except (binascii.Error, ValueError) as e:
        # Битый base64 или неверный формат — данные повреждены, ключ цел
        logger.error(
            'Ошибка расшифровки данных: неверный формат шифротекста: %s',
            e, exc_info=True,
        )
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: InvalidTag и др.
        # InvalidTag (повреждённый шифротекст/ключ) и прочие крипто-ошибки.
        # Детали ключа/шифротекста в лог не попадают — только текст исключения.
        logger.error(
            'Ошибка расшифровки данных (возможно, повреждён ключ или '
            'шифротекст): %s', e, exc_info=True,
        )
        raise
