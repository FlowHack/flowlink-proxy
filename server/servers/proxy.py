"""
HTTP CONNECT прокси-сервер на asyncio.

Единственная ответственность: запуск/остановка сервера и диспетчеризация запросов.
Парсинг протокола, туннелирование и пересылка данных вынесены в отдельные модули.
"""

import asyncio
import logging

from server.protocols.parser import parse_connect, parse_http, skip_headers
from server.servers.base_server import BaseServer, safe_close_writer
from server.services.router import MaskRouter
from server.services.tunnel import tunnel_connect, tunnel_http, validate_target

logger = logging.getLogger('flowlink.proxy')


class ProxyServer(BaseServer):
    """
    HTTP CONNECT прокси-сервер.

    Принимает HTTP/HTTPS-запросы от клиента (Chrome), парсит их,
    определяет целевой прокси через MaskRouter и устанавливает туннель.
    """

    def __init__(self, router: MaskRouter, host: str = '127.0.0.1',
                 port: int = 8080):
        """
        Args:
            router: Экземпляр MaskRouter для маршрутизации URL.
            host: Интерфейс (по умолч. localhost).
            port: Порт для HTTP CONNECT прокси (по умолч. 8080).
        """
        super().__init__(host=host, port=port, name='proxy')
        self._router = router

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ):
        """Читает первую строку запроса и диспетчеризует:
        CONNECT → _handle_connect, GET/POST → _handle_http."""
        peername = writer.get_extra_info('peername', ('?', 0))
        try:
            first_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not first_line:
                logger.debug('Клиент %s закрыл соединение без отправки данных',
                             peername)
                writer.close()
                return

            line = (
                first_line.decode(errors='ignore')
                .strip()
                .replace('\n', ' ')
                .replace('\r', '')[:500]
            )
            logger.debug('Входящий запрос от %s: %s', peername, line)

            if first_line.upper().startswith(b'CONNECT '):
                await self._handle_connect(reader, writer, first_line)
            elif first_line.upper().startswith(
                (b'GET ', b'POST ', b'PUT ', b'DELETE '),
            ):
                await self._handle_http(reader, writer, first_line)
            else:
                logger.warning('Неподдерживаемый метод от %s: %s',
                               peername, line[:200])
                writer.close()

        except asyncio.TimeoutError:
            logger.debug('Таймаут ожидания запроса от %s', peername)
            writer.close()
        except (ValueError,
                ConnectionError, OSError,
                asyncio.IncompleteReadError) as e:
            if isinstance(e, ValueError) and 'SSRF' in str(e):
                try:
                    body = 'SSRF: запрос к локальному адресу запрещён'
                    writer.write(
                        f'HTTP/1.1 502 Bad Gateway\r\n'
                        f'Content-Type: text/plain; charset=utf-8\r\n'
                        f'Content-Length: {len(body.encode())}\r\n\r\n'
                        f'{body}'.encode(),
                    )
                    await writer.drain()
                except (ConnectionError, OSError):
                    pass
            logger.error('Ошибка обработки клиента %s: %s',
                         peername, e, exc_info=True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Последний рубеж: логируем неожиданные ошибки в туннеле
            logger.error('Неожиданная ошибка в клиенте %s: %s',
                         peername, e, exc_info=True)
        finally:
            safe_close_writer(writer)

    async def _handle_connect(
        self, reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter, first_line: bytes,
    ):
        """Обрабатывает HTTPS CONNECT-запрос:
        парсит host:port, находит прокси, устанавливает туннель."""
        parsed = parse_connect(first_line)
        if not parsed:
            logger.warning('Неверный CONNECT запрос: %s',
                           first_line.decode(errors='ignore').strip())
            writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            await writer.drain()
            writer.close()
            return

        target_host, target_port = parsed
        await skip_headers(reader)
        await validate_target(target_host, target_port)
        full_url = f'https://{target_host}:{target_port}/'
        proxy = self._router.route(full_url)

        if proxy:
            logger.debug('Туннель HTTPS %s:%s через %s:%s',
                         target_host, target_port,
                         proxy['host'], proxy['port'])
        else:
            logger.debug('Туннель HTTPS %s:%s напрямую',
                         target_host, target_port)
        await tunnel_connect((reader, writer), (target_host, target_port),
                             full_url, proxy)

    async def _handle_http(
        self, reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter, first_line: bytes,
    ):
        """Обрабатывает plain HTTP запрос:
        переписывает URL (абсолютный → относительный), туннелирует."""
        parsed = parse_http(first_line)
        if not parsed:
            logger.warning('Не удалось распарсить HTTP запрос: %s',
                           first_line.decode(errors='ignore').strip())
            writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            await writer.drain()
            writer.close()
            return

        _, host, port, path, relative_line = parsed
        await validate_target(host, port)
        full_url = f'http://{host}:{port}{path}'
        proxy = self._router.route(full_url)

        if proxy:
            logger.debug('HTTP %s:%s%s через %s:%s',
                         host, port, path,
                         proxy['host'], proxy['port'])
        else:
            logger.debug('HTTP %s:%s%s напрямую',
                         host, port, path)
        await tunnel_http((reader, writer), (host, port), full_url,
                          relative_line, proxy)
