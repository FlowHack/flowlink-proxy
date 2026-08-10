"""
Тесты запуска браузера из __main__.py.

Проверяет:
- уведомление о невыбранном браузере при нажатии «Запустить браузер»
  (пустой/невалидный путь → диалог и возврат False);
- поведение _show_browser_not_selected_dialog при наличии tk_root и без него;
- _show_browser_already_running_dialog возвращает только выбор пользователя
  (True/False) и не выполняет kill/launch внутри себя;
- _show_browser_already_running_with_proxy_dialog — диалог о браузере, уже
  запущенном через FlowLink Proxy: возвращает только выбор пользователя
  и не выполняет kill/launch внутри себя;
- _launch_browser_sync при 'already_running' возвращает выбор диалога;
- _launch_browser_sync при 'already_running_with_proxy': выбор перезапуска
  делегируется _restart_browser_sync, отмена → True без перезапуска;
- _restart_browser_sync: успешный перезапуск → True, неудача kill или
  «всё ещё запущен после kill» → False;
- _launch_browser_callback: при выборе перезапуска kill + launch выполняются
  в фоновом потоке _restart_worker, а результат возвращается только после
  его завершения.
"""

import threading
import unittest
from unittest.mock import MagicMock, patch

from server.__main__ import (_launch_browser_callback, _launch_browser_sync,
                             _restart_browser_sync,
                             _show_browser_already_running_dialog,
                             _show_browser_already_running_with_proxy_dialog,
                             _show_browser_not_selected_dialog)


class _FakeVar:
    """Аналог tk.BooleanVar: set выставляет threading.Event для wait_variable."""

    def __init__(self):
        self._event = threading.Event()
        self._value = None

    def set(self, value):
        """Выставляет значение и сигнализирует ожидающему wait_variable."""
        self._value = value
        self._event.set()

    def get(self):
        """Возвращает текущее значение переменной."""
        return self._value

    def wait(self, timeout=None):
        """Блокирует вызывающий поток до вызова set (аналог wait_variable)."""
        return self._event.wait(timeout=timeout)


class _FakeTkRoot:
    """Фейковый tk_root для _launch_browser_callback.

    after(0, func) выполняет func синхронно (в тесте потоки не блокируются),
    wait_variable блокируется до выставления done_var — как реальный tkinter.
    """

    def __init__(self):
        self.after_calls = []

    def after(self, delay, func, *args):
        """Регистрирует и синхронно выполняет отложенный коллбэк."""
        self.after_calls.append((delay, func, args))
        func(*args)

    def wait_variable(self, var):
        """Блокируется до тех пор, пока фоновый поток не выставит done_var."""
        if not var.wait(timeout=10):
            raise AssertionError(
                'wait_variable: таймаут ожидания фонового запуска браузера',
            )


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


class TestBrowserAlreadyRunningDialog(unittest.TestCase):
    """_show_browser_already_running_dialog возвращает выбор пользователя."""

    def _click_primary(self, mock_show_info):
        """Делает show_info «блокирующим»: перед возвратом нажимает главную кнопку.

        В реальности show_info использует wait_window и не возвращается,
        пока пользователь не выберет действие. В тесте имитируем клик через
        side_effect — иначе функция вернёт choice до нажатия кнопки.
        """

        def _side_effect(**kwargs):
            buttons = kwargs.get('buttons', [])
            primary = next((b for b in buttons if b['primary']), None)
            if primary and primary.get('action'):
                primary['action']()

        mock_show_info.side_effect = _side_effect

    def _show_dialog(self, click_primary=False):
        """Вызывает диалог с мокнутым show_info и возвращает его результат."""
        tk_root = MagicMock()
        with (
            patch('server.ui.dialogs.show_info') as mock_show_info,
            patch(
                'server.config.browser_process.get_manual_kill_instructions',
                return_value='инструкция по завершению',
            ),
        ):
            if click_primary:
                self._click_primary(mock_show_info)
            result = _show_browser_already_running_dialog(
                {'tk_root': tk_root}, '/usr/bin/chrome', 8080,
            )
        return result, mock_show_info

    def test_returns_true_when_user_chooses_restart(self):
        """Выбор «Закрыть и запустить через FlowLink Proxy» → True."""
        result, _ = self._show_dialog(click_primary=True)
        self.assertTrue(result)

    def test_returns_false_when_cancelled(self):
        """Отмена (или закрытие диалога) → False."""
        result, mock_show_info = self._show_dialog(click_primary=False)
        self.assertFalse(result)
        # Ни одна кнопка не нажималась — результат остался False
        buttons = mock_show_info.call_args.kwargs['buttons']
        cancel_btn = next(b for b in buttons if not b['primary'])
        self.assertFalse(cancel_btn['primary'])

    def test_returns_false_without_tk_root(self):
        """Без tk_root — предупреждение и False, диалог не показывается."""
        with patch('server.ui.dialogs.show_info') as mock_show_info:
            result = _show_browser_already_running_dialog(
                {}, '/usr/bin/chrome', 8080,
            )
        self.assertFalse(result)
        mock_show_info.assert_not_called()

    def test_dialog_does_not_kill_or_launch_browser(self):
        """Внутри диалога kill/launch не вызываются (это делает _restart_worker)."""
        tk_root = MagicMock()
        with (
            patch('server.ui.dialogs.show_info') as mock_show_info,
            patch(
                'server.config.browser_process.get_manual_kill_instructions',
                return_value='инструкция по завершению',
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=True,
            ) as mock_kill,
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value=True,
            ) as mock_launch,
        ):
            self._click_primary(mock_show_info)
            result = _show_browser_already_running_dialog(
                {'tk_root': tk_root}, '/usr/bin/chrome', 8080,
            )

        self.assertTrue(result)
        mock_kill.assert_not_called()
        mock_launch.assert_not_called()


class TestBrowserAlreadyRunningWithProxyDialog(unittest.TestCase):
    """_show_browser_already_running_with_proxy_dialog возвращает выбор пользователя."""

    def _click_primary(self, mock_show_info):
        """Делает show_info «блокирующим»: перед возвратом нажимает главную кнопку."""

        def _side_effect(**kwargs):
            buttons = kwargs.get('buttons', [])
            primary = next((b for b in buttons if b['primary']), None)
            if primary and primary.get('action'):
                primary['action']()

        mock_show_info.side_effect = _side_effect

    def _show_dialog(self, click_primary=False):
        """Вызывает диалог с мокнутым show_info и возвращает его результат."""
        tk_root = MagicMock()
        with patch('server.ui.dialogs.show_info') as mock_show_info:
            if click_primary:
                self._click_primary(mock_show_info)
            result = _show_browser_already_running_with_proxy_dialog(
                {'tk_root': tk_root}, '/usr/bin/chrome',
            )
        return result, mock_show_info

    def test_returns_true_when_user_chooses_restart(self):
        """Выбор «Перезапустить браузер» → True."""
        result, mock_show_info = self._show_dialog(click_primary=True)
        self.assertTrue(result)
        kwargs = mock_show_info.call_args.kwargs
        self.assertEqual(kwargs['title'], 'Браузер уже запущен')
        self.assertIn('уже запущен через FlowLink Proxy', kwargs['message'])

    def test_returns_false_when_cancelled(self):
        """Отмена (или закрытие диалога) → False."""
        result, mock_show_info = self._show_dialog(click_primary=False)
        self.assertFalse(result)
        buttons = mock_show_info.call_args.kwargs['buttons']
        restart_btn = next(b for b in buttons if b['primary'])
        self.assertEqual(restart_btn['text'], 'Перезапустить браузер')
        cancel_btn = next(b for b in buttons if not b['primary'])
        self.assertEqual(cancel_btn['text'], 'Не перезапускать')

    def test_returns_false_without_tk_root(self):
        """Без tk_root — предупреждение и False, диалог не показывается."""
        with patch('server.ui.dialogs.show_info') as mock_show_info:
            result = _show_browser_already_running_with_proxy_dialog(
                {}, '/usr/bin/chrome',
            )
        self.assertFalse(result)
        mock_show_info.assert_not_called()



class TestLaunchBrowserSyncAlreadyRunningWithProxy(unittest.TestCase):
    """_launch_browser_sync при браузере, уже запущенном через FlowLink Proxy."""

    def test_restart_choice_calls_restart_browser_sync(self):
        """Выбор перезапуска → делегируется _restart_browser_sync, результат возвращается."""
        with (
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value='already_running_with_proxy',
            ),
            patch(
                'server.__main__._show_browser_already_running_with_proxy_dialog',
                return_value=True,
            ) as mock_dialog,
            patch(
                'server.__main__._restart_browser_sync',
                return_value=True,
            ) as mock_restart,
        ):
            result = _launch_browser_sync(
                callbacks={}, browser_path='/usr/bin/chrome', proxy_port=8080,
            )

        self.assertTrue(result)
        mock_dialog.assert_called_once()
        mock_restart.assert_called_once_with('/usr/bin/chrome', 8080)

    def test_cancel_returns_true_without_restart(self):
        """Отмена диалога → True (браузер уже работает через прокси), без перезапуска."""
        with (
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value='already_running_with_proxy',
            ),
            patch(
                'server.__main__._show_browser_already_running_with_proxy_dialog',
                return_value=False,
            ) as mock_dialog,
            patch(
                'server.__main__._restart_browser_sync',
                return_value=True,
            ) as mock_restart,
        ):
            result = _launch_browser_sync(
                callbacks={}, browser_path='/usr/bin/chrome', proxy_port=8080,
            )

        self.assertTrue(result)
        mock_dialog.assert_called_once()
        mock_restart.assert_not_called()


class TestRestartBrowserSync(unittest.TestCase):
    """_restart_browser_sync — синхронный перезапуск браузера через прокси."""

    def test_successful_restart_returns_true(self):
        """Kill успешен и повторный запуск успешен → True."""
        with (
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=True,
            ) as mock_kill,
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value=True,
            ) as mock_launch,
            patch('server.__main__.time.sleep') as mock_sleep,
        ):
            result = _restart_browser_sync('/usr/bin/chrome', 8080)

        self.assertTrue(result)
        mock_kill.assert_called_once_with('/usr/bin/chrome')
        mock_launch.assert_called_once_with(
            '/usr/bin/chrome', proxy_port=8080,
        )
        mock_sleep.assert_called_once_with(0.5)

    def test_second_launch_failure_returns_false(self):
        """Kill успешен, но повторный запуск вернул False → False."""
        with (
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value=False,
            ) as mock_launch,
            patch('server.__main__.time.sleep'),
        ):
            result = _restart_browser_sync('/usr/bin/chrome', 8080)

        self.assertFalse(result)
        mock_launch.assert_called_once_with(
            '/usr/bin/chrome', proxy_port=8080,
        )

    def test_kill_failure_returns_false(self):
        """Не удалось завершить процессы → False, повторный запуск не выполняется."""
        with (
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=False,
            ) as mock_kill,
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value=True,
            ) as mock_launch,
            patch('server.__main__.time.sleep') as mock_sleep,
        ):
            result = _restart_browser_sync('/usr/bin/chrome', 8080)

        self.assertFalse(result)
        mock_kill.assert_called_once_with('/usr/bin/chrome')
        mock_launch.assert_not_called()
        mock_sleep.assert_not_called()

    def test_still_running_after_kill_returns_false(self):
        """После kill браузер всё ещё запущен ('already_running') → False."""
        with (
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value='already_running',
            ) as mock_launch,
            patch('server.__main__.time.sleep'),
        ):
            result = _restart_browser_sync('/usr/bin/chrome', 8080)

        self.assertFalse(result)
        mock_launch.assert_called_once_with(
            '/usr/bin/chrome', proxy_port=8080,
        )


class TestLaunchBrowserSyncAlreadyRunning(unittest.TestCase):
    """_launch_browser_sync при уже запущенном без прокси браузере."""

    def test_already_running_dialog_true_returns_true(self):
        """Пользователь выбрал перезапуск → True."""
        with (
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value='already_running',
            ),
            patch(
                'server.__main__._show_browser_already_running_dialog',
                return_value=True,
            ) as mock_dialog,
        ):
            result = _launch_browser_sync(
                callbacks={}, browser_path='/usr/bin/chrome', proxy_port=8080,
            )

        self.assertTrue(result)
        mock_dialog.assert_called_once()

    def test_already_running_dialog_false_returns_false(self):
        """Отмена диалога → False."""
        with (
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value='already_running',
            ),
            patch(
                'server.__main__._show_browser_already_running_dialog',
                return_value=False,
            ),
        ):
            result = _launch_browser_sync(
                callbacks={}, browser_path='/usr/bin/chrome', proxy_port=8080,
            )

        self.assertFalse(result)


class TestLaunchBrowserCallbackRestart(unittest.TestCase):
    """Полный поток _launch_browser_callback с фоновым перезапуском.

    Использует _FakeTkRoot: after выполняет коллбэки синхронно, а
    wait_variable блокируется до завершения фонового _restart_worker —
    так проверяется, что результат возвращается ПОСЛЕ перезапуска.
    """

    def _make_callbacks(self):
        """Создаёт callbacks с фейковым tk_root и мокнутым popup."""
        tk_root = _FakeTkRoot()
        popup = MagicMock()
        return {'tk_root': tk_root, 'popup': popup}, tk_root, popup

    def _run_callback(self, callbacks, launch_side_effect, dialog_value):
        """Запускает _launch_browser_callback с заданными моками."""
        with (
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value='/usr/bin/chrome',
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                side_effect=launch_side_effect,
            ) as mock_launch,
            patch(
                'server.__main__._show_browser_already_running_dialog',
                return_value=dialog_value,
            ) as mock_dialog,
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=True,
            ) as mock_kill,
            patch('server.__main__.time.sleep'),
            patch(
                'tkinter.BooleanVar',
                side_effect=lambda root: _FakeVar(),
            ),
        ):
            result = _launch_browser_callback(callbacks, proxy_port=8080)
        return result, mock_launch, mock_dialog, mock_kill

    def test_restart_choice_runs_background_worker_and_returns_true(self):
        """Выбор перезапуска: kill+launch в фоне, возврат True после завершения."""
        callbacks, _tk_root, popup = self._make_callbacks()
        result, mock_launch, mock_dialog, mock_kill = self._run_callback(
            callbacks,
            launch_side_effect=['already_running', True],
            dialog_value=True,
        )

        self.assertTrue(result)
        # Диалог показан один раз, kill и повторный launch выполнялись
        mock_dialog.assert_called_once()
        mock_kill.assert_called_once_with('/usr/bin/chrome')
        self.assertEqual(mock_launch.call_count, 2)
        # Статусбар перезапуска показывался и затем был скрыт
        popup.show_loading.assert_any_call('Перезапуск браузера...')
        popup.hide_loading.assert_called()

    def test_cancel_restart_returns_false_and_no_worker(self):
        """Отмена диалога: возврат False, kill/повторный launch не вызываются."""
        callbacks, _tk_root, popup = self._make_callbacks()
        result, mock_launch, mock_dialog, mock_kill = self._run_callback(
            callbacks,
            launch_side_effect=['already_running'],
            dialog_value=False,
        )

        self.assertFalse(result)
        mock_dialog.assert_called_once()
        mock_kill.assert_not_called()
        self.assertEqual(mock_launch.call_count, 1)
        # Статусбар перезапуска не показывался (только «Запуск браузера...»)
        restart_msgs = [
            c.args[0] for c in popup.show_loading.call_args_list
            if c.args and c.args[0] == 'Перезапуск браузера...'
        ]
        self.assertEqual(restart_msgs, [])

    def test_restart_kill_failure_returns_false(self):
        """Не удалось завершить процессы — возврат False."""
        callbacks, _tk_root, popup = self._make_callbacks()
        with (
            patch(
                'server.__main__._browser_config.get_browser_path',
                return_value='/usr/bin/chrome',
            ),
            patch(
                'server.__main__._browser_config.validate_browser_path',
                return_value=True,
            ),
            patch(
                'server.__main__._browser_config.launch_browser',
                return_value='already_running',
            ) as mock_launch,
            patch(
                'server.__main__._show_browser_already_running_dialog',
                return_value=True,
            ),
            patch(
                'server.config.browser_process.kill_browser_processes',
                return_value=False,
            ) as mock_kill,
            patch('server.__main__.time.sleep'),
            patch(
                'tkinter.BooleanVar',
                side_effect=lambda root: _FakeVar(),
            ),
        ):
            result = _launch_browser_callback(callbacks, proxy_port=8080)

        self.assertFalse(result)
        mock_kill.assert_called_once_with('/usr/bin/chrome')
        # Повторный запуск после неудачного kill не выполняется
        self.assertEqual(mock_launch.call_count, 1)
        popup.hide_loading.assert_called()
