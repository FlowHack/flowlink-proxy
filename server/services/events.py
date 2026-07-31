"""
SSE-шина событий для realtime-уведомлений расширения.

Единственная ответственность: управление очередью событий Server-Sent Events.

Использование:
  from server.services.events import emit_event
  await emit_event('config_changed', {})
"""
from __future__ import annotations

import asyncio
import json
import logging

from server.services.extension_connection import (mark_connected,
                                                  mark_disconnected)

logger = logging.getLogger('flowlink.events')

# Максимальный размер очереди (защита от утечки памяти при отключённом клиенте)
_MAX_QUEUE_SIZE = 100
# Таймаут keepalive для SSE (секунды) — если очередь пуста дольше этого,
# отправляется комментарий для поддержания соединения
_SSE_KEEPALIVE_TIMEOUT = 30
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


SSE_HEADERS = (
    'HTTP/1.1 200 OK\r\n'
    'Content-Type: text/event-stream\r\n'
    'Cache-Control: no-cache\r\n'
    'Connection: keep-alive\r\n'
    'Access-Control-Allow-Origin: *\r\n'
    '\r\n'
)


async def handle_sse(writer: asyncio.StreamWriter) -> None:
    """
    Держит SSE-соединение открытым, отправляя события из очереди.

    При переподключении клиента старые события из очереди отбрасываются,
    чтобы избежать «лавины» устаревших уведомлений.

    Формат:
      event: <type>\n
      data: <json>\n\n

    Args:
        writer: asyncio StreamWriter для отправки данных.
    """
    queue = get_queue()
    peername = writer.get_extra_info('peername', ('?', 0))
    logger.debug('SSE: клиент %s подключился', peername)
    # Регистрируем подключение расширения (для индикации в системном трее)
    mark_connected()

    # Очищаем очередь при переподключении (убираем устаревшие события)
    cleared = 0
    while not queue.empty():
        try:
            queue.get_nowait()
            cleared += 1
        except asyncio.QueueEmpty:
            break
    if cleared:
        logger.debug('SSE: очищено %d устаревших событий', cleared)

    try:
        writer.write(SSE_HEADERS.encode())
        await writer.drain()

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_SSE_KEEPALIVE_TIMEOUT)
            except asyncio.TimeoutError:
                try:
                    writer.write(b': keepalive\n\n')
                    await writer.drain()
                except (OSError, ConnectionError):
                    logger.debug('SSE: клиент %s отключился (keepalive)', peername)
                    break
                continue
            payload = (
                f'event: {event["event"]}\n'
                f'data: {json.dumps(event["data"], ensure_ascii=False)}\n\n'
            )
            try:
                writer.write(payload.encode())
                await writer.drain()
            except (OSError, ConnectionError):
                logger.debug('SSE: клиент %s отключился', peername)
                break
    except asyncio.CancelledError:
        pass
    finally:
        # Регистрируем отключение расширения (для индикации в системном трее)
        mark_disconnected()
        try:
            writer.close()
        except OSError:
            pass
        logger.debug('SSE: клиент %s отключён', peername)
