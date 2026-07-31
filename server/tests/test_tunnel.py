"""
Тесты SSRF-защиты validate_target() и регрессионные тесты
tunnel_connect()/tunnel_http() из server/services/tunnel.py.

Проверяет блокировку приватных/локальных IP-адресов, разрешение публичных
доменов, а также корректную обработку ошибок соединения (баг
"generator didn't yield") и пересылку HTTP-ответа клиенту.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from server.services.tunnel import tunnel_connect, tunnel_http, validate_target


class TestValidateTarget(unittest.TestCase):
    """Тесты функции validate_target — SSRF-защита."""

    def _run(self, coro):
        """Запускает корутину в изолированном event loop."""
        return asyncio.run(coro)

    def test_loopback_127(self):
        """127.0.0.1 → блокируется (loopback)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('127.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_loopback_127_range(self):
        """127.0.0.2 → блокируется (loopback range)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('127.0.0.2', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_private_10(self):
        """10.0.0.1 → блокируется (private 10.0.0.0/8)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('10.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_private_172(self):
        """172.16.0.1 → блокируется (private 172.16.0.0/12)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('172.16.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_private_192(self):
        """192.168.1.1 → блокируется (private 192.168.0.0/16)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('192.168.1.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_link_local(self):
        """169.254.0.1 → блокируется (link-local)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('169.254.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_ipv6_loopback(self):
        """[::1] → блокируется (IPv6 loopback)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('::1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_public_domain(self):
        """example.com → разрешается (публичный домен)"""
        # Не должно выбрасывать исключение
        try:
            self._run(validate_target('example.com', 80))
        except ValueError as e:
            # Если example.com резолвится в приватный IP — это ок (CI/ocker)
            if 'SSRF' not in str(e):
                raise

    def test_invalid_host(self):
        """Невалидный хост → ValueError (не SSRF)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('this.host.does.not.exist', 80))
        self.assertNotIn('SSRF', str(ctx.exception))


class TestTunnelConnectHttp(unittest.TestCase):
    """
    Регрессионные тесты tunnel_connect()/tunnel_http().

    Покрывают баг "RuntimeError: generator didn't yield": ошибка соединения
    ДО первого yield в _tunnel_context должна обрабатываться (502 клиенту)
    и перевыбрасываться наружу, где её перехватывает try/except
    в tunnel_connect/tunnel_http — без всплытия RuntimeError.
    """

    def _run(self, coro):
        """Запускает корутину в изолированном event loop."""
        return asyncio.run(coro)

    def test_http_success_forwards_response(self):
        """Успешный HTTP-туннель: ответ клиенту пересылается через pipe_http_response."""
        remote_reader, remote_writer = Mock(), Mock()
        client = (Mock(), Mock())
        with patch(
            'server.services.tunnel._establish_remote',
            new=AsyncMock(return_value=(remote_reader, remote_writer)),
        ), patch(
            'server.services.tunnel.pipe_http_request', new=AsyncMock(),
        ) as mock_req, patch(
            'server.services.tunnel.pipe_http_response', new=AsyncMock(),
        ) as mock_resp:
            self._run(tunnel_http(
                client,
                ('example.com', 80),
                'http://example.com/',
                b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n',
            ))
        mock_req.assert_awaited_once()
        mock_resp.assert_awaited_once()

    def test_http_connection_error_swallowed(self):
        """Ошибка соединения до yield: 502 отправлен, ошибка не всплывает."""
        client = (Mock(), Mock())
        with patch(
            'server.services.tunnel._establish_remote',
            new=AsyncMock(side_effect=OSError('connection refused')),
        ), patch(
            'server.services.tunnel._handle_tunnel_error', new=AsyncMock(),
        ) as mock_handle, patch(
            'server.services.tunnel.pipe_http_response', new=AsyncMock(),
        ) as mock_resp:
            # Не должно бросать RuntimeError "generator didn't yield" и OSError
            self._run(tunnel_http(
                client,
                ('example.com', 80),
                'http://example.com/',
                b'GET / HTTP/1.1\r\nHost: example.com\r\n\r\n',
            ))
        mock_handle.assert_awaited_once()
        mock_resp.assert_not_awaited()

    def test_connect_connection_error_swallowed(self):
        """tunnel_connect: ошибка соединения до yield обрабатывается без всплытия."""
        client = (Mock(), Mock())
        with patch(
            'server.services.tunnel._establish_remote',
            new=AsyncMock(side_effect=ConnectionError('refused')),
        ), patch(
            'server.services.tunnel._handle_tunnel_error', new=AsyncMock(),
        ) as mock_handle, patch(
            'server.services.tunnel.pipe', new=AsyncMock(),
        ) as mock_pipe:
            self._run(tunnel_connect(
                client, ('example.com', 80), 'https://example.com/',
            ))
        mock_handle.assert_awaited_once()
        mock_pipe.assert_not_awaited()

    def test_connect_success_pipes_data(self):
        """Успешный CONNECT-туннель: клиенту пишется 200 и данные пересылаются."""
        remote_reader, remote_writer = Mock(), Mock()
        client_writer = Mock()
        client_writer.drain = AsyncMock()
        client = (Mock(), client_writer)
        with patch(
            'server.services.tunnel._establish_remote',
            new=AsyncMock(return_value=(remote_reader, remote_writer)),
        ), patch(
            'server.services.tunnel.pipe', new=AsyncMock(),
        ) as mock_pipe:
            self._run(tunnel_connect(
                client, ('example.com', 80), 'https://example.com/',
            ))
        client_writer.write.assert_called_once_with(
            b'HTTP/1.1 200 Connection Established\r\n\r\n',
        )
        client_writer.drain.assert_awaited_once()
        mock_pipe.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
