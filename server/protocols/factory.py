"""
Фабрика протоколов.

Выбирает реализацию ProxyProtocol по типу прокси из конфига.
Использует реестр протоколов (Open/Closed принцип SOLID):
новый протокол добавляется регистрацией класса в _PROTOCOLS.
"""

from server.protocols.base import ProxyProtocol
from server.protocols.socks5 import Socks5Protocol

# Реестр протоколов: тип -> класс реализации.
# Единая точка регистрации новых протоколов (DRY, SOLID).
_PROTOCOLS: dict[str, type[ProxyProtocol]] = {
    'socks5': Socks5Protocol,
}


def get_protocol(config: dict) -> ProxyProtocol:
    """
    Возвращает экземпляр протокола для переданной конфигурации прокси.

    Args:
        config: Словарь с полями type, host, port, username, password.

    Returns:
        Экземпляр ProxyProtocol.

    Raises:
        ValueError: если тип протокола неизвестен.
    """
    proto_type = config.get('type', 'socks5')

    protocol_cls = _PROTOCOLS.get(proto_type)
    if protocol_cls is None:
        raise ValueError(f'Неизвестный тип прокси-протокола: {proto_type}')

    return protocol_cls(config)
