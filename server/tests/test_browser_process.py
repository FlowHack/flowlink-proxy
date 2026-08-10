"""
Тесты модуля browser_process.py — работа с процессами браузера.

Проверяются: поиск PID (Windows wmic/PowerShell, POSIX pgrep),
проверка запущенности, завершение процессов (taskkill / SIGTERM+SIGKILL),
инструкции по ручному завершению.
"""

import signal
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from server.config.browser_process import (find_browser_pids,
                                           find_browser_pids_with_proxy,
                                           get_browser_process_name,
                                           get_manual_kill_instructions,
                                           is_browser_running,
                                           is_browser_running_with_proxy,
                                           kill_browser_processes,
                                           _parse_pids, _proxy_arg_pattern)

# Путь к браузеру, используемый в большинстве тестов
_BROWSER = '/usr/bin/google-chrome'


class TestGetBrowserProcessName(unittest.TestCase):
    """Тесты извлечения имени исполняемого файла из пути."""

    def test_windows_path(self):
        """Путь Windows: возвращается browser.exe."""
        path = r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
        self.assertEqual(get_browser_process_name(path), 'browser.exe')

    def test_posix_path(self):
        """Путь POSIX: возвращается имя файла."""
        self.assertEqual(get_browser_process_name(_BROWSER), 'google-chrome')

    def test_empty_path(self):
        """Пустой путь возвращает пустую строку."""
        self.assertEqual(get_browser_process_name(''), '')


class TestFindBrowserPids(unittest.TestCase):
    """Тесты поиска PID процессов браузера."""

    def test_empty_path(self):
        """Пустой путь — пустой список, subprocess не вызывается."""
        with patch('server.config.browser_process.subprocess.run') as mock_run:
            result = find_browser_pids('')
        self.assertEqual(result, [])
        mock_run.assert_not_called()

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run')
    def test_posix_returns_pids(self, mock_run):
        """pgrep -f возвращает список целых PID."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='123\n456\n', stderr='',
        )
        result = find_browser_pids(_BROWSER)
        self.assertEqual(result, [123, 456])
        args = mock_run.call_args.args[0]
        self.assertEqual(args, ['pgrep', '-f', _BROWSER])

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run')
    def test_posix_skips_non_numeric_lines(self, mock_run):
        """Нечисловые строки вывода пропускаются."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='PID\n123\n\nabc\n456\n', stderr='',
        )
        result = find_browser_pids(_BROWSER)
        self.assertEqual(result, [123, 456])

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run')
    def test_posix_no_processes(self, _mock_run):
        """pgrep с кодом 1 (нет процессов) — пустой список."""
        _mock_run.return_value = SimpleNamespace(
            returncode=1, stdout='', stderr='',
        )
        self.assertEqual(find_browser_pids(_BROWSER), [])

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run',
           side_effect=OSError('pgrep отсутствует'))
    def test_posix_error_returns_empty(self, _mock_run):
        """Ошибка pgrep — пустой список (без падения)."""
        self.assertEqual(find_browser_pids(_BROWSER), [])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_wmic(self, mock_run):
        """wmic возвращает список целых PID."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='ProcessId\n101\n102\n', stderr='',
        )
        path = r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
        result = find_browser_pids(path)
        self.assertEqual(result, [101, 102])
        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], 'wmic')
        # Точное сопоставление по ExecutablePath (аргумент 3 — where-условие)
        self.assertIn("ExecutablePath='", args[3])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_wmic_escapes_quotes(self, mock_run):
        """Одинарные кавычки в пути экранируются для wmic."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='ProcessId\n5\n', stderr='',
        )
        path = r"C:\My'Browser\browser.exe"
        result = find_browser_pids(path)
        self.assertEqual(result, [5])
        where_clause = mock_run.call_args.args[0][3]
        self.assertIn("ExecutablePath='C:\\My''Browser\\browser.exe'",
                      where_clause)

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_powershell_fallback(self, mock_run):
        """При сбое wmic используется PowerShell Get-CimInstance."""
        mock_run.side_effect = [
            SimpleNamespace(returncode=1, stdout='', stderr='wmic устарел'),
            SimpleNamespace(returncode=0, stdout='ProcessId\n777\n', stderr=''),
        ]
        result = find_browser_pids(r'C:\browser.exe')
        self.assertEqual(result, [777])
        self.assertEqual(mock_run.call_count, 2)
        second_args = mock_run.call_args_list[1].args[0]
        self.assertEqual(second_args[0], 'powershell')
        # PowerShell-команда передаётся четвёртым аргументом (после -Command)
        self.assertIn('Get-CimInstance', second_args[3])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_wmic_missing_uses_powershell(self, mock_run):
        """Отсутствие wmic (OSError) — переход на PowerShell."""
        mock_run.side_effect = [
            OSError('wmic не найден'),
            SimpleNamespace(returncode=0, stdout='ProcessId\n42\n', stderr=''),
        ]
        result = find_browser_pids(r'C:\browser.exe')
        self.assertEqual(result, [42])
        self.assertEqual(mock_run.call_count, 2)

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_wmic_timeout_uses_powershell(self, mock_run):
        """Таймаут wmic (TimeoutExpired) — fallback на PowerShell."""
        mock_run.side_effect = [
            subprocess.TimeoutExpired('wmic', 10),
            SimpleNamespace(returncode=0, stdout='ProcessId\n999\n', stderr=''),
        ]
        result = find_browser_pids(r'C:\browser.exe')
        self.assertEqual(result, [999])
        self.assertEqual(mock_run.call_count, 2)
        second_args = mock_run.call_args_list[1].args[0]
        self.assertEqual(second_args[0], 'powershell')

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run',
           side_effect=subprocess.TimeoutExpired('pgrep', 10))
    def test_posix_timeout_returns_empty(self, _mock_run):
        """Таймаут pgrep (TimeoutExpired) — пустой список (без падения)."""
        self.assertEqual(find_browser_pids(_BROWSER), [])


class TestParsePids(unittest.TestCase):
    """Прямые тесты _parse_pids — разбор вывода wmic/PowerShell/pgrep."""

    def test_parses_numeric_lines(self):
        """Числовые строки разбираются в список целых PID."""
        self.assertEqual(
            _parse_pids('ProcessId\n123\n456\n'), [123, 456],
        )

    def test_skips_garbage_and_empty_lines(self):
        """Заголовки, пустые и нечисловые строки пропускаются."""
        self.assertEqual(
            _parse_pids('PID\n123\n\nabc\n456\n'), [123, 456],
        )

    def test_empty_output(self):
        """Пустой вывод — пустой список."""
        self.assertEqual(_parse_pids(''), [])

    def test_case_insensitive_header(self):
        """Заголовок 'processid' (нижний регистр) пропускается."""
        self.assertEqual(_parse_pids('processid\n7\n'), [7])


class TestIsBrowserRunning(unittest.TestCase):
    """Тесты проверки запущенности браузера."""

    @patch('server.config.browser_process.find_browser_pids', return_value=[123])
    def test_running_true(self, _mock_find):
        """Найденные PID — браузер запущен."""
        self.assertTrue(is_browser_running(_BROWSER))

    @patch('server.config.browser_process.find_browser_pids', return_value=[])
    def test_running_false(self, _mock_find):
        """PID не найдены — браузер не запущен."""
        self.assertFalse(is_browser_running(_BROWSER))


class TestProxyArgPattern(unittest.TestCase):
    """Тесты формирования паттерна --proxy-server."""

    def test_default_port(self):
        """Паттерн для порта 8080."""
        self.assertEqual(
            _proxy_arg_pattern(8080),
            '--proxy-server=127.0.0.1:8080',
        )

    def test_custom_port(self):
        """Паттерн для кастомного порта."""
        self.assertEqual(
            _proxy_arg_pattern(9090),
            '--proxy-server=127.0.0.1:9090',
        )


class TestFindBrowserPidsWithProxy(unittest.TestCase):
    """Тесты поиска PID браузера, запущенного с флагом --proxy-server."""

    def test_empty_path(self):
        """Пустой путь — пустой список, subprocess не вызывается."""
        with patch('server.config.browser_process.subprocess.run') as mock_run:
            result = find_browser_pids_with_proxy('', 8080)
        self.assertEqual(result, [])
        mock_run.assert_not_called()

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run')
    def test_posix_returns_pids(self, mock_run):
        """pgrep -f с объединённым паттерном возвращает список целых PID."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='111\n222\n', stderr='',
        )
        result = find_browser_pids_with_proxy(_BROWSER, 8080)
        self.assertEqual(result, [111, 222])
        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], 'pgrep')
        self.assertEqual(args[1], '-f')
        self.assertIn(_BROWSER, args[2])
        self.assertIn('--proxy-server=127.0.0.1:8080', args[2])

    @patch('server.config.browser_process.sys.platform', 'darwin')
    @patch('server.config.browser_process.subprocess.run')
    def test_posix_macos_uses_pgrep(self, mock_run):
        """macOS (не win32) использует ту же pgrep-ветку."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='333\n', stderr='',
        )
        result = find_browser_pids_with_proxy(_BROWSER, 9090)
        self.assertEqual(result, [333])
        args = mock_run.call_args.args[0]
        self.assertIn('--proxy-server=127.0.0.1:9090', args[2])

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run')
    def test_posix_no_processes(self, mock_run):
        """pgrep с кодом 1 (процессы не найдены) — пустой список."""
        mock_run.return_value = SimpleNamespace(
            returncode=1, stdout='', stderr='',
        )
        self.assertEqual(find_browser_pids_with_proxy(_BROWSER, 8080), [])

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.subprocess.run',
           side_effect=OSError('pgrep отсутствует'))
    def test_posix_error_returns_empty(self, _mock_run):
        """Ошибка pgrep — пустой список (без падения)."""
        self.assertEqual(find_browser_pids_with_proxy(_BROWSER, 8080), [])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_powershell_returns_pids(self, mock_run):
        """PowerShell Get-CimInstance возвращает список целых PID."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='ProcessId\n444\n555\n', stderr='',
        )
        path = r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
        result = find_browser_pids_with_proxy(path, 8080)
        self.assertEqual(result, [444, 555])
        args = mock_run.call_args.args[0]
        self.assertEqual(args[0], 'powershell')
        self.assertIn('Get-CimInstance', args[3])
        self.assertIn('--proxy-server=127.0.0.1:8080', args[3])
        # Точный путь экранирован и участвует в фильтре ExecutablePath
        self.assertIn("ExecutablePath -eq 'C:\\Program Files\\", args[3])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    def test_windows_no_processes(self, mock_run):
        """PowerShell с кодом 1 — пустой список."""
        mock_run.return_value = SimpleNamespace(
            returncode=1, stdout='', stderr='процессы не найдены',
        )
        self.assertEqual(find_browser_pids_with_proxy(r'C:\browser.exe', 8080), [])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run',
           side_effect=OSError('powershell отсутствует'))
    def test_windows_error_returns_empty(self, _mock_run):
        """Ошибка PowerShell — пустой список (без падения)."""
        self.assertEqual(find_browser_pids_with_proxy(r'C:\browser.exe', 8080), [])


class TestIsBrowserRunningWithProxy(unittest.TestCase):
    """Тесты проверки запущенности браузера с прокси."""

    @patch('server.config.browser_process.find_browser_pids_with_proxy',
           return_value=[123])
    def test_running_true(self, _mock_find):
        """Найденные PID — браузер запущен через прокси."""
        self.assertTrue(is_browser_running_with_proxy(_BROWSER, 8080))

    @patch('server.config.browser_process.find_browser_pids_with_proxy',
           return_value=[])
    def test_running_false(self, _mock_find):
        """PID не найдены — браузер не запущен через прокси."""
        self.assertFalse(is_browser_running_with_proxy(_BROWSER, 8080))


class TestKillBrowserProcesses(unittest.TestCase):
    """Тесты завершения процессов браузера."""

    @patch('server.config.browser_process.find_browser_pids', return_value=[])
    def test_no_processes_returns_true(self, _mock_find):
        """Нет процессов — завершать нечего, возврат True."""
        with patch('server.config.browser_process.subprocess.run') as mock_run:
            self.assertTrue(kill_browser_processes(_BROWSER))
        mock_run.assert_not_called()

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    @patch('server.config.browser_process.find_browser_pids', return_value=[101])
    def test_windows_taskkill(self, _mock_find, mock_run):
        """Windows: taskkill /F /PID <pid> /T для каждого PID."""
        mock_run.return_value = SimpleNamespace(
            returncode=0, stdout='', stderr='',
        )
        result = kill_browser_processes(r'C:\browser.exe')
        self.assertTrue(result)
        args = mock_run.call_args.args[0]
        self.assertEqual(args, ['taskkill', '/F', '/PID', '101', '/T'])

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    @patch('server.config.browser_process._process_alive', return_value=True)
    @patch('server.config.browser_process.find_browser_pids', return_value=[101])
    def test_windows_taskkill_failure(self, _mock_find, _mock_alive, mock_run):
        """Ошибка taskkill и процесс жив — возврат False.

        Например, 'Отказано в доступе': taskkill не смог завершить
        процесс, и он по-прежнему существует — это настоящая ошибка.
        """
        mock_run.return_value = SimpleNamespace(
            returncode=1, stdout='', stderr='Отказано в доступе',
        )
        self.assertFalse(kill_browser_processes(r'C:\browser.exe'))

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.subprocess.run')
    @patch('server.config.browser_process._process_alive', return_value=False)
    @patch('server.config.browser_process.find_browser_pids', return_value=[101])
    def test_windows_taskkill_error_process_dead_is_success(
            self, _mock_find, _mock_alive, mock_run):
        """taskkill вернул ошибку, но процесс не жив — успех.

        taskkill /T убивает всё дерево процессов: последующие PID
        уже мертвы, команда возвращает ненулевой код, но фактически
        браузер закрыт. Такой случай не должен блокировать запуск.
        """
        mock_run.return_value = SimpleNamespace(
            returncode=1, stdout='', stderr='Не удается найти процесс',
        )
        self.assertTrue(kill_browser_processes(r'C:\browser.exe'))

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.time.sleep')
    @patch('server.config.browser_process.os.kill')
    @patch('server.config.browser_process._process_alive', return_value=False)
    @patch('server.config.browser_process.find_browser_pids',
           return_value=[101, 102])
    def test_posix_sigterm_only(self, _mock_find, _mock_alive,
                                mock_kill, _mock_sleep):
        """POSIX: процессы завершились после SIGTERM, SIGKILL не нужен."""
        result = kill_browser_processes(_BROWSER)
        self.assertTrue(result)
        signals = [call.args[1] for call in mock_kill.call_args_list]
        self.assertEqual(signals, [signal.SIGTERM, signal.SIGTERM])

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.time.sleep')
    @patch('server.config.browser_process.os.kill')
    @patch('server.config.browser_process._process_alive',
           side_effect=[True, True, False, False])
    @patch('server.config.browser_process.find_browser_pids',
           return_value=[101, 102])
    def test_posix_sigkill_fallback(self, _mock_find, _mock_alive,
                                    mock_kill, _mock_sleep):
        """POSIX: выжившие после SIGTERM добиваются SIGKILL."""
        result = kill_browser_processes(_BROWSER)
        self.assertTrue(result)
        signals = [call.args[1] for call in mock_kill.call_args_list]
        self.assertEqual(
            signals,
            [signal.SIGTERM, signal.SIGTERM,
             signal.SIGKILL, signal.SIGKILL],
        )

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.time.sleep')
    @patch('server.config.browser_process.os.kill')
    @patch('server.config.browser_process._process_alive', return_value=True)
    @patch('server.config.browser_process.find_browser_pids', return_value=[101])
    def test_posix_survivors_return_false(self, _mock_find, _mock_alive,
                                          mock_kill, _mock_sleep):
        """POSIX: выжившие процессы после SIGKILL — возврат False."""
        result = kill_browser_processes(_BROWSER)
        self.assertFalse(result)
        signals = [call.args[1] for call in mock_kill.call_args_list]
        self.assertEqual(signals, [signal.SIGTERM, signal.SIGKILL])


class TestGetManualKillInstructions(unittest.TestCase):
    """Тесты инструкций по ручному завершению браузера."""

    @patch('server.config.browser_process.sys.platform', 'linux')
    @patch('server.config.browser_process.find_browser_pids', return_value=[123])
    def test_linux_instructions(self, _mock_find):
        """Linux: pkill -f с путём, без перечисления PID."""
        text = get_manual_kill_instructions(_BROWSER)
        self.assertIn("pkill -f '/usr/bin/google-chrome'", text)
        # PID в тексте не перечисляются — сообщение остаётся компактным
        self.assertNotIn('123', text)

    @patch('server.config.browser_process.sys.platform', 'darwin')
    @patch('server.config.browser_process.find_browser_pids', return_value=[123])
    def test_macos_instructions(self, _mock_find):
        """macOS: та же команда pkill -f, что и на Linux."""
        text = get_manual_kill_instructions(_BROWSER)
        self.assertIn("pkill -f '/usr/bin/google-chrome'", text)
        self.assertNotIn('123', text)

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.find_browser_pids', return_value=[123])
    def test_windows_instructions(self, _mock_find):
        """Windows: Диспетчер задач, имя процесса, без PID."""
        path = r'C:\Program Files\Yandex\YandexBrowser\Application\browser.exe'
        text = get_manual_kill_instructions(path)
        self.assertIn('Диспетчер задач', text)
        self.assertIn('browser.exe', text)
        # PID не перечисляются — текст не шире экрана
        self.assertNotIn('123', text)

    @patch('server.config.browser_process.sys.platform', 'win32')
    @patch('server.config.browser_process.find_browser_pids', return_value=[])
    def test_no_processes_message(self, _mock_find):
        """Процессы не найдены — сообщение об этом."""
        text = get_manual_kill_instructions(r'C:\browser.exe')
        self.assertIn('не обнаружены', text)


if __name__ == '__main__':
    unittest.main()
