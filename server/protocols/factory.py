"""
Фабрика протоколов.

Выбирает реализацию ProxyProtocol по типу прокси из конфига.
"""

from server.protocols.base import ProxyProtocol


def get_protocol(config: dict) -> ProxyProtocol:
    """
    Возвращает экземпляр протокола для переданной конфигурации прокси.

    Args:
        config: Словарь с полями type, host, port, username, password.

    Returns:
        Экземпляр ProxyProtocol.
    """
    proto_type = config.get('type', 'socks5')

    if proto_type == 'socks5':
        from server.protocols.socks5 import Socks5Protocol
        return Socks5Protocol(config)

    raise ValueError(f'Неизвестный тип прокси-протокола: {proto_type}')
