"""
Тесты таймаута ожидания подключения расширения.

Проверяет:
- значение константы _EXTENSION_CONNECT_TIMEOUT (120 секунд = 2 минуты);
- что цикл _watch_api_connection использует константы,
  а не захардкоженные значения;
- текст уведомления о неподключённом расширении.
"""

import asyncio
import inspect
import unittest
import urllib.error
from unittest.mock import patch

from server.__main__ import (
    _EXTENSION_CHECK_INTERVAL,
    _EXTENSION_CONNECT_TIMEOUT,
    _watch_api_connection,
)


class _SyncThread:  # pylint: disable=too-few-public-methods
    """Заглушка threading.Thread: запускает target синхронно в start().

    Позволяет проверить текст уведомления без реального потока и
    модального диалога.
    """

    def __init__(self, target=None, **kwargs):
        self._target = target
        self.daemon = kwargs.get('daemon', False)

    def start(self) -> None:
        """Выполняет target в текущем потоке."""
        if self._target is not None:
            self._target()


class TestExtensionTimeoutConstant(unittest.TestCase):
    """Проверка значений констант таймаута."""

    def test_timeout_is_two_minutes(self):
        """Таймаут ожидания расширения равен 120 секундам (2 минуты)."""
        self.assertEqual(_EXTENSION_CONNECT_TIMEOUT, 120)

    def test_check_interval_is_ten_seconds(self):
        """Интервал проверки равен 10 секундам."""
        self.assertEqual(_EXTENSION_CHECK_INTERVAL, 10)


class TestWatchApiConnectionLoop(unittest.TestCase):
    """Проверка, что цикл ожидания использует константы."""

    def test_loop_uses_connect_timeout_constant(self):
        """range() в цикле использует _EXTENSION_CONNECT_TIMEOUT."""
        source = inspect.getsource(_watch_api_connection)
        self.assertIn(
            'range(0, _EXTENSION_CONNECT_TIMEOUT, _EXTENSION_CHECK_INTERVAL)',
            source,
        )

    def test_loop_has_no_hardcoded_300(self):
        """В цикле отсутствует захардкоженное значение 300."""
        source = inspect.getsource(_watch_api_connection)
        self.assertNotIn('range(0, 300', source)


class TestWatchApiConnectionNotification(unittest.IsolatedAsyncioTestCase):
    """Поведение _watch_api_connection при неподключённом расширении."""

    async def test_starts_notification_with_new_message(self):
        """При недоступном API запускается уведомление с новым текстом."""
        messages = []

        def _fake_ask_yes_no(_title, message, **_kwargs):
            messages.append(message)
            return False

        with (
            patch('server.__main__._EXTENSION_CONNECT_TIMEOUT', 1),
            patch('server.__main__._EXTENSION_CHECK_INTERVAL', 1),
            patch(
                'server.__main__.urllib.request.urlopen',
                side_effect=urllib.error.URLError('нет соединения'),
            ),
            patch(
                'server.ui.dialogs.ask_yes_no',
                side_effect=_fake_ask_yes_no,
            ),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            await asyncio.wait_for(
                _watch_api_connection(api_port=1, server_dir='server'),
                timeout=5,
            )

        self.assertEqual(len(messages), 1)
        msg = messages[0]
        self.assertIn('FlowLink Proxy запущен, но расширение не подключено.', msg)
        self.assertIn('и установленное', msg)
        self.assertIn('и запущенное расширение FlowLink Proxy.', msg)
        self.assertIn('«Запустить браузер»', msg)
        self.assertIn('расширение подключится автоматически.', msg)
