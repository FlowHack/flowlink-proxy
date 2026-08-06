"""
Тесты SSE-шины событий events.py.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.events import (_MAX_QUEUE_SIZE, SSE_QUEUE, emit_event)
from server.services.sse import handle_sse


async def _wait_event(flag: asyncio.Event, timeout: float = 1.0) -> None:
    """Ожидает установки asyncio.Event без asyncio.wait_for.

    В тестах asyncio.wait_for может быть замокан (для детерминизма),
    поэтому ожидание реализовано коротким поллингом с жёстким таймаутом.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not flag.is_set():
        if loop.time() > deadline:
            raise TimeoutError('Таймаут ожидания asyncio.Event в тесте')
        await asyncio.sleep(0.01)


def _timeout_wait_for():
    """Возвращает замену asyncio.wait_for, сразу бросающую TimeoutError.

    Входящий awaitable закрывается, чтобы не оставались непотреблённые
    корутины (иначе RuntimeWarning «coroutine was never awaited»).
    """
    async def fake_wait_for(  # pylint: disable=unused-argument  # имя timeout фиксировано вызовом asyncio.wait_for
        awaitable, timeout=None,
    ):
        # Сначала закрываем awaitable — если задача будет отменена во время
        # sleep(0) ниже, корутина queue.get() уже закрыта (нет RuntimeWarning).
        if awaitable is not None:
            awaitable.close()
        # ВАЖНО: await asyncio.sleep(0) ДО броска TimeoutError — иначе исключение
        # возникает синхронно (до первого await) и цикл handle_sse не отдаёт
        # управление event loop: бесконечный цикл, монополизирующий CPU.
        await asyncio.sleep(0)
        raise asyncio.TimeoutError
    return fake_wait_for


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
    """Тесты keepalive-механизма SSE-соединения.

    Детерминированность достигается патчем asyncio.wait_for: вместо реальных
    задержек таймаут эмулируется немедленным TimeoutError, а момент записи
    нужного payload фиксируется asyncio.Event — без sleep-зависимых ассертов.
    """

    def _make_writer(self, flag_event: asyncio.Event, needle: bytes):
        """Создаёт mock-писатель, выставляющий flag_event при записи needle.

        Args:
            flag_event: asyncio.Event, выставляется после записи payload
                с искомым байтовым фрагментом.
            needle: Байтовый фрагмент, по которому определяется нужная запись.

        Returns:
            MagicMock-писатель с асинхронным drain.
        """
        writer = MagicMock()
        writer.get_extra_info.return_value = ('127.0.0.1', 12345)
        writer.write = MagicMock()

        async def drain():
            if flag_event.is_set():
                return
            for call in writer.write.call_args_list:
                payload = call[0][0]
                if isinstance(payload, bytes) and needle in payload:
                    flag_event.set()
                    break
        writer.drain = AsyncMock(side_effect=drain)
        return writer

    def test_keepalive_sent_when_no_events(self):
        """При пустой очереди отправляется keepalive-комментарий.

        Патчим asyncio.wait_for так, чтобы он сразу выбрасывал TimeoutError —
        цикл SSE немедленно переходит к отправке keepalive без реальных задержек.
        """
        async def run():
            queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
            keepalive_sent = asyncio.Event()
            writer = self._make_writer(keepalive_sent, b': keepalive')

            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue), \
                 patch(
                     'server.services.sse.asyncio.wait_for',
                     new=_timeout_wait_for(),
                 ):
                task = asyncio.create_task(handle_sse(writer))
                await _wait_event(keepalive_sent)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            payloads = [c[0][0] for c in writer.write.call_args_list]
            self.assertTrue(
                any(b': keepalive' in p for p in payloads),
                'keepalive-комментарий не был отправлен',
            )
        asyncio.run(run())

    def test_event_sent_after_keepalive(self):
        """Событие отправляется после keepalive если очередь не пуста.

        Первый вызов wait_for выбрасывает TimeoutError (keepalive), затем
        событие из очереди забирается реальным queue.get() — без sleep.
        """
        async def run():
            queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)

            event_sent = asyncio.Event()
            writer = self._make_writer(event_sent, b'event: test')

            calls = 0

            async def fake_wait_for(  # pylint: disable=unused-argument  # имя timeout фиксировано вызовом asyncio.wait_for
                awaitable, timeout=None,
            ):
                nonlocal calls
                calls += 1
                if calls == 1:
                    if awaitable is not None:
                        awaitable.close()
                    # handle_sse очищает очередь при подключении, поэтому
                    # событие, положенное до старта, было бы выброшено как
                    # устаревшее — кладём его ПОСЛЕ первой итерации: на
                    # второй итерации queue.get() заберёт его без sleep.
                    queue.put_nowait({'event': 'test', 'data': {'msg': 'hello'}})
                    # await ДО броска TimeoutError — см. _timeout_wait_for
                    await asyncio.sleep(0)
                    raise asyncio.TimeoutError
                # Последующие вызовы — реальное ожидание события из очереди
                return await awaitable

            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue), \
                 patch(
                     'server.services.sse.asyncio.wait_for', new=fake_wait_for,
                 ):
                task = asyncio.create_task(handle_sse(writer))
                await _wait_event(event_sent)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            payloads = [c[0][0] for c in writer.write.call_args_list]
            event_payloads = [p for p in payloads if b'event: test' in p]
            self.assertEqual(len(event_payloads), 1)
            self.assertIn(b'"msg": "hello"', event_payloads[0])
        asyncio.run(run())


class TestSSEAuthAndCors(unittest.TestCase):
    """Тесты проверки токена и CORS-allowlist в handle_sse.

    Детерминированность: headers_sent-флаг (asyncio.Event) выставляется
    сразу после записи заголовков, реальных задержек нет.
    """

    def _make_writer(self, headers_sent: asyncio.Event | None = None):
        """Создаёт mock-писатель для SSE-соединения.

        Args:
            headers_sent: Если задан — выставляется после первой записи.

        Returns:
            MagicMock-писатель с асинхронным drain.
        """
        writer = MagicMock()
        writer.get_extra_info.return_value = ('127.0.0.1', 12345)
        writer.write = MagicMock()

        async def drain():
            if headers_sent is not None and not headers_sent.is_set():
                if writer.write.call_count >= 1:
                    headers_sent.set()
        writer.drain = AsyncMock(side_effect=drain)
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
            headers_sent = asyncio.Event()
            writer = self._make_writer(headers_sent)
            queue = asyncio.Queue()
            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue), \
                 patch(
                     'server.services.sse.asyncio.wait_for',
                     new=_timeout_wait_for(),
                 ):
                task = asyncio.create_task(
                    handle_sse(writer, auth_token='secret', token='secret')
                )
                await _wait_event(headers_sent)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            calls = writer.write.call_args_list
            self.assertGreaterEqual(len(calls), 1)
            self.assertIn(b'HTTP/1.1 200', calls[0][0][0])
        asyncio.run(run())

    def test_cors_header_for_extension_origin(self):
        """Origin chrome-extension:// → Access-Control-Allow-Origin в SSE."""
        async def run():
            headers_sent = asyncio.Event()
            writer = self._make_writer(headers_sent)
            queue = asyncio.Queue()
            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue), \
                 patch(
                     'server.services.sse.asyncio.wait_for',
                     new=_timeout_wait_for(),
                 ):
                task = asyncio.create_task(
                    handle_sse(writer, origin='chrome-extension://abc123')
                )
                await _wait_event(headers_sent)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            first = writer.write.call_args_list[0][0][0]
            self.assertIn(
                b'Access-Control-Allow-Origin: chrome-extension://abc123',
                first,
            )
            self.assertIn(b'Vary: Origin', first)
        asyncio.run(run())

    def test_no_cors_for_foreign_origin(self):
        """Чужой Origin → без Access-Control-Allow-Origin в SSE."""
        async def run():
            headers_sent = asyncio.Event()
            writer = self._make_writer(headers_sent)
            queue = asyncio.Queue()
            with patch('server.services.sse._SSE_KEEPALIVE_TIMEOUT', 0.05), \
                 patch('server.services.sse.get_queue', return_value=queue), \
                 patch(
                     'server.services.sse.asyncio.wait_for',
                     new=_timeout_wait_for(),
                 ):
                task = asyncio.create_task(
                    handle_sse(writer, origin='http://evil.example.com')
                )
                await _wait_event(headers_sent)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            first = writer.write.call_args_list[0][0][0]
            self.assertNotIn(b'Access-Control-Allow-Origin:', first)
        asyncio.run(run())
