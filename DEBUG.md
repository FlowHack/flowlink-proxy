# FlowLink Proxy — Отладка и API

## Содержание

1. [Флаги CLI](#флаги-cli)
2. [Логирование](#логирование)
3. [API для разработчиков](#api-для-разработчиков)
4. [Устранение проблем](#устранение-проблем)
5. [Сборка из исходного кода](#сборка-из-исходного-кода)
6. [Скрипты и их настройка](#скрипты-и-их-настройка)
7. [Структура проекта](#структура-проекта)

---

## Флаги CLI

```bash
"FlowLink Proxy" [флаги]                          # standalone
python -m server [флаги]                           # исходный код
./scripts/setup/setup-and-run-linux.sh [флаги]     # dev-лаунчер (Linux)
./scripts/setup/setup-and-run-macos.sh [флаги]     # dev-лаунчер (macOS)
```

| Флаг | По умолч. | Описание |
|------|-----------|----------|
| `--proxy-port` | `8080` | Порт HTTP CONNECT прокси |
| `--api-port` | `8081` | Порт HTTP API для расширения |
| `--debug` | выкл. | Подробные логи в консоль и файл |
| `--dev` | выкл. | Режим разработки (подробные логи + автообновление + тестовый SOCKS5) |
| `--need-update` | выкл. | Симуляция обновления (подробные логи + баннер «Доступно обновление») |
| `--count-proxy` | `0` | Количество тестовых прокси (требует `--debug`, `--dev` или `--need-update`) |
| `--test-fallback-icon` | выкл. | Тестирование дефолтной иконки (красный круг + FLP) вместо `icons/icon.ico` |
| `--browser-path` | нет | Путь к браузеру (перезаписывает настройку из `.flowlink-settings`) |

### Примеры

```bash
# Сменить порты
"FlowLink Proxy" --proxy-port 9090 --api-port 9091

# Режим отладки
"FlowLink Proxy" --debug

# Смена портов + отладка
"FlowLink Proxy" --proxy-port 7777 --api-port 8888 --debug

# Режим разработки (автообновление + тестовый SOCKS5)
python -m server --dev

# Симуляция баннера обновления
python -m server --need-update

# Тестовые прокси + подробные логи
python -m server --debug --count-proxy 5

# Тестовые прокси + автообновление + тестовый SOCKS5
python -m server --dev --count-proxy 10

# Всё вместе: тестовые прокси + автообновление + баннер обновления
python -m server --dev --need-update --count-proxy 5

# Тестирование дефолтной иконки (красный круг + FLP)
python -m server --debug --test-fallback-icon
```

### `--debug`

Включает подробное логирование — все действия бэкенда записываются в консоль и файл `FlowLink Proxy.log` в директории данных:
- Все входящие HTTP-запросы (адрес, метод, тело)
- SOCKS5-соединения (какой прокси выбран, результат подключения)
- Маршрутизация (какая маска совпала с URL)
- Ошибки с подробным описанием (трейсбеки)

### `--dev`

Включает `--debug` плюс:
- **Автообновление** — при изменении любого `.py` файла процесс завершается (`os._exit(0)`). Для автоматического перезапуска используйте внешнюю обёртку (например, `while true; do python -m server --dev; done`)
- **Тестовый SOCKS5-сервер** — встроенный сервер-заглушка на случайном порту. Имитирует реальный SOCKS5-прокси, чтобы пинг и подключения работали без покупки аккаунта

Не предназначен для продакшена.

### `--need-update`

Включает `--debug` и симулирует наличие обновления:
- При старте отправляет специальное событие расширению
- Расширение показывает баннер «Доступно обновление» с кнопками «Помощь» и «Скачать»

Полезно для тестирования UI обновлений без реального релиза.

### `--count-proxy N`

Генерирует N фиктивных (тестовых) прокси, чтобы не покупать реальные для проверки работы расширения и маршрутизации. **Требует** `--debug` или `--dev` — без них бэкенд выдаст ошибку.

Как это работает:
- При старте создаётся N тестовых прокси-аккаунтов со случайными адресами, логинами и паролями
- Каждому прокси автоматически создаётся маска (шаблон маршрутизации), чтобы трафик шёл через него
- Все тестовые прокси сразу включены и видны в расширении — можно переключать, пинговать, удалять
- При первом запуске логин/пароль будут помечены как «ошибка расшифровки» — это нормально, тестовые аккаунты не шифруются

> **Важно:** Тестовые прокси записываются в `config.json` и остаются там после перезапуска. Чтобы убрать их — удалите через расширение или API.

```bash
# 5 тестовых прокси + подробные логи
python -m server --debug --count-proxy 5

# 10 тестовых прокси + автообновление + тестовый SOCKS5-сервер
python -m server --dev --count-proxy 10

# 3 тестовых прокси + баннер «Доступно обновление»
python -m server --need-update --count-proxy 3
```

### Отказоустойчивость меню трея

Меню трея автоматически переключается на запасной вариант, если основной не удалось создать.

Цепочка отказоустойчивости:

1. **Основной трей** — платформенный бэкенд: Win32 ctypes + tkinter popup (Windows) или pystray + tkinter popup (Linux/macOS)
2. **Завершение** — если трей не запустился, в лог записывается критическая ошибка `Не удалось запустить трей (запуск): Системный трей недоступен`. В standalone-сборке приложение завершается с кодом 1, при запуске из исходников — только предупреждение в лог

Для работы трея и диалогов бэкенда обязателен **tkinter**. Если tkinter недоступен, трей не запускается, а диалоги (выбор браузера, предупреждения) не отображаются. Установите tkinter для вашей ОС (Linux: `sudo apt install python3-tk`).

Поведение при падении popup: если во время показа меню происходит ошибка рендера (например, 
tkinter `TclError`), бэкенд не падает — ошибка перехватывается и записывается в лог с полным 
трейсбеком (`exc_info`), меню просто не отображается.

Как диагностировать:

- Запустите с `--debug` и смотрите `FlowLink Proxy.log` в директории данных
- При сбое трея в логе появится строка:
  - `Основной трей не запустился (runtime ошибка): ...`
- Если приложение сразу завершается — ищите в логе строку с `critical` и причину отказа

### `--test-fallback-icon`

Принудительно использует **дефолтную иконку** (красный круг с «FLP») вместо `icons/icon.ico`. Иконка генерируется через Pillow при запуске и сохраняется во временный `.ico` файл.

Используется для:
- **Тестирования дефолтной иконки** — проверить как выглядит красный круг + «FLP» в трее
- **Диагностики проблем с иконкой** — если `icons/icon.ico` не загружается (неправильный формат, отсутствует, повреждён)
- **Отладки без иконки** — проверить поведение при отсутствии `icons/icon.ico`

На standalone-сборках без `icons/icon.ico` рядом с бинарником:
- При запуске **без** этого флага — автоматически создастся дефолтная иконка (красный круг + FLP)
- При запуске **с** этим флагом — будет использована дефолтная иконка и в логе будет `INFO: Tray Win32: --test-fallback-icon, пропуск icon.ico`

```bash
# Тестирование дефолтной иконки
python -m server --test-fallback-icon

# С отладкой
python -m server --debug --test-fallback-icon
```

---

Все флаги можно комбинировать. Вот полная таблица совместимости:

| Комбинация | Результат |
|------------|-----------|
| `--debug` | Подробные логи в консоль и файл |
| `--dev` | Подробные логи + автообновление при изменении файлов + встроенный тестовый SOCKS5-сервер |
| `--need-update` | Подробные логи + при старте расширение покажет баннер «Доступно обновление» |
| `--count-proxy N` | Генерирует N тестовых прокси. **Одиночно не работает** — требует `--debug`, `--dev` или `--need-update` |
| `--dev --count-proxy N` | Тестовые прокси + автообновление + тестовый SOCKS5. Удобно для отладки расширения |
| `--need-update --count-proxy N` | Тестовые прокси + баннер обновления. Удобно для проверки UI обновлений |
| `--dev --need-update --count-proxy N` | Всё вместе: тестовые прокси + автообновление + тестовый SOCKS5 + баннер обновления |
| `--test-fallback-icon` | Использует дефолтную иконку (красный круг + FLP) вместо `icons/icon.ico` |
| `--proxy-port 9090 --api-port 9091` | Кастомные порты (работает с любыми другими флагами) |

Примеры:

```bash
# Минимальный вариант: подробные логи + тестовые прокси
python -m server --debug --count-proxy 3

# Полный набор для разработки
python -m server --dev --need-update --count-proxy 5

# Кастомные порты + тестовые прокси
python -m server --proxy-port 9090 --api-port 9091 --debug --count-proxy 3

# Тестирование дефолтной иконки + отладка
python -m server --debug --test-fallback-icon
```

---

### Автообнаружение порта

Если бэкенд запущен на нестандартном порту (например, `--api-port 9091`), расширение автоматически найдёт его при открытии:

1. Проверяет сохранённый порт (из настроек расширения)
2. Если не отвечает — сканирует порты 8080–8090 параллельно
3. Нашёл — автоматически подключается и сохраняет порт в настройках

Бэкенд при старте также записывает фактические порты в файл `.flowlink-port` (JSON) в директории данных — для отладки и внешних скриптов.

> **Совет:** Для повседневной работы настройка порта не требуется — расширение найдёт бэкенд автоматически. Ручная настройка нужна только если бэкенд работает за пределами диапазона 8080–8090.

---

## Логирование

### Куда пишутся логи

| Куда | Уровень | Где найти |
|------|---------|-----------|
| Консоль (stdout) | INFO+, DEBUG с `--debug` | Терминал |
| Файл | DEBUG+ | `FlowLink Proxy.log` в директории данных |

### Расположение файла

| Среда | Путь |
|-------|------|
| Linux / macOS | `~/.FlowHack/FlowLink Proxy/logs/FlowLink Proxy.log` |
| Windows | `%APPDATA%\FlowHack\FlowLink Proxy\logs\FlowLink Proxy.log` |

> Standalone-бинарник пишет логи в ту же директорию данных, что и запуск из исходников.

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
| `POST` | `/api/config` | Обновить конфигурацию. Тело — JSON-объект с `proxies[]` и `masks[]`. При конфликте масок (включено более одного прокси из группы с пересекающимися масками) возвращает `422` с `{"error": "...", "conflict": {...}}` |
| `POST` | `/api/enabled` | Установить глобальный флаг. Тело: `{"enabled": true/false}` |
| `POST` | `/api/rotate-key` | Ротация ключа шифрования AES-GCM (перешифровывает пароли). При сбое — откат к старой паре ключ/соль |
| `GET` | `/api/status` | Статус backend (proxiesCount, masksCount, debug, needUpdate, isEnabled, status, cryptoHealthy) |
| `GET` | `/api/version` | Версия сервера: `{"version": "X.X.X"}` |
| `GET` | `/api/language` | Текущий язык интерфейса: `{"language": "ru"}` |
| `POST` | `/api/language` | Установить язык интерфейса (ru/en/sr). Тело: `{"language": "ru"}` |
| `GET` | `/api/bootstrap` | Токен и порт API для расширения (открытый, без токена): `{"token": "...", "apiPort": 8081}` |
| `POST` | `/api/ping` | Пинг прокси. Тело: `{"proxyId": "..."}` |
| `GET` | `/api/events` | SSE-поток событий (`config_changed`, `need_update`, `autostart_browser_changed`, `system_autostart_changed`, `browser_config_changed`, `backend_error`, `backend_ready`, `language_changed`) |
| `GET` | `/api/autostart-browser` | Автозапуск браузера: `{"autostartBrowser": true/false}` |
| `GET` | `/api/system-autostart` | Статус автозапуска с системой |
| `POST` | `/api/system-autostart` | Включить/выключить автозапуск с системой. Тело: `{"enabled": true/false}` |
| `GET` | `/api/browser-path` | Текущий путь к браузеру: `{"browserPath": "..."}` |
| `POST` | `/api/browser-path` | Сохранить путь к браузеру. Тело: `{"browserPath": "..."}` (возвращает 422 при невалидном пути) |
| `POST` | `/api/validate-browser` | Валидация пути к браузеру без сохранения. Тело: `{"browserPath": "..."}` |
| `GET` | `/api/detected-browsers` | Список найденных браузеров (автопоиск) |
| `GET` | `/api/browser-config` | Конфигурация браузера (path + autostart + detected) |
| `POST` | `/api/proxies` | Добавить прокси. Тело: `{"host": "...", "port": 1080, "username": "...", "password": "...", "label": "..."}`. Дубликат host:port → 422, невалидный port → 400 |
| `PATCH` | `/api/proxy/{id}` | Обновить поля прокси (host, port, username, password, label). Несуществующий → 404, дубликат host:port → 422 |
| `PATCH` | `/api/proxy/{id}/enabled` | Переключить активность прокси. Тело: `{"enabled": true/false}`. Конфликт масок при включении → 422 |
| `DELETE` | `/api/proxy/{id}` | Удалить прокси и связанные маски. Несуществующий → 404 |
| `POST` | `/api/masks` | Добавить маску. Тело: `{"pattern": "*.com", "regexString": ".*\\.com", "proxyId": "..."}`. regexString генерируется из pattern, если не передан. Конфликт → 422 |
| `PATCH` | `/api/mask/{id}` | Обновить маску (pattern, regexString). regexString пересчитывается из pattern, если не передан. Несуществующая → 404 |
| `DELETE` | `/api/mask/{id}` | Удалить маску. Несуществующая → 404 |

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
| `autostart_browser_changed` | `{"autostartBrowser": true/false}` | Изменена настройка автозапуска браузера |
| `system_autostart_changed` | `{"enabled": true/false}` | Изменена настройка автозапуска с системой |
| `browser_config_changed` | `{"browserPath": "..."}` | Изменён выбранный браузер |
| `backend_error` | `{"message": "..."}` | Ошибка бэкенда (например, не удалось сохранить конфиг) |
| `backend_ready` | `{}` | Бэкенд готов (отправляется при подключении SSE-клиента, в т.ч. после перезапуска) |
| `language_changed` | `{"language": "ru"}` | Изменён язык интерфейса |

### Структура конфигурации

```json
{
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
      "pattern": "*google.com*",
      "regexString": ".*google\\.com.*"
    }
  ],
  "lastActiveProxyId": "uuid"
}
```

> `isEnabled` (глобальный тоггл) хранится только в памяти и в config.json не пишется.
> `lastActiveProxyId` — id последнего включённого прокси, восстанавливается при запуске.
> Маска содержит `pattern` (wildcard-шаблон для UI) и `regexString` (сконвертированный regex для маршрутизации).

Файл `.flowlink-settings` (JSON) в директории данных содержит:

- `autostart_browser` — флаг автозапуска браузера при старте бэкенда (true/false)
- `browser_path` — путь к исполняемому файлу браузера
- `parallel_launch` — флаг параллельного запуска браузера (не ждать закрытия предыдущего)
- `language` — язык интерфейса (`ru`/`en`/`sr`)

> Директория данных задаётся переменной окружения `FLOWLINK_DATA_DIR` (по умолчанию `~/.FlowHack/FlowLink Proxy`).

---

## Устранение проблем

Общие проблемы установки и запуска (бэкенд не запускается, расширение не подключается, `ERR_PROXY_CONNECTION_FAILED`, занятый порт и т.д.) — см. [SETUP.md](SETUP.md#устранение-проблем-при-установке). Ниже — только dev-специфичные случаи.

### PowerShell блокирует `.ps1`

```bat
scripts\build\build.bat
```
Или:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\build\build.ps1
```

### Меню трея не отображается или падает

| Симптом | Причина и решение |
|---------|-------------------|
| Меню не открывается, в логе ошибка рендера | Ошибка tkinter-рендера. Бэкенд продолжает работать — смотрите трейсбек в `FlowLink Proxy.log` в директории данных |
| Приложение сразу завершается при запуске | Трей не запустился. В логе: `critical: Не удалось запустить трей (запуск): Системный трей недоступен`. Проверьте установку tkinter (`python -m tkinter`) и pystray (`pip show pystray`) |
| tkinter недоступен | Установите пакет tkinter для вашей ОС (Linux: `sudo apt install python3-tk`, macOS: `brew install python-tk`) |

---

## Сборка из исходного кода

Этот раздел для разработчиков и сборщиков пакетов.

### Сборка standalone-бинарника

```bash
# Linux / macOS
./scripts/build/build.sh

# Windows
scripts\build\build.bat
```

Результат: `releases/FlowLink Proxy` (Linux/macOS) или `releases\FlowLink Proxy\FlowLink Proxy.exe` (Windows, onedir)

### Упаковка архива релиза (Linux / macOS)

```bash
./scripts/build/build.sh
./scripts/build/create-release.sh
```

Скрипт `create-release.sh` создаёт в папке `releases/`:
- `FlowLink-Proxy-vX.X.X-linux-x64.tar.gz`
- (на macOS: `...-macos-x64.tar.gz` или `...-macos-arm64.tar.gz`)

Внутри архива: бинарник, лаунчер, установщик `install.sh`, папка `scripts/autostart/` (шаблоны автозапуска), `EULA.rtf`, `LICENSE.txt`, `README.md`. SETUP.md и DEBUG.md в архив не попадают.

### Сборка .deb-пакета (Linux)

```bash
./scripts/build/build.sh
./scripts/build/build-deb.sh
```

Результат: `releases/FlowLink-Proxy_<версия>_<арх>.deb`

### Сборка .rpm-пакета (Linux)

```bash
./scripts/build/build.sh
./scripts/build/build-rpm.sh
```

Результат: `~/rpmbuild/RPMS/x86_64/FlowLink-Proxy-<версия>-1.x86_64.rpm`

### Сборка .pkg-пакета (macOS)

```bash
./scripts/build/build.sh
./scripts/build/build-pkg.sh
```

Результат: `releases/FlowLink-Proxy-<версия>-macos-<арх>.pkg`

### Сборка установщика Windows

1. Установите [Inno Setup](https://jrsoftware.org/isdl.php) (последнюю стабильную **6**, не бета 7)
2. Соберите бинарник: `scripts\build\build.bat`
3. Откройте `scripts/installer/flowlink-installer.iss` в Inno Setup → Build → Compile
4. Результат: `releases/FlowLink-Proxy-vX.X.X-Setup.exe`

> **Архитектура:** Inno Setup соберёт установщик под x64. В .iss уже указано `ArchitecturesInstallIn64BitMode=x64compatible` — автоматически выбирает правильную Program Files папку (32 или 64 бит).

---

## Скрипты и их настройка

### Сводная таблица переменных

| Скрипт | Переменная | По умолч. | Описание |
|--------|------------|-----------|----------|
| `launcher/FlowLink Proxy-linux.sh` | — | — | Лаунчер запускает бинарник напрямую. Браузер выбирается через трей-меню или расширение |
| `launcher/FlowLink Proxy-macos.sh` | — | — | Лаунчер запускает бинарник напрямую. Браузер выбирается через трей-меню или расширение |
| `setup/setup-and-run-linux.sh` | — | — | Dev-скрипт: venv + зависимости + запуск `python -m server` |
| `setup/setup-and-run-macos.sh` | — | — | Dev-скрипт: venv + зависимости + запуск `python -m server` |
| `setup/setup-and-run.bat` | — | — | Dev-скрипт Windows: venv + зависимости + запуск `python -m server` |
| `crx/build-crx.sh` / `build-crx.ps1` | — | — | Сборка расширения: `.crx` и `.zip` |
| `install/` | — | — | Установочные файлы/шаблоны для релизных пакетов |
| `autostart/flowlink.service` | `ExecStart` | — | Путь к бинарнику (настраивается вручную) |
| `autostart/flowlink.service` | `FLOWLINK_DATA_DIR` | `%h/.FlowHack/FlowLink Proxy` | Папка данных |
| `autostart/flowlink.desktop` | `Exec` | — | Путь к бинарнику (настраивается вручную; пробел экранируется как `\ `) |

### Скрипты запуска

| Скрипт | Платформа | Назначение |
|--------|-----------|------------|
| `launcher/FlowLink Proxy-linux.sh` | Linux | Лаунчер: запускает бинарник напрямую |
| `launcher/FlowLink Proxy-macos.sh` | macOS | Лаунчер: запускает бинарник напрямую |
| `setup/setup-and-run-linux.sh` | Linux | Dev-скрипт: venv + зависимости + запуск `python -m server` |
| `setup/setup-and-run-macos.sh` | macOS | Dev-скрипт: venv + зависимости + запуск `python -m server` |
| `setup/setup-and-run.bat` | Windows | Dev-скрипт: venv + зависимости + запуск `python -m server` |

### Файлы автозапуска

| Файл | Платформа | Назначение |
|------|-----------|------------|
| `autostart/flowlink.service` | Linux (systemd) | Автозапуск бэкенда как сервис |
| `autostart/flowlink.desktop` | Linux (GNOME/KDE) | Ярлык в меню приложений |
| `autostart/com.flowlink.proxy.plist` | macOS (launchd) | Автозапуск бэкенда |

---

## Структура проекта

```
flowlink-proxy/
├── server/                    # Python-бэкенд
│   ├── __main__.py            # Точка входа (CLI + tray icon)
│   ├── version.py             # Версия проекта
│   ├── logging_config.py      # Настройка логгера (файл + консоль)
│   ├── i18n.py                # Локализация бэкенда (ru/en/sr)
│   ├── locales/               # Переводы бэкенда (gettext)
│   │   ├── en/                # Английский (LC_MESSAGES)
│   │   └── sr/                # Сербский (LC_MESSAGES)
│   ├── tray/                  # System tray icon (tkinter / pystray / ctypes)
│   │   ├── __init__.py        # Координатор: start_tray()
│   │   ├── platform.py        # Определение ОС и возможностей
│   │   ├── popup.py           # Tkinter безрамочное меню (тёмная тема)
│   │   ├── menu.py            # Общая логика построения меню
│   │   ├── pystray_base.py    # Базовый класс pystray-трея
│   │   ├── win32.py           # Win32 Tray (ctypes)
│   │   ├── linux.py           # Linux Tray (pystray + tkinter)
│   │   └── macos.py           # macOS Tray (pystray + tkinter)
│   ├── config/
│   │   ├── config.py          # Бизнес-логика конфига (proxies, masks, enabled)
│   │   ├── repo.py            # Чтение/запись config.json
│   │   ├── crypto.py          # AES-GCM шифрование паролей (PBKDF2)
│   │   ├── autostart.py       # Настройки автозапуска браузера
│   │   ├── browser_config.py  # Конфигурация браузера (автопоиск, валидация, запуск)
│   │   ├── browser_process.py # Управление процессами браузера (поиск PID, kill)
│   │   └── system_autostart.py # Автозапуск с системой (Win/Linux/macOS)
│   ├── protocols/
│   │   ├── base.py            # ABC ProxyProtocol
│   │   ├── socks5.py          # SOCKS5-клиент (чистый asyncio + struct)
│   │   ├── factory.py         # Фабрика протоколов
│   │   ├── parser.py          # Парсинг CONNECT/HTTP-запросов
│   │   ├── mock_socks5.py     # Тестовый SOCKS5-сервер (--dev)
│   │   └── socks5_constants.py # Константы SOCKS5-протокола
│   ├── services/
│   │   ├── router.py          # Маршрутизация URL по маскам
│   │   ├── tunnel.py          # Установка туннелей (SOCKS5 / прямой) + SSRF-защита
│   │   ├── pipe.py            # Двусторонняя пересылка данных
│   │   ├── ping.py            # Пинг прокси (SOCKS5 handshake)
│   │   ├── debug.py           # Debug-утилиты
│   │   ├── events.py          # SSE-шина событий
│   │   ├── sse.py             # SSE-обработчик (text/event-stream)
│   │   ├── extension_connection.py # Отслеживание подключения расширения
│   │   ├── fake_proxies.py    # Генерация тестовых прокси (--count-proxy)
│   │   └── mask_conflicts.py  # Проверка конфликтов масок (пересечение паттернов)
│   ├── servers/
│   │   ├── base_server.py     # ABC BaseServer
│   │   ├── proxy.py           # HTTP CONNECT прокси (порт 8080)
│   │   ├── api.py             # HTTP API (порт 8081)
│   │   └── handlers.py        # Обработчики API-эндпоинтов
│   ├── ui/
│   │   ├── dialogs.py         # Кастомные tkinter-диалоги (show_info, show_item_picker)
│   │   └── theme.py           # Тёмная тема для диалогов
│   ├── utils.py               # Утилиты (get_data_dir, clear_all_data, write_port_file)
│   ├── icons/                 # Иконки бэкенда (icon.ico, icon1024.png)
│   ├── requirements.txt       # Зависимости Python
│   └── tests/                 # Юнит-тесты
│       ├── base.py            # Базовые миксины (TempConfigMixin)
│       ├── conftest.py        # Общие вспомогательные функции
│       ├── test_config.py
│       ├── test_crypto.py
│       ├── test_handlers.py
│       ├── test_events.py
│       ├── test_proxy_server.py
│       ├── test_router.py
│       ├── test_socks5.py
│       ├── test_tunnel.py     # SSRF-защита validate_target()
│       ├── test_utils.py
│       ├── test_autostart.py
│       ├── test_browser_config.py
│       ├── test_fake_proxies.py
│       ├── test_system_autostart.py
│       ├── test_tray_menu.py
│       ├── test_tray_platform.py
│       ├── test_tray_popup.py
│       ├── test_tray_fallback.py
│       ├── test_main_launch_browser.py
│       ├── test_main_autostart.py
│       ├── test_main_close_browser.py
│       ├── test_extension_timeout.py
│       ├── test_extension_connection.py
│       ├── test_dialogs.py
│       ├── test_build_scripts.py
│       ├── test_browser_process.py
│       └── test_api_routes.py
│
├── extension/                 # Chrome-расширение (Manifest V3)
│   ├── manifest.json          # Манифест расширения
│   ├── _locales/              # Локализация расширения (ru/en/sr)
│   ├── background/
│   │   └── service-worker.js  # SSE-клиент + pushEnabledState
│   ├── popup/
│   │   ├── popup.html         # Главное окно
│   │   ├── popup.css          # Стили
│   │   ├── popup.js           # Главный контроллер
│   │   ├── crud-proxy.js      # CRUD-операции с прокси
│   │   ├── crud-mask.js       # CRUD-операции с масками
│   │   ├── draft.js           # Черновики форм (chrome.storage.session)
│   │   ├── ping.js            # Пинг прокси
│   │   ├── settings.js        # Настройки порта API
│   │   ├── tab-status.js      # Статус текущей вкладки
│   │   ├── modal.js           # Модальные окна
│   │   ├── help.js            # Окно помощи
│   │   ├── help-page.js       # Логика статической справки (help.html)
│   │   ├── help.css           # Стили справки
│   │   ├── help.html          # Статическая справка (открывается из tkinter-диалога)
│   │   └── updater.js         # Проверка обновлений
│   ├── shared/
│   │   ├── api.js             # HTTP хелперы (apiGet, apiPost, apiPatch, apiDelete, apiPostRaw)
│   │   ├── auth.js            # Работа с токеном авторизации API
│   │   ├── constants.js       # API_BASE, GitHub URLs
│   │   ├── dom.js             # escapeHtml, утилиты DOM
│   │   ├── i18n.js            # Словарь переводов (RU/EN/SR)
│   │   ├── utils.js           # Валидация IP/port, wildcard→regex, copyEmailToClipboard
│   │   └── port_discovery.js  # Автообнаружение порта API
│   ├── tests/                 # Тесты расширения
│   │   ├── auth.test.js       # Тесты токена авторизации
│   │   ├── draft.test.js      # Тесты черновиков форм
│   │   ├── help.test.js       # Тесты логики вкладок справки
│   │   └── port.test.js       # Тесты автообнаружения порта
│   └── icons/                 # Иконки расширения
│
├── scripts/
│   ├── installer/
│   │   └── flowlink-installer.iss  # Inno Setup установщик Windows
│   ├── icons/
│   │   ├── icon.ico            # Иконка для установщика и ярлыков
│   │   ├── icon1024.png        # Иконка для Linux/macOS
│   │   └── icon.icns           # Иконка для macOS
│   ├── launcher/
│   │   ├── FlowLink Proxy-linux.sh  # Linux-лаунчер (только бинарник)
│   │   └── FlowLink Proxy-macos.sh  # macOS-лаунчер (только бинарник)
│   ├── setup/
│   │   ├── setup-and-run.bat         # Windows: проверка Python+tkinter + запуск
│   │   ├── setup-and-run-linux.sh    # Linux: проверка Python+tkinter + запуск
│   │   └── setup-and-run-macos.sh    # macOS: проверка Python+tkinter + запуск
│   ├── build/
│   │   ├── build.bat              # Windows: обёртка для build.ps1
│   │   ├── build.ps1              # Windows: сборка standalone onedir (PyInstaller)
│   │   ├── build.sh               # Linux/macOS: сборка standalone (PyInstaller)
│   │   ├── build-deb.sh           # Linux: сборка .deb-пакета
│   │   ├── build-rpm.sh           # Linux: сборка .rpm-пакета
│   │   ├── flowlink.spec          # RPM-спецификация
│   │   ├── build-pkg.sh           # macOS: сборка .pkg-пакета
│   │   └── create-release.sh      # Упаковка архивов релиза
│   ├── crx/
│   │   ├── build-crx.sh           # Linux/macOS: сборка CRX-расширения
│   │   ├── build-crx.ps1          # Windows: сборка CRX-расширения
│   │   └── crx-private-key.pem    # Приватный ключ подписи CRX (не коммитится)
│   ├── install/
│   │   └── install.sh             # Универсальный standalone-установщик
│   └── autostart/
│       ├── flowlink.service       # Linux: systemd-сервис
│       ├── flowlink.desktop       # Linux: десктоп-файл
│       └── com.flowlink.proxy.plist # macOS: LaunchAgent
│
├── AI_DEV_LOG.md              # Журнал разработки (локально, не комиттится)
├── SETUP.md                   # Подробная установка и настройка
├── DEBUG.md                   # Отладка, CLI-флаги, API
├── PRIVACY_POLICY.md          # Политика конфиденциальности
├── README.md                  # Этот файл
├── EULA.rtf                   # Лицензионное соглашение конечного пользователя
└── LICENSE.txt                # GNU AGPL v3
```
