"""
Тесты пересылки данных (pipe) и проверки доступности прокси (ping).

Покрывают реальные функции server/services/pipe.py и server/services/ping.py
с асинхронными моками потоков: читатель — AsyncMock (read/at_eof),
писатель — MagicMock с асинхронным drain.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.i18n import _
from server.services.pipe import (
    _pipe_data,
    pipe,
    pipe_http_request,
    pipe_http_response,
)
from server.services.ping import ping_proxy


def _make_reader(chunks):
    """Создаёт мок потока чтения, отдающий заданные чанки данных.

    at_eof() в реальном коде вызывается синхронно, поэтому он — MagicMock;
    read() асинхронный, поэтому — AsyncMock.
    """
    reader = MagicMock()
    reader.read = AsyncMock(side_effect=chunks)
    reader.at_eof = MagicMock(return_value=False)
    return reader


def _make_writer():
    """Создаёт мок потока записи с асинхронным drain."""
    writer = MagicMock()
    writer.drain = AsyncMock()
    return writer


class TestPipeData(unittest.IsolatedAsyncioTestCase):
    """Тесты утилиты _pipe_data — однонаправленной пересылки данных."""

    async def test_pipe_data_transfers_all_chunks(self):
        """Проверяет, что _pipe_data передаёт все чанки до пустого."""
        src = _make_reader([b'data1', b'data2', b''])
        dst = _make_writer()

        await _pipe_data(src, dst, 'тест')

        self.assertEqual(dst.write.call_count, 2)
        self.assertEqual(dst.write.call_args_list[0][0][0], b'data1')
        self.assertEqual(dst.write.call_args_list[1][0][0], b'data2')
        dst.drain.assert_awaited()
        dst.close.assert_called_once()

    async def test_pipe_data_stops_on_empty_read(self):
        """Проверяет, что _pipe_data завершается на пустом чанке."""
        src = _make_reader([b'data', b''])
        dst = _make_writer()

        await _pipe_data(src, dst, 'тест')

        self.assertEqual(dst.write.call_count, 1)
        dst.close.assert_called_once()

    async def test_pipe_data_handles_connection_error(self):
        """Проверяет, что разрыв соединения не пробрасывается наружу."""
        src = MagicMock()
        src.read = AsyncMock(side_effect=ConnectionError('соединение разорвано'))
        src.at_eof = MagicMock(return_value=False)
        dst = _make_writer()

        await _pipe_data(src, dst, 'тест')

        dst.close.assert_called_once()

    async def test_pipe_data_closes_writer_on_os_error(self):
        """Проверяет, что ошибка закрытия писателя не роняет функцию."""
        src = _make_reader([b'data', b''])
        dst = _make_writer()
        dst.close.side_effect = OSError('ошибка закрытия')

        await _pipe_data(src, dst, 'тест')

        # Функция завершилась без исключения, ошибка закрытия залогирована.
        dst.close.assert_called_once()


class TestPipe(unittest.IsolatedAsyncioTestCase):
    """Тесты функции pipe — двунаправленной пересылки данных."""

    async def test_pipe_transfers_data_bidirectionally(self):
        """Проверяет, что pipe передаёт данные в обоих направлениях."""
        client_reader = _make_reader([b'client_data', b''])
        client_writer = _make_writer()
        remote_reader = _make_reader([b'remote_data', b''])
        remote_writer = _make_writer()

        await pipe(client_reader, client_writer, remote_reader, remote_writer)

        # Клиент -> удалённый сервер
        self.assertEqual(remote_writer.write.call_count, 1)
        self.assertEqual(remote_writer.write.call_args_list[0][0][0], b'client_data')
        # Удалённый сервер -> клиент
        self.assertEqual(client_writer.write.call_count, 1)
        self.assertEqual(client_writer.write.call_args_list[0][0][0], b'remote_data')
        remote_writer.close.assert_called_once()
        client_writer.close.assert_called_once()


class TestPipeHttpRequest(unittest.IsolatedAsyncioTestCase):
    """Тесты функции pipe_http_request — пересылки тела HTTP-запроса."""

    async def test_pipe_http_request_transfers_data(self):
        """Проверяет, что тело запроса передаётся удалённому серверу."""
        client_reader = _make_reader([b'request_data', b''])
        remote_writer = _make_writer()

        await pipe_http_request(client_reader, remote_writer)

        self.assertEqual(remote_writer.write.call_count, 1)
        self.assertEqual(remote_writer.write.call_args_list[0][0][0], b'request_data')
        remote_writer.close.assert_called_once()


class TestPipeHttpResponse(unittest.IsolatedAsyncioTestCase):
    """Тесты функции pipe_http_response — пересылки тела HTTP-ответа."""

    async def test_pipe_http_response_transfers_data(self):
        """Проверяет, что тело ответа передаётся клиенту."""
        remote_reader = _make_reader([b'response_data', b''])
        client_writer = _make_writer()

        await pipe_http_response(remote_reader, client_writer)

        self.assertEqual(client_writer.write.call_count, 1)
        self.assertEqual(client_writer.write.call_args_list[0][0][0], b'response_data')
        client_writer.close.assert_called_once()


class TestPingProxy(unittest.IsolatedAsyncioTestCase):
    """Тесты функции ping_proxy — проверки доступности прокси."""

    @patch('server.services.ping.cfg')
    @patch('server.services.ping.get_protocol')
    async def test_ping_proxy_success(self, mock_get_protocol, mock_cfg):
        """Проверяет, что успешный пинг возвращает alive=True и latency."""
        mock_cfg.get_proxy_by_id.return_value = {
            'proxyId': 'test_proxy',
            'host': '127.0.0.1',
            'port': 8080,
        }
        mock_protocol = MagicMock()
        mock_protocol.ping = AsyncMock(return_value=(True, None))
        mock_get_protocol.return_value = mock_protocol

        result = await ping_proxy('test_proxy')

        self.assertTrue(result['alive'])
        self.assertIsInstance(result['latency'], int)

    @patch('server.services.ping.cfg')
    async def test_ping_proxy_not_found(self, mock_cfg):
        """Проверяет, что неизвестный прокси возвращает alive=False."""
        mock_cfg.get_proxy_by_id.return_value = None

        result = await ping_proxy('nonexistent_proxy')

        self.assertFalse(result['alive'])
        self.assertIsNone(result['latency'])
        self.assertEqual(result['error'], _('Прокси не найден'))

    @patch('server.services.ping.cfg')
    @patch('server.services.ping.get_protocol')
    async def test_ping_proxy_connection_refused(self, mock_get_protocol, mock_cfg):
        """Проверяет, что отказ соединения возвращает errorKind='refused'."""
        mock_cfg.get_proxy_by_id.return_value = {
            'proxyId': 'test_proxy',
            'host': '127.0.0.1',
            'port': 8080,
        }
        mock_protocol = MagicMock()
        mock_protocol.ping = AsyncMock(return_value=(False, 'refused'))
        mock_get_protocol.return_value = mock_protocol

        result = await ping_proxy('test_proxy')

        self.assertFalse(result['alive'])
        self.assertIsNone(result['latency'])
        self.assertEqual(result['errorKind'], 'refused')

    @patch('server.services.ping.cfg')
    async def test_ping_proxy_config_error(self, mock_cfg):
        """Проверяет, что ошибка конфига возвращает alive=False с ошибкой."""
        mock_cfg.get_proxy_by_id.side_effect = OSError('нет доступа к конфигу')

        result = await ping_proxy('test_proxy')

        self.assertFalse(result['alive'])
        self.assertIsNone(result['latency'])
        self.assertIn('error', result)
