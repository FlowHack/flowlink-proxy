"""
Тесты SSE-шины событий events.py.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.events import (_MAX_QUEUE_SIZE, SSE_QUEUE, emit_event,
                                    handle_sse)


class TestEventsQueue(unittest.TestCase):
    """Тесты управления очередью событий."""

    def setUp(self):
        # Очищаем очередь перед каждым тестом
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

    def test_emit_event_multiple(self):
        """Несколько emit_event добавляют несколько событий"""
        async def run():
            await emit_event('event1', {'a': 1})
            await emit_event('event2', {'b': 2})
            await emit_event('event3', {'c': 3})
            self.assertEqual(SSE_QUEUE.qsize(), 3)
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

            with patch('server.services.events._SSE_KEEPALIVE_TIMEOUT', 0.1), \
                 patch('server.services.events.get_queue', return_value=queue):
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

            with patch('server.services.events._SSE_KEEPALIVE_TIMEOUT', 0.1), \
                 patch('server.services.events.get_queue', return_value=queue):
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
