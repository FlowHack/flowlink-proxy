"""
Тесты модуля extension_connection.py.

Тестирует: mark_connected, mark_disconnected, is_extension_connected.
"""

import unittest
from unittest.mock import patch

from server.services import extension_connection
from server.services.extension_connection import (is_extension_connected,
                                                  mark_connected,
                                                  mark_disconnected)


class TestExtensionConnection(unittest.TestCase):
    """Тесты отслеживания подключения расширения."""

    def setUp(self):
        """Сбрасывает счётчик перед каждым тестом."""
        patcher = patch.object(
            extension_connection, '_active_connections', 0,
        )
        self._counter_patcher = patcher
        self._counter_patcher.start()
        self.addCleanup(self._counter_patcher.stop)

    def test_initial_state_disconnected(self):
        """Изначально расширение не подключено."""
        self.assertFalse(is_extension_connected())

    def test_mark_connected_sets_connected(self):
        """После mark_connected расширение считается подключённым."""
        mark_connected()
        self.assertTrue(is_extension_connected())

    def test_mark_disconnected_sets_disconnected(self):
        """После mark_disconnected расширение считается отключённым."""
        mark_connected()
        mark_disconnected()
        self.assertFalse(is_extension_connected())

    def test_multiple_connections(self):
        """Несколько mark_connected требуют столько же mark_disconnected."""
        mark_connected()
        mark_connected()
        self.assertTrue(is_extension_connected())
        mark_disconnected()
        self.assertTrue(is_extension_connected())
        mark_disconnected()
        self.assertFalse(is_extension_connected())

    def test_disconnect_when_zero_no_crash(self):
        """mark_disconnected при нулевом счётчике не падает."""
        # Не должен бросить исключение
        mark_disconnected()
        self.assertFalse(is_extension_connected())


if __name__ == '__main__':
    unittest.main()
