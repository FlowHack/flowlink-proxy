"""
Тесты колбэка закрытия браузера из __main__.py (_close_browser_callback).

Проверяет:
- невалидный путь к браузеру → False, kill не вызывается;
- браузер не запущен через прокси → True (закрывать нечего);
- браузер запущен через прокси и успешно закрыт → True;
- сбой завершения процессов → False.

Примечание: browser_process импортируется лениво внутри функции, поэтому
моки ставятся на атрибуты модуля server.config.browser_process, а не на
server.__main__._browser_process.
"""

import unittest
from unittest.mock import patch

from server.__main__ import _close_browser_callback


class TestCloseBrowserCallback(unittest.TestCase):
    """Тесты _close_browser_callback — закрытие браузера с прокси."""

    def test_invalid_path_returns_false(self):
        """Невалидный путь к браузеру — False, kill не вызывается."""
        with (
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value='',
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=False,
            ),
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
            ) as mock_running,
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
        ):
            result = _close_browser_callback(_callbacks={}, proxy_port=8080)

        self.assertFalse(result)
        mock_running.assert_not_called()
        mock_kill.assert_not_called()

    def test_not_running_with_proxy_returns_true(self):
        """Браузер не запущен через прокси — True, kill не вызывается."""
        with (
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value='/usr/bin/google-chrome',
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=False,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
        ):
            result = _close_browser_callback(_callbacks={}, proxy_port=8080)

        self.assertTrue(result)
        mock_kill.assert_not_called()

    def test_kill_success_returns_true(self):
        """Браузер запущен с прокси и успешно закрыт — True."""
        with (
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value='/usr/bin/google-chrome',
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=True,
            ) as mock_kill,
        ):
            result = _close_browser_callback(_callbacks={}, proxy_port=8080)

        self.assertTrue(result)
        mock_kill.assert_called_once_with('/usr/bin/google-chrome')

    def test_kill_failure_returns_false(self):
        """Сбой завершения процессов — False."""
        with (
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value='/usr/bin/google-chrome',
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=False,
            ),
        ):
            result = _close_browser_callback(_callbacks={}, proxy_port=8080)

        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
