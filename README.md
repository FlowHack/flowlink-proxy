# FlowLink Proxy

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-green.svg)](LICENSE.txt)
[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-orange?logo=googlechrome&logoColor=white)](extension/)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)](https://github.com/flowhack/flowlink-proxy/releases/latest)

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
| **Установщик Windows** | Скачайте `.exe`-установщик из [релизов](https://github.com/flowhack/flowlink-proxy/releases/latest) → запустите → выберите браузер. Всё остальное автоматически. |
| **Standalone-бинарник** | Скачайте архив из [релизов](https://github.com/flowhack/flowlink-proxy/releases/latest) → распакуйте в любую папку → см. ниже. |
| **Исходный код** | `git clone` → `./scripts/flowlink.sh` (см. [SETUP.md](SETUP.md#исходный-код-python)). |

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

> **Если вы используете установщик или лаунчер (`flowlink-proxy-run.bat` / `.sh`) — браузер настраивается автоматически.**

---

## Использование

### Запуск

**Установщик (Windows):** кликните по ярлыку FlowLink Proxy в меню «Пуск» или на рабочем столе — бэкенд и браузер запустятся автоматически.

**Standalone / исходный код:** запустите лаунчер:
- Windows: `flowlink-proxy-run.bat`
- Linux / macOS: `./flowlink-proxy-run.sh`

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
│   ├── utils.py               # Утилиты (get_data_dir, get_resource_dir)
│   ├── requirements.txt       # Зависимости Python
│   └── tests/                 # Юнит-тесты
│       ├── test_config.py
│       ├── test_crypto.py
│       ├── test_handlers.py
│       ├── test_events.py
│       ├── test_proxy.py
│       ├── test_router.py
│       └── test_socks5.py
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
│   ├── flowlink-proxy-run.bat # Windows-лаунчер: запускает бэкенд + браузер
│   │                          # (пользователь указывает путь к браузеру)
│   ├── flowlink-proxy-run.sh  # Linux/macOS-лаунчер: аналогично
│   ├── flowlink.sh            # Dev-лаунчер: venv + зависимости + запуск
│   ├── build.bat              # Windows: обёртка для build.ps1
│   ├── build.ps1              # Windows: сборка standalone (PyInstaller)
│   ├── build.sh               # Linux/macOS: сборка standalone (PyInstaller)
│   ├── flowlink.service       # Linux: systemd-сервис
│   └── flowlink.desktop       # Linux: десктоп-файл
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

## Устранение проблем

| Симптом | Причина | Решение |
|---------|---------|---------|
| Расширение пишет «Нет связи с бэкендом» | Бэкенд не запущен | Запустите `FlowLink Proxy.exe` или `flowlink-proxy-run.bat` |
| `ERR_PROXY_CONNECTION_FAILED` | Браузер настроен на SOCKS5 вместо HTTP-прокси | Флаг должен быть `--proxy-server=127.0.0.1:8080` (HTTP, не SOCKS5) |
| Браузер не использует прокси | Браузер запущен без флага `--proxy-server` | Запускайте браузер **только** через ярлык или лаунчер |
| Порт 8080 уже занят | Другой процесс использует порт | Windows: Диспетчер задач → завершите старый процесс. Linux: `lsof -i :8080` |
| Расширение не подключается | Порт API не совпадает | Проверьте порт в настройках расширения (⚙) — он должен совпадать с `--api-port` |
| PowerShell блокирует `.ps1` | Политика выполнения скриптов | Используйте `scripts\build.bat` или `powershell -ExecutionPolicy Bypass -File build.ps1` |
| Логин/пароль не отправляются | Браузер не поддерживает SOCKS5-auth | Это нормально — FlowLink Proxy берёт аутентификацию на себя через HTTP-прокси |

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
