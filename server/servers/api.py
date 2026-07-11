"""
HTTP API сервер для управления FlowLink Proxy из расширения.

Единственная ответственность: запуск/остановка HTTP-сервера и диспетчеризация запросов.
Обработчики эндпоинтов вынесены в handlers.py.
"""

import asyncio
import json
import logging

from server.servers import handlers
from server.servers.base_server import BaseServer, safe_close_writer
from server.services.debug import mask_sensitive, truncate
from server.services.events import handle_sse
from server.services.router import MaskRouter

logger = logging.getLogger('flowlink.api')

MAX_POST_BODY = 10 * 1024 * 1024  # 10 MB


class _RequestTooLarge(Exception):
    """Тело запроса превышает MAX_POST_BODY."""


async def _parse_http_request(
    reader: asyncio.StreamReader,
    peername: tuple,
) -> tuple[str | None, str | None, bytes]:
    """Парсит HTTP-запрос: читает request-line, заголовки, тело."""
    request_line = await asyncio.wait_for(reader.readline(), timeout=10)
    if not request_line:
        return None, None, b''

    parts = request_line.decode(errors='ignore').strip().split(' ')
    if len(parts) < 2:
        logger.warning('API: неверный формат запроса от %s', peername)
        return None, None, b''

    method = parts[0].upper()
    path = parts[1]

    content_length = 0
    while True:
        line = await reader.readline()
        if not line or line == b'\r\n':
            break
        header_line = line.decode().strip().lower()
        if header_line.startswith('content-length:'):
            try:
                content_length = int(header_line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass

    if content_length > MAX_POST_BODY:
        logger.warning('API: слишком большой запрос (%s байт) от %s',
                       content_length, peername)
        raise _RequestTooLarge()

    body = b''
    if content_length > 0:
        body = await asyncio.wait_for(
            reader.readexactly(content_length), timeout=30,
        )

    return method, path, body


async def _build_response(
    writer: asyncio.StreamWriter,
    status_code: int,
    response_body: dict,
):
    """Собирает и отправляет HTTP JSON-ответ."""
    try:
        response_json = json.dumps(response_body, ensure_ascii=False)
    except TypeError:
        logger.error('API: не удалось сериализовать ответ')
        response_json = json.dumps({'error': 'Внутренняя ошибка сервера'}, ensure_ascii=False)
    reason = {
        200: 'OK', 400: 'Bad Request', 404: 'Not Found',
        413: 'Request Entity Too Large',
    }.get(status_code, 'Error')
    response_headers = (
        f'HTTP/1.1 {status_code} {reason}\r\n'
        f'Content-Type: application/json\r\n'
        f'Content-Length: {len(response_json.encode())}\r\n'
        f'Access-Control-Allow-Origin: *\r\n'
        f'Connection: close\r\n'
        f'\r\n'
    )
    writer.write(response_headers.encode() + response_json.encode())
    await writer.drain()


class ApiServer(BaseServer):
    """
    HTTP API сервер для управления FlowLink Proxy.

    Эндпоинты:
      GET  /api/config              — получить конфиг
      POST /api/config              — обновить конфиг
      GET  /api/status              — статус gateway
      GET  /api/version             — версия сервера
      POST /api/ping                — пинг прокси по proxyId
      POST /api/enabled             — глобальный тоггл
      GET  /api/autostart-browser   — настройка автозапуска браузера
      POST /api/autostart-browser   — обновить настройку автозапуска
    """

    def __init__(self, router: MaskRouter, host: str = '127.0.0.1',
                 port: int = 8081, debug: bool = False,
                 need_update: bool = False):
        """
        Args:
            router: Экземпляр MaskRouter (для refresh после сохранения конфига).
            host: Интерфейс (по умолч. localhost).
            port: Порт API (по умолч. 8081).
            debug: Включает отладку в статусе.
            need_update: Флаг симуляции обновления (передаётся в статус).
        """
        super().__init__(host=host, port=port, name='api')
        self._router = router
        self._debug = debug
        self._need_update = need_update

    async def _route_request(
        self, method: str, path: str, body: bytes,
        peername: tuple, writer: asyncio.StreamWriter,
    ) -> tuple[int, dict] | None:
        """Маршрутизирует запрос к обработчику,
        возвращает (код, тело) или None (SSE)."""
        try:
            if path == '/api/events' and method == 'GET':
                await handle_sse(writer)
                return None

            status_code = 200
            if path == '/api/config' and method == 'GET':
                response_body = handlers.handle_get_config()
            elif path == '/api/config' and method == 'POST':
                data = json.loads(body)
                response_body = await handlers.handle_post_config(
                    data, self._router,
                )
            elif path == '/api/status' and method == 'GET':
                response_body = handlers.handle_get_status(
                    self._debug, self._need_update,
                )
            elif path == '/api/enabled' and method == 'POST':
                data = json.loads(body)
                response_body = await handlers.handle_post_enabled(
                    data, self._router,
                )
            elif path == '/api/version' and method == 'GET':
                response_body = handlers.handle_get_version()
            elif path == '/api/ping' and method == 'POST':
                data = json.loads(body)
                proxy_id = data.get('proxyId')
                response_body, status_code = await handlers.handle_ping(
                    proxy_id, peername,
                )
            elif path == '/api/autostart-browser' and method == 'GET':
                response_body = handlers.handle_get_autostart_browser()
            elif path == '/api/autostart-browser' and method == 'POST':
                data = json.loads(body)
                response_body = await handlers.handle_post_autostart_browser(
                    data,
                )
            else:
                status_code = 404
                response_body = {'error': f'Не найдено: {method} {path}'}
                logger.warning('API: неизвестный запрос %s %s от %s',
                               method, path, peername)
            return status_code, response_body
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning('API: неверный запрос от %s: %s', peername, e)
            return 400, {'error': 'Неверный запрос'}
        except (OSError, RuntimeError) as e:
            logger.error('API: ошибка сервера от %s: %s', peername, e, exc_info=True)
            msg = (
                'Внутренняя ошибка сервера. '
                'Если проблема повторяется, '
                'обратитесь в поддержку: flowlink.proxy@atomicmail.io'
            )
            return 500, {'error': msg}

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ):
        """Диспетчеризует входящие HTTP-запросы к API."""
        peername = writer.get_extra_info('peername', ('?', 0))
        try:
            method, path, body = await _parse_http_request(reader, peername)
            if method is None:
                writer.close()
                return

            logger.debug('API: %s %s от %s', method, path, peername)

            if self._debug and logger.isEnabledFor(logging.DEBUG) and body:
                body_str = body.decode('utf-8', errors='replace')
                if path == '/api/config' and method == 'POST':
                    body_str = mask_sensitive(body_str)
                logger.debug('API >>> %s %s body: %s',
                             method, path, body_str)

            result = await self._route_request(method, path, body,
                                               peername, writer)
            if result is None:
                return
            status_code, response_body = result

            await _build_response(writer, status_code, response_body)

            if self._debug and logger.isEnabledFor(logging.DEBUG):
                resp_str = truncate(json.dumps(response_body,
                                               ensure_ascii=False))
                logger.debug('API <<< %s %s -> %d body: %s',
                             method, path, status_code, resp_str)

        except _RequestTooLarge:
            await _build_response(
                writer, 413,
                {'error': f'Request body too large '
                          f'(max {MAX_POST_BODY} bytes)'},
            )
        except asyncio.TimeoutError:
            logger.debug('API: таймаут ожидания запроса')
        except (ConnectionError, OSError,
                asyncio.IncompleteReadError) as e:
            logger.error('API ошибка: %s', e, exc_info=True)
        finally:
            safe_close_writer(writer)
