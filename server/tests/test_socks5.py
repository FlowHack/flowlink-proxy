"""
Тесты обработки исключений и интеграционные тесты Socks5Protocol.
"""

import asyncio
import unittest

from server.protocols.mock_socks5 import MockSocks5Server
from server.protocols.socks5 import Socks5Error, Socks5Protocol


class TestSocks5Exceptions(unittest.TestCase):
    """Тесты обработки исключений Socks5Protocol."""

    def _make_proto(self, host='127.0.0.1', port=9, **kwargs) -> Socks5Protocol:
        config = {'host': host, 'port': port, **kwargs}
        return Socks5Protocol(config)

    def test_connect_timeout_raises_socks5_error(self):
        """Таймаут подключения → Socks5Error"""
        async def run():
            proto = self._make_proto(host='192.0.2.1', port=1080)
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=80,
                    timeout=0.1,
                )
        asyncio.run(run())

    def test_connect_refused_raises_socks5_error(self):
        """Соединение отклонено → Socks5Error"""
        async def run():
            proto = self._make_proto(host='127.0.0.1', port=9)
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=80,
                    timeout=2,
                )
        asyncio.run(run())

    def test_empty_username_password_no_auth(self):
        """Пустые логин/пароль → без аутентификации"""
        async def run():
            proto = self._make_proto(host='127.0.0.1', port=9, username='', password='')
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=80,
                    timeout=1,
                )
        asyncio.run(run())


class TestSocks5Integration(unittest.TestCase):
    """Интеграционные тесты Socks5Protocol с mock-сервером."""

    def setUp(self):
        self.mock_server = MockSocks5Server()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.mock_server.start())

    def tearDown(self):
        self.loop.run_until_complete(self.mock_server.stop())
        self.loop.close()

    def _make_proto(self, **kwargs) -> Socks5Protocol:
        config = {'host': '127.0.0.1', 'port': self.mock_server.port, **kwargs}
        return Socks5Protocol(config)

    def test_successful_connect(self):
        """Успешный CONNECT через mock-сервер"""
        async def run():
            proto = self._make_proto()
            reader, writer = await proto.connect(
                target_host='example.com',
                target_port=443,
                timeout=3,
            )
            self.assertIsNotNone(reader)
            self.assertIsNotNone(writer)
            writer.close()
            await writer.wait_closed()
        self.loop.run_until_complete(run())

    def test_successful_connect_ipv4(self):
        """CONNECT к IPv4 адресу"""
        async def run():
            proto = self._make_proto()
            reader, writer = await proto.connect(
                target_host='1.2.3.4',
                target_port=80,
                timeout=3,
            )
            self.assertIsNotNone(reader)
            writer.close()
            await writer.wait_closed()
        self.loop.run_until_complete(run())

    def test_ping_alive(self):
        """Ping живого прокси → True"""
        async def run():
            proto = self._make_proto()
            result = await proto.ping(timeout=3)
            self.assertTrue(result)
        self.loop.run_until_complete(run())

    def test_ping_dead_proxy(self):
        """Ping мёртвого прокси → False"""
        async def run():
            proto = self._make_proto(port=1)
            result = await proto.ping(timeout=0.5)
            self.assertFalse(result)
        self.loop.run_until_complete(run())
