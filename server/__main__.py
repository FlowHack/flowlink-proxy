#!/usr/bin/env python3
"""
Точка входа FlowLink Proxy.

Запускает:
  - HTTP CONNECT прокси-сервер (порт 8080)
  - HTTP API сервер для расширения (порт 8081)

Единственная ответственность: парсинг аргументов CLI и запуск компонентов.

Использование:
  python -m server  # Стандартные порты
  python -m server --proxy-port 9090  # Кастомный прокси порт
  python -m server --api-port 9091  # Кастомный API порт
  python -m server --debug  # Debug-логирование
  python -m server --dev  # Dev-режим (auto-reload + debug)
  python -m server --need-update  # Симуляция обновления (debug + SSE-событие)
"""

import argparse
import asyncio
import logging
import os
import signal
import sys

from server.logging_config import setup_logging
from server.protocols.mock_socks5 import MockSocks5Server
from server.servers.api import ApiServer
from server.servers.proxy import ProxyServer
from server.services.debug import log_startup_config
from server.services.events import emit_event
from server.services.router import MaskRouter
from server.version import __version__

try:
    from server.tray import start_tray
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False

logger = logging.getLogger('flowlink')


def _find_py_files(root: str) -> list[str]:
    """Собирает все .py файлы в директории рекурсивно."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith('.py'):
                files.append(os.path.join(dirpath, fn))
    return files


async def _file_watcher(root: str, poll_interval: float = 1.0) -> None:
    """
    Следит за изменениями .py файлов через os.stat.
    При любом изменении — логирует и завершает процесс через os._exit,
    чтобы внешняя обёртка перезапустила сервер.
    """
    files = _find_py_files(root)
    snapshots = {f: os.stat(f).st_mtime for f in files}
    logger.debug('Auto-reload: отслеживается %d файлов', len(files))

    while True:
        await asyncio.sleep(poll_interval)
        for f in files:
            try:
                mtime = os.stat(f).st_mtime
            except OSError:
                continue
            if mtime != snapshots.get(f):
                snapshots[f] = mtime
                rel = os.path.relpath(f, root)
                logger.info('Обнаружено изменение в %s, перезапуск...', rel)
                os._exit(0)


def _start_tray_icon(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event, args: argparse.Namespace):
    """Запускает иконку в системном трее, если поддерживается платформа."""
    if not getattr(sys, 'frozen', False) or not _HAS_TRAY or args.dev:
        return None
    try:
        icon = start_tray(lambda: loop.call_soon_threadsafe(stop_event.set))
        if icon:
            logger.info('Иконка в трее запущена')
        return icon
    except Exception as e:
        logger.warning('Не удалось запустить иконку в трее: %s', e)
        return None


def _setup_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    """Регистрирует обработчики сигналов SIGINT и SIGTERM."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _on_signal(s, stop_event))
        except NotImplementedError:
            logger.warning(
                'Регистрация обработчика %s не поддерживается на этой платформе',
                signal.Signals(sig).name,
            )


def _on_signal(sig: signal.Signals, stop_event: asyncio.Event) -> None:
    """Обработчик сигнала — устанавливает stop_event."""
    logger.info('Получен сигнал %s, завершение работы...', signal.Signals(sig).name)
    stop_event.set()


async def _run_server(args: argparse.Namespace) -> None:
    """Запускает proxy + API серверы и ждёт сигнала остановки."""
    try:
        router = MaskRouter()
    except RuntimeError as e:
        logger.error('Ошибка инициализации маршрутизатора: %s', e)
        return

    if args.debug:
        log_startup_config()

    proxy_server = ProxyServer(router, port=args.proxy_port)
    api_server = ApiServer(
        router, port=args.api_port,
        debug=args.debug, need_update=args.need_update,
    )

    try:
        await asyncio.gather(
            proxy_server.start(),
            api_server.start(),
        )
        logger.info('Прокси-сервер слушает 127.0.0.1:%d', args.proxy_port)
        logger.info('API-сервер слушает 127.0.0.1:%d', args.api_port)
    except OSError as e:
        if 'address already in use' in str(e).lower():
            logger.error(
                'Порт занят: %s. Укажите другие порты через '
                '--proxy-port / --api-port', e,
            )
        else:
            logger.error('Ошибка запуска сервера: %s', e)
        return

    logger.info('FlowLink Proxy запущен. Нажмите Ctrl+C для остановки.')

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    tray_icon = _start_tray_icon(loop, stop_event, args)
    _setup_signal_handlers(loop, stop_event)

    if args.need_update:
        asyncio.create_task(emit_event('need_update', {'version': __version__}))
        logger.info('Симуляция обновления: отправлено SSE-событие need_update')

    if args.dev:
        server_root = os.path.dirname(os.path.abspath(__file__))
        asyncio.create_task(_file_watcher(server_root))
        mock_socks5 = MockSocks5Server()
        try:
            await mock_socks5.start()
            logger.info(
                'Mock-SOCKS5 сервер для тестирования: 127.0.0.1:%d',
                mock_socks5.port,
            )
        except OSError as e:
            logger.warning(
                'Не удалось запустить Mock-SOCKS5 сервер: %s. '
                'Пинг прокси будет недоступен.', e,
            )

    await stop_event.wait()
    del tray_icon

    logger.info('Останавливаю серверы...')
    try:
        await asyncio.wait_for(
            asyncio.gather(
                proxy_server.stop(),
                api_server.stop(),
            ),
            timeout=10,
        )
        logger.info('FlowLink Proxy остановлен.')
    except asyncio.TimeoutError:
        logger.warning('Таймаут остановки серверов — принудительный выход.')

    os._exit(0)


async def main():
    """
    Главная корутина FlowLink Proxy.

    Парсит аргументы CLI, запускает ProxyServer (прокси) и ApiServer (API),
    ожидает сигнала завершения и останавливает серверы.
    """
    parser = argparse.ArgumentParser(description='FlowLink Proxy — шлюз для маршрутизации трафика через SOCKS5')
    parser.add_argument('--proxy-port', type=int, default=8080,
                        help='Порт прокси-сервера (по умолч. 8080)')
    parser.add_argument('--api-port', type=int, default=8081,
                        help='Порт API сервера (по умолч. 8081)')
    parser.add_argument('--debug', action='store_true', help='Режим отладки')
    parser.add_argument('--dev', action='store_true',
                        help='Режим разработки (debug + auto-reload)')
    parser.add_argument(
        '--need-update', action='store_true',
        help='Симуляция обновления (debug + SSE-событие need_update)',
    )
    args = parser.parse_args()

    if args.dev:
        args.debug = True
    if args.need_update:
        args.debug = True

    setup_logging(args.debug)
    logger.info('FlowLink Proxy v%s запуск...', __version__)
    logger.info('Прокси-сервер: порт %d', args.proxy_port)
    logger.info('API-сервер: порт %d', args.api_port)
    logger.info('Режим отладки: %s', 'включён' if args.debug else 'выключен')
    if args.dev:
        logger.info('Режим разработки: включён (auto-reload)')
    if args.need_update:
        logger.info('Симуляция обновления: включена')

    await _run_server(args)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger = logging.getLogger('flowlink')
        logger.critical(
            'Критическая ошибка: %s. Если проблема повторяется, '
            'обратитесь в поддержку: flowlink.proxy@atomicmail.io',
            e, exc_info=True,
        )
        sys.exit(1)
