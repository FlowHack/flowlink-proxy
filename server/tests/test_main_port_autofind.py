"""
Тесты автоподбора порта API-сервера (_find_available_port, _resolve_api_port).

Проверяет:
- _find_available_port находит свободный порт в диапазоне, границы
  [start, end] включительно;
- порты проверяются строго по возрастанию (детерминизм выбора);
- при занятом всём диапазоне возвращается None;
- патч asyncio.start_server восстанавливается после выхода из контекста;
- _resolve_api_port возвращает запрошенный порт, если он свободен, не
  затрагивая диапазон расширения 8080–8090;
- при занятом запрошенном порте подбирается свободный из 8080–8090;
- если весь диапазон занят — возвращается запрошенный порт (fallback)
  без исключений: дальше сработает except OSError в _run_server.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.__main__ import _find_available_port, _resolve_api_port


def _make_probe():
    """Создаёт фейковый объект сервера с awaitable wait_closed()."""
    probe = MagicMock()
    probe.close = MagicMock(return_value=None)
    probe.wait_closed = AsyncMock(return_value=None)
    return probe


def _make_start_server_mock(occupied: set):
    """Создаёт AsyncMock для asyncio.start_server.

    Занятые порты (множество occupied) бросают OSError — как bind на занятый
    порт. Свободные возвращают фейковый probe с close()/wait_closed().
    """
    # pylint: disable=unused-argument  # сигнатура повторяет asyncio.start_server — мок получает kwargs по именам реального API
    async def _fake_start_server(handler, host=None, port=None):
        if port in occupied:
            raise OSError(f'address already in use: {port}')
        return _make_probe()

    return AsyncMock(side_effect=_fake_start_server)


def _ports_probed(mock) -> list:
    """Возвращает порты в порядке обращений к start_server."""
    return [call.kwargs.get('port') for call in mock.call_args_list]


class TestFindAvailablePort(unittest.TestCase):
    """_find_available_port — поиск свободного порта в диапазоне."""

    def test_returns_free_port_in_middle(self):
        """Свободный порт в середине диапазона находится корректно."""
        occupied = {10, 11, 12, 14, 15, 16, 17, 18, 19}
        mock = _make_start_server_mock(occupied)
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_find_available_port(10, 20))
        self.assertEqual(result, 13)
        # Порт 13 — первый свободный: проверялись порты 10..13 по возрастанию
        self.assertEqual(_ports_probed(mock), [10, 11, 12, 13])

    def test_returns_first_port_of_range(self):
        """Свободный первый порт диапазона возвращается сразу (start)."""
        mock = _make_start_server_mock(set())
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_find_available_port(8080, 8090))
        self.assertEqual(result, 8080)
        self.assertEqual(_ports_probed(mock), [8080])

    def test_returns_last_port_of_range(self):
        """Свободный последний порт возвращается (граница end включительно)."""
        # Заняты все порты, кроме 8090
        occupied = set(range(8080, 8090))
        mock = _make_start_server_mock(occupied)
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_find_available_port(8080, 8090))
        self.assertEqual(result, 8090)
        # Проверены все 11 портов диапазона
        self.assertEqual(len(_ports_probed(mock)), 11)

    def test_returns_none_when_all_ports_busy(self):
        """Весь диапазон занят — возвращается None."""
        occupied = set(range(8080, 8091))
        mock = _make_start_server_mock(occupied)
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_find_available_port(8080, 8090))
        self.assertIsNone(result)
        self.assertEqual(len(_ports_probed(mock)), 11)

    def test_probes_ports_in_ascending_order(self):
        """Порты проверяются строго по возрастанию (детерминизм)."""
        occupied = {8080, 8081, 8082, 8085, 8089}
        mock = _make_start_server_mock(occupied)
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_find_available_port(8080, 8090))
        self.assertEqual(result, 8083)
        self.assertEqual(_ports_probed(mock), [8080, 8081, 8082, 8083])

    def test_patch_restored_after_context(self):
        """После выхода из with-контекста asyncio.start_server восстанавливается."""
        mock = _make_start_server_mock(set())
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_find_available_port(8080, 8080))
            self.assertEqual(result, 8080)
        # Вне контекста патча start_server — оригинальная функция asyncio
        self.assertNotEqual(asyncio.start_server, mock)


class TestResolveApiPort(unittest.TestCase):
    """_resolve_api_port — выбор порта API с fallback на диапазон 8080–8090."""

    def test_returns_requested_when_free(self):
        """Запрошенный порт свободен — возвращается он, диапазон не трогается."""
        mock = _make_start_server_mock(set())
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_resolve_api_port(8081))
        self.assertEqual(result, 8081)
        # Проверялся только запрошенный порт — 8080–8090 не сканировались
        self.assertEqual(_ports_probed(mock), [8081])

    def test_returns_free_port_from_range(self):
        """Запрошенный занят, свободен порт в 8080–8090 — берётся свободный."""
        occupied = {8081, 8080}
        mock = _make_start_server_mock(occupied)
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_resolve_api_port(8081))
        self.assertEqual(result, 8082)
        # Сначала проверен 8081 (занят), затем диапазон по возрастанию до 8082
        self.assertEqual(_ports_probed(mock), [8081, 8080, 8081, 8082])

    def test_falls_back_to_requested_when_range_busy(self):
        """Запрошенный и весь диапазон 8080–8090 заняты — возвращается запрошенный.

        Функция не бросает исключений: дальше в _run_server сработает
        существующий except OSError как fallback.
        """
        occupied = set(range(8080, 8091))
        mock = _make_start_server_mock(occupied)
        with patch('asyncio.start_server', new=mock):
            result = asyncio.run(_resolve_api_port(8081))
        self.assertEqual(result, 8081)
        # 1 проверка запрошенного + 11 проверок диапазона
        self.assertEqual(len(_ports_probed(mock)), 12)
