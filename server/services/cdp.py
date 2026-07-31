"""
Загрузка unpacked-расширения в браузер через Chrome DevTools Protocol (CDP).

Яндекс.Браузер 26.x (Chromium 148) блокирует флаг --load-extension для
неподписанных расширений без включённого Developer Mode. Обходной путь —
CDP-команда Extensions.loadUnpacked: расширение, установленное через неё,
получает флаг INSTALLED_VIA_CDP и проходит Developer Mode-гейт.

Модуль реализует минимальный WebSocket-клиент на asyncio (без внешних
зависимостей) и функцию загрузки расширения через CDP.
"""

import asyncio
import base64
import json
import logging
import os
import socket
import time
import urllib.request

logger = logging.getLogger('flowlink.cdp')

# Диапазон портов для CDP-сервера браузера.
CDP_PORT_START = 9222
CDP_PORT_END = 9322


def find_free_port(start: int = CDP_PORT_START, end: int = CDP_PORT_END) -> int:
    """
    Находит свободный TCP-порт в заданном диапазоне.

    Args:
        start: Начало диапазона (включительно).
        end: Конец диапазона (включительно).

    Returns:
        Свободный порт.

    Raises:
        OSError: Если свободный порт в диапазоне не найден.
    """
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise OSError(
        f'Не удалось найти свободный порт в диапазоне {start}-{end}',
    )


def _build_handshake_request(host: str, port: int, key: str, path: str) -> bytes:
    """Формирует HTTP-запрос рукопожатия WebSocket.

    Args:
        host: Хост CDP-сервера.
        port: Порт CDP-сервера.
        key: Случайный Sec-WebSocket-Key.
        path: Путь WebSocket-таргета (например /devtools/browser/<id>).
    """
    return (
        f'GET {path} HTTP/1.1\r\n'
        f'Host: {host}:{port}\r\n'
        f'Upgrade: websocket\r\n'
        f'Connection: Upgrade\r\n'
        f'Sec-WebSocket-Key: {key}\r\n'
        f'Sec-WebSocket-Version: 13\r\n'
        f'\r\n'
    ).encode('ascii')


def _encode_text_frame(payload: str) -> bytes:
    """Кодирует текстовый фрейм WebSocket (opcode 1, без маскирования)."""
    data = payload.encode('utf-8')
    length = len(data)
    header = bytearray([0x81])  # FIN + opcode text
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header.extend(length.to_bytes(2, 'big'))
    else:
        header.append(127)
        header.extend(length.to_bytes(8, 'big'))
    return bytes(header) + data


async def _read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    """
    Читает один фрейм WebSocket.

    Returns:
        Кортеж (opcode, payload).

    Raises:
        ConnectionError: При закрытии соединения или некорректном фрейме.
    """
    header = await reader.readexactly(2)
    opcode = header[0] & 0x0F
    masked = header[1] & 0x80
    length = header[1] & 0x7F

    if length == 126:
        length = int.from_bytes(await reader.readexactly(2), 'big')
    elif length == 127:
        length = int.from_bytes(await reader.readexactly(8), 'big')

    if masked:
        mask = await reader.readexactly(4)
        data = await reader.readexactly(length)
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    else:
        payload = await reader.readexactly(length)

    return opcode, payload


async def _send_cdp_command(  # pylint: disable=too-many-locals
    ws_url: str,
    command: dict,
    timeout: float = 30.0,
) -> dict:
    """
    Отправляет CDP-команду по WebSocket и ждёт ответ.

    Args:
        ws_url: URL WebSocket browser-таргета (webSocketDebuggerUrl).
        command: Словарь CDP-команды (id, method, params).
        timeout: Таймаут ожидания ответа в секундах.

    Returns:
        Словарь ответа CDP (result или error).

    Raises:
        TimeoutError: Если ответ не получен за отведённое время.
        ConnectionError: При ошибке соединения.
    """
    # Парсим URL WebSocket вручную (без внешних зависимостей).
    # Формат: ws://host:port/devtools/browser/<id>
    rest = ws_url[len('ws://'):]
    host_port, path = rest.split('/', 1)
    host, port_str = host_port.rsplit(':', 1)
    port = int(port_str)
    path = '/' + path

    key = base64.b64encode(os.urandom(16)).decode('ascii')

    reader, writer = await asyncio.open_connection(host, port)
    try:
        # Рукопожатие WebSocket: путь берём из webSocketDebuggerUrl,
        # т.к. browser-таргет имеет путь /devtools/browser/<id>.
        request = _build_handshake_request(host, port, key, path)
        writer.write(request)
        await writer.drain()

        # Читаем HTTP-ответ рукопожатия (до \r\n\r\n).
        response = b''
        while b'\r\n\r\n' not in response:
            chunk = await reader.read(1024)
            if not chunk:
                raise ConnectionError('Соединение закрыто во время рукопожатия')
            response += chunk

        if b'101' not in response.split(b'\r\n', 1)[0]:
            raise ConnectionError(
                f'Рукопожатие WebSocket отклонено: {response[:200]!r}',
            )

        # Отправляем CDP-команду.
        writer.write(_encode_text_frame(json.dumps(command)))
        await writer.drain()

        # Читаем фреймы до получения ответа с нужным id.
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError('Таймаут ожидания ответа CDP')

            try:
                opcode, payload = await asyncio.wait_for(
                    _read_frame(reader), timeout=remaining,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError('Таймаут ожидания ответа CDP') from exc

            if opcode == 8:  # close
                raise ConnectionError('Соединение WebSocket закрыто сервером')
            if opcode != 1:  # не текстовый фрейм — пропускаем
                continue

            try:
                msg = json.loads(payload.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            if msg.get('id') == command.get('id'):
                return msg
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass


def _wait_for_cdp_sync(port: int, timeout: float) -> str:
    """
    Синхронно ждёт появления CDP-эндпоинта и возвращает webSocketDebuggerUrl.

    Args:
        port: Порт CDP-сервера.
        timeout: Таймаут ожидания в секундах.

    Returns:
        URL WebSocket browser-таргета.

    Raises:
        TimeoutError: Если CDP-эндпоинт не стал доступен за отведённое время.
    """
    deadline = time.monotonic() + timeout
    url = f'http://127.0.0.1:{port}/json/version'
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                data = json.load(resp)
                ws_url = data.get('webSocketDebuggerUrl')
                if ws_url:
                    return ws_url
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.2)
    raise TimeoutError(
        f'CDP-эндпоинт {url} не стал доступен за {timeout} секунд',
    )


async def _load_unpacked_async(
    port: int,
    extension_dir: str,
    timeout: float = 30.0,
) -> str:
    """
    Асинхронно загружает unpacked-расширение через CDP.

    Args:
        port: Порт CDP-сервера браузера.
        extension_dir: Абсолютный путь к папке расширения с manifest.json.
        timeout: Таймаут ожидания в секундах.

    Returns:
        ID загруженного расширения.

    Raises:
        TimeoutError: Если CDP-эндпоинт недоступен или ответ не получен.
        RuntimeError: При ошибке CDP-команды.
    """
    # Ждём появления CDP-эндпоинта.
    ws_url = await asyncio.to_thread(_wait_for_cdp_sync, port, timeout)

    command = {
        'id': 1,
        'method': 'Extensions.loadUnpacked',
        'params': {'path': extension_dir},
    }
    response = await _send_cdp_command(ws_url, command, timeout)

    if 'error' in response:
        raise RuntimeError(
            f'CDP-ошибка Extensions.loadUnpacked: {response["error"]}',
        )
    result = response.get('result', {})
    ext_id = result.get('id')
    if not ext_id:
        raise RuntimeError(
            'CDP Extensions.loadUnpacked не вернул ID расширения',
        )
    return ext_id


def load_unpacked_extension(
    port: int,
    extension_dir: str,
    timeout: float = 30.0,
) -> str:
    """
    Загружает unpacked-расширение в браузер через CDP Extensions.loadUnpacked.

    Функция НЕ бросает исключений: все ошибки логируются внутри,
    а вызывающему возвращается текст результата — ID расширения
    при успехе или сообщение об ошибке.

    Args:
        port: Порт CDP-сервера браузера.
        extension_dir: Абсолютный путь к папке расширения с manifest.json.
        timeout: Таймаут ожидания в секундах.

    Returns:
        ID загруженного расширения или текст ошибки.
    """
    try:
        return asyncio.run(_load_unpacked_async(port, extension_dir, timeout))
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error(
            'Не удалось загрузить расширение %s через CDP: %s',
            extension_dir,
            exc,
        )
        return f'Ошибка загрузки расширения через CDP: {exc}'
