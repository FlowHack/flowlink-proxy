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
import webbrowser

from server.config import browser_config as _browser_config
from server.config import config as cfg
from server.config import system_autostart as _system_autostart
from server.logging_config import setup_logging
from server.protocols.mock_socks5 import MockSocks5Server
from server.servers.api import ApiServer
from server.servers.proxy import ProxyServer
from server.services.debug import log_config_state
from server.services.events import emit_event
from server.services.extension_connection import is_extension_connected
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
from server.utils import clear_all_data, clear_logs_only, get_data_dir

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


def _handle_tray_error(
    exc: Exception, error_label: str,
) -> None:
    """Обработка ошибки запуска трей: critical в standalone, warning иначе."""
    if getattr(sys, 'frozen', False):
        logger.critical(
            'Не удалось запустить трей (%s): %s',
            error_label, exc,
            exc_info=isinstance(exc, Exception),
        )
        sys.exit(1)
    logger.warning(
        'Не удалось запустить трей (%s): %s',
        error_label, exc,
        exc_info=isinstance(exc, Exception),
    )


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

    Цепочка исключений (от конкретного к общему):
    1. ImportError — модуль tray не найден
    2. OSError — системные ошибки (Win32 API, файловая система)
    3. RuntimeError — runtime ошибки (Tcl, tkinter)
    4. ValueError/TypeError — некорректные аргументы
    5. AttributeError — отсутствующие атрибуты
    6. Exception — последний рубец
    """
    if not getattr(sys, 'frozen', False) or not _HAS_TRAY or args.dev:
        if not _HAS_TRAY:
            logger.info('Трей-иконка недоступна: tray модуль не найден')
        elif args.dev:
            logger.info('Трей-иконка отключена в dev-режиме')
        else:
            logger.info(
                'Трей-иконка доступна только '
                'в standalone-сборке',
            )
        return None

    logs_dir = os.path.join(get_data_dir(), 'logs')

    def _on_stop():
        try:
            loop.call_soon_threadsafe(stop_event.set)
        except RuntimeError:
            # Loop уже закрыт — сервер и так завершается
            pass

    def _autostart_getter() -> bool:
        return _autostart.get_autostart_browser()

    def _autostart_setter(value: bool) -> None:
        _autostart.set_autostart_browser(value)

    def _system_autostart_getter() -> bool:
        return _system_autostart.is_system_autostart_enabled()

    def _system_autostart_setter(value: bool) -> None:
        _system_autostart.set_system_autostart_enabled(value)

    def _log_dir_getter() -> str:
        return logs_dir

    def _data_dir_getter() -> str:
        return get_data_dir()

    def _clear_logs() -> None:
        clear_logs_only()

    def _clear_data() -> None:
        clear_all_data()

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
        'test_fallback_icon': args.test_fallback_icon,
        'browser_path_getter': _browser_config.get_browser_path,
        'browser_path_saver': _browser_config.save_browser_path,
        'browser_detector': _browser_config.auto_detect_browsers,
        'browser_launcher': lambda: _browser_config.launch_browser(
            _browser_config.get_browser_path(),
            proxy_port=args.proxy_port,
        ),
        'extension_connected_getter': is_extension_connected,
    }
    if not _HAS_TRAY:
        logger.warning('Модуль трея недоступен')
        return None

    return _try_start_tray(callbacks, args.no_tkinter)


def _start_alt_tray(callbacks: dict):
    """
    Запускает альтернативный трей-бэкенд: pystray с нативным меню.

    Второй шаг цепочки отказоустойчивости: вызывается, когда основной
    платформенный бэкенд (start_tray) вернул None или бросил исключение.
    Нативное меню pystray не зависит от tkinter и работает на всех ОС.

    Args:
        callbacks: Словарь с коллбэками трея.

    Returns:
        Объект трей-иконки или None при ошибке.
    """
    try:
        # Ленивый импорт: функция обёрнута в server/tray/__init__.py
        from server.tray import \
            _start_pystray_fallback  # pylint: disable=import-outside-toplevel,protected-access
        return _start_pystray_fallback(callbacks)
    except ImportError as e:
        logger.error(
            'Альтернативный трей: модуль fallback недоступен: %s', e,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(
            'Альтернативный трей: непредвиденная ошибка: %s',
            e, exc_info=True,
        )
    return None


def _try_start_tray(
    callbacks: dict, no_tkinter: bool,
):
    """
    Запуск start_tray с обработкой ошибок и цепочкой fallback.

    Цепочка отказоустойчивости:
    1. Основной трей (платформенный бэкенд, start_tray).
    2. Если основной вернул None или бросил исключение — pystray
       с нативным меню (_start_alt_tray). Шаг пропускается при
       --no-tkinter: start_tray уже использовал нативный fallback.
    3. Если все бэкенды недоступны — _handle_tray_error
       (critical + sys.exit(1) в standalone, warning в исходниках).
    """
    _labels: dict[type, str] = {
        ImportError: 'импорт',
        OSError: 'системная ошибка',
        RuntimeError: 'runtime ошибка',
        ValueError: 'некорректные данные',
        TypeError: 'некорректные данные',
        AttributeError: 'атрибут не найден',
    }

    # Шаг 1: основной платформенный бэкенд
    try:
        # _HAS_TRAY=True гарантирует импорт start_tray
        assert start_tray is not None  # type: ignore[reportPossiblyUnbound]
        icon = start_tray(  # type: ignore[reportPossiblyUnbound]
            callbacks, no_tkinter=no_tkinter,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        icon = None
        label = _labels.get(type(exc), 'непредвиденная ошибка')
        logger.warning(
            'Основной трей не запустился (%s): %s',
            label, exc, exc_info=True,
        )

    if icon:
        logger.info('Иконка в трее запущена')
        return icon

    # Шаг 2: альтернативный бэкенд — pystray с нативным меню
    if not no_tkinter:
        logger.info(
            'Основной трей недоступен, попытка pystray '
            'с нативным меню...',
        )
        alt_icon = _start_alt_tray(callbacks)
        if alt_icon:
            logger.info(
                'Альтернативный трей (pystray, нативное меню) запущен',
            )
            return alt_icon

    # Шаг 3: все трей-бэкенды недоступны
    _handle_tray_error(
        RuntimeError('Все трей-бэкенды недоступны'),
        'запуск',
    )
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
_EXTENSION_CONNECT_TIMEOUT = 120
_EXTENSION_CHECK_INTERVAL = 10


async def _watch_api_connection(server_dir: str) -> None:
    """
    Следит за подключением расширения к API-серверу.

    Если за 2 минуты расширение не установило SSE-соединение —
    показывает пользователю уведомление с инструкцией по установке.
    Состояние подключения отслеживается через extension_connection
    (активные SSE-соединения от расширения к /api/events).

    Args:
        server_dir: Директория server/ (для поиска help.html).
    """
    logger.debug('Ожидание подключения расширения (%d сек)...',
                 _EXTENSION_CONNECT_TIMEOUT)

    for elapsed in range(0, _EXTENSION_CONNECT_TIMEOUT, _EXTENSION_CHECK_INTERVAL):
        await asyncio.sleep(_EXTENSION_CHECK_INTERVAL)
        if is_extension_connected():
            # Расширение установило SSE-соединение
            logger.debug(
                'Расширение подключено (прошло %d сек)',
                elapsed + _EXTENSION_CHECK_INTERVAL,
            )
            return

    # 2 минуты прошли, расширение не подключилось
    logger.warning('Расширение не подключено к API-серверу за %d секунд',
                   _EXTENSION_CONNECT_TIMEOUT)

    help_path = os.path.join(server_dir, '..', 'extension', 'popup', 'help.html')
    help_path = os.path.normpath(help_path)

    def _show_notification():
        """Показывает уведомление в отдельном потоке (tkinter или webbrowser)."""
        try:
            from server.ui.dialogs import \
                ask_yes_no  # pylint: disable=import-outside-toplevel

            message = (
                'FlowLink Proxy запущен, но расширение не подключено.\n'
                'Для работы необходимы браузер на Chromium (Chrome, Edge,\n'
                'Яндекс Браузер, Opera, Brave и др.) и установленное\n'
                'и запущенное расширение FlowLink Proxy.\n\n'
                'Установите расширение вручную и подключите его к серверу.\n'
                'Инструкция доступна в справке расширения.'
            )
            answer = ask_yes_no(
                'FlowLink Proxy',
                message,
                yes_text='Открыть инструкцию',
                no_text='Закрыть',
            )

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


async def main() -> None:
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
        '--test-fallback-icon', action='store_true',
        help='Тестирование дефолтной иконки (красный круг + FLP) '
             'вместо icons/icon.ico',
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
