# FlowLink Proxy

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-green.svg)](LICENSE.txt)
[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-orange?logo=googlechrome&logoColor=white)](extension/)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)](https://github.com/FlowHack/flowlink-proxy/releases/latest)

Автоматическая маршрутизация трафика: сайты по маскам — через SOCKS5-прокси с паролем, остальные — напрямую.

> Chrome не умеет передавать логин/пароль в SOCKS5. FlowLink Proxy берёт аутентификацию на себя, а браузер работает через обычный HTTP-прокси `localhost:8080`.

```
Браузер → HTTP CONNECT localhost:8080 (без пароля)
                │
        Python-бэкенд (server/)
                │
     ┌──────────┴──────────┐
     ▼                      ▼
Маска совпала?         Маска не совпала?
     │                      │
     ▼                      ▼
SOCKS5 с паролем       Прямое соединение
(ваш сервер)           ( Happ / интернет )
```

---

## Быстрый старт

### 1. Установите бэкенд

| Способ | Что делать |
|--------|-----------|
| **Установщик Windows** | Скачайте `.exe`-установщик из [релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest) → запустите → выберите браузер. Всё остальное автоматически. |
| **Standalone-бинарник** | Скачайте архив из [релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest) → распакуйте в любую папку → см. ниже. |
| **Исходный код** | `git clone` → `./scripts/FlowLink Proxy Source.sh` (см. [SETUP.md](SETUP.md#исходный-код-python)). |

> **Обратите внимание:** standalone-бинарники доступны для **Windows (.exe)** и **Linux**. Для **macOS** бинарник пока не поставляется, но вы можете легко собрать его сами — см. [SETUP.md](SETUP.md#macOS-самостоятельная-сборка).

### 2. Установите расширение

> **Из магазина:** ссылка будет добавлена после публикации.

**Из исходника:** откройте страницу расширений → включите «Режим разработчика» → «Загрузить распакованное расширение» → выберите папку `extension/`.

| Браузер | Страница расширений |
|---------|---------------------|
| Chrome | `chrome://extensions` |
| Yandex Browser | `browser://extensions` |
| Opera | `opera://extensions` |
| Edge | `edge://extensions` |
| Firefox | `about:debugging#/runtime/this-firefox` → «Загрузить временный дополнитель» |

### 3. Настройте браузер

Добавьте флаг `--proxy-server=127.0.0.1:8080` к запуску браузера. Подробности: **[SETUP.md](SETUP.md#настройка-браузера)**

> **Если вы используете установщик или лаунчер (`FlowLink Proxy.bat` / `.sh`) — браузер настраивается автоматически.**

---

## Использование

### Запуск

**Установщик (Windows):** кликните по ярлыку FlowLink Proxy в меню «Пуск» или на рабочем столе — бэкенд и браузер запустятся автоматически.

**Standalone / исходный код:** запустите лаунчер:
- Windows: `FlowLink Proxy.bat`
- Linux / macOS: `./FlowLink Proxy.sh` (standalone) или `./scripts/FlowLink Proxy Source.sh` (исходный код)

> При первом запуске лаунчера нужно указать путь к браузеру в текстовом редакторе. Подробности: **[SETUP.md](SETUP.md#windows-standalone)**

### Интерфейс расширения

Нажмите иконку FlowLink Proxy в панели расширений.

#### Добавление прокси

1. Нажмите **«Добавить прокси»**
2. Заполните поля:
   - **IP** — адрес SOCKS5-сервера (например `80.243.18.120`)
   - **Порт** — порт SOCKS5-сервера (например `10000`)
   - **Логин** — имя пользователя
   - **Пароль** — пароль (хранится в зашифрованном виде)
   - **Метка** — удобное название (например «Мой прокси»)
3. Нажмите **«Сохранить»**

#### Добавление маски

Маска определяет, какие сайты идут через прокси, а какие — напрямую.

1. Нажмите на **иконку масок** (ряду с нужным прокси) — откроется список масок для этого прокси
2. Нажмите **«Добавить маску»**
3. Введите шаблон. Примеры:
   - `*google.com*` — все домены google.com
   - `*translate.google.com*` — только Google Translate
   - `*github.com*` — все домены github.com
4. Нажмите **«Сохранить»**

> Маска привязывается к тому прокси, рядом с которым вы открыли список. Символ `*` заменяет любую часть адреса. Маски автоматически конвертируются в регулярные выражения.

#### Включение и выключение

- **Глобальный тоггл** (внизу окна) — включает/выключает весь FlowLink Proxy. При выключении весь трафик идёт напрямую (минуя прокси).
- **Тоггл прокси** (ряду с каждым прокси) — включает/выключает отдельный прокси. Маски, привязанные к выключенному прокси, игнорируются.

#### Пинг

Нажмите **«Пинг»** чтобы проверить доступность всех прокси. Результат показывает время отклика (в мс) или «н/д» если прокси недоступен.

#### Настройки (⚙)

Нажмите шестерёнку рядом с версией:
- **Порт API** — измените если бэкенд работает на другом порту (по умолчанию `8081`)
- **Обновление** — проверить наличие новой версии

#### Директория данных

Все данные FlowLink Proxy хранятся в стандартной директории данных ОС:

| ОС | Путь |
|---|---|
| Linux / macOS | `~/.flowlink-proxy/` |
| Windows | `%APPDATA%\FlowLink Proxy\` |
| systemd | Путь из `FLOWLINK_DATA_DIR` |

Содержимое: `config.json`, ключи шифрования (`.flowlink.key`, `.flowlink.salt`), настройки автозапуска (`.flowlink-settings`), порты (`.flowlink-port`), логи (`logs/`).

Очистить все данные можно через иконку в системном трее → «Очистить все данные».

---

## Структура проекта

```
flowlink-proxy/
├── server/                    # Python-бэкенд
│   ├── __main__.py            # Точка входа (CLI + tray icon)
│   ├── version.py             # Версия проекта
│   ├── logging_config.py      # Настройка логгера (файл + консоль)
│   ├── tray.py                # System tray icon (только Windows)
│   ├── config/
│   │   ├── config.py          # Бизнес-логика конфига (proxies, masks, enabled)
│   │   ├── repo.py            # Чтение/запись config.json
│   │   └── crypto.py          # AES-GCM шифрование паролей (PBKDF2)
│   ├── protocols/
│   │   ├── base.py            # ABC ProxyProtocol
│   │   ├── socks5.py          # SOCKS5-клиент (чистый asyncio + struct)
│   │   ├── factory.py         # Фабрика протоколов
│   │   ├── parser.py          # Парсинг CONNECT/HTTP-запросов
│   │   └── mock_socks5.py     # Тестовый SOCKS5-сервер (--dev)
│   ├── services/
│   │   ├── router.py          # Маршрутизация URL по маскам
│   │   ├── tunnel.py          # Установка туннелей (SOCKS5 / прямой)
│   │   ├── pipe.py            # Двусторонняя пересылка данных
│   │   ├── ping.py            # Пинг прокси (SOCKS5 handshake)
│   │   ├── debug.py           # Debug-утилиты
│   │   └── events.py          # SSE-шина событий
│   ├── servers/
│   │   ├── base_server.py     # ABC BaseServer
│   │   ├── proxy.py           # HTTP CONNECT прокси (порт 8080)
│   │   ├── api.py             # HTTP API (порт 8081)
│   │   └── handlers.py        # Обработчики API-эндпоинтов
│   ├── utils.py               # Утилиты (get_data_dir, clear_all_data, get_resource_dir)
│   ├── icons/                 # Иконки бэкенда (icon.ico, icon.png)
│   ├── requirements.txt       # Зависимости Python
│   └── tests/                 # Юнит-тесты
│       ├── test_config.py
│       ├── test_crypto.py
│       ├── test_handlers.py
│       ├── test_events.py
│       ├── test_proxy.py
│       ├── test_router.py
│       ├── test_socks5.py
│       └── test_utils.py
│
├── extension/                 # Chrome-расширение (Manifest V3)
│   ├── manifest.json          # Манифест расширения
│   ├── background/
│   │   └── service-worker.js  # SSE-клиент + pushEnabledState
│   ├── popup/
│   │   ├── popup.html         # Главное окно
│   │   ├── popup.css          # Стили
│   │   ├── popup.js           # Главный контроллер
│   │   ├── crud-proxy.js      # CRUD-операции с прокси
│   │   ├── crud-mask.js       # CRUD-операции с масками
│   │   ├── ping.js            # Пинг прокси
│   │   ├── settings.js        # Настройки порта API
│   │   ├── tab-status.js      # Статус текущей вкладки
│   │   ├── modal.js           # Модальные окна
│   │   ├── help.js            # Окно помощи
│   │   └── updater.js         # Проверка обновлений
│   ├── shared/
│   │   ├── api.js             # HTTP GET/POST хелперы
│   │   ├── constants.js       # API_BASE, GitHub URLs
│   │   ├── dom.js             # escapeHtml, утилиты DOM
│   │   └── utils.js           # Валидация IP/port, wildcard→regex
│   └── icons/                 # Иконки расширения
│
├── scripts/                   # Скрипты сборки и запуска
│   ├── FlowLink Proxy.bat     # Windows-лаунчер: запускает бэкенд + браузер
│   │                          # (пользователь указывает путь к браузеру в начале файла)
│   ├── FlowLink Proxy.sh      # Linux/macOS-лаунчер: аналогично
│   ├── FlowLink Proxy Source.sh  # Dev-лаунчер: venv + зависимости + запуск + браузер
│   ├── build.bat              # Windows: обёртка для build.ps1
│   ├── build.ps1              # Windows: сборка standalone (PyInstaller)
│   ├── build.sh               # Linux/macOS: сборка standalone (PyInstaller)
│   ├── flowlink.service       # Linux: systemd-сервис для автозапуска
│   └── flowlink.desktop       # Linux: десктоп-файл для меню приложений
│
├── myAgents/                  # Конфиги агента (для разработки)
├── AI_DEV_LOG.md              # Журнал разработки
├── SETUP.md                   # Подробная установка и настройка
├── DEBUG.md                   # Отладка, CLI-флаги, API
├── PRIVACY_POLICY.md          # Политика конфиденциальности
├── README.md                  # Этот файл
└── LICENSE.txt                # GNU AGPL v3
```

---

## Описание скриптов в папке scripts/

### Лаунчеры (запуск приложения)

| Скрипт | Платформа | Что делает | Что настраивать |
|--------|-----------|------------|-----------------|
| `FlowLink Proxy.bat` | Windows | Запускает бэкенд + браузер с прокси | `BROWSER_PATH` — путь к браузеру, `PROXY_PORT` — порт прокси |
| `FlowLink Proxy.sh` | Linux / macOS | Запускает бэкенд + браузер с прокси | `BROWSER_PATH` — путь к браузеру, `PROXY_PORT` — порт прокси |
| `FlowLink Proxy Source.sh` | Linux / macOS | Запускает из исходников (venv + зависимости + backend + браузер) | `BROWSER_PATH` — путь к браузеру, `PROXY_PORT` — порт прокси |

> Все переменные для настройки расположены **в начале каждого файла** — просто откройте в текстовом редакторе.

### Скрипты сборки

| Скрипт | Платформа | Что делает |
|--------|-----------|------------|
| `build.bat` | Windows | Обёртка для `build.ps1` (обходит политику выполнения PowerShell) |
| `build.ps1` | Windows | Собирает standalone-бинарник через PyInstaller |
| `build.sh` | Linux / macOS | Собирает standalone-бинарник через PyInstaller |

### Файлы автозапуска

| Файл | Платформа | Что делает | Что настраивать |
|------|-----------|------------|-----------------|
| `flowlink.service` | Linux (systemd) | Автозапуск бэкенда как сервис | Путь к бинарнику в `ExecStart`, порты |
| `flowlink.desktop` | Linux (GNOME/KDE) | Ярлык в меню приложений | `Exec` — путь к скрипту, `Icon` — путь к иконке |

---

## Устранение проблем

| Симптом | Причина | Решение |
|---------|---------|---------|
| Расширение пишет «Нет связи с бэкендом» | Бэкенд не запущен | Запустите `FlowLink Proxy.exe` или `FlowLink Proxy.bat` |
| `ERR_PROXY_CONNECTION_FAILED` | Браузер настроен на SOCKS5 вместо HTTP-прокси | Флаг должен быть `--proxy-server=127.0.0.1:8080` (HTTP, не SOCKS5) |
| Браузер не использует прокси | Браузер запущен без флага `--proxy-server` | Запускайте браузер **только** через ярлык или лаунчер |
| Порт 8080 уже занят | Другой процесс использует порт | Windows: Диспетчер задач → завершите старый процесс. Linux: `lsof -i :8080` |
| Расширение не подключается | Порт API не совпадает | Проверьте порт в настройках расширения (⚙) — он должен совпадать с `--api-port` |
| PowerShell блокирует `.ps1` | Политика выполнения скриптов | Используйте `scripts\build.bat` или `powershell -ExecutionPolicy Bypass -File build.ps1` |
| Логин/пароль не отправляются | Браузер не поддерживает SOCKS5-auth | Это нормально — FlowLink Proxy берёт аутентификацию на себя через HTTP-прокси |
| FlowLink Proxy.bat не находит exe | bat-файл лежит не в одной папке с exe | Поместите bat-файл в ту же папку, что и FlowLink Proxy.exe |
| FlowLink Proxy.sh не находит бинарник | Скрипт запущен не из папки с бинарником | Поместите скрипт в ту же папку, что и FlowLink Proxy |
| Браузер не найден (Path не указан) | Переменная BROWSER_PATH не отредактирована | Откройте скрипт в текстовом редакторе, замените ПУТЬ_К_БРАУЗЕРУ |

Для отладки запустите с флагом `--debug` — подробные логи в консоли и файле `logs/flowlink.log`. Подробнее: [DEBUG.md](DEBUG.md)

---

## Документация

| Документ | Содержание |
|----------|------------|
| **[SETUP.md](SETUP.md)** | Установка, настройка браузеров, порты, автозапуск, обновление |
| **[DEBUG.md](DEBUG.md)** | Флаги CLI, HTTP API, логи, устранение проблем |
| **[PRIVACY_POLICY.md](PRIVACY_POLICY.md)** | Политика конфиденциальности |
| **[LICENSE.txt](LICENSE.txt)** | GNU AGPL v3 |

---

## Требования

- **Windows:** 10+ (установщик) или standalone-бинарник
- **Linux / macOS:** Python 3.10+ или standalone-бинарник
- **Браузер:** Chrome 100+, Yandex Browser, Opera, Edge (Chromium) или Firefox

---

## Контакты

По вопросам и ошибкам: [GitHub Issues](https://github.com/FlowHack/flowlink-proxy/issues) или email: flowlink.proxy@atomicmail.io
