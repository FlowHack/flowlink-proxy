"""
Тесты SSE-шины событий events.py.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.events import (_MAX_QUEUE_SIZE, SSE_QUEUE, emit_event)
from server.services.sse import handle_sse


class TestEventsQueue(unittest.TestCase):
    """Тесты управления очередью событий."""

    def setUp(self):
        """Очищаем глобальную очередь перед каждым тестом."""
        self._clear_queue()

    def tearDown(self):
        """Очищаем очередь после теста — защита от утечки между тестами."""
        self._clear_queue()

    def _clear_queue(self):
        """Сбрасывает глобальную SSE_QUEUE."""
        while not SSE_QUEUE.empty():
            try:
                SSE_QUEUE.get_nowait()
            except asyncio.QueueEmpty:
                break

    def test_emit_event_adds_to_queue(self):
        """emit_event добавляет событие в очередь"""
        async def run():
            await emit_event('test_event', {'key': 'value'})
            self.assertFalse(SSE_QUEUE.empty())
            event = SSE_QUEUE.get_nowait()
            self.assertEqual(event['event'], 'test_event')
            self.assertEqual(event['data'], {'key': 'value'})
        asyncio.run(run())

    def test_emit_event_queue_full(self):
        """При заполненной очереди событие отбрасывается (не падает)"""
        async def run():
            # Заполняем очередь до максимума
            for _ in range(_MAX_QUEUE_SIZE):
                SSE_QUEUE.put_nowait({'event': 'filler', 'data': {}})
            # Попытка добавить ещё одно событие
            await emit_event('overflow', {'d': 4})
            # Очередь не должна вырасти за maxsize
            self.assertLessEqual(SSE_QUEUE.qsize(), _MAX_QUEUE_SIZE)
        asyncio.run(run())


class TestSSEKeepalive(unittest.TestCase):
    """Тесты keepalive-механизма SSE-соединения."""

    def _clear_queue(self, queue):
        """Очищает очередь."""
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def test_keepalive_sent_when_no_events(self):
        """При пустой очереди > таймаута отправляется keepalive-комментарий"""
        async def run():
            queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
            self._clear_queue(queue)

            writer = MagicMock()
            writer.get_extra_info.return_value = ('127.0.0.1', 12345)
            writer.write = MagicMock()
            writer.drain = AsyncMock()

            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.1), \
                 patch('server.services.sse.get_queue', return_value=queue):
                task = asyncio.create_task(handle_sse(writer))
                await asyncio.sleep(0.3)

                calls = writer.write.call_args_list
                self.assertGreaterEqual(len(calls), 2)
                keepalive_call = calls[1]
                self.assertIn(b': keepalive', keepalive_call[0][0])

                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        asyncio.run(run())

    def test_event_sent_after_keepalive(self):
        """Событие отправляется после keepalive если очередь не пуста"""
        async def run():
            queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
            self._clear_queue(queue)

            writer = MagicMock()
            writer.get_extra_info.return_value = ('127.0.0.1', 12345)
            writer.write = MagicMock()
            writer.drain = AsyncMock()

            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.1), \
                 patch('server.services.sse.get_queue', return_value=queue):
                task = asyncio.create_task(handle_sse(writer))
                await asyncio.sleep(0.2)

                queue.put_nowait({'event': 'test', 'data': {'msg': 'hello'}})
                await asyncio.sleep(0.1)

                calls = writer.write.call_args_list
                payloads = [c[0][0] for c in calls]
                event_payloads = [p for p in payloads if b'event: test' in p]
                self.assertEqual(len(event_payloads), 1)
                self.assertIn(b'"msg": "hello"', event_payloads[0])

                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        asyncio.run(run())


class TestSSEAuthAndCors(unittest.TestCase):
    """Тесты проверки токена и CORS-allowlist в handle_sse."""

    def _make_writer(self):
        """Создаёт mock-писатель для SSE-соединения."""
        writer = MagicMock()
        writer.get_extra_info.return_value = ('127.0.0.1', 12345)
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        return writer

    def test_rejects_invalid_token_without_data(self):
        """Неверный токен → соединение закрывается без отправки данных."""
        async def run():
            writer = self._make_writer()
            await handle_sse(writer, auth_token='secret', token='wrong')
            self.assertEqual(writer.write.call_count, 0)
        asyncio.run(run())

    def test_accepts_valid_token_and_sends_headers(self):
        """Верный токен → отправляются SSE-заголовки."""
        async def run():
            writer = self._make_writer()
            queue = asyncio.Queue()
            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue):
                task = asyncio.create_task(
                    handle_sse(writer, auth_token='secret', token='secret')
                )
                await asyncio.sleep(0.15)
                calls = writer.write.call_args_list
                self.assertGreaterEqual(len(calls), 1)
                self.assertIn(b'HTTP/1.1 200', calls[0][0][0])
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        asyncio.run(run())

    def test_cors_header_for_extension_origin(self):
        """Origin chrome-extension:// → Access-Control-Allow-Origin в SSE."""
        async def run():
            writer = self._make_writer()
            queue = asyncio.Queue()
            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue):
                task = asyncio.create_task(
                    handle_sse(writer, origin='chrome-extension://abc123')
                )
                await asyncio.sleep(0.15)
                first = writer.write.call_args_list[0][0][0]
                self.assertIn(
                    b'Access-Control-Allow-Origin: chrome-extension://abc123',
                    first,
                )
                self.assertIn(b'Vary: Origin', first)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        asyncio.run(run())

    def test_no_cors_for_foreign_origin(self):
        """Чужой Origin → без Access-Control-Allow-Origin в SSE."""
        async def run():
            writer = self._make_writer()
            queue = asyncio.Queue()
            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue):
                task = asyncio.create_task(
                    handle_sse(writer, origin='http://evil.example.com')
                )
                await asyncio.sleep(0.15)
                first = writer.write.call_args_list[0][0][0]
                self.assertNotIn(b'Access-Control-Allow-Origin:', first)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        asyncio.run(run())
