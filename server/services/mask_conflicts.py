"""Логика конфликтов масок между прокси.

Правило: маски разных прокси могут пересекаться, включать друг друга или
быть идентичными, но в группе конфликтующих прокси может быть включён
только один прокси.

Группа конфликта — множество прокси, связанных транзитивно через
пересекающиеся маски. Если A конфликтует с B, а B с C — все трое в одной
группе, и включён может быть только один из них.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger('flowlink.mask_conflicts')

# Максимальная длина паттерна для защиты от ReDoS (совпадает с клиентом).
_MAX_PATTERN_LENGTH = 255


def convert_wildcard_to_regex(pattern: str) -> str:
    """Преобразует wildcard-паттерн в регулярное выражение.

    Логика повторяет convertWildcardToRegex из extension/shared/utils.js:
    '*' -> '.*', '?' -> '.', остальные спецсимволы экранируются.
    """
    if not isinstance(pattern, str):
        return ''
    truncated = pattern[:_MAX_PATTERN_LENGTH]
    # Схлопываем повторяющиеся звёздочки в одну.
    collapsed = re.sub(r'\*{2,}', '*', truncated)
    escaped = []
    for char in collapsed:
        if char == '*':
            escaped.append('.*')
        elif char == '?':
            escaped.append('.')
        elif char in '*?.+^${}()|[]\\':
            escaped.append('\\' + char)
        else:
            escaped.append(char)
    return ''.join(escaped)


def _split_segments(pattern: str) -> list[str]:
    """Разбивает wildcard-паттерн на литеральные сегменты между '*'.

    Пустые сегменты (от соседних звёздочек) отбрасываются.
    """
    return [seg for seg in pattern.split('*') if seg]


def wildcard_intersects(a: str, b: str) -> bool:
    """Проверяет, пересекаются ли два wildcard-паттерна.

    Два паттерна пересекаются, если существует строка, удовлетворяющая
    обоим. Для wildcard (только '*' и литералы) это решается через
    разбиение на сегменты: паттерны пересекаются, если хотя бы один
    литеральный сегмент одного паттерна содержится в другом паттерне
    (с учётом порядка сегментов).

    Точная проверка пересечения wildcard-паттернов — нетривиальная задача.
    Здесь используется детерминированная эвристика, покрывающая реальные
    кейсы: substring-проверка и проверка сегментов длиной >= 3 символов.
    """
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    if not a or not b:
        return False

    # Нормализуем: убираем звёздочки для substring-проверки.
    a_norm = a.replace('*', '').lower()
    b_norm = b.replace('*', '').lower()
    if not a_norm or not b_norm:
        # Паттерн из одних звёздочек пересекается со всем.
        return True

    # Уровень 1: substring-проверка.
    if a_norm in b_norm or b_norm in a_norm:
        return True

    # Уровень 2: сегментная проверка (сегменты от 3+ символов).
    a_segments = _split_segments(a)
    b_segments = _split_segments(b)
    for seg_a in a_segments:
        if len(seg_a) < 3:
            continue
        for seg_b in b_segments:
            if len(seg_b) < 3:
                continue
            if seg_a.lower() in seg_b.lower() or seg_b.lower() in seg_a.lower():
                return True

    return False


def compute_conflict_groups(  # pylint: disable=too-many-locals  # построение графа конфликтов требует нескольких структур
    proxies: list[dict[str, Any]],  # pylint: disable=unused-argument  # параметр сохранён для симметрии с validate_config
    masks: list[dict[str, Any]],
) -> list[set[str]]:
    """Вычисляет группы конфликтующих прокси.

    Два прокси конфликтуют, если существует хотя бы одна пара масок
    (по одной от каждого), чьи паттерны пересекаются. Группы строятся
    транзитивно.

    Args:
        proxies: список прокси из конфига.
        masks: список масок из конфига.

    Returns:
        Список множеств proxyId, каждое — группа конфликта.
        Прокси без масок и без конфликтов в группы не попадают.
    """
    # Собираем маски по прокси.
    masks_by_proxy: dict[str, list[dict[str, Any]]] = {}
    for mask in masks:
        pid = mask.get('proxyId')
        if not pid:
            continue
        masks_by_proxy.setdefault(pid, []).append(mask)

    # Строим граф конфликтов между прокси.
    proxy_ids = list(masks_by_proxy.keys())
    adjacency: dict[str, set[str]] = {pid: set() for pid in proxy_ids}

    # pylint: disable=consider-using-enumerate  # нужны индексы пары (i, j)
    for i in range(len(proxy_ids)):
        for j in range(i + 1, len(proxy_ids)):
            pid_a = proxy_ids[i]
            pid_b = proxy_ids[j]
            if _proxies_conflict(masks_by_proxy[pid_a], masks_by_proxy[pid_b]):
                adjacency[pid_a].add(pid_b)
                adjacency[pid_b].add(pid_a)

    # Обходим граф в ширину для построения транзитивных групп.
    visited: set[str] = set()
    groups: list[set[str]] = []
    for pid in proxy_ids:
        if pid in visited:
            continue
        group: set[str] = set()
        stack = [pid]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            group.add(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    stack.append(neighbor)
        if len(group) > 1:
            groups.append(group)

    return groups


def _proxies_conflict(
    masks_a: list[dict[str, Any]],
    masks_b: list[dict[str, Any]],
) -> bool:
    """Проверяет, конфликтуют ли два прокси по своим маскам."""
    for mask_a in masks_a:
        pattern_a = mask_a.get('pattern', '')
        if not pattern_a:
            continue
        for mask_b in masks_b:
            pattern_b = mask_b.get('pattern', '')
            if not pattern_b:
                continue
            if wildcard_intersects(pattern_a, pattern_b):
                return True
    return False


def _proxy_label(proxy: dict[str, Any]) -> str:
    """Возвращает человекочитаемую метку прокси для сообщений об ошибке."""
    label = proxy.get('label')
    if label:
        return str(label)
    host = proxy.get('host', '?')
    port = proxy.get('port', '?')
    return f'{host}:{port}'


def validate_config(
    proxies: list[dict[str, Any]],
    masks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Проверяет конфиг на конфликты включённых прокси.

    Правило: в каждой группе конфликтующих прокси может быть включён
    только один прокси.

    Args:
        proxies: список прокси из конфига.
        masks: список масок из конфига.

    Returns:
        Список ошибок. Каждая ошибка — словарь вида:
        {
            'proxyId': str,
            'proxyLabel': str,
            'conflictingProxyId': str,
            'conflictingProxyLabel': str,
            'maskPattern': str,
        }
        Пустой список — конфликтов нет.
    """
    proxy_by_id = {p.get('proxyId'): p for p in proxies if p.get('proxyId')}

    # Собираем маски по прокси.
    masks_by_proxy: dict[str, list[dict[str, Any]]] = {}
    for mask in masks:
        pid = mask.get('proxyId')
        if not pid:
            continue
        masks_by_proxy.setdefault(pid, []).append(mask)

    errors: list[dict[str, Any]] = []
    proxy_ids = list(masks_by_proxy.keys())

    # pylint: disable=consider-using-enumerate  # нужны индексы пары (i, j)
    for i in range(len(proxy_ids)):
        for j in range(i + 1, len(proxy_ids)):
            pid_a = proxy_ids[i]
            pid_b = proxy_ids[j]
            proxy_a = proxy_by_id.get(pid_a)
            proxy_b = proxy_by_id.get(pid_b)
            if not proxy_a or not proxy_b:
                continue
            # Конфликт важен только если оба прокси включены.
            if not proxy_a.get('isEnabled', True) or not proxy_b.get('isEnabled', True):
                continue
            if _proxies_conflict(masks_by_proxy[pid_a], masks_by_proxy[pid_b]):
                errors.append({
                    'proxyId': pid_a,
                    'proxyLabel': _proxy_label(proxy_a),
                    'conflictingProxyId': pid_b,
                    'conflictingProxyLabel': _proxy_label(proxy_b),
                    'maskPattern': _first_conflicting_pattern(
                        masks_by_proxy[pid_a], masks_by_proxy[pid_b],
                    ),
                })

    return errors


def _first_conflicting_pattern(
    masks_a: list[dict[str, Any]],
    masks_b: list[dict[str, Any]],
) -> str:
    """Возвращает первый паттерн маски, вызвавший конфликт."""
    for mask_a in masks_a:
        pattern_a = mask_a.get('pattern', '')
        if not pattern_a:
            continue
        for mask_b in masks_b:
            pattern_b = mask_b.get('pattern', '')
            if not pattern_b:
                continue
            if wildcard_intersects(pattern_a, pattern_b):
                return str(pattern_a)
    return ''
