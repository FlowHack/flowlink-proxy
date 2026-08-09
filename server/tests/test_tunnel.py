"""
Тесты SSRF-защиты validate_target(), регрессионные тесты
tunnel_connect()/tunnel_http() и тесты трекинга туннелей из
server/services/tunnel.py.

Проверяет блокировку приватных/локальных IP-адресов, разрешение публичных
доменов, корректную обработку ошибок соединения (баг "generator didn't yield"),
пересылку HTTP-ответа клиенту, а также управление глобальными трекерами
соединений: register_tunnel, unregister_tunnel, close_tunnels_for_proxy,
close_all_proxy_tunnels, close_all_connections.
"""

import asyncio
import socket
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

# Приватные глобальные трекеры импортируются напрямую для белого ящика:
# тесты трекинга проверяют реальную внутреннюю структуру данных tunnel.py.
from server.services.tunnel import (
    _active_tunnels,
    _all_writers,
    _client_writers,
    close_all_connections,
    close_all_proxy_tunnels,
    close_tunnels_for_proxy,
    register_client_writer,
    register_tunnel,
    tunnel_connect,
    tunnel_http,
    unregister_client_writer,
    unregister_tunnel,
    validate_target,
)


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

    def test_unspecified_ipv4_zero(self):
        """0.0.0.0 → блокируется (unspecified IPv4)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('0.0.0.0', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_unspecified_ipv6_unbounded(self):
        """:: → блокируется (unspecified IPv6)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('::', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_broadcast_255_255_255_255(self):
        """255.255.255.255 → блокируется (ограниченный broadcast)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('255.255.255.255', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_ipv4_mapped_ipv6_loopback(self):
        """::ffff:127.0.0.1 → блокируется (IPv4-mapped IPv6 loopback)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('::ffff:127.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_ipv4_mapped_ipv6_private(self):
        """::ffff:10.0.0.1 → блокируется (IPv4-mapped IPv6 private)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('::ffff:10.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_multicast_ipv4(self):
        """224.0.0.1 → блокируется (multicast)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('224.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_reserved_ipv4(self):
        """240.0.0.1 → блокируется (reserved 240.0.0.0/4)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('240.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_public_domain_allowed(self):
        """Публичный домен, резолвящийся в публичный IP, не блокируется.

        Не зависит от окружения: DNS-резолв мокается, поэтому инвариант
        «публичный адрес разрешён» проверяется детерминированно.
        """
        async def run():
            mock_loop = MagicMock()
            mock_loop.getaddrinfo = AsyncMock(return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, '',
                 ('93.184.216.34', 80)),
            ])
            with patch(
                'server.services.tunnel.asyncio.get_running_loop',
                return_value=mock_loop,
            ):
                # Не должно бросить ValueError — публичный адрес разрешён
                await validate_target('example.com', 80)
        self._run(run())

    def test_public_domain_resolving_to_private_blocked(self):
        """Публичный домен, резолвящийся в приватный IP, блокируется (SSRF)."""
        async def run():
            mock_loop = MagicMock()
            mock_loop.getaddrinfo = AsyncMock(return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, '',
                 ('10.0.0.5', 80)),
            ])
            with patch(
                'server.services.tunnel.asyncio.get_running_loop',
                return_value=mock_loop,
            ):
                with self.assertRaises(ValueError) as ctx:
                    await validate_target('example.com', 80)
                self.assertIn('SSRF', str(ctx.exception))
        self._run(run())

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

    def test_remote_writer_closed_on_client_error(self):
        """При ошибке клиента до pipe remote_writer закрывается (нет утечки TCP)."""
        remote_reader, remote_writer = Mock(), Mock()
        remote_writer.close = Mock()
        client_writer = Mock()
        # Клиент обрывает соединение: write/drain бросают ConnectionError
        client_writer.write = Mock(side_effect=ConnectionError('client gone'))
        client_writer.drain = AsyncMock(side_effect=ConnectionError('client gone'))
        client = (Mock(), client_writer)
        with patch(
            'server.services.tunnel._establish_remote',
            new=AsyncMock(return_value=(remote_reader, remote_writer)),
        ), patch(
            'server.services.tunnel.pipe', new=AsyncMock(),
        ) as mock_pipe, patch(
            'server.services.tunnel.safe_close_writer',
            new=Mock(side_effect=lambda w: w.close()),
        ):
            self._run(tunnel_connect(
                client, ('example.com', 80), 'https://example.com/',
            ))
        # remote_writer должен быть закрыт в finally _tunnel_context
        remote_writer.close.assert_called()
        mock_pipe.assert_not_awaited()


class TestTunnelTracking(unittest.TestCase):  # pylint: disable=too-many-public-methods  # тестовый класс: много мелких проверок трекинга
    """Тесты функций трекинга туннелей (белый ящик).

    Покрывают register_tunnel, unregister_tunnel, close_tunnels_for_proxy,
    close_all_proxy_tunnels, close_all_connections — управление глобальными
    трекерами _active_tunnels (proxy_id -> список writer'ов) и _all_writers
    (все удалённые соединения, включая direct).
    """

    def setUp(self):
        """Сбрасывает глобальные трекеры перед каждым тестом."""
        _active_tunnels.clear()
        _all_writers.clear()
        _client_writers.clear()

    def tearDown(self):
        """Очищает трекеры после теста — защита от межтестового загрязнения."""
        _active_tunnels.clear()
        _all_writers.clear()
        _client_writers.clear()

    def test_register_tunnel_adds_to_tracking(self):
        """register_tunnel добавляет writer в _active_tunnels по proxy_id."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_tunnel('proxy-1', w1)
        register_tunnel('proxy-1', w2)
        self.assertEqual(_active_tunnels['proxy-1'], [w1, w2])

    def test_register_tunnel_multiple_proxies(self):
        """Разные proxy_id ведут к отдельным спискам в _active_tunnels."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_tunnel('proxy-a', w1)
        register_tunnel('proxy-b', w2)
        self.assertEqual(_active_tunnels['proxy-a'], [w1])
        self.assertEqual(_active_tunnels['proxy-b'], [w2])

    def test_unregister_tunnel_removes_writer(self):
        """unregister_tunnel удаляет writer из списка активных туннелей."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_tunnel('proxy-1', w1)
        register_tunnel('proxy-1', w2)
        unregister_tunnel('proxy-1', w1)
        self.assertEqual(_active_tunnels['proxy-1'], [w2])

    def test_unregister_tunnel_removes_empty_key(self):
        """После удаления последнего writer ключ прокси исчезает из словаря."""
        w = MagicMock()
        register_tunnel('proxy-1', w)
        unregister_tunnel('proxy-1', w)
        self.assertNotIn('proxy-1', _active_tunnels)

    def test_unregister_tunnel_absent_writer_no_error(self):
        """unregister_tunnel с незарегистрированным writer не падает."""
        w = MagicMock()
        register_tunnel('proxy-1', MagicMock())
        # Этот writer в списке отсутствует — ValueError должен гаситься внутри
        unregister_tunnel('proxy-1', w)
        self.assertEqual(len(_active_tunnels['proxy-1']), 1)

    def test_close_tunnels_for_proxy_closes_and_removes(self):
        """close_tunnels_for_proxy закрывает все writer прокси и чистит трекеры."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_tunnel('proxy-1', w1)
        register_tunnel('proxy-1', w2)
        _all_writers.update([w1, w2])
        close_tunnels_for_proxy('proxy-1')
        w1.close.assert_called_once()
        w2.close.assert_called_once()
        self.assertNotIn('proxy-1', _active_tunnels)
        self.assertNotIn(w1, _all_writers)
        self.assertNotIn(w2, _all_writers)

    def test_close_tunnels_for_proxy_ignores_other_proxies(self):
        """close_tunnels_for_proxy('proxy-1') не трогает туннели proxy-2."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_tunnel('proxy-1', w1)
        register_tunnel('proxy-2', w2)
        _all_writers.update([w1, w2])
        close_tunnels_for_proxy('proxy-1')
        w1.close.assert_called_once()
        w2.close.assert_not_called()
        self.assertNotIn('proxy-1', _active_tunnels)
        # Туннель другого прокси остаётся в трекинге и в _all_writers
        self.assertEqual(_active_tunnels['proxy-2'], [w2])
        self.assertIn(w2, _all_writers)

    def test_close_tunnels_for_proxy_unknown_noop(self):
        """close_tunnels_for_proxy для неизвестного proxy_id — no-op без ошибок."""
        close_tunnels_for_proxy('nonexistent')
        self.assertEqual(_active_tunnels, {})
        self.assertEqual(_all_writers, set())

    def test_close_all_proxy_tunnels_closes_all(self):
        """close_all_proxy_tunnels закрывает туннели всех прокси."""
        w1 = MagicMock()
        w2 = MagicMock()
        w3 = MagicMock()
        register_tunnel('proxy-1', w1)
        register_tunnel('proxy-2', w2)
        register_tunnel('proxy-2', w3)
        _all_writers.update([w1, w2, w3])
        close_all_proxy_tunnels()
        w1.close.assert_called_once()
        w2.close.assert_called_once()
        w3.close.assert_called_once()
        self.assertEqual(_active_tunnels, {})
        self.assertEqual(_all_writers, set())

    def test_close_all_connections_closes_direct_writers(self):
        """close_all_connections закрывает и direct-соединения без прокси."""
        proxy_w = MagicMock()
        # Direct-соединение присутствует только в _all_writers (без proxy_id)
        direct_w = MagicMock()
        register_tunnel('proxy-1', proxy_w)
        _all_writers.update([proxy_w, direct_w])
        close_all_connections()
        proxy_w.close.assert_called_once()
        direct_w.close.assert_called_once()
        self.assertEqual(_all_writers, set())
        self.assertEqual(_active_tunnels, {})

    def test_close_oserror_does_not_break_others(self):
        """OSError при close() не прерывает закрытие остальных writer'ов."""
        w_bad = MagicMock()
        w_bad.close = Mock(side_effect=OSError('already closed'))
        w_ok = MagicMock()
        register_tunnel('proxy-1', w_bad)
        register_tunnel('proxy-1', w_ok)
        _all_writers.update([w_bad, w_ok])
        # Не должно падать: OSError логируется на debug-уровне и гасится
        close_all_connections()
        w_ok.close.assert_called_once()
        self.assertEqual(_all_writers, set())
        self.assertEqual(_active_tunnels, {})

    def test_register_client_writer_adds_to_tracking(self):
        """register_client_writer добавляет writer в _client_writers по proxy_id."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_client_writer('proxy-1', w1)
        register_client_writer('proxy-1', w2)
        self.assertEqual(_client_writers['proxy-1'], {w1, w2})

    def test_register_client_writer_multiple_proxies(self):
        """Разные proxy_id ведут к отдельным множествам в _client_writers."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_client_writer('proxy-a', w1)
        register_client_writer('proxy-b', w2)
        self.assertEqual(_client_writers['proxy-a'], {w1})
        self.assertEqual(_client_writers['proxy-b'], {w2})

    def test_unregister_client_writer_removes_writer(self):
        """unregister_client_writer удаляет writer из множества клиентских туннелей."""
        w1 = MagicMock()
        w2 = MagicMock()
        register_client_writer('proxy-1', w1)
        register_client_writer('proxy-1', w2)
        unregister_client_writer('proxy-1', w1)
        self.assertEqual(_client_writers['proxy-1'], {w2})

    def test_unregister_client_writer_removes_empty_key(self):
        """После удаления последнего writer ключ прокси исчезает из словаря."""
        w = MagicMock()
        register_client_writer('proxy-1', w)
        unregister_client_writer('proxy-1', w)
        self.assertNotIn('proxy-1', _client_writers)

    def test_unregister_client_writer_absent_writer_no_error(self):
        """unregister_client_writer с незарегистрированным writer не падает."""
        w = MagicMock()
        register_client_writer('proxy-1', MagicMock())
        unregister_client_writer('proxy-1', w)
        self.assertEqual(len(_client_writers['proxy-1']), 1)

    def test_close_tunnels_for_proxy_closes_client_writers(self):
        """close_tunnels_for_proxy закрывает и клиентские keep-alive туннели."""
        remote_w = MagicMock()
        client_w = MagicMock()
        register_tunnel('proxy-1', remote_w)
        register_client_writer('proxy-1', client_w)
        _all_writers.add(remote_w)
        close_tunnels_for_proxy('proxy-1')
        remote_w.close.assert_called_once()
        client_w.close.assert_called_once()
        self.assertNotIn('proxy-1', _active_tunnels)
        self.assertNotIn('proxy-1', _client_writers)

    def test_close_tunnels_for_proxy_ignores_other_proxy_client_writers(self):
        """close_tunnels_for_proxy('proxy-1') не трогает клиентские туннели proxy-2."""
        client_w1 = MagicMock()
        client_w2 = MagicMock()
        register_client_writer('proxy-1', client_w1)
        register_client_writer('proxy-2', client_w2)
        close_tunnels_for_proxy('proxy-1')
        client_w1.close.assert_called_once()
        client_w2.close.assert_not_called()
        self.assertNotIn('proxy-1', _client_writers)
        self.assertEqual(_client_writers['proxy-2'], {client_w2})

    def test_close_all_connections_closes_client_writers(self):
        """close_all_connections закрывает все клиентские keep-alive туннели."""
        client_w1 = MagicMock()
        client_w2 = MagicMock()
        register_client_writer('proxy-1', client_w1)
        register_client_writer('proxy-2', client_w2)
        close_all_connections()
        client_w1.close.assert_called_once()
        client_w2.close.assert_called_once()
        self.assertEqual(_client_writers, {})

    def test_close_all_connections_oserror_client_writer_does_not_break_others(self):
        """OSError при close() клиентского writer не прерывает закрытие остальных."""
        bad_w = MagicMock()
        bad_w.close = Mock(side_effect=OSError('already closed'))
        ok_w = MagicMock()
        register_client_writer('proxy-1', bad_w)
        register_client_writer('proxy-1', ok_w)
        close_all_connections()
        ok_w.close.assert_called_once()
        self.assertEqual(_client_writers, {})


if __name__ == '__main__':
    unittest.main()
