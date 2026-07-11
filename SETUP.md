# FlowLink Proxy — Установка и настройка

## Содержание

1. [Установка бэкенда](#установка-бэкенда)
   - [Windows (установщик)](#windows-установщик)
   - [Windows (standalone)](#windows-standalone)
   - [Linux / macOS (standalone)](#linux--macos-standalone)
   - [Исходный код (Python)](#исходный-код-python)
2. [Установка расширения](#установка-расширения)
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
   - **`BROWSER_PATH`** — путь к exe-файлу вашего браузера. Замените `ПУТЬ_К_БРАУЗЕРУ`:
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
2. Скачайте архив для Linux: `.tar.gz` или `.zip`
3. Распакуйте архив в удобную папку
4. В папке будут файлы:
   - `FlowLink Proxy` — бэкенд
   - `FlowLink Proxy.sh` — лаунчер
   - `README.md`, `SETUP.md`, `DEBUG.md` — документация
5. **Откройте `FlowLink Proxy.sh` в текстовом редакторе**. В начале файла найдите блок `═══ НАСТРОЙКА ПЕРЕМЕННЫХ ═══`. Два параметра:
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
chmod +x "FlowLink Proxy.sh"
./FlowLink Proxy.sh
```

> **Автоопределение бинарника:** скрипт сначала ищет `FlowLink Proxy` рядом с собой (standalone), затем в `server/FlowLink Proxy/` (dev-сборка).

### macOS

На данный момент **готовый standalone-бинарник для macOS не поставляется** в релизах. Однако вы можете легко собрать его сами с помощью скрипта `build.sh`:

```bash
cd flowlink-proxy
./scripts/build.sh
```

Скрипт `build.sh` автоматически:
1. Создаёт/использует виртуальное окружение
2. Устанавливает зависимости (cryptography, pystray, Pillow)
3. Собирает standalone-бинарник через PyInstaller

Результат: `server/FlowLink Proxy/FlowLink Proxy`

После сборки:
1. Распакуйте полученный бинарник в удобную папку
2. Отредактируйте `FlowLink Proxy.sh` — укажите `BROWSER_PATH`
3. Запустите: `./FlowLink Proxy.sh`

**Или используйте исходный код напрямую:**

```bash
git clone https://github.com/FlowHack/flowlink-proxy.git
cd flowlink-proxy
./scripts/FlowLink Proxy Source.sh
```

### Исходный код (Python)

Требуется Python 3.10+.

```bash
git clone https://github.com/FlowHack/flowlink-proxy.git
cd flowlink-proxy
./scripts/FlowLink Proxy Source.sh
```

Скрипт `FlowLink Proxy Source.sh` автоматически:
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
./scripts/FlowLink Proxy Source.sh --proxy-port 9090 --api-port 9091
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
./scripts/FlowLink Proxy Source.sh
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
| `FlowLink Proxy.bat` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к exe-файлу браузера (ОБЯЗАТЕЛЬНО) |
| `FlowLink Proxy.bat` | `PROXY_PORT` | `8080` | Порт HTTP-прокси |
| `FlowLink Proxy.sh` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к исполняемому файлу браузера (ОБЯЗАТЕЛЬНО) |
| `FlowLink Proxy.sh` | `PROXY_PORT` | `8080` | Порт HTTP-прокси |
| `FlowLink Proxy Source.sh` | `BROWSER_PATH` | `ПУТЬ_К_БРАУЗЕРУ` | Путь к исполняемому файлу браузера (ОБЯЗАТЕЛЬНО) |
| `FlowLink Proxy Source.sh` | `PROXY_PORT` | `8080` | Порт HTTP-прокси |
| `flowlink.service` | `ExecStart` | — | Путь к бинарнику (настраивается вручную) |
| `flowlink.service` | `FLOWLINK_DATA_DIR` | `%h/.local/share/flowlink-proxy` | Папка данных |
| `flowlink.desktop` | `Exec` | `%h/flowlink-proxy/scripts/FlowLink Proxy Source.sh` | Путь к скрипту запуска |
| `flowlink.desktop` | `Icon` | `%h/flowlink-proxy/server/icons/icon.png` | Путь к иконке |

### Скрипты запуска

| Скрипт | Платформа | Назначение |
|--------|-----------|------------|
| `FlowLink Proxy.bat` | Windows | Лаунчер: запускает бэкенд + браузер (нужно указать путь к браузеру в начале файла) |
| `FlowLink Proxy.sh` | Linux / macOS | Лаунчер: запускает бэкенд + браузер (нужно указать путь к браузеру в начале файла) |
| `FlowLink Proxy Source.sh` | Linux / macOS | Dev-лаунчер: venv + зависимости + запуск + браузер (нужно указать путь к браузеру в начале файла) |

### Скрипты сборки

| Скрипт | Платформа | Назначение |
|--------|-----------|------------|
| `build.sh` | Linux / macOS | Сборка standalone-бинарника (PyInstaller) |
| `build.bat` | Windows | Обёртка для `build.ps1` (обходит ExecutionPolicy) |
| `build.ps1` | Windows | Сборка standalone-бинарника (PyInstaller) |

Результат сборки: `server/FlowLink Proxy/FlowLink Proxy`

### Файлы автозапуска

| Файл | Платформа | Назначение |
|------|-----------|------------|
| `flowlink.service` | Linux (systemd) | Автозапуск бэкенда как сервис |
| `flowlink.desktop` | Linux (GNOME/KDE) | Ярлык в меню приложений |

### Сборка standalone-бинарника

```bash
# Linux / macOS
./scripts/build.sh

# Windows
scripts\build.bat
```

Результат: `server/FlowLink Proxy/FlowLink Proxy.exe` (Windows) или `server/FlowLink Proxy/FlowLink Proxy` (Linux/macOS)

### Сборка установщика Windows

1. Установите [Inno Setup](https://jrsoftware.org/isdl.php)
2. Соберите бинарник: `scripts\build.bat`
3. Откройте `scripts/flowlink-installer.iss` в Inno Setup → Build → Compile
4. Результат: `installer/FlowLink-Proxy-vX.X.X-Setup.exe`

Подробнее: [FLOWLINK_INSTALLER.md](myAgents/FLOWLINK_INSTALLER.md)

---

## Устранение проблем при установке

| Проблема | Причина | Решение |
|----------|---------|---------|
| `FlowLink Proxy.bat` не находит exe | bat-файл лежит не в одной папке с exe | Поместите bat в ту же папку, что и FlowLink Proxy.exe |
| `FlowLink Proxy.sh: Permission denied` | Скрипт не имеет прав на выполнение | `chmod +x "FlowLink Proxy.sh"` |
| `FlowLink Proxy Source.sh: Python 3 не найден` | Python не установлен или не в PATH | Установите Python 3.10+ с python.org |
| PowerShell блокирует `build.ps1` | Политика выполнения скриптов | Используйте `scripts\build.bat` или `powershell -ExecutionPolicy Bypass -File build.ps1` |
| Браузер не использует прокси | Браузер запущен без флага `--proxy-server` | Используйте лаунчер или настройте ярлык |
| Нет русских символов в консоли | Кодировка консоли не UTF-8 | `FlowLink Proxy.bat` уже содержит `chcp 65001` — перезапустите |
