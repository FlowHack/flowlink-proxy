"""Тесты маршрутизации API-эндпоинтов (таблица _ROUTES в api.py).

Проверяют корректность распаковки кортежей (response_body, status_code)
для обработчиков, возвращающих нестандартные коды, и обычных dict-ответов.
Также проверяют аутентификацию по токену (X-Auth-Token / query token),
открытые маршруты /api/version и /api/bootstrap, CORS-allowlist
(chrome-extension://) и обработку CORS preflight (OPTIONS).
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.servers.api import (
    _RequestHeaderLimit, _RequestTimeout, _build_options_response,
    _build_response, _mask_token_in_path, _parse_http_request, ApiServer,
)


def _write_all(writer) -> bytes:
    """Собирает все байты, записанные в mock-писатель."""
    return b''.join(c[0][0] for c in writer.write.call_args_list)


class TestApiRouteRequest(unittest.IsolatedAsyncioTestCase):
    """Тесты _route_request: распаковка кортежей и dict-ответов."""

    def _make_server(self, auth_token: str | None = None) -> ApiServer:
        """Создаёт ApiServer с мок-роутером."""
        router = MagicMock()
        return ApiServer(
            router, port=8081, debug=False, need_update=False,
            auth_token=auth_token,
        )

    async def test_ping_returns_tuple(self):
        """POST /api/ping возвращает кортеж (response_body, status_code)."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_ping',
                   new=AsyncMock(return_value=({'alive': True}, 200))):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'POST', '/api/ping', b'{"proxyId":"p1"}',
                ('127.0.0.1', 1234), MagicMock(),
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'alive': True})

    async def test_browser_path_returns_tuple(self):
        """POST /api/browser-path возвращает кортеж (response_body, status_code)."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_post_browser_path',
                   new=AsyncMock(return_value=({'ok': True}, 200))):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'POST', '/api/browser-path', b'{"path":"/usr/bin/chrome"}',
                ('127.0.0.1', 1234), MagicMock(),
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'ok': True})

    async def test_validate_browser_returns_tuple(self):
        """POST /api/validate-browser возвращает кортеж (response_body, status_code)."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_post_validate_browser',
                   return_value=({'valid': False}, 400)):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'POST', '/api/validate-browser', b'{"path":"/bad/path"}',
                ('127.0.0.1', 1234), MagicMock(),
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 400)
        self.assertEqual(response_body, {'valid': False})

    async def test_config_get_returns_dict(self):
        """GET /api/config возвращает dict (код 200 по умолчанию)."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_get_config',
                   return_value={'proxies': [], 'masks': []}):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'GET', '/api/config', b'',
                ('127.0.0.1', 1234), MagicMock(),
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'proxies': [], 'masks': []})

    async def test_unknown_route_returns_404(self):
        """Неизвестный маршрут возвращает 404."""
        server = self._make_server()
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/unknown', b'',
            ('127.0.0.1', 1234), MagicMock(),
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 404)
        self.assertIn('error', response_body)

    async def test_ping_missing_proxy_id_returns_400(self):
        """POST /api/ping без proxyId возвращает 400."""
        server = self._make_server()
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'POST', '/api/ping', b'{}',
            ('127.0.0.1', 1234), MagicMock(),
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 400)
        self.assertIn('error', response_body)


class TestApiAuth(unittest.IsolatedAsyncioTestCase):
    """Тесты аутентификации по токену в _route_request."""

    def _make_server(self, auth_token: str | None = 'secret') -> ApiServer:
        """Создаёт ApiServer с заданным auth_token."""
        router = MagicMock()
        return ApiServer(
            router, port=8081, debug=False, need_update=False,
            auth_token=auth_token,
        )

    async def test_missing_token_returns_403(self):
        """Запрос без токена → 403 Не авторизован."""
        server = self._make_server()
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/config', b'',
            ('127.0.0.1', 1234), MagicMock(), {},
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 403)
        self.assertEqual(response_body, {'error': 'Не авторизован'})

    async def test_wrong_header_token_returns_403(self):
        """Неверный заголовок X-Auth-Token → 403."""
        server = self._make_server()
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/config', b'',
            ('127.0.0.1', 1234), MagicMock(),
            {'x-auth-token': 'wrong'},
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 403)
        self.assertEqual(response_body, {'error': 'Не авторизован'})

    async def test_correct_header_token_returns_200(self):
        """Верный заголовок X-Auth-Token → обработчик вызывается."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_get_config',
                   return_value={'proxies': []}):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'GET', '/api/config', b'',
                ('127.0.0.1', 1234), MagicMock(),
                {'x-auth-token': 'secret'},
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'proxies': []})

    async def test_correct_query_token_returns_200(self):
        """GET-запрос с query-параметром token → 200."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_get_config',
                   return_value={'proxies': []}):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'GET', '/api/config?token=secret', b'',
                ('127.0.0.1', 1234), MagicMock(), {},
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'proxies': []})

    async def test_wrong_query_token_returns_403(self):
        """Неверный query-параметр token → 403."""
        server = self._make_server()
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/config?token=wrong', b'',
            ('127.0.0.1', 1234), MagicMock(), {},
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 403)
        self.assertEqual(response_body, {'error': 'Не авторизован'})

    async def test_query_token_not_accepted_for_post(self):
        """POST не принимает токен из query-параметра (только заголовок)."""
        server = self._make_server()
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'POST', '/api/config?token=secret', b'{}',
            ('127.0.0.1', 1234), MagicMock(), {},
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 403)
        self.assertEqual(response_body, {'error': 'Не авторизован'})

    async def test_version_open_without_token(self):
        """GET /api/version открыт без токена."""
        server = self._make_server()
        with patch('server.servers.api.handlers.handle_get_version',
                   return_value={'version': '1.0.0'}):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'GET', '/api/version', b'',
                ('127.0.0.1', 1234), MagicMock(), {},
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'version': '1.0.0'})

    async def test_no_auth_token_skips_check(self):
        """Без auth_token проверка токена не выполняется."""
        server = self._make_server(auth_token=None)
        with patch('server.servers.api.handlers.handle_get_config',
                   return_value={'proxies': []}):
            result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
                'GET', '/api/config', b'',
                ('127.0.0.1', 1234), MagicMock(), {},
            )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'proxies': []})


class TestApiBootstrap(unittest.IsolatedAsyncioTestCase):
    """Тесты открытого маршрута GET /api/bootstrap."""

    def _make_server(self, auth_token: str | None) -> ApiServer:
        """Создаёт ApiServer с заданным auth_token на порту 8081."""
        router = MagicMock()
        return ApiServer(
            router, port=8081, debug=False, need_update=False,
            auth_token=auth_token,
        )

    async def test_bootstrap_returns_token_and_port(self):
        """bootstrap возвращает токен и порт API."""
        server = self._make_server('secret')
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/bootstrap', b'',
            ('127.0.0.1', 1234), MagicMock(), {},
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'token': 'secret', 'apiPort': 8081})

    async def test_bootstrap_without_auth_returns_none_token(self):
        """Без auth_token bootstrap возвращает token=None."""
        server = self._make_server(None)
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/bootstrap', b'',
            ('127.0.0.1', 1234), MagicMock(), None,
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'token': None, 'apiPort': 8081})

    async def test_bootstrap_open_without_token_header(self):
        """bootstrap доступен без заголовка токена даже при включённом auth."""
        server = self._make_server('secret')
        result = await server._route_request(  # pylint: disable=protected-access  # internal: проверка маршрутизации напрямую
            'GET', '/api/bootstrap', b'',
            ('127.0.0.1', 1234), MagicMock(), None,
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, {'token': 'secret', 'apiPort': 8081})


class TestApiCors(unittest.IsolatedAsyncioTestCase):
    """Тесты CORS-allowlist в _build_response."""

    async def test_chrome_extension_origin_gets_cors(self):
        """Origin chrome-extension:// → Access-Control-Allow-Origin + Vary."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_response(
            writer, 200, {'ok': True}, 'chrome-extension://abcdef123456',
        )
        written = _write_all(writer)
        self.assertIn(
            b'Access-Control-Allow-Origin: chrome-extension://abcdef123456',
            written,
        )
        self.assertIn(b'Vary: Origin', written)

    async def test_foreign_origin_gets_no_cors(self):
        """Чужой Origin (веб-страница) → без CORS-заголовка."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_response(writer, 200, {'ok': True},
                              'http://evil.example.com')
        written = _write_all(writer)
        self.assertNotIn(b'Access-Control-Allow-Origin', written)

    async def test_no_origin_gets_no_cors(self):
        """Запрос без Origin → без CORS-заголовка."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_response(writer, 200, {'ok': True}, None)
        written = _write_all(writer)
        self.assertNotIn(b'Access-Control-Allow-Origin', written)


class TestApiResponseReasons(unittest.IsolatedAsyncioTestCase):
    """Тесты reason-строк в _build_response."""

    async def test_422_reason_unprocessable_entity(self):
        """HTTP 422 → reason-строка 'Unprocessable Entity'."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_response(writer, 422, {'error': 'Невалидные данные'})
        written = _write_all(writer)
        self.assertIn(b'HTTP/1.1 422 Unprocessable Entity', written)

    async def test_408_reason_request_timeout(self):
        """HTTP 408 → reason-строка 'Request Timeout'."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_response(writer, 408, {'error': 'Таймаут'})
        written = _write_all(writer)
        self.assertIn(b'HTTP/1.1 408 Request Timeout', written)


class TestApiOptions(unittest.IsolatedAsyncioTestCase):
    """Тесты обработки CORS preflight (OPTIONS)."""

    async def test_options_response_204_with_headers(self):
        """OPTIONS с валидным Origin → 204 + preflight-заголовки."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_options_response(
            writer, 'chrome-extension://abcdef123456',
        )
        written = _write_all(writer)
        self.assertIn(b'HTTP/1.1 204', written)
        self.assertIn(
            b'Access-Control-Allow-Origin: chrome-extension://abcdef123456',
            written,
        )
        self.assertIn(
            b'Access-Control-Allow-Methods: GET, POST, OPTIONS', written,
        )
        self.assertIn(
            b'Access-Control-Allow-Headers: Content-Type, X-Auth-Token',
            written,
        )
        self.assertIn(b'Access-Control-Max-Age: 86400', written)

    async def test_options_with_foreign_origin_no_cors(self):
        """OPTIONS с чужим Origin → 204 без Access-Control-Allow-Origin."""
        writer = MagicMock()
        writer.drain = AsyncMock()
        await _build_options_response(writer, 'http://evil.example.com')
        written = _write_all(writer)
        self.assertIn(b'HTTP/1.1 204', written)
        self.assertNotIn(b'Access-Control-Allow-Origin:', written)

    async def test_handle_client_options_preflight(self):
        """_handle_client обрабатывает OPTIONS без проверки токена."""
        server = ApiServer(MagicMock(), port=8081, auth_token='secret')
        reader = asyncio.StreamReader()
        reader.feed_data(
            b'OPTIONS /api/config HTTP/1.1\r\n'
            b'Origin: chrome-extension://abcdef123456\r\n'
            b'Access-Control-Request-Method: GET\r\n'
            b'\r\n',
        )
        reader.feed_eof()
        writer = MagicMock()
        writer.drain = AsyncMock()
        writer.get_extra_info.return_value = ('127.0.0.1', 1234)
        await server._handle_client(reader, writer)  # pylint: disable=protected-access  # internal: проверка диспетчера напрямую
        written = _write_all(writer)
        self.assertIn(b'HTTP/1.1 204', written)
        self.assertIn(
            b'Access-Control-Allow-Origin: chrome-extension://abcdef123456',
            written,
        )


class TestApiHeaderLimits(unittest.IsolatedAsyncioTestCase):
    """Тесты защиты от медленного DoS: лимиты заголовков в _parse_http_request."""

    def _make_reader(self, lines: list[bytes]):
        """Создаёт StreamReader с заданными строками."""
        reader = asyncio.StreamReader()
        for line in lines:
            reader.feed_data(line)
        reader.feed_eof()
        return reader

    async def test_too_many_headers_raises_header_limit(self):
        """Превышение MAX_HEADERS → _RequestHeaderLimit."""
        lines = [b'GET /api/config HTTP/1.1\r\n']
        # 51 заголовок (лимит 50)
        for i in range(51):
            lines.append(f'X-Hdr-{i}: value\r\n'.encode())
        lines.append(b'\r\n')
        reader = self._make_reader(lines)
        with self.assertRaises(_RequestHeaderLimit):
            await _parse_http_request(reader, ('127.0.0.1', 1234))

    async def test_header_read_timeout_raises_request_timeout(self):
        """Таймаут чтения заголовков → _RequestTimeout."""
        reader = asyncio.StreamReader()
        # Только request-line, без пустой строки — цикл чтения зависнет
        reader.feed_data(b'GET /api/config HTTP/1.1\r\n')
        with patch('server.servers.api.HEADER_READ_TIMEOUT', 0.01):
            with self.assertRaises(_RequestTimeout):
                await _parse_http_request(reader, ('127.0.0.1', 1234))

    async def test_body_read_timeout_raises_request_timeout(self):
        """Таймаут чтения тела запроса → _RequestTimeout (408)."""
        reader = asyncio.StreamReader()
        # Заголовки полные, но тело (10 байт) не передаётся —
        # readexactly зависает, wait_for бросает TimeoutError.
        reader.feed_data(
            b'POST /api/config HTTP/1.1\r\n'
            b'Content-Length: 10\r\n'
            b'\r\n',
        )
        with patch.object(
            reader, 'readexactly',
            new=AsyncMock(side_effect=asyncio.TimeoutError),
        ):
            with self.assertRaises(_RequestTimeout):
                await _parse_http_request(reader, ('127.0.0.1', 1234))

    async def test_invalid_content_length_ignored(self):
        """Некорректный Content-Length не ломает парсинг."""
        lines = [
            b'POST /api/config HTTP/1.1\r\n',
            b'Content-Length: not-a-number\r\n',
            b'\r\n',
        ]
        reader = self._make_reader(lines)
        method, path, body, headers = await _parse_http_request(
            reader, ('127.0.0.1', 1234)
        )
        self.assertEqual(method, 'POST')
        self.assertEqual(path, '/api/config')
        self.assertEqual(body, b'')
        self.assertEqual(headers.get('content-length'), 'not-a-number')

    async def test_parse_returns_lowercase_header_keys(self):
        """_parse_http_request возвращает заголовки с lowercase-ключами."""
        lines = [
            b'GET /api/config HTTP/1.1\r\n',
            b'Origin: chrome-extension://abcdef123456\r\n',
            b'X-Auth-Token: MySecretToken\r\n',
            b'\r\n',
        ]
        reader = self._make_reader(lines)
        method, path, body, headers = await _parse_http_request(
            reader, ('127.0.0.1', 1234)
        )
        self.assertEqual(method, 'GET')
        self.assertEqual(path, '/api/config')
        self.assertEqual(body, b'')
        self.assertEqual(headers['origin'], 'chrome-extension://abcdef123456')
        self.assertEqual(headers['x-auth-token'], 'MySecretToken')
        self.assertNotIn('Origin', headers)


class TestApiLogMasking(unittest.TestCase):
    """Тесты маскирования query-параметра token в пути для логов."""

    def test_masks_simple_token(self):
        """token=... заменяется на token=***."""
        self.assertEqual(
            _mask_token_in_path('/api/config?token=abc'),
            '/api/config?token=***',
        )

    def test_masks_token_among_other_params(self):
        """Маскируется token среди других query-параметров."""
        self.assertEqual(
            _mask_token_in_path('/api/config?a=1&token=abc&b=2'),
            '/api/config?a=1&token=***&b=2',
        )

    def test_path_without_query_unchanged(self):
        """Путь без query-строки не меняется."""
        self.assertEqual(
            _mask_token_in_path('/api/config'),
            '/api/config',
        )


if __name__ == '__main__':
    unittest.main()
