"""
SSE-обработчик для realtime-уведомлений расширения.

Единственная ответственность: поддержание SSE-соединения и отправка
событий из очереди (см. server.services.events).
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging

from server.services.events import get_queue
from server.services.extension_connection import (mark_connected,
                                                  mark_disconnected)
from server.utils import cors_allow_origin

logger = logging.getLogger('flowlink.sse')

# Таймаут keepalive для SSE (секунды) — если очередь пуста дольше этого,
# отправляется комментарий для поддержания соединения
_SSE_KEEPALIVE_TIMEOUT = 30


def _sse_headers(origin: str | None) -> bytes:
    """Собирает HTTP-заголовки SSE-ответа с учётом CORS-allowlist.

    Заголовок доступа добавляется только для расширений Chrome
    (chrome-extension://<id>), остальным источникам CORS не отдаётся.
    """
    headers = (
        'HTTP/1.1 200 OK\r\n'
        'Content-Type: text/event-stream\r\n'
        'Cache-Control: no-cache\r\n'
        'Connection: keep-alive\r\n'
    )
    headers += cors_allow_origin(origin)
    headers += '\r\n'
    return headers.encode()


async def handle_sse(
    writer: asyncio.StreamWriter,
    auth_token: str | None = None,
    token: str | None = None,
    origin: str | None = None,
) -> None:
    """
    Держит SSE-соединение открытым, отправляя события из очереди.

    При переподключении клиента старые события из очереди отбрасываются,
    чтобы избежать «лавины» устаревших уведомлений.

    Формат:
      event: <type>\n
      data: <json>\n\n

    Args:
        writer: asyncio StreamWriter для отправки данных.
        auth_token: Токен аутентификации API. Если задан — соединение
            открывается только при совпадении с token.
        token: Токен из query-параметра '?token=' запроса (EventSource
            не позволяет задавать заголовки).
        origin: Заголовок Origin запроса — для CORS-allowlist.
    """
    peername = writer.get_extra_info('peername', ('?', 0))
    # Проверка токена до отправки каких-либо данных: при несовпадении
    # соединение закрывается без единого байта ответа
    if auth_token is not None and not hmac.compare_digest(token or '', auth_token):
        logger.warning(
            'SSE: отказ в доступе (неверный токен) от %s', peername
        )
        return
    queue = get_queue()
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
        writer.write(_sse_headers(origin))
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
            try:
                payload = (
                    f'event: {event["event"]}\n'
                    f'data: {json.dumps(event["data"], ensure_ascii=False)}\n\n'
                )
            except (TypeError, ValueError) as e:
                # Несериализуемые данные не должны ронять SSE-цикл
                logger.error('SSE: не удалось сериализовать событие %s: %s',
                             event.get('event'), e)
                continue
            try:
                writer.write(payload.encode())
                await writer.drain()
            except (OSError, ConnectionError):
                logger.debug('SSE: клиент %s отключился', peername)
                break
    except asyncio.CancelledError:
        logger.debug('SSE: соединение %s отменено', peername)
    finally:
        # Регистрируем отключение расширения (для индикации в системном трее)
        mark_disconnected()
        try:
            writer.close()
        except OSError as e:
            logger.debug('SSE: ошибка закрытия writer для %s: %s', peername, e)
        logger.debug('SSE: клиент %s отключён', peername)
