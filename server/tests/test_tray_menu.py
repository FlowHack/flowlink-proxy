"""
Тесты модуля tray/menu.py.

Тестирует: get_autostart_state, build_menu_items, load_icon (через mock).
"""

import unittest
from unittest.mock import MagicMock, patch

from server.tray.menu import build_menu_items, get_autostart_state


class TestGetAutostartState(unittest.TestCase):
    """Тесты get_autostart_state."""

    def test_returns_true_when_enabled(self):
        """Возвращает True если autostart_getter вернул True."""
        callbacks = {'autostart_getter': lambda: True}
        self.assertTrue(get_autostart_state(callbacks))

    def test_returns_false_when_disabled(self):
        """Возвращает False если autostart_getter вернул False."""
        callbacks = {'autostart_getter': lambda: False}
        self.assertFalse(get_autostart_state(callbacks))

    def test_returns_false_when_no_getter(self):
        """Возвращает False если autostart_getter отсутствует."""
        callbacks = {}
        self.assertFalse(get_autostart_state(callbacks))

    def test_returns_false_when_getter_is_none(self):
        """Возвращает False если autostart_getter — None."""
        callbacks = {'autostart_getter': None}
        self.assertFalse(get_autostart_state(callbacks))

    def test_returns_false_on_os_error(self):
        """Возвращает False если autostart_getter бросил OSError."""
        def broken_getter():
            raise OSError('файл не найден')

        callbacks = {'autostart_getter': broken_getter}
        self.assertFalse(get_autostart_state(callbacks))

    def test_returns_false_on_type_error(self):
        """Возвращает False если autostart_getter бросил TypeError."""
        def broken_getter():
            raise TypeError('неверный тип')

        callbacks = {'autostart_getter': broken_getter}
        self.assertFalse(get_autostart_state(callbacks))

    def test_returns_false_on_attribute_error(self):
        """Возвращает False если autostart_getter бросил AttributeError."""
        def broken_getter():
            raise AttributeError('нет атрибута')

        callbacks = {'autostart_getter': broken_getter}
        self.assertFalse(get_autostart_state(callbacks))


class TestBuildMenuItems(unittest.TestCase):
    """Тесты build_menu_items."""

    def _base_callbacks(self):
        """Минимальный набор колбэков для тестов."""
        return {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }

    def test_returns_list(self):
        """build_menu_items возвращает список."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        self.assertIsInstance(items, list)

    def test_has_exit_item(self):
        """Меню содержит пункт «Выход»."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        texts = [item.get('text') for item in items]
        self.assertIn('Выход', texts)

    def test_exit_is_last(self):
        """Пункт «Выход» — последний в меню."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        self.assertEqual(items[-1]['text'], 'Выход')

    def test_has_separator_before_exit(self):
        """Перед «Выход» стоит разделитель."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        # Предпоследний элемент — разделитель
        self.assertEqual(items[-2]['type'], 'separator')

    def test_has_autostart_checks(self):
        """Меню содержит чекбоксы автозапуска и системного автозапуска."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        check_items = [
            item for item in items if item.get('type') == 'check'
        ]
        self.assertEqual(len(check_items), 2)
        self.assertEqual(
            check_items[0]['text'], 'Автозапуск браузера',
        )
        self.assertEqual(
            check_items[1]['text'], 'Запуск с системой',
        )

    def test_autostart_checked(self):
        """Чекбокс автозапуска отмечен когда getter=True."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: True,
        }
        items = build_menu_items(callbacks, MagicMock())
        check = next(
            item for item in items if item.get('type') == 'check'
        )
        self.assertTrue(check['checked'])

    def test_autostart_unchecked(self):
        """Чекбокс автозапуска не отмечен когда getter=False."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }
        items = build_menu_items(callbacks, MagicMock())
        check = next(
            item for item in items if item.get('type') == 'check'
        )
        self.assertFalse(check['checked'])

    def test_separator_count(self):
        """Два разделителя в меню (до и после автозапуска)."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        separators = [
            item for item in items if item.get('type') == 'separator'
        ]
        self.assertEqual(len(separators), 2)

    @patch('server.tray.menu.os._exit')
    def test_exit_calls_stop_fn(self, mock_exit):  # pylint: disable=unused-argument
        """Клик по «Выход» вызывает stop_fn."""
        stop_fn = MagicMock()
        callbacks = self._base_callbacks()
        items = build_menu_items(callbacks, stop_fn)

        exit_item = next(
            item for item in items if item.get('text') == 'Выход'
        )
        exit_item['command']()
        stop_fn.assert_called_once()

    @patch('server.tray.menu.os._exit')
    def test_exit_calls_stop_callback(self, mock_exit):  # pylint: disable=unused-argument
        """Клик по «Выход» вызывает callbacks['stop']."""
        callbacks = self._base_callbacks()
        items = build_menu_items(callbacks, MagicMock())

        exit_item = next(
            item for item in items if item.get('text') == 'Выход'
        )
        exit_item['command']()
        callbacks['stop'].assert_called_once()

    def test_toggle_autostart_calls_setter(self):
        """Переключение автозапуска вызывает autostart_setter."""
        setter = MagicMock()
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'autostart_setter': setter,
        }
        items = build_menu_items(callbacks, MagicMock())

        check = next(
            item for item in items if item.get('type') == 'check'
        )
        check['command']()
        setter.assert_called_once_with(True)

    def test_toggle_autostart_setter_os_error_handled(self):
        """Ошибка записи autostart не приводит к crash."""
        def broken_setter(value):
            raise OSError('нет доступа')

        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'autostart_setter': broken_setter,
        }
        items = build_menu_items(callbacks, MagicMock())

        check = next(
            item for item in items if item.get('type') == 'check'
        )
        # Не должен бросить исключение
        check['command']()

    def test_clear_logs_calls_callback(self):
        """«Очистить логи» вызывает callbacks['clear_logs']."""
        clear_logs = MagicMock()
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'clear_logs': clear_logs,
        }
        items = build_menu_items(callbacks, MagicMock())

        item = next(
            i for i in items if i.get('text') == 'Очистить логи'
        )
        item['command']()
        clear_logs.assert_called_once()

    def test_clear_data_calls_callback(self):
        """«Очистить данные» вызывает callbacks['clear_data']."""
        clear_data = MagicMock()
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'clear_data': clear_data,
        }
        items = build_menu_items(callbacks, MagicMock())

        item = next(
            i for i in items if i.get('text') == 'Очистить данные'
        )
        item['command']()
        clear_data.assert_called_once()

    @patch('server.tray.menu.webbrowser.open')
    @patch('server.tray.menu.os.makedirs')
    def test_open_logs_uses_log_dir_getter(
        self, _mock_makedirs, mock_open,
    ):
        """«Посмотреть логи» использует log_dir_getter."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'log_dir_getter': lambda: '/tmp/test-logs',
        }
        items = build_menu_items(callbacks, MagicMock())

        item = next(
            i for i in items if i.get('text') == 'Посмотреть логи'
        )
        item['command']()
        mock_open.assert_called_once()
        # URL содержит file:// и путь
        url = mock_open.call_args[0][0]
        self.assertTrue(url.startswith('file://'))

    @patch('server.tray.menu.webbrowser.open')
    @patch('server.tray.menu.get_data_dir')
    @patch('server.tray.menu.os.makedirs')
    def test_open_data_uses_get_data_dir(
        self, _mock_makedirs, mock_get_data_dir, mock_open,
    ):
        """«Посмотреть данные» использует get_data_dir."""
        mock_get_data_dir.return_value = '/tmp/test-data'
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }
        items = build_menu_items(callbacks, MagicMock())

        item = next(
            i for i in items if i.get('text') == 'Посмотреть данные'
        )
        item['command']()
        mock_open.assert_called_once()

    def test_open_logs_no_crash_when_no_getter(self):
        """«Посмотреть логи» не крашнется без log_dir_getter."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }
        items = build_menu_items(callbacks, MagicMock())

        item = next(
            i for i in items if i.get('text') == 'Посмотреть логи'
        )
        # Не должен бросить исключение
        item['command']()

    def test_clear_logs_no_crash_when_no_callback(self):
        """«Очистить логи» не крашнется без clear_logs."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }
        items = build_menu_items(callbacks, MagicMock())

        item = next(
            i for i in items if i.get('text') == 'Очистить логи'
        )
        item['command']()

    def test_each_item_has_command(self):
        """Каждый пункт меню (кроме разделителей) имеет command."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        for item in items:
            if item['type'] in ('separator', 'header'):
                continue
            self.assertIn('command', item)
            self.assertTrue(callable(item['command']))


if __name__ == '__main__':
    unittest.main()
