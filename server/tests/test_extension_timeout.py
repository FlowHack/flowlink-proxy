# pylint: disable=too-few-public-methods  # классы-заглушки (моки tk_root/Thread) для тестов
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

from server.__main__ import _show_extension_notification, _watch_api_connection

try:
    import tkinter  # pylint: disable=unused-import  # проверка доступности tkinter (нужен для тестов трея)
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False


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

    async def test_notifies_on_sse_drop_after_connect(self):
        """При обрыве SSE после подключения watcher показывает уведомление повторно."""
        notification_shown = asyncio.Event()

        def _fake_ask_yes_no(_title, _message, **_kwargs):
            notification_shown.set()
            return False

        # Первые проверки — подключено, затем обрыв и удержание в отключённом
        connected_states = iter([True, True, False, False, False])

        def _fake_connected():
            return next(connected_states)

        with (
            patch('server.__main__._EXTENSION_CONNECT_TIMEOUT', 120),
            patch('server.__main__._EXTENSION_CHECK_INTERVAL', 1),
            patch('server.__main__._EXTENSION_NOTIFY_INTERVAL', 0),
            patch(
                'server.__main__.is_extension_connected',
                side_effect=_fake_connected,
            ),
            patch(
                'server.ui.dialogs.ask_yes_no',
                side_effect=_fake_ask_yes_no,
            ),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            task = asyncio.create_task(
                _watch_api_connection(
                    server_dir='server', callbacks={},
                    monitor_after_connect=True,
                ),
            )
            # Детерминированно ждём именно уведомление (без гонки таймеров:
            # ждём asyncio.Event, выставленный диалогом, а не sleep+cancel)
            await asyncio.wait_for(notification_shown.wait(), timeout=5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Обрыв после подключения — уведомление показано
        self.assertTrue(notification_shown.is_set())


class _FakeTkRoot:
    """Заглушка tk_root трея для проверки планирования диалога через after(0, ...).

    run_callbacks=False имитирует занятый mainloop: коллбэк after не
    выполняется, и поток уведомления должен дождаться таймаута и
    продолжить без диалога.
    """

    def __init__(self, run_callbacks: bool = True):
        self.run_callbacks = run_callbacks
        self.after_calls: list = []

    def after(self, delay_ms: int, callback) -> None:
        """Записывает планирование и при необходимости выполняет коллбэк."""
        self.after_calls.append((delay_ms, callback))
        if self.run_callbacks and delay_ms == 0:
            callback()


class TestExtensionNotificationWithTrayRoot(unittest.TestCase):
    """Поведение уведомления при доступном tk_root трея (кросс-потоковый tkinter).

    tkinter не потокобезопасен: ask_yes_no должен выполняться в mainloop-
    потоке трея через after(0, ...), а поток уведомления — лишь ожидать
    результат (или таймаут), не блокируя _watch_api_connection.
    """

    @unittest.skipUnless(_HAS_TKINTER, 'tkinter недоступен')
    def test_dialog_runs_via_after_in_tray_root(self):
        """ask_yes_no вызывается через after(0, ...) в потоке трея, результат дожидается."""
        root = _FakeTkRoot()
        ask_kwargs: list = []

        def _fake_ask_yes_no(_title, _message, **_kwargs):
            ask_kwargs.append(_kwargs)
            return True

        browser_calls = []

        def _fake_open(url, *_args, **_kwargs):
            browser_calls.append(url)
            return True

        with (
            patch('server.ui.dialogs.ask_yes_no', side_effect=_fake_ask_yes_no),
            patch('os.path.isfile', return_value=True),
            patch('server.__main__.webbrowser.open', side_effect=_fake_open),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            _show_extension_notification('server', {'tk_root': root})

        # Диалог запланирован через after(0, ...) в потоке трея
        self.assertEqual(len(root.after_calls), 1)
        self.assertEqual(root.after_calls[0][0], 0)
        # ask_yes_no выполнен ровно один раз и привязан к tk_root трея
        self.assertEqual(len(ask_kwargs), 1)
        self.assertIs(ask_kwargs[0]['parent_root'], root)
        # Ответ «Да» → открыта локальная инструкция
        expected = f'file://{os.path.abspath("extension/popup/help.html")}'
        self.assertEqual(browser_calls, [expected])

    @unittest.skipUnless(_HAS_TKINTER, 'tkinter недоступен')
    def test_dialog_exception_in_tray_thread_graceful(self):
        """Исключение в ask_yes_no в потоке трея → без падения и без браузера."""
        root = _FakeTkRoot()
        browser_calls = []

        def _fake_open(url, *_args, **_kwargs):
            browser_calls.append(url)
            return True

        with (
            patch(
                'server.ui.dialogs.ask_yes_no',
                side_effect=RuntimeError('tkinter crashed'),
            ),
            patch('os.path.isfile', return_value=True),
            patch('server.__main__.webbrowser.open', side_effect=_fake_open),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            # Не должно быть исключений: диалог пропускается, mainloop трея цел
            _show_extension_notification('server', {'tk_root': root})

        # Исключение перехвачено в коллбэке потока трея: инструкция не открывается
        self.assertEqual(browser_calls, [])

    @unittest.skipUnless(_HAS_TKINTER, 'tkinter недоступен')
    def test_timeout_when_tray_mainloop_busy(self):
        """Занятый mainloop трея (коллбэк after не выполняется) → таймаут без диалога."""
        root = _FakeTkRoot(run_callbacks=False)
        ask_calls: list = []

        def _fake_ask_yes_no(*_args, **_kwargs):
            ask_calls.append(True)
            return True

        browser_calls = []

        def _fake_open(url, *_args, **_kwargs):
            browser_calls.append(url)
            return True

        with (
            patch('server.__main__._NOTIFICATION_DIALOG_TIMEOUT', 0.2),
            patch('server.ui.dialogs.ask_yes_no', side_effect=_fake_ask_yes_no),
            patch('os.path.isfile', return_value=True),
            patch('server.__main__.webbrowser.open', side_effect=_fake_open),
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            # Не должно быть исключений: уведомление просто пропускается
            _show_extension_notification('server', {'tk_root': root})

        # Коллбэк запланирован, но не выполнен (mainloop занят)
        self.assertEqual(len(root.after_calls), 1)
        # Диалог не показывался, браузер не открывался
        self.assertEqual(ask_calls, [])
        self.assertEqual(browser_calls, [])

    @unittest.skipUnless(_HAS_TKINTER, 'tkinter недоступен')
    def test_after_raises_when_root_closed(self):
        """after() бросает RuntimeError (root закрыт) → уведомление пропускается без падения."""

        class _BrokenRoot:
            """Заглушка root с закрытым Tcl-интерпретатором."""

            def after(self, _delay_ms, _callback):
                """Заглушка after(): имитирует закрытый/нерабочий root трея."""
                raise RuntimeError('invalid command name "after"')

        with (
            patch('server.ui.dialogs.ask_yes_no') as ask_mock,
            patch('os.path.isfile', return_value=True),
            patch('server.__main__.webbrowser.open') as open_mock,
            patch('server.__main__.threading.Thread', new=_SyncThread),
        ):
            # Не должно быть исключений: root закрыт — диалог просто не показывается
            _show_extension_notification('server', {'tk_root': _BrokenRoot()})

        ask_mock.assert_not_called()
        open_mock.assert_not_called()
