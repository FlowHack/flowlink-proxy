"""Тесты маршрутизации API-эндпоинтов (таблица _ROUTES в api.py).

Проверяют корректность распаковки кортежей (response_body, status_code)
для обработчиков, возвращающих нестандартные коды, и обычных dict-ответов.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.servers.api import ApiServer


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
            result = await server._route_request(  # pylint: disable=protected-access
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
            result = await server._route_request(  # pylint: disable=protected-access
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
            result = await server._route_request(  # pylint: disable=protected-access
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
            result = await server._route_request(  # pylint: disable=protected-access
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
        result = await server._route_request(  # pylint: disable=protected-access
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
        result = await server._route_request(  # pylint: disable=protected-access
            'POST', '/api/ping', b'{}',
            ('127.0.0.1', 1234), MagicMock(),
        )
        if result is None:
            self.fail('_route_request вернул None')
        status_code, response_body = result
        self.assertEqual(status_code, 400)
        self.assertIn('error', response_body)


if __name__ == '__main__':
    unittest.main()
