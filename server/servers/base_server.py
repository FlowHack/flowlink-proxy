"""
Базовый класс для asyncio-серверов FlowLink Proxy.

Содержит общий start()/stop() boilerplate.
Единственная ответственность: запуск/остановка TCP-сервера.
"""

import asyncio
import logging
from abc import ABC, abstractmethod


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
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Обрабатывает одно входящее подключение. Должен быть переопределён в подклассе."""
        ...

    async def start(self):
        """Запускает TCP-сервер на self._host:self._port."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )
        logger = logging.getLogger(f'flowlink.{self._name}')
        logger.info(f'{self._name.capitalize()} сервер запущен на {self._host}:{self._port}')

    async def stop(self):
        """Корректно останавливает сервер: закрывает все подключения."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger = logging.getLogger(f'flowlink.{self._name}')
            logger.info(f'{self._name.capitalize()} сервер остановлен')
