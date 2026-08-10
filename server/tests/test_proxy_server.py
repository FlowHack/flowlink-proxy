"""
Юнит-тесты HTTP CONNECT прокси-сервера (server/servers/proxy.py).

Стратегия: прямое тестирование _handle_client/_handle_connect/_handle_http
с мок-объектами reader/writer и патчингом модульных функций
(parse_connect, parse_http, skip_headers, safe_close_writer,
tunnel_connect, tunnel_http, validate_target).
"""

# pylint: disable=protected-access
# Белый ящик: тесты намеренно обращаются к приватным методам диспетчеризации
# ProxyServer (_handle_client/_handle_connect/_handle_http) и атрибутам
# (_host/_port) — это внутренний контракт сервера, проверяемый напрямую.

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.servers.proxy import ProxyServer

CONNECT_LINE = b'CONNECT example.com:443 HTTP/1.1\r\n'
HTTP_LINE = b'GET http://example.com/path HTTP/1.1\r\n'


def _make_writer():
    """Создаёт мок writer с get_extra_info и awaitable drain."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ('127.0.0.1', 12345)
    writer.drain = AsyncMock()
    return writer


class ProxyServerTestBase(unittest.IsolatedAsyncioTestCase):
    """Общая настройка: сервер с мок-router'ом и writer."""

    def setUp(self):
        self.router = MagicMock()
        self.router.route.return_value = None
        self.server = ProxyServer(self.router, host='127.0.0.1', port=8080)
        self.writer = _make_writer()

    def _make_reader(self, first_line):
        """Создаёт мок reader, у которого readline возвращает first_line."""
        reader = MagicMock()
        reader.readline = AsyncMock(return_value=first_line)
        return reader


class TestProxyServerConnect(ProxyServerTestBase):
    """Тесты CONNECT-ветки диспетчеризации."""

    async def test_connect_success_order_and_arguments(self):
        """CONNECT: порядок skip_headers → validate_target → route → tunnel_connect."""
        reader = self._make_reader(CONNECT_LINE)
        proxy = {'host': 'proxy.local', 'port': 3128}
        order = []

        skip_headers = AsyncMock(
            side_effect=lambda *a, **k: order.append('skip_headers'),
        )
        validate_target = AsyncMock(
            side_effect=lambda *a, **k: order.append('validate_target'),
        )
        tunnel_connect = AsyncMock(
            side_effect=lambda *a, **k: order.append('tunnel_connect'),
        )

        with patch('server.servers.proxy.parse_connect',
                   return_value=('example.com', 443)), \
             patch('server.servers.proxy.skip_headers', skip_headers), \
             patch('server.servers.proxy.validate_target', validate_target), \
             patch('server.servers.proxy.tunnel_connect', tunnel_connect), \
             patch('server.servers.proxy.safe_close_writer'):
            self.router.route.side_effect = (
                lambda url: (order.append('route') or proxy)
            )
            await self.server._handle_client(reader, self.writer)

        self.assertEqual(
            order,
            ['skip_headers', 'validate_target', 'route', 'tunnel_connect'],
        )
        self.router.route.assert_called_once_with('https://example.com:443/')
        tunnel_connect.assert_awaited_once_with(
            (reader, self.writer),
            ('example.com', 443),
            'https://example.com:443/',
            proxy,
        )
        # 200-ответ клиенту не пишется — соединение просто туннелируется
        self.writer.write.assert_not_called()

    async def test_connect_bad_request_400(self):
        """parse_connect → None → ответ 400, туннель не устанавливается."""
        reader = self._make_reader(CONNECT_LINE)
        tunnel_connect = AsyncMock()

        with patch('server.servers.proxy.parse_connect', return_value=None), \
             patch('server.servers.proxy.tunnel_connect', tunnel_connect), \
             patch('server.servers.proxy.safe_close_writer'):
            await self.server._handle_client(reader, self.writer)

        self.writer.write.assert_called_once_with(
            b'HTTP/1.1 400 Bad Request\r\n\r\n',
        )
        self.writer.drain.assert_awaited_once()
        self.writer.close.assert_called()
        tunnel_connect.assert_not_awaited()
        self.router.route.assert_not_called()

    async def test_connect_validate_target_ssrf_returns_502(self):
        """validate_target кидает SSRF-ValueError → ответ 502 Bad Gateway."""
        reader = self._make_reader(CONNECT_LINE)
        tunnel_connect = AsyncMock()

        def _raise_ssrf(_host, _port):
            raise ValueError('SSRF: запрос к локальному адресу запрещён')

        with patch('server.servers.proxy.parse_connect',
                   return_value=('example.com', 443)), \
             patch('server.servers.proxy.skip_headers', AsyncMock()), \
             patch('server.servers.proxy.validate_target',
                   side_effect=_raise_ssrf), \
             patch('server.servers.proxy.tunnel_connect', tunnel_connect), \
             patch('server.servers.proxy.safe_close_writer'):
            await self.server._handle_client(reader, self.writer)

        payload = self.writer.write.call_args[0][0]
        self.assertIn(b'HTTP/1.1 502 Bad Gateway', payload)
        self.assertIn('SSRF: запрос к локальному адресу запрещён'.encode('utf-8'),
                      payload)
        self.writer.drain.assert_awaited_once()
        tunnel_connect.assert_not_awaited()
        self.router.route.assert_not_called()

    async def test_connect_ssrf_skip_headers_before_validate_target(self):
        """При SSRF-ошибке skip_headers вызывается до validate_target."""
        reader = self._make_reader(b'X-Header: value\r\n\r\n')
        order = []
        skip_headers = AsyncMock(
            side_effect=lambda *a, **k: order.append('skip_headers'),
        )

        def _raise_ssrf(_host, _port):
            order.append('validate_target')
            raise ValueError('SSRF: запрос к локальному адресу запрещён')

        with patch('server.servers.proxy.parse_connect',
                   return_value=('example.com', 443)), \
             patch('server.servers.proxy.skip_headers', skip_headers), \
             patch('server.servers.proxy.validate_target',
                   side_effect=_raise_ssrf), \
             patch('server.servers.proxy.tunnel_connect', AsyncMock()):
            with self.assertRaises(ValueError):
                await self.server._handle_connect(
                    reader, self.writer, CONNECT_LINE,
                )

        self.assertEqual(order, ['skip_headers', 'validate_target'])


class TestProxyServerHttp(ProxyServerTestBase):
    """Тесты HTTP-ветки диспетчеризации."""

    async def test_http_success_order_and_arguments(self):
        """HTTP: порядок validate_target → route → tunnel_http, skip_headers не зовётся."""
        reader = self._make_reader(HTTP_LINE)
        relative_line = b'GET /path HTTP/1.1\r\n'
        order = []

        validate_target = AsyncMock(
            side_effect=lambda *a, **k: order.append('validate_target'),
        )
        tunnel_http = AsyncMock(
            side_effect=lambda *a, **k: order.append('tunnel_http'),
        )
        skip_headers = AsyncMock(
            side_effect=lambda *a, **k: order.append('skip_headers'),
        )

        with patch('server.servers.proxy.parse_http',
                   return_value=('GET', 'example.com', 80, '/path',
                                 relative_line)), \
             patch('server.servers.proxy.validate_target', validate_target), \
             patch('server.servers.proxy.tunnel_http', tunnel_http), \
             patch('server.servers.proxy.skip_headers', skip_headers), \
             patch('server.servers.proxy.safe_close_writer'):
            self.router.route.side_effect = (
                lambda url: (order.append('route') or None)
            )
            await self.server._handle_client(reader, self.writer)

        self.assertEqual(order, ['validate_target', 'route', 'tunnel_http'])
        skip_headers.assert_not_awaited()
        self.router.route.assert_called_once_with(
            'http://example.com:80/path',
        )
        tunnel_http.assert_awaited_once_with(
            (reader, self.writer),
            ('example.com', 80),
            'http://example.com:80/path',
            relative_line,
            None,
        )

    async def test_http_bad_request_400(self):
        """parse_http → None → ответ 400, туннель не устанавливается."""
        reader = self._make_reader(HTTP_LINE)
        tunnel_http = AsyncMock()

        with patch('server.servers.proxy.parse_http', return_value=None), \
             patch('server.servers.proxy.tunnel_http', tunnel_http), \
             patch('server.servers.proxy.safe_close_writer'):
            await self.server._handle_client(reader, self.writer)

        self.writer.write.assert_called_once_with(
            b'HTTP/1.1 400 Bad Request\r\n\r\n',
        )
        self.writer.drain.assert_awaited_once()
        self.writer.close.assert_called()
        tunnel_http.assert_not_awaited()
        self.router.route.assert_not_called()

    async def test_http_validate_target_failure_stops_before_route(self):
        """Ошибка validate_target → route не вызывается (validate до route)."""
        reader = self._make_reader(HTTP_LINE)
        relative_line = b'GET /path HTTP/1.1\r\n'

        def _raise_ssrf(_host, _port):
            raise ValueError('SSRF: запрос к локальному адресу запрещён')

        with patch('server.servers.proxy.parse_http',
                   return_value=('GET', 'example.com', 80, '/path',
                                 relative_line)), \
             patch('server.servers.proxy.validate_target',
                   side_effect=_raise_ssrf), \
             patch('server.servers.proxy.tunnel_http', AsyncMock()):
            with self.assertRaises(ValueError):
                await self.server._handle_http(reader, self.writer, HTTP_LINE)

        self.router.route.assert_not_called()


class TestProxyServerDispatch(ProxyServerTestBase):
    """Тесты диспетчеризации и граничных случаев _handle_client."""

    async def test_timeout_first_line_closes_writer(self):
        """Таймаут ожидания первой строки → только close, без ответа."""
        reader = MagicMock()
        reader.readline = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch('server.servers.proxy.safe_close_writer'):
            await self.server._handle_client(reader, self.writer)

        self.writer.write.assert_not_called()
        self.writer.close.assert_called()

    async def test_unknown_method_closes_writer(self):
        """Неизвестный метод (FOO) → close, обработчики не вызываются."""
        reader = self._make_reader(b'FOO / HTTP/1.1\r\n')
        tunnel_connect = AsyncMock()
        tunnel_http = AsyncMock()
        parse_connect = MagicMock()
        parse_http = MagicMock()

        with patch('server.servers.proxy.parse_connect', parse_connect), \
             patch('server.servers.proxy.parse_http', parse_http), \
             patch('server.servers.proxy.tunnel_connect', tunnel_connect), \
             patch('server.servers.proxy.tunnel_http', tunnel_http), \
             patch('server.servers.proxy.safe_close_writer'):
            await self.server._handle_client(reader, self.writer)

        self.writer.close.assert_called()
        parse_connect.assert_not_called()
        parse_http.assert_not_called()
        tunnel_connect.assert_not_awaited()
        tunnel_http.assert_not_awaited()

    async def test_empty_first_line_closes_writer(self):
        """Пустая первая строка (клиент закрыл соединение) → close, без туннеля."""
        reader = self._make_reader(b'')
        tunnel_connect = AsyncMock()
        tunnel_http = AsyncMock()

        with patch('server.servers.proxy.tunnel_connect', tunnel_connect), \
             patch('server.servers.proxy.tunnel_http', tunnel_http), \
             patch('server.servers.proxy.safe_close_writer'):
            await self.server._handle_client(reader, self.writer)

        self.writer.close.assert_called()
        tunnel_connect.assert_not_awaited()
        tunnel_http.assert_not_awaited()

    async def test_constructor_does_not_bind_socket(self):
        """Конструктор не поднимает сокет — start() создаёт сервер позже."""
        # Создание без контекстного менеджера не должно падать и не должно
        # поднимать сокет (нет вызовов asyncio.start_server в конструкторе).
        self.assertIsNotNone(self.server)
        self.assertEqual(self.server._host, '127.0.0.1')
        self.assertEqual(self.server._port, 8080)
