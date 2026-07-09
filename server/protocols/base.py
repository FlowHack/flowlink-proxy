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


class ProxyProtocol(ABC):
    """Интерфейс прокси-протокола."""

    def __init__(self, config: dict):
        self._config = config

    @abstractmethod
    async def connect(
        self,
        target_host: str,
        target_port: int,
        timeout: float = 10,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Устанавливает туннель до target_host:target_port через прокси.

        Returns:
            (reader, writer) — асинхронный поток для передачи данных.

        Raises:
            ProxyError: при ошибке соединения.
        """
        raise NotImplementedError

    @abstractmethod
    async def ping(
        self,
        timeout: float = 5,
    ) -> bool:
        """
        Проверяет доступность прокси-сервера (handshake без CONNECT).

        Returns:
            True если прокси ответил, иначе False.
        """
        raise NotImplementedError
