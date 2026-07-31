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

    async def _run_and_capture(
        self,
        browser_path: str = '',
        browser_valid: bool = False,
        ext_enabled: bool = False,
    ) -> str:
        """
        Запускает watcher с заданными настройками и возвращает текст уведомления.

        Args:
            browser_path: Значение _browser_config.get_browser_path().
            browser_valid: Значение _browser_config.validate_browser_path().
            ext_enabled: Значение _autostart.get_ext_enabled().

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
                'server.__main__.urllib.request.urlopen',
                side_effect=urllib.error.URLError('нет соединения'),
            ),
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value=browser_path,
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=browser_valid,
            ),
            patch(
                'server.__main__._autostart.get_ext_enabled',
                return_value=ext_enabled,
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
        return messages[0]

    async def test_notification_without_settings_lists_missing_steps(self):
        """Без выбранного браузера и галочки текст перечисляет оба недостающих пункта."""
        msg = await self._run_and_capture()
        self.assertIn('FlowLink Proxy запущен, но расширение не подключено.', msg)
        self.assertIn('и установленное', msg)
        self.assertIn('и запущенное расширение FlowLink Proxy.', msg)
        self.assertIn('Укажите браузер через пункт "Выбрать браузер..."', msg)
        self.assertIn('Отметьте чекбокс "Запуск с расширением"', msg)
        self.assertIn('Либо установите расширение вручную', msg)

    async def test_notification_with_all_settings_omits_done_steps(self):
        """При выбранном браузере и включённом ext_enabled текст не содержит
        пунктов про выбор браузера и галочку."""
        msg = await self._run_and_capture(
            browser_path='/usr/bin/google-chrome',
            browser_valid=True,
            ext_enabled=True,
        )
        self.assertNotIn('Укажите браузер', msg)
        self.assertNotIn('Выбрать браузер', msg)
        self.assertNotIn('Отметьте чекбокс "Запуск с расширением"', msg)
        self.assertIn('Нажмите "Запустить браузер" в меню трея', msg)
        self.assertIn('Либо установите расширение вручную', msg)

    async def test_notification_with_browser_only_lists_ext_step(self):
        """Браузер выбран, но галочка не стоит — текст упоминает только чекбокс."""
        msg = await self._run_and_capture(
            browser_path='/usr/bin/google-chrome',
            browser_valid=True,
            ext_enabled=False,
        )
        self.assertNotIn('Укажите браузер', msg)
        self.assertNotIn('Выбрать браузер', msg)
        self.assertIn('Отметьте чекбокс "Запуск с расширением"', msg)
        self.assertIn('Либо установите расширение вручную', msg)

    async def test_notification_with_ext_only_lists_browser_step(self):
        """Галочка стоит, но браузер не выбран — текст упоминает только выбор браузера."""
        msg = await self._run_and_capture(
            browser_path='',
            browser_valid=False,
            ext_enabled=True,
        )
        self.assertIn('Укажите браузер через пункт "Выбрать браузер..."', msg)
        self.assertNotIn('Отметьте чекбокс "Запуск с расширением"', msg)
        self.assertIn('Либо установите расширение вручную', msg)
