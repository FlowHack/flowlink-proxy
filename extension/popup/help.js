/**
 * @fileoverview
 * Тексты помощи и переключение вкладок модального окна.
 * Единственная ответственность: help-контент и управление его отображением.
 */

import { GITHUB_RELEASES_URL, EXTENSION_STORE_URL } from '../shared/constants.js';
import { escapeHtml } from '../shared/dom.js';
import { copyEmailToClipboard } from '../shared/utils.js';
import { showModal } from './modal.js';

/** Email поддержки — сноска внизу каждого раздела помощи. */
const _EMAIL = 'flowlink.proxy@atomicmail.io';
const _EMAIL_FOOTER = `
  <p class="help-email-footer">
    Не удалось решить проблему?
    Напишите на <span class="help-email-copy" data-email="${_EMAIL}" title="Нажмите, чтобы скопировать">${_EMAIL}</span> — поможем.
  </p>`;

/** Блок с портами по умолчанию (используется в нескольких разделах). */
const _PORTS_DEFAULT_TABLE = `
    <h3>Порты по умолчанию</h3>
    <table class="help-ports-table">
      <tr class="help-ports-row">
        <td class="help-ports-cell"><code>8080</code></td>
        <td class="help-ports-cell">Прокси-сервер (для браузера)</td>
      </tr>
      <tr>
        <td class="help-ports-cell"><code>8081</code></td>
        <td class="help-ports-cell">API-сервер (для расширения)</td>
      </tr>
    </table>`;

/** Блок troubleshooting по портам (используется в windows/linux/macos/source). */
const _PORTS_TROUBLESHOOT = `
    <h3>Проблемы с портами</h3>
    <p>Если вы меняли порты через <code>--proxy-port</code> или <code>--api-port</code>:</p>
    <ol>
      <li><strong>Расширение не находит бэкенд.</strong>
        Автопоиск порта работает в диапазоне 8080–8090. Если API-порт за его пределами:
        <ol type="a">
          <li>Нажмите ⚙ (шестерёнка внизу popup)</li>
          <li>Введите порт API (должен совпадать с <code>--api-port</code> на бэкенде)</li>
          <li>Нажмите «Сохранить»</li>
        </ol>
      </li>
      <li><strong>Браузер не может подключиться к прокси.</strong>
        Убедитесь, что <code>--proxy-port</code> на бэкенде совпадает с настройками прокси в браузере.
        По умолчанию: <code>8080</code>.
      </li>
      <li><strong>Порт уже занят.</strong>
        Другой процесс использует тот же порт. Проверьте:
        <br><code>lsof -i :8080</code> (Linux/macOS) или
        <code>netstat -ano | findstr :8080</code> (Windows)
      </li>
      <li><strong>Посмотрите порты в логах.</strong>
        Запустите бэкенд с <code>--debug</code> — в логах будет указан фактический порт:
        <br><code>python -m server --debug --api-port 9091</code>
      </li>
    </ol>`;

/**
 * Тексты помощи для разных режимов.
 * Ключи:
 *   windows/linux/macos/source — установка (заголовок «Настройка FlowLink Proxy»).
 *   port — настройка порта и диагностика.
 *   updateExe/updateSource/updateExt — обновление (заголовок «Обновление»).
 *   autostartHelp — помощь по настройке автозапуска браузера.
 */
const HELP_TEXTS = {
  windows: `
    <h3>1. Скачайте установщик</h3>
    <ol>
      <li>Перейдите по ссылке <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Скачайте <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Установите</h3>
    <ol>
      <li>Запустите установщик</li>
      <li>На странице выбора браузера укажите ваш браузер (автопоиск или вручную)</li>
      <li>Установщик создаст:
        <ul>
          <li>Программу в <code>C:\\Program Files\\FlowLink Proxy\\</code></li>
          <li>Ярлык в меню «Пуск» и на рабочем столе</li>
          <li>Автозапуск бэкенда при входе в Windows</li>
          <li>Ярлык для запуска бэкенда</li>
        </ul>
      </li>
    </ol>
    <h3>3. Запустите</h3>
    <ol>
      <li>Нажмите «FlowLink Proxy» в меню «Пуск» или на рабочем столе</li>
      <li>Бэкенд и браузер запустятся автоматически</li>
    </ol>
    <h3>Установка расширения</h3>
    <ol>
      <li>Откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>)</li>
      <li>Включите «Режим разработчика»</li>
      <li>Нажмите «Загрузить распакованное расширение»</li>
      <li>Выберите папку <code>extension\\</code> внутри установленной директории</li>
    </ol>
    ${EXTENSION_STORE_URL
      ? `<p>Или установите из магазина: <a href="${escapeHtml(EXTENSION_STORE_URL)}" target="_blank" rel="noopener">открыть страницу расширения</a></p>`
      : '<p>Расширение будет доступно в Chrome Web Store после публикации.</p>'
    }
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
  `,
  linux: `
    <h3>1. Установите Python 3.10+</h3>
    <ol>
      <li><strong>Debian/Ubuntu:</strong> <code>sudo apt install python3 python3-venv python3-pip</code></li>
      <li><strong>Fedora:</strong> <code>sudo dnf install python3 python3-virtualenv python3-pip</code></li>
      <li><strong>Arch:</strong> <code>sudo pacman -S python python-virtualenv python-pip</code></li>
      <li>Проверьте: <code>python3 --version</code></li>
    </ol>
    <h3>2. Получите исходный код</h3>
    <ol>
      <li><strong>Через Git:</strong> <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li><strong>Или ZIP:</strong> скачайте со <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
    </ol>
    <h3>3. Запустите</h3>
    <ol>
      <li><code>cd flowlink-proxy</code></li>
      <li>Создайте виртуальное окружение: <code>python3 -m venv venv</code></li>
      <li>Активируйте: <code>source venv/bin/activate</code></li>
      <li>Установите зависимости: <code>pip install -r requirements.txt</code></li>
      <li>Запустите бэкенд: <code>python3 -m server</code></li>
    </ol>
    <h3>Установка расширения</h3>
    <ol>
      <li>Откройте <code>chrome://extensions</code></li>
      <li>Включите «Режим разработчика»</li>
      <li>Нажмите «Загрузить распакованное расширение»</li>
      <li>Выберите папку <code>extension/</code></li>
    </ol>
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
  `,
  macos: `
    <h3>1. Установите Python 3.10+</h3>
    <ol>
      <li><strong>Homebrew:</strong> <code>brew install python@3.12</code></li>
      <li><strong>Или:</strong> скачайте с <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">официального сайта</a></li>
      <li>Проверьте: <code>python3 --version</code></li>
    </ol>
    <h3>2. Получите исходный код</h3>
    <ol>
      <li><strong>Через Git:</strong> <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li><strong>Или ZIP:</strong> скачайте со <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
    </ol>
    <h3>3. Запустите</h3>
    <ol>
      <li><code>cd flowlink-proxy</code></li>
      <li>Создайте виртуальное окружение: <code>python3 -m venv venv</code></li>
      <li>Активируйте: <code>source venv/bin/activate</code></li>
      <li>Установите зависимости: <code>pip install -r requirements.txt</code></li>
      <li>Запустите бэкенд: <code>python3 -m server</code></li>
    </ol>
    <h3>Установка расширения</h3>
    <ol>
      <li>Откройте <code>chrome://extensions</code></li>
      <li>Включите «Режим разработчика»</li>
      <li>Нажмите «Загрузить распакованное расширение»</li>
      <li>Выберите папку <code>extension/</code></li>
    </ol>
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
  `,
  source: `
    <h3>1. Установите Python 3.10+</h3>
    <ol>
      <li>Скачайте Python с <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">официального сайта</a></li>
      <li>При установке обязательно отметьте «Add Python to PATH»</li>
      <li>Проверьте: <code>python --version</code></li>
    </ol>
    <h3>2. Получите исходный код</h3>
    <ol>
      <li><strong>Через Git:</strong> <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li><strong>Или ZIP:</strong> скачайте со <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
    </ol>
    <h3>3. Запустите</h3>
    <ol>
      <li><code>cd flowlink-proxy</code></li>
      <li>Создайте виртуальное окружение: <code>python -m venv venv</code></li>
      <li>Активируйте: <code>source venv/bin/activate</code> (Linux/macOS) или <code>venv\\Scripts\\activate</code> (Windows)</li>
      <li>Установите зависимости: <code>pip install -r requirements.txt</code></li>
      <li>Запустите бэкенд: <code>python -m server</code></li>
    </ol>
    <h3>Установка расширения</h3>
    <p>Откройте <code>chrome://extensions</code> → «Режим разработчика» → «Загрузить распакованное расширение» → папка <code>extension/</code>.</p>
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
  `,
  port: `
    <h3>Настройка порта</h3>

    <div class="help-section" id="help-port">
      <h4>🔌 Автоматическое обнаружение</h4>
      <p>Бэкенд по умолчанию слушает порт <strong>8081</strong>. Расширение автоматически сканирует порты с 8080 по 8090 для поиска бэкенда.</p>
      <p>При нажатии «Повторить» расширение проверит текущий порт, а затем просканирует диапазон 8080–8090. Если бэкенд найден на другом порту, расширение подключится к нему автоматически.</p>
    </div>

    <div class="help-section" id="help-port-manual">
      <h4>⚙ Ручная настройка порта</h4>
      <ol>
        <li>Нажмите кнопку ⚙ внизу popup.</li>
        <li>В поле «Порт API» укажите номер порта, на котором запущен бэкенд.</li>
        <li>Нажмите «Сохранить».</li>
        <li>Расширение переподключится к новому порту.</li>
      </ol>
      <p><strong>Важно:</strong> Если вы меняете порт в расширении, убедитесь, что бэкенд запущен на том же порту. Порт бэкенда можно изменить через аргумент командной строки: <code>--api-port 9090</code>.</p>
    </div>

    ${_PORTS_DEFAULT_TABLE}

    <div class="help-section" id="help-diagnose">
      <h4>🩺 Диагностика</h4>
      <p>Если ни один из вариантов не помог, попробуйте следующее:</p>
      <ul>
        <li>Проверьте, запущен ли процесс бэкенда (в диспетчере задач или <code>ps aux | grep flowlink</code>).</li>
        <li>Проверьте логи бэкенда на наличие ошибок (правый клик на иконке в трее → «Посмотреть логи»).</li>
        <li>Перезапустите бэкенд.</li>
        <li>Перезапустите браузер.</li>
        <li>Временно отключите антивирус или файрволл для проверки.</li>
      </ul>
    </div>
  `,
  updateExe: (tag) => `
    <h3>Установщик</h3>
    <ol>
      <li>Скачайте новый установщик со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Запустите — установщик заменит файлы автоматически</li>
      <li>Бэкенд будет перезапущен</li>
    </ol>
    <h3>Standalone-бинарник</h3>
    <ol>
      <li>Скачайте новый архив со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Остановите старый процесс (системный трей → «Выход»)</li>
      <li>Замените файлы и запустите новый</li>
    </ol>
    ${_EMAIL_FOOTER}
  `,
  updateSource: (tag) => `
    <ol>
      <li><strong>Через Git:</strong> <code>git pull</code></li>
      <li><strong>Или ZIP:</strong> скачайте новый архив, распакуйте поверх старой папки</li>
      <li>Остановите старый процесс, перезапустите: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER}
  `,
  updateExt: (tag) => `
    <ol>
      <li><strong>Из магазина:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked:</strong> откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>), нажмите «Обновить» (круглая стрелка)</li>
    </ol>
    ${_EMAIL_FOOTER}
  `,
  license: `
    <h3>Лицензия</h3>
    <p>FlowLink Proxy распространяется под лицензией <strong>GNU AGPL v3</strong>.</p>
    <p>При использовании вы соглашаетесь с условиями
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">EULA.rtf</a> и
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">LICENSE.txt</a>.
    </p>
    ${_EMAIL_FOOTER}
  `,
  autostartHelp: `
    <h3>Автозапуск браузера</h3>
    <p>FlowLink Proxy может автоматически запускать браузер при старте бэкенда.</p>
    <h4>Как настроить</h4>
    <ol>
      <li>Откройте настройки расширения (кнопка ⚙ внизу popup).</li>
      <li>Включите тумблер «Автозапуск браузера».</li>
      <li>Выберите браузер из списка обнаруженных или укажите путь вручную.</li>
      <li>Бэкенд автоматически запустит выбранный браузер при старте.</li>
    </ol>
    <h4>Как это работает</h4>
    <p>При запуске бэкенд проверяет настройки автозапуска. Если автозапуск включён и браузер выбран, бэкенд запускает браузер с необходимыми параметрами прокси. Вам не нужно запускать браузер вручную или использовать дополнительные скрипты.</p>
    <h4>Если браузер не запускается</h4>
    <ul>
      <li>Убедитесь, что в настройках расширения выбран браузер и указан корректный путь.</li>
      <li>Проверьте, что бэкенд запущен (зелёный индикатор в popup).</li>
      <li>Попробуйте перезапустить бэкенд.</li>
    </ul>
    ${_EMAIL_FOOTER}
  `,
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;
/** @type {boolean} True, когда модалка открыта в режиме «Автозапуск — помощь». */
let _isAutostartHelpMode = false;

/** Список вкладок help-модалки (порядок отображения). */
const _TABS = ['windows', 'linux', 'macos', 'source', 'port'];

/**
 * Открывает модальное окно помощи.
 * @param {string} [tab] — вкладка ('windows', 'linux', 'macos', 'source', 'port').
 *   Если не указана, открывается в режиме установки.
 * @param {boolean} [isUpdate] — режим обновления.
 * @param {boolean} [isAutostartHelp] — режим помощи по настройке автозапуска браузера.
 */
export function openHelpModal(tab, isUpdate, isAutostartHelp) {
  _isUpdateMode = !!isUpdate;
  _isAutostartHelpMode = !!isAutostartHelp;
  const isWindows = (navigator.userAgentData?.platform || navigator.platform).includes('Win');
  const defaultTab = isWindows ? 'windows' : 'linux';
  const title = document.querySelector('#modal-help .modal-title');
  if (!title) return;
  if (isAutostartHelp) {
    title.textContent = 'Автозапуск браузера';
  } else if (isUpdate) {
    title.textContent = 'Обновление';
  } else {
    title.textContent = 'Настройка FlowLink Proxy';
  }
  if (isAutostartHelp) {
    _hideTabs();
    _showAutostartHelpContent();
  } else {
    _showTabs();
    switchHelpTab(tab || defaultTab);
  }
  showModal('modal-help');
  _setupEmailCopyHandler();
}

/** Скрывает панель вкладок модалки помощи. */
function _hideTabs() {
  const tabsEl = document.getElementById('modal-tabs');
  if (tabsEl) tabsEl.classList.add('hidden');
}

/** Показывает панель вкладок модалки помощи. */
function _showTabs() {
  const tabsEl = document.getElementById('modal-tabs');
  if (tabsEl) tabsEl.classList.remove('hidden');
}

/** Показывает контент помощи по автозапуску (без вкладок). */
function _showAutostartHelpContent() {
  const container = document.getElementById('help-content');
  if (!container) return;
  container.innerHTML = HELP_TEXTS.autostartHelp;
}

/**
 * Копирует email в буфер обмена и показывает toast.
 * Использует shared/utils.js copyEmailToClipboard.
 * @param {string} email — адрес для копирования.
 */
function _copyEmailToClipboard(email) {
  copyEmailToClipboard(email, window.__flowlinkShowToast);
}

/** Флаг: обработчик делегирования уже установлен. */
let _emailHandlerAttached = false;

/**
 * Устанавливает делегированный обработчик клика по .help-email-copy
 * на контейнере #help-content. Вызывается один раз при первом открытии.
 */
function _setupEmailCopyHandler() {
  if (_emailHandlerAttached) return;
  const container = document.getElementById('help-content');
  if (!container) return;
  container.addEventListener('click', (e) => {
    const span = e.target.closest('.help-email-copy');
    if (span) {
      const email = span.dataset.email || span.textContent.trim();
      _copyEmailToClipboard(email);
    }
  });
  _emailHandlerAttached = true;
}

/**
 * Переключает вкладку в окне помощи.
 * @param {string} tab — имя вкладки ('windows', 'linux', 'macos', 'source', 'port').
 */
export function switchHelpTab(tab) {
  // Если открыт режим autostartHelp — вкладки не нужны
  if (_isAutostartHelpMode) {
    _showAutostartHelpContent();
    return;
  }

  _TABS.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.toggle('active', t === tab);
  });

  const container = document.getElementById('help-content');
  if (!container) return;

  if (_isUpdateMode) {
    // В режиме обновления: windows → updateExe, linux/macos/source → updateSource, port → updateExt
    const key = tab === 'windows' ? 'updateExe'
      : tab === 'source' ? 'updateSource'
      : 'updateExt';
    const updateText = document.getElementById('update-text');
    const rawTag = updateText
      ? updateText.textContent.replace(/^Доступно обновление\s*/i, '').trim()
      : '';
    const tag = escapeHtml(rawTag);
    const label = tab === 'windows' ? 'Windows (.exe)'
      : tab === 'source' ? 'Исходный код'
      : 'Расширение';
    container.innerHTML = `<h3>${label}</h3>`
      + HELP_TEXTS[key](tag);
  } else {
    const content = HELP_TEXTS[tab] || '';
    container.innerHTML = content + _EMAIL_FOOTER;
  }
}
