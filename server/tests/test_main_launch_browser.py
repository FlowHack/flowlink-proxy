"""
Тесты запуска браузера из __main__.py.

Проверяет:
- уведомление о невыбранном браузере при нажатии «Запустить браузер»
  (пустой/невалидный путь → диалог и возврат False);
- поведение _show_browser_not_selected_dialog при наличии tk_root и без него.
"""

import unittest
from unittest.mock import MagicMock, patch

from server.__main__ import (_launch_browser_callback, _launch_browser_sync,
                             _show_browser_not_selected_dialog)


class TestLaunchBrowserNotSelected(unittest.TestCase):
    """Уведомление при запуске браузера без выбранного пути."""

    def test_callback_empty_path_returns_false_and_shows_dialog(self):
        """Пустой путь в _launch_browser_callback → False и диалог."""
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
                'server.__main__._show_browser_not_selected_dialog',
            ) as mock_dialog,
        ):
            result = _launch_browser_callback(callbacks={}, proxy_port=8080)

        self.assertFalse(result)
        mock_dialog.assert_called_once()

    def test_sync_empty_path_returns_false_and_shows_dialog(self):
        """Пустой путь в _launch_browser_sync → False и диалог."""
        with (
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=False,
            ),
            patch(
                'server.__main__._show_browser_not_selected_dialog',
            ) as mock_dialog,
        ):
            result = _launch_browser_sync(
                callbacks={}, browser_path='', proxy_port=8080,
            )

        self.assertFalse(result)
        mock_dialog.assert_called_once()


class TestBrowserNotSelectedDialog(unittest.TestCase):
    """Поведение _show_browser_not_selected_dialog."""

    def test_no_tk_root_logs_and_returns(self):
        """Без tk_root функция не падает и ничего не показывает."""
        with patch(
            'server.ui.dialogs.show_info',
        ) as mock_show_info:
            _show_browser_not_selected_dialog(callbacks={})

        mock_show_info.assert_not_called()

    def test_with_tk_root_shows_info(self):
        """С tk_root показывается диалог с заголовком и кнопкой OK."""
        tk_root = MagicMock()
        with patch(
            'server.ui.dialogs.show_info',
        ) as mock_show_info:
            _show_browser_not_selected_dialog(callbacks={'tk_root': tk_root})

        mock_show_info.assert_called_once()
        kwargs = mock_show_info.call_args.kwargs
        self.assertEqual(kwargs['title'], 'Браузер не выбран')
        self.assertIn('Выбрать браузер', kwargs['message'])
        self.assertEqual(
            kwargs['buttons'],
            [{'text': 'OK', 'primary': True}],
        )
        self.assertIs(kwargs['parent_root'], tk_root)
