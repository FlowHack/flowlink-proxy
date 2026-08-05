"""Тесты восстановления последнего активного прокси при запуске.

Проверяют _restore_last_active_proxy из server/__main__.py:
  - восстанавливает lastActiveProxyId, если прокси существует;
  - при отсутствии lastActiveProxyId (все выключены) ничего не меняет;
  - при несуществующем lastActiveProxyId ничего не меняет;
  - не трогает конфиг, если прокси нет.
"""

import unittest
from unittest.mock import patch

from server.__main__ import _restore_last_active_proxy


def _make_proxy(pid, enabled=True):
    return {
        'proxyId': pid,
        'host': '1.2.3.4',
        'port': 8080,
        'isEnabled': enabled,
    }


class TestRestoreLastActiveProxy(unittest.TestCase):
    """Тесты восстановления активного прокси при запуске."""

    def _run(self, config_data, last_active):
        """Выполняет _restore_last_active_proxy и возвращает сохранённый конфиг."""
        saved = {}

        def fake_load_config(**_kwargs):
            return config_data

        def fake_get_last_active():
            return last_active

        def fake_save_config(data):
            saved['data'] = data

        with patch('server.__main__.cfg.load_config', side_effect=fake_load_config), \
             patch('server.__main__.cfg.get_last_active_proxy', side_effect=fake_get_last_active), \
             patch('server.__main__.cfg.save_config', side_effect=fake_save_config):
            _restore_last_active_proxy()
        return saved.get('data')

    def test_restores_last_active(self):
        """Восстанавливает lastActiveProxyId, если прокси существует."""
        config = {
            'proxies': [_make_proxy('p1'), _make_proxy('p2')],
            'masks': [],
        }
        saved = self._run(config, 'p2')
        self.assertIsNotNone(saved)
        self.assertTrue(saved['proxies'][1]['isEnabled'])
        self.assertFalse(saved['proxies'][0]['isEnabled'])

    def test_no_proxies_no_change(self):
        """Нет прокси — конфиг не сохраняется."""
        config = {'proxies': [], 'masks': []}
        saved = self._run(config, 'p1')
        self.assertIsNone(saved)

    def test_no_last_active_no_change(self):
        """Нет lastActiveProxyId (все выключены) — конфиг не меняется."""
        config = {
            'proxies': [_make_proxy('p1'), _make_proxy('p2')],
            'masks': [],
        }
        saved = self._run(config, None)
        self.assertIsNone(saved)

    def test_nonexistent_last_active_no_change(self):
        """Несуществующий lastActiveProxyId — конфиг не меняется."""
        config = {
            'proxies': [_make_proxy('p1'), _make_proxy('p2')],
            'masks': [],
        }
        saved = self._run(config, 'ghost')
        self.assertIsNone(saved)

    def test_all_disabled_restores_last_active(self):
        """Все прокси выключены, но lastActiveProxyId есть — включаем его."""
        config = {
            'proxies': [_make_proxy('p1', enabled=False), _make_proxy('p2', enabled=False)],
            'masks': [],
        }
        saved = self._run(config, 'p1')
        self.assertIsNotNone(saved)
        self.assertTrue(saved['proxies'][0]['isEnabled'])
        self.assertFalse(saved['proxies'][1]['isEnabled'])

    def test_no_change_when_target_already_enabled(self):
        """Целевой прокси уже включён — конфиг не сохраняется."""
        config = {
            'proxies': [_make_proxy('p1', enabled=True), _make_proxy('p2', enabled=False)],
            'masks': [],
        }
        saved = self._run(config, 'p1')
        self.assertIsNone(saved)


if __name__ == '__main__':
    unittest.main()
