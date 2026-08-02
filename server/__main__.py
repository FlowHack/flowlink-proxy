#!/usr/bin/env python3
# pylint: disable=too-many-lines  # модуль оркестрирует запуск серверов, трея и автозапуск браузера; разбиение нецелесообразно
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
import time
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


def _show_browser_already_running_dialog(
    callbacks: dict,
    browser_path: str,
    proxy_port: int,
) -> bool:
    """
    Показывает диалог предупреждения о запущенном процессе браузера.

    Chrome/Chromium игнорирует --proxy-server, если браузер уже запущен.
    Диалог предлагает завершить процессы браузера и запустить его заново
    через FlowLink Proxy, либо закрыть диалог (отмена). В сообщение
    включается инструкция по ручному завершению процесса.

    Диалог привязан к tk_root трея (parent_root), чтобы не создавать
    второй tk.Tk() в потоке, где уже работает mainloop. Корректно
    вызывается и из _on_done (mainloop-поток через after(0, ...)):
    show_info с parent_root использует wait_window — вложенный цикл
    событий, безопасный в этом потоке.

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root).
        browser_path: Путь к исполняемому файлу браузера.
        proxy_port: Порт HTTP-прокси.

    Returns:
        True если браузер был перезапущен после завершения процессов,
        False при отмене, ошибке или недоступности tkinter.
    """
    tk_root = callbacks.get('tk_root')
    if tk_root is None:
        logger.warning(
            'Браузер уже запущен (%s), но tk_root недоступен — '
            'диалог предупреждения не показан',
            browser_path,
        )
        return False

    try:
        # Ленивый импорт: tkinter-диалог нужен только при работе с треем
        from server.ui.dialogs import \
            show_info  # pylint: disable=import-outside-toplevel
    except ImportError:
        logger.info('tkinter недоступен — диалог предупреждения не показан')
        return False

    # Ленивый импорт: модуль browser_process подключается только при
    # необходимости показа диалога
    from server.config import \
        browser_process as _browser_process  # pylint: disable=import-outside-toplevel

    instructions = _browser_process.get_manual_kill_instructions(browser_path)
    relaunched = {'value': False}

    def _on_kill_and_launch() -> None:
        """
        Завершает процессы браузера и запускает его через FlowLink Proxy.
        """
        if not _browser_process.kill_browser_processes(browser_path):
            logger.error(
                'Не удалось завершить процессы браузера: %s',
                browser_path,
            )
            return
        # Небольшая пауза, чтобы ОС освободила ресурсы завершённых
        # процессов (особенно актуально для Windows taskkill)
        time.sleep(0.5)
        second_result = _browser_config.launch_browser(
            browser_path, proxy_port=proxy_port,
        )
        if second_result == 'already_running':
            logger.warning(
                'После завершения процессов браузер всё ещё запущен: %s',
                browser_path,
            )
            return
        relaunched['value'] = bool(second_result)

    message = (
        'Для работы через прокси браузер необходимо закрыть и запустить '
        'через FlowLink Proxy. Закрытие браузера может прервать '
        'незавершённые действия (скачивание файлов, обновления и т.п.). '
        'Если идёт важный процесс — дождитесь его завершения и повторите '
        'попытку.\n\n'
        'Как завершить процесс вручную:\n'
        f'{instructions}\n\n'
        'Внимание: будут закрыты все процессы выбранного браузера. '
        'Если запущено несколько профилей или окон — все они будут закрыты.'
    )

    show_info(
        title='Браузер уже запущен',
        message=message,
        buttons=[
            {
                'text': 'Отмена',
                'action': lambda: None,
                'primary': False,
            },
            {
                'text': 'Закрыть браузер и запустить через FlowLink Proxy',
                'action': _on_kill_and_launch,
                'primary': True,
            },
        ],
        parent_root=tk_root,
    )
    return relaunched['value']


def _show_browser_not_selected_dialog(callbacks: dict) -> None:
    """
    Показывает диалог о том, что браузер не выбран.

    Вызывается при нажатии «Запустить браузер», когда путь к браузеру
    пуст или невалиден (браузер ещё не выбран в меню бэкенда).
    Диалог привязан к tk_root трея (parent_root), аналогично
    _show_browser_already_running_dialog.

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root).
    """
    tk_root = callbacks.get('tk_root')
    if tk_root is None:
        logger.warning(
            'Браузер не выбран, но tk_root недоступен — '
            'диалог уведомления не показан',
        )
        return

    try:
        # Ленивый импорт: tkinter-диалог нужен только при работе с треем
        from server.ui.dialogs import \
            show_info  # pylint: disable=import-outside-toplevel
    except ImportError:
        logger.info('tkinter недоступен — диалог уведомления не показан')
        return

    show_info(
        title='Браузер не выбран',
        message=(
            'Для запуска браузера через FlowLink Proxy сначала выберите '
            'его в меню бэкенда (пункт «Выбрать браузер...»).'
        ),
        buttons=[
            {
                'text': 'OK',
                'primary': True,
            },
        ],
        parent_root=tk_root,
    )


def _launch_browser_sync(
    callbacks: dict,
    browser_path: str,
    proxy_port: int,
) -> bool:
    """
    Синхронный запуск браузера (fallback без трея/popup).

    Блокирует вызывающий поток на время проверки процессов и запуска.
    Используется, когда tkinter/popup недоступны (трей не запущен).

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root).
        browser_path: Путь к исполняемому файлу браузера.
        proxy_port: Порт HTTP-прокси.

    Returns:
        True если браузер запущен, False при ошибке или отмене.
    """
    # Браузер не выбран — показываем уведомление и не пытаемся запускать
    if not _browser_config.validate_browser_path(browser_path):
        _show_browser_not_selected_dialog(callbacks)
        return False

    result = _browser_config.launch_browser(
        browser_path, proxy_port=proxy_port,
    )
    if result == 'already_running':
        return _show_browser_already_running_dialog(
            callbacks, browser_path, proxy_port,
        )
    return bool(result)


def _launch_browser_callback(
    callbacks: dict,
    proxy_port: int,
) -> bool:
    """
    Запускает браузер через FlowLink Proxy, обрабатывая уже запущенный процесс.

    При доступном popup-меню (трей) запуск выполняется в фоновом потоке,
    а в статусбаре popup показывается индикатор «Запуск браузера...».
    Mainloop продолжает работать через вложенный wait_variable, поэтому
    статусбар успевает отрисоваться. Если tk_root/popup недоступны —
    используется синхронный запуск (_launch_browser_sync).

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root, popup).
        proxy_port: Порт HTTP-прокси.

    Returns:
        True если браузер запущен (напрямую или после диалога),
        False при ошибке или отмене.
    """
    browser_path = _browser_config.get_browser_path()
    # Браузер не выбран — показываем уведомление и не пытаемся запускать
    if not _browser_config.validate_browser_path(browser_path):
        _show_browser_not_selected_dialog(callbacks)
        return False

    tk_root = callbacks.get('tk_root')
    popup = callbacks.get('popup')

    # Если трея (tkinter) нет — синхронный запуск, как раньше
    if tk_root is None or popup is None:
        return _launch_browser_sync(callbacks, browser_path, proxy_port)

    try:
        # tkinter гарантированно доступен, раз tk_root создан треем
        import tkinter as tk  # pylint: disable=import-outside-toplevel
    except ImportError:
        return _launch_browser_sync(callbacks, browser_path, proxy_port)

    result: dict = {'value': None, 'error': None}
    done_var = tk.BooleanVar(tk_root)

    def _on_done() -> None:
        """
        Обрабатывает результат фонового запуска в mainloop-потоке.

        Вызывается через tk_root.after(0, ...) — все операции с tk
        выполняются только здесь (не в фоновом потоке).
        """
        try:
            if result['error'] is not None:
                logger.error(
                    'Ошибка запуска браузера %s: %s',
                    browser_path, result['error'],
                )
            elif result['value'] == 'already_running':
                # Диалог выполняется в mainloop-потоке: wait_window внутри
                # show_info запускает вложенный цикл событий, что безопасно.
                result['value'] = _show_browser_already_running_dialog(
                    callbacks, browser_path, proxy_port,
                )
        finally:
            try:
                popup.hide_loading()
            except (tk.TclError, RuntimeError) as e:
                logger.debug(
                    'Не удалось скрыть статусбар загрузки: %s', e,
                )
            try:
                done_var.set(True)
            except tk.TclError:
                logger.debug(
                    'Не удалось разблокировать wait_variable',
                )

    def _worker() -> None:
        """
        Фоновый поток: запускает браузер, не трогая tkinter.

        Результат сохраняется в общий словарь, а завершение планируется
        через tk_root.after(0, ...) — потокобезопасно в tkinter.
        """
        try:
            result['value'] = _browser_config.launch_browser(
                browser_path, proxy_port=proxy_port,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: лог ошибки
            result['error'] = e
        finally:
            try:
                tk_root.after(0, _on_done)
            except (tk.TclError, RuntimeError) as e:
                logger.error(
                    'Не удалось запланировать обработку результата: %s', e,
                )
                try:
                    done_var.set(True)
                except tk.TclError:
                    pass

    try:
        popup.show_loading('Запуск браузера...')
    except (tk.TclError, RuntimeError) as e:
        logger.debug('Не удалось показать статусбар загрузки: %s', e)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    # Вложенный event loop: mainloop продолжает обрабатывать события
    # (в том числе обновление статусбара), пока не придёт результат
    try:
        tk_root.wait_variable(done_var)
    except (tk.TclError, RuntimeError) as e:
        logger.warning('Прервано ожидание запуска браузера: %s', e)

    if result['error'] is not None:
        return False
    return bool(result['value'])


def _close_browser_callback(
    _callbacks: dict,
    proxy_port: int,
) -> bool:
    """
    Закрывает браузер, запущенный через FlowLink Proxy.

    Проверяет, что браузер действительно запущен с флагом --proxy-server
    (а не просто запущен пользователем), и завершает его процессы.

    Args:
        _callbacks: Словарь коллбэков трея (сохранён для единообразия
            сигнатуры с другими колбэками меню).
        proxy_port: Порт HTTP-прокси.

    Returns:
        True если браузер закрыт (или не был запущен через прокси),
        False при ошибке завершения процессов.
    """
    browser_path = _browser_config.get_browser_path()
    if not _browser_config.validate_browser_path(browser_path):
        logger.warning(
            'Закрытие браузера: путь не выбран или невалиден: %s',
            browser_path,
        )
        return False

    from server.config import \
        browser_process as _browser_process  # pylint: disable=import-outside-toplevel

    if not _browser_process.is_browser_running_with_proxy(
        browser_path, proxy_port,
    ):
        logger.info(
            'Закрытие браузера: браузер не запущен через FlowLink Proxy: %s',
            browser_path,
        )
        return True

    if not _browser_process.kill_browser_processes(browser_path):
        logger.error(
            'Не удалось закрыть браузер: %s',
            browser_path,
        )
        return False

    logger.info('Браузер закрыт: %s', browser_path)
    return True


# Подавление: функция собирает колбэки для всех пунктов меню трея;
# локальные переменные — это сами колбэки и меню. Вынос в хелперы
# разорвал бы целостность настройки трея.
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

    Возвращает кортеж (tray, callbacks):
    - tray — объект трей-иконки или None, если трей недоступен;
    - callbacks — словарь коллбэков трея (нужен для автозапуска браузера
      и диалогов, даже когда сам трей не запущен).

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
        # На этой ветке callbacks ещё не собран — возвращаем пустой словарь
        return None, {}

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

    def _browser_path_saver(path: str) -> None:
        """Сохраняет путь браузера и уведомляет расширение через SSE."""
        _browser_config.save_browser_path(path)
        logger.info('Путь браузера сохранён: %s, отправляю SSE-событие', path)
        try:
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(
                    emit_event('browser_config_changed', {'browserPath': path})
                )
            )
        except RuntimeError:
            # Loop уже закрыт — событие не отправить, это не критично
            logger.warning('Не удалось отправить SSE-событие: loop закрыт')

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
        'browser_path_saver': _browser_path_saver,
        'browser_detector': _browser_config.auto_detect_browsers,
        'extension_connected_getter': is_extension_connected,
        'proxy_port': args.proxy_port,
        'close_browser_with_app_getter': _browser_config.get_close_browser_with_app,
        'close_browser_with_app_setter': _browser_config.set_close_browser_with_app,
    }
    # browser_launcher вынесен за литерал словаря: lambda замыкается на
    # callbacks (late binding) — при вызове из трея словарь уже создан.
    # Коллбэк обрабатывает случай уже запущенного браузера (диалог).
    callbacks['browser_launcher'] = lambda: _launch_browser_callback(
        callbacks, args.proxy_port,
    )
    # browser_closer закрывает браузер, запущенный через FlowLink Proxy.
    callbacks['browser_closer'] = lambda: _close_browser_callback(
        callbacks, args.proxy_port,
    )
    if not _HAS_TRAY:
        logger.warning('Модуль трея недоступен')
        return None, callbacks

    return _try_start_tray(callbacks, args.no_tkinter), callbacks


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
        # protected-access: вызов приватной функции-обёртки пакета tray —
        # публичного аналога для запуска fallback-трея нет.
        from server.tray import \
            _start_pystray_fallback  # pylint: disable=import-outside-toplevel,protected-access
        return _start_pystray_fallback(callbacks)
    except ImportError as e:
        logger.error(
            'Альтернативный трей: модуль fallback недоступен: %s', e,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: лог ошибки
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
        # type: ignore[reportPossiblyUnbound] — pyright не отслеживает
        # инвариант _HAS_TRAY=True → start_tray определён
        assert start_tray is not None  # type: ignore[reportPossiblyUnbound]
        icon = start_tray(  # type: ignore[reportPossiblyUnbound]
            callbacks, no_tkinter=no_tkinter,
        )
    # Последний рубеж: любой сбой бэкенда не должен уронить процесс,
    # а должен привести к цепочке fallback на другой трей.
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


async def _watch_api_connection(server_dir: str, callbacks: dict) -> None:
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
        """Показывает уведомление в отдельном потоке (tkinter или webbrowser).

        Если трей запущен и tk_root доступен — диалог привязывается к нему
        (не создаётся второй Tk() в потоке). Иначе создаётся отдельный root.
        """
        # Ссылка на .md файл с инструкцией на GitHub (для РФ — предупреждение о VPN)
        github_md_url = (
            'https://github.com/FlowHack/flowlink-proxy/blob/main/SETUP.md'
        )
        try:
            # Ленивый импорт: диалог подключения расширения показывается редко
            from server.ui.dialogs import \
                ask_yes_no  # pylint: disable=import-outside-toplevel

            message = (
                'FlowLink Proxy запущен, но расширение не подключено.\n'
                'Для работы необходимы браузер на Chromium (Chrome, Edge,\n'
                'Яндекс Браузер, Opera, Brave и др.) и установленное\n'
                'и запущенное расширение FlowLink Proxy.\n\n'
                'Установите расширение вручную и подключите его к серверу.\n'
                'Инструкция доступна в справке расширения.\n\n'
                'Внимание: для доступа к GitHub (скачивание расширения)\n'
                'пользователям в России может потребоваться VPN или прокси.'
            )
            # Привязываем диалог к существующему tk_root трея, если он доступен
            parent_root = callbacks.get('tk_root')
            answer = ask_yes_no(
                'FlowLink Proxy',
                message,
                yes_text='Открыть инструкцию',
                no_text='Закрыть',
                parent_root=parent_root,
            )

            if answer:
                logger.warning(
                    'Возможно, потребуется VPN или прокси для доступа '
                    'к GitHub (для пользователей в России)',
                )
                if os.path.isfile(help_path):
                    webbrowser.open(f'file://{os.path.abspath(help_path)}')
                else:
                    webbrowser.open(github_md_url)
        except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: лог ошибки
            # tkinter может упасть (TclError, RuntimeError) в потоке —
            # не роняем daemon-поток, а открываем инструкцию в браузере.
            logger.warning('Не удалось показать диалог уведомления (%s), '
                           'открываю инструкцию в браузере', e)
            if os.path.isfile(help_path):
                webbrowser.open(f'file://{os.path.abspath(help_path)}')
            else:
                webbrowser.open(github_md_url)

    thread = threading.Thread(target=_show_notification, daemon=True)
    thread.start()


def _autostart_browser_on_startup(
    tray_icon,
    callbacks: dict,
    args: argparse.Namespace,
) -> None:
    """
    Запускает браузер при старте бэкенда, если включён автозапуск.

    Если трей запущен и tk_root доступен — запуск выполняется в
    mainloop-потоке трея через after(0, ...), чтобы диалог «Браузер уже
    запущен» мог показаться (wait_variable/wait_window работают только
    в этом потоке). Если трея нет — синхронный запуск без popup.

    Args:
        tray_icon: Объект трей-иконки или None.
        callbacks: Словарь коллбэков трея.
        args: Аргументы командной строки (proxy_port).
    """
    if not _autostart.get_autostart_browser():
        return

    browser_path = _browser_config.get_browser_path()
    if not _browser_config.validate_browser_path(browser_path):
        logger.warning(
            'Автозапуск браузера включён, но путь к браузеру не выбран '
            'или невалиден: %s', browser_path,
        )
        return

    # Трей запущен и tk_root ещё не занят меню — запускаем в mainloop-потоке
    if tray_icon is not None and callbacks.get('tk_root') is None:
        tk_root = getattr(tray_icon, 'tk_root', None)
        popup = getattr(tray_icon, 'popup', None)
        if tk_root is not None:
            callbacks['tk_root'] = tk_root
            callbacks['popup'] = popup
            tk_root.after(0, lambda: _launch_browser_callback(
                callbacks, args.proxy_port,
            ))
            return

    # Трея нет или tk_root ещё не готов — синхронный запуск
    _launch_browser_sync(callbacks, browser_path, args.proxy_port)


async def _run_server(  # pylint: disable=too-many-statements  # сложная оркестрация запуска серверов и трея, разбиение нецелесообразно
    args: argparse.Namespace,
) -> None:
    """Запускает proxy + API серверы и ждёт сигнала остановки.

    Метод последовательно инициализирует маршрутизатор, серверы, трей,
    автозапуск браузера и обработку сигналов — вынос в отдельные функции
    разорвал бы единый жизненный цикл сервера.
    """
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
    except OSError as e:
        if 'address already in use' in str(e).lower():
            logger.error(
                'Порт занят: %s. Укажите другие порты через '
                '--proxy-port / --api-port', e,
            )
        else:
            logger.error('Ошибка запуска сервера: %s', e)
        return

    # Запись порт-файла выполняется ПОСЛЕ успешного старта серверов и вне
    # try-блока запуска: ошибка записи (например, отсутствие прав на каталог)
    # не должна останавливать уже работающие серверы — файл нужен только
    # для отладки и внешних инструментов.
    try:
        write_port_file(args.api_port, args.proxy_port)
    except OSError as e:
        logger.warning('Не удалось записать файл портов: %s', e)

    # Словарь callbacks создаётся заранее и передаётся в _watch_api_connection,
    # чтобы уведомление могло привязаться к tk_root трея (заполняется позже).
    callbacks = {}
    asyncio.create_task(_watch_api_connection(
        os.path.dirname(os.path.abspath(__file__)),
        callbacks,
    ))

    logger.info('FlowLink Proxy запущен. Нажмите Ctrl+C для остановки.')

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    tray_icon, tray_callbacks = _start_tray_icon(loop, stop_event, args)
    # Обновляем словарь callbacks, переданный в _watch_api_connection,
    # чтобы уведомление получило доступ к tk_root трея.
    callbacks.update(tray_callbacks)
    _setup_signal_handlers(loop, stop_event)

    # Автозапуск браузера при старте бэкенда (если включён)
    _autostart_browser_on_startup(tray_icon, callbacks, args)

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
    except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: лог ошибки
        # Последний рубеж: логируем и корректно завершаем процесс
        logger = logging.getLogger('flowlink')
        logger.critical(
            'Критическая ошибка: %s. Если проблема повторяется, '
            'обратитесь в поддержку: flowlink.proxy@atomicmail.io',
            e, exc_info=True,
        )
        sys.exit(1)
