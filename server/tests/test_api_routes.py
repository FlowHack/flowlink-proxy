"""Тесты маршрутизации API-эндпоинтов (таблица _ROUTES в api.py).

Проверяют корректность распаковки кортежей (response_body, status_code)
для обработчиков, возвращающих нестандартные коды, и обычных dict-ответов.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.servers.api import (_RequestHeaderLimit, _RequestTimeout,
                                _parse_http_request, ApiServer)


class TestApiRouteRequest(unittest.IsolatedAsyncioTestCase):
    """Тесты _route_request: распаковка кортежей и dict-ответов."""

    def _make_server(self) -> ApiServer:
        """Создаёт ApiServer с мок-роутером."""
        router = MagicMock()
        return ApiServer(router, port=8081, debug=False, need_update=False)

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

    async def test_invalid_content_length_ignored(self):
        """Некорректный Content-Length не ломает парсинг."""
        lines = [
            b'POST /api/config HTTP/1.1\r\n',
            b'Content-Length: not-a-number\r\n',
            b'\r\n',
        ]
        reader = self._make_reader(lines)
        method, path, body = await _parse_http_request(reader, ('127.0.0.1', 1234))
        self.assertEqual(method, 'POST')
        self.assertEqual(path, '/api/config')
        self.assertEqual(body, b'')


if __name__ == '__main__':
    unittest.main()
