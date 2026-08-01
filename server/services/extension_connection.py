"""
Отслеживание подключения расширения к бэкенду.

Единственная ответственность: учёт активных SSE-соединений от расширения
и предоставление текущего состояния подключения для UI (системный трей).

Расширение держит постоянное SSE-соединение к /api/events (service-worker.js).
Пока хотя бы одно такое соединение активно — считаем, что расширение
подключено к бэкенду.

Использование:
  from server.services.extension_connection import (
      mark_connected, mark_disconnected, is_extension_connected,
  )
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger('flowlink.extension_connection')

# Счётчик активных SSE-соединений от расширения.
# Защищён блокировкой: handle_sse выполняется в asyncio-потоке,
# а чтение состояния может происходить из потока трея (tkinter).
# pylint: disable=invalid-name — изменяемая глобальная переменная,
# а не константа (snake_case отражает mutable-состояние)
_active_connections = 0  # pylint: disable=invalid-name
_lock = threading.Lock()


def mark_connected() -> None:
    """Регистрирует новое активное SSE-соединение от расширения."""
    # Изменяем mutable-счётчик под блокировкой (см. шапку файла):
    # глобальное состояние неизбежно, т.к. счётчик живёт на уровне модуля.
    global _active_connections  # pylint: disable=global-statement
    global _active_connections  # pylint: disable=global-statement
    with _lock:
        _active_connections += 1
        logger.debug(
            'Расширение подключено (активных SSE-соединений: %d)',
            _active_connections,
        )


def mark_disconnected() -> None:
    """Регистрирует закрытие SSE-соединения от расширения."""
    # Изменяем mutable-счётчик под блокировкой (см. шапку файла):
    # глобальное состояние неизбежно, т.к. счётчик живёт на уровне модуля.
    global _active_connections  # pylint: disable=global-statement
    global _active_connections  # pylint: disable=global-statement
    with _lock:
        if _active_connections > 0:
            _active_connections -= 1
        else:
            logger.warning(
                'mark_disconnected: счётчик уже равен нулю — '
                'некорректное закрытие SSE-соединения',
            )
        logger.debug(
            'Расширение отключено (активных SSE-соединений: %d)',
            _active_connections,
        )


def is_extension_connected() -> bool:
    """
    Возвращает True, если расширение подключено к бэкенду.

    Расширение считается подключённым, пока активно хотя бы одно
    SSE-соединение к /api/events.
    """
    with _lock:
        return _active_connections > 0
