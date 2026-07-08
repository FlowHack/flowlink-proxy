"""
SSE-шина событий для realtime-уведомлений расширения.

Единственная ответственность: управление очередью событий Server-Sent Events.

Использование:
  from server.services.events import emit_event
  await emit_event('config_changed', {})
"""
import asyncio
import json
import logging

logger = logging.getLogger('flowlink.events')

_sse_queue: asyncio.Queue[dict] | None = None


def get_queue() -> asyncio.Queue:
    """Возвращает глобальную SSE-очередь (ленивая инициализация)."""
    global _sse_queue
    if _sse_queue is None:
        _sse_queue = asyncio.Queue()
    return _sse_queue


async def emit_event(event_type: str, data: dict):
    """Кладёт событие в SSE-очередь (неблокирующая отправка)."""
    try:
        get_queue().put_nowait({'event': event_type, 'data': data})
    except asyncio.QueueFull:
        pass


SSE_HEADERS = (
    'HTTP/1.1 200 OK\r\n'
    'Content-Type: text/event-stream\r\n'
    'Cache-Control: no-cache\r\n'
    'Connection: keep-alive\r\n'
    'Access-Control-Allow-Origin: *\r\n'
    '\r\n'
)


async def handle_sse(writer: asyncio.StreamWriter):
    """
    Держит SSE-соединение открытым, отправляя события из очереди.

    Формат:
      event: <type>\n
      data: <json>\n\n

    Args:
        writer: asyncio StreamWriter для отправки данных.
    """
    queue = get_queue()
    peername = writer.get_extra_info('peername', ('?', 0))
    logger.debug('SSE: клиент %s подключился', peername)

    try:
        writer.write(SSE_HEADERS.encode())
        await writer.drain()

        while True:
            event = await queue.get()
            payload = 'event: {}\ndata: {}\n\n'.format(
                event['event'],
                json.dumps(event['data'], ensure_ascii=False),
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
        try:
            writer.close()
        except Exception:
            pass
        logger.debug('SSE: клиент %s отключён', peername)
