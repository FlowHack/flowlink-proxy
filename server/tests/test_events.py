"""
Тесты SSE-шины событий events.py.
"""

import asyncio
import unittest

from server.services.events import (_MAX_QUEUE_SIZE, SSE_QUEUE, emit_event)


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
