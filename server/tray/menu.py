"""
Общая логика построения меню и загрузки иконки для всех трей-бэкендов.

Единственная ответственность: дедупликация кода между
Linux, macOS и Win32 трей-модулями.
"""

from __future__ import annotations

import types
from typing import Any, Callable, Dict, List, Optional

import logging
import os
import webbrowser

from server.utils import get_data_dir

logger = logging.getLogger('flowlink.tray.menu')

_ICON_PATH = os.path.join('icons', 'icon.png')
_DEFAULT_ICON_SIZE = (64, 64)


def load_icon(
    pil_image: types.ModuleType,
    logger_name: str = 'flowlink.tray',
    force_fallback: bool = False,
) -> Any:
    """
    Загружает иконку трей из файла.

    Если файл иконки не найден или force_fallback=True — создаёт
    дефолтную: красный круг с «FLP» (16×16, масштабируется до 64×64).

    Args:
        pil_image: Модуль PIL.Image (передаётся вызывающим кодом).
        logger_name: Имя логгера для предупреждений.
        force_fallback: Принудительно использовать дефолтную иконку.

    Returns:
        PIL.Image (64x64 RGBA).
    """
    icon_logger = logging.getLogger(logger_name)
    # Ленивый импорт: избегает циклических зависимостей
    from server.utils import get_resource_dir  # pylint: disable=import-outside-toplevel
    icon_path = os.path.normpath(
        os.path.join(get_resource_dir(), _ICON_PATH),
    )

    if not force_fallback and os.path.exists(icon_path):
        img = pil_image.open(icon_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img.resize(_DEFAULT_ICON_SIZE, pil_image.Resampling.LANCZOS)

    if force_fallback:
        icon_logger.info(
            '%s: --test-fallback-icon, пропуск %s',
            logger_name, icon_path,
        )
    else:
        icon_logger.warning(
            '%s: иконка %s не найдена, создание дефолтной',
            logger_name, icon_path,
        )
    return _create_fallback_icon(pil_image)


def _create_fallback_icon(pil_image: types.ModuleType) -> Any:
    """
    Создаёт дефолтную иконку: красный круг с «FLP».

    Args:
        pil_image: Модуль PIL.Image.

    Returns:
        PIL.Image (16x16 RGBA, масштабируется до 64x64).
    """
    import PIL.ImageDraw as _draw  # pylint: disable=import-outside-toplevel
    import PIL.ImageFont as _font  # pylint: disable=import-outside-toplevel

    size = 16
    img = pil_image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = _draw.Draw(img)

    draw.ellipse([1, 1, size - 2, size - 2], fill=(231, 76, 60, 255))

    try:
        font = _font.truetype('arial.ttf', 7)
    except OSError:
        try:
            font = _font.truetype(
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 7,
            )
        except OSError:
            font = _font.load_default()

    bbox = draw.textbbox((0, 0), 'FLP', font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - 1
    draw.text((tx, ty), 'FLP', fill=(0, 0, 0, 255), font=font)

    return img.resize(_DEFAULT_ICON_SIZE, pil_image.Resampling.LANCZOS)


def get_autostart_state(
    callbacks: Dict[str, Any],
    logger_name: str = 'flowlink.tray',
) -> bool:
    """
    Безопасно читает текущее состояние автозапуска.

    Args:
        callbacks: Словарь коллбэков (может содержать autostart_getter).
        logger_name: Имя логгера для ошибок.

    Returns:
        bool — текущее значение автозапуска (False при ошибке).
    """
    if not callbacks.get('autostart_getter'):
        return False
    try:
        return callbacks['autostart_getter']()
    except (OSError, TypeError, AttributeError) as e:
        logging.getLogger(logger_name).error(
            '%s: ошибка чтения autostart: %s', logger_name, e,
        )
        return False


def safe_open_folder(
    path: str, label: str, log: logging.Logger,
) -> None:
    """Безопасно открывает папку в файловом менеджере."""
    try:
        os.makedirs(path, exist_ok=True)
        webbrowser.open(
            f'file://{os.path.normpath(path)}',
        )
    except OSError as exc:
        log.error(
            '%s: не удалось открыть %s (%s): %s',
            'Tray', label, path, exc,
        )


def _get_system_autostart_state(
    callbacks: Dict[str, Any], logger_name: str,
) -> bool:
    """Безопасно читает текущее состояние системного автозапуска."""
    if not callbacks.get('system_autostart_getter'):
        return False
    try:
        return callbacks['system_autostart_getter']()
    except (OSError, TypeError, AttributeError) as e:
        logging.getLogger(logger_name).error(
            '%s: ошибка чтения system_autostart: %s',
            logger_name, e,
        )
        return False


# ─── Вспомогательные функции для построения меню ───


def _open_logs(
    callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """Открывает папку с логами в файловом менеджере."""
    log.info('Tray: открытие папки логов')
    if callbacks.get('log_dir_getter'):
        try:
            log_dir = callbacks['log_dir_getter']()
        except (OSError, TypeError) as exc:
            log.error(
                'Tray: log_dir_getter() ошибка: %s', exc,
            )
            return
        if log_dir:
            safe_open_folder(log_dir, 'логи', log)


def _clear_logs(
    callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """Очищает папку с логами."""
    log.info('Tray: очистка логов')
    if callbacks.get('clear_logs'):
        try:
            callbacks['clear_logs']()
        except OSError as exc:
            log.error(
                'Tray: ошибка очистки логов: %s', exc,
            )


def _open_data(
    _callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """Открывает папку с данными в файловом менеджере."""
    log.info('Tray: открытие папки данных')
    try:
        data_dir = get_data_dir()
    except OSError as exc:
        log.error(
            'Tray: get_data_dir() ошибка: %s', exc,
        )
        return
    safe_open_folder(data_dir, 'данные', log)


def _clear_data(
    callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """Очищает папку с данными."""
    log.info('Tray: очистка всех данных')
    if callbacks.get('clear_data'):
        try:
            callbacks['clear_data']()
        except OSError as exc:
            log.error(
                'Tray: ошибка очистки данных: %s', exc,
            )


def _toggle_autostart(
    callbacks: Dict[str, Any],
    log: logging.Logger,
    current_value: bool,
) -> None:
    """Переключает автозапуск браузера."""
    new_val = not current_value
    log.debug(
        'Tray: _toggle_autostart вызван, new_val=%s',
        new_val,
    )
    log.info(
        'Tray: автозапуск браузера → %s',
        'включён' if new_val else 'выключен',
    )
    if callbacks.get('autostart_setter'):
        try:
            callbacks['autostart_setter'](new_val)
        except OSError as exc:
            log.error(
                'Tray: ошибка записи autostart: %s',
                exc,
            )
    else:
        log.warning(
            'Tray: callback autostart_setter '
            'не зарегистрирован',
        )


def _toggle_system_autostart(
    callbacks: Dict[str, Any],
    log: logging.Logger,
    current_value: bool,
) -> None:
    """Переключает автозапуск с системой."""
    new_val = not current_value
    log.debug(
        'Tray: _toggle_system_autostart вызван, '
        'new_val=%s', new_val,
    )
    log.info(
        'Tray: автозапуск с системой → %s',
        'включён' if new_val else 'выключен',
    )
    if callbacks.get('system_autostart_setter'):
        try:
            callbacks['system_autostart_setter'](new_val)
        except OSError as exc:
            log.error(
                'Tray: ошибка записи system_autostart: %s',
                exc,
            )
    else:
        log.warning(
            'Tray: callback system_autostart_setter '
            'не зарегистрирован',
        )


def _toggle_ext_enabled(
    callbacks: Dict[str, Any],
    log: logging.Logger,
    current_value: bool,
) -> None:
    """
    Переключает флаг загрузки расширения при запуске браузера.

    Args:
        callbacks: Словарь коллбэков.
        log: Логгер.
        current_value: Текущее значение флага.
    """
    new_val = not current_value
    try:
        setter = callbacks.get('ext_enabled_setter')
        if setter:
            setter(new_val)
            log.info(
                'Запуск с расширением: %s',
                'включён' if new_val else 'выключен',
            )
    except OSError as e:
        log.error('Не удалось переключить загрузку расширения: %s', e)


def _select_browser(
    callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """
    Открывает диалог выбора браузера.

    Диалог show_item_picker получает parent_root=tk_root: он использует
    root трея через wait_window вместо создания второго tk.Tk().
    Создание второго Tk() в том же потоке, где уже работает mainloop
    трея, не поддерживается Tcl/Tk — mainloop возвращается сразу,
    и диалог не обрабатывается (окно 150×25 без содержимого).

    tk_root из callbacks также используется для _open_file_dialog
    (системного диалога выбора файла); если его нет — тот создаст
    свой root сам.

    Args:
        callbacks: Словарь коллбэков.
        log: Логгер.
    """
    try:
        log.debug('_select_browser: вход')
        detector = callbacks.get('browser_detector')
        detected = detector() if detector else []
        log.debug('_select_browser: обнаружено %s браузеров', len(detected))

        # Текущий путь к браузеру — для подсветки выбранного элемента.
        current_path = callbacks.get('browser_path_getter', lambda: '')()
        log.debug('_select_browser: текущий путь: %r', current_path)

        # Получаем tk_root из callbacks (передаётся из трея).
        tk_root = callbacks.get('tk_root')
        if tk_root is None:
            # Без tk_root диалог не может использовать wait_window:
            # создание второго tk.Tk() root в том же потоке, где уже
            # работает mainloop трея, не поддерживается Tcl/Tk.
            return

        if detected:
            # Используем кастомный диалог выбора из списка
            from server.ui.dialogs import show_item_picker  # pylint: disable=import-outside-toplevel

            def _on_select(item: dict) -> None:
                """Обработчик выбора браузера из списка."""
                path = item['path']
                saver = callbacks.get('browser_path_saver')
                if saver:
                    saver(path)
                    log.info('Путь браузера изменён: %s', path)

            # Строим список из найденных браузеров, помечая выбранный.
            items = [
                {
                    'label': b['name'],
                    'subtitle': b['path'],
                    'path': b['path'],
                    'selected': b['path'] == current_path,
                }
                for b in detected
            ]

            # Если текущий браузер указан вручную и не найден детектором —
            # добавляем его в конец списка как выбранный элемент.
            if current_path:
                from server.config import browser_config as _bc  # pylint: disable=import-outside-toplevel
                not_detected = all(
                    b['path'] != current_path for b in detected
                )
                if not_detected and _bc.validate_browser_path(current_path):
                    items.append({
                        'label': os.path.basename(current_path),
                        'subtitle': current_path,
                        'path': current_path,
                        'selected': True,
                    })

            # Передаём parent_root=tk_root — диалог использует root трея
            # через wait_window вместо создания второго tk.Tk() root
            # (два mainloop в одном потоке не поддерживаются Tcl/Tk).
            show_item_picker(
                title='Выбор браузера',
                message='Найденные браузеры:',
                items=items,
                on_select=_on_select,
                allow_manual=True,
                on_manual=lambda: _open_file_dialog(
                    callbacks, log, tk_root,
                ),
                parent_root=tk_root,
            )
        else:
            # Браузеры не найдены — сразу открываем диалог выбора файла
            _open_file_dialog(callbacks, log, tk_root)

    except ImportError:
        log.error('tkinter недоступен для диалога выбора файла')


def _open_file_dialog(
    callbacks: Dict[str, Any],
    log: logging.Logger,
    tk_root: Optional[Any] = None,
) -> None:
    """Открывает системный диалог выбора исполняемого файла браузера.

    Использует переданный tk_root из трея (если есть) вместо
    создания нового tk.Tk(), чтобы избежать конфликта с mainloop
    на Windows.

    Args:
        callbacks: Словарь коллбэков.
        log: Логгер.
        tk_root: Существующий tk.Tk() трея. Если None — создаётся
            новый (fallback, например из lambda в on_manual).
    """
    try:
        import tkinter as tk  # pylint: disable=import-outside-toplevel
        from tkinter import filedialog  # pylint: disable=import-outside-toplevel
        from server.ui.dialogs import _set_window_icon  # pylint: disable=import-outside-toplevel

        owns_root = tk_root is None
        root = tk_root if tk_root is not None else tk.Tk()
        if owns_root:
            root.withdraw()
            root.attributes('-topmost', True)
            _set_window_icon(root)

        path = filedialog.askopenfilename(
            title='Выберите исполняемый файл браузера',
            filetypes=[
                ('Исполняемые файлы', '*.exe *.app *.AppImage'),
                ('Все файлы', '*'),
            ],
        )
        if owns_root:
            root.destroy()

        if path:
            from server.config import browser_config as _bc  # pylint: disable=import-outside-toplevel
            validation = _bc.validate_browser_path_detailed(path)
            if validation['valid']:
                saver = callbacks.get('browser_path_saver')
                if saver:
                    saver(path)
                    log.info('Путь браузера изменён: %s', path)
            else:
                log.warning(
                    'Некорректный путь браузера: %s',
                    validation['error'],
                )
    except ImportError:
        log.error('tkinter недоступен для диалога выбора файла')


def _launch_browser_now(
    callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """
    Запускает браузер с расширением (если включено).

    Args:
        callbacks: Словарь коллбэков.
        log: Логгер.
    """
    launcher = callbacks.get('browser_launcher')
    if launcher:
        success = launcher()
        if success:
            log.info('Браузер запущен')
        else:
            log.error('Не удалось запустить браузер')
    else:
        log.warning('Функция запуска браузера не зарегистрирована')


def _exit(
    stop_fn: Callable[[], None],
    callbacks: Dict[str, Any],
    log: logging.Logger,
) -> None:
    """Выполняет выход из приложения."""
    log.info('Tray: выбран Выход')

    # Сначала останавливаем сервер, потом трей
    if callbacks.get('stop'):
        try:
            callbacks['stop']()
        except (OSError, RuntimeError) as e:
            log.error(
                'Tray: ошибка при остановке сервера: %s',
                e, exc_info=True,
            )

    try:
        stop_fn()
    except (OSError, RuntimeError) as e:
        log.error(
            'Tray: ошибка при остановке трея: %s',
            e, exc_info=True,
        )

    # Гарантированный выход, если предыдущие шаги не завершили процесс
    os._exit(0)


# ─── Фабрики замыканий ───


def _make_action(
    func: Callable[..., None],
    callbacks: Dict[str, Any],
    log: logging.Logger,
    **extra: Any,
) -> Callable[[], None]:
    """Создаёт замыкание callable→() для пункта меню."""
    def _wrapper() -> None:
        func(callbacks, log, **extra)
    return _wrapper


def build_menu_items(
    callbacks: Dict[str, Any],
    stop_fn: Callable[[], None],
    logger_name: str = 'flowlink.tray',
) -> List[Dict[str, Any]]:
    """
    Строит список пунктов меню для popup.

    Используется всеми трей-бэкендами (Linux, macOS, Win32).

    Каждый пункт меню — словарь с ключами:
      type: 'item' | 'check' | 'separator' | 'header'
      text: Отображаемый текст
      icon: Unicode-символ (опционально)
      command: Callable, вызываемый при клике
      color: Цвет текста (для 'item') или галочки (для 'check')
      tooltip: Всплывающая подсказка в статусбаре popup (опционально)

    Замыкания внутри формируются динамически и привязаны к callbacks
    на момент построения меню. Autostart читается один раз —
    popup пересоздаётся при каждом открытии.

    Args:
        callbacks: Словарь коллбэков:
            stop: Callable — остановка сервера.
            autostart_getter: Callable → bool — чтение настройки.
            autostart_setter: Callable(bool) — запись настройки.
            system_autostart_getter: Callable → bool — чтение
                системного автозапуска.
            system_autostart_setter: Callable(bool) — запись
                системного автозапуска.
            ext_enabled_getter: Callable → bool — чтение настройки расширения.
            ext_enabled_setter: Callable(bool) — запись настройки расширения.
            browser_path_getter: Callable → str — чтение пути к браузеру.
            browser_path_saver: Callable(str) — сохранение пути к браузеру.
            browser_detector: Callable → list[dict] — обнаружение браузеров.
            browser_launcher: Callable → bool — запуск браузера.
            log_dir_getter: Callable → str — путь к папке логов.
            data_dir_getter: Callable → str — путь к папке данных.
            clear_logs: Callable — очистка логов.
            clear_data: Callable — очистка данных.
        stop_fn: Callable — остановка трей-иконки (вызывается
            перед callbacks['stop'] для корректного завершения).
        logger_name: Имя логгера для сообщений об ошибках.

    Returns:
        Список словарей с описанием пунктов меню.
    """
    log = logging.getLogger(logger_name)
    autostart = get_autostart_state(callbacks, logger_name)
    sys_autostart = _get_system_autostart_state(
        callbacks, logger_name,
    )

    # Определяем, выбран ли браузер: для валидного пути показываем
    # зелёную пометку у пункта «Выбрать браузер...».
    browser_path = callbacks.get('browser_path_getter', lambda: '')()
    from server.config import browser_config as _bc  # pylint: disable=import-outside-toplevel
    browser_selected = bool(browser_path) and _bc.validate_browser_path(browser_path)

    return [
        {
            'type': 'item',
            'text': 'Посмотреть логи',
            'icon': '\U0001f4dc',
            'tooltip': 'Открыть папку с логами FlowLink Proxy',
            'command': _make_action(
                _open_logs, callbacks, log,
            ),
        },
        {
            'type': 'item',
            'text': 'Очистить логи',
            'icon': '\U0001f5d1',
            'tooltip': 'Удалить все файлы логов',
            'command': _make_action(
                _clear_logs, callbacks, log,
            ),
        },
        {
            'type': 'item',
            'text': 'Посмотреть данные',
            'icon': '\U0001f4c2',
            'tooltip': 'Открыть папку с данными (конфиг, ключи)',
            'command': _make_action(
                _open_data, callbacks, log,
            ),
        },
        {
            'type': 'item',
            'text': 'Очистить данные',
            'icon': '\u26a0\ufe0f',
            'tooltip': 'Удалить конфигурацию и все данные',
            'command': _make_action(
                _clear_data, callbacks, log,
            ),
        },
        {'type': 'separator'},
        {
            'type': 'check',
            'text': 'Автозапуск браузера',
            'icon': '\U0001f310',
            'checked': autostart,
            'tooltip': 'Запускать браузер автоматически при старте системы',
            'command': _make_action(
                _toggle_autostart, callbacks, log,
                current_value=autostart,
            ),
        },
        {
            'type': 'check',
            'text': 'Запуск с системой',
            'icon': '\U0001f50a',
            'checked': sys_autostart,
            'tooltip': 'Автозапуск FlowLink Proxy вместе с системой',
            'command': _make_action(
                _toggle_system_autostart,
                callbacks, log,
                current_value=sys_autostart,
            ),
        },
        {'type': 'separator'},
        {
            'type': 'check',
            'text': 'Запуск с расширением',
            'icon': '\U0001f4e6',
            'checked': callbacks.get('ext_enabled_getter', lambda: False)(),
            'tooltip': 'Запускать браузер с автоматическим подключением расширения',
            'command': _make_action(
                _toggle_ext_enabled, callbacks, log,
                current_value=callbacks.get(
                    'ext_enabled_getter', lambda: False,
                )(),
            ),
        },
        {
            'type': 'item',
            'text': (
                'Выбрать браузер... ✓' if browser_selected
                else 'Выбрать браузер...'
            ),
            'icon': '\U0001f4c1',
            'color': '#2ecc71' if browser_selected else None,
            'tooltip': 'Указать, какой браузер использовать',
            'command': _make_action(
                _select_browser, callbacks, log,
            ),
        },
        {
            'type': 'item',
            'text': 'Запустить браузер',
            'icon': '\U0001f310',
            'tooltip': 'Запустить выбранный браузер сейчас',
            'command': _make_action(
                _launch_browser_now, callbacks, log,
            ),
        },
        {'type': 'separator'},
        {
            'type': 'item',
            'text': 'Выход',
            'icon': '\u274c',
            'color': '#e74c3c',
            'tooltip': 'Завершить работу FlowLink Proxy',
            'command': lambda: _exit(
                stop_fn, callbacks, log,
            ),
        },
    ]
