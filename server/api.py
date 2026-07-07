"""
HTTP API сервер для управления FlowLink Proxy из расширения.

Порт: 8081 (настраивается).
Слушает только localhost.
Формат: JSON.

Эндпоинты:
  GET  /api/config    - получить конфигурацию
  POST /api/config    - обновить конфигурацию (JSON в теле)
  GET  /api/status    - статус gateway
  GET  /api/version   - версия gateway
  POST /api/ping      - пинг прокси (JSON: {proxyId})
"""

import asyncio
import json
import logging
import time

from server import config as cfg
from server import socks5
from server.router import MaskRouter
from server.version import __version__ as server_version

logger = logging.getLogger('flowlink.api')


class ApiServer:

    def __init__(self, router: MaskRouter, host: str = '127.0.0.1', port: int = 8081, debug: bool = False):
        self._router = router
        self._host = host
        self._port = port
        self._debug = debug
        self._server: asyncio.AbstractServer | None = None

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )
        logger.info(f'API сервер запущен на {self._host}:{self._port}')

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info('API сервер остановлен')

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not request_line:
                return

            parts = request_line.decode().strip().split(' ')
            if len(parts) < 2:
                writer.close()
                return

            method = parts[0].upper()
            path = parts[1]

            content_length = 0
            while True:
                line = await reader.readline()
                if not line or line == b'\r\n':
                    break
                header_line = line.decode().strip().lower()
                if header_line.startswith('content-length:'):
                    try:
                        content_length = int(header_line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass

            body = b''
            if content_length > 0:
                body = await reader.readexactly(content_length)

            status_code = 200
            response_body = {'error': 'Not Found'}
            content_type = 'application/json'

            if path == '/api/config' and method == 'GET':
                response_body = cfg.load_config()
            elif path == '/api/config' and method == 'POST':
                try:
                    data = json.loads(body)
                    old_data = cfg.load_config()
                    old_proxies = {p['proxyId']: p for p in old_data.get('proxies', [])}
                    old_masks = {m['maskId']: m for m in old_data.get('masks', [])}
                    cfg.save_config(data)
                    self._router.refresh()
                    response_body = {'success': True}
                    # Логируем изменения (без паролей)
                    new_proxies = {p['proxyId']: p for p in data.get('proxies', [])}
                    for pid, p in new_proxies.items():
                        addr = f'{p["host"]}:{p["port"]}'
                        if pid not in old_proxies:
                            logger.info(f'Добавлен прокси {addr}')
                        else:
                            old = old_proxies[pid]
                            if old.get('host') != p['host'] or old.get('port') != p['port']:
                                logger.info(f'Изменён прокси {addr}')
                    for pid, p in old_proxies.items():
                        if pid not in new_proxies:
                            logger.info(f'Удалён прокси {p["host"]}:{p["port"]}')
                    new_masks = {m['maskId']: m for m in data.get('masks', [])}
                    for mid, m in new_masks.items():
                        if mid not in old_masks:
                            logger.info(f'Добавлена маска {m["regexString"]} для прокси {m["proxyId"]}')
                    for mid, m in old_masks.items():
                        if mid not in new_masks:
                            logger.info(f'Удалена маска {m["regexString"]}')
                except json.JSONDecodeError as e:
                    status_code = 400
                    response_body = {'error': f'Invalid JSON: {e}'}
            elif path == '/api/status' and method == 'GET':
                response_body = {
                    'isEnabled': cfg.is_enabled(),
                    'proxiesCount': len(cfg.get_all_proxies()),
                    'masksCount': len(cfg.get_all_masks()),
                    'status': 'running',
                    'debug': self._debug,
                }
            elif path == '/api/version' and method == 'GET':
                response_body = {'version': server_version}
            elif path == '/api/ping' and method == 'POST':
                try:
                    data = json.loads(body)
                    proxy_id = data.get('proxyId')
                    if not proxy_id:
                        status_code = 400
                        response_body = {'error': 'proxyId required'}
                    else:
                        result = await self._ping_proxy(proxy_id)
                        response_body = result
                        proxy = next((p for p in cfg.get_all_proxies() if p.get('proxyId') == proxy_id), None)
                        addr = f'{proxy["host"]}:{proxy["port"]}' if proxy else proxy_id
                        if result.get('alive'):
                            logger.info(f'Пинг {addr}: {result["latency"]}мс')
                        else:
                            logger.warning(f'Пинг {addr}: недоступен')
                except json.JSONDecodeError as e:
                    status_code = 400
                    response_body = {'error': f'Invalid JSON: {e}'}
            else:
                status_code = 404
                response_body = {'error': f'Not Found: {method} {path}'}

            response_json = json.dumps(response_body, ensure_ascii=False)
            response_headers = (
                f'HTTP/1.1 {status_code} {"OK" if status_code == 200 else "Error"}\r\n'
                f'Content-Type: {content_type}\r\n'
                f'Content-Length: {len(response_json.encode())}\r\n'
                f'Access-Control-Allow-Origin: *\r\n'
                f'Connection: close\r\n'
                f'\r\n'
            )
            writer.write(response_headers.encode() + response_json.encode())
            await writer.drain()

        except asyncio.TimeoutError:
            logger.debug('API: таймаут ожидания запроса')
        except Exception as e:
            logger.error(f'API ошибка: {e}', exc_info=True)
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def _ping_proxy(self, proxy_id: str) -> dict:
        proxies = cfg.get_all_proxies()
        proxy = None
        for p in proxies:
            if p.get('proxyId') == proxy_id:
                proxy = p
                break

        if not proxy:
            return {'alive': False, 'latency': None, 'error': 'Proxy not found'}

        has_auth = bool(proxy.get('username') and proxy.get('password'))
        start = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy['host'], proxy['port']),
                timeout=5
            )

            methods = [0x00]
            if has_auth:
                methods.append(0x02)
            writer.write(bytes([0x05, len(methods)] + methods))
            await writer.drain()

            response = await asyncio.wait_for(reader.readexactly(2), timeout=5)

            ver, method = response
            if ver != 0x05:
                writer.close()
                return {'alive': False, 'latency': None}

            if method == 0x02 and has_auth:
                u = proxy['username'].encode()
                p = proxy['password'].encode()
                auth_msg = bytes([0x01, len(u)]) + u + bytes([len(p)]) + p
                writer.write(auth_msg)
                await writer.drain()
                auth_resp = await asyncio.wait_for(reader.readexactly(2), timeout=5)
                if auth_resp[1] != 0x00:
                    writer.close()
                    return {'alive': False, 'latency': None, 'error': 'Auth failed'}

            writer.close()
            latency = int((time.monotonic() - start) * 1000)
            return {'alive': True, 'latency': latency}

        except (OSError, ConnectionError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
            logger.debug(f'Пинг прокси {proxy_id}: {e}')
            return {'alive': False, 'latency': None}
