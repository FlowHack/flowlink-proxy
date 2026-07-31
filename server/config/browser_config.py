"""
Конфигурация и автозапуск браузера FlowLink Proxy.

Единственная ответственность: автопоиск браузеров, валидация путей,
запуск браузера с --proxy-server, чтение/запись browser_path.
"""

import logging
import os
import subprocess
import sys
import threading

from server.config import autostart as _autostart_mod
from server.services.cdp import find_free_port, load_unpacked_extension
from server.utils import get_data_dir

logger = logging.getLogger('flowlink.browser')

_KEY_BROWSER_PATH = 'browser_path'
_KEY_PARALLEL_LAUNCH = 'parallel_launch'

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
            except OSError:
                pass
    except ImportError:
        pass

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
        except (OSError, subprocess.TimeoutExpired):
            pass

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


def _is_valid_extension_path(ext_path: str) -> bool:
    """
    Проверяет, является ли путь корректным расширением FlowLink Proxy.

    Валидной считается ТОЛЬКО распакованная папка с manifest.json:
    и CDP-команда Extensions.loadUnpacked, и флаг --load-extension
    принимают исключительно unpacked-директорию, а путь к .crx-файлу
    молча игнорируется.

    Args:
        ext_path: Путь к расширению.

    Returns:
        True если путь — распакованная папка с manifest.json, иначе False.
    """
    if not ext_path:
        return False

    if os.path.isdir(ext_path) and os.path.isfile(
        os.path.join(ext_path, 'manifest.json'),
    ):
        return True

    if os.path.isfile(ext_path):
        logger.debug(
            'Расширение %s отклонено: загрузка через CDP не поддерживает '
            'CRX-файлы, только распакованную папку с manifest.json',
            ext_path,
        )
    else:
        logger.debug(
            'Расширение %s отклонено: путь не является папкой с manifest.json',
            ext_path,
        )
    return False


def launch_browser(
    browser_path: str,
    proxy_port: int = 8080,
    ext_path: str | None = None,
) -> bool:
    """
    Запускает браузер с флагом --proxy-server, базовыми флагами запуска
    и опционально загружает расширение через Chrome DevTools Protocol (CDP).

    Базовые флаги (добавляются всегда):
        --no-first-run, --no-default-browser-check — подавление первого
        запуска и проверки браузера по умолчанию.
        --user-data-dir — выделенный профиль, чтобы не перехватывать
        уже запущенный процесс пользователя (handoff).

    При наличии валидного расширения добавляются:
        --remote-debugging-port и --remote-allow-origins=* — открывают
        CDP-эндпоинт, через который расширение загружается командой
        Extensions.loadUnpacked. Такой способ обходит Developer Mode-гейт
        Яндекс.Браузера 26.x (Chromium 148): расширение получает флаг
        INSTALLED_VIA_CDP и загружается без --load-extension, который
        браузер игнорирует для неподписанных расширений.

    Загрузка расширения через CDP выполняется в фоновом потоке: она не
    блокирует запуск браузера и не влияет на результат функции. Если
    CDP-загрузка не удалась — браузер всё равно считается запущенным.

    Args:
        browser_path: Путь к исполняемому файлу браузера.
        proxy_port: Порт HTTP-прокси (по умолчанию 8080).
        ext_path: Путь к распакованной папке расширения с manifest.json
            (CRX-файл не поддерживается), опционально.

    Returns:
        True если браузер успешно запущен, False при ошибке.
    """
    if not validate_browser_path(browser_path):
        logger.warning(
            'Невалидный путь к браузеру: %s. Браузер не запущен.',
            browser_path,
        )
        return False

    proxy_arg = f'--proxy-server=127.0.0.1:{proxy_port}'

    # Выделенный профиль браузера в data-директории: исключает handoff
    # в уже запущенный процесс и изолирует настройки расширения.
    profile_dir = os.path.join(get_data_dir(), 'browser-profile')
    try:
        os.makedirs(profile_dir, exist_ok=True)
    except OSError as e:
        logger.warning(
            'Не удалось создать профиль браузера %s: %s', profile_dir, e,
        )

    args = [
        browser_path,
        proxy_arg,
        '--no-first-run',
        '--no-default-browser-check',
        f'--user-data-dir={profile_dir}',
    ]

    # Валидность расширения проверяется один раз: результат используется
    # и для формирования CDP-флагов, и для запуска фоновой загрузки.
    has_valid_ext = bool(ext_path and _is_valid_extension_path(ext_path))

    cdp_port: int | None = None
    if has_valid_ext:
        try:
            cdp_port = find_free_port()
        except OSError as exc:
            logger.warning(
                'Не удалось найти свободный порт для CDP: %s. '
                'Расширение не будет загружено через CDP.',
                exc,
            )
        if cdp_port is not None:
            args.append(f'--remote-debugging-port={cdp_port}')
            args.append('--remote-allow-origins=*')
            logger.debug('CDP-порт для загрузки расширения: %d', cdp_port)

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

        subprocess.Popen(**kwargs)  # pylint: disable=consider-using-with
        logger.info('Браузер запущен: %s', ' '.join(args))
    except (OSError, ValueError) as e:
        logger.error('Не удалось запустить браузер %s: %s', browser_path, e)
        return False

    # Загрузка расширения через CDP Extensions.loadUnpacked выполняется
    # в фоновом daemon-потоке: не блокирует запуск браузера и не роняет
    # функцию при ошибке CDP-загрузки.
    if cdp_port is not None:
        ext_dir = ext_path or ''

        def _load_ext() -> None:
            result = load_unpacked_extension(cdp_port, ext_dir)
            logger.info('Результат загрузки расширения через CDP: %s', result)

        threading.Thread(target=_load_ext, daemon=True).start()

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
