# FlowLink Proxy — Отладка и API

## Содержание

1. [Флаги CLI](#флаги-cli)
2. [Логирование](#логирование)
3. [API для разработчиков](#api-для-разработчиков)
4. [Устранение проблем](#устранение-проблем)

---

## Флаги CLI

```bash
"FlowLink Proxy" [флаги]           # standalone
python -m server [флаги]           # исходный код
./scripts/flowlink.sh [флаги]      # лаунчер
```

| Флаг | По умолч. | Описание |
|------|-----------|----------|
| `--proxy-port` | `8080` | Порт HTTP CONNECT прокси |
| `--api-port` | `8081` | Порт HTTP API для расширения |
| `--debug` | выкл. | Подробные логи в консоль и файл |
| `--dev` | выкл. | Режим разработки (debug + auto-reload + mock-сервер) |
| `--need-update` | выкл. | Симуляция обновления (debug + SSE-событие `need_update`) |

### Примеры

```bash
# Сменить порты
"FlowLink Proxy" --proxy-port 9090 --api-port 9091

# Режим отладки
"FlowLink Proxy" --debug

# Смена портов + отладка
"FlowLink Proxy" --proxy-port 7777 --api-port 8888 --debug

# Режим разработки
python -m server --dev

# Симуляция баннера обновления
python -m server --need-update
```

### `--debug`

Включает подробное логирование:
- Все входящие HTTP-запросы
- SOCKS5 handshake (host:port, результат)
- Маршрутизация (какая маска совпала)
- Ошибки с трейсбеками

### `--dev`

Включает `--debug` плюс:
- **Auto-reload** — при изменении `.py` файла сервер перезапускается автоматически
- **Mock SOCKS5** — встроенный mock-сервер на `127.0.0.1:<случайный_порт>` для тестирования без реального прокси

Не предназначен для продакшена.

### `--need-update`

Симулирует наличие обновления:
- Включает `--debug`
- Отправляет SSE-событие `need_update` при старте
- Расширение показывает баннер «Доступно обновление»

Полезно для тестирования UI обновлений без реального релиза.

---

## Логирование

### Куда пишутся логи

| Куда | Уровень | Где найти |
|------|---------|-----------|
| Консоль (stdout) | INFO+, DEBUG с `--debug` | Терминал |
| Файл | DEBUG+ | `logs/flowlink.log` |

### Расположение файла

| Среда | Путь |
|-------|------|
| Python (из исходника) | `logs/flowlink.log` в корне проекта |
| Standalone-бинарник | `logs/flowlink.log` рядом с `.exe` |

### Ротация

5 МБ на файл, до 3 старых копий (`.log.1`, `.log.2`, `.log.3`).

> Пароли никогда не пишутся в логи — только `host:port`.

---

## API для разработчиков

Бэкенд предоставляет HTTP API на `127.0.0.1:<api-port>` (по умолчанию `8081`).

### Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/config` | Получить конфигурацию (прокси, маски, isEnabled) |
| `POST` | `/api/config` | Обновить конфигурацию. Тело — JSON-объект с `proxies[]` и `masks[]` |
| `POST` | `/api/enabled` | Установить глобальный флаг. Тело: `{"enabled": true/false}` |
| `GET` | `/api/status` | Статус gateway (proxiesCount, masksCount, debug, needUpdate) |
| `GET` | `/api/version` | Версия сервера: `{"version": "X.X.X"}` |
| `POST` | `/api/ping` | Пинг прокси. Тело: `{"proxyId": "..."}` |
| `GET` | `/api/events` | SSE-поток событий (`config_changed`, `need_update`) |

### Примеры запросов

```bash
# Получить конфигурацию
curl http://127.0.0.1:8081/api/config

# Статус
curl http://127.0.0.1:8081/api/status

# Версия
curl http://127.0.0.1:8081/api/version

# Включить глобально
curl -X POST http://127.0.0.1:8081/api/enabled \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Пинг прокси
curl -X POST http://127.0.0.1:8081/api/ping \
  -H "Content-Type: application/json" \
  -d '{"proxyId": "abc123"}'
```

### SSE-события

Подключение: `GET /api/events` (text/event-stream).

| Событие | Данные | Описание |
|---------|--------|----------|
| `config_changed` | `{}` | Конфигурация изменена (прокси, маски, тоггл) |
| `need_update` | `{"version": "X.X.X"}` | Доступно обновление |

### Структура конфигурации

```json
{
  "isEnabled": true,
  "proxies": [
    {
      "proxyId": "uuid",
      "host": "80.243.18.120",
      "port": 10000,
      "username": "user",
      "password": "encrypted_base64",
      "label": "Мой прокси",
      "isEnabled": true
    }
  ],
  "masks": [
    {
      "maskId": "uuid",
      "proxyId": "uuid",
      "regexString": "*.google.com"
    }
  ]
}
```

---

## Устранение проблем

### Бэкенд не запускается

| Причина | Решение |
|---------|---------|
| Python не найден | Установите Python 3.10+ и добавьте в PATH |
| Порт занят | `lsof -i :8080` (Linux) или Диспетчер задач (Windows) → завершите старый процесс |
| Зависимости не установлены | `pip install -r server/requirements.txt` |

### Расширение не подключается

1. Проверьте, запущен ли бэкенд
2. Проверьте порт API в настройках расширения (⚙) — должен совпадать с `--api-port`
3. Запустите с `--debug` и смотрите логи

### `ERR_PROXY_CONNECTION_FAILED`

В браузере указан SOCKS5 вместо HTTP-прокси. Проверьте флаг: `--proxy-server=127.0.0.1:8080`

### PowerShell блокирует `.ps1`

```bat
scripts\build.bat
```
Или:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

### Браузер не использует прокси

Запускайте браузер **только** через ярлык с `--proxy-server`. Если открыть браузер напрямую (без флага), трафик идёт минуя FlowLink Proxy.
