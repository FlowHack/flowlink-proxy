"""
Модуль маршрутизации — проверяет URL по маскам и возвращает целевой прокси.

Предкомпилирует все RegExp из масок для быстрой проверки.
"""

import re
from typing import Optional

from server import config


class MaskRouter:

    def __init__(self):
        self._rules: list[dict] = []
        self._proxy_map: dict[str, dict] = {}
        self._rebuild()

    def _rebuild(self):
        cfg = config.load_config()
        enabled = cfg.get('isEnabled', True)

        proxies = cfg.get('proxies', [])
        masks = cfg.get('masks', [])

        self._proxy_map = {}
        for p in proxies:
            self._proxy_map[p['proxyId']] = p

        rules = []
        for mask in masks:
            pid = mask.get('proxyId')
            proxy = self._proxy_map.get(pid)
            if not proxy or not proxy.get('isEnabled', True):
                continue
            if not enabled:
                continue

            try:
                regex = re.compile(mask['regexString'])
            except re.error:
                continue

            rules.append({
                'regex': regex,
                'proxyId': pid,
                'host': proxy['host'],
                'port': proxy['port'],
                'username': proxy.get('username', ''),
                'password': proxy.get('password', ''),
            })

        self._rules = rules

    def route(self, url: str) -> Optional[dict]:
        for rule in self._rules:
            try:
                if rule['regex'].search(url):
                    return {
                        'host': rule['host'],
                        'port': rule['port'],
                        'username': rule.get('username', ''),
                        'password': rule.get('password', ''),
                    }
            except re.error:
                continue
        return None

    def refresh(self):
        self._rebuild()
