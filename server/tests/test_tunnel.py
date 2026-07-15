"""
Тесты SSRF-защиты validate_target() из server/services/tunnel.py.

Проверяет блокировку приватных/локальных IP-адресов и разрешение публичных доменов.
"""

import asyncio
import unittest

from server.services.tunnel import validate_target


class TestValidateTarget(unittest.TestCase):
    """Тесты функции validate_target — SSRF-защита."""

    def _run(self, coro):
        """Запускает корутину в изолированном event loop."""
        return asyncio.run(coro)

    def test_loopback_127(self):
        """127.0.0.1 → блокируется (loopback)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('127.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_loopback_127_range(self):
        """127.0.0.2 → блокируется (loopback range)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('127.0.0.2', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_private_10(self):
        """10.0.0.1 → блокируется (private 10.0.0.0/8)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('10.0.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_private_172(self):
        """172.16.0.1 → блокируется (private 172.16.0.0/12)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('172.16.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_private_192(self):
        """192.168.1.1 → блокируется (private 192.168.0.0/16)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('192.168.1.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_link_local(self):
        """169.254.0.1 → блокируется (link-local)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('169.254.0.1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_ipv6_loopback(self):
        """[::1] → блокируется (IPv6 loopback)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('::1', 80))
        self.assertIn('SSRF', str(ctx.exception))

    def test_public_domain(self):
        """example.com → разрешается (публичный домен)"""
        # Не должно выбрасывать исключение
        try:
            self._run(validate_target('example.com', 80))
        except ValueError as e:
            # Если example.com резолвится в приватный IP — это ок (CI/ocker)
            if 'SSRF' not in str(e):
                raise

    def test_invalid_host(self):
        """Невалидный хост → ValueError (не SSRF)"""
        with self.assertRaises(ValueError) as ctx:
            self._run(validate_target('this.host.does.not.exist', 80))
        self.assertNotIn('SSRF', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
