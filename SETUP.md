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
7. [Скрипты](#скрипты)

---

## Установка бэкенда

### Windows (установщик)

Рекомендуемый способ. Не требует Python.

1. Перейдите на [страницу релизов](https://github.com/flowhack/flowlink-proxy/releases/latest)
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
- `flowlink-proxy-run.bat` — лаунчер, запускающий бэкенд и браузер с прокси

### Windows (standalone)

Без установщика, без Python. Подходит если не хотите устанавливать программу.

1. Перейдите на [страницу релизов](https://github.com/flowhack/flowlink-proxy/releases/latest)
2. Нажмите «Assets» → скачайте архив для Windows (`.zip`)
3. Распакуйте архив в **любую удобную папку** (например `C:\FlowLink Proxy\`)
4. В папке будут два файла:
   - `FlowLink Proxy.exe` — бэкенд
   - `flowlink-proxy-run.bat` — лаунчер
5. **Откройте `flowlink-proxy-run.bat` в текстовом редакторе** (ПКМ → «Изменить»)
6. Найдите строку `set BROWSER_PATH=ПУТЬ_К_БРАУЗЕРУ` и замените путь. Примеры:
   ```
   set BROWSER_PATH=C:\Program Files\Yandex\YandexBrowser\Application\browser.exe
   set BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
   set BROWSER_PATH=C:\Program Files\Microsoft\Edge\Application\msedge.exe
   ```
7. **Сохраните** файл
8. Запустите `flowlink-proxy-run.bat` двойным кликом

> Лаунчер автоматически запустит бэкенд и браузер с флагом `--proxy-server`. При повторном запуске процессы не дублируются.

### Linux / macOS (standalone)

1. Перейдите на [страницу релизов](https://github.com/flowhack/flowlink-proxy/releases/latest)
2. Скачайте архив для вашей ОС:
   - **Linux:** `.tar.gz` или `.zip`
   - **macOS:** `.zip`
3. Распакуйте архив в удобную папку
4. В папке будут два файла:
   - `FlowLink Proxy` — бэкенд
   - `flowlink-proxy-run.sh` — лаунчер
5. **Откройте `flowlink-proxy-run.sh` в текстовом редакторе** и замените `ПУТЬ_К_БРАУЗЕРУ` на путь к вашему браузеру. Примеры:
   ```bash
   BROWSER_PATH="/usr/bin/google-chrome-stable"
   BROWSER_PATH="/usr/bin/chromium-browser"
   BROWSER_PATH="/usr/bin/yandex-browser"
   BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
   ```
6. Сохраните файл
7. Откройте терминал в папке и выполните:

```bash
chmod +x flowlink-proxy-run.sh
./flowlink-proxy-run.sh
```

### Исходный код (Python)

Требуется Python 3.10+.

```bash
git clone https://github.com/flowhack/flowlink-proxy.git
cd flowlink-proxy
./scripts/flowlink.sh
```

Скрипт `flowlink.sh` автоматически:
- Создаёт виртуальное окружение (`venv/`)
- Устанавливает зависимости
- Запускает бэкенд

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

> **Если вы используете установщик или лаунчер (`flowlink-proxy-run.bat` / `.sh`) — этот шаг выполняется автоматически.** Раздел ниже для тех, кто настраивает браузер вручную.

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
./scripts/flowlink.sh --proxy-port 9090 --api-port 9091
```

### После смены порта

1. **Ярлык браузера:** обновите флаг `--proxy-server=127.0.0.1:9090`
2. **Расширение:** ⚙ рядом с версией → введите API-порт → «Сохранить»
3. **Перезапустите** бэкенд

---

## Автозапуск

### Windows

При установке через установщик — настраивается автоматически.

**Ручная настройка:**
1. `Win+R` → `shell:startup` → Enter
2. Создайте ярлык для `FlowLink Proxy.exe` в открывшейся папке

### Linux (systemd)

```bash
# Отредактируйте путь в scripts/flowlink.service
systemctl --user enable "$PWD/scripts/flowlink.service"
systemctl --user start flowlink.service
```

### Linux (автозагрузка рабочего стола)

Добавьте `scripts/flowlink.desktop` в автозагрузку вашего окружения.

### macOS

Создайте скрипт запуска и добавьте в `~/Library/LaunchAgents`.

---

## Обновление

### Windows (установщик)

Скачайте и запустите новый установщик — он заменит файлы автоматически.

### Standalone-бинарник

1. Скачайте новый архив со [страницы релизов](https://github.com/flowhack/flowlink-proxy/releases/latest)
2. Остановите старый процесс (Диспетчер задач / `pkill`)
3. Замените файлы и запустите новый

### Исходный код

```bash
git pull
./scripts/flowlink.sh
# или
python -m server
```

### Расширение

- **Из магазина:** обновляется автоматически
- **Unpacked:** страница расширений → «Обновить» (круглая стрелка)

> Бэкенд и расширение должны быть одной версии. Сначала обновите бэкенд, потом расширение.

---

## Скрипты

| Скрипт | Платформа | Назначение |
|--------|-----------|------------|
| `scripts/flowlink-proxy-run.bat` | Windows | Лаунчер: запускает бэкенд + браузер (нужно указать путь к браузеру) |
| `scripts/flowlink-proxy-run.sh` | Linux / macOS | Лаунчер: запускает бэкенд + браузер (нужно указать путь к браузеру) |
| `scripts/flowlink.sh` | Linux / macOS | Dev-лаунчер: venv + зависимости + запуск (только бэкенд) |
| `scripts/build.sh` | Linux / macOS | Сборка standalone-бинарника (PyInstaller) |
| `scripts/build.bat` | Windows | Обёртка для `build.ps1` (обходит ExecutionPolicy) |
| `scripts/build.ps1` | Windows | Сборка standalone-бинарника (PyInstaller) |
| `scripts/flowlink.service` | Linux | systemd-сервис для автозапуска |
| `scripts/flowlink.desktop` | Linux | Десктоп-файл для меню приложений |

### Сборка standalone-бинарника

```bash
# Linux / macOS
./scripts/build.sh

# Windows
scripts\build.bat
```

Результат: `server/FlowLink Proxy/FlowLink Proxy.exe`

### Сборка установщика Windows

1. Установите [Inno Setup](https://jrsoftware.org/isdl.php)
2. Соберите бинарник: `scripts\build.bat`
3. Откройте `scripts/flowlink-installer.iss` в Inno Setup → Build → Compile
4. Результат: `installer/FlowLink-Proxy-vX.X.X-Setup.exe`

Подробнее: [FLOWLINK_INSTALLER.md](myAgents/FLOWLINK_INSTALLER.md)
