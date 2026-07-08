# FlowLink Proxy

Автоматическая маршрутизация трафика в Chrome: сайты по маскам → через SOCKS5-прокси с паролем, остальные → напрямую.

> **Зачем?** Chrome не умеет передавать логин/пароль в SOCKS5. FlowLink Proxy делает SOCKS5-туннель на своей стороне, а Chrome просто работает через HTTP-прокси `localhost:8080` — без пароля.

---

## Быстрый старт (2 минуты)

### 1. Запустите gateway

**Вариант А — через Python (если установлен Python 3.10+):**

```bash
git clone https://github.com/flowhack/flowlink-proxy.git
cd flowlink-proxy
./scripts/flowlink.sh
```

Скрипт сам создаст виртуальное окружение, установит зависимости и запустит сервер.

**Вариант Б — standalone-бинарник (Python не нужен):**

1. Скачайте `FlowLink Proxy` (Linux/macOS) или `FlowLink Proxy.exe` (Windows) со [страницы релизов](https://github.com/flowhack/flowlink-proxy/releases)
2. Дайте права на запуск (Linux/macOS): `chmod +x FlowLink Proxy`
3. Запустите: `./"FlowLink Proxy"` или `FlowLink Proxy.exe`

> Бинарник собран через PyInstaller — в нём уже есть Python и все зависимости.

### 2. Установите расширение в Chrome

1. Откройте `chrome://extensions`
2. Включите **«Режим разработчика»** (правый верхний угол)
3. Нажмите **«Загрузить распакованное расширение»**
4. Выберите папку `extension/` внутри `flowlink-proxy`

### 3. Настройте браузер на прокси

Браузер нужно направить на HTTP-прокси `127.0.0.1:<прокси_порт>` (по умолчанию порт `8080`).  
Самый надёжный способ — **флаг `--proxy-server` в ярлыке** — он не затрагивает другие приложения.

> Флаг работает в Chrome, Яндекс Браузере, Opera, Edge и любом Chromium-браузере.

#### Windows: ярлык браузера

1. Найдите ярлык браузера на рабочем столе или в меню «Пуск»
2. Правый клик → **Свойства**
3. В поле **«Объект»** допишите **после закрывающей кавычки** через пробел:

```
"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe" --proxy-server=127.0.0.1:8080
```

4. Нажмите «Применить» → «ОК»
5. Запускайте браузер только через этот ярлык

Для Chrome путь обычно такой:
```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --proxy-server=127.0.0.1:8080
```

#### Linux / macOS: терминал

```bash
google-chrome --proxy-server=127.0.0.1:8080
# или
yandex-browser --proxy-server=127.0.0.1:8080
```

#### Linux: системный прокси (все приложения)

```bash
gsettings set org.gnome.system.proxy.http host '127.0.0.1'
gsettings set org.gnome.system.proxy.http port 8080
gsettings set org.gnome.system.proxy.https host '127.0.0.1'
gsettings set org.gnome.system.proxy.https port 8080
gsettings set org.gnome.system.proxy mode 'manual'
```

> **Важно:** порт в `--proxy-server` должен совпадать с портом, который слушает FlowLink Proxy (`--proxy-port`, по умолч. 8080). Если вы сменили порт — укажите его там.

> **Важно:** Python принимает HTTP CONNECT, браузер ничего не знает про SOCKS5. Пароль тоже не указывается — SOCKS5-аутентификацию делает Python.

> **Важно про порты:** По умолчанию используются порты `8080` (прокси) и `8081` (API). Если они заняты — см. раздел «Настройка портов» ниже.

---

## Как это работает

```
Chrome → HTTP CONNECT localhost:8080 (без пароля)
                │
        Python-шлюз (server/)
                │
     ┌──────────┴──────────┐
     ▼                      ▼
URL совпал с маской?   Нет совпадения?
     │                      │
     ▼                      ▼
SOCKS5 c паролем      Прямое соединение
(ваш сервер)          (Happ / обычный интернет)
```

- **Прокси-сервер** (`:8080`) — принимает HTTP CONNECT от Chrome
- **API-сервер** (`:8081`) — расширение читает/пишет настройки
- **Расширение** — только интерфейс для добавления прокси и масок

---

## Использование расширения

После установки нажмите на иконку FlowLink в панели расширений Chrome:

1. **Добавить прокси** — введите IP, порт, логин и пароль вашего SOCKS5-сервера
2. **Добавить маску** — можно через `*` (например `*gemini.google.com*` или `*.google.com`) или regex
3. **Включить/выключить** — глобальный переключатель и отдельно для каждого прокси
4. **Пинг** — проверить доступность прокси-сервера
5. **Настройка порта API** — нажмите ⚙ рядом с версией, чтобы изменить порт подключения к Python gateway

---

## Обновление

FlowLink Proxy уведомляет о новой версии баннером в расширении.

### Как обновить

**Если используете standalone-бинарник (.exe):**

1. Скачайте последний релиз со [страницы релизов](https://github.com/flowhack/flowlink-proxy/releases/latest)
2. Распакуйте ZIP, замените старый `FlowLink Proxy.exe` новым
3. Остановите старый процесс и запустите новый

**Если используете исходный код (Python):**

```bash
cd flowlink-proxy
git pull
python -m server
```

**Если используете unpacked-расширение:**

1. Откройте `chrome://extensions`
2. Нажмите «Обновить» (круглая стрелка) или переустановите расширение

> Бэкенд и расширение должны быть одной версии. Сначала обновите бэкенд, потом расширение.

### Как отключить уведомления

Уведомления об обновлениях приходят только для стабильных релизов (GitHub releases).  
Если вы запускаете Python с флагом `--debug`, уведомления автоматически отключаются.

---

## Автозапуск (Linux)

**Через systemd (для standalone-бинарника):**

```bash
# Отредактируйте путь к бинарнику в scripts/flowlink.service при необходимости
systemctl --user enable "$PWD/scripts/flowlink.service"
systemctl --user start flowlink.service
```

**Через автозагрузку (для Python-версии):**
Добавьте `./flowlink.sh` в автозагрузку вашей системы.

---

## Сборка standalone-бинарника

Если у вас есть Python, вы можете собрать бинарник сами:

```bash
# Linux / macOS
./scripts/build.sh
# Результат: "server/FlowLink Proxy/FlowLink Proxy"
# Запуск: ./"server/FlowLink Proxy"/"FlowLink Proxy"

# Windows (PowerShell)
scripts\build.bat
# или напрямую:
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
# Результат: "server\FlowLink Proxy\FlowLink Proxy.exe"
# Запуск: .\server\"FlowLink Proxy"\FlowLink Proxy.exe
```

---

## Флаги запуска

| Флаг | По умолч. | Описание |
|------|-----------|----------|
| `--proxy-port` | `8080` | Порт HTTP CONNECT прокси (браузер подключается сюда) |
| `--api-port` | `8081` | Порт HTTP API для расширения |
| `--debug` | выкл. | Подробные логи в консоль (SOCKS5 handshake, все маршруты) |

### Примеры

```bash
# Только сменить порты
"FlowLink Proxy" --proxy-port 9090 --api-port 9091

# Режим отладки
"FlowLink Proxy" --debug

# Сменить порт прокси и включить отладку
"FlowLink Proxy" --proxy-port 7777 --api-port 8888 --debug
```

Для Python-версии флаги те же:
```bash
python -m server --proxy-port 9090 --api-port 9091 --debug
./scripts/flowlink.sh --proxy-port 9090 --api-port 9091
```

### Windows: ярлык для gateway

Создайте ярлык для `FlowLink Proxy.exe`, откройте его свойства и в поле «Объект» допишите флаги **после закрывающей кавычки**:
```
"C:\FlowLink\FlowLink Proxy.exe" --proxy-port 9090 --api-port 9091
```

---

## Настройка портов

Если порт по умолчанию занят — смените его флагами `--proxy-port` и `--api-port` (см. раздел «Флаги запуска» выше).

**После смены порта обязательно сделайте три вещи:**

1. **Обновите флаг браузера:** `--proxy-server=127.0.0.1:<новый_прокси_порт>`
2. **Укажите тот же API-порт в расширении** (см. ниже) — иначе расширение не подключится к gateway
3. **Перезапустите gateway**

### Настройка порта API в расширении

1. Нажмите на иконку FlowLink Proxy → найдите шестерёнку ⚙ рядом с версией
2. Нажмите ⚙ — появится строка «Порт API»
3. Введите новый порт и нажмите «Сохранить»
4. Расширение перезагрузит данные с новым портом

> Порт сохраняется в `chrome.storage.local` и сохраняется после перезапуска браузера.

### Устранение проблем с портами

Если при запуске gateway вы видите ошибку `address already in use`:

```bash
# Linux / macOS — кто занял порт?
lsof -i :8080
lsof -i :8081

# Принудительно завершить старый FlowLink
pkill -f "FlowLink Proxy"
pkill -f "python -m server"
```

**Windows:** Диспетчер задач → Процессы → найдите `FlowLink Proxy.exe` или `python.exe` → Снять задачу.

---

## Структура проекта

```
flowlink-proxy/
├── server/                 # Python-бэкенд (пакет)
│   ├── __init__.py         # Экспорт версии
│   ├── __main__.py         # Точка входа
│   ├── version.py          # Каноническая версия проекта
│   ├── proxy.py            # HTTP CONNECT прокси (:8080)
│   ├── api.py              # HTTP API (:8081)
│   ├── socks5.py           # SOCKS5 клиент (asyncio, без зависимостей)
│   ├── router.py           # Маршрутизация по маскам
│   ├── config.py           # Загрузка/сохранение config.json
│   ├── crypto.py           # AES-GCM шифрование паролей
│   └── requirements.txt    # Зависимости (только cryptography)
├── scripts/                # Вспомогательные скрипты
│   ├── build.sh            # Сборка standalone-бинарника (Linux/macOS)
│   ├── build.bat           # Обёртка для build.ps1 (обходит ExecutionPolicy)
│   ├── build.ps1           # Сборка standalone-бинарника (Windows)
│   ├── flowlink.sh         # Лаунчер (venv + запуск, Linux/macOS)
│   ├── flowlink.service    # systemd-сервис
│   └── flowlink.desktop    # Десктоп-файл для меню приложений
├── extension/              # Chrome-расширение
│   ├── manifest.json
│   ├── background/service-worker.js
│   ├── popup/popup.{html,css,js}
│   └── icons/
├── server/FlowLink Proxy/  # Готовый бинарник (после сборки)
├── config.json             # Конфигурация (пароли зашифрованы)
└── README.md
```

---

## API (для разработчиков)

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/config` | Получить конфигурацию |
| `POST` | `/api/config` | Обновить конфигурацию |
| `GET` | `/api/status` | Статус gateway |
| `GET` | `/api/version` | Версия gateway |
| `POST` | `/api/ping` | Пинг прокси `{"proxyId": "..."}` |

---

## Требования

- **Вариант А (через Python):** Python 3.10+, pip
- **Вариант Б (standalone):** ничего
- **Chrome:** версия 100+ (для Manifest V3)
- **ОС:** Linux, macOS, Windows (WSL)

---

## Безопасность

- Пароли шифруются AES-GCM-256 перед записью в `config.json`
- Мастер-ключ хранится в `.flowlink.key` (права доступа 600)
- Пароли никогда не логируются
- Chrome не имеет доступа к паролям — вся аутентификация в Python
- **Standalone-бинарник:** `config.json` и `.flowlink.key` лежат рядом с `FlowLink Proxy.exe` — достаточно просто положить `.exe` в отдельную папку

---

## Логи

FlowLink Proxy пишет логи в два места:

| Куда | Уровень | Где найти |
|------|---------|-----------|
| **Консоль** (stdout) | INFO+, DEBUG с `--debug` | Терминал, в котором запущен gateway |
| **Файл** (ротация) | DEBUG+ | См. ниже |

**Расположение файла `flowlink.log`:**

- **Python-версия** (`./scripts/flowlink.sh` / `python -m server`) — `logs/flowlink.log` в корне проекта
- **Standalone-бинарник** (`.exe` / `FlowLink Proxy`) — `logs/flowlink.log` рядом с самим бинарником

Файл ротируется: 5 МБ на файл, до 3 старых копий (`flowlink.log.1`, `.2`, `.3`).

**Режим отладки:** `--debug` — подробные логи в консоль + файл (все запросы, SOCKS5 handshake, ошибки).

> **Важно:** пароли никогда не пишутся в логи. В логах фигурирует только `host:port` прокси.

---

## Устранение проблем

**Расширение показывает «Ошибка соединения»** → gateway не запущен. Запустите `./scripts/flowlink.sh`.

**Расширение пишет конкретную ошибку (например, «Invalid JSON»)** → ошибка от Python gateway. Проверьте, что версия расширения соответствует версии gateway. Перезагрузите расширение на странице `chrome://extensions`.

**Кнопка «Сохранить» долго не реагирует** → идёт запрос к Python gateway. При сохранении на кнопке отображается вращающийся спиннер — дождитесь его завершения. Если спиннер крутится >10 секунд — проверьте, запущен ли gateway.

**Chrome пишет ERR_PROXY_CONNECTION_FAILED** → проверьте, что в настройках браузера указан HTTP-прокси `127.0.0.1:8080` (а не SOCKS5).

**Не работает SOCKS5** → проверьте логи: `./scripts/flowlink.sh --debug`. Пинг в расширении покажет, доступен ли сервер.

**PowerShell: «не имеет цифровой подписи»** → политика выполнения по умолчанию блокирует `.ps1`. Запускайте через обёртку:
```bat
scripts\build.bat
```
Или напрямую с флагом:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```
