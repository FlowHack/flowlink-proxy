"""
HTTP CONNECT прокси-сервер на asyncio.

Принимает HTTP CONNECT (HTTPS) и plain HTTP запросы,
маршрутизирует через SOCKS5 (если маска совпала) или напрямую.

Порт: 8080 (настраивается).
Слушает только localhost.
"""

import asyncio
import logging
import re

from server import socks5
from server.router import MaskRouter

logger = logging.getLogger('flowlink.proxy')

RE_CONNECT = re.compile(rb'^CONNECT\s+([^\s:]+):(\d+)\s+HTTP/\d\.\d')
RE_HTTP = re.compile(rb'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+https?://([^\s/]+)(:\d+)?(/[^\s]*)\s+HTTP/\d\.\d', re.IGNORECASE)


class ProxyServer:

    def __init__(self, router: MaskRouter, host: str = '127.0.0.1', port: int = 8080):
        self._router = router
        self._host = host
        self._port = port
        self._server: asyncio.AbstractServer | None = None

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )
        logger.info(f'Прокси-сервер запущен на {self._host}:{self._port}')

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info('Прокси-сервер остановлен')

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            first_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not first_line:
                return

            if first_line.upper().startswith(b'CONNECT '):
                await self._handle_connect(reader, writer, first_line)
            elif first_line.upper().startswith((b'GET ', b'POST ', b'PUT ', b'DELETE ')):
                await self._handle_http(reader, writer, first_line)
            else:
                logger.warning(f'Неподдерживаемый метод: {first_line.decode(errors="ignore").strip()}')
                writer.close()

        except asyncio.TimeoutError:
            logger.debug('Таймаут ожидания первой строки запроса')
            writer.close()
        except Exception as e:
            logger.error(f'Ошибка обработки клиента: {e}', exc_info=True)
            try:
                writer.close()
            except Exception:
                pass

    async def _handle_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, first_line: bytes):
        match = RE_CONNECT.match(first_line)
        if not match:
            logger.warning(f'Неверный CONNECT запрос: {first_line.decode(errors="ignore").strip()}')
            writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            await writer.drain()
            writer.close()
            return

        target_host = match.group(1).decode()
        target_port = int(match.group(2))

        await self._skip_headers(reader)

        full_url = f'https://{target_host}:{target_port}/'

        proxy = self._router.route(full_url)

        if proxy:
            logger.debug(f'Туннель HTTPS {target_host}:{target_port} через SOCKS5 {proxy["host"]}:{proxy["port"]}')
            await self._tunnel_via_socks5(reader, writer, target_host, target_port, proxy, full_url)
        else:
            logger.debug(f'Туннель HTTPS {target_host}:{target_port} напрямую')
            await self._tunnel_direct(reader, writer, target_host, target_port, full_url)

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, first_line: bytes):
        match = RE_HTTP.match(first_line)
        if not match:
            logger.warning(f'Не удалось распарсить HTTP запрос: {first_line.decode(errors="ignore").strip()}')
            writer.write(b'HTTP/1.1 400 Bad Request\r\n\r\n')
            await writer.drain()
            writer.close()
            return

        method = match.group(1).decode()
        host = match.group(2).decode()
        port_str = match.group(3)
        path = match.group(4).decode()

        port = int(port_str[1:]) if port_str else 80
        relative_line = f'{method} {path} HTTP/1.1\r\n'.encode()

        full_url = f'http://{host}:{port}{path}'
        proxy = self._router.route(full_url)

        if proxy:
            logger.debug(f'HTTP {host}:{port}{path} через SOCKS5 {proxy["host"]}:{proxy["port"]}')
            await self._http_via_socks5(reader, writer, host, port, proxy, full_url, relative_line)
        else:
            logger.debug(f'HTTP {host}:{port}{path} напрямую')
            await self._http_direct(reader, writer, host, port, full_url, relative_line)

    async def _skip_headers(self, reader: asyncio.StreamReader):
        while True:
            line = await reader.readline()
            if not line or line == b'\r\n':
                break

    async def _tunnel_via_socks5(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        proxy: dict,
        url: str
    ):
        try:
            username = proxy.get('username', '')
            password = proxy.get('password', '')
            logger.debug(f'SOCKS5 creds для {url}: username="{username}" password_len={len(password)}')
            remote_reader, remote_writer = await socks5.socks5_connect(
                proxy_host=proxy['host'],
                proxy_port=proxy['port'],
                target_host=target_host,
                target_port=target_port,
                username=username,
                password=password,
            )

            client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await client_writer.drain()

            await self._pipe(client_reader, client_writer, remote_reader, remote_writer)

        except socks5.Socks5Error as e:
            logger.warning(f'SOCKS5 ошибка для {url}: {e}')
            client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            await client_writer.drain()
        except Exception as e:
            logger.error(f'Ошибка туннеля SOCKS5 для {url}: {e}')
            try:
                client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                await client_writer.drain()
            except Exception:
                pass

    async def _tunnel_direct(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        url: str
    ):
        try:
            remote_reader, remote_writer = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port),
                timeout=10
            )

            client_writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            await client_writer.drain()

            await self._pipe(client_reader, client_writer, remote_reader, remote_writer)

        except (OSError, ConnectionError, asyncio.TimeoutError) as e:
            logger.warning(f'Ошибка прямого соединения для {url}: {e}')
            try:
                client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                await client_writer.drain()
            except Exception:
                pass

    async def _http_via_socks5(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        proxy: dict,
        url: str,
        relative_line: bytes,
    ):
        try:
            remote_reader, remote_writer = await socks5.socks5_connect(
                proxy_host=proxy['host'],
                proxy_port=proxy['port'],
                target_host=target_host,
                target_port=target_port,
                username=proxy.get('username', ''),
                password=proxy.get('password', ''),
            )

            remote_writer.write(relative_line)
            await self._pipe_http_request(client_reader, remote_writer)
            await self._pipe_http_response(remote_reader, client_writer)

        except socks5.Socks5Error as e:
            logger.warning(f'SOCKS5 ошибка HTTP для {url}: {e}')
            client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            await client_writer.drain()
        except Exception as e:
            logger.error(f'Ошибка HTTP через SOCKS5 для {url}: {e}')
            try:
                client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                await client_writer.drain()
            except Exception:
                pass

    async def _http_direct(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_host: str,
        target_port: int,
        url: str,
        relative_line: bytes,
    ):
        try:
            remote_reader, remote_writer = await asyncio.wait_for(
                asyncio.open_connection(target_host, target_port),
                timeout=10
            )

            remote_writer.write(relative_line)
            await self._pipe_http_request(client_reader, remote_writer)
            await self._pipe_http_response(remote_reader, client_writer)

        except (OSError, ConnectionError, asyncio.TimeoutError) as e:
            logger.warning(f'Ошибка прямого HTTP-соединения для {url}: {e}')
            try:
                client_writer.write(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                await client_writer.drain()
            except Exception:
                pass

    async def _pipe(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        remote_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
    ):
        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
            try:
                while not src.at_eof():
                    data = await src.read(65536)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                try:
                    dst.close()
                except Exception:
                    pass

        await asyncio.gather(
            forward(client_reader, remote_writer),
            forward(remote_reader, client_writer),
        )

    async def _pipe_http_request(
        self,
        client_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
    ):
        try:
            while not client_reader.at_eof():
                data = await client_reader.read(65536)
                if not data:
                    break
                remote_writer.write(data)
                await remote_writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                remote_writer.close()
            except Exception:
                pass

    async def _pipe_http_response(
        self,
        remote_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ):
        try:
            while not remote_reader.at_eof():
                data = await remote_reader.read(65536)
                if not data:
                    break
                client_writer.write(data)
                await client_writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            try:
                client_writer.close()
            except Exception:
                pass
