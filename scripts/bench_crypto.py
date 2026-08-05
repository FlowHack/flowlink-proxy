"""
Бенчмарк криптографии FlowLink Proxy: замер ускорения от кэша PBKDF2.

Замеряет время N вызовов encrypt + decrypt до прогрева кэша (холодный
старт — PBKDF2 выполняется) и после (все вызовы берут производный ключ
из кэша). Использует временную директорию для ключа и соли — реальные
данные пользователя не затрагиваются.

Запуск:
    python -m scripts.bench_crypto
    # или
    python scripts/bench_crypto.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

# Добавляем корень репозитория в sys.path, чтобы работал запуск
# «python scripts/bench_crypto.py» из любого каталога.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# pylint: disable=wrong-import-position,import-error  # импорт намеренно после sys.path
from server.config import crypto as crypto_mod  # noqa: E402

# Количество «прокси» и полей для имитации реальной нагрузки.
# Каждый прокси имеет username и password — по 2 поля.
_PROXY_COUNT = 20
_FIELDS_PER_PROXY = 2


def _make_payloads(count: int) -> list[str]:
    """Генерирует строки для шифрования (имитация username/password)."""
    return [f'user{i}_secret_password_{i}' for i in range(count)]


def _run_batch(payloads: list[str]) -> float:
    """Шифрует и расшифровывает каждый payload; возвращает время в секундах.

    Дважды шифрует каждый payload (имитация повторной сериализации
    конфига: шифрование при сохранении + дешифровка при загрузке/refresh).
    """
    start = time.perf_counter()
    encrypted = [crypto_mod.encrypt(p) for p in payloads]
    encrypted += [crypto_mod.encrypt(p) for p in payloads]
    for e in encrypted:
        crypto_mod.decrypt(e)
    return time.perf_counter() - start


def main() -> int:
    """Основная точка входа бенчмарка. Возвращает код завершения."""
    tmpdir = tempfile.mkdtemp(prefix='flowlink-bench-crypto-')
    orig_key_file = crypto_mod.KEY_FILE
    orig_salt_file = crypto_mod.SALT_FILE
    crypto_mod.KEY_FILE = os.path.join(tmpdir, '.flowlink.key')
    crypto_mod.SALT_FILE = os.path.join(tmpdir, '.flowlink.salt')
    try:
        # Инициализируем ключ и соль в изолированной директории.
        # load_or_create_key() сам создаёт ключ и соль при первом запуске.
        crypto_mod.reset_key_cache()
        crypto_mod.load_or_create_key()
        crypto_mod.reset_key_cache()

        payloads = _make_payloads(_PROXY_COUNT * _FIELDS_PER_PROXY)
        # В батче каждый payload шифруется дважды (имитация повторной
        # сериализации конфига), затем каждый шифротекст расшифровывается.
        n_encrypt = len(payloads) * 2

        # Холодный замер: кэш пуст, первый вызов выполняет PBKDF2 (600k итераций)
        cold = _run_batch(payloads)

        # Тёплый замер: производный ключ уже лежит в кэше
        hot = _run_batch(payloads)

        speedup = cold / hot if hot > 0 else float('inf')
        print('=== Бенчмарк криптографии FlowLink Proxy (кэш PBKDF2) ===')
        print(f'Операций в батче: {n_encrypt} encrypt + {n_encrypt} decrypt '
              f'(всего {2 * n_encrypt} операций)')
        print(f'Холодный старт (PBKDF2 выполняется): {cold:.4f} с')
        print(f'Тёплый кэш (производный ключ из кэша): {hot:.4f} с')
        print(f'Ускорение: {speedup:.1f}×')
        return 0
    finally:
        # Восстанавливаем состояние модуля и очищаем временные файлы
        crypto_mod.reset_key_cache()
        crypto_mod.KEY_FILE = orig_key_file
        crypto_mod.SALT_FILE = orig_salt_file
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
