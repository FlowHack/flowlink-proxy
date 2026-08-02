"""
HTTP API сервер для управления FlowLink Proxy из расширения.

Единственная ответственность: запуск/остановка HTTP-сервера и диспетчеризация
запросов.
Обработчики эндпоинтов вынесены в handlers.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from server.servers import handlers
from server.servers.base_server import BaseServer
from server.utils import cors_allow_origin, safe_close_writer
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
# Защита от медленного DoS: максимум 50 заголовков и 16 КБ суммарного размера
MAX_HEADERS = 50
MAX_HEADER_SIZE = 16 * 1024  # 16 КБ
HEADER_READ_TIMEOUT = 10  # секунд на чтение request-line/заголовков


class _RequestTooLarge(Exception):
    """Тело запроса превышает MAX_POST_BODY."""


class _RequestHeaderLimit(Exception):
    """Превышен лимит количества или суммарного размера заголовков."""


class _RequestTimeout(Exception):
    """Таймаут чтения request-line или заголовков запроса."""


# Тип обработчика: принимает (data, router, debug, need_update, peername)
# и возвращает dict (код 200) или кортеж (response_body, status_code).
_Handler = Callable[
    [dict, MaskRouter, bool, bool, tuple],
    Awaitable[dict | tuple[dict, int]],
]


async def _handle_config_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/config — получить конфигурацию."""
    return handlers.handle_get_config()


async def _handle_config_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """POST /api/config — обновить конфигурацию."""
    return await handlers.handle_post_config(data, router)


async def _handle_status_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/status — статус gateway."""
    return handlers.handle_get_status(debug, need_update)


async def _handle_enabled_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """POST /api/enabled — глобальный тоггл."""
    return await handlers.handle_post_enabled(data, router)


async def _handle_version_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/version — версия сервера."""
    return handlers.handle_get_version()


async def _handle_ping_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> tuple[dict, int]:
    """POST /api/ping — пинг прокси по proxyId."""
    proxy_id = data.get('proxyId')
    if not isinstance(proxy_id, str):
        return {'error': 'Требуется proxyId'}, 400
    return await handlers.handle_ping(proxy_id, peername)


async def _handle_autostart_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/autostart-browser — состояние автозапуска браузера."""
    return handlers.handle_get_autostart_browser()


async def _handle_autostart_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """POST /api/autostart-browser — установить автозапуск браузера."""
    return await handlers.handle_post_autostart_browser(data)


async def _handle_system_autostart_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/system-autostart — состояние системного автозапуска."""
    return handlers.handle_get_system_autostart()


async def _handle_system_autostart_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """POST /api/system-autostart — установить системный автозапуск."""
    return await handlers.handle_post_system_autostart(data)


async def _handle_browser_path_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/browser-path — путь к браузеру."""
    return handlers.handle_get_browser_path()


async def _handle_browser_path_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> tuple[dict, int]:
    """POST /api/browser-path — сохранить путь к браузеру."""
    return await handlers.handle_post_browser_path(data)


async def _handle_validate_browser_post(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> tuple[dict, int]:
    """POST /api/validate-browser — проверить путь к браузеру."""
    return handlers.handle_post_validate_browser(data)


async def _handle_detected_browsers_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
) -> dict:
    """GET /api/detected-browsers — список обнаруженных браузеров."""
    return handlers.handle_get_detected_browsers()


async def _handle_browser_config_get(
    data: dict, router: MaskRouter, debug: bool, need_update: bool,
    peername: tuple,
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


def _extract_token_from_query(query: str) -> str | None:
    """Извлекает значение query-параметра token из query-строки.

    Параметр может стоять в любом месте строки запроса:
    '?token=abc', '?a=1&token=abc', '?token=abc&b=2'.
    """
    if not query:
        return None
    for param in query.split('&'):
        if param.startswith('token='):
            return param[len('token='):]
    return None


def _mask_token_in_path(path: str) -> str:
    """Маскирует значение query-параметра token в path для логов."""
    route_path, _, query = path.partition('?')
    if not query:
        return path
    masked = []
    for param in query.split('&'):
        if param.startswith('token='):
            masked.append('token=***')
        else:
            masked.append(param)
    return f'{route_path}?{"&".join(masked)}'


def _parse_header_line(line: bytes) -> tuple[str, str] | None:
    """Разбирает строку HTTP-заголовка на пару (ключ, значение).

    Ключ приводится к нижнему регистру, значение сохраняет исходный
    регистр. Возвращает None, если в строке нет двоеточия.
    """
    text = line.decode(errors='replace').strip()
    if ':' not in text:
        return None
    key, _, value = text.partition(':')
    return key.strip().lower(), value.strip()


async def _read_headers(
    reader: asyncio.StreamReader,
    peername: tuple,
) -> dict[str, str]:
    """Читает HTTP-заголовки до пустой строки.

    Возвращает dict с ключами в нижнем регистре (значения сохраняют
    исходный регистр). Защита от медленного DoS: чтение каждого
    заголовка ограничено таймаутом HEADER_READ_TIMEOUT, количество —
    MAX_HEADERS, суммарный размер — MAX_HEADER_SIZE. При превышении
    лимитов выбрасывается _RequestTimeout или _RequestHeaderLimit.

    Args:
        reader: asyncio StreamReader для чтения данных.
        peername: Кортеж (host, port) клиента — для логов.

    Returns:
        Словарь заголовков с ключами в нижнем регистре.
    """
    headers: dict[str, str] = {}
    header_count = 0
    total_header_size = 0
    try:
        while True:
            line = await asyncio.wait_for(
                reader.readline(), timeout=HEADER_READ_TIMEOUT
            )
            if not line or line == b'\r\n':
                break
            header_count += 1
            total_header_size += len(line)
            if (
                header_count >
                MAX_HEADERS or total_header_size >
                MAX_HEADER_SIZE
            ):
                logger.warning(
                    'API: превышен лимит заголовков (%d шт, %d байт) от %s',
                    header_count, total_header_size, peername,
                )
                raise _RequestHeaderLimit()
            header = _parse_header_line(line)
            if header is not None:
                headers[header[0]] = header[1]
    except asyncio.TimeoutError:
        # Клиент держит соединение, не отправляя пустую строку —
        # защита от медленного DoS: отвечаем 408 Request Timeout.
        logger.warning('API: таймаут чтения заголовков от %s', peername)
        raise _RequestTimeout() from None
    return headers


async def _parse_http_request(
    reader: asyncio.StreamReader,
    peername: tuple,
) -> tuple[str | None, str | None, bytes, dict[str, str]]:
    """Парсит HTTP-запрос: читает request-line, заголовки, тело.

    Возвращает (method, path, body, headers), где headers — dict с
    ключами в нижнем регистре (значения сохраняют исходный регистр).
    Заголовок Origin нужен для CORS-allowlist, X-Auth-Token — для
    проверки токена аутентификации.

    Защита от медленного DoS: чтение request-line и каждого заголовка
    ограничено таймаутом HEADER_READ_TIMEOUT, количество заголовков —
    MAX_HEADERS, суммарный размер — MAX_HEADER_SIZE. При превышении
    лимитов выбрасывается _RequestTimeout или _RequestHeaderLimit.
    """
    try:
        request_line = await asyncio.wait_for(
            reader.readline(), timeout=HEADER_READ_TIMEOUT
        )
    except asyncio.TimeoutError:
        # Клиент не прислал даже request-line — отвечаем 408
        logger.warning('API: таймаут ожидания request-line от %s', peername)
        raise _RequestTimeout() from None
    if not request_line:
        return None, None, b'', {}

    parts = request_line.decode(errors='replace').strip().split(' ')
    if len(parts) < 2:
        logger.warning('API: неверный формат запроса от %s', peername)
        return None, None, b'', {}

    method = parts[0].upper()
    path = parts[1]

    content_length = 0
    headers = await _read_headers(reader, peername)

    # Извлекаем Content-Length из собранных заголовков (ключи в lowercase)
    if 'content-length' in headers:
        try:
            content_length = int(headers['content-length'])
        except ValueError as e:
            # Некорректный Content-Length — логируем и игнорируем
            logger.debug(
                'API: некорректный Content-Length от %s: %r (%s)',
                peername, headers['content-length'], e,
            )

    if content_length > MAX_POST_BODY:
        logger.warning('API: слишком большой запрос (%s байт) от %s',
                       content_length, peername)
        raise _RequestTooLarge()

    body = b''
    if content_length > 0:
        try:
            body = await asyncio.wait_for(
                reader.readexactly(content_length), timeout=30,
            )
        except asyncio.TimeoutError:
            # Клиент медленно передаёт тело запроса — защита от
            # медленного DoS: отвечаем 408 Request Timeout.
            logger.warning('API: таймаут чтения тела запроса от %s', peername)
            raise _RequestTimeout() from None

    return method, path, body, headers


async def _build_response(
    writer: asyncio.StreamWriter,
    status_code: int,
    response_body: dict,
    origin: str | None = None,
) -> None:
    """Собирает и отправляет HTTP JSON-ответ.

    Args:
        writer: asyncio StreamWriter для отправки ответа.
        status_code: HTTP-код ответа.
        response_body: JSON-сериализуемое тело ответа.
        origin: Заголовок Origin запроса — для CORS-allowlist.
    """
    try:
        response_json = json.dumps(response_body, ensure_ascii=False)
    except TypeError:
        logger.error('API: не удалось сериализовать ответ')
        response_json = json.dumps(
            {'error': 'Внутренняя ошибка сервера'},
            ensure_ascii=False
        )
    reason = {
        200: 'OK', 204: 'No Content', 400: 'Bad Request',
        403: 'Forbidden', 404: 'Not Found',
        408: 'Request Timeout', 413: 'Request Entity Too Large',
        422: 'Unprocessable Entity',
    }.get(status_code, 'Error')
    # CORS-allowlist: заголовок доступа добавляется только для
    # расширений Chrome (chrome-extension://<id>)
    cors_headers = cors_allow_origin(origin)
    response_headers = (
        f'HTTP/1.1 {status_code} {reason}\r\n'
        f'Content-Type: application/json\r\n'
        f'Content-Length: {len(response_json.encode())}\r\n'
        f'{cors_headers}'
        f'Connection: close\r\n'
        f'\r\n'
    )
    writer.write(response_headers.encode() + response_json.encode())
    await writer.drain()


async def _build_options_response(
    writer: asyncio.StreamWriter,
    origin: str | None,
) -> None:
    """Отвечает на CORS preflight (OPTIONS) кодом 204.

    Заголовки доступа добавляются только если Origin в allowlist
    (chrome-extension://). Без валидного Origin браузер заблокирует
    фактический запрос, так как Access-Control-Allow-Origin не будет
    присутствовать в ответе.
    """
    cors_headers = cors_allow_origin(origin)
    headers = (
        'HTTP/1.1 204 No Content\r\n'
        f'{cors_headers}'
        'Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n'
        'Access-Control-Allow-Headers: Content-Type, X-Auth-Token\r\n'
        'Access-Control-Max-Age: 86400\r\n'
        'Connection: close\r\n'
        '\r\n'
    )
    writer.write(headers.encode())
    await writer.drain()


class ApiServer(BaseServer):
    """
    HTTP API сервер для управления FlowLink Proxy.

    Эндпоинты:
      GET  /api/config              — получить конфиг
      POST /api/config              — обновить конфиг
      GET  /api/status              — статус gateway
      GET  /api/version             — версия сервера (открытый, без токена)
      GET  /api/bootstrap           — токен и порт API (открытый, без токена)
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

    Аутентификация: если задан auth_token, все маршруты, кроме
    /api/version и /api/bootstrap, требуют заголовок X-Auth-Token
    (или query-параметр token для GET). CORS разрешён только для
    Origin вида chrome-extension://<id>.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        # Параметры конфигурируют сервер: роутер, хост, порт, режимы
        # отладки/обновления и токен аутентификации — единый объект-настройки
        # здесь избыточен, все значения используются напрямую.
        self, router: MaskRouter, host: str = '127.0.0.1',
        port: int = 8081, debug: bool = False,
        need_update: bool = False,
        auth_token: str | None = None):
        """
        Инициализирует API-сервер FlowLink Proxy.

        Args:
            router: Экземпляр MaskRouter (refresh после сохранения конфига).
            host: Интерфейс (по умолч. localhost).
            port: Порт API (по умолч. 8081).
            debug: Включает отладку в статусе.
            need_update: Флаг симуляции обновления (передаётся в статус).
            auth_token: Токен аутентификации API. Если задан — все
                маршруты, кроме /api/version и /api/bootstrap, требуют
                заголовок X-Auth-Token (или query-параметр token для GET).
        """
        super().__init__(host=host, port=port, name='api')
        self._router = router
        self._debug = debug
        self._need_update = need_update
        self._auth_token = auth_token

    def _is_authenticated(
        self, method: str, route_path: str, query: str,
        headers: dict | None,
    ) -> bool:
        """Проверяет токен аутентификации для закрытых маршрутов.

        Открытые маршруты (/api/version, /api/bootstrap) не требуют токена.
        Для GET-запросов токен может передаваться в query-параметре token
        (EventSource не позволяет задавать заголовки), для остальных
        методов — только в заголовке X-Auth-Token.
        """
        if self._auth_token is None:
            return True
        if route_path in ('/api/version', '/api/bootstrap'):
            return True
        supplied = (headers or {}).get('x-auth-token')
        if supplied is None and method == 'GET':
            supplied = _extract_token_from_query(query)
        return supplied == self._auth_token

    async def _route_request(
        self, method: str, path: str, body: bytes,
        peername: tuple, writer: asyncio.StreamWriter,
        headers: dict | None = None,
    ) -> tuple[int, dict] | None:
        """Маршрутизирует запрос к обработчику,
        возвращает (код, тело) или None (SSE).

        Args:
            method: HTTP-метод.
            path: Путь запроса (может содержать query-строку).
            body: Тело запроса (байты).
            peername: Кортеж (хост, порт) клиента.
            writer: asyncio StreamWriter для ответа.
            headers: Заголовки запроса (ключи в нижнем регистре).
        """
        # Маршрутизатор принимает полный контекст запроса (метод, путь, тело,
        # заголовки, клиента, writer) и завершается несколькими ветвями
        # ответа — подавление лимитов аргументов и return оправдано ролью
        # диспетчера.
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        # pylint: disable=too-many-return-statements
        # Отделяем путь от query-строки: маршрутизация по чистому пути,
        # а токен в GET-запросах может передаваться в query-параметре token
        route_path, _, query = path.partition('?')
        try:
            # Аутентификация: закрытые маршруты требуют валидный токен
            if not self._is_authenticated(method, route_path, query, headers):
                logger.warning(
                    'API: отказ в доступе (неверный токен) %s %s от %s',
                    method, route_path, peername,
                )
                return 403, {'error': 'Не авторизован'}

            if route_path == '/api/bootstrap' and method == 'GET':
                # Открытый маршрут: расширение получает токен и порт API
                # для дальнейшей аутентификации запросов
                return 200, {
                    'token': self._auth_token,
                    'apiPort': self._port,
                }

            if route_path == '/api/events' and method == 'GET':
                await handle_sse(
                    writer,
                    auth_token=self._auth_token,
                    token=_extract_token_from_query(query),
                    origin=(headers or {}).get('origin'),
                )
                return None

            handler = _ROUTES.get((method, route_path))
            if handler is None:
                logger.warning('API: неизвестный запрос %s %s от %s',
                               method, route_path, peername)
                return 404, {'error': f'Не найдено: {method} {route_path}'}

            # Единая точка вызова обработчика: парсинг JSON и
            # передача контекста
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
            logger.error(
                'API: ошибка сервера от %s: %s', peername, e, exc_info=True
            )
            return 500, {
                'error': (
                    'Внутренняя ошибка сервера. '
                    'Если проблема повторяется, '
                    'обратитесь в поддержку: flowlink.proxy@atomicmail.io'
                )
            }

    async def _handle_client(  # pylint: disable=too-many-branches,too-many-locals  # диспетчер всех HTTP-методов; разбиение ухудшит читаемость
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        """Диспетчеризует входящие HTTP-запросы к API.

        Метод содержит множество ветвей обработки исключений (413, 400,
        408, таймаут, сетевые ошибки, страховочный 500) — вынос каждой
        ветви в отдельный метод раздробил бы логику диспетчера. Множество
        локальных переменных (заголовки, Origin, маскированный путь) —
        следствие того же диспетчерского контекста запроса.
        """
        peername = writer.get_extra_info('peername', ('?', 0))
        try:
            method, path, body, headers = await _parse_http_request(
                reader, peername
            )
            if method is None or path is None:
                writer.close()
                return

            # CORS-allowlist строится по Origin из заголовков запроса
            origin = (headers or {}).get('origin')

            # Маскируем query-параметр token в пути для логов
            log_path = _mask_token_in_path(path)
            logger.debug('API: %s %s от %s', method, log_path, peername)

            # CORS preflight: отвечаем 204 без проверки токена —
            # предварительные запросы браузера не содержат кастомных
            # заголовков (X-Auth-Token), поэтому токен тут не требуется
            if method == 'OPTIONS':
                await _build_options_response(writer, origin)
                return

            if self._debug and logger.isEnabledFor(logging.DEBUG) and body:
                body_str = body.decode('utf-8', errors='replace')
                if path.split('?', 1)[0] == '/api/config' and method == 'POST':
                    body_str = mask_sensitive(body_str)
                logger.debug('API >>> %s %s body: %s',
                             method, log_path, body_str)

            result = await self._route_request(
                method, path, body, peername, writer, headers,
            )
            if result is None:
                return
            status_code, response_body = result

            await _build_response(writer, status_code, response_body, origin)

            if self._debug and logger.isEnabledFor(logging.DEBUG):
                # Маскируем чувствительные поля перед логированием
                resp_str = mask_sensitive(
                    truncate(json.dumps(response_body, ensure_ascii=False))
                )
                logger.debug('API <<< %s %s -> %d body: %s',
                             method, log_path, status_code, resp_str)

        except _RequestTooLarge:
            await _build_response(
                writer, 413,
                {'error': f'Тело запроса слишком большое '
                          f'(максимум {MAX_POST_BODY} байт)'},
            )
        except _RequestHeaderLimit:
            await _build_response(
                writer, 400,
                {'error': 'Слишком много заголовков или превышен их суммарный'
                          f' размер (максимум {MAX_HEADERS} шт / '
                          f'{MAX_HEADER_SIZE} байт)'},
            )
        except _RequestTimeout:
            await _build_response(
                writer, 408,
                {'error': 'Таймаут ожидания запроса'},
            )
        except asyncio.TimeoutError:
            logger.debug('API: таймаут ожидания запроса')
        except (ConnectionError, OSError,
                asyncio.IncompleteReadError) as e:
            # Штатный разрыв соединения (клиент закрыл fetch/SSE) — не ошибка.
            # Логируем на debug без стека, чтобы не засорять логи.
            logger.debug('API: соединение разорвано: %s', e)
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
