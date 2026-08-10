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
   - Выберите, создать ли ярлык на рабочем столе
   - Отметьте флажок автозапуска бэкенда (по умолчанию выключен)
5. Нажмите «Установить»
6. Готово! В меню «Пуск» появится ярлык «FlowLink Proxy»

**Что создаёт установщик:**
- Программа в `C:\Program Files\FlowLink Proxy\`
- Ярлык в меню «Пуск» (и на рабочем столе, если выбрано)
- Автозапуск бэкенда при входе в Windows (через реестр `HKCU\...\Run`; опциональный флажок в установщике, по умолчанию выключен)
- Бинарник `FlowLink Proxy.exe` — бэкенд

### Windows (standalone)

Без установщика, без Python. Подходит если не хотите устанавливать программу.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте установщик `FlowLink-Proxy-v<версия>-Setup.exe` — отдельный `.zip`-архив в релизах не публикуется
3. Запустите установщик и следуйте инструкциям
4. После установки бэкенд `FlowLink Proxy.exe` будет доступен в `C:\Program Files\FlowLink Proxy\`
5. Запустите `FlowLink Proxy.exe` двойным кликом

> Бэкенд запускается напрямую. Браузер выбирается через трей-меню («Выбрать браузер...») или через расширение. При повторном запуске процессы не дублируются.

### Linux (standalone)

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте архив для Linux: `.tar.gz`
3. Распакуйте архив в удобную папку
4. В папке будут файлы:
   - `FlowLink Proxy` — бэкенд (имя с пробелом)
   - `FlowLink Proxy-linux.sh` — лаунчер
   - `EULA.rtf`, `LICENSE.txt`, `README.md` — документация
5. Откройте терминал в папке и выполните:

```bash
chmod +x "FlowLink Proxy-linux.sh"
./FlowLink Proxy-linux.sh
```

> **Автоопределение бинарника:** скрипт сначала ищет `FlowLink Proxy` и `flowlink-proxy` рядом с собой (standalone), затем ищет в PATH. Браузер выбирается через трей-меню или расширение.

### Linux (.deb)

Установка через `dpkg` — самый удобный способ для Debian/Ubuntu.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте `.deb`-пакет: `flowlink-proxy_<версия>_amd64.deb`
3. Установите:

```bash
sudo dpkg -i flowlink-proxy_*.deb
```

4. Если есть проблемы с зависимостями:

```bash
sudo apt-get install -f
```

**Что создаёт пакет:**
- Бинарник: `/usr/local/bin/FlowLink Proxy` (имя с пробелом)
- Документация: `/usr/local/share/flowlink-proxy/` (EULA.rtf, LICENSE.txt)
- Ярлык меню: `flowlink.desktop` в `/usr/share/applications/` (НЕ автозапуск)

Лаунчер и шаблоны автозапуска пакет НЕ устанавливает.

**Запуск:**
```bash
"FlowLink Proxy"             # Запуск бэкенда (имя бинарника с пробелом)
```

**Удаление:**
```bash
sudo dpkg -r flowlink-proxy
```

### Linux (.rpm)

Установка через `rpm` — для Fedora/RHEL/CentOS.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте `.rpm`-пакет: `flowlink-proxy-<версия>-1.x86_64.rpm`
3. Установите:

```bash
sudo rpm -i flowlink-proxy-*.rpm
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

> **Важно:** `install.sh` и папка `scripts/autostart/` ВХОДЯТ в релизный `.tar.gz` (см. раздел «Linux (standalone)»). В архиве — бинарник `FlowLink Proxy`, лаунчер `FlowLink Proxy-linux.sh`, установщик `install.sh`, шаблоны автозапуска и документация (`EULA.rtf`, `LICENSE.txt`, `README.md`). Установщик также можно скачать отдельно:

```bash
curl -sL https://github.com/FlowHack/flowlink-proxy/releases/latest/download/install.sh -o install.sh
chmod +x install.sh
sudo ./install.sh
```

Скрипт автоматически:
- Определяет платформу (Linux) и архитектуру (x64/arm64)
- Устанавливает бинарник в `/usr/local/bin/`
- Копирует документацию в `/usr/local/share/FlowLink Proxy/`
- Устанавливает лаунчер и шаблоны автозапуска

### macOS (.pkg)

Автоматическая установка через стандартный установщик macOS.

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте `.pkg`-пакет для вашей архитектуры:
   - `flowlink-proxy-<версия>-macos-x64.pkg` — Intel
   - `flowlink-proxy-<версия>-macos-arm64.pkg` — Apple Silicon (M1/M2/M3)
3. Дважды кликните по скачанному файлу
4. Следуйте инструкциям установщика

**Что создаёт пакет:**
- Бинарник: `/usr/local/bin/FlowLink Proxy` (имя с пробелом)
- Документация: `/usr/local/share/flowlink-proxy/` (EULA.rtf, LICENSE.txt)

> Пакет НЕ устанавливает лаунчер и НЕ создаёт LaunchAgent `~/Library/LaunchAgents/com.flowlink.proxy.plist` — это делает `install.sh`.

**Удаление:**
```bash
sudo rm "/usr/local/bin/FlowLink Proxy"
sudo rm -rf /usr/local/share/flowlink-proxy
```

> Строка `rm ~/Library/LaunchAgents/com.flowlink.proxy.plist` не нужна — `.pkg` не создаёт LaunchAgent. Она актуальна только для `install.sh`, где LaunchAgent создаётся при установке (см. раздел «macOS (standalone)» → «Автозапуск»).

### macOS (standalone)

1. Перейдите на [страницу релизов](https://github.com/FlowHack/flowlink-proxy/releases/latest)
2. Скачайте архив для macOS: `.tar.gz` (Intel `.x64` или Apple Silicon `.arm64`)
3. Распакуйте архив в удобную папку
4. В папке будут файлы:
   - `FlowLink Proxy` — бэкенд (имя с пробелом)
   - `FlowLink Proxy-macos.sh` — лаунчер
   - `EULA.rtf`, `LICENSE.txt`, `README.md` — документация
5. Откройте терминал в папке и выполните:

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
scripts\setup\setup-and-run.bat           # Windows (CMD)
```

Скрипт автоматически:
- Проверяет наличие Python и tkinter
- Создаёт виртуальное окружение (`venv/`)
- Устанавливает зависимости
- Запускает бэкенд (`python -m server`)

> Скрипт запускает только бэкенд. Браузер выбирается через трей-меню или расширение.

Или вручную:

```bash
python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows
pip install -r server/requirements.txt
python -m server
```

#### Зависимость: tkinter

Для системного трея и всех диалогов бэкенда (выбор браузера, предупреждения, уведомления) требуется **tkinter**. Скрипт запуска и сборки проверяют его наличие автоматически и предлагают установить.

| Платформа | tkinter по умолчанию | Как установить |
|-----------|---------------------|----------------|
| **Windows** (python.org) | ✅ Включён | Не нужно |
| **macOS** (python.org) | ✅ Включён | Не нужно |
| **macOS** (Homebrew) | ❌ Отсутствует | `brew install python-tk` |
| **Linux** | ❌ Отсутствует | `sudo apt install python3-tk` (Debian/Ubuntu) |

> Если tkinter не установлен, трей не запускается, а диалоги бэкенда (выбор браузера, предупреждения) не отображаются. Установите tkinter для вашей ОС.

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
| Linux / macOS | `~/.FlowHack/FlowLink Proxy/` → `rm -rf ~/.FlowHack/FlowLink\ Proxy/` |
| Windows | `%APPDATA%\FlowHack\FlowLink Proxy\` → `rmdir /s /q "%APPDATA%\FlowHack\FlowLink Proxy"` |

---

## Сборка бинарников

Для сборки standalone-бинарников необходим Python 3.10+ и PyInstaller.

### Linux / macOS

```bash
./scripts/build/build.sh
```

Результат: `releases/FlowLink Proxy`

### Windows

```batch
scripts\build\build.bat
```

Результат: `releases\FlowLink Proxy.exe`

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

Результат: `releases/flowlink-proxy_<версия>_<арх>.deb`

### Сборка .rpm-пакета (Linux)

```bash
./scripts/build/build.sh
./scripts/build/build-rpm.sh
```

Результат: `~/rpmbuild/RPMS/x86_64/flowlink-proxy-<версия>-1.x86_64.rpm`

### Сборка .pkg-пакета (macOS)

```bash
./scripts/build/build.sh
./scripts/build/build-pkg.sh
```

Результат: `releases/flowlink-proxy-<версия>-macos-<арх>.pkg`

### Сборка установщика Windows

1. Установите [Inno Setup 6](https://jrsoftware.org/isdl.php)
2. Соберите бинарник: `scripts\build\build.bat`
3. Откройте `scripts/installer/flowlink-installer.iss` в Inno Setup → Build → Compile

Результат: `releases/FlowLink-Proxy-v<версия>-Setup.exe`

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

> **Если вы используете установщик или лаунчер (`.sh`) — этот шаг выполняется автоматически.** Раздел ниже для тех, кто настраивает браузер вручную.

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

### Выбор браузера через GUI

После запуска бэкенда вы можете выбрать браузер через системный трей:

1. Нажмите правой кнопкой мыши на иконку FlowLink Proxy в трее
2. Выберите пункт «Выбрать браузер...»
3. Откроется диалог со списком найденных браузеров
4. Кликните по нужному браузеру — путь сохранится автоматически
5. Если браузер не найден, нажмите «Указать вручную» и выберите исполняемый файл

В диалоге выбора браузера выбранный браузер подсвечивается зелёной галочкой, а вручную указанный ненайденный браузер отображается в списке как обычный элемент.

Также можно указать путь через CLI при запуске:

```bash
python -m server --browser-path "/path/to/browser"
```

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
3. **Перезапустите** бэкенд

### Параллельный запуск нескольких экземпляров

FlowLink Proxy поддерживает запуск нескольких экземпляров одновременно, каждый со своим набором портов. Это полезно для разделения трафика по разным прокси-наборам.

```bash
# Первый экземпляр (порты по умолчанию)
"FlowLink Proxy" --proxy-port 8080 --api-port 8081

# Второй экземпляр (другие порты, в диапазоне автопоиска 8080–8090)
"FlowLink Proxy" --proxy-port 8084 --api-port 8085
```

Расширение автоматически обнаруживает доступный бэкенд, сканируя порты API в диапазоне **8080–8090** (см. `extension/shared/port_discovery.js`). Если нужно, чтобы расширение подключалось к конкретному экземпляру — укажите его API-порт вручную в настройках расширения.

> **Примечание:** ключ `parallel_launch` существует в `.flowlink-settings` и влияет на поведение запуска браузера при параллельных экземплярах, однако UI для его записи нет — значение можно задать только вручную в файле.

---

## Автозапуск

### Автозапуск через системный трей

После запуска бэкенда настройте автозапуск через меню в трее:

- **Автозапуск браузера** — браузер будет автоматически запускаться при старте бэкенда
- **Запуск с системой** — бэкенд будет автоматически запускаться при входе в систему

Все настройки сохраняются в файле `.flowlink-settings` в директории данных.

### Windows

При установке через установщик — настраивается автоматически.

**Ручная настройка:**
1. `Win+R` → `shell:startup` → Enter
2. Создайте ярлык для `FlowLink Proxy.exe` в открывшейся папке

### Linux (systemd)

1. Скопируйте бинарник:
   ```bash
   mkdir -p ~/.local/share/flowlink-proxy
   cp "FlowLink Proxy" ~/.local/share/flowlink-proxy/
   ```
2. Отредактируйте `scripts/autostart/flowlink.service` — укажите правильный путь в `ExecStart`
3. Установите и запустите:
   ```bash
   systemctl --user enable "$PWD/scripts/autostart/flowlink.service"
   systemctl --user start flowlink.service
   ```

> **Настройка `flowlink.service`:** файл содержит переменные `ExecStart`, `WorkingDirectory`, `Environment`. Путь к бинарнику и порты настраиваются в этих строках.

### Linux (автозагрузка рабочего стола)

Добавьте `scripts/autostart/flowlink.desktop` в автозагрузку вашего окружения.

> **Настройка `flowlink.desktop`:** `Exec` — путь к бинарнику `FlowLink Proxy` (пробел экранируется как `\ `, например `Exec=/usr/local/bin/FlowLink\ Proxy`).

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
| Браузер не найден (Path не указан) | Браузер не выбран | Выберите браузер через трей-меню («Выбрать браузер...») или в расширении |

Для отладки запустите с флагом `--debug` — подробные логи в консоли и файле `FlowLink Proxy.log` в директории данных. Подробнее: [DEBUG.md](DEBUG.md)
