"""
Модуль маршрутизации — проверяет URL по маскам и возвращает целевой прокси.

Предкомпилирует все RegExp из масок для быстрой проверки.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from server.config import config

logger = logging.getLogger('flowlink.router')


class MaskRouter:
    """
    Маршрутизатор URL до прокси на основе масок.

    Загружает конфиг, компилирует regex-маски и для каждого входящего URL
    находит первое совпадение. Предкомпиляция всех regex выполняется
    однократно в _rebuild() для производительности.
    """

    def __init__(self):
        """Инициализирует маршрутизатор масок.

        Загружает конфигурацию и перестраивает правила маршрутизации.
        """
        self._rules: list[dict] = []
        self._proxy_map: dict[str, dict] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        """
        Перестраивает список правил из текущего конфига.
        Вызывается при инициализации и refresh().
        """
        try:
            cfg = config.load_config(force=True)
        except (OSError, RuntimeError) as e:
            logger.error(
                'Не удалось загрузить конфиг для маршрутизации: %s. '
                'Маршрутизация временно отключена.', e,
            )
            self._rules = []
            self._proxy_map = {}
            return
        enabled = config.is_enabled()

        proxies = cfg.get('proxies', [])
        masks = cfg.get('masks', [])

        # Строим карту прокси по proxyId для быстрого доступа
        self._proxy_map = {}
        for p in proxies:
            pid = p.get('proxyId')
            if not pid:
                logger.warning(
                    'Прокси без proxyId пропущен: %s:%s',
                    p.get('host', '?'), p.get('port', '?'),
                )
                continue
            self._proxy_map[pid] = p

        # Если глобально выключен — очищаем правила и выходим
        if not enabled:
            self._rules = []
            logger.debug('Маршрутизация отключена глобальным переключателем')
            return

        # Компилируем все маски в regex
        rules = []
        for mask in masks:
            pid = mask.get('proxyId')
            regex_raw = mask.get('regexString', '')
            if not pid:
                logger.warning('Маска без proxyId пропущена: %s', regex_raw)
                continue
            if not regex_raw:
                logger.warning('Маска %s без regexString пропущена', pid)
                continue
            proxy = self._proxy_map.get(pid)
            if not proxy:
                logger.warning('Маска %s ссылается на несуществующий прокси %s', regex_raw, pid)
                continue
            if not proxy.get('isEnabled', True):
                logger.debug('Маска %s пропущена: прокси %s выключен', regex_raw, pid)
                continue

            try:
                regex = re.compile(regex_raw)
            except re.error as e:
                logger.warning('Ошибка компиляции regex маски "%s": %s', regex_raw, e)
                continue

            # Защита от битого конфига: отсутствие host/port не должно ронять маршрутизатор
            host = proxy.get('host')
            port = proxy.get('port')
            if not host or not isinstance(port, int) or not 1 <= port <= 65535:
                logger.warning(
                    'Маска %s: прокси %s имеет некорректные host/port (%r:%r), пропущена',
                    regex_raw, pid, host, port,
                )
                continue

            rules.append({
                'regex': regex,
                'proxyId': pid,
                'host': host,
                'port': port,
                'username': proxy.get('username', ''),
                'password': proxy.get('password', ''),
                'isEnabled': proxy.get('isEnabled', True),
            })

        self._rules = rules
        logger.debug('Маршрутизация включена: %d правил из %d масок', len(rules), len(masks))

    def route(self, url: str) -> Optional[dict]:
        """
        Проверяет URL по всем правилам и возвращает первый подходящий прокси.

        Args:
            url: Полный URL (например, 'https://example.com/path').

        Returns:
            Словарь с host/port/username/password или None, если нет совпадений.
        """
        for rule in self._rules:
            try:
                if rule['regex'].search(url):
                    logger.debug(
                        'Маршрут: %s -> %s:%s (прокси %s)',
                        url, rule['host'], rule['port'], rule['proxyId'],
                    )
                    return {
                        'host': rule['host'],
                        'port': rule['port'],
                        'username': rule.get('username', ''),
                        'password': rule.get('password', ''),
                        'proxyId': rule['proxyId'],
                    }
            except re.error as e:
                logger.warning('Regex ошибка при проверке URL %s: %s', url, e)
                continue
        logger.debug('Маршрут: %s -> напрямую (нет совпадений)', url)
        return None

    def refresh(self) -> None:
        """Принудительно перезагружает конфиг и перестраивает правила."""
        logger.info('Обновление правил маршрутизации')
        self._rebuild()
