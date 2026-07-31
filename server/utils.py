"""
Общие утилиты FlowLink Proxy.

Единственная ответственность: вспомогательные функции общего назначения.
"""

import json
import logging
import os
import shutil
import sys

logger = logging.getLogger('flowlink.utils')

# Имя файла для хранения фактического порта API-сервера.
# Используется для отладки, логов и внешних инструментов.
_PORT_FILENAME = '.flowlink-port'

# Диапазон допустимых портов TCP
_PORT_MIN = 1
_PORT_MAX = 65535


def get_extension_dir() -> str | None:
    """
    Возвращает путь к распакованной папке расширения FlowLink Proxy.

    Папка `extension/` лежит в корне проекта рядом с `server/`. Путь
    вычисляется через __file__ (utils.py находится в server/), поэтому
    работает и при запуске из исходников, и в PyInstaller-сборке
    (при условии добавления папки через --add-data).

    Returns:
        Путь к папке расширения или None, если manifest.json не найден.
    """
    ext_dir = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..',
        'extension',
    ))
    if os.path.isfile(os.path.join(ext_dir, 'manifest.json')):
        logger.debug('Найдена папка распакованного расширения: %s', ext_dir)
        return ext_dir
    return None


def ensure_extension_dir() -> str | None:
    """
    Обеспечивает стабильную копию распакованного расширения в data-директории.

    В PyInstaller-сборке папка расширения лежит во временной директории
    sys._MEIPASS (путь вида _MEI*), которая исчезает после перезапуска
    приложения. Чтобы путь к расширению был стабильным и переживал
    рестарты/обновления, содержимое источника копируется в
    <data_dir>/extension.

    Returns:
        Путь к стабильной копии расширения или None, если источник
        не найден или копирование не удалось.
    """
    src = get_extension_dir()
    if not src:
        logger.debug(
            'Исходная папка расширения не найдена — стабильная копия не создана',
        )
        return None

    dst = os.path.join(get_data_dir(), 'extension')
    try:
        os.makedirs(dst, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
    except (OSError, shutil.Error) as e:
        logger.error(
            'Не удалось скопировать расширение из %s в %s: %s',
            src, dst, e,
        )
        return None

    logger.debug('Расширение скопировано из %s в %s', src, dst)
    return dst


def get_crx_path() -> str | None:
    """
    Возвращает путь к расширению FlowLink Proxy.

    Порядок поиска:
    1. Стабильная копия распакованной папки extension/ в data-директории
       (создаётся через ensure_extension_dir) — приоритетный вариант, т.к.
       флаг --load-extension в Chromium-движках принимает только
       unpacked-директорию с manifest.json (путь к .crx-файлу молча
       игнорируется браузером). Копия не зависит от временной _MEI*-папки.
    2. CRX-файл рядом с бинарником (PyInstaller — CRX добавлен через --add-data)
    3. CRX-файл в resource_dir (для отладки из исходников)
    4. CRX-файл в data_dir (пользователь скопировал вручную)

    Returns:
        Путь к распакованной папке расширения или к CRX-файлу,
        либо None, если ничего не найдено.
    """
    stable_dir = ensure_extension_dir()
    if stable_dir:
        return stable_dir

    candidates = []

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, 'flowlink-proxy.crx'))

    candidates.append(os.path.join(get_resource_dir(), 'flowlink-proxy.crx'))
    candidates.append(os.path.join(get_data_dir(), 'flowlink-proxy.crx'))

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def get_data_dir() -> str:
    """
    Возвращает базовую директорию для хранения данных приложения.

    Все данные (config.json, ключи, логи, настройки) хранятся в одной
    стандартной директории данных пользователя — независимо от того,
    запущен ли сервер из исходников, standalone-бинарника или systemd.

    Приоритет (от высшего к низшему):
    1. Переменная окружения FLOWLINK_DATA_DIR (для systemd-сервиса и кастомных путей)
    2. Стандартная директория данных ОС:
       - Linux/macOS: ~/.FlowHack/FlowLink Proxy
       - Windows: %APPDATA%\\FlowHack\\FlowLink Proxy

    Гарантия: возвращаемая директория существует (создаётся при первом вызове).
    """
    env_dir = os.environ.get('FLOWLINK_DATA_DIR')
    if env_dir:
        data_dir = os.path.abspath(env_dir)
    elif sys.platform == 'win32':
        appdata = os.environ.get('APPDATA')
        if appdata:
            data_dir = os.path.join(appdata, 'FlowHack', 'FlowLink Proxy')
        else:
            data_dir = os.path.join(
                os.path.expanduser('~'), '.FlowHack', 'FlowLink Proxy',
            )
    else:
        data_dir = os.path.join(
            os.path.expanduser('~'), '.FlowHack', 'FlowLink Proxy',
        )

    # Создаём директорию, если она ещё не существует (exist_ok)
    try:
        os.makedirs(data_dir, exist_ok=True)
    except OSError as e:
        logger.error('Не удалось создать директорию данных %s: %s', data_dir, e)
        raise

    return data_dir


# Файлы данных, которые удаляются при очистке
_DATA_FILES = [
    'config.json',
    '.flowlink.key',
    '.flowlink.salt',
    '.flowlink-settings',
    '.flowlink-port',
]


def clear_all_data() -> int:
    """
    Удаляет все файлы данных приложения из data-директории.

    Удаляет:
    - config.json (конфигурация прокси и масок)
    - .flowlink.key (мастер-ключ AES-GCM)
    - .flowlink.salt (соль PBKDF2)
    - .flowlink-settings (настройки автозапуска)
    - .flowlink-port (порты API/прокси)
    - logs/ (директория с логами, целиком)

    Не удаляет саму data-директорию — она пересоздаётся автоматически.

    Returns:
        Количество удалённых файлов/директорий.
    """
    data_dir = get_data_dir()
    removed = 0

    # Удаляем файлы данных
    for filename in _DATA_FILES:
        filepath = os.path.join(data_dir, filename)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                removed += 1
                logger.info('Удалён файл данных: %s', filepath)
            except OSError as e:
                logger.error('Не удалось удалить %s: %s', filepath, e)

    # Переоткрываем логгер, чтобы освободить файловый дескриптор
    # Ленивый импорт для избежания циклической зависимости
    from server.logging_config import reopen_logging  # pylint: disable=import-outside-toplevel
    reopen_logging()

    # Удаляем директорию логов целиком
    logs_dir = os.path.join(data_dir, 'logs')
    if os.path.isdir(logs_dir):
        try:
            shutil.rmtree(logs_dir)
            removed += 1
            logger.info('Удалена директория логов: %s', logs_dir)
        except OSError as e:
            logger.error('Не удалось удалить %s: %s', logs_dir, e)

    # Пересоздаём пустую директорию логов (logging может писать в неё)
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except OSError as e:
        logger.error('Не удалось пересоздать %s: %s', logs_dir, e)

    logger.info('Очистка данных завершена: удалено %d элементов', removed)
    return removed


def clear_logs_only() -> int:
    """
    Удаляет только директорию логов из data-директории.

    Не удаляет конфиги, ключи или настройки — только logs/.

    Returns:
        Количество удалённых элементов (0 или 1).
    """
    data_dir = get_data_dir()
    logs_dir = os.path.join(data_dir, 'logs')
    removed = 0

    # Переоткрываем логгер, чтобы освободить файловый дескриптор
    # Ленивый импорт для избежания циклической зависимости
    from server.logging_config import reopen_logging  # pylint: disable=import-outside-toplevel
    reopen_logging()

    if os.path.isdir(logs_dir):
        try:
            shutil.rmtree(logs_dir)
            removed += 1
            logger.info('Удалена директория логов: %s', logs_dir)
        except OSError as e:
            logger.error('Не удалось удалить %s: %s', logs_dir, e)

    # Пересоздаём пустую директорию логов
    try:
        os.makedirs(logs_dir, exist_ok=True)
    except OSError as e:
        logger.error('Не удалось пересоздать %s: %s', logs_dir, e)

    logger.info('Очистка логов завершена: удалено %d элементов', removed)
    return removed


def clear_data_only() -> int:
    """
    Удаляет файлы данных (конфиги, ключи, настройки) без логов.

    Удаляет:
    - config.json
    - .flowlink.key
    - .flowlink.salt
    - .flowlink-settings
    - .flowlink-port

    Не удаляет logs/.

    Returns:
        Количество удалённых файлов.
    """
    data_dir = get_data_dir()
    removed = 0

    for filename in _DATA_FILES:
        filepath = os.path.join(data_dir, filename)
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)
                removed += 1
                logger.info('Удалён файл данных: %s', filepath)
            except OSError as e:
                logger.error('Не удалось удалить %s: %s', filepath, e)

    logger.info('Очистка данных завершена: удалено %d файлов', removed)
    return removed


def get_resource_dir() -> str:
    """
    Возвращает директорию ресурсов (иконки, и т.д.).

    В режиме PyInstaller (.frozen) — sys._MEIPASS (временная папка с распакованными ресурсами).
    Иначе — текущая рабочая директория.
    """
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', None) or os.path.dirname(
            os.path.abspath(sys.executable),
        )
    return os.getcwd()


def _validate_port(port: object, name: str) -> int:
    """
    Валидирует номер порта и возвращает его как int.

    Raises:
        TypeError: если port не является int.
        ValueError: если port вне диапазона 1–65535.
    """
    if not isinstance(port, int):
        raise TypeError(f'{name}: ожидался int, получен {type(port).__name__}')
    if port < _PORT_MIN or port > _PORT_MAX:
        raise ValueError(
            f'{name}: порт должен быть в диапазоне {_PORT_MIN}–{_PORT_MAX}, '
            f'получен {port}',
        )
    return port


def write_port_file(api_port: int, proxy_port: int) -> None:
    """
    Записывает фактические порты сервера в JSON-файл в data-директории.

    Файл содержит порты API и прокси-серверов — полезно для отладки,
    логов и внешних инструментов (скрипты, мониторинг).

    Формат файла (.flowlink-port):
        {"api_port": 8081, "proxy_port": 8080}

    Безопасность:
    - Валидация диапазона портов (1–65535) перед записью.
    - Файл записывается в data-директорию (не в ресурсную).
    - Не содержит секретов — только номера портов.

    Args:
        api_port: Фактический порт API-сервера (для расширения).
        proxy_port: Фактический порт прокси-сервера (для Chrome).

    Raises:
        TypeError: если порты не являются int.
        ValueError: если порты вне диапазона 1–65535.
    """
    # Валидация — ловим ошибки ДО записи в файл
    _validate_port(api_port, 'api_port')
    _validate_port(proxy_port, 'proxy_port')

    data_dir = get_data_dir()
    port_file = os.path.join(data_dir, _PORT_FILENAME)
    payload = {'api_port': api_port, 'proxy_port': proxy_port}
    try:
        with open(port_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        logger.debug(
            'Порты записаны в %s: API=%d, прокси=%d',
            port_file, api_port, proxy_port,
        )
    except OSError as e:
        # Не критично — файл для отладки, его отсутствие не влияет на работу
        logger.warning('Не удалось записать файл портов %s: %s', port_file, e)
