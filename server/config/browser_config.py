"""
Конфигурация и автозапуск браузера FlowLink Proxy.

Единственная ответственность: автопоиск браузеров, валидация путей,
запуск браузера с --proxy-server, чтение/запись browser_path.
"""

import logging
import os
import subprocess
import sys

from server.config import autostart as _autostart_mod
from server.config.browser_process import (
    is_browser_running,
    is_browser_running_with_proxy,
)

logger = logging.getLogger('flowlink.browser')

_KEY_BROWSER_PATH = 'browser_path'
_KEY_PARALLEL_LAUNCH = 'parallel_launch'
_KEY_CLOSE_BROWSER_WITH_APP = 'close_browser_with_app'

# Расширения файлов, которые НЕ являются исполняемыми браузерами
_NON_EXECUTABLE_EXTENSIONS = frozenset({
    '.txt', '.log', '.cfg', '.ini', '.conf', '.json', '.xml',
    '.yaml', '.yml', '.toml',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.mp3', '.mp4', '.avi', '.mkv', '.wav', '.flac',
    '.py', '.js', '.sh', '.bash', '.zsh', '.bat', '.cmd', '.ps1',
    '.html', '.css', '.htm', '.mht',
    '.csv', '.tsv', '.sql', '.db', '.sqlite',
    '.rtf', '.odt', '.ods', '.odp',
})


def auto_detect_browsers() -> list[dict]:
    """
    Автоматически обнаруживает установленные браузеры.

    Returns:
        Список словарей {name, path}, отсортированный по приоритету.
    """
    candidates = []

    if sys.platform == 'win32':
        candidates = _detect_windows()
    elif sys.platform == 'darwin':
        candidates = _detect_macos()
    else:
        candidates = _detect_linux()

    found = []
    for name, path in candidates:
        if os.path.isfile(path):
            found.append({'name': name, 'path': path})
            logger.debug('Обнаружен браузер: %s (%s)', name, path)

    logger.info('Обнаружено браузеров: %d', len(found))
    return found


def _detect_windows() -> list[tuple[str, str]]:
    """Обнаруживает браузеры в стандартных путях Windows."""
    candidates = []
    try:
        # winreg доступен только на Windows
        import winreg  # pylint: disable=import-outside-toplevel
        # type: ignore[reportAttributeAccessIssue] — модуль winreg доступен только
        # на Windows; pyright не видит его атрибуты (модуль не установлен в dev-среде).
        reg_paths = [
            (winreg.HKEY_CURRENT_USER,  # type: ignore[reportAttributeAccessIssue]
             r'Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'),
            (winreg.HKEY_LOCAL_MACHINE,  # type: ignore[reportAttributeAccessIssue]
             r'Software\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe'),
        ]
        for root, subpath in reg_paths:
            try:
                with winreg.OpenKey(  # type: ignore[reportAttributeAccessIssue]
                    root, subpath,
                ) as key:
                    val, _ = winreg.QueryValueEx(  # type: ignore[reportAttributeAccessIssue]
                        key, '',
                    )
                    if val and os.path.isfile(val):
                        name = 'Chrome' if 'chrome' in val.lower() else 'Edge'
                        candidates.append((name, val))
            except OSError as e:
                logger.debug('Не удалось прочитать реестр Windows: %s', e)
    except ImportError:
        # Модуль winreg недоступен (не Windows) — пропускаем поиск в реестре
        logger.debug('winreg недоступен, поиск браузера в реестре пропущен')

    local = os.environ.get('LOCALAPPDATA', '')
    pf = os.environ.get('PROGRAMFILES', '')
    pf86 = os.environ.get('PROGRAMFILES(X86)', '')

    standard = [
        ('Яндекс Браузер', os.path.join(pf, r'Yandex\YandexBrowser\Application\browser.exe')),
        ('Яндекс Браузер (x86)', os.path.join(
            pf86, r'Yandex\YandexBrowser\Application\browser.exe')),
        ('Google Chrome', os.path.join(pf, r'Google\Chrome\Application\chrome.exe')),
        ('Google Chrome (x86)', os.path.join(pf86, r'Google\Chrome\Application\chrome.exe')),
        ('Microsoft Edge', os.path.join(pf, r'Microsoft\Edge\Application\msedge.exe')),
        ('Microsoft Edge (x86)', os.path.join(pf86, r'Microsoft\Edge\Application\msedge.exe')),
        ('Mozilla Firefox', os.path.join(pf, r'Mozilla Firefox\firefox.exe')),
        ('Mozilla Firefox (x86)', os.path.join(pf86, r'Mozilla Firefox\firefox.exe')),
        ('Opera', os.path.join(local, r'Programs\Opera\opera.exe')),
        ('Brave', os.path.join(pf, r'BraveSoftware\Brave-Browser\Application\brave.exe')),
    ]

    seen = {c[1].lower() for c in candidates}
    for name, path in standard:
        if path.lower() not in seen and os.path.isfile(path):
            candidates.append((name, path))
            seen.add(path.lower())

    return candidates


def _detect_linux() -> list[tuple[str, str]]:
    """Обнаруживает браузеры через which и стандартные пути."""
    candidates = []
    names = {
        'google-chrome': 'Google Chrome',
        'google-chrome-stable': 'Google Chrome',
        'chromium-browser': 'Chromium',
        'chromium': 'Chromium',
        'firefox': 'Mozilla Firefox',
        'yandex-browser': 'Яндекс Браузер',
        'yandex-browser-stable': 'Яндекс Браузер',
        'opera': 'Opera',
        'brave-browser': 'Brave',
        'microsoft-edge-stable': 'Microsoft Edge',
    }

    seen = set()
    for cmd, name in names.items():
        if cmd in seen:
            continue
        try:
            result = subprocess.run(
                ['which', cmd], capture_output=True, text=True,
                timeout=5, check=False,
            )
            if not result.returncode and result.stdout.strip():
                path = result.stdout.strip()
                if os.path.isfile(path):
                    candidates.append((name, path))
                    seen.add(cmd)
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.debug('Не удалось найти команду %s: %s', cmd, e)

    return candidates


def _detect_macos() -> list[tuple[str, str]]:
    """Обнаруживает браузеры в стандартных путях macOS."""
    apps = '/Applications'
    candidates = [
        ('Google Chrome', os.path.join(apps, 'Google Chrome.app/Contents/MacOS/Google Chrome')),
        ('Yandex Браузер', os.path.join(apps, 'Yandex.app/Contents/MacOS/Yandex')),
        ('Mozilla Firefox', os.path.join(apps, 'Firefox.app/Contents/MacOS/firefox')),
        ('Microsoft Edge', os.path.join(apps, 'Microsoft Edge.app/Contents/MacOS/Microsoft Edge')),
        ('Opera', os.path.join(apps, 'Opera.app/Contents/MacOS/Opera')),
        ('Brave', os.path.join(apps, 'Brave Browser.app/Contents/MacOS/Brave Browser')),
        ('Safari', os.path.join(apps, 'Safari.app/Contents/MacOS/Safari')),
    ]
    return candidates


def validate_browser_path(path: str) -> bool:
    """
    Проверяет, существует ли файл по указанному пути.

    Args:
        path: Путь к исполняемому файлу браузера.

    Returns:
        True если файл существует и доступен.
    """
    if not path or not path.strip():
        return False
    return os.path.isfile(path)


def validate_browser_path_detailed(path: str) -> dict:
    """
    Расширенная валидация пути к браузеру.

    Проверяет:
      - Путь не пуст
      - Файл существует
      - Путь ведёт к файлу (не к директории)
      - Файл не является текстом/изображением/архивом по расширению
      - Файл исполняемый (Linux/macOS: X_OK, Windows: пропуск)

    Args:
        path: Путь к исполняемому файлу браузера.

    Returns:
        Словарь {valid: bool, error: str|None, warnings: list[str]}.
    """
    warnings: list[str] = []

    if not path or not path.strip():
        return {'valid': False, 'error': 'Путь не может быть пустым', 'warnings': []}

    path = path.strip()
    error = _check_path_exists(path)
    if error:
        return {'valid': False, 'error': error, 'warnings': []}

    # Проверка расширения — не похоже на браузер (до X_OK, т.к. быстрее)
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in _NON_EXECUTABLE_EXTENSIONS:
        return {
            'valid': False,
            'error': f'Файл с расширением «{ext}» не является исполняемым файлом браузера',
            'warnings': [],
        }

    # Проверка исполняемости (Linux/macOS)
    if sys.platform != 'win32' and not os.access(path, os.X_OK):
        return {
            'valid': False,
            'error': 'Файл не является исполняемым',
            'warnings': [],
        }

    # Предупреждение для .desktop файлов (Linux)
    if path.endswith('.desktop'):
        warnings.append(
            'Файл .desktop является ярлыком. '
            'Укажите путь к исполняемому файлу напрямую.',
        )

    return {'valid': True, 'error': None, 'warnings': warnings}


def _check_path_exists(path: str) -> str | None:
    """
    Проверяет существование и тип по указанному пути.

    Args:
        path: Путь к файлу.

    Returns:
        Текст ошибки или None если всё в порядке.
    """
    if not os.path.exists(path):
        return 'Файл не найден'
    if os.path.isdir(path):
        return 'Указан путь к директории, а не к файлу браузера'
    if not os.path.isfile(path):
        return 'Путь не ведёт к обычному файлу'
    return None


def launch_browser(
    browser_path: str,
    proxy_port: int = 8080,
) -> bool | str:
    """
    Запускает выбранный браузер с флагом --proxy-server.

    Браузер запускается как обычно, с профилем пользователя, но с
    добавленным флагом --proxy-server, направляющим трафик через
    локальный прокси FlowLink Proxy.

    Chrome/Chromium игнорирует флаг --proxy-server, если процесс браузера
    уже запущен, поэтому перед запуском выполняется проверка запущенных
    процессов. Если браузер уже запущен с нужным флагом --proxy-server —
    повторный запуск не требуется, возвращается True. Если браузер запущен
    без прокси — возвращается 'already_running', чтобы вызывающий код
    предложил перезапустить его через FlowLink Proxy.

    Args:
        browser_path: Путь к исполняемому файлу браузера.
        proxy_port: Порт HTTP-прокси (по умолчанию 8080).

    Returns:
        True если браузер успешно запущен,
        'already_running_with_proxy' если браузер уже запущен через
            FlowLink Proxy (повторный запуск не требуется),
        'already_running' если процесс браузера уже запущен без прокси,
        False при ошибке.
    """
    if not validate_browser_path(browser_path):
        logger.warning(
            'Невалидный путь к браузеру: %s. Браузер не запущен.',
            browser_path,
        )
        return False

    # Если браузер уже запущен через FlowLink Proxy (с нужным флагом
    # --proxy-server) — повторный запуск не требуется. Возвращаем
    # специальное значение, чтобы вызывающий код мог оповестить
    # пользователя и предложить перезапуск.
    if is_browser_running_with_proxy(browser_path, proxy_port):
        logger.info(
            'Браузер уже запущен через FlowLink Proxy: %s. '
            'Повторный запуск не требуется.',
            browser_path,
        )
        return 'already_running_with_proxy'

    # Проверка запущенных процессов: Chrome/Chromium игнорирует
    # --proxy-server, если браузер уже запущен без прокси
    if is_browser_running(browser_path):
        logger.warning(
            'Браузер уже запущен без прокси: %s. Запуск через FlowLink '
            'Proxy не выполнен, флаг --proxy-server был бы проигнорирован.',
            browser_path,
        )
        return 'already_running'

    proxy_arg = f'--proxy-server=127.0.0.1:{proxy_port}'

    args = [
        browser_path,
        proxy_arg,
    ]

    try:
        kwargs: dict = {
            'args': args,
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
        }
        if sys.platform == 'win32':
            kwargs['creationflags'] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
        else:
            kwargs['start_new_session'] = True

        # Запуск браузера в отдельном процессе (fire-and-forget).
        # Контекстный менеджер закрывает стандартные потоки (DEVNULL),
        # а сам процесс продолжает работать независимо от родителя —
        # ожидать его завершения или читать вывод не требуется.
        with subprocess.Popen(**kwargs):
            pass
        logger.info('Браузер запущен: %s', ' '.join(args))
    except (OSError, ValueError) as e:
        logger.error('Не удалось запустить браузер %s: %s', browser_path, e)
        return False

    return True


def get_browser_config() -> dict:
    """
    Возвращает текущую конфигурацию браузера из .flowlink-settings.

    Returns:
        Словарь {browserPath, autostartBrowser, parallelLaunch}.
    """
    settings = {}
    path = _autostart_mod.SETTINGS_FILE
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            settings = _autostart_mod.parse_settings(content)
        except OSError as e:
            logger.warning('Не удалось прочитать %s: %s', path, e)

    return {
        'browserPath': settings.get(_KEY_BROWSER_PATH, ''),
        'autostartBrowser': _autostart_mod.get_autostart_browser(),
        'parallelLaunch': settings.get(_KEY_PARALLEL_LAUNCH, 'false').lower()
            in ('true', '1', 'yes', 'on'),
        'closeBrowserWithApp': settings.get(
            _KEY_CLOSE_BROWSER_WITH_APP, 'false',
        ).lower() in ('true', '1', 'yes', 'on'),
    }


def get_browser_path() -> str:
    """
    Возвращает сохранённый путь к браузеру из .flowlink-settings.

    Returns:
        Путь к браузеру или пустая строка.
    """
    path = _autostart_mod.SETTINGS_FILE
    if not os.path.isfile(path):
        return ''
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = _autostart_mod.parse_settings(f.read())
        return settings.get(_KEY_BROWSER_PATH, '')
    except OSError as e:
        logger.warning('Не удалось прочитать browser_path: %s', e)
        return ''


def save_browser_path(browser_path: str) -> None:
    """
    Сохраняет путь к браузеру в .flowlink-settings.

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Raises:
        OSError: Не удалось записать файл настроек.
    """
    path = _autostart_mod.SETTINGS_FILE
    existing = {}
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing = _autostart_mod.parse_settings(f.read())
        except OSError as e:
            logger.warning('Не удалось прочитать %s перед записью: %s', path, e)

    existing[_KEY_BROWSER_PATH] = browser_path
    content = _autostart_mod.format_settings(existing)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info('Путь браузера сохранён: %s', browser_path)
    except OSError as e:
        logger.error('Не удалось записать browser_path: %s', e)
        raise


def get_close_browser_with_app() -> bool:
    """
    Возвращает настройку «Закрывать браузер вместе с FlowLink Proxy».

    Если флаг установлен — при выходе из FlowLink Proxy браузер,
    запущенный через прокси, закрывается без предупреждения.

    Returns:
        True если браузер следует закрывать вместе с приложением.
    """
    path = _autostart_mod.SETTINGS_FILE
    if not os.path.isfile(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            settings = _autostart_mod.parse_settings(f.read())
        value = settings.get(_KEY_CLOSE_BROWSER_WITH_APP, 'false').lower()
        return value in ('true', '1', 'yes', 'on')
    except OSError as e:
        logger.warning('Не удалось прочитать close_browser_with_app: %s', e)
        return False


def set_close_browser_with_app(value: bool) -> None:
    """
    Сохраняет настройку «Закрывать браузер вместе с FlowLink Proxy».

    Args:
        value: True — закрывать браузер при выходе без предупреждения.

    Raises:
        OSError: Не удалось записать файл настроек.
    """
    path = _autostart_mod.SETTINGS_FILE
    existing = {}
    if os.path.isfile(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                existing = _autostart_mod.parse_settings(f.read())
        except OSError as e:
            logger.warning(
                'Не удалось прочитать %s перед записью: %s', path, e,
            )

    existing[_KEY_CLOSE_BROWSER_WITH_APP] = 'true' if value else 'false'
    content = _autostart_mod.format_settings(existing)

    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info('Настройка close_browser_with_app сохранена: %s', value)
    except OSError as e:
        logger.error('Не удалось записать close_browser_with_app: %s', e)
        raise
