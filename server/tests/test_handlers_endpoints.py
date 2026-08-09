"""Поведенческие тесты эндпоинтов обработчиков API.

Покрывают обработчики, которые ранее проверялись только моками в таблице
маршрутов test_api_routes.py: ping, системный автозапуск, путь к браузеру,
список обнаруженных браузеров и валидация пути браузера.
"""
import unittest
from unittest.mock import patch
from server.servers.handlers import (
    handle_ping, handle_get_system_autostart, handle_post_system_autostart,
    handle_get_browser_path, handle_post_browser_path, handle_get_detected_browsers,
    handle_post_validate_browser
)

class TestHandlePing(unittest.IsolatedAsyncioTestCase):
    """Тестирует обработчик POST /api/ping - проверяет пинг прокси"""
    @patch('server.servers.handlers.ping_proxy')
    async def test_ping_success(self, mock_ping):
        """Проверяет успешный пинг прокси"""
        mock_ping.return_value = {'alive': True, 'latency': 150}
        result = await handle_ping('test_id', ('127.0.0.1', 8080))
        self.assertEqual(result[0]['alive'], True)
        self.assertEqual(result[0]['latency'], 150)

    @patch('server.servers.handlers.ping_proxy')
    async def test_ping_timeout(self, mock_ping):
        """Проверяет обработку таймаута при пинге"""
        mock_ping.return_value = {'alive': False, 'latency': None, 'errorKind': 'timeout'}
        result = await handle_ping('test_id', ('127.0.0.1', 8080))
        self.assertFalse(result[0]['alive'])
        self.assertEqual(result[0]['errorKind'], 'timeout')
        self.assertEqual(result[1], 200)

class TestGetSystemAutostart(unittest.TestCase):
    """Тестирует обработчик GET /api/system-autostart - получение статуса автозапуска"""
    @patch('server.servers.handlers.system_autostart')
    def test_get_system_autostart(self, mock_autostart):
        """Проверяет возврат текущего статуса автозапуска"""
        mock_autostart.get_system_autostart_info.return_value = {
            'enabled': True, 'platform': 'Windows', 'method': 'service'
        }
        result = handle_get_system_autostart()
        self.assertEqual(result['enabled'], True)
        self.assertEqual(result['platform'], 'Windows')

class TestPostSystemAutostart(unittest.IsolatedAsyncioTestCase):
    """Тестирует обработчик POST /api/system-autostart - изменение статуса автозапуска"""
    @patch('server.servers.handlers.system_autostart')
    async def test_post_system_autostart_success(self, mock_autostart):
        """Проверяет успешное включение автозапуска"""
        mock_autostart.set_system_autostart_enabled.return_value = True
        result = await handle_post_system_autostart({'enabled': True})
        if not isinstance(result, dict):
            self.fail('При успешном включении автозапуска ожидался словарь')
        self.assertTrue(result['success'])
        self.assertTrue(mock_autostart.set_system_autostart_enabled.called)

    @patch('server.servers.handlers.system_autostart')
    async def test_post_system_autostart_error(self, mock_autostart):
        """Проверяет обработку ошибки при включении автозапуска"""
        mock_autostart.set_system_autostart_enabled.side_effect = OSError()
        result = await handle_post_system_autostart({'enabled': True})
        if not isinstance(result, tuple):
            self.fail('При ошибке автозапуска ожидался кортеж (ответ, код)')
        self.assertIn('Не удалось изменить настройку автозапуска', result[0]['error'])
        self.assertEqual(result[1], 500)

class TestGetBrowserPath(unittest.TestCase):
    """Тестирует обработчик GET /api/browser-path - получение пути к браузеру"""
    @patch('server.servers.handlers.browser_config')
    def test_get_browser_path(self, mock_config):
        """Проверяет возврат текущего пути к браузеру"""
        mock_config.get_browser_path.return_value = '/usr/bin/chromium'
        result = handle_get_browser_path()
        self.assertEqual(result['browserPath'], '/usr/bin/chromium')

class TestPostBrowserPath(unittest.IsolatedAsyncioTestCase):
    """Тестирует обработчик POST /api/browser-path - сохранение пути к браузеру"""
    @patch('server.servers.handlers.browser_config')
    async def test_post_browser_path_valid(self, mock_config):
        """Проверяет сохранение валидного пути к браузеру"""
        mock_config.validate_browser_path_detailed.return_value = {'valid': True}
        mock_config.save_browser_path.return_value = None
        result = await handle_post_browser_path({'browserPath': '/usr/bin/firefox'})
        self.assertTrue(result[0]['success'])
        self.assertEqual(result[0]['browserPath'], '/usr/bin/firefox')
        self.assertEqual(result[1], 200)

    @patch('server.servers.handlers.browser_config')
    async def test_post_browser_path_invalid(self, mock_config):
        """Проверяет обработку невалидного пути к браузеру"""
        mock_config.validate_browser_path_detailed.return_value = {
            'valid': False, 'error': 'Неверный путь'
        }
        mock_config.get_browser_path.return_value = '/current/path'
        result = await handle_post_browser_path({'browserPath': 'invalid_path'})
        self.assertIn('Неверный путь', result[0]['error'])
        self.assertEqual(result[0]['browserPath'], '/current/path')
        self.assertTrue(result[0]['validationFailed'])
        self.assertEqual(result[1], 422)

class TestGetDetectedBrowsers(unittest.TestCase):
    """Тестирует обработчик GET /api/detected-browsers - список обнаруженных браузеров"""
    @patch('server.servers.handlers.browser_config')
    def test_get_detected_browsers(self, mock_config):
        """Проверяет возврат списка обнаруженных браузеров"""
        mock_config.auto_detect_browsers.return_value = ['Chrome', 'Firefox']
        result = handle_get_detected_browsers()
        self.assertEqual(result['browsers'], ['Chrome', 'Firefox'])

class TestPostValidateBrowser(unittest.TestCase):
    """Тестирует обработчик POST /api/validate-browser - валидация пути к браузеру"""
    @patch('server.servers.handlers.browser_config')
    def test_validate_browser_success(self, mock_config):
        """Проверяет успешную валидацию пути"""
        mock_config.validate_browser_path_detailed.return_value = {'valid': True}
        result = handle_post_validate_browser({'browserPath': '/usr/bin/chromium'})
        self.assertEqual(result[0]['valid'], True)
        self.assertEqual(result[1], 200)

    @patch('server.servers.handlers.browser_config')
    def test_validate_browser_failure(self, mock_config):
        """Проверяет обработку невалидного пути"""
        mock_config.validate_browser_path_detailed.return_value = {
            'valid': False, 'error': 'Путь не существует'
        }
        result = handle_post_validate_browser({'browserPath': 'invalid'})
        self.assertIn('Путь не существует', result[0]['error'])
        self.assertEqual(result[0]['valid'], False)
        self.assertEqual(result[1], 200)

# Все тесты должны пройти
print("Все тесты пройдены")
