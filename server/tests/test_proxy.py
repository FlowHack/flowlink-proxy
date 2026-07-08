"""
Тесты краевых случаев парсинга протокола в proxy.py.
"""

import unittest

from server.protocols.parser import RE_CONNECT, RE_HTTP


class TestProxyEdgeCases(unittest.TestCase):
    """Тестируем только те части proxy, которые можно без сети."""

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
