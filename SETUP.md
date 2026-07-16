# FlowLink Proxy — Установка и настройка

## Содержание

1. [Установка бэкенда](#установка-бэкенда)
   - [Windows (установщик)](#windows-установщик)
   - [Windows (standalone)](#windows-standalone)
   - [Linux (.deb)](#linux-deb)
   - [Linux (.rpm)](#linux-rpm)
   - [Linux / macOS (standalone)](#linux--macos-standalone)
   - [macOS (.pkg)](#macos-pkg)
   - [macOS (standalone)](#macos-standalone)
   - [Исходный код (Python)](#исходный-код-python)
2. [Сборка бинарников](#сборка-бинарников)
3. [Установка расширения](#установка-расширения)
3. [Настройка браузера](#настройка-браузера)
4. [Настройка портов](#настройка-портов)
5. [Автозапуск](#автозапуск)
6. [Обновление](#обновление)
7. [Скрипты и их настройка](#скрипты-и-их-настройка)

---

## Установка бэкенда

### Windows (установщик)

Рекомендуемый способ. Не требует Python.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте файл `FlowLink-Proxy-vX.X.X-Setup.exe` (нажмите «Assets» → `.exe`)
3. Запустите скачанный файл
4. Следуйте инструкциям установщика:
   - Примите лицензионное соглашение
   - Выберите папку установки (по умолчанию `C:\Program Files\FlowLink Proxy\`)
   - На странице выбора браузера укажите ваш браузер (автопоиск найдёт установленные)
   - Выберите, создать ли ярлык на рабочем столе
5. Нажмите «Установить»
6. Готово! В меню «Пуск» появится ярлык «FlowLink Proxy»

**Что создаёт установщик:**
- Программа в `C:\Program Files\FlowLink Proxy\`
- Ярлык в меню «Пуск» (и на рабочем столе, если выбрано)
- Автозапуск бэкенда при входе в Windows
- `FlowLink Proxy.bat` — лаунчер, запускающий бэкенд и браузер с прокси

### Windows (standalone)

Без установщика, без Python. Подходит если не хотите устанавливать программу.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Нажмите «Assets» → скачайте архив для Windows (`.zip`)
3. Распакуйте архив в **любую удобную папку** (например `C:\FlowLink Proxy\`)
4. В папке будут два файла:
   - `FlowLink Proxy.exe` — бэкенд
   - `FlowLink Proxy.bat` — лаунчер
5. **Откройте `FlowLink Proxy.bat` в текстовом редакторе** (ПКМ → «Изменить»)
6. Найдите блок `═══ НАСТРОЙКА ПЕРЕМЕННЫХ ═══` в начале файла. Там два параметра:
   - **`BROWSER_PATH`** — путь к exe-файлу вашего браузера. Замените `CHANGE_ME`:
     ```
     set BROWSER_PATH=C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
     set BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
     set BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
     ```
   - **`PROXY_PORT`** — порт прокси (оставьте `8080`, если не уверены)
7. **Сохраните** файл
8. Запустите `FlowLink Proxy.bat` двойным кликом

> Лаунчер автоматически запустит бэкенд и браузер с флагом `--proxy-server`. При повторном запуске процессы не дублируются.

> **Автоопределение бинарника:** `FlowLink Proxy.bat` сначала ищет `FlowLink Proxy.exe` рядом с собой (standalone), затем в `server\FlowLink Proxy\` (dev-сборка). Убедитесь, что bat-файл лежит в одной папке с exe.

### Linux (standalone)

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте архив для Linux: `.tar.gz`
3. Распакуйте архив в удобную папку
4. В папке будут файлы:
   - `flowlink-proxy` — бэкенд
   - `FlowLink Proxy-linux.sh` — лаунчер
   - `EULA.rtf`, `LICENSE.txt`, `README.md`, `SETUP.md`, `DEBUG.md` — документация
5. **Откройте `FlowLink Proxy-linux.sh` в текстовом редакторе**. В начале файла найдите блок `═══ НАСТРОЙКА ПЕРЕМЕННЫХ ═══`. Два параметра:
   - **`BROWSER_PATH`** — путь к исполняемому файлу браузера. Замените `ПУТЬ_К_БРАУЗЕРУ`:
     ```bash
     BROWSER_PATH="/usr/bin/google-chrome-stable"
     BROWSER_PATH="/usr/bin/chromium-browser"
     BROWSER_PATH="/usr/bin/yandex-browser"
     ```
   - **`PROXY_PORT`** — порт прокси (оставьте `8080`, если не уверены)
6. Сохраните файл
7. Откройте терминал в папке и выполните:

```bash
chmod +x "FlowLink Proxy-linux.sh"
./FlowLink Proxy-linux.sh
```

> **Автоопределение бинарника:** скрипт сначала ищет `flowlink-proxy` рядом с собой (standalone), затем в `server/FlowLink Proxy/` (dev-сборка).

### Linux (.deb)

Установка через `dpkg` — самый удобный способ для Debian/Ubuntu.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте `.deb`-пакет: `FlowLink-Proxy-vX.X.X-amd64.deb`
3. Установите:

```bash
sudo dpkg -i FlowLink-Proxy-*.deb
```

4. Если есть проблемы с зависимостями:

```bash
sudo apt-get install -f
```

**Что создаёт пакет:**
- Бинарник: `/usr/local/bin/FlowLink Proxy`
- Документация: `/usr/local/share/FlowLink Proxy/` (EULA.rtf, LICENSE.txt)
- Лаунчер: `/usr/local/bin/flowlink-launcher`
- Шаблоны автозапуска: `/usr/local/share/FlowLink Proxy/autostart/`

**Запуск:**
```bash
FlowLink Proxy              # Запуск бэкенда
flowlink-launcher           # Запуск бэкенда + браузера
```

**Удаление:**
```bash
sudo dpkg -r flowlink-proxy
```

### Linux (.rpm)

Установка через `rpm` — для Fedora/RHEL/CentOS.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте `.rpm`-пакет: `FlowLink-Proxy-vX.X.X-x86_64.rpm`
3. Установите:

```bash
sudo rpm -i FlowLink-Proxy-*.rpm
```

Или обновите (если уже установлен):

```bash
sudo rpm -U FlowLink-Proxy-*.rpm
```

**Структура пакета аналогична .deb.**

**Удаление:**
```bash
sudo rpm -e flowlink-proxy
```

### Linux (установщик install.sh)

Универсальный скрипт для всех Linux-дистрибутивов.

1. Скачайте архив `.tar.gz` из [релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Распакуйте архив
3. Запустите установщик:

```bash
chmod +x install.sh
sudo ./install.sh
```

Скрипт автоматически:
- Определяет платформу (Linux) и архитектуру (x64/arm64)
- Устанавливает бинарник в `/usr/local/bin/`
- Копирует документацию в `/usr/local/share/flowlink-proxy/`
- Устанавливает лаунчер и шаблоны автозапуска

### macOS (.pkg)

Автоматическая установка через стандартный установщик macOS.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте `.pkg`-пакет для вашей архитектуры:
   - `FlowLink-Proxy-vX.X.X-x64.pkg` — Intel
   - `FlowLink-Proxy-vX.X.X-arm64.pkg` — Apple Silicon (M1/M2/M3)
3. Дважды кликните по скачанному файлу
4. Следуйте инструкциям установщика

**Что создаёт пакет:**
- Бинарник: `/usr/local/bin/flowlink-proxy`
- Документация: `/usr/local/share/flowlink-proxy/`
- LaunchAgent: `~/Library/LaunchAgents/com.flowlink.proxy.plist`

**Удаление:**
```bash
sudo rm /usr/local/bin/flowlink-proxy
sudo rm -rf /usr/local/share/flowlink-proxy
rm ~/Library/LaunchAgents/com.flowlink.proxy.plist
```

### macOS (standalone)

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте архив для macOS: `.tar.gz` (Intel `.x64` или Apple Silicon `.arm64`)
3. Распакуйте архив в удобную папку
4. В папке будут файлы:
   - `flowlink-proxy` — бэкенд
   - `FlowLink Proxy-macos.sh` — лаунчер
   - `EULA.rtf`, `LICENSE.txt`, `README.md`, `SETUP.md`, `DEBUG.md` — документация
5. **Откройте `FlowLink Proxy-macos.sh` в текстовом редакторе**. Укажите `BROWSER_PATH`:
   ```bash
   BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
   BROWSER_PATH="/Applications/Yandex Browser.app/Contents/MacOS/Yandex Browser"
   ```
6. Сохраните файл
7. Откройте терминал в папке и выполните:

```bash
chmod +x "FlowLink Proxy-macos.sh"
./FlowLink Proxy-macos.sh
```

**Или используйте исходный код напрямую:**

```bash
git clone https://github.com/FlowHack/flowlink-proxy.git
cd flowlink-proxy
./scripts/setup/setup-and-run-macos.sh
```

### Исходный код (Python)

Требуется Python 3.10+.

```bash
git clone https://github.com/FlowHack/flowlink-proxy.git
cd flowlink-proxy
./scripts/setup/setup-and-run-linux.sh    # Linux
./scripts/setup/setup-and-run-macos.sh    # macOS
```

Скрипт автоматически:
- Проверяет наличие Python и tkinter
- Создаёт виртуальное окружение (`venv/`)
- Устанавливает зависимости
- Запускает бэкенд и браузер

**Настройка:** откройте скрипт в текстовом редакторе и укажите `BROWSER_PATH` в начале файла.

Или вручную:

```bash
python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows
pip install -r server/requirements.txt
python -m server
```

#### Зависимость: tkinter

Для кастомного трей-меню с тёмной темой требуется **tkinter**. Скрипт запуска и сборки проверяют его наличие автоматически и предлагают установить.

| Платформа | tkinter по умолчанию | Как установить |
|-----------|---------------------|----------------|
| **Windows** (python.org) | ✅ Включён | Не нужно |
| **macOS** (python.org) | ✅ Включён | Не нужно |
| **macOS** (Homebrew) | ❌ Отсутствует | `brew install python-tk` |
| **Linux** | ❌ Отсутствует | `sudo apt install python3-tk` (Debian/Ubuntu) |

> Если tkinter не установлен, бэкенд работает нормально, но вместо кастомного трей-меню используется стандартное меню pystray (без чекбокса автозапуска браузера).

#### Удаление

```bash
# Остановить бэкенд (если запущен)
pkill -f "python -m server"       # Linux / macOS
# taskkill /F /IM python.exe      # Windows (CMD)

# Удалить виртуальное окружение
rm -rf venv/                      # Linux / macOS
# rmdir /s /q venv                # Windows
```

Удаление директории данных (опционально, содержит зашифрованные пароли прокси):

| ОС | Путь |
|---|---|
| Linux / macOS | `~/.flowlink-proxy/` → `rm -rf ~/.flowlink-proxy/` |
| Windows | `%APPDATA%\FlowLink Proxy\` → `rmdir /s /q "%APPDATA%\FlowLink Proxy"` |

---

## Сборка бинарников

Для сборки standalone-бинарников необходим Python 3.10+ и PyInstaller.

### Linux / macOS

```bash
./scripts/build/build.sh
```

Результат: `releases/flowlink-proxy`

### Windows

```batch
scripts\build\build.bat
```

Результат: `releases\flowlink-proxy.exe`

### Упаковка архивов релиза

```bash
./scripts/build/create-release.sh
```

Создаёт в `releases/` архивы `.tar.gz` с бинарником, лаунчером и документацией.

### Сборка .deb-пакета (Linux)

```bash
./scripts/build/build.sh
./scripts/build/build-deb.sh
```

Результат: `releases/FlowLink-Proxy-vX.X.X-amd64.deb`

### Сборка .rpm-пакета (Linux)

```bash
./scripts/build/build.sh
./scripts/build/build-rpm.sh
```

Результат: `~/rpmbuild/RPMS/x86_64/FlowLink-Proxy-vX.X.X-x86_64.rpm`

### Сборка .pkg-пакета (macOS)

```bash
./scripts/build/build.sh
./scripts/build/build-pkg.sh
```

Результат: `releases/FlowLink-Proxy-vX.X.X-{x64|arm64}.pkg`

### Сборка установщика Windows

1. Установите [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. Соберите бинарник: `scripts\build\build.bat`
3. Откройте `scripts/installer/flowlink-installer.iss` в Inno Setup → Build → Compile

Результат: `scripts/installer/Output/FlowLink-Proxy-vX.X.X-Setup.exe`

---

## Установка расширения

### Из магазина

> **Ссылка будет добавлена после публикации в Chrome Web Store / Opera Add-ons.**

### Из исходника (unpacked)

1. Откройте страницу расширений в браузере
2. Включите **«Режим разработчика»** (переключатель в правом верхнем углу)
3. Нажмите **«Загрузить распакованное расширение»**
4. Выберите папку `extension/` внутри проекта

| Браузер | Страница расширений |
|---------|---------------------|
| Chrome | `chrome://extensions` |
| Yandex Browser | `browser://extensions` |
| Opera | `opera://extensions` |
| Edge | `edge://extensions` |
| Firefox | `about:debugging#/runtime/this-firefox` → «Загрузить временный дополнитель» → `extension/manifest.json` |

> Расширение из исходника нужно **обновлять вручную** через кнопку «Обновить» (круглая стрелка) на странице расширений.

---

## Настройка браузера

Браузер нужно направить на HTTP-прокси `127.0.0.1:<порт>` (по умолчанию `8080`).

> **Если вы используете установщик или лаунчер (`FlowLink Proxy.bat` / `.sh`) — этот шаг выполняется автоматически.** Раздел ниже для тех, кто настраивает браузер вручную.

### Windows

1. Найдите ярлык браузера на рабочем столе или в меню «Пуск»
2. Нажмите правой кнопкой → **Свойства**
3. В поле **«Объект»** допишите **после закрывающей кавычки** через пробел:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --proxy-server=127.0.0.1:8080
```

Другие браузеры:
```
"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe" --proxy-server=127.0.0.1:8080
"C:\Program Files\Opera\opera.exe" --proxy-server=127.0.0.1:8080
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --proxy-server=127.0.0.1:8080
```

4. Нажмите «Применить» → «ОК»

> **Важно:** запускайте браузер **только** через этот ярлык. Если открыть браузер напрямую (без флага), трафик пойдёт мимо FlowLink Proxy.

### Linux

```bash
google-chrome --proxy-server=127.0.0.1:8080
yandex-browser --proxy-server=127.0.0.1:8080
opera --proxy-server=127.0.0.1:8080
microsoft-edge --proxy-server=127.0.0.1:8080
firefox --proxy-server=127.0.0.1:8080
```

Для постоянного использования создайте ярлык или `.desktop`-файл.

### macOS

```bash
open -a "Google Chrome" --args --proxy-server=127.0.0.1:8080
open -a "Yandex Browser" --args --proxy-server=127.0.0.1:8080
open -a "Opera" --args --proxy-server=127.0.0.1:8080
open -a "Microsoft Edge" --args --proxy-server=127.0.0.1:8080
open -a "Firefox" --args --proxy-server=127.0.0.1:8080
```

Для постоянного использования создайте скрипт `.command` на рабочем столе.

> **Важно:** порт в `--proxy-server` должен совпадать с портом бэкенда (`--proxy-port`, по умолчанию `8080`).

---

## Настройка портов

Порты по умолчанию: `8080` (прокси) и `8081` (API).

### Смена портов

```bash
# Standalone / Python
"FlowLink Proxy" --proxy-port 9090 --api-port 9091
python -m server --proxy-port 9090 --api-port 9091
./scripts/setup/setup-and-run-linux.sh --proxy-port 9090 --api-port 9091
```

### После смены порта

1. **Ярлык браузера:** обновите флаг `--proxy-server=127.0.0.1:9090`
2. **Расширение:** ⚙ рядом с версией → введите API-порт → «Сохранить»
3. **Лаунчеры:** обновите `PROXY_PORT` в начале файла лаунчера
4. **Перезапустите** бэкенд

---

## Автозапуск

### Windows

При установке через установщик — настраивается автоматически.

**Ручная настройка:**
1. `Win+R` → `shell:startup` → Enter
2. Создайте ярлык для `FlowLink Proxy.exe` в открывшейся папке

### Linux (systemd)

1. Скопируйте бинарник и скрипт:
   ```bash
   mkdir -p ~/.local/share/flowlink-proxy
   cp FlowLink Proxy ~/.local/share/flowlink-proxy/
   cp scripts/FlowLink Proxy.sh ~/.local/share/flowlink-proxy/
   ```
2. Отредактируйте `scripts/flowlink.service` — укажите правильный путь в `ExecStart`
3. Установите и запустите:
   ```bash
   systemctl --user enable "$PWD/scripts/flowlink.service"
   systemctl --user start flowlink.service
   ```

> **Настройка `flowlink.service`:** файл содержит переменные `ExecStart`, `WorkingDirectory`, `Environment`. Путь к бинарнику и порты настраиваются в этих строках.

### Linux (автозагрузка рабочего стола)

Добавьте `scripts/flowlink.desktop` в автозагрузку вашего окружения.

> **Настройка `flowlink.desktop`:** `Exec` — путь к скрипту запуска, `Icon` — путь к иконке (по умолчанию `server/icons/icon.png`).

### macOS

Создайте скрипт запуска и добавьте в `~/Library/LaunchAgents`.

---

## Обновление

### Windows (установщик)

Скачайте и запустите новый установщик — он автоматически завершит запущенный процесс бэкенда (если есть) и заменит файлы.

> Если автоматическое завершение не сработало (например, процесс висит в трее), закройте бэкенд вручную: правый клик по иконке FlowLink Proxy в системном трее → «Выход».

### Standalone-бинарник

1. Скачайте новый архив со [страницы релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Остановите старый процесс (Диспетчер задач / `pkill`)
3. Замените файлы и запустите новый

### Исходный код

```bash
git pull
./scripts/setup/setup-and-run-linux.sh
# или
python -m server
```

### Расширение

- **Из магазина:** обновляется автоматически
- **Unpacked:** страница расширений → «Обновить» (круглая стрелка)

> Бэкенд и расширение должны быть одной версии. Сначала обновите бэкенд, потом расширение.

---

## Скрипты и их настройка

### Сводная таблица переменных

| Скрипт | Переменная | По умолч. | Описание |
|--------|------------|-----------|----------|
| `launcher/FlowLink Proxy-linux.sh` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к исполняемому файлу браузера (ОБЯЗАТЕЛЬНО) |
| `launcher/FlowLink Proxy-linux.sh` | `PROXY_PORT` | `8080` | Порт HTTP-прокси |
| `launcher/FlowLink Proxy-macos.sh` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к исполняемому файлу браузера (ОБЯЗАТЕЛЬНО) |
| `launcher/FlowLink Proxy-macos.sh` | `PROXY_PORT` | `8080` | Порт HTTP-прокси |
| `setup/setup-and-run-linux.sh` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к исполняемому файлу браузера (ОБЯЗАТЕЛЬНО) |
| `setup/setup-and-run-macos.sh` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к исполняемому файлу браузера (ОБЯЗАТЕЛЬНО) |
| `autostart/flowlink.service` | `ExecStart` | — | Путь к бинарнику (настраивается вручную) |
| `autostart/flowlink.service` | `FLOWLINK_DATA_DIR` | `%h/.local/share/flowlink-proxy` | Папка данных |
| `autostart/flowlink.desktop` | `Exec` | `%h/flowlink-proxy/scripts/setup/setup-and-run-linux.sh` | Путь к скрипту запуска |
| `autostart/flowlink.desktop` | `Icon` | `%h/flowlink-proxy/server/icons/icon.png` | Путь к иконке |

### Скрипты запуска

| Скрипт | Платформа | Назначение |
|--------|-----------|------------|
| `launcher/FlowLink Proxy-linux.sh` | Linux | Лаунчер: запускает бинарник (нужно указать путь к браузеру в начале файла) |
| `launcher/FlowLink Proxy-macos.sh` | macOS | Лаунчер: запускает бинарник (нужно указать путь к браузеру в начале файла) |
| `setup/setup-and-run-linux.sh` | Linux | Dev-лаунчер: venv + зависимости + запуск + браузер |
| `setup/setup-and-run-macos.sh` | macOS | Dev-лаунчер: venv + зависимости + запуск + браузер |

### Файлы автозапуска

| Файл | Платформа | Назначение |
|------|-----------|------------|
| `autostart/flowlink.service` | Linux (systemd) | Автозапуск бэкенда как сервис |
| `autostart/flowlink.desktop` | Linux (GNOME/KDE) | Ярлык в меню приложений |
| `autostart/com.flowlink.proxy.plist` | macOS (launchd) | Автозапуск бэкенда |

---

## Устранение проблем при установке

| Проблема | Причина | Решение |
|----------|---------|---------|
| Расширение пишет «Нет связи с бэкендом» | Бэкенд не запущен | Запустите `flowlink-proxy` (standalone) или `./scripts/setup/setup-and-run-linux.sh` (исходники) |
| `ERR_PROXY_CONNECTION_FAILED` | Браузер настроен на SOCKS5 вместо HTTP-прокси | Флаг должен быть `--proxy-server=127.0.0.1:8080` (HTTP, не SOCKS5) |
| Браузер не использует прокси | Браузер запущен без флага `--proxy-server` | Запускайте браузер **только** через лаунчер или ярлык |
| Порт 8080 уже занят | Другой процесс использует порт | Linux: `lsof -i :8080` → завершите старый процесс. Windows: Диспетчер задач |
| Расширение не подключается | Порт API не совпадает | Проверьте порт в настройках расширения (⚙) — должен совпадать с `--api-port` |
| `FlowLink Proxy-linux.sh: Permission denied` | Скрипт не имеет прав на выполнение | `chmod +x "FlowLink Proxy-linux.sh"` |
| Python 3 не найден | Python не установлен или не в PATH | Установите Python 3.10+ с python.org |
| «tkinter не установлен» при запуске | Python установлен без поддержки tkinter | Linux: `sudo apt install python3-tk`. macOS: `brew install python-tk`. Windows: переустановите с галочкой «tcl/tk and IDLE» |
| Браузер не найден (Path не указан) | Переменная BROWSER_PATH не отредактирована | Откройте лаунчер в текстовом редакторе, замените `ПУТЬ_К_БРАУЗЕРУ` на путь к браузеру |

Для отладки запустите с флагом `--debug` — подробные логи в консоли и файле `logs/flowlink.log`. Подробнее: [DEBUG.md](DEBUG.md)
