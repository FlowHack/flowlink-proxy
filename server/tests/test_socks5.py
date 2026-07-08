"""
Тесты обработки исключений Socks5Protocol.
"""

import asyncio
import unittest

from server.protocols.socks5 import Socks5Error, Socks5Protocol


class TestSocks5Exceptions(unittest.TestCase):

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
