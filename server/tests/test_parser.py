"""
Тесты краевых случаев парсинга протокола: regex и функции
parse_connect/parse_http, а также skip_headers (защита от slowloris).
"""

import asyncio
import unittest
from unittest.mock import AsyncMock

from server.protocols.parser import (RE_CONNECT, RE_HTTP, parse_connect,
                                     parse_http, skip_headers)

# type: ignore[reportOptionalMemberAccess] / [reportGeneralTypeIssues] ниже:
# pyright не знает, что assertIsNotNone(match) сужает тип Optional до match;
# в тестах доступ к группам и распаковка безопасны после явной проверки.


class TestParserRegex(unittest.TestCase):
    """Тестируем regex-паттерны парсера."""

    def test_connect_regex_valid(self):
        """RE_CONNECT совпадает с корректным CONNECT"""
        match = RE_CONNECT.match(b'CONNECT example.com:443 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        host = match.group(2).decode()  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(host, 'example.com')
        self.assertEqual(int(match.group(3)), 443)  # type: ignore[reportOptionalMemberAccess]

    def test_connect_regex_no_port(self):
        """CONNECT без порта → не совпадает (требуется порт)"""
        match = RE_CONNECT.match(b'CONNECT example.com HTTP/1.1\r\n')
        self.assertIsNone(match)

    def test_connect_regex_ipv4(self):
        """CONNECT с IPv4"""
        match = RE_CONNECT.match(b'CONNECT 1.2.3.4:8080 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        host = match.group(2).decode()  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(host, '1.2.3.4')

    def test_connect_regex_lowercase(self):
        """CONNECT lowercase"""
        match = RE_CONNECT.match(b'connect example.com:443 HTTP/1.1\r\n')
        self.assertIsNone(match)

    def test_connect_regex_binary_host(self):
        """CONNECT с не-UTF8 хостом → decode не падает"""
        match = RE_CONNECT.match(b'CONNECT \xff\xfe\x00:443 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        host = match.group(2).decode(errors='replace')  # type: ignore[reportOptionalMemberAccess]
        self.assertIn('\ufffd', host)

    def test_connect_regex_ipv6(self):
        """CONNECT с IPv6"""
        match = RE_CONNECT.match(b'CONNECT [::1]:443 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).decode(), '::1')  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(int(match.group(3)), 443)  # type: ignore[reportOptionalMemberAccess]

    def test_connect_regex_ipv6_full(self):
        """CONNECT с полным IPv6"""
        match = RE_CONNECT.match(b'CONNECT [2001:db8::1]:8080 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        addr = match.group(1).decode()  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(addr, '2001:db8::1')
        port = int(match.group(3))  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(port, 8080)

    def test_http_regex_valid(self):
        """RE_HTTP совпадает с корректным HTTP запросом"""
        match = RE_HTTP.match(b'GET http://example.com/path HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        # group(2) — схема, group(3) — host
        scheme = match.group(2).decode()  # type: ignore[reportOptionalMemberAccess]
        host = match.group(3).decode()  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(scheme, 'http')
        self.assertEqual(host, 'example.com')

    def test_http_regex_https(self):
        """RE_HTTP совпадает с https URL"""
        match = RE_HTTP.match(b'GET https://example.com/ HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        scheme = match.group(2).decode()  # type: ignore[reportOptionalMemberAccess]
        self.assertEqual(scheme, 'https')

    def test_http_regex_no_method(self):
        """Не HTTP запрос → None"""
        match = RE_HTTP.match(b'INVALID / HTTP/1.1\r\n')
        self.assertIsNone(match)


class TestParserParseConnect(unittest.TestCase):
    """Тесты функции parse_connect."""

    def test_valid_connect(self):
        """Корректный CONNECT → (host, port)"""
        result = parse_connect(b'CONNECT example.com:443 HTTP/1.1')
        self.assertEqual(result, ('example.com', 443))

    def test_connect_ipv4(self):
        """CONNECT с IPv4 → (host, port)"""
        result = parse_connect(b'CONNECT 1.2.3.4:8080 HTTP/1.1')
        self.assertEqual(result, ('1.2.3.4', 8080))

    def test_connect_ipv6(self):
        """CONNECT с IPv6 → (host, port)"""
        result = parse_connect(b'CONNECT [::1]:443 HTTP/1.1')
        self.assertEqual(result, ('::1', 443))

    def test_connect_invalid(self):
        """Некорректная строка → None"""
        result = parse_connect(b'GET / HTTP/1.1')
        self.assertIsNone(result)

    def test_connect_empty(self):
        """Пустая строка → None"""
        result = parse_connect(b'')
        self.assertIsNone(result)


class TestParserParseHttp(unittest.TestCase):
    """Тесты функции parse_http."""

    def test_valid_get(self):
        """Корректный GET → (method, host, port, path, relative_line)"""
        result = parse_http(b'GET http://example.com/path HTTP/1.1')
        self.assertIsNotNone(result)
        method, host, port, path, relative_line = result  # type: ignore[reportGeneralTypeIssues]
        self.assertEqual(method, 'GET')
        self.assertEqual(host, 'example.com')
        self.assertEqual(port, 80)
        self.assertEqual(path, '/path')
        self.assertIn(b'GET /path HTTP/1.1', relative_line)

    def test_valid_post_with_port(self):
        """POST с явным портом — порт парсится из URL"""
        result = parse_http(b'POST http://example.com:8080/api HTTP/1.1')
        self.assertIsNotNone(result)
        _, host, port, path, _ = result  # type: ignore[reportGeneralTypeIssues]
        self.assertEqual(host, 'example.com')
        self.assertEqual(port, 8080)
        self.assertEqual(path, '/api')

    def test_valid_https(self):
        """HTTPS URL без порта — порт по умолчанию 443"""
        result = parse_http(b'GET https://example.com/ HTTP/1.1')
        self.assertIsNotNone(result)
        _, host, port, _, _ = result  # type: ignore[reportGeneralTypeIssues]
        self.assertEqual(host, 'example.com')
        self.assertEqual(port, 443)

    def test_valid_https_with_explicit_port(self):
        """HTTPS URL с явным портом — явный порт имеет приоритет"""
        result = parse_http(b'GET https://example.com:8443/ HTTP/1.1')
        self.assertIsNotNone(result)
        _, _, port, _, _ = result  # type: ignore[reportGeneralTypeIssues]
        self.assertEqual(port, 8443)

    def test_http_invalid(self):
        """Некорректная строка → None"""
        result = parse_http(b'CONNECT example.com:443 HTTP/1.1')
        self.assertIsNone(result)

    def test_http_empty(self):
        """Пустая строка → None"""
        result = parse_http(b'')
        self.assertIsNone(result)

    def test_relative_line_contains_method_and_path(self):
        """relative_line содержит method + path + HTTP/1.1"""
        result = parse_http(b'PUT http://example.com/data HTTP/1.1')
        self.assertIsNotNone(result)
        _, _, _, _, relative_line = result  # type: ignore[reportGeneralTypeIssues]
        self.assertEqual(relative_line, b'PUT /data HTTP/1.1\r\n')


class TestSkipHeaders(unittest.IsolatedAsyncioTestCase):
    """Тесты skip_headers — чтение заголовков и защита от slowloris."""

    def _make_reader(self, lines):
        """
        Создаёт AsyncMock-ридер, возвращающий заданные строки из readline.

        Args:
            lines: Список байтовых строк, которые вернёт readline.

        Returns:
            AsyncMock с асинхронным readline.
        """
        reader = AsyncMock()
        reader.readline = AsyncMock(side_effect=lines)
        return reader

    async def test_reads_headers_until_empty_line(self):
        """Читает заголовки до пустой строки и возвращается (не падает)."""
        reader = self._make_reader([
            b'Host: example.com\r\n',
            b'User-Agent: test\r\n',
            b'\r\n',
        ])
        await skip_headers(reader)
        # Прочитано ровно 3 строки: 2 заголовка + пустая строка-терминатор
        self.assertEqual(reader.readline.await_count, 3)

    async def test_empty_line_returns_immediately(self):
        """При первой же пустой строке сразу возвращается (readline не повторяется)."""
        reader = self._make_reader([
            b'\r\n',
            b'Host: example.com\r\n',
        ])
        await skip_headers(reader)
        # После пустой строки чтение заголовков прекращается
        self.assertEqual(reader.readline.await_count, 1)

    async def test_header_limit_exceeded_does_not_raise(self):
        """Превышение лимита заголовков → молчаливый возврат (без исключений)."""
        # Непустые строки без пустой — цикл доходит до лимита _MAX_HEADER_LINES
        reader = self._make_reader([b'X-Test: value\r\n'] * 100)
        await skip_headers(reader)
        self.assertEqual(reader.readline.await_count, 100)

    async def test_timeout_does_not_raise(self):
        """Таймаут чтения (TimeoutError) → молчаливый возврат (без исключений)."""
        reader = AsyncMock()
        reader.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        await skip_headers(reader)
        self.assertEqual(reader.readline.await_count, 1)
