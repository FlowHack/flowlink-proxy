"""
Базовый класс для всех прокси-протоколов.

Определяет интерфейс, который обязан реализовать каждый протокол.
Для добавления нового протокола:
  1. Создать файл server/protocols/<protocol>.py
  2. Реализовать класс, наследующий ProxyProtocol
  3. Зарегистрировать в factory.py
"""

import asyncio
from abc import ABC, abstractmethod


class ProxyError(Exception):
    """Базовая ошибка прокси-протокола."""
    pass


class ProxyProtocol(ABC):
    """Интерфейс прокси-протокола."""

    def __init__(self, config: dict):
        self._config = config

    @abstractmethod
    async def connect(
        self,
        proxy_host: str,
        proxy_port: int,
        target_host: str,
        target_port: int,
        username: str = '',
        password: str = '',
        timeout: float = 10,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Устанавливает туннель до target_host:target_port через прокси.

        Returns:
            (reader, writer) — асинхронный поток для передачи данных.

        Raises:
            ProxyError: при ошибке соединения.
        """
        ...

    @abstractmethod
    async def ping(
        self,
        proxy_host: str,
        proxy_port: int,
        username: str = '',
        password: str = '',
        timeout: float = 5,
    ) -> bool:
        """
        Проверяет доступность прокси-сервера (handshake без CONNECT).

        Returns:
            True если прокси ответил, иначе False.
        """
        ...
