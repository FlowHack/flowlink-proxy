"""
Тесты автозапуска браузера при старте бэкенда (_run_server).

Проверяет:
- _start_tray_icon возвращает кортеж (tray, callbacks);
- при get_autostart_browser()=True и валидном пути без трея браузер
  запускается через _launch_browser_sync;
- при запущенном трее запуск планируется в mainloop-потоке через
  tk_root.after(0, ...) (_launch_browser_callback);
- callbacks['tk_root'] не перезаписывается, если он уже установлен
  (пользователь открыл меню до автозапуска);
- при невалидном пути выводится предупреждение и запуск не выполняется.
"""

import argparse
import asyncio
import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

from server.__main__ import _run_server, _start_tray_icon


def _make_server_mock():
    """Создаёт мок сервера с awaitable start()/stop()."""
    server = MagicMock()
    server.start = AsyncMock(return_value=None)
    server.stop = AsyncMock(return_value=None)
    return server


def _make_args() -> argparse.Namespace:
    """Создаёт минимальный argparse.Namespace для _run_server."""
    args = argparse.Namespace()
    args.proxy_port = 8080
    args.api_port = 8081
    args.debug = False
    args.dev = False
    args.need_update = False
    args.no_tkinter = False
    args.test_fallback_icon = False
    args.count_proxy = 0
    args.browser_path = None
    return args


class _FakeTray:
    """Фейковый трей с публичными свойствами tk_root/popup."""

    def __init__(self) -> None:
        self._tk_root = MagicMock()
        self._popup = MagicMock()

    @property
    def tk_root(self):
        """Возвращает корневой Tk трея (или None)."""
        return self._tk_root

    @property
    def popup(self):
        """Возвращает popup-меню трея (или None)."""
        return self._popup


def _enter_runtime_patches(
    stack: ExitStack,
    tray_icon,
    callbacks: dict,
) -> None:
    """Применяет общие патенчи для запуска _run_server.

    Заменяет серверы, сокеты, signal handlers и os._exit, чтобы корутина
    отработала до конца без реальной сети и выхода из процесса.
    """
    stop_event = MagicMock()
    stop_event.wait = AsyncMock(return_value=None)
    stack.enter_context(patch(
        'server.__main__.asyncio.Event', return_value=stop_event,
    ))
    stack.enter_context(patch('server.__main__.MaskRouter'))
    stack.enter_context(patch(
        'server.__main__.ProxyServer', return_value=_make_server_mock(),
    ))
    stack.enter_context(patch(
        'server.__main__.ApiServer', return_value=_make_server_mock(),
    ))
    stack.enter_context(patch('server.__main__.write_port_file'))
    stack.enter_context(patch(
        'server.__main__._watch_api_connection', new=AsyncMock(),
    ))
    stack.enter_context(patch('server.__main__._setup_signal_handlers'))
    stack.enter_context(patch('server.__main__.os._exit'))
    stack.enter_context(patch(
        'server.__main__._start_tray_icon',
        return_value=(tray_icon, callbacks),
    ))


def _patch_autostart_enabled(stack: ExitStack, browser_path: str) -> None:
    """Включает автозапуск и подменяет путь браузера (валидный)."""
    stack.enter_context(patch(
        'server.__main__._autostart.get_autostart_browser',
        return_value=True,
    ))
    stack.enter_context(patch(
        'server.__main__._browser_config.get_browser_path',
        return_value=browser_path,
    ))
    stack.enter_context(patch(
        'server.__main__._browser_config.validate_browser_path',
        return_value=True,
    ))


class TestStartTrayIconReturnsTuple(unittest.TestCase):
    """Новая сигнатура _start_tray_icon — кортеж (tray, callbacks)."""

    def test_returns_tuple_when_tray_unavailable(self):
        """Без трея возвращается (None, {})."""
        args = _make_args()
        loop = asyncio.new_event_loop()
        try:
            with (
                patch('server.__main__._HAS_TRAY', False),
                patch('server.__main__.sys.frozen', True, create=True),
            ):
                tray, callbacks = _start_tray_icon(
                    loop, asyncio.Event(), args,
                )
        finally:
            loop.close()

        self.assertIsNone(tray)
        self.assertEqual(callbacks, {})


class TestAutostartBrowserAtStartup(unittest.TestCase):
    """Автозапуск браузера в _run_server."""

    def test_without_tray_uses_sync_launch(self):
        """Без трея автозапуск вызывает _launch_browser_sync."""
        args = _make_args()
        callbacks: dict = {}
        mock_sync: MagicMock | None = None

        async def run() -> None:
            nonlocal mock_sync
            with ExitStack() as stack:
                _enter_runtime_patches(stack, None, callbacks)
                _patch_autostart_enabled(stack, '/fake/browser')
                mock_sync = stack.enter_context(patch(
                    'server.__main__._launch_browser_sync',
                ))
                await _run_server(args)

        asyncio.run(run())
        assert mock_sync is not None
        mock_sync.assert_called_once_with(callbacks, '/fake/browser', 8080)

    def test_with_tray_schedules_callback_in_mainloop(self):
        """При трее запуск планируется через tk_root.after(0, ...)."""
        args = _make_args()
        callbacks: dict = {}
        tray = _FakeTray()
        mock_sync: MagicMock | None = None
        mock_cb: MagicMock | None = None

        async def run() -> None:
            nonlocal mock_sync, mock_cb
            with ExitStack() as stack:
                _enter_runtime_patches(stack, tray, callbacks)
                _patch_autostart_enabled(stack, '/fake/browser')
                mock_sync = stack.enter_context(patch(
                    'server.__main__._launch_browser_sync',
                ))
                mock_cb = stack.enter_context(patch(
                    'server.__main__._launch_browser_callback',
                ))
                await _run_server(args)

                mock_sync.assert_not_called()

                # Планирование через after(0, ...) — коллбэк выполняется в mainloop.
                # Вызываем scheduled() ВНУТРИ ExitStack, пока патчи активны,
                # иначе реальный _launch_browser_callback покажет tkinter-диалог.
                tray.tk_root.after.assert_called_once()
                scheduled = tray.tk_root.after.call_args.args[1]
                scheduled()
                mock_cb.assert_called_once()
                # В словарь, переданный в _launch_browser_callback, должны попасть
                # tk_root и popup трея (для диалога «браузер уже запущен»).
                cb_callbacks = mock_cb.call_args.args[0]
                self.assertIs(cb_callbacks['tk_root'], tray.tk_root)
                self.assertIs(cb_callbacks['popup'], tray.popup)
                self.assertEqual(mock_cb.call_args.args[1], 8080)

        asyncio.run(run())

    def test_does_not_overwrite_existing_tk_root(self):
        """Уже установленный callbacks['tk_root'] не перезаписывается."""
        args = _make_args()
        existing_root = MagicMock()
        callbacks = {'tk_root': existing_root}
        tray = _FakeTray()
        mock_sync: MagicMock | None = None
        mock_cb: MagicMock | None = None

        async def run() -> None:
            nonlocal mock_sync, mock_cb
            with ExitStack() as stack:
                _enter_runtime_patches(stack, tray, callbacks)
                _patch_autostart_enabled(stack, '/fake/browser')
                mock_sync = stack.enter_context(patch(
                    'server.__main__._launch_browser_sync',
                ))
                mock_cb = stack.enter_context(patch(
                    'server.__main__._launch_browser_callback',
                ))
                await _run_server(args)

        asyncio.run(run())

        # Существующий корень не заменён, popup не записан
        self.assertIs(callbacks['tk_root'], existing_root)
        self.assertNotIn('popup', callbacks)
        assert mock_sync is not None
        assert mock_cb is not None
        mock_sync.assert_called_once()
        mock_cb.assert_not_called()

    def test_invalid_path_logs_warning_and_no_launch(self):
        """Невалидный путь → предупреждение, запуск не выполняется."""
        args = _make_args()
        callbacks: dict = {}
        mock_sync: MagicMock | None = None

        async def run() -> None:
            nonlocal mock_sync
            with ExitStack() as stack:
                _enter_runtime_patches(stack, None, callbacks)
                stack.enter_context(patch(
                    'server.__main__._autostart.get_autostart_browser',
                    return_value=True,
                ))
                stack.enter_context(patch(
                    'server.__main__._browser_config.get_browser_path',
                    return_value='/bad/path',
                ))
                stack.enter_context(patch(
                    'server.__main__._browser_config.validate_browser_path',
                    return_value=False,
                ))
                mock_sync = stack.enter_context(patch(
                    'server.__main__._launch_browser_sync',
                ))
                await _run_server(args)

        with self.assertLogs('flowlink', level='WARNING') as logs:
            asyncio.run(run())

        assert mock_sync is not None
        mock_sync.assert_not_called()
        self.assertTrue(any(
            'не выбран или невалиден' in message for message in logs.output
        ))

    def test_write_port_file_error_does_not_kill_server(self):
        """Ошибка записи порт-файла не останавливает уже запущенные серверы."""
        args = _make_args()
        callbacks: dict = {}
        proxy_server = _make_server_mock()
        api_server = _make_server_mock()

        async def run() -> None:
            with ExitStack() as stack:
                _enter_runtime_patches(stack, None, callbacks)
                # Подменяем серверы на захваченные моки, чтобы проверить их запуск
                stack.enter_context(patch(
                    'server.__main__.ProxyServer',
                    return_value=proxy_server,
                ))
                stack.enter_context(patch(
                    'server.__main__.ApiServer',
                    return_value=api_server,
                ))
                # write_port_file бросает OSError — сервер не должен падать
                stack.enter_context(patch(
                    'server.__main__.write_port_file',
                    side_effect=OSError('permission denied'),
                ))
                await _run_server(args)

        # Не должно бросать исключение — сервер продолжает работу
        asyncio.run(run())

        # Несмотря на ошибку записи порт-файла, серверы запускаются
        proxy_server.start.assert_awaited_once()
        api_server.start.assert_awaited_once()
