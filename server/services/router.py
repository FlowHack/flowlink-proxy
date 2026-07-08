"""
Модуль маршрутизации — проверяет URL по маскам и возвращает целевой прокси.

Предкомпилирует все RegExp из масок для быстрой проверки.
"""

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
        self._rules: list[dict] = []
        self._proxy_map: dict[str, dict] = {}
        self._rebuild()

    def _rebuild(self):
        """Перестраивает список правил из текущего конфига. Вызывается при инициализации и refresh()."""
        cfg = config.load_config(force=True)
        enabled = config.is_enabled()

        proxies = cfg.get('proxies', [])
        masks = cfg.get('masks', [])

        # Строим карту прокси по proxyId для быстрого доступа
        self._proxy_map = {}
        for p in proxies:
            pid = p.get('proxyId')
            if not pid:
                logger.warning(f'Прокси без proxyId пропущен: {p.get("host", "?")}:{p.get("port", "?")}')
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
                logger.warning(f'Маска без proxyId пропущена: {regex_raw}')
                continue
            if not regex_raw:
                logger.warning(f'Маска {pid} без regexString пропущена')
                continue
            proxy = self._proxy_map.get(pid)
            if not proxy:
                logger.warning(f'Маска {regex_raw} ссылается на несуществующий прокси {pid}')
                continue
            if not proxy.get('isEnabled', True):
                logger.debug(f'Маска {regex_raw} пропущена: прокси {pid} выключен')
                continue

            try:
                regex = re.compile(regex_raw)
            except re.error as e:
                logger.warning(f'Ошибка компиляции regex маски "{regex_raw}": {e}')
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
        logger.debug(f'Маршрутизация включена: {len(rules)} правил из {len(masks)} масок')

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
                    logger.debug(f'Маршрут: {url} -> {rule["host"]}:{rule["port"]} (прокси {rule["proxyId"]})')
                    return {
                        'host': rule['host'],
                        'port': rule['port'],
                        'username': rule.get('username', ''),
                        'password': rule.get('password', ''),
                    }
            except re.error as e:
                logger.warning(f'Regex ошибка при проверке URL {url}: {e}')
                continue
        logger.debug(f'Маршрут: {url} -> напрямую (нет совпадений)')
        return None

    def refresh(self):
        """Принудительно перезагружает конфиг и перестраивает правила."""
        logger.info('Обновление правил маршрутизации')
        self._rebuild()
