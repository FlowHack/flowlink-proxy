"""
Пакет протоколов прокси.

Каждый файл — реализация одного прокси-протокола (SOCKS5, MTProto, SOCKS4 и т.д.).
Все протоколы реализуют интерфейс ProxyProtocol из .base.
"""

from server.protocols.base import ProxyProtocol, ProxyError
from server.protocols.factory import get_protocol

__all__ = ['ProxyProtocol', 'ProxyError', 'get_protocol']
