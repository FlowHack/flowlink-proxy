"""
Константы протокола SOCKS5.

Единый источник истины для всех констант SOCKS5,
используемых в Socks5Protocol и MockSocks5Server (DRY).
"""

# Версия протокола SOCKS5
SOCKS5_VERSION = 0x05

# Команды
CMD_CONNECT = 0x01

# Типы адресов (ATYP)
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03

# Методы аутентификации
METHOD_NO_AUTH = 0x00
METHOD_USERPASS = 0x02
METHOD_NO_ACCEPTABLE = 0xFF

# Версия аутентификации username/password
USERPASS_VERSION = 0x01
USERPASS_SUCCESS = 0x00

# Зарезервированный байт (RSV)
SOCKS5_RSV = 0x00

# Код успешного ответа
SOCKS5_SUCCESS = 0x00

# Коды ошибок SOCKS5 (REP)
SOCKS5_ERRORS = {
    0x01: 'Общая ошибка SOCKS-сервера',
    0x02: 'Соединение запрещено правилами',
    0x03: 'Сеть недоступна',
    0x04: 'Хост недоступен',
    0x05: 'Соединение отклонено',
    0x06: 'Истёк TTL',
    0x07: 'Команда не поддерживается',
    0x08: 'Тип адреса не поддерживается',
}
