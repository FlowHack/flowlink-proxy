"""
Генерация фиктивных прокси для тестирования в debug-режиме.

Используется при запуске с --count-proxy N для создания N фиктивных прокси
с рандомными IP:port и логинами/паролями. Позволяет тестировать маршрутизацию,
логирование и расширение без реальных прокси.

Единственная ответственность: генерация тестовых данных.
"""

import logging
import random
import string
import uuid

logger = logging.getLogger('flowlink.fake_proxies')

# Префикс для ID фиктивных прокси (позволяет отличать от реальных)
_PROXY_ID_PREFIX = 'fake-'
_MASK_ID_PREFIX = 'fake-mask-'

# Диапазон портов для фиктивных прокси
_MIN_PORT = 10000
_MAX_PORT = 65000

# Диапазон IP-адресов для тестирования (RFC 5737, documentation range)
# 198.51.100.0/24 — зарезервирован для документации/тестирования
_IP_OCTETS_PREFIX = (198, 51, 100)

# Длина генерируемых логинов и паролей (после префикса)
_CREDENTIAL_LEN = 8


def _random_id() -> str:
    """Генерирует короткий уникальный идентификатор из hex-символов."""
    return uuid.uuid4().hex[:12]


def _random_credential(prefix: str) -> str:
    """
    Генерирует случайный логин или пароль.

    Формат: <prefix>-<8_hex_символов>
    Пример: fake-user-a1b2c3d4
    """
    suffix = ''.join(random.choices(string.hexdigits[:16], k=_CREDENTIAL_LEN))
    return f'{prefix}-{suffix}'


def _random_ip(index: int) -> str:
    """
    Генерирует тестовый IP-адрес из диапазона 198.51.100.X.

    Последний октет = (index + 1) % 255, чтобы избежать 0.
    Используется documentation-диапазон (RFC 5737) — не конфликтует
    с реальными адресами.

    Args:
        index: Порядковый номер прокси (0-based).

    Returns:
        IP-адрес в формате строки, например '198.51.100.1'.
    """
    last_octet = (index + 1) % 255
    if not last_octet:
        last_octet = 1
    return f'{_IP_OCTETS_PREFIX[0]}.{_IP_OCTETS_PREFIX[1]}.{_IP_OCTETS_PREFIX[2]}.{last_octet}'


def _random_port() -> int:
    """Генерирует случайный порт в диапазоне 10000–65000."""
    return random.randint(_MIN_PORT, _MAX_PORT)


def generate_fake_proxies(count: int) -> dict:
    """
    Генерирует набор фиктивных прокси и масок для тестирования.

    Каждый фиктивный прокси получает:
    - Уникальный proxyId (prefixed 'fake-')
    - IP-адрес из тестового диапазона 198.51.100.X (RFC 5737)
    - Случайный порт 10000–65000
    - Логин/пароль вида 'fake-user-XXXX' / 'fake-pass-XXXX'
    - Маску вида '*.{последний_октет}.test' (wildcard)

    Args:
        count: Количество фиктивных прокси для генерации (>= 1).

    Returns:
        Словарь {'proxies': [...], 'masks': [...]} в формате конфига.

    Raises:
        ValueError: Если count < 1.
    """
    if count < 1:
        raise ValueError(
            f'Количество фиктивных прокси должно быть >= 1, получено: {count}'
        )

    proxies = []
    masks = []

    for i in range(count):
        proxy_id = _PROXY_ID_PREFIX + _random_id()
        host = _random_ip(i)
        port = _random_port()
        username = _random_credential('fake-user')
        password = _random_credential('fake-pass')

        proxy = {
            'proxyId': proxy_id,
            'host': host,
            'port': port,
            'username': username,
            'password': password,
            'label': f'Тестовый прокси #{i + 1}',
            'isEnabled': True,
        }
        proxies.append(proxy)

        mask_id = _MASK_ID_PREFIX + _random_id()
        last_octet = host.rsplit('.', maxsplit=1)[-1]
        regex_string = f'*.{last_octet}.test'
        mask = {
            'maskId': mask_id,
            'proxyId': proxy_id,
            'regexString': regex_string,
        }
        masks.append(mask)

    logger.info(
        'Сгенерировано %d фиктивных прокси (диапазон 198.51.100.X)',
        count,
    )
    for p in proxies:
        logger.debug(
            '  фиктивный прокси %s — %s:%s (маска: *.%s.test)',
            p['proxyId'], p['host'], p['port'],
            p['host'].rsplit('.', maxsplit=1)[-1],
        )

    return {'proxies': proxies, 'masks': masks}
