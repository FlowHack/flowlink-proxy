"""
Модуль управления конфигурацией FlowLink Proxy.

Загружает, сохраняет и предоставляет доступ к config.json.
Пароли шифруются/расшифровываются через crypto.py.
"""

import json
import logging
import os
import sys

from server import crypto

logger = logging.getLogger('flowlink.config')

if getattr(sys, 'frozen', False):
    CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'config.json')
else:
    CONFIG_FILE = 'config.json'

DEFAULT_CONFIG = {
    'proxies': [],
    'masks': [],
    'isEnabled': True,
}


def _load_raw() -> dict:
    if not os.path.exists(CONFIG_FILE):
        save_raw(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(f'Ошибка загрузки {CONFIG_FILE}: {e}')


def save_raw(data: dict):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_config() -> dict:
    data = _load_raw()

    for proxy in data.get('proxies', []):
        if proxy.get('username'):
            try:
                proxy['username'] = crypto.decrypt(proxy['username'])
            except Exception as e:
                logger.warning('Ошибка расшифровки username для прокси %s: %s', proxy.get('proxyId', '?'), e)
                proxy['username'] = ''
        if proxy.get('password'):
            try:
                proxy['password'] = crypto.decrypt(proxy['password'])
            except Exception as e:
                logger.warning('Ошибка расшифровки password для прокси %s: %s', proxy.get('proxyId', '?'), e)
                proxy['password'] = ''

    return data


def save_config(data: dict):
    to_save = {
        'proxies': [],
        'masks': data.get('masks', []),
        'isEnabled': data.get('isEnabled', True),
    }

    for proxy in data.get('proxies', []):
        proxy_copy = dict(proxy)
        if proxy_copy.get('username'):
            proxy_copy['username'] = crypto.encrypt(proxy_copy['username'])
        if proxy_copy.get('password'):
            proxy_copy['password'] = crypto.encrypt(proxy_copy['password'])
        to_save['proxies'].append(proxy_copy)

    save_raw(to_save)


def get_all_proxies() -> list:
    return load_config().get('proxies', [])


def get_all_masks() -> list:
    return load_config().get('masks', [])


def is_enabled() -> bool:
    return load_config().get('isEnabled', True)
