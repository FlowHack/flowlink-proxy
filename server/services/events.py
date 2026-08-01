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


def get_queue() -> asyncio.Queue:
    """Возвращает глобальную SSE-очередь."""
    return SSE_QUEUE


async def emit_event(event_type: str, data: dict) -> None:
    """
    Кладёт событие в SSE-очередь (неблокирующая отправка).

    Если очередь переполнена — событие отбрасывается с предупреждением.
    """
    try:
        get_queue().put_nowait({'event': event_type, 'data': data})
    except asyncio.QueueFull:
        logger.warning('SSE-очередь переполнена (%d событий), событие %s отброшено',
                       _MAX_QUEUE_SIZE, event_type)
