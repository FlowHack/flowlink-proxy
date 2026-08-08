"""
Тесты обработчиков API-эндпоинтов handlers.py.
"""

import asyncio
import logging
import logging.handlers
import unittest
from unittest.mock import patch

from server.config import config as cfg
from server.config import repo as config_repo
from server.servers.handlers import (_close_tunnels_on_config_change,
                                     _extract_masks_dict,
                                     _extract_proxies_dict,
                                     _log_config_changes, handle_get_browser_config,
                                     handle_get_config,
                                     handle_get_status, handle_get_version,
                                     handle_post_config, handle_post_enabled)
from server.services.router import MaskRouter
from server.tests.base import TempConfigEnabledMixin, TempConfigMixin


class TestExtractHelpers(unittest.TestCase):
    """Тесты вспомогательных функций извлечения данных."""

    def test_extract_proxies_dict_normal(self):
        """Извлечение словаря прокси из данных"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080},
                {'proxyId': 'p2', 'host': '2.2.2.2', 'port': 9090},
            ]
        }
        result = _extract_proxies_dict(data)
        self.assertEqual(len(result), 2)
        self.assertIn('p1', result)
        self.assertIn('p2', result)

    def test_extract_proxies_dict_skips_none_id(self):
        """Прокси без proxyId пропускаются"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080},
                {'host': 'no-id', 'port': 9090},
            ]
        }
        result = _extract_proxies_dict(data)
        self.assertEqual(len(result), 1)
        self.assertIn('p1', result)

    def test_extract_proxies_dict_empty(self):
        """Пустой список прокси"""
        data = {'proxies': []}
        result = _extract_proxies_dict(data)
        self.assertEqual(result, {})

    def test_extract_proxies_dict_no_key(self):
        """Нет ключа proxies в данных"""
        data = {}
        result = _extract_proxies_dict(data)
        self.assertEqual(result, {})

    def test_extract_masks_dict_normal(self):
        """Извлечение словаря масок из данных"""
        data = {
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'},
                {'maskId': 'm2', 'proxyId': 'p2', 'regexString': r'\.org'},
            ]
        }
        result = _extract_masks_dict(data)
        self.assertEqual(len(result), 2)
        self.assertIn('m1', result)
        self.assertIn('m2', result)

    def test_extract_masks_dict_skips_none_id(self):
        """Маски без maskId пропускаются"""
        data = {
            'masks': [
                {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'},
                {'proxyId': 'p1', 'regexString': r'\.org'},
            ]
        }
        result = _extract_masks_dict(data)
        self.assertEqual(len(result), 1)


class TestHandleGetConfig(TempConfigMixin, unittest.TestCase):
    """Тесты handle_get_config."""

    def setUp(self):
        super().setUp()
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                         'username': '', 'password': '', 'isEnabled': True}],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}],
        })

    def test_handle_get_config_returns_data(self):
        """GET /api/config возвращает данные с isEnabled"""
        result = handle_get_config()
        self.assertIn('proxies', result)
        self.assertIn('masks', result)
        self.assertIn('isEnabled', result)
        self.assertIsInstance(result['isEnabled'], bool)

    def test_handle_get_config_includes_is_enabled(self):
        """GET /api/config инжектит isEnabled из памяти"""
        cfg.set_enabled(False)
        result = handle_get_config()
        self.assertFalse(result['isEnabled'])


class TestHandleGetStatus(unittest.TestCase):
    """Тесты handle_get_status."""

    def test_handle_get_status_debug_and_need_update(self):
        """GET /api/status возвращает корректные флаги debug и needUpdate"""
        result = handle_get_status(debug=True, need_update=True)
        self.assertEqual(result['status'], 'running')
        self.assertTrue(result['debug'])
        self.assertTrue(result['needUpdate'])

    def test_handle_get_status_defaults(self):
        """GET /api/status по умолчанию — debug=False, needUpdate=False"""
        result = handle_get_status(debug=False)
        self.assertEqual(result['status'], 'running')
        self.assertFalse(result['debug'])
        self.assertFalse(result['needUpdate'])


class TestHandleGetVersion(unittest.TestCase):
    """Тесты handle_get_version."""

    def test_handle_get_version_returns_string(self):
        """GET /api/version возвращает строку версии"""
        result = handle_get_version()
        self.assertIn('version', result)
        self.assertIsInstance(result['version'], str)


class TestHandleGetBrowserConfig(unittest.TestCase):
    """Тесты handle_get_browser_config."""

    def test_response_has_no_detected_browsers(self):
        """Ответ не содержит поле detectedBrowsers (убрано из горячего пути)."""
        with patch('server.servers.handlers.browser_config.get_browser_config',
                   return_value={'browserPath': '/path', 'autostartBrowser': True}):
            result = handle_get_browser_config()
        self.assertNotIn('detectedBrowsers', result)
        self.assertEqual(result['browserPath'], '/path')

    def test_response_includes_browser_path_and_autostart(self):
        """Ответ содержит browserPath и autostartBrowser."""
        with patch('server.servers.handlers.browser_config.get_browser_config',
                   return_value={'browserPath': '/custom/path', 'autostartBrowser': False}):
            result = handle_get_browser_config()
        self.assertEqual(result['browserPath'], '/custom/path')
        self.assertFalse(result['autostartBrowser'])


class TestCloseTunnelsOnConfigChange(unittest.TestCase):
    """Тесты _close_tunnels_on_config_change."""

    def setUp(self):
        patcher = patch('server.servers.handlers.close_tunnels_for_proxy')
        self.mock_close = patcher.start()
        self.addCleanup(patcher.stop)

        patcher_all = patch('server.servers.handlers.close_all_connections')
        self.mock_close_all = patcher_all.start()
        self.addCleanup(patcher_all.stop)

    def test_no_changes(self):
        """Без изменений — ничего не закрывается"""
        old = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        new = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        need_flush = _close_tunnels_on_config_change(old, new)
        self.assertFalse(need_flush)
        self.mock_close.assert_not_called()

    def test_proxy_removed(self):
        """Удалённый прокси — туннели закрываются"""
        old = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        new = {}
        need_flush = _close_tunnels_on_config_change(old, new)
        self.assertFalse(need_flush)
        self.mock_close.assert_called_once_with('p1')

    def test_proxy_disabled(self):
        """Выключенный прокси — туннели закрываются"""
        old = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        new = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': False}}
        need_flush = _close_tunnels_on_config_change(old, new)
        self.assertFalse(need_flush)
        self.mock_close.assert_called_once_with('p1')

    def test_proxy_enabled(self):
        """Включённый прокси — нужен полный сброс"""
        old = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': False}}
        new = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        need_flush = _close_tunnels_on_config_change(old, new)
        self.assertTrue(need_flush)
        self.mock_close.assert_not_called()

    def test_proxy_host_changed(self):
        """Изменение host у включённого прокси — туннели закрываются"""
        old = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        new = {'p1': {'proxyId': 'p1', 'host': '2.2.2.2', 'port': 1080, 'isEnabled': True}}
        need_flush = _close_tunnels_on_config_change(old, new)
        self.assertFalse(need_flush)
        self.mock_close.assert_called_once_with('p1')

    def test_proxy_port_changed(self):
        """Изменение порта у включённого прокси — туннели закрываются"""
        old = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}}
        new = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 9090, 'isEnabled': True}}
        need_flush = _close_tunnels_on_config_change(old, new)
        self.assertFalse(need_flush)
        self.mock_close.assert_called_once_with('p1')


class TestLogConfigChanges(unittest.TestCase):
    """Тесты _log_config_changes (проверяем, что код не падает и логирует корректно)."""

    def setUp(self):
        self.logger = logging.getLogger('flowlink.api')
        self.orig_level = self.logger.level
        self.logger.setLevel(logging.INFO)
        # Перехватываем логи
        self.handler = logging.handlers.MemoryHandler(capacity=100)
        self.logger.addHandler(self.handler)

    def tearDown(self):
        self.logger.removeHandler(self.handler)
        self.handler.close()
        self.logger.setLevel(self.orig_level)

    def _get_log_messages(self):
        return [r.getMessage() for r in self.handler.buffer]

    def test_no_changes(self):
        """Без изменений — пустые логи"""
        old_p = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        new_p = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        old_m = {'m1': {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}}
        new_m = {'m1': {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}}
        _log_config_changes(old_p, new_p, old_m, new_m)
        self.assertEqual(len(self._get_log_messages()), 0)

    def test_added_proxy(self):
        """Добавленный прокси — сообщение 'Добавлен прокси'"""
        old_p = {}
        new_p = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        _log_config_changes(old_p, new_p, {}, {})
        msgs = self._get_log_messages()
        self.assertTrue(any('Добавлен прокси' in m for m in msgs))

    def test_removed_proxy(self):
        """Удалённый прокси — сообщение 'Удалён прокси'"""
        old_p = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        new_p = {}
        _log_config_changes(old_p, new_p, {}, {})
        msgs = self._get_log_messages()
        self.assertTrue(any('Удалён прокси' in m for m in msgs))

    def test_changed_proxy_host(self):
        """Изменение host — сообщение 'Изменён прокси'"""
        old_p = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        new_p = {'p1': {'proxyId': 'p1', 'host': '2.2.2.2', 'port': 1080}}
        _log_config_changes(old_p, new_p, {}, {})
        msgs = self._get_log_messages()
        self.assertTrue(any('Изменён прокси' in m for m in msgs))

    def test_added_mask(self):
        """Добавленная маска — сообщение 'Добавлена маска'"""
        old_m = {}
        new_m = {'m1': {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}}
        proxy = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        _log_config_changes(proxy, proxy, old_m, new_m)
        msgs = self._get_log_messages()
        self.assertTrue(any('Добавлена маска' in m for m in msgs))

    def test_removed_mask(self):
        """Удалённая маска — сообщение 'Удалена маска'"""
        old_m = {'m1': {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}}
        new_m = {}
        proxy = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        _log_config_changes(proxy, proxy, old_m, new_m)
        msgs = self._get_log_messages()
        self.assertTrue(any('Удалена маска' in m for m in msgs))

    def test_mask_change_not_logged(self):
        """Изменение regexString маски НЕ логируется (фиксация текущего контракта)

        _log_config_changes сообщает только о добавленных/удалённых масках,
        изменение существующей маски не попадает в лог.
        """
        old_m = {'m1': {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}}
        new_m = {'m1': {'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.org'}}
        proxy = {'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080}}
        _log_config_changes(proxy, proxy, old_m, new_m)
        self.assertEqual(self._get_log_messages(), [])

    def test_proxy_username_password_change_not_logged(self):
        """Изменение только username/password прокси НЕ логируется

        Текущий контракт: логируется смена host/port, а смена
        credentials (username/password) — нет.
        """
        old_p = {
            'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                   'username': 'old_user', 'password': 'old_pass'},
        }
        new_p = {
            'p1': {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                   'username': 'new_user', 'password': 'new_pass'},
        }
        _log_config_changes(old_p, new_p, {}, {})
        self.assertEqual(self._get_log_messages(), [])


class TestHandlePostConfig(TempConfigMixin, unittest.TestCase):
    """Тесты handle_post_config — критический путь сохранения конфига."""

    def setUp(self):
        super().setUp()
        self.router = MaskRouter()
        self.router.refresh()

    def test_post_config_save_success(self):
        """POST /api/config сохраняет конфиг и возвращает success"""
        data = {
            'proxies': [
                {'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080,
                 'username': '', 'password': '', 'isEnabled': True},
            ],
            'masks': [{'maskId': 'm1', 'proxyId': 'p1', 'regexString': r'\.com'}],
        }
        result = asyncio.run(handle_post_config(data, self.router))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        # Проверяем, что данные действительно сохранились
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 1)
        self.assertEqual(len(loaded['masks']), 1)

    def test_post_config_non_dict_returns_error(self):
        """POST /api/config с не-данными возвращает ошибку"""
        # type: ignore[reportArgumentType] — намеренно передаём не-словарь для проверки ошибки
        result = asyncio.run(
            handle_post_config('not a dict', self.router),  # type: ignore[reportArgumentType]
        )
        self.assertIn('error', result)

    def test_post_config_empty_data(self):
        """POST /api/config с пустыми данными сохраняет пустой конфиг"""
        data = {'proxies': [], 'masks': []}
        result = asyncio.run(handle_post_config(data, self.router))
        assert isinstance(result, dict)
        self.assertTrue(result.get('success'))
        loaded = cfg.load_config()
        self.assertEqual(len(loaded['proxies']), 0)

    def test_post_config_closes_tunnels_on_removal(self):
        """POST /api/config с удалённым прокси закрывает туннели"""
        # Сохраняем прокси
        config_repo.save_raw({
            'proxies': [{'proxyId': 'p1', 'host': '1.1.1.1', 'port': 1080, 'isEnabled': True}],
            'masks': [],
        })
        # Принудительный сброс кэша — необходимо для изоляции тестов
        cfg.invalidate_cache()
        # Сохраняем конфиг без этого прокси
        data = {'proxies': [], 'masks': []}
        with patch('server.servers.handlers.close_tunnels_for_proxy') as mock_close:
            result = asyncio.run(handle_post_config(data, self.router))
            assert isinstance(result, dict)
            self.assertTrue(result.get('success'))
            mock_close.assert_called_once_with('p1')


class TestHandlePostEnabled(TempConfigEnabledMixin, unittest.TestCase):
    """Тесты handle_post_enabled — глобальный тоггл."""

    def setUp(self):
        super().setUp()
        self.router = MaskRouter()
        self.router.refresh()

    def test_enable_returns_success(self):
        """POST /api/enabled {enabled: true} → success"""
        cfg.set_enabled(False)
        result = asyncio.run(handle_post_enabled({'enabled': True}, self.router))
        self.assertTrue(result.get('success'))
        self.assertTrue(result.get('enabled'))
        self.assertTrue(cfg.is_enabled())

    def test_disable_returns_success(self):
        """POST /api/enabled {enabled: false} → success"""
        cfg.set_enabled(True)
        result = asyncio.run(handle_post_enabled({'enabled': False}, self.router))
        self.assertTrue(result.get('success'))
        self.assertFalse(result.get('enabled'))
        self.assertFalse(cfg.is_enabled())

    def test_missing_enabled_field_returns_error(self):
        """POST /api/enabled без поля enabled → ошибка"""
        result = asyncio.run(handle_post_enabled({}, self.router))
        self.assertIn('error', result)

    def test_non_dict_returns_error(self):
        """POST /api/enabled с не-данными → ошибка"""
        result = asyncio.run(
            # type: ignore[reportArgumentType] — намеренно передаём строку для проверки ошибки
            handle_post_enabled('invalid', self.router),  # type: ignore[reportArgumentType]
        )
        self.assertIn('error', result)
