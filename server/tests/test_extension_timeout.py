"""
Тесты таймаута ожидания подключения расширения.

Проверяет реальную логику _watch_api_connection: показ уведомления ровно
один раз при неподключённом расширении, выбор help_path (локальный файл
или GitHub-инструкция), ветку webbrowser.open при ответе «Да» на
ask_yes_no и fallback на браузер при ошибке в диалоге.
"""

import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from server.__main__ import _watch_api_connection


# too-few-public-methods — тестовая заглушка threading.Thread,
# единственный публичный метод start(); класс-заглушка по назначению
class _SyncThread:  # pylint: disable=too-few-public-methods
    """Заглушка threading.Thread: запускает target синхронно в start().

    Позволяет проверить поведение _show_notification без реального
    потока и модального диалога.
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

    async def _run_watcher(
        self,
        ask_yes_no_mock: MagicMock,
        isfile_value: bool = True,
    ) -> list[str]:
        """Запускает watcher и возвращает URL, переданные в webbrowser.open.

        Args:
            ask_yes_no_mock: Мок диалога (return_value или side_effect).
            isfile_value: Возвращаемое значение os.path.isfile для help_path.

        Returns:
            Список аргументов вызовов webbrowser.open.
        """
        browser_calls = []

        def _fake_open(url, *_args, **_kwargs):
            browser_calls.append(url)
            return True

        with (
            patch('server.__main__._EXTENSION_CONNECT_TIMEOUT', 1),
            patch('server.__main__._EXTENSION_CHECK_INTERVAL', 1),
            patch(
                'server.__main__.is_extension_connected',
                return_value=False,
            ),
            patch('server.ui.dialogs.ask_yes_no', ask_yes_no_mock),
            patch('os.path.isfile', return_value=isfile_value),
            patch(
                'server.__main__.webbrowser.open',
                side_effect=_fake_open,
            ),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            await asyncio.wait_for(
                _watch_api_connection(server_dir='server', callbacks={}),
                timeout=5,
            )
        return browser_calls

    async def test_notification_shown_once_when_disconnected(self):
        """При неподключённом расширении уведомление показывается один раз."""
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
        self.assertIsInstance(messages[0], str)

    async def test_yes_opens_local_help_when_file_exists(self):
        """Ответ «Да» при существующем help.html → открывается локальный файл."""
        calls = await self._run_watcher(
            MagicMock(return_value=True), isfile_value=True,
        )
        self.assertEqual(len(calls), 1)
        expected = f'file://{os.path.abspath("extension/popup/help.html")}'
        self.assertEqual(calls[0], expected)

    async def test_yes_opens_github_when_help_missing(self):
        """Ответ «Да» при отсутствующем help.html → GitHub-инструкция."""
        calls = await self._run_watcher(
            MagicMock(return_value=True), isfile_value=False,
        )
        self.assertEqual(
            calls,
            ['https://github.com/FlowHack/flowlink-proxy/blob/main/SETUP.md'],
        )

    async def test_no_answer_does_not_open_browser(self):
        """Ответ «Нет» → браузер не открывается."""
        calls = await self._run_watcher(MagicMock(return_value=False))
        self.assertEqual(calls, [])

    async def test_notification_exception_falls_back_to_browser(self):
        """Ошибка в диалоге → fallback: инструкция открывается в браузере."""
        calls = await self._run_watcher(
            MagicMock(side_effect=RuntimeError('tkinter crashed')),
            isfile_value=False,
        )
        self.assertEqual(
            calls,
            ['https://github.com/FlowHack/flowlink-proxy/blob/main/SETUP.md'],
        )


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
