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
from unittest.mock import patch

from server.__main__ import (_EXTENSION_CHECK_INTERVAL,
                             _EXTENSION_CONNECT_TIMEOUT, _watch_api_connection)


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

    async def _run_and_capture(self) -> str:
        """
        Запускает watcher и возвращает текст уведомления.

        Returns:
            Текст уведомления, переданный в ask_yes_no.
        """
        messages = []

        def _fake_ask_yes_no(_title, message, **_kwargs):
            messages.append(message)
            return False

        with (
            patch('server.__main__._EXTENSION_CONNECT_TIMEOUT', 1),
            patch('server.__main__._EXTENSION_CHECK_INTERVAL', 1),
            patch(
                'server.__main__.is_extension_connected',
                return_value=False,
            ),
            patch(
                'server.ui.dialogs.ask_yes_no',
                side_effect=_fake_ask_yes_no,
            ),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            await asyncio.wait_for(
                _watch_api_connection(server_dir='server'),
                timeout=5,
            )

        self.assertEqual(len(messages), 1)
        return messages[0]

    async def test_notification_mentions_manual_install(self):
        """Уведомление советует установить расширение вручную."""
        msg = await self._run_and_capture()
        self.assertIn('FlowLink Proxy запущен, но расширение не подключено.', msg)
        self.assertIn(
            'Установите расширение вручную и подключите его к серверу.', msg,
        )
        self.assertIn('Инструкция доступна в справке расширения.', msg)

    async def test_notification_mentions_chromium_browsers(self):
        """Уведомление перечисляет браузеры на Chromium."""
        msg = await self._run_and_capture()
        self.assertIn('браузер на Chromium (Chrome, Edge,', msg)
        self.assertIn('Яндекс Браузер, Opera, Brave и др.)', msg)
        self.assertIn('и запущенное расширение FlowLink Proxy.', msg)

    async def test_notification_has_no_old_steps(self):
        """В уведомлении нет старых шагов про чекбокс и запуск браузера."""
        msg = await self._run_and_capture()
        self.assertNotIn('Отметьте чекбокс "Запуск с расширением"', msg)
        self.assertNotIn('Нажмите "Запустить браузер" в меню трея', msg)
        self.assertNotIn('Укажите браузер через пункт "Выбрать браузер..."', msg)


class TestWatchApiConnectionConnected(unittest.IsolatedAsyncioTestCase):
    """Поведение _watch_api_connection при подключённом расширении."""

    async def test_returns_when_extension_connected(self):
        """При подключённом расширении watcher возвращается без уведомления."""
        messages = []

        def _fake_ask_yes_no(_title, message, **_kwargs):
            messages.append(message)
            return False

        with (
            patch('server.__main__._EXTENSION_CONNECT_TIMEOUT', 120),
            patch('server.__main__._EXTENSION_CHECK_INTERVAL', 1),
            patch(
                'server.__main__.is_extension_connected',
                return_value=True,
            ),
            patch(
                'server.ui.dialogs.ask_yes_no',
                side_effect=_fake_ask_yes_no,
            ),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            await asyncio.wait_for(
                _watch_api_connection(server_dir='server'),
                timeout=5,
            )

        # Уведомление не должно показываться
        self.assertEqual(len(messages), 0)
