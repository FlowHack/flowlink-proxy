"""
Тесты модуля tray/menu.py.

Тестирует: get_autostart_state, build_menu_items, load_icon (через mock).
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from server.tray.menu import (_close_browser_now, _handle_browser_on_exit,
                              _select_browser,
                              _toggle_close_browser_with_app,
                              build_menu_items, get_autostart_state)


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
        """Три чекбокса: автозапуск, автозакрытие браузера и запуск с системой."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        check_items = [
            item for item in items if item.get('type') == 'check'
        ]
        self.assertEqual(len(check_items), 3)
        self.assertEqual(
            check_items[0]['text'], 'Автозапуск браузера',
        )
        self.assertEqual(
            check_items[1]['text'], 'Автозакрытие браузера',
        )
        self.assertEqual(
            check_items[2]['text'], 'Запуск с системой',
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
        """Три разделителя в меню (после пунктов данных, после чекбоксов, перед выходом)."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        separators = [
            item for item in items if item.get('type') == 'separator'
        ]
        self.assertEqual(len(separators), 3)

    @patch('server.tray.menu.os._exit')
    # Параметр mock_exit — мок os._exit, нужен для @patch,
    # но в тесте не используется (unused-argument)
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
    # Параметр mock_exit — мок os._exit, нужен для @patch,
    # но в тесте не используется (unused-argument)
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


class TestBuildMenuItemsTooltipFields(unittest.TestCase):
    """Тесты поля tooltip в пунктах меню."""

    def _items(self):
        """Строит меню с базовыми колбэками."""
        return build_menu_items(
            {
                'stop': MagicMock(),
                'autostart_getter': lambda: False,
            },
            MagicMock(),
        )

    def test_all_items_and_checks_have_tooltip(self):
        """Каждый пункт type=item/check содержит непустой tooltip."""
        items = self._items()
        for item in items:
            if item.get('type') in ('item', 'check'):
                self.assertIn('tooltip', item, f'нет tooltip у {item.get("text")!r}')
                self.assertTrue(
                    item['tooltip'],
                    f'пустой tooltip у {item.get("text")!r}',
                )

    def test_separators_have_no_tooltip(self):
        """Разделители не содержат tooltip."""
        items = self._items()
        for item in items:
            if item.get('type') == 'separator':
                self.assertNotIn('tooltip', item)

    def test_specific_tooltip_texts(self):
        """Ключевые пункты имеют ожидаемые подсказки."""
        items = self._items()
        by_text = {i.get('text'): i for i in items}
        self.assertEqual(
            by_text['Выход']['tooltip'],
            'Завершить работу FlowLink Proxy',
        )
        self.assertEqual(
            by_text['Автозапуск браузера']['tooltip'],
            'Запускать браузер автоматически при старте системы',
        )
        self.assertEqual(
            by_text['Выбрать браузер...']['tooltip'],
            'Указать, какой браузер использовать',
        )


class TestBuildMenuItemsCommands(unittest.TestCase):
    """Тесты команд пунктов меню (поведение без tkinter)."""

    def _base_callbacks(self):
        """Минимальный набор колбэков для тестов."""
        return {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }

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

    def test_select_browser_exists(self):
        """Пункт «Выбрать браузер...» присутствует в меню."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        texts = [item.get('text') for item in items]
        self.assertIn('Выбрать браузер...', texts)

    def test_launch_browser_exists(self):
        """Пункт «Запустить браузер» присутствует в меню."""
        items = build_menu_items(
            self._base_callbacks(), MagicMock(),
        )
        texts = [item.get('text') for item in items]
        self.assertIn('Запустить браузер', texts)


class TestBrowserSelectedMarker(unittest.TestCase):
    """Тесты зелёной пометки у пункта «Выбрать браузер...»."""

    def _browser_item(self, callbacks):
        """Возвращает пункт «Выбрать браузер...» из построенного меню."""
        items = build_menu_items(callbacks, MagicMock())
        return next(
            item for item in items
            if item.get('text', '').startswith('Выбрать браузер')
        )

    @patch('server.config.browser_config.validate_browser_path', return_value=True)
    def test_marker_present_when_path_valid(self, _mock_validate):
        """При валидном browser_path пункт получает пометку и зелёный цвет."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'browser_path_getter': lambda: '/usr/bin/google-chrome',
        }
        item = self._browser_item(callbacks)
        self.assertEqual(item['text'], 'Выбрать браузер... ✓')
        self.assertEqual(item.get('color'), '#2ecc71')

    def test_marker_absent_without_path(self):
        """Без browser_path пункт «Выбрать браузер...» остаётся без пометки."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
        }
        item = self._browser_item(callbacks)
        self.assertEqual(item['text'], 'Выбрать браузер...')
        self.assertTrue(not item.get('color'))

    @patch('server.config.browser_config.validate_browser_path', return_value=False)
    def test_marker_absent_when_path_invalid(self, _mock_validate):
        """При невалидном browser_path пометка не добавляется."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'browser_path_getter': lambda: '/nonexistent/browser',
        }
        item = self._browser_item(callbacks)
        self.assertEqual(item['text'], 'Выбрать браузер...')
        self.assertTrue(not item.get('color'))


class TestSelectBrowserItems(unittest.TestCase):
    """Тесты формирования списка браузеров в _select_browser."""

    def _base_callbacks(self, detected, current_path):
        """Минимальный набор колбэков для _select_browser."""
        return {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'tk_root': MagicMock(),
            'browser_detector': lambda: detected,
            'browser_path_getter': lambda: current_path,
            'browser_path_saver': MagicMock(),
        }

    def _capture_items(self, callbacks):
        """Вызывает _select_browser и возвращает items из show_item_picker."""
        captured = {}

        def _fake_picker(**kwargs):
            captured.update(kwargs)

        with patch(
            'server.ui.dialogs.show_item_picker',
            side_effect=_fake_picker,
        ):
            _select_browser(callbacks, MagicMock())

        return captured['items']

    def test_adds_manually_selected_browser_to_items(self):
        """Выбранный ненайденный браузер добавляется в конец списка выбранным."""
        detected = [
            {'name': 'Google Chrome', 'path': '/usr/bin/google-chrome'},
        ]
        current_path = '/opt/custom/chrome-browser'
        callbacks = self._base_callbacks(detected, current_path)

        with patch(
            'server.config.browser_config.validate_browser_path',
            return_value=True,
        ):
            items = self._capture_items(callbacks)

        self.assertEqual(len(items), 2)
        last = items[-1]
        self.assertEqual(last['label'], os.path.basename(current_path))
        self.assertEqual(last['subtitle'], current_path)
        self.assertEqual(last['path'], current_path)
        self.assertTrue(last['selected'])
        # Найденный браузер — не выбран
        self.assertFalse(items[0]['selected'])

    def test_does_not_add_invalid_manual_path(self):
        """Невалидный выбранный ненайденный путь не добавляется в список."""
        detected = [
            {'name': 'Google Chrome', 'path': '/usr/bin/google-chrome'},
        ]
        current_path = '/opt/custom/missing-browser'
        callbacks = self._base_callbacks(detected, current_path)

        with patch(
            'server.config.browser_config.validate_browser_path',
            return_value=False,
        ):
            items = self._capture_items(callbacks)

        self.assertEqual(len(items), 1)
        self.assertFalse(items[0]['selected'])

    def test_marks_detected_browser_as_selected(self):
        """Выбранный среди найденных браузер помечается selected=True."""
        detected = [
            {'name': 'Google Chrome', 'path': '/usr/bin/google-chrome'},
            {'name': 'Mozilla Firefox', 'path': '/usr/bin/firefox'},
        ]
        current_path = '/usr/bin/firefox'
        callbacks = self._base_callbacks(detected, current_path)

        items = self._capture_items(callbacks)

        self.assertEqual(len(items), 2)
        by_path = {item['path']: item['selected'] for item in items}
        self.assertTrue(by_path['/usr/bin/firefox'])
        self.assertFalse(by_path['/usr/bin/google-chrome'])


class TestToggleCloseBrowserWithApp(unittest.TestCase):
    """Тесты переключения настройки «Автозакрытие браузера»."""

    def test_toggle_calls_setter(self):
        """Переключение вызывает close_browser_with_app_setter с инвертированным значением."""
        setter = MagicMock()
        callbacks = {'close_browser_with_app_setter': setter}
        _toggle_close_browser_with_app(callbacks, MagicMock(), current_value=False)
        setter.assert_called_once_with(True)

    def test_toggle_false_calls_setter(self):
        """Выключение настройки передаёт False в setter."""
        setter = MagicMock()
        callbacks = {'close_browser_with_app_setter': setter}
        _toggle_close_browser_with_app(callbacks, MagicMock(), current_value=True)
        setter.assert_called_once_with(False)

    def test_setter_os_error_handled(self):
        """Ошибка записи настройки не приводит к исключению."""
        def broken_setter(value):
            raise OSError('нет доступа')

        callbacks = {'close_browser_with_app_setter': broken_setter}
        # Не должен бросить исключение
        _toggle_close_browser_with_app(callbacks, MagicMock(), current_value=False)

    def test_no_setter_logs_warning(self):
        """Отсутствие setter не приводит к падению."""
        _toggle_close_browser_with_app({}, MagicMock(), current_value=False)


class TestCloseBrowserNow(unittest.TestCase):
    """Тесты пункта меню «Закрыть браузер»."""

    def test_calls_browser_closer(self):
        """Вызывает browser_closer из callbacks."""
        closer = MagicMock(return_value=True)
        callbacks = {'browser_closer': closer}
        _close_browser_now(callbacks, MagicMock())
        closer.assert_called_once()

    def test_no_closer_no_crash(self):
        """Отсутствие browser_closer не приводит к падению."""
        _close_browser_now({}, MagicMock())


class TestHandleBrowserOnExit(unittest.TestCase):
    """Тесты _handle_browser_on_exit — закрытие браузера при выходе."""

    def _callbacks(self, browser_path='', proxy_port=None, **extra):
        """Базовый набор колбэков для _handle_browser_on_exit."""
        callbacks = {
            'browser_path_getter': lambda: browser_path,
            'proxy_port': proxy_port,
        }
        callbacks.update(extra)
        return callbacks

    def test_no_browser_path_does_nothing(self):
        """Без пути браузера ничего не происходит (kill и диалог не вызываются)."""
        callbacks = self._callbacks(browser_path='', proxy_port=8080)
        with (
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
            ) as mock_running,
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
            patch('server.ui.dialogs.show_info') as mock_dialog,
        ):
            _handle_browser_on_exit(callbacks, MagicMock())

        mock_running.assert_not_called()
        mock_kill.assert_not_called()
        mock_dialog.assert_not_called()

    def test_no_proxy_port_does_nothing(self):
        """Без порта прокси ничего не происходит."""
        callbacks = self._callbacks(browser_path='/usr/bin/google-chrome', proxy_port=None)
        with (
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
            ) as mock_running,
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
            patch('server.ui.dialogs.show_info') as mock_dialog,
        ):
            _handle_browser_on_exit(callbacks, MagicMock())

        mock_running.assert_not_called()
        mock_kill.assert_not_called()
        mock_dialog.assert_not_called()

    def test_browser_not_running_with_proxy_does_nothing(self):
        """Браузер не запущен через прокси — ничего не делаем."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
            close_browser_with_app_getter=lambda: True,
        )
        with (
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=False,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
            patch('server.ui.dialogs.show_info') as mock_dialog,
        ):
            _handle_browser_on_exit(callbacks, MagicMock())

        mock_kill.assert_not_called()
        mock_dialog.assert_not_called()

    def test_setting_enabled_kills_silently(self):
        """Настройка включена — браузер закрывается молча, без диалога."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
            close_browser_with_app_getter=lambda: True,
        )
        with (
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
            patch('server.ui.dialogs.show_info') as mock_dialog,
        ):
            _handle_browser_on_exit(callbacks, MagicMock())

        mock_kill.assert_called_once_with('/usr/bin/google-chrome')
        mock_dialog.assert_not_called()

    def test_setting_disabled_shows_dialog(self):
        """Настройка выключена — показывается диалог, kill не вызывается."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
            close_browser_with_app_getter=lambda: False,
            tk_root=MagicMock(),
        )
        with (
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
            patch('server.ui.dialogs.show_info') as mock_dialog,
        ):
            _handle_browser_on_exit(callbacks, MagicMock())

        mock_kill.assert_not_called()
        mock_dialog.assert_called_once()
        kwargs = mock_dialog.call_args.kwargs
        self.assertEqual(kwargs['title'], 'Закрыть браузер?')
        self.assertIs(kwargs['parent_root'], callbacks['tk_root'])

    def test_setting_disabled_without_tk_root_no_dialog(self):
        """Настройка выключена и нет tk_root — диалог не показывается."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
            close_browser_with_app_getter=lambda: False,
        )
        with (
            patch(
                'server.config.browser_process.is_browser_running_with_proxy',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
            ) as mock_kill,
            patch('server.ui.dialogs.show_info') as mock_dialog,
        ):
            _handle_browser_on_exit(callbacks, MagicMock())

        mock_kill.assert_not_called()
        mock_dialog.assert_not_called()


class TestBuildMenuItemsBrowserClose(unittest.TestCase):
    """Тесты пунктов меню «Автозакрытие браузера» и «Закрыть браузер»."""

    def _callbacks(self, browser_path='', proxy_port=None):
        """Минимальный набор колбэков для тестов меню."""
        return {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'browser_path_getter': lambda: browser_path,
            'proxy_port': proxy_port,
        }

    def test_close_browser_checkbox_present(self):
        """Чекбокс «Автозакрытие браузера» присутствует."""
        items = build_menu_items(
            self._callbacks(), MagicMock(),
        )
        texts = [item.get('text') for item in items]
        self.assertIn('Автозакрытие браузера', texts)

    def test_close_browser_checkbox_checked(self):
        """Чекбокс отмечен, когда close_browser_with_app_getter возвращает True."""
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'close_browser_with_app_getter': lambda: True,
        }
        items = build_menu_items(callbacks, MagicMock())
        check = next(
            item for item in items
            if item.get('text') == 'Автозакрытие браузера'
        )
        self.assertTrue(check['checked'])

    def test_close_browser_checkbox_toggles_setter(self):
        """Переключение чекбокса вызывает close_browser_with_app_setter."""
        setter = MagicMock()
        callbacks = {
            'stop': MagicMock(),
            'autostart_getter': lambda: False,
            'close_browser_with_app_getter': lambda: False,
            'close_browser_with_app_setter': setter,
        }
        items = build_menu_items(callbacks, MagicMock())
        check = next(
            item for item in items
            if item.get('text') == 'Автозакрытие браузера'
        )
        check['command']()
        setter.assert_called_once_with(True)

    @patch(
        'server.config.browser_process.is_browser_running_with_proxy',
        return_value=True,
    )
    def test_close_browser_item_present_when_running(self, _mock_running):
        """Пункт «Закрыть браузер» появляется, если браузер запущен с прокси."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
        )
        items = build_menu_items(callbacks, MagicMock())
        texts = [item.get('text') for item in items]
        self.assertIn('Закрыть браузер', texts)

    @patch(
        'server.config.browser_process.is_browser_running_with_proxy',
        return_value=False,
    )
    def test_close_browser_item_absent_when_not_running(self, _mock_running):
        """Пункт «Закрыть браузер» отсутствует, если браузер не запущен с прокси."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
        )
        items = build_menu_items(callbacks, MagicMock())
        texts = [item.get('text') for item in items]
        self.assertNotIn('Закрыть браузер', texts)

    @patch(
        'server.config.browser_process.is_browser_running_with_proxy',
        return_value=True,
    )
    def test_close_browser_item_position_before_exit(self, _mock_running):
        """Пункт «Закрыть браузер» стоит перед разделителем и «Выход»."""
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
        )
        items = build_menu_items(callbacks, MagicMock())
        self.assertEqual(items[-1]['text'], 'Выход')
        self.assertEqual(items[-2]['type'], 'separator')
        self.assertEqual(items[-3]['text'], 'Закрыть браузер')

    @patch(
        'server.config.browser_process.is_browser_running_with_proxy',
        return_value=True,
    )
    def test_close_browser_item_calls_closer(self, _mock_running):
        """Клик по «Закрыть браузер» вызывает browser_closer."""
        closer = MagicMock(return_value=True)
        callbacks = self._callbacks(
            browser_path='/usr/bin/google-chrome', proxy_port=8080,
        )
        callbacks['browser_closer'] = closer
        items = build_menu_items(callbacks, MagicMock())
        item = next(
            i for i in items if i.get('text') == 'Закрыть браузер'
        )
        item['command']()
        closer.assert_called_once()


if __name__ == '__main__':
    unittest.main()
