"""
HTTP API сервер для управления FlowLink Proxy из расширения.

Единственная ответственность: запуск/остановка HTTP-сервера и диспетчеризация запросов.
Обработчики эндпоинтов вынесены в handlers.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from server.servers import handlers
from server.servers.base_server import BaseServer
from server.utils import safe_close_writer
from server.services.debug import mask_sensitive, truncate
from server.services.sse import handle_sse
from server.services.router import MaskRouter

# Обработчики реестра _ROUTES имеют единую сигнатуру
# (data, router, debug, need_update, peername), но не все используют
# каждый параметр — единый контракт реестра важнее отсутствия
# неиспользуемых аргументов у отдельных обработчиков.
# pylint: disable=unused-argument

logger = logging.getLogger('flowlink.api')

MAX_POST_BODY = 10 * 1024 * 1024  # 10 MB


class _RequestTooLarge(Exception):
    """Тело запроса превышает MAX_POST_BODY."""


# Тип обработчика: принимает (data, router, debug, need_update, peername)
# и возвращает dict (код 200) или кортеж (response_body, status_code).
_Handler = Callable[
    [dict, MaskRouter, bool, bool, tuple],
    Awaitable[dict | tuple[dict, int]],
]


async def _handle_config_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/config — получить конфигурацию."""
    return handlers.handle_get_config()


async def _handle_config_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """POST /api/config — обновить конфигурацию."""
    return await handlers.handle_post_config(data, router)


async def _handle_status_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/status — статус gateway."""
    return handlers.handle_get_status(debug, need_update)


async def _handle_enabled_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """POST /api/enabled — глобальный тоггл."""
    return await handlers.handle_post_enabled(data, router)


async def _handle_version_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/version — версия сервера."""
    return handlers.handle_get_version()


async def _handle_ping_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> tuple[dict, int]:
    """POST /api/ping — пинг прокси по proxyId."""
    proxy_id = data.get('proxyId')
    if not isinstance(proxy_id, str):
        return {'error': 'Требуется proxyId'}, 400
    return await handlers.handle_ping(proxy_id, peername)


async def _handle_autostart_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/autostart-browser — состояние автозапуска браузера."""
    return handlers.handle_get_autostart_browser()


async def _handle_autostart_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """POST /api/autostart-browser — установить автозапуск браузера."""
    return await handlers.handle_post_autostart_browser(data)


async def _handle_system_autostart_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/system-autostart — состояние системного автозапуска."""
    return handlers.handle_get_system_autostart()


async def _handle_system_autostart_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """POST /api/system-autostart — установить системный автозапуск."""
    return await handlers.handle_post_system_autostart(data)


async def _handle_browser_path_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/browser-path — путь к браузеру."""
    return handlers.handle_get_browser_path()


async def _handle_browser_path_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> tuple[dict, int]:
    """POST /api/browser-path — сохранить путь к браузеру."""
    return await handlers.handle_post_browser_path(data)


async def _handle_validate_browser_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> tuple[dict, int]:
    """POST /api/validate-browser — проверить путь к браузеру."""
    return handlers.handle_post_validate_browser(data)


async def _handle_detected_browsers_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/detected-browsers — список обнаруженных браузеров."""
    return handlers.handle_get_detected_browsers()


async def _handle_browser_config_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool, peername: tuple,
) -> dict:
    """GET /api/browser-config — конфигурация браузера."""
    return handlers.handle_get_browser_config()


# Таблица маршрутов: (method, path) -> обработчик.
# Единая точка регистрации эндпоинтов (DRY, SOLID).
_ROUTES: dict[tuple[str, str], _Handler] = {
    ('GET', '/api/config'): _handle_config_get,
    ('POST', '/api/config'): _handle_config_post,
    ('GET', '/api/status'): _handle_status_get,
    ('POST', '/api/enabled'): _handle_enabled_post,
    ('GET', '/api/version'): _handle_version_get,
    ('POST', '/api/ping'): _handle_ping_post,
    ('GET', '/api/autostart-browser'): _handle_autostart_get,
    ('POST', '/api/autostart-browser'): _handle_autostart_post,
    ('GET', '/api/system-autostart'): _handle_system_autostart_get,
    ('POST', '/api/system-autostart'): _handle_system_autostart_post,
    ('GET', '/api/browser-path'): _handle_browser_path_get,
    ('POST', '/api/browser-path'): _handle_browser_path_post,
    ('POST', '/api/validate-browser'): _handle_validate_browser_post,
    ('GET', '/api/detected-browsers'): _handle_detected_browsers_get,
    ('GET', '/api/browser-config'): _handle_browser_config_get,
}


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
            except (ValueError, IndexError) as e:
                # Некорректный Content-Length — логируем и игнорируем (тело не читаем)
                logger.debug('API: некорректный Content-Length от %s: %r (%s)',
                             peername, header_line, e)

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
) -> None:
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
      GET  /api/system-autostart    — статус автозапуска с системой
      POST /api/system-autostart    — вкл/выкл автозапуск с системой
      GET  /api/browser-path        — текущий путь к браузеру
      POST /api/browser-path        — сохранить путь к браузеру (с валидацией)
      POST /api/validate-browser    — валидировать путь без сохранения
      GET  /api/detected-browsers   — список обнаруженных браузеров
      GET  /api/browser-config      — полная конфигурация браузера
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

            handler = _ROUTES.get((method, path))
            if handler is None:
                status_code = 404
                response_body = {'error': f'Не найдено: {method} {path}'}
                logger.warning('API: неизвестный запрос %s %s от %s',
                               method, path, peername)
                return status_code, response_body

            # Единая точка вызова обработчика: парсинг JSON и передача контекста
            data = json.loads(body) if body else {}
            result = await handler(
                data, self._router, self._debug, self._need_update, peername,
            )
            if isinstance(result, tuple):
                # Обработчики возвращают (response_body, status_code)
                response_body, status_code = result
            else:
                status_code, response_body = 200, result
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
    ) -> None:
        """Диспетчеризует входящие HTTP-запросы к API."""
        peername = writer.get_extra_info('peername', ('?', 0))
        try:
            method, path, body = await _parse_http_request(reader, peername)
            if method is None or path is None:
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
                # Маскируем чувствительные поля (пароли, логины) перед логированием
                resp_str = mask_sensitive(
                    truncate(json.dumps(response_body, ensure_ascii=False))
                )
                logger.debug('API <<< %s %s -> %d body: %s',
                             method, path, status_code, resp_str)

        except _RequestTooLarge:
            await _build_response(
                writer, 413,
                {'error': f'Тело запроса слишком большое '
                          f'(максимум {MAX_POST_BODY} байт)'},
            )
        except asyncio.TimeoutError:
            logger.debug('API: таймаут ожидания запроса')
        except (ConnectionError, OSError,
                asyncio.IncompleteReadError) as e:
            logger.error('API ошибка: %s', e, exc_info=True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Страховка от непредвиденных ошибок: не роняем сервер,
            # а отвечаем 500 и логируем полный стек.
            logger.error('API: непредвиденная ошибка: %s', e, exc_info=True)
            try:
                await _build_response(
                    writer, 500,
                    {'error': 'Внутренняя ошибка сервера'},
                )
            except (ConnectionError, OSError):
                logger.debug('API: клиент отключился при отправке 500')
        finally:
            safe_close_writer(writer)
