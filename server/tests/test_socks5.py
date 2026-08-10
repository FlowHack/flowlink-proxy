"""
Тесты обработки исключений и интеграционные тесты Socks5Protocol.
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from server.protocols.mock_socks5 import MockSocks5Server
from server.protocols.socks5 import Socks5Error, Socks5Protocol


def _run_with_server(server, coro):
    """
    Запускает корутину с заданным mock-сервером на отдельном цикле.

    Args:
        server: Экземпляр MockSocks5Server.
        coro: Корутина для выполнения.

    Returns:
        Результат корутины.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.start())
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(server.stop())
        loop.close()


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
        """Ping живого прокси → (True, None)"""
        async def run():
            proto = self._make_proto()
            alive, error_kind = await proto.ping(timeout=3)
            self.assertTrue(alive)
            self.assertIsNone(error_kind)
        self.loop.run_until_complete(run())

    def test_ping_dead_proxy(self):
        """Ping мёртвого прокси → (False, 'refused' или 'timeout').

        В разных окружениях закрытый порт даёт либо ConnectionRefusedError
        ('refused'), либо таймаут ('timeout') — например, при фильтрации
        брандмауэром. Оба варианта означают «прокси недоступен».
        """
        async def run():
            proto = self._make_proto(port=1)
            alive, error_kind = await proto.ping(timeout=0.5)
            self.assertFalse(alive)
            self.assertIn(error_kind, ('refused', 'timeout'))
        self.loop.run_until_complete(run())


class TestSocks5HandshakeReject(unittest.TestCase):
    """Негативные handshake-кейсы: отказ метода и отказ CONNECT."""

    def test_method_negotiation_rejected(self):
        """Отказ на method negotiation → Socks5Error."""
        server = MockSocks5Server(reject_methods=True)

        async def run():
            proto = Socks5Protocol({
                'host': '127.0.0.1',
                'port': server.port,
            })
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=443,
                    timeout=3,
                )

        _run_with_server(server, run())

    def test_connect_rejected(self):
        """Отказ на CONNECT → Socks5Error."""
        server = MockSocks5Server(reject_connect=True)

        async def run():
            proto = Socks5Protocol({
                'host': '127.0.0.1',
                'port': server.port,
            })
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=443,
                    timeout=3,
                )

        _run_with_server(server, run())


class TestSocks5UserpassAuth(unittest.TestCase):
    """Тесты USERPASS-аутентификации (метод 0x02)."""

    def test_userpass_auth_success(self):
        """Верные credentials → CONNECT успешен."""
        server = MockSocks5Server(
            require_userpass=True,
            username='user',
            password='pass',
        )

        async def run():
            proto = Socks5Protocol({
                'host': '127.0.0.1',
                'port': server.port,
                'username': 'user',
                'password': 'pass',
            })
            reader, writer = await proto.connect(
                target_host='example.com',
                target_port=443,
                timeout=3,
            )
            self.assertIsNotNone(reader)
            self.assertIsNotNone(writer)
            writer.close()
            await writer.wait_closed()

        _run_with_server(server, run())

    def test_userpass_wrong_credentials(self):
        """Неверные credentials → Socks5Error."""
        server = MockSocks5Server(
            require_userpass=True,
            username='user',
            password='pass',
        )

        async def run():
            proto = Socks5Protocol({
                'host': '127.0.0.1',
                'port': server.port,
                'username': 'user',
                'password': 'wrong',
            })
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=443,
                    timeout=3,
                )

        _run_with_server(server, run())

    def test_userpass_not_supported_by_server(self):
        """Сервер без USERPASS при запросе USERPASS → NO_ACCEPTABLE → Socks5Error.

        Mock-сервер моделирует сервер, поддерживающий только NO AUTH:
        если клиент предлагает USERPASS, сервер отвечает 0xFF
        (нет приемлемого метода аутентификации).
        """
        server = MockSocks5Server(reject_userpass=True)

        async def run():
            proto = Socks5Protocol({
                'host': '127.0.0.1',
                'port': server.port,
                'username': 'user',
                'password': 'pass',
            })
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=443,
                    timeout=3,
                )

        _run_with_server(server, run())

    def test_no_credentials_uses_no_auth(self):
        """Без credentials клиент предлагает только NO AUTH (не USERPASS).

        Сервер с require_userpass=True соглашается на USERPASS (0x02),
        только если клиент предложил этот метод. Клиент без credentials
        предлагает лишь NO AUTH → сервер отвечает 0xFF → Socks5Error.
        Это подтверждает, что без credentials клиент использует NO AUTH.
        """
        server = MockSocks5Server(require_userpass=True)

        async def run():
            proto = Socks5Protocol({
                'host': '127.0.0.1',
                'port': server.port,
            })
            with self.assertRaises(Socks5Error):
                await proto.connect(
                    target_host='example.com',
                    target_port=443,
                    timeout=3,
                )

        _run_with_server(server, run())


class TestSocks5Cancellation(unittest.TestCase):
    """Тесты закрытия writer при отмене (CancelledError) в _do_connect."""

    def test_cancelled_connect_closes_writer(self):
        """При отмене по таймауту writer закрывается (нет утечки TCP)."""
        async def run():
            proto = Socks5Protocol({'host': '127.0.0.1', 'port': 1080})
            writer = MagicMock()
            writer.close = MagicMock()
            writer.is_closing.return_value = False

            async def fake_open_connection(_host, _port):
                # Возвращаем reader и writer сразу — отмена произойдёт
                # на этапе _handshake (внутри try-блока _do_connect)
                reader = MagicMock()
                return reader, writer

            async def fake_handshake(_self, _reader, _writer):
                # Зависаем, чтобы wait_for отменил корутину
                await asyncio.sleep(10)

            with patch(
                'server.protocols.socks5.asyncio.open_connection',
                side_effect=fake_open_connection,
            ), patch(
                'server.protocols.socks5.Socks5Protocol._handshake',
                new=fake_handshake,
            ):
                # В Python 3.12 asyncio.wait_for при таймауте бросает TimeoutError,
                # но внутренняя корутина отменяется через CancelledError.
                with self.assertRaises((asyncio.CancelledError, asyncio.TimeoutError)):
                    await asyncio.wait_for(
                        proto.connect(
                            target_host='example.com',
                            target_port=80,
                            timeout=5,
                        ),
                        timeout=0.1,
                    )
            # writer должен быть закрыт после отмены
            writer.close.assert_called()

        asyncio.run(run())
