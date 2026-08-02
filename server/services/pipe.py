"""
Пересылка данных (pipe) между клиентом и удалённым сервером.

Содержит утилиту _pipe_data для однонаправленной пересылки,
и публичные функции pipe / pipe_http_request / pipe_http_response,
которые делегируют в _pipe_data с разными именами потоков.

Единственная ответственность: пересылка потоковых данных.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger('flowlink.pipe')

_CHUNK_SIZE = 65536


async def _pipe_data(
    src: asyncio.StreamReader,
    dst: asyncio.StreamWriter,
    name: str,
) -> None:
    """Читает данные из src и пишет в dst до закрытия src.

    Args:
        src: Поток чтения данных.
        dst: Поток записи данных.
        name: Имя потока для логов (например, 'клиент->удалённый').

    Returns:
        None. Функция завершается при закрытии src или разрыве соединения.

    Raises:
        Исключения ConnectionError/OSError перехватываются и логируются,
        наружу не пробрасываются.
    """
    try:
        while not src.at_eof():
            data = await src.read(_CHUNK_SIZE)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (ConnectionError, OSError) as e:
        logger.debug('Соединение %s разорвано: %s', name, e)
    finally:
        try:
            dst.close()
        except OSError as e:
            logger.debug('Ошибка закрытия сокета %s при разрыве потока: %s',
                         name, e)


async def pipe(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    remote_reader: asyncio.StreamReader,
    remote_writer: asyncio.StreamWriter,
) -> None:
    """Двунаправленная пересылка данных между клиентом и удалённым сервером.

    Запускает две параллельные задачи _pipe_data: из клиента в удалённый
    сервер и обратно. Завершается после закрытия обоих потоков.

    Args:
        client_reader: Поток чтения от клиента.
        client_writer: Поток записи клиенту.
        remote_reader: Поток чтения от удалённого сервера.
        remote_writer: Поток записи удалённому серверу.

    Returns:
        None.
    """
    await asyncio.gather(
        _pipe_data(client_reader, remote_writer, 'клиент->удалённый'),
        _pipe_data(remote_reader, client_writer, 'удалённый->клиент'),
    )


async def pipe_http_request(
    client_reader: asyncio.StreamReader,
    remote_writer: asyncio.StreamWriter,
) -> None:
    """Пересылает тело HTTP-запроса от клиента к удалённому серверу.

    Args:
        client_reader: Поток чтения тела запроса от клиента.
        remote_writer: Поток записи удалённому серверу.

    Returns:
        None.
    """
    await _pipe_data(client_reader, remote_writer, 'HTTP-запрос')


async def pipe_http_response(
    remote_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
) -> None:
    """Пересылает тело HTTP-ответа от удалённого сервера к клиенту.

    Args:
        remote_reader: Поток чтения тела ответа от удалённого сервера.
        client_writer: Поток записи клиенту.

    Returns:
        None.
    """
    await _pipe_data(remote_reader, client_writer, 'HTTP-ответ')
