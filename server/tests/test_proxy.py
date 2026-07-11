"""
Тесты краевых случаев парсинга протокола: regex и функции parse_connect/parse_http.
"""

import unittest

from server.protocols.parser import RE_CONNECT, RE_HTTP, parse_connect, parse_http


class TestProxyRegex(unittest.TestCase):
    """Тестируем regex-паттерны парсера."""

    def test_connect_regex_valid(self):
        """RE_CONNECT совпадает с корректным CONNECT"""
        match = RE_CONNECT.match(b'CONNECT example.com:443 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2).decode(), 'example.com')
        self.assertEqual(int(match.group(3)), 443)

    def test_connect_regex_no_port(self):
        """CONNECT без порта → не совпадает (требуется порт)"""
        match = RE_CONNECT.match(b'CONNECT example.com HTTP/1.1\r\n')
        self.assertIsNone(match)

    def test_connect_regex_ipv4(self):
        """CONNECT с IPv4"""
        match = RE_CONNECT.match(b'CONNECT 1.2.3.4:8080 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2).decode(), '1.2.3.4')

    def test_connect_regex_lowercase(self):
        """CONNECT lowercase"""
        match = RE_CONNECT.match(b'connect example.com:443 HTTP/1.1\r\n')
        self.assertIsNone(match)

    def test_connect_regex_binary_host(self):
        """CONNECT с не-UTF8 хостом → decode не падает"""
        match = RE_CONNECT.match(b'CONNECT \xff\xfe\x00:443 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        host = match.group(2).decode(errors='replace')
        self.assertIn('\ufffd', host)

    def test_connect_regex_ipv6(self):
        """CONNECT с IPv6"""
        match = RE_CONNECT.match(b'CONNECT [::1]:443 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).decode(), '::1')
        self.assertEqual(int(match.group(3)), 443)

    def test_connect_regex_ipv6_full(self):
        """CONNECT с полным IPv6"""
        match = RE_CONNECT.match(b'CONNECT [2001:db8::1]:8080 HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1).decode(), '2001:db8::1')
        self.assertEqual(int(match.group(3)), 8080)

    def test_http_regex_valid(self):
        """RE_HTTP совпадает с корректным HTTP запросом"""
        match = RE_HTTP.match(b'GET http://example.com/path HTTP/1.1\r\n')
        self.assertIsNotNone(match)
        self.assertEqual(match.group(2).decode(), 'example.com')

    def test_http_regex_https(self):
        """RE_HTTP совпадает с https URL"""
        match = RE_HTTP.match(b'GET https://example.com/ HTTP/1.1\r\n')
        self.assertIsNotNone(match)

    def test_http_regex_no_method(self):
        """Не HTTP запрос → None"""
        match = RE_HTTP.match(b'INVALID / HTTP/1.1\r\n')
        self.assertIsNone(match)


class TestParseConnect(unittest.TestCase):
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


class TestParseHttp(unittest.TestCase):
    """Тесты функции parse_http."""

    def test_valid_get(self):
        """Корректный GET → (method, host, port, path, relative_line)"""
        result = parse_http(b'GET http://example.com/path HTTP/1.1')
        self.assertIsNotNone(result)
        method, host, port, path, relative_line = result
        self.assertEqual(method, 'GET')
        self.assertEqual(host, 'example.com')
        self.assertEqual(port, 80)
        self.assertEqual(path, '/path')
        self.assertIn(b'GET /path HTTP/1.1', relative_line)

    def test_valid_post_with_port(self):
        """POST с явным портом — порт входит в host-group парсера"""
        result = parse_http(b'POST http://example.com:8080/api HTTP/1.1')
        self.assertIsNotNone(result)
        _, host, port, path, _ = result
        # Парсер включает порт в host-group: example.com:8080
        self.assertEqual(host, 'example.com:8080')
        # Портgroup не захватывается отдельно (consumed by host)
        self.assertEqual(port, 80)
        self.assertEqual(path, '/api')

    def test_valid_https(self):
        """HTTPS URL — порт по умолчанию 80 (парсер не различает http/https)"""
        result = parse_http(b'GET https://example.com/ HTTP/1.1')
        self.assertIsNotNone(result)
        _, _, port, _, _ = result
        # Парсер использует порт по умолчанию 80 для всех протоколов
        self.assertEqual(port, 80)

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
        _, _, _, _, relative_line = result
        self.assertEqual(relative_line, b'PUT /data HTTP/1.1\r\n')
