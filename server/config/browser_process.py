"""
Работа с процессами браузера: поиск PID, проверка запущенности, завершение.

Единственная ответственность: платформенные операции с процессами браузера
по пути к исполняемому файлу.

Chrome/Chromium игнорирует флаг --proxy-server, если процесс браузера уже
запущен, поэтому перед запуском необходимо проверять наличие живых процессов
и при необходимости завершать их.

Windows: поиск через wmic (точное сопоставление по ExecutablePath),
fallback на PowerShell; завершение через taskkill /F /PID <pid> /T.
Linux/macOS: поиск через pgrep -f (сопоставление по полному пути в командной
строке); завершение через SIGTERM с последующим SIGKILL.
"""

import logging
import os
import signal
import subprocess
import sys
import time

logger = logging.getLogger('flowlink.browser_process')

# CREATE_NO_WINDOW скрывает мигающее окно командной строки при вызове
# wmic/powershell/taskkill из GUI-приложения. Флаг существует только на
# Windows; на других ОС атрибута нет — подставляем 0 (ветки win32 там
# не выполняются, а тесты запускаются на Linux с замоканной платформой).
_CREATE_NO_WINDOW: int = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

# Пауза между отправкой SIGTERM и проверкой выживших процессов (секунды)
_SIGTERM_GRACE_SECONDS = 2.0


def get_browser_process_name(browser_path: str) -> str:
    """
    Извлекает имя исполняемого файла браузера из пути.

    Для кросс-платформенной надёжности обратные слеши нормализуются в
    прямые: так имя корректно извлекается из Windows-путей даже на
    Linux/macOS (например, browser.exe для Яндекс.Браузера).

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        Имя файла (например, browser.exe) или пустая строка.
    """
    return os.path.basename((browser_path or '').replace('\\', '/'))


def find_browser_pids(browser_path: str) -> list[int]:
    """
    Находит PID всех процессов браузера по пути к исполняемому файлу.

    Сопоставление ведётся по полному пути, а не по имени процесса, чтобы
    не задеть другие браузеры с тем же именем исполняемого файла
    (например, browser.exe Яндекс.Браузера).

    Windows: wmic process where "ExecutablePath='<path>'" get ProcessId.
    Linux/macOS: pgrep -f '<path>'.

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        Список целых PID запущенных процессов. Пустой список при ошибке
        или отсутствии процессов.
    """
    if not browser_path or not browser_path.strip():
        logger.warning('Пустой путь к браузеру — поиск процессов не выполнен')
        return []

    if sys.platform == 'win32':
        return _find_browser_pids_windows(browser_path)
    return _find_browser_pids_posix(browser_path)


def _find_browser_pids_windows(browser_path: str) -> list[int]:
    """
    Ищет PID процессов браузера на Windows по точному пути ExecutablePath.

    Сначала пробует wmic, при его отсутствии — PowerShell
    (Get-CimInstance Win32_Process).

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        Список целых PID или пустой список.
    """
    # Одинарные кавычки в пути экранируются удвоением (wmic и PowerShell)
    escaped = browser_path.replace("'", "''")

    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', f"ExecutablePath='{escaped}'",
             'get', 'ProcessId'],
            capture_output=True, text=True,
            timeout=10, check=False,
            # CREATE_NO_WINDOW скрывает мигающее окно командной строки
            # при вызове wmic из GUI-приложения (см. _CREATE_NO_WINDOW).
            creationflags=_CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            pids = _parse_pids(result.stdout)
            logger.debug('wmic: найдено процессов браузера %s: %s',
                         browser_path, pids)
            return pids
        logger.warning(
            'wmic вернул код %d, пробую PowerShell: %s',
            result.returncode, result.stderr.strip() or result.stdout.strip(),
        )
    except OSError as e:
        # wmic недоступен (устарел/удалён) — переходим на PowerShell
        logger.warning('wmic недоступен (%s), пробую PowerShell', e)
    except subprocess.TimeoutExpired as e:
        logger.warning('wmic превысил таймаут (%s), пробую PowerShell', e)

    # Fallback: PowerShell Get-CimInstance Win32_Process
    ps_command = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{$_.ExecutablePath -eq '{escaped}'}} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_command],
            capture_output=True, text=True,
            timeout=15, check=False,
            # Аналогично wmic: без CREATE_NO_WINDOW powershell на
            # мгновение открывает окно консоли, что отвлекает
            # пользователя (см. _CREATE_NO_WINDOW).
            creationflags=_CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            pids = _parse_pids(result.stdout)
            logger.debug('PowerShell: найдено процессов браузера %s: %s',
                         browser_path, pids)
            return pids
        logger.warning(
            'PowerShell не нашёл процессы браузера %s (код %d): %s',
            browser_path, result.returncode,
            result.stderr.strip() or result.stdout.strip(),
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.error('Не удалось найти процессы браузера %s: %s',
                     browser_path, e)
    return []


def _find_browser_pids_posix(browser_path: str) -> list[int]:
    """
    Ищет PID процессов браузера на Linux/macOS по полному пути.

    pgrep -f сопоставляет полный путь в командной строке и ловит все
    дочерние процессы браузера (renderer, gpu-process и т.п.).

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        Список целых PID или пустой список.
    """
    try:
        result = subprocess.run(
            ['pgrep', '-f', browser_path],
            capture_output=True, text=True,
            timeout=10, check=False,
        )
        if result.returncode == 0:
            pids = _parse_pids(result.stdout)
            logger.debug('pgrep: найдено процессов браузера %s: %s',
                         browser_path, pids)
            return pids
        # returncode 1 — процессы не найдены (штатная ситуация)
        return []
    except OSError as e:
        logger.error('pgrep недоступен для поиска %s: %s', browser_path, e)
    except subprocess.TimeoutExpired as e:
        logger.error('pgrep превысил таймаут при поиске %s: %s',
                     browser_path, e)
    return []


def _parse_pids(output: str) -> list[int]:
    """
    Разбирает вывод wmic/PowerShell/pgrep в список целых PID.

    Args:
        output: Текстовый вывод команды поиска процессов.

    Returns:
        Список целых PID (невалидные строки пропускаются).
    """
    pids: list[int] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.lower() == 'processid':
            continue
        try:
            pids.append(int(line))
        except ValueError:
            # Строка не является числом — пропускаем (заголовок, мусор)
            continue
    return pids


def is_browser_running(browser_path: str) -> bool:
    """
    Проверяет, запущен ли процесс указанного браузера.

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        True если найден хотя бы один процесс браузера.
    """
    pids = find_browser_pids(browser_path)
    if pids:
        logger.info('Браузер уже запущен: %s (PID: %s)',
                    browser_path, ', '.join(str(p) for p in pids))
        return True
    return False


def kill_browser_processes(browser_path: str) -> bool:
    """
    Завершает все найденные процессы указанного браузера.

    Windows: taskkill /F /PID <pid> /T для каждого PID.
    Linux/macOS: SIGTERM для каждого PID, затем через паузу SIGKILL
    для выживших процессов.

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        True если все найденные процессы завершены (или их не было),
        False если хотя бы один процесс завершить не удалось.
    """
    pids = find_browser_pids(browser_path)
    if not pids:
        logger.info('Процессы браузера не найдены — завершать нечего: %s',
                    browser_path)
        return True

    logger.info('Завершение процессов браузера %s (PID: %s)',
                browser_path, ', '.join(str(p) for p in pids))

    if sys.platform == 'win32':
        return _kill_browser_windows(pids, browser_path)
    return _kill_browser_posix(pids, browser_path)


def _kill_browser_windows(pids: list[int], browser_path: str) -> bool:
    """
    Завершает процессы браузера на Windows через taskkill /F /T.

    Args:
        pids: Список PID процессов.
        browser_path: Путь к исполняемому файлу браузера (для логов).

    Returns:
        True если все процессы завершены успешно.
    """
    all_killed = True
    for pid in pids:
        try:
            result = subprocess.run(
                ['taskkill', '/F', '/PID', str(pid), '/T'],
                capture_output=True, text=True,
                timeout=15, check=False,
                # CREATE_NO_WINDOW скрывает окно консоли taskkill —
                # иначе при завершении каждого процесса браузера
                # пользователь видит мигающее окно (см. _CREATE_NO_WINDOW).
                creationflags=_CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                logger.info('Процесс %d браузера %s завершён (taskkill)',
                            pid, browser_path)
            elif not _process_alive(pid):
                # Процесс уже завершён как часть дерева другого процесса
                # (taskkill /T убивает всё дерево). Это не ошибка —
                # браузер фактически закрыт, блокировать запуск нельзя.
                logger.info('Процесс %d браузера %s уже завершён (дерево)',
                            pid, browser_path)
            else:
                all_killed = False
                logger.error(
                    'Не удалось завершить процесс %d браузера %s: %s',
                    pid, browser_path,
                    result.stderr.strip() or result.stdout.strip(),
                )
        except OSError as e:
            all_killed = False
            logger.error('taskkill недоступен для PID %d (%s): %s',
                         pid, browser_path, e)
        except subprocess.TimeoutExpired as e:
            all_killed = False
            logger.error('taskkill превысил таймаут для PID %d (%s): %s',
                         pid, browser_path, e)
    return all_killed


def _kill_browser_posix(pids: list[int], browser_path: str) -> bool:
    """
    Завершает процессы браузера на Linux/macOS: SIGTERM, затем SIGKILL.

    Args:
        pids: Список PID процессов.
        browser_path: Путь к исполняемому файлу браузера (для логов).

    Returns:
        True если все процессы завершены успешно.
    """
    all_killed = True

    # Шаг 1: вежливый SIGTERM всем найденным процессам
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info('Процесс %d браузера %s: отправлен SIGTERM',
                        pid, browser_path)
        except ProcessLookupError:
            # Процесс уже завершился — штатная ситуация
            logger.info('Процесс %d браузера %s уже завершён (SIGTERM)',
                        pid, browser_path)
        except PermissionError as e:
            all_killed = False
            logger.error('Нет прав на завершение процесса %d (%s): %s',
                         pid, browser_path, e)
        except OSError as e:
            all_killed = False
            logger.error('Ошибка SIGTERM для процесса %d (%s): %s',
                         pid, browser_path, e)

    # Пауза для graceful-завершения (сохранение данных и т.п.)
    time.sleep(_SIGTERM_GRACE_SECONDS)

    # Шаг 2: выжившие процессы добиваем SIGKILL
    for pid in pids:
        if not _process_alive(pid):
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            logger.info('Процесс %d браузера %s: отправлен SIGKILL',
                        pid, browser_path)
        except ProcessLookupError:
            # Процесс успел завершиться после SIGTERM
            logger.info('Процесс %d браузера %s завершён после SIGTERM',
                        pid, browser_path)
        except PermissionError as e:
            all_killed = False
            logger.error('Нет прав на SIGKILL процесса %d (%s): %s',
                         pid, browser_path, e)
        except OSError as e:
            all_killed = False
            logger.error('Ошибка SIGKILL для процесса %d (%s): %s',
                         pid, browser_path, e)

    # Финальная проверка: не осталось ли живых процессов
    alive = [pid for pid in pids if _process_alive(pid)]
    if alive:
        all_killed = False
        logger.error('Не удалось завершить процессы браузера %s: %s',
                     browser_path, alive)
    return all_killed


def _process_alive(pid: int) -> bool:
    """
    Проверяет, жив ли процесс с указанным PID (сигнал 0).

    Args:
        pid: Идентификатор процесса.

    Returns:
        True если процесс существует и доступен.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Процесс существует, но нет прав на сигнал 0 — считаем живым
        return True
    except OSError:
        return False
    return True


def get_manual_kill_instructions(browser_path: str) -> str:
    """
    Возвращает платформенную инструкцию для ручного завершения браузера.

    PID в текст не включаются: они устаревают, а их перечисление делает
    сообщение слишком широким для диалогового окна. Вместо этого
    описывается, как найти и завершить процесс браузера.

    Args:
        browser_path: Путь к исполняемому файлу браузера.

    Returns:
        Строка инструкции, или сообщение об отсутствии процессов.
    """
    pids = find_browser_pids(browser_path)
    if not pids:
        return 'Процессы браузера не обнаружены.'

    name = get_browser_process_name(browser_path)

    if sys.platform == 'win32':
        return (
            'Откройте Диспетчер задач (Ctrl+Shift+Esc) → вкладка '
            f'«Подробности» → найдите процесс {name} '
            '→ ПКМ → «Завершить задачу».'
        )

    # Linux и macOS используют одинаковую команду завершения
    return f"Выполните в терминале: pkill -f '{browser_path}'"
