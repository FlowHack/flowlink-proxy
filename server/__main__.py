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
import secrets
import signal
import sys
import threading
import time
import webbrowser

from server.config import browser_config as _browser_config
from server.config import config as cfg
from server.config import system_autostart as _system_autostart
from server.i18n import _, init_i18n
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
    for dirpath, _dirs, filenames in os.walk(root):
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
            except OSError as e:
                logger.debug('Не удалось получить mtime для %s: %s', f, e)
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


def _show_browser_choice_dialog(
    callbacks: dict,
    title: str,
    message: str,
    primary_text: str,
    secondary_text: str,
) -> bool:
    """
    Показывает диалог выбора с двумя кнопками (вторичная — отмена).

    Единый шаблон для диалогов о запущенном браузере: проверка tk_root,
    ленивый импорт show_info, фиксация выбора primary-кнопки через
    вложенный коллбэк. Диалог привязан к tk_root трея (parent_root),
    чтобы не создавать второй tk.Tk() в потоке, где уже работает mainloop.

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root).
        title: Заголовок диалога.
        message: Текст сообщения.
        primary_text: Текст основной (подтверждающей) кнопки.
        secondary_text: Текст вторичной (отменяющей) кнопки.

    Returns:
        True если пользователь выбрал primary-кнопку, False при отмене,
        ошибке или недоступности tkinter.
    """
    tk_root = callbacks.get('tk_root')
    if tk_root is None:
        logger.warning(
            'Диалог «%s» не показан: tk_root недоступен', title,
        )
        return False

    try:
        # Ленивый импорт: tkinter-диалог нужен только при работе с треем
        from server.ui.dialogs import \
            show_info  # pylint: disable=import-outside-toplevel
    except ImportError:
        logger.info('tkinter недоступен — диалог «%s» не показан', title)
        return False

    choice = {'value': False}

    def _on_choose_primary() -> None:
        """Фиксирует выбор пользователя: primary-кнопка."""
        choice['value'] = True

    show_info(
        title=title,
        message=message,
        buttons=[
            {
                'text': secondary_text,
                'action': lambda: None,
                'primary': False,
            },
            {
                'text': primary_text,
                'action': _on_choose_primary,
                'primary': True,
            },
        ],
        parent_root=tk_root,
    )
    return choice['value']


def _show_browser_already_running_dialog(
    callbacks: dict,
    browser_path: str,
    _proxy_port: int,
) -> bool:
    """
    Показывает диалог предупреждения о запущенном процессе браузера.

    Chrome/Chromium игнорирует --proxy-server, если браузер уже запущен.
    Диалог предлагает завершить процессы браузера и запустить его заново
    через FlowLink Proxy, либо закрыть диалог (отмена). В сообщение
    включается инструкция по ручному завершению процесса.

    Диалог возвращает только ВЫБОР пользователя, а не результат
    перезапуска. Само завершение процессов и запуск браузера выполняются
    вызывающим кодом в фоновом потоке — иначе блокирующие вызовы
    (taskkill, time.sleep) заморозили бы mainloop tkinter.

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root).
        browser_path: Путь к исполняемому файлу браузера.
        _proxy_port: Порт HTTP-прокси (не используется внутри диалога,
            сохранён для единообразия сигнатуры с вызывающим кодом).

    Returns:
        True если пользователь выбрал «Закрыть браузер и запустить через
        FlowLink Proxy», False при отмене, ошибке или недоступности tkinter.
    """
    # Ленивый импорт: модуль browser_process подключается только при
    # необходимости показа диалога
    from server.config import \
        browser_process as _browser_process  # pylint: disable=import-outside-toplevel

    instructions = _browser_process.get_manual_kill_instructions(browser_path)
    message = _(
        'Для работы через прокси браузер необходимо закрыть и запустить '
        'через FlowLink Proxy. Закрытие браузера может прервать '
        'незавершённые действия (скачивание файлов, обновления и т.п.). '
        'Если идёт важный процесс — дождитесь его завершения и повторите '
        'попытку.\n\n'
        'Как завершить процесс вручную:\n'
        '{instructions}\n\n'
        'Внимание: будут закрыты все процессы выбранного браузера. '
        'Если запущено несколько профилей или окон — все они будут закрыты.'
    ).format(instructions=instructions)

    return _show_browser_choice_dialog(
        callbacks,
        title=_('Браузер уже запущен'),
        message=message,
        primary_text=_('Закрыть браузер и запустить через FlowLink Proxy'),
        secondary_text=_('Отмена'),
    )


# pylint: disable=unused-argument  # browser_path сохранён для симметрии сигнатуры диалогов
def _show_browser_already_running_with_proxy_dialog(
    callbacks: dict,
    browser_path: str,
) -> bool:
    """
    Показывает диалог о том, что браузер уже запущен через FlowLink Proxy.

    Вызывается при нажатии «Запустить браузер», когда браузер уже работает
    через прокси (с флагом --proxy-server). Повторный запуск не требуется,
    но пользователю предлагается перезапустить браузер, если это нужно.

    Диалог возвращает только выбор пользователя; сам перезапуск (kill +
    launch) выполняется вызывающим кодом в фоновом потоке, чтобы не
    блокировать mainloop tkinter.

    Args:
        callbacks: Словарь коллбэков трея (используется tk_root).
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        True если пользователь выбрал «Перезапустить браузер»,
        False при отмене, ошибке или недоступности tkinter.
    """
    message = _(
        'Браузер уже запущен через FlowLink Proxy и работает через прокси. '
        'Повторный запуск не требуется.\n\n'
        'Если вы хотите перезапустить браузер (например, после изменения '
        'настроек), нажмите «Перезапустить браузер». Закрытие браузера '
        'может прервать незавершённые действия (скачивание файлов, '
        'обновления и т.п.) — дождитесь их завершения.\n\n'
        'Внимание: будут закрыты все процессы выбранного браузера. '
        'Если запущено несколько профилей или окон — все они будут закрыты.'
    )

    return _show_browser_choice_dialog(
        callbacks,
        title=_('Браузер уже запущен'),
        message=message,
        primary_text=_('Перезапустить браузер'),
        secondary_text=_('Не перезапускать'),
    )


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
    if result == 'already_running_with_proxy':
        # Браузер уже работает через FlowLink Proxy. Оповещаем и при
        # необходимости перезапускаем синхронно (fallback без трея).
        if _show_browser_already_running_with_proxy_dialog(
            callbacks, browser_path,
        ):
            return _restart_browser_sync(browser_path, proxy_port)
        return True
    return bool(result)


def _restart_browser_kill_launch(browser_path: str, proxy_port: int) -> bool:
    """
    Завершает процессы браузера и запускает его заново через FlowLink Proxy.

    Единый блок «kill → пауза → launch → проверка already_running»,
    используемый и синхронным _restart_browser_sync, и фоновым
    перезапуском (_browser_worker с restart=True). Возвращает True при
    успешном перезапуске, False при ошибке или если браузер всё ещё
    запущен после завершения процессов.

    Args:
        browser_path: Путь к исполняемому файлу браузера.
        proxy_port: Порт HTTP-прокси.

    Returns:
        True если браузер успешно перезапущен, False при ошибке.
    """
    # Ленивый импорт: модуль browser_process подключается только
    # при необходимости перезапуска браузера
    from server.config import \
        browser_process as _browser_process  # pylint: disable=import-outside-toplevel

    if not _browser_process.kill_browser_processes(browser_path):
        logger.error(
            'Не удалось завершить процессы браузера: %s',
            browser_path,
        )
        return False
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
        return False
    return bool(second_result)


def _restart_browser_sync(browser_path: str, proxy_port: int) -> bool:
    """
    Синхронно перезапускает браузер через FlowLink Proxy.

    Используется в fallback-ветке без трея, где нет фонового потока.
    Блокирует вызывающий поток на время перезапуска.

    Args:
        browser_path: Путь к исполняемому файлу браузера.
        proxy_port: Порт HTTP-прокси.

    Returns:
        True если браузер успешно перезапущен, False при ошибке.
    """
    return _restart_browser_kill_launch(browser_path, proxy_port)


def _launch_browser_callback(  # pylint: disable=too-many-statements  # запуск браузера + диалог + фоновый перезапуск
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
        logger.debug('tkinter недоступен — переход на синхронный запуск браузера')
        return _launch_browser_sync(callbacks, browser_path, proxy_port)

    result: dict = {'value': None, 'error': None}
    done_var = tk.BooleanVar(tk_root)

    def _on_done() -> None:
        """
        Обрабатывает результат фонового запуска в mainloop-потоке.

        Вызывается через tk_root.after(0, ...) — все операции с tk
        выполняются только здесь (не в фоновом потоке).
        """
        started_restart = False
        try:
            if result['error'] is not None:
                logger.error(
                    'Ошибка запуска браузера %s: %s',
                    browser_path, result['error'],
                )
            elif result['value'] == 'already_running':
                # Диалог выполняется в mainloop-потоке: wait_window внутри
                # show_info запускает вложенный цикл событий, что безопасно.
                # Функция возвращает только выбор пользователя; сам
                # перезапуск (kill + launch) выполняется в фоновом потоке
                # _browser_worker(restart=True), чтобы не блокировать mainloop.
                if _show_browser_already_running_dialog(
                    callbacks, browser_path, proxy_port,
                ):
                    started_restart = True
                    _start_restart_worker()
                    return
                result['value'] = False
            elif result['value'] == 'already_running_with_proxy':
                # Браузер уже работает через FlowLink Proxy. Оповещаем
                # пользователя и предлагаем перезапустить его, если нужно.
                if _show_browser_already_running_with_proxy_dialog(
                    callbacks, browser_path,
                ):
                    started_restart = True
                    _start_restart_worker()
                    return
                result['value'] = True
        finally:
            # Если запущен фоновый перезапуск — не закрываем wait_variable
            # и не прячем статусбар: done_var будет выставлен вторым
            # _on_done после завершения _browser_worker.
            if not started_restart:
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

    def _schedule_on_done() -> None:
        """Планирует _on_done в mainloop-потоке из фонового потока.

        При недоступности tk (окно закрыто) разблокирует wait_variable
        напрямую, чтобы вызывающий код не завис навсегда.
        """
        try:
            tk_root.after(0, _on_done)
        except (tk.TclError, RuntimeError) as e:
            logger.error(
                'Не удалось запланировать обработку результата: %s', e,
            )
            try:
                done_var.set(True)
            except tk.TclError:
                logger.debug(
                    'Не удалось разблокировать wait_variable после '
                    'ошибки планирования',
                )

    def _start_restart_worker() -> None:
        """
        Запускает перезапуск браузера в фоновом потоке.

        Завершает процессы браузера и запускает его заново через
        FlowLink Proxy. Выполняется в отдельном потоке, чтобы
        блокирующие вызовы (taskkill, time.sleep) не замораживали
        mainloop tkinter. По завершении планирует _on_done через
        tk_root.after(0, ...).
        """
        try:
            popup.show_loading('Перезапуск браузера...')
        except (tk.TclError, RuntimeError) as e:
            logger.debug('Не удалось показать статусбар загрузки: %s', e)

        thread = threading.Thread(
            target=_browser_worker, args=(True,), daemon=True,
        )
        thread.start()

    def _browser_worker(restart: bool = False) -> None:
        """
        Фоновый поток: запускает или перезапускает браузер.

        При restart=True сначала завершает процессы браузера (kill) и
        запускает заново (общий блок _restart_browser_kill_launch).
        Результат сохраняется в общий словарь, а завершение планируется
        через tk_root.after(0, _on_done) — потокобезопасно в tkinter.
        """
        try:
            if restart:
                result['value'] = _restart_browser_kill_launch(
                    browser_path, proxy_port,
                )
            else:
                result['value'] = _browser_config.launch_browser(
                    browser_path, proxy_port=proxy_port,
                )
        except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: лог ошибки
            # Логируем в файл — иначе ошибка видна только в диалоге
            logger.error(
                'Ошибка %s браузера %s: %s',
                'перезапуска' if restart else 'запуска',
                browser_path, e, exc_info=True,
            )
            result['error'] = e
        finally:
            _schedule_on_done()

    try:
        popup.show_loading('Запуск браузера...')
    except (tk.TclError, RuntimeError) as e:
        logger.debug('Не удалось показать статусбар загрузки: %s', e)

    thread = threading.Thread(target=_browser_worker, daemon=True)
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

    # Ленивый импорт: модуль browser_process подключается только при необходимости
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
            logger.debug('Loop уже закрыт при остановке сервера')

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

    return _try_start_tray(callbacks), callbacks


def _try_start_tray(callbacks: dict):
    """
    Запуск start_tray с обработкой ошибок.

    Цепочка отказоустойчивости:
    1. Основной трей (платформенный бэкенд, start_tray).
    2. Если основной вернул None или бросил исключение — _handle_tray_error
       (critical + sys.exit(1) в standalone, warning в исходниках).

    tkinter обязателен для трея и диалогов бэкенда, поэтому отдельный
    fallback-бэкенд без tkinter не предусмотрен.
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
            callbacks,
        )
    # Последний рубеж: любой сбой бэкенда не должен уронить процесс.
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

    # Шаг 2: трей недоступен
    _handle_tray_error(
        RuntimeError('Системный трей недоступен'),
        'запуск',
    )
    return None


def _setup_signal_handlers(loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event) -> None:
    """Регистрирует обработчики сигналов SIGINT и SIGTERM."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _on_signal(s, stop_event))
        except NotImplementedError:
            logger.debug(
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
# Минимальный интервал между повторными уведомлениями об обрыве SSE
_EXTENSION_NOTIFY_INTERVAL = 600


def _show_extension_notification(server_dir: str, callbacks: dict) -> None:
    """
    Показывает уведомление о неподключённом расширении в отдельном потоке.

    Если трей запущен и tk_root доступен — диалог привязывается к нему
    (не создаётся второй Tk() в потоке). Иначе создаётся отдельный root.
    При отказе tkinter открывает инструкцию в браузере: локальный help.html
    или .md-инструкцию на GitHub (для пользователей в РФ — предупреждение
    о необходимости VPN/прокси для доступа к GitHub).

    Args:
        server_dir: Директория server/ (для поиска help.html).
        callbacks: Словарь коллбэков трея (tk_root для привязки диалога).
    """
    help_path = os.path.join(server_dir, '..', 'extension', 'popup', 'help.html')
    help_path = os.path.normpath(help_path)

    # Ссылка на .md файл с инструкцией на GitHub (для РФ — предупреждение о VPN)
    github_md_url = (
        'https://github.com/FlowHack/flowlink-proxy/blob/main/SETUP.md'
    )

    def _open_help() -> None:
        """Открывает локальную справку или GitHub-инструкцию в браузере."""
        if os.path.isfile(help_path):
            webbrowser.open(f'file://{os.path.abspath(help_path)}')
        else:
            webbrowser.open(github_md_url)

    def _show_notification() -> None:
        """Показывает уведомление в отдельном потоке (tkinter или webbrowser)."""
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
                _open_help()
        except Exception as e:  # pylint: disable=broad-exception-caught  # последний рубеж: лог ошибки
            # tkinter может упасть (TclError, RuntimeError) в потоке —
            # не роняем daemon-поток, а открываем инструкцию в браузере.
            logger.warning('Не удалось показать диалог уведомления (%s), '
                           'открываю инструкцию в браузере', e)
            _open_help()

    thread = threading.Thread(target=_show_notification, daemon=True)
    thread.start()


async def _watch_api_connection(
    server_dir: str,
    callbacks: dict,
    monitor_after_connect: bool = False,
) -> None:
    """
    Следит за подключением расширения к API-серверу.

    Если за 2 минуты расширение не установило SSE-соединение —
    показывает пользователю уведомление с инструкцией по установке.
    Состояние подключения отслеживается через extension_connection
    (активные SSE-соединения от расширения к /api/events).

    При monitor_after_connect=True продолжает мониторинг после первого
    подключения: при обрыве SSE (бэкенд жив, расширение отключилось)
    уведомление показывается повторно, но не чаще одного раза в
    _EXTENSION_NOTIFY_INTERVAL секунд.

    Args:
        server_dir: Директория server/ (для поиска help.html).
        callbacks: Словарь коллбэков трея (tk_root для привязки диалога).
        monitor_after_connect: Если True — не завершаться после первого
            подключения, а продолжать следить за обрывами соединения.
    """
    logger.debug('Ожидание подключения расширения (%d сек)...',
                 _EXTENSION_CONNECT_TIMEOUT)

    # None — уведомление ещё не показывалось (первый обрыв срабатывает сразу)
    notified_at: float | None = None
    connected_ever = False

    # Первичное ожидание: даём расширению время на подключение при старте
    for elapsed in range(0, _EXTENSION_CONNECT_TIMEOUT, _EXTENSION_CHECK_INTERVAL):
        await asyncio.sleep(_EXTENSION_CHECK_INTERVAL)
        if is_extension_connected():
            connected_ever = True
            logger.debug(
                'Расширение подключено (прошло %d сек)',
                elapsed + _EXTENSION_CHECK_INTERVAL,
            )
            break
    else:
        # 2 минуты прошли, расширение не подключилось
        logger.warning('Расширение не подключено к API-серверу за %d секунд',
                       _EXTENSION_CONNECT_TIMEOUT)
        _show_extension_notification(server_dir, callbacks)
        notified_at = asyncio.get_running_loop().time()

    # Без мониторинга завершаемся после первичной проверки
    if not monitor_after_connect:
        return

    # Дальнейший мониторинг: уведомляем при обрыве SSE-соединения,
    # но не чаще одного раза в _EXTENSION_NOTIFY_INTERVAL секунд
    while True:
        await asyncio.sleep(_EXTENSION_CHECK_INTERVAL)
        if is_extension_connected():
            connected_ever = True
            # Сбрасываем троттлинг: первый обрыв после (повторного)
            # подключения должен уведомить сразу
            notified_at = None
            continue
        if not connected_ever:
            # Расширение так и не подключалось — начальное уведомление
            # уже показано, повторно не спамим
            continue
        # Был обрыв после успешного подключения
        now = asyncio.get_running_loop().time()
        if notified_at is None or now - notified_at >= _EXTENSION_NOTIFY_INTERVAL:
            logger.warning('Обнаружен обрыв SSE-соединения расширения')
            _show_extension_notification(server_dir, callbacks)
            notified_at = now


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
    # Восстанавливаем последний активный прокси перед инициализацией роутера,
    # чтобы _rebuild сразу собрал корректные правила маршрутизации.
    _restore_last_active_proxy()

    try:
        router = MaskRouter()
    except RuntimeError as e:
        logger.error('Ошибка инициализации маршрутизатора: %s', e)
        return

    if args.debug:
        log_config_state(is_startup=True)

    # Токен аутентификации API: генерируется при каждом старте сервера.
    # Никогда не логируется — только расширение получает его через
    # открытый маршрут GET /api/bootstrap.
    auth_token = secrets.token_urlsafe(32)

    proxy_server = ProxyServer(router, port=args.proxy_port)
    api_server = ApiServer(
        router, port=args.api_port,
        debug=args.debug, need_update=args.need_update,
        auth_token=auth_token,
    )

    try:
        await asyncio.gather(
            proxy_server.start(),
            api_server.start(),
        )
        logger.info('Прокси-сервер слушает 127.0.0.1:%d', args.proxy_port)
        logger.info('API-сервер слушает 127.0.0.1:%d', args.api_port)
    except OSError as e:
        # Останавливаем уже запущенные серверы при ошибке
        try:
            await proxy_server.stop()
        except Exception as exc:  # pylint: disable=broad-exception-caught  # при откате останавливаем серверы при любой ошибке
            logger.debug('Ошибка остановки прокси-сервера: %s', exc)
        try:
            await api_server.stop()
        except Exception as exc:  # pylint: disable=broad-exception-caught  # при откате останавливаем серверы при любой ошибке
            logger.debug('Ошибка остановки API-сервера: %s', exc)
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

    # Уведомляем расширение о готовности бэкенда (после перезапуска).
    # Расширение может переподключиться к SSE и перечитать конфиг.
    asyncio.create_task(emit_event('backend_ready', {'apiPort': args.api_port}))

    # Словарь callbacks создаётся заранее и передаётся в _watch_api_connection,
    # чтобы уведомление могло привязаться к tk_root трея (заполняется позже).
    callbacks = {}
    asyncio.create_task(_watch_api_connection(
        os.path.dirname(os.path.abspath(__file__)),
        callbacks,
        # Мониторинг продолжается и после подключения: при обрыве SSE
        # расширения пользователь получает повторное уведомление
        monitor_after_connect=True,
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
    init_i18n()
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

    if args.count_proxy > 0:
        fake_data = generate_fake_proxies(args.count_proxy)
        cfg.inject_proxies(fake_data)

    await _run_server(args)


def _restore_last_active_proxy() -> None:
    """Восстанавливает последний активный прокси при запуске.

    Логика:
      1. Читаем lastActiveProxyId из конфига.
      2. Если прокси существует — включаем его, остальные выключаем.
      3. Если lastActiveProxyId отсутствует или прокси не найден —
         ничего не делаем (состояние включённости берётся из config.json).

    Восстановление выполняется до инициализации MaskRouter, чтобы
    _rebuild сразу собрал корректные правила маршрутизации.
    """
    try:
        config_data = cfg.load_config(force=True)
    except (OSError, RuntimeError) as e:
        logger.warning('Не удалось загрузить конфиг для восстановления: %s', e)
        return

    proxies = config_data.get('proxies', [])
    if not proxies:
        return

    last_active_id = cfg.get_last_active_proxy()
    if not last_active_id:
        # Нет последнего активного прокси (все выключены или включено
        # несколько неконфликтующих) — оставляем состояние как есть.
        return

    # Проверяем, существует ли прокси.
    target_exists = any(p.get('proxyId') == last_active_id for p in proxies)
    if not target_exists:
        logger.info(
            'Последний активный прокси %s не найден, состояние не меняется',
            last_active_id,
        )
        return

    # Включаем целевой прокси, остальные выключаем.
    changed = False
    for proxy in proxies:
        pid = proxy.get('proxyId')
        if not pid:
            continue
        should_enable = pid == last_active_id
        if proxy.get('isEnabled', True) != should_enable:
            proxy['isEnabled'] = should_enable
            changed = True

    if changed:
        try:
            cfg.save_config(config_data)
            logger.info(
                'Восстановлен активный прокси: %s',
                last_active_id,
            )
        except (OSError, RuntimeError) as e:
            logger.warning('Не удалось сохранить восстановленный конфиг: %s', e)


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
