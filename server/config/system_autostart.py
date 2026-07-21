"""
Автозапуск FlowLink Proxy с системой.

Единственная ответственность: включение/отключение автозапуска
бэкенда при входе пользователя в систему.

Поддерживаемые платформы:
  - Windows: winreg (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
  - Linux: ~/.config/autostart/flowlink-proxy.desktop
  - macOS: ~/Library/LaunchAgents/com.flowlink.proxy.plist
"""

import logging
import os
import sys

logger = logging.getLogger('flowlink.system_autostart')

_APP_NAME = 'FlowLink Proxy'


def _get_autostart_path() -> str:
    """Возвращает путь к файлу автозапуска для текущей платформы."""
    if sys.platform == 'win32':
        return _WINDOWS_KEY
    if sys.platform == 'darwin':
        return os.path.expanduser(
            '~/Library/LaunchAgents/com.flowlink.proxy.plist'
        )
    return os.path.expanduser('~/.config/autostart/flowlink-proxy.desktop')


_WINDOWS_KEY = (
    r'Software\Microsoft\Windows\CurrentVersion\Run'
)


def _get_executable_info() -> tuple[str, list[str]]:
    """Возвращает (путь_к_исполняемому, аргументы_командной_строки)."""
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        return exe, []

    exe = sys.executable
    return exe, ['-m', 'server']


def is_system_autostart_enabled() -> bool:
    """
    Проверяет, включён ли автозапуск FlowLink Proxy с системой.

    Returns:
        True если автозапуск настроен.
    """
    if sys.platform == 'win32':
        return _check_windows()
    if sys.platform == 'darwin':
        return _check_macos()
    return _check_linux()


def set_system_autostart_enabled(enabled: bool) -> bool:
    """
    Включает или отключает автозапуск FlowLink Proxy с системой.

    Args:
        enabled: True — включить автозапуск, False — отключить.

    Returns:
        True если операция успешна, False при ошибке.
    """
    if sys.platform == 'win32':
        return _set_windows(enabled)
    if sys.platform == 'darwin':
        return _set_macos(enabled)
    return _set_linux(enabled)


def get_system_autostart_info() -> dict:
    """
    Возвращает информацию о состоянии автозапуска с системой.

    Returns:
        Словарь {enabled, platform, method, path}.
    """
    enabled = is_system_autostart_enabled()
    path = _get_autostart_path()

    method = 'registry'
    if sys.platform == 'darwin':
        method = 'launchd'
    elif sys.platform == 'linux':
        method = 'autostart_desktop'

    return {
        'enabled': enabled,
        'platform': sys.platform,
        'method': method,
        'path': path,
    }


def _check_windows() -> bool:
    """Проверяет автозапуск через реестр Windows."""
    try:
        # winreg доступен только на Windows
        import winreg  # pylint: disable=import-outside-toplevel
        _get_executable_info()
        key_path = winreg.HKEY_CURRENT_USER  # type: ignore[reportAttributeAccessIssue]
        with winreg.OpenKey(  # type: ignore[reportAttributeAccessIssue]
            key_path, _WINDOWS_KEY,
        ) as key:
            winreg.QueryValueEx(  # type: ignore[reportAttributeAccessIssue]
                key, _APP_NAME,
            )
            return True
    except (ImportError, OSError):
        return False


def _set_windows(enabled: bool) -> bool:
    """Устанавливает автозапуск через реестр Windows."""
    try:
        # winreg доступен только на Windows
        import winreg  # pylint: disable=import-outside-toplevel
        exe, args = _get_executable_info()
        cmd = f'"{exe}"' + (' ' + ' '.join(args) if args else '')

        with winreg.OpenKey(  # type: ignore[reportAttributeAccessIssue]
            winreg.HKEY_CURRENT_USER, _WINDOWS_KEY,  # type: ignore[reportAttributeAccessIssue]
            0, winreg.KEY_SET_VALUE,  # type: ignore[reportAttributeAccessIssue]
        ) as key:
            if enabled:
                val_args = (
                    key, _APP_NAME, 0,
                    winreg.REG_SZ, cmd,  # type: ignore[reportAttributeAccessIssue]
                )
                winreg.SetValueEx(*val_args)  # type: ignore[reportAttributeAccessIssue]
                logger.info('Автозапуск Windows включён: %s', cmd)
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)  # type: ignore[reportAttributeAccessIssue]
                    logger.info('Автозапуск Windows выключен')
                except FileNotFoundError:
                    pass
        return True
    except (ImportError, OSError) as e:
        logger.error('Ошибка настройки автозапуска Windows: %s', e)
        return False


def _check_macos() -> bool:
    """Проверяет автозапуск через launchd на macOS."""
    plist_path = _get_autostart_path()
    return os.path.isfile(plist_path)


def _set_macos(enabled: bool) -> bool:
    """Устанавливает автозапуск через launchd на macOS."""
    plist_path = _get_autostart_path()
    plist_dir = os.path.dirname(plist_path)

    try:
        if enabled:
            exe, args = _get_executable_info()
            os.makedirs(plist_dir, exist_ok=True)

            args_xml = ''
            if args:
                args_xml = '\n'.join(
                    f'        <string>{a}</string>' for a in args
                )
                args_xml = f'\n{args_xml}'

            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.flowlink.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>{args_xml}
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>'''

            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write(plist_content)
            logger.info('Автозапуск macOS создан: %s', plist_path)
        else:
            if os.path.isfile(plist_path):
                os.remove(plist_path)
                logger.info('Автозапуск macOS удалён: %s', plist_path)
        return True
    except OSError as e:
        logger.error('Ошибка настройки автозапуска macOS: %s', e)
        return False


def _check_linux() -> bool:
    """Проверяет автозапуск через .desktop файл на Linux."""
    desktop_path = _get_autostart_path()
    return os.path.isfile(desktop_path)


def _set_linux(enabled: bool) -> bool:
    """Устанавливает автозапуск через .desktop файл на Linux."""
    desktop_path = _get_autostart_path()
    autostart_dir = os.path.dirname(desktop_path)

    try:
        if enabled:
            exe, args = _get_executable_info()
            os.makedirs(autostart_dir, exist_ok=True)

            exec_line = f'"{exe}"'
            if args:
                exec_line += ' ' + ' '.join(args)

            desktop_content = f'''[Desktop Entry]
Type=Application
Name={_APP_NAME}
Exec={exec_line}
Hidden=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
'''

            with open(desktop_path, 'w', encoding='utf-8') as f:
                f.write(desktop_content)
            os.chmod(desktop_path, 0o755)
            logger.info('Автозапуск Linux создан: %s', desktop_path)
        else:
            if os.path.isfile(desktop_path):
                os.remove(desktop_path)
                logger.info('Автозапуск Linux удалён: %s', desktop_path)
        return True
    except OSError as e:
        logger.error('Ошибка настройки автозапуска Linux: %s', e)
        return False
