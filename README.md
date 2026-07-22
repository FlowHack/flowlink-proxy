# FlowLink Proxy

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-green.svg)](LICENSE.txt)
[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-orange?logo=googlechrome&logoColor=white)](extension/)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)](https://github.com/FlowHack/flowlink-proxy/releases/latest)
[![AI: DeepSeek](https://img.shields.io/badge/AI-DeepSeek-4A6CF7?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTEyIDJhNyA3IDAgMCAwLTcgN2MwIDMgMS41IDUuNSA0IDdsLTEgNmg0bC0xLTZjMi41LTEuNSA0LTQgNC03YTcgNyAwIDAgMC03LTd6Ii8+PC9zdmc+)](https://deepseek.com)
[![AI: AiderDesk](https://img.shields.io/badge/AI-AiderDesk-7C3AED?logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHJlY3QgeD0iMiIgeT0iMiIgd2lkdGg9IjIwIiBoZWlnaHQ9IjIwIiByeD0iNCIvPjxwYXRoIGQ9Ik04IDEyaDgiLz48cGF0aCBkPSJNMTIgOHY4Ii8+PC9zdmc+)](https://aiderdesk.com)

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

## Создание проекта

FlowLink Proxy создан с использованием **AI-assisted development** в среде **AiderDesk**.

**Роли:**
- **DeepSeek (Architect Manager)** — архитектура проекта, распределение задач, контроль качества
- **Big Pickle (SubAgent)** — реализация задач средней сложности, рефакторинг, написание тестов, запуск линтинга (pylint, pyright, pytest)

Архитектор-менеджер определяет план, делегирует выполнение субагенту и проверяет результат. Такой подход позволил поддерживать высокое качество кода при минимальном времени разработки.

---

## Технологический стек

| Категория | Технологии |
|---|---|
| **Языки** | Python 3.10+, JavaScript (ES Modules), Shell, PowerShell |
| **Бэкенд** | asyncio, HTTP CONNECT-прокси, SOCKS5-клиент (чистый struct/asyncio), SSE-шина событий |
| **Шифрование** | AES-256-GCM + PBKDF2-HMAC-SHA256 (cryptography) |
| **Системный трей** | tkinter (кастомное тёмное меню), pystray, Win32 ctypes |
| **Расширение** | Chrome Extension Manifest V3, Service Worker, EventSource (SSE) |
| **Сборка** | PyInstaller (standalone), Inno Setup (Windows), dpkg-deb / rpmbuild (Linux), pkgbuild (macOS) |
| **CI/CD** | GitHub Actions (lint + typecheck + pytest; multios сборка + релизы по тегам) |
| **Качество** | pytest, pylint >= 9.0, pyright (type-checking) |
| **Платформы** | Windows 10+, Linux x64, macOS (Intel + Apple Silicon) |

Ключевые особенности:
- **Плагинная архитектура протоколов** — `ProxyProtocol` ABC + фабрика; добавление нового протокола = новый класс + регистрация
- **Mask Router** — wildcard-маски конвертируются в precompiled regex, кешируются, O(n) по активным правилам
- **SSRF-защита** — резолв IP, блокировка private/loopback/link-local диапазонов
- **Пароли в AES-256-GCM** — authenticated encryption, PBKDF2 (600k итераций)
- **Состояние в памяти** — `isEnabled` не пишется на диск; SSE push при реконнекте расширения
- **Multi-platform tray** — цепочка fallback'ов (Win32 → pystray+tkinter → pystray+native)
- **Connection teardown** — при изменении конфига активные туннели принудительно закрываются
- **Dev mode** — hot-reload, mock SOCKS5-сервер, генерация тестовых данных

---

## Быстрый старт

### 1. Скачайте и запустите бэкенд

Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest) и скачайте архив для вашей ОС:

| Платформа | Файл | Установка |
|-----------|------|-----------|
| **Windows x64** | `FlowLink-Proxy-v*-Setup.exe` | Запустите установщик → следуйте инструкциям |
| **Linux x64** | `FlowLink-Proxy-v*-linux-x64.tar.gz` | Распакуйте → `chmod +x flowlink-proxy` → запустите |
| **Linux x64** | `FlowLink-Proxy-v*-amd64.deb` | `sudo dpkg -i FlowLink-Proxy-*.deb` |
| **Linux x64** | `FlowLink-Proxy-v*-x86_64.rpm` | `sudo rpm -i FlowLink-Proxy-*.rpm` |
| **macOS Intel** | `FlowLink-Proxy-v*-macos-x64.tar.gz` | Распакуйте → запустите |
| **macOS Apple Silicon** | `FlowLink-Proxy-v*-macos-arm64.tar.gz` | Распакуйте → запустите |
| **macOS** | `FlowLink-Proxy-v*-macos-*.pkg` | Дважды кликните по `.pkg` |

> Подробные инструкции по каждому способу: **[SETUP.md](SETUP.md)**

### 2. Установите расширение

Откройте страницу расширений в браузере → включите «Режим разработчика» → «Загрузить распакованное расширение» → выберите папку `extension/`.

| Браузер | Страница расширений |
|---------|---------------------|
| Chrome | `chrome://extensions` |
| Yandex Browser | `browser://extensions` |
| Opera | `opera://extensions` |
| Edge | `edge://extensions` |

> Расширение настраивает браузер автоматически (флаг `--proxy-server`).

### 3. Готово

Нажмите иконку FlowLink Proxy в панели расширений → добавьте прокси и маски.

---

## Интерфейс расширения

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
| Linux / macOS | `~/.FlowHack/FlowLink Proxy/` |
| Windows | `%APPDATA%\FlowHack\FlowLink Proxy\` |
| systemd | Путь из `FLOWLINK_DATA_DIR` |

Содержимое: `config.json`, ключи шифрования (`.flowlink.key`, `.flowlink.salt`), настройки автозапуска браузера, пути к браузеру, флага загрузки расширения (`.flowlink-settings`), порты (`.flowlink-port`), логи (`logs/`).

Очистить все данные можно через иконку в системном трее → «Очистить все данные».

---

## Системный трей

После запуска бэкенда в системном трее (рядом с часами) появляется иконка FlowLink Proxy. 
Правый клик открывает контекстное меню со следующими пунктами:

| Пункт меню | Описание |
|---|---|
| 📜 Посмотреть логи | Открывает папку с логами в файловом менеджере |
| 🗑 Очистить логи | Удаляет все файлы логов |
| 📂 Посмотреть данные | Открывает папку с данными (конфиги, ключи, настройки) |
| ⚠️ Очистить данные | Удаляет все конфиги, ключи и настройки (сброс к заводским) |
| 🌐 Автозапуск браузера | Чекбокс: при запуске бэкенда автоматически запускать браузер |
| 🔊 Запуск с системой | Чекбокс: автоматически запускать бэкенд при входе в систему |
| 📦 Запуск с расширением | Чекбокс: при запуске браузера загружать расширение FlowLink Proxy |
| 📁 Выбрать браузер... | Открывает диалог выбора браузера (автопоиск + ручной выбор) |
| 🌐 Запустить браузер | Немедленно запустить браузер с настроенным прокси |
| ❌ Выход | Остановить бэкенд и закрыть приложение |

**Выбор браузера:** при нажатии «Выбрать браузер...» выполняется автоматический поиск 
установленных браузеров. Найденные браузеры отображаются в виде списка — достаточно 
кликнуть по нужному, чтобы сохранить путь. Если браузер не найден, можно указать путь 
вручную через системный диалог выбора файла.

---

## Устранение проблем

| Симптом | Решение |
|---------|---------|
| «Нет связи с бэкендом» | Бэкенд не запущен. Запустите бинарник или `python -m server` |
| `ERR_PROXY_CONNECTION_FAILED` | Браузер на SOCKS5 вместо HTTP. Флаг: `--proxy-server=127.0.0.1:8080` |
| Порт 8080 занят | Завершите старый процесс: Linux `lsof -i :8080`, Windows — Диспетчер задач |

Подробная таблица проблем: **[SETUP.md](SETUP.md#устранение-проблем-при-установке)**. Отладка: **[DEBUG.md](DEBUG.md)**

---

## Структура проекта

```
flowlink-proxy/
├── server/                    # Python-бэкенд
│   ├── __main__.py            # Точка входа (CLI + tray icon)
│   ├── version.py             # Версия проекта
│   ├── logging_config.py      # Настройка логгера (файл + консоль)
│   ├── tray/                  # System tray icon (tkinter / pystray / ctypes)
│   │   ├── __init__.py        # Координатор: start_tray()
│   │   ├── platform.py        # Определение ОС и возможностей
│   │   ├── popup.py           # Tkinter безрамочное меню (тёмная тема)
│   │   ├── menu.py            # Общая логика построения меню
│   │   ├── fallback.py        # pystray fallback (нестандартные ОС)
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
│   │   └── system_autostart.py # Автозапуск с системой (Win/Linux/macOS)
│   ├── protocols/
│   │   ├── base.py            # ABC ProxyProtocol
│   │   ├── socks5.py          # SOCKS5-клиент (чистый asyncio + struct)
│   │   ├── factory.py         # Фабрика протоколов
│   │   ├── parser.py          # Парсинг CONNECT/HTTP-запросов
│   │   └── mock_socks5.py     # Тестовый SOCKS5-сервер (--dev)
│   ├── services/
│   │   ├── router.py          # Маршрутизация URL по маскам
│   │   ├── tunnel.py          # Установка туннелей (SOCKS5 / прямой) + SSRF-защита
│   │   ├── pipe.py            # Двусторонняя пересылка данных
│   │   ├── ping.py            # Пинг прокси (SOCKS5 handshake)
│   │   ├── debug.py           # Debug-утилиты
│   │   ├── events.py          # SSE-шина событий
│   │   └── fake_proxies.py    # Генерация тестовых прокси (--count-proxy)
│   ├── servers/
│   │   ├── base_server.py     # ABC BaseServer
│   │   ├── proxy.py           # HTTP CONNECT прокси (порт 8080)
│   │   ├── api.py             # HTTP API (порт 8081)
│   │   └── handlers.py        # Обработчики API-эндпоинтов
│   ├── utils.py               # Утилиты (get_data_dir, clear_all_data, write_port_file)
│   ├── icons/                 # Иконки бэкенда (icon.ico, icon.png)
│   ├── requirements.txt       # Зависимости Python
│   └── tests/                 # Юнит-тесты
│       ├── base.py            # Базовые миксины (TempConfigMixin)
│       ├── conftest.py        # Общие вспомогательные функции
│       ├── test_config.py
│       ├── test_crypto.py
│       ├── test_handlers.py
│       ├── test_events.py
│       ├── test_proxy.py
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
│       └── test_tray_popup.py
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
│   │   ├── autostart.js       # Настройки автозапуска браузера
│   │   ├── tab-status.js      # Статус текущей вкладки
│   │   ├── modal.js           # Модальные окна
│   │   ├── help.js            # Окно помощи
│   │   ├── help.html          # Статическая справка (открывается из tkinter-диалога)
│   │   └── updater.js         # Проверка обновлений
│   ├── shared/
│   │   ├── api.js             # HTTP GET/POST хелперы (apiGet, apiPost, apiPostRaw)
│   │   ├── constants.js       # API_BASE, GitHub URLs
│   │   ├── dom.js             # escapeHtml, утилиты DOM
│   │   ├── utils.js           # Валидация IP/port, wildcard→regex, copyEmailToClipboard
│   │   └── port_discovery.js  # Автообнаружение порта API
│   └── icons/                 # Иконки расширения
│
├── scripts/
│   ├── installer/
│   │   └── flowlink-installer.iss  # Inno Setup установщик Windows
│   ├── icons/
│   │   ├── icon.ico            # Иконка для установщика и ярлыков
│   │   ├── icon.png            # Иконка для Linux/macOS
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
│   │   ├── build.ps1              # Windows: сборка standalone (PyInstaller)
│   │   ├── build.sh               # Linux/macOS: сборка standalone (PyInstaller)
│   │   ├── build-deb.sh           # Linux: сборка .deb-пакета
│   │   ├── build-rpm.sh           # Linux: сборка .rpm-пакета
│   │   ├── flowlink.spec          # RPM-спецификация
│   │   ├── build-pkg.sh           # macOS: сборка .pkg-пакета
│   │   └── create-release.sh      # Упаковка архивов релиза
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
└── LICENSE.txt                # GNU AGPL v3
```

---

## Документация

| Документ | Содержание |
|----------|------------|
| **[SETUP.md](SETUP.md)** | Установка из релизов, из исходников, настройка браузеров, порты, автозапуск, сборка бинарников |
| **[DEBUG.md](DEBUG.md)** | CLI-флаги, HTTP API, логи, отладка |
| **[PRIVACY_POLICY.md](PRIVACY_POLICY.md)** | Политика конфиденциальности |
| **[LICENSE.txt](LICENSE.txt)** | GNU AGPL v3 |

---

## Требования

- **Windows:** 10+ (standalone-бинарник или установщик)
- **Linux:** x64 (standalone-бинарник, `.deb` или `.rpm`)
- **macOS:** Intel или Apple Silicon (standalone-бинарник или `.pkg`)
- **Исходный код:** Python 3.10+ и tkinter (см. [SETUP.md](SETUP.md#исходный-код-python))
- **Браузер:** Chrome, Yandex Browser, Opera, Edge (Chromium)

---

## Удаление

| Способ установки | Команда / действие |
|------------------|--------------------|
| **Windows (установщик)** | «Установка и удаление программ» → FlowLink Proxy → «Удалить» |
| **Windows (standalone)** | Удалите папку с `FlowLink Proxy.exe` вручную |
| **Linux (.deb)** | `sudo dpkg -r flowlink-proxy` |
| **Linux (.rpm)** | `sudo rpm -e flowlink-proxy` |
| **Linux (.tar.gz)** | Удалите папку с бинарником и лаунчером |
| **macOS (.pkg)** | `sudo rm /usr/local/bin/FlowLink Proxy && sudo rm -rf "/usr/local/share/FlowLink Proxy" && rm ~/Library/LaunchAgents/com.flowlink.proxy.plist` |
| **macOS (.tar.gz)** | Удалите папку с бинарником и лаунчером |
| **Исходники** | Удалите `venv/` и папку данных (см. [SETUP.md](SETUP.md)) |

Директория данных содержит зашифрованные пароли прокси. Удалите её отдельно, если нужно полностью очистить FlowLink Proxy:

| ОС | Путь |
|---|---|
| Linux / macOS | `~/.FlowHack/FlowLink Proxy/` |
| Windows | `%APPDATA%\FlowHack\FlowLink Proxy\` |

---

## Лицензия

FlowLink Proxy распространяется под лицензией **GNU AGPL v3**.
При использовании вы соглашаетесь с условиями [EULA.rtf](EULA.rtf) и [LICENSE.txt](LICENSE.txt).

---

## Контакты

По вопросам и ошибкам: [GitHub Issues](https://github.com/FlowHack/flowlink-proxy/issues) или email: flowlink.proxy@atomicmail.io
