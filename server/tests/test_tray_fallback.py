"""
Тесты отказоустойчивости трей-бэкендов.

Тестирует:
- PystrayTray._show_popup: guard от дублей, передача tk_root
  в callbacks, обработка исключений рендера.
- __main__._try_start_tray: цепочка fallback на pystray
  с нативным меню.
"""

import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from server.tray.pystray_base import PystrayTray


class TestPystrayShowPopup(unittest.TestCase):
    """Тесты PystrayTray._show_popup."""

    def _make_tray(self):
        """Создаёт трей с mocked popup и tk_root.

        Returns:
            Кортеж (tray, popup_mock): трей и мок его popup-меню.
        """
        popup = MagicMock()
        tray = PystrayTray(callbacks={}, platform_name='Linux')
        cast(Any, tray)._popup = popup  # pylint: disable=protected-access  # internal: подмена popup-меню моком
        cast(Any, tray)._tk_root = MagicMock()  # pylint: disable=protected-access  # internal: подмена tk_root моком
        return tray, popup

    def test_returns_early_without_tk_root(self):
        """Без tk_root _show_popup ничего не делает."""
        popup = MagicMock()
        tray = PystrayTray(callbacks={}, platform_name='Linux')
        cast(Any, tray)._popup = popup  # pylint: disable=protected-access  # internal: подмена popup-меню моком
        tray._show_popup()  # pylint: disable=protected-access  # internal: проверка раннего выхода без tk_root
        popup.show.assert_not_called()

    def test_injects_tk_root_into_callbacks(self):
        """tk_root передаётся в callbacks (для «Выбрать браузер...»)."""
        tray, _ = self._make_tray()
        tray._show_popup()  # pylint: disable=protected-access  # internal: проверка передачи tk_root
        self.assertIs(tray._callbacks['tk_root'], tray._tk_root)  # pylint: disable=protected-access  # internal: проверка tk_root

    def test_builds_items_and_shows_popup(self):
        """Строит меню через build_menu_items и показывает popup."""
        tray, popup = self._make_tray()
        tray._show_popup()  # pylint: disable=protected-access  # internal: проверка построения меню
        popup.show.assert_called_once()
        _, kwargs = popup.show.call_args
        self.assertIn('items', kwargs)
        self.assertGreater(len(kwargs['items']), 0)

    def test_duplicate_guard(self):
        """Повторный вызов во время показа пропускается."""
        tray, popup = self._make_tray()
        tray._popup_open = True  # pylint: disable=protected-access  # internal: проверка guard от дублей
        tray._show_popup()  # pylint: disable=protected-access  # internal: проверка guard от дублей
        popup.show.assert_not_called()

    def test_exception_is_caught_and_flag_reset(self):
        """Ошибка рендера не выходит наружу, флаг сбрасывается."""
        tray, popup = self._make_tray()
        popup.show.side_effect = RuntimeError('не удалось показать')
        tray._show_popup()  # pylint: disable=protected-access  # internal: проверка обработки ошибок рендера
        self.assertFalse(tray._popup_open)  # pylint: disable=protected-access  # internal: проверка сброса флага

    def test_build_error_is_caught_and_flag_reset(self):
        """Ошибка в build_menu_items ловится, tk_root уже передан."""
        tray, _ = self._make_tray()
        with patch(
            'server.tray.pystray_base.build_menu_items',
            side_effect=ValueError('плохие данные'),
        ):
            tray._show_popup()  # pylint: disable=protected-access  # internal: проверка обработки ошибки построения меню
        self.assertFalse(tray._popup_open)  # pylint: disable=protected-access  # internal: проверка сброса флага


class TestTryStartTrayFallback(unittest.TestCase):
    """Тесты цепочки fallback в __main__._try_start_tray."""

    def _base_callbacks(self):
        """Минимальный набор коллбэков для тестов."""
        return {'stop': MagicMock()}

    @patch('server.__main__._start_alt_tray')
    @patch('server.__main__.start_tray')
    def test_primary_success(self, mock_start, mock_alt):
        """Основной бэкенд запущен — альтернативный не пробуем."""
        mock_start.return_value = MagicMock()
        from server.__main__ import _try_start_tray  # pylint: disable=import-outside-toplevel  # ленивый импорт: избегаем цикла
        result = _try_start_tray(
            self._base_callbacks(), no_tkinter=False,
        )
        self.assertIsNotNone(result)
        mock_alt.assert_not_called()

    @patch('server.__main__._handle_tray_error')
    @patch('server.__main__._start_alt_tray')
    @patch('server.__main__.start_tray')
    def test_primary_none_uses_alt(
        self, mock_start, mock_alt, mock_handle,
    ):
        """Основной вернул None — пробуем альтернативный."""
        mock_start.return_value = None
        mock_alt.return_value = MagicMock()
        from server.__main__ import _try_start_tray  # pylint: disable=import-outside-toplevel  # ленивый импорт: избегаем цикла
        result = _try_start_tray(
            self._base_callbacks(), no_tkinter=False,
        )
        self.assertIsNotNone(result)
        mock_alt.assert_called_once()
        mock_handle.assert_not_called()

    @patch('server.__main__._handle_tray_error')
    @patch('server.__main__._start_alt_tray')
    @patch('server.__main__.start_tray')
    def test_primary_exception_uses_alt(
        self, mock_start, mock_alt, mock_handle,
    ):
        """Основной бросил исключение — пробуем альтернативный."""
        mock_start.side_effect = OSError('нет дисплея')
        mock_alt.return_value = MagicMock()
        from server.__main__ import _try_start_tray  # pylint: disable=import-outside-toplevel  # ленивый импорт: избегаем цикла
        result = _try_start_tray(
            self._base_callbacks(), no_tkinter=False,
        )
        self.assertIsNotNone(result)
        mock_alt.assert_called_once()
        mock_handle.assert_not_called()

    @patch('server.__main__._handle_tray_error')
    @patch('server.__main__._start_alt_tray')
    @patch('server.__main__.start_tray')
    def test_all_failed_calls_handle_error(
        self, mock_start, mock_alt, mock_handle,
    ):
        """Все бэкенды недоступны — вызывается _handle_tray_error."""
        mock_start.return_value = None
        mock_alt.return_value = None
        from server.__main__ import _try_start_tray  # pylint: disable=import-outside-toplevel  # ленивый импорт: избегаем цикла
        result = _try_start_tray(
            self._base_callbacks(), no_tkinter=False,
        )
        self.assertIsNone(result)
        mock_handle.assert_called_once()

    @patch('server.__main__._handle_tray_error')
    @patch('server.__main__._start_alt_tray')
    @patch('server.__main__.start_tray')
    def test_no_tkinter_skips_alt(
        self, mock_start, mock_alt, mock_handle,
    ):
        """При --no-tkinter альтернативный бэкенд не пробуем повторно."""
        mock_start.return_value = None
        from server.__main__ import _try_start_tray  # pylint: disable=import-outside-toplevel  # ленивый импорт: избегаем цикла
        result = _try_start_tray(
            self._base_callbacks(), no_tkinter=True,
        )
        self.assertIsNone(result)
        mock_alt.assert_not_called()
        mock_handle.assert_called_once()
