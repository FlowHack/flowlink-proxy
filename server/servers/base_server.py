"""
Базовый класс для asyncio-серверов FlowLink Proxy.

Содержит общий start()/stop() boilerplate.
Единственная ответственность: запуск/остановка TCP-сервера.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod


def safe_close_writer(writer: asyncio.StreamWriter | None) -> None:
    """Безопасно закрывает writer, игнорируя ошибки."""
    if writer is None:
        return
    try:
        writer.close()
    except (ConnectionError, OSError):
        pass


class BaseServer(ABC):
    """
    Базовый TCP-сервер на asyncio.

    Предоставляет стандартный жизненный цикл: start() — запуск, stop() — остановка.
    Конкретная логика обработки клиента реализуется в _handle_client() подкласса.
    """

    def __init__(self, host: str, port: int, name: str):
        """
        Args:
            host: Интерфейс для прослушивания (127.0.0.1).
            port: Порт для прослушивания.
            name: Имя сервера (используется в логах: flowlink.<name>).
        """
        self._host = host
        self._port = port
        self._name = name
        self._server: asyncio.AbstractServer | None = None

    @abstractmethod
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Обрабатывает одно входящее подключение. Должен быть переопределён в подклассе."""
        raise NotImplementedError

    async def start(self) -> None:
        """Запускает TCP-сервер на self._host:self._port."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )
        logger = logging.getLogger(f'flowlink.{self._name}')
        logger.info('%s сервер запущен на %s:%s', self._name.capitalize(), self._host, self._port)

    async def stop(self) -> None:
        """Корректно останавливает сервер: закрывает все подключения."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger = logging.getLogger(f'flowlink.{self._name}')
            logger.info('%s сервер остановлен', self._name.capitalize())
