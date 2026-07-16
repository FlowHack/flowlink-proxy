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
  python -m server --debug --count-proxy 5  # 5 фиктивных прокси для тестирования
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
import urllib.request
import urllib.error
import webbrowser

from server.config import config as cfg
from server.config import system_autostart as _system_autostart
from server.config import browser_config as _browser_config
from server.logging_config import setup_logging
from server.protocols.mock_socks5 import MockSocks5Server
from server.servers.api import ApiServer
from server.servers.proxy import ProxyServer
from server.services.debug import log_config_state
from server.services.events import emit_event
from server.services.fake_proxies import generate_fake_proxies
from server.services.router import MaskRouter
from server.utils import write_port_file
from server.version import __version__

try:
    from server.tray import start_tray
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False

# Импорты для колбэков трей
from server.config import autostart as _autostart
from server.utils import (
    clear_logs_only,
    clear_all_data,
    get_data_dir,
)

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


def _start_tray_icon(  # pylint: disable=too-many-locals
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
    args: argparse.Namespace,
):
    """
    Запускает иконку в системном трее с кастомным popup-меню.

    Передаёт все необходимые колбэки для пунктов меню:
    - Открытие/очистка логов и данных
    - Переключение автозапуска браузера
    - Выход из приложения
    """
    if not getattr(sys, 'frozen', False) or not _HAS_TRAY or args.dev:
        if not _HAS_TRAY:
            logger.info('Трей-иконка недоступна: tray модуль не найден')
        elif args.dev:
            logger.info('Трей-иконка отключена в dev-режиме')
        else:
            logger.info('Трей-иконка доступна только в standalone-сборке')
        return None

    logs_dir = os.path.join(get_data_dir(), 'logs')

    def _on_stop():
        try:
            loop.call_soon_threadsafe(stop_event.set)
        except RuntimeError:
            # Loop уже закрыт — сервер и так завершается
            pass

    def _autostart_getter():
        return _autostart.get_autostart_browser()

    def _autostart_setter(value):
        _autostart.set_autostart_browser(value)

    def _system_autostart_getter():
        return _system_autostart.is_system_autostart_enabled()

    def _system_autostart_setter(value):
        _system_autostart.set_system_autostart_enabled(value)

    def _log_dir_getter():
        return logs_dir

    def _data_dir_getter():
        return get_data_dir()

    def _clear_logs():
        clear_logs_only()

    def _clear_data():
        clear_all_data()

    try:
        callbacks = {
            'stop': _on_stop,
            'autostart_getter': _autostart_getter,
            'autostart_setter': _autostart_setter,
            'system_autostart_getter': _system_autostart_getter,
            'system_autostart_setter': _system_autostart_setter,
            'log_dir_getter': _log_dir_getter,
            'data_dir_getter': _data_dir_getter,
            'clear_logs': _clear_logs,
            'clear_data': _clear_data,
        }
        icon = start_tray(callbacks, no_tkinter=args.no_tkinter)
        if icon:
            logger.info('Иконка в трее запущена')
        return icon
    except (ImportError, OSError, RuntimeError) as e:
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


# Таймаут ожидания подключения расширения (секунды)
_EXTENSION_CONNECT_TIMEOUT = 300
_EXTENSION_CHECK_INTERVAL = 10


async def _watch_api_connection(api_port: int, server_dir: str) -> None:
    """
    Следит за подключением расширения к API-серверу.

    Если за 5 минут ни один запрос от расширения не был получен —
    показывает пользователю уведомление с инструкцией по установке.
    Использует stdlib urllib (без внешних зависимостей).

    Args:
        api_port: Порт API-сервера для проверки.
        server_dir: Директория server/ (для поиска help.html).
    """
    logger.debug('Ожидание подключения расширения (%d сек)...',
                 _EXTENSION_CONNECT_TIMEOUT)

    for elapsed in range(0, _EXTENSION_CONNECT_TIMEOUT, _EXTENSION_CHECK_INTERVAL):
        await asyncio.sleep(_EXTENSION_CHECK_INTERVAL)
        try:
            url = f'http://127.0.0.1:{api_port}/api/version'
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=3):
                # Сервер отвечает — расширение может подключиться
                logger.debug('API-сервер отвечает (прошло %d сек)', elapsed + _EXTENSION_CHECK_INTERVAL)
                return
        except (urllib.error.URLError, OSError):
            continue

    # 5 минут прошли, расширение не подключилось
    logger.warning('Расширение не подключено к API-серверу за %d секунд',
                   _EXTENSION_CONNECT_TIMEOUT)

    help_path = os.path.join(server_dir, '..', 'extension', 'popup', 'help.html')
    help_path = os.path.normpath(help_path)

    def _show_notification():
        """Показывает уведомление в отдельном потоке (tkinter или webbrowser)."""
        try:
            import tkinter as tk  # pylint: disable=import-outside-toplevel
            from tkinter import messagebox  # pylint: disable=import-outside-toplevel

            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)

            message = (
                'FlowLink Proxy запущен. Для работы необходимы также\n'
                'браузер Chrome и расширение FlowLink.\n\n'
                'Установите расширение и подключите его к серверу.'
            )
            answer = messagebox.askyesno(
                'FlowLink Proxy',
                message,
                icon='info',
            )
            root.destroy()

            if answer:
                logger.warning(
                    'Возможно, потребуется VPN или прокси для доступа '
                    'к GitHub (для пользователей в России)',
                )
                if os.path.isfile(help_path):
                    webbrowser.open(f'file://{os.path.abspath(help_path)}')
                else:
                    webbrowser.open('https://github.com/FlowHack/flowlink-proxy')
        except ImportError:
            logger.info('tkinter недоступен, открытие help.html через браузер')
            if os.path.isfile(help_path):
                webbrowser.open(f'file://{os.path.abspath(help_path)}')
            else:
                webbrowser.open('https://github.com/FlowHack/flowlink-proxy')

    thread = threading.Thread(target=_show_notification, daemon=True)
    thread.start()


async def _run_server(args: argparse.Namespace) -> None:
    """Запускает proxy + API серверы и ждёт сигнала остановки."""
    try:
        router = MaskRouter()
    except RuntimeError as e:
        logger.error('Ошибка инициализации маршрутизатора: %s', e)
        return

    if args.debug:
        log_config_state(is_startup=True)

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
        write_port_file(args.api_port, args.proxy_port)
        asyncio.create_task(_watch_api_connection(
            args.api_port,
            os.path.dirname(os.path.abspath(__file__)),
        ))
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
    parser = argparse.ArgumentParser(
        description='FlowLink Proxy — шлюз для маршрутизации трафика через SOCKS5',
    )
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
    parser.add_argument(
        '--count-proxy', type=int, default=0, metavar='N',
        help='Количество фиктивных прокси для тестирования (требует --debug)',
    )
    parser.add_argument(
        '--no-tkinter', action='store_true',
        help='Принудительно отключить tkinter popup (fallback на pystray)',
    )
    parser.add_argument(
        '--browser-path', type=str, default=None, metavar='PATH',
        help='Путь к браузеру для автозапуска (сохраняется в .flowlink-settings)',
    )
    args = parser.parse_args()

    if args.dev:
        args.debug = True
    if args.need_update:
        args.debug = True

    if args.count_proxy > 0 and not args.debug:
        parser.error('--count-proxy требует флага --debug (или --dev)')

    if args.browser_path:
        _browser_config.save_browser_path(args.browser_path)
        logger.info('Путь к браузеру сохранён: %s', args.browser_path)

    setup_logging(args.debug)
    logger.info('FlowLink Proxy v%s запуск...', __version__)
    logger.info('Прокси-сервер: порт %d', args.proxy_port)
    logger.info('API-сервер: порт %d', args.api_port)
    logger.info('Режим отладки: %s', 'включён' if args.debug else 'выключен')
    if args.dev:
        logger.info('Режим разработки: включён (auto-reload)')
    if args.need_update:
        logger.info('Симуляция обновления: включена')
    if args.count_proxy > 0:
        logger.info('Фиктивные прокси: %d', args.count_proxy)
    if args.no_tkinter:
        logger.info('Tkinter отключён (--no-tkinter), fallback на pystray')

    if args.count_proxy > 0:
        fake_data = generate_fake_proxies(args.count_proxy)
        cfg.inject_proxies(fake_data)

    await _run_server(args)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Последний рубеж: логируем и корректно завершаем процесс
        logger = logging.getLogger('flowlink')
        logger.critical(
            'Критическая ошибка: %s. Если проблема повторяется, '
            'обратитесь в поддержку: flowlink.proxy@atomicmail.io',
            e, exc_info=True,
        )
        sys.exit(1)
