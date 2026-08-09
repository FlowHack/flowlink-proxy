"""
SSE-шина событий для realtime-уведомлений расширения.

Единственная ответственность: управление очередью событий Server-Sent Events.
SSE-обработчик (handle_sse) вынесен в server.services.sse.

Использование:
  from server.services.events import emit_event
  await emit_event('config_changed', {})
"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger('flowlink.events')

# Максимальный размер очереди (защита от утечки памяти при отключённом клиенте)
_MAX_QUEUE_SIZE = 100
SSE_QUEUE: asyncio.Queue[dict] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)

# Счётчик отброшенных из-за переполнения событий. Позволяет диагностировать
# потерю уведомлений расширения (например, config_changed) в логах и API.
_DROPPED_EVENTS_COUNT = 0


def get_dropped_events_count() -> int:
    """Возвращает число отброшенных из-за переполнения SSE-событий."""
    return _DROPPED_EVENTS_COUNT


def get_queue() -> asyncio.Queue:
    """Возвращает глобальную SSE-очередь."""
    return SSE_QUEUE


async def emit_event(event_type: str, data: dict) -> None:
    """
    Кладёт событие в SSE-очередь (неблокирующая отправка).

    Если очередь переполнена — событие отбрасывается, счётчик потерь
    увеличивается, в лог пишется предупреждение с накопленной статистикой.
    """
    global _DROPPED_EVENTS_COUNT  # pylint: disable=global-statement  # счётчик — глобальное состояние шины
    try:
        get_queue().put_nowait({'event': event_type, 'data': data})
    except asyncio.QueueFull:
        _DROPPED_EVENTS_COUNT += 1
        logger.warning(
            'SSE-очередь переполнена (%d событий), событие %s отброшено, '
            'всего отброшено: %d',
            _MAX_QUEUE_SIZE, event_type, _DROPPED_EVENTS_COUNT,
        )
