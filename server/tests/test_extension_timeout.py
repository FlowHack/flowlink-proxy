"""
Тесты таймаута ожидания подключения расширения.

Проверяет текст уведомления о неподключённом расширении и поведение
_watch_api_connection при подключённом/неподключённом расширении.
"""

import asyncio
import unittest
from unittest.mock import patch

from server.__main__ import _watch_api_connection


# too-few-public-methods — тестовая заглушка threading.Thread,
# единственный публичный метод start(); класс-заглушка по назначению
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
                _watch_api_connection(server_dir='server', callbacks={}),
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
                _watch_api_connection(server_dir='server', callbacks={}),
                timeout=5,
            )

        # Уведомление не должно показываться
        self.assertEqual(len(messages), 0)
