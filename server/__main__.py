#!/usr/bin/env python3
"""
Точка входа FlowLink Proxy.

Запускает:
  - HTTP CONNECT прокси-сервер (порт 8080)
  - HTTP API сервер для расширения (порт 8081)

Использование:
  python -m server                        # Стандартные порты
  python -m server --proxy-port 9090      # Кастомный прокси порт
  python -m server --api-port 9091        # Кастомный API порт
  python -m server --debug                # Debug-логирование
"""

import argparse
import asyncio
import logging
import logging.handlers
import os
import signal
import sys

from server.api import ApiServer
from server.proxy import ProxyServer
from server.router import MaskRouter


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # --- Консоль: INFO+ ---
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # --- Файл: DEBUG+ с ротацией ---
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller: __file__ ведёт в _MEIPASS — берём путь к .exe
            base = os.path.dirname(os.path.abspath(sys.executable))
            log_dir = os.path.join(base, 'logs')
        else:
            # Обычный Python: проект в ../server/__main__.py
            base = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base, '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'flowlink.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_242_880, backupCount=3, encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        pass  # Логи не критичны для работы


async def main():
    parser = argparse.ArgumentParser(description='FlowLink Proxy Gateway')
    parser.add_argument('--proxy-port', type=int, default=8080, help='Порт прокси-сервера (по умолч. 8080)')
    parser.add_argument('--api-port', type=int, default=8081, help='Порт API сервера (по умолч. 8081)')
    parser.add_argument('--debug', action='store_true', help='Режим отладки')
    args = parser.parse_args()

    setup_logging(args.debug)
    logger = logging.getLogger('flowlink')

    logger.info('FlowLink Proxy запуск...')
    logger.info(f'Прокси порт: {args.proxy_port}, API порт: {args.api_port}')

    router = MaskRouter()
    proxy_server = ProxyServer(router, port=args.proxy_port)
    api_server = ApiServer(router, port=args.api_port, debug=args.debug)

    try:
        await asyncio.gather(
            proxy_server.start(),
            api_server.start(),
        )
    except OSError as e:
        if 'address already in use' in str(e).lower():
            logger.error(f'Порт занят: {e}. Проверьте, не запущен ли уже FlowLink Proxy')
        else:
            logger.error(f'Ошибка запуска сервера: {e}')
        return

    logger.info('FlowLink Proxy запущен. Нажмите Ctrl+C для остановки.')

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info('Получен сигнал завершения...')
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    await stop_event.wait()

    logger.info('Останавливаю серверы...')
    await asyncio.gather(
        proxy_server.stop(),
        api_server.stop(),
    )
    logger.info('FlowLink Proxy остановлен.')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
