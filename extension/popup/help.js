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
  `,
  linux: () => `
    <div class="help-sub-tabs" id="help-sub-tabs-linux">
      <button class="help-sub-tab active" data-sub="linux-bin">Бинарник (.tar.gz)</button>
      <button class="help-sub-tab" data-sub="linux-deb">Пакет (.deb)</button>
      <button class="help-sub-tab" data-sub="linux-rpm">Пакет (.rpm)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-linux">
      ${_renderSubTabContent('linux', 'linux-bin')}
    </div>
  `,
  macos: () => `
    <div class="help-sub-tabs" id="help-sub-tabs-macos">
      <button class="help-sub-tab active" data-sub="macos-intel-bin">Intel — Бинарник (.tar.gz)</button>
      <button class="help-sub-tab" data-sub="macos-intel-pkg">Intel — Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-arm-bin">ARM — Бинарник (.tar.gz)</button>
      <button class="help-sub-tab" data-sub="macos-arm-pkg">ARM — Пакет (.pkg)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos">
      ${_renderSubTabContent('macos', 'macos-intel-bin')}
    </div>
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

    <p>Если проблема не решена — обратитесь в поддержку (ссылка ниже).</p>
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
  ext: () => `
    <div class="help-sub-tabs" id="help-sub-tabs-ext">
      <button class="help-sub-tab active" data-sub="ext-crx">Из CRX</button>
      <button class="help-sub-tab" data-sub="ext-store">Chrome Web Store</button>
      <button class="help-sub-tab" data-sub="ext-source">Из исходников</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-ext">
      ${_renderSubTabContent('ext', 'ext-crx')}
    </div>
  `,
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;
/** @type {boolean} True, когда модалка открыта в режиме «Автозапуск — помощь». */
let _isAutostartHelpMode = false;

/** Список вкладок help-модалки (порядок отображения). */
const _TABS = ['windows', 'linux', 'macos', 'source', 'port', 'ext'];

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

  // Если вкладка linux/macos/ext — вешаем обработчик на подвкладки
  if (tab === 'linux' || tab === 'macos' || tab === 'ext') {
    _setupSubTabHandler(tab);
  }
}

/**
 * Контент для подвкладок Linux и macOS.
 * @type {Object<string, Object<string, string>>}
 */
const _SUB_TEXTS = {
  linux: {
    'linux-bin': `
      <h3>Бинарник (.tar.gz)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
        <li>Запустите: <code>./flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
    'linux-deb': `
      <h3>Пакет (.deb)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.deb</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Установите: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
        <li>Запустите: <code>flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
    'linux-rpm': `
      <h3>Пакет (.rpm)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.rpm</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Установите: <code>sudo rpm -i FlowLink-Proxy-*.rpm</code></li>
        <li>Запустите: <code>flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
  },
  macos: {
    'macos-intel-bin': `
      <h3>Intel — Бинарник (.tar.gz)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
        <li>Запустите: <code>./flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
    'macos-intel-pkg': `
      <h3>Intel — Пакет (.pkg)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Установите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
        <li>Запустите: <code>flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
    'macos-arm-bin': `
      <h3>ARM — Бинарник (.tar.gz)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
        <li>Запустите: <code>./flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
    'macos-arm-pkg': `
      <h3>ARM — Пакет (.pkg)</h3>
      <ol>
        <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
        <li>Установите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
        <li>Запустите: <code>flowlink-proxy</code></li>
      </ol>
      <h3>Установка расширения</h3>
      <ol>
        <li>Откройте <code>chrome://extensions</code></li>
        <li>Включите «Режим разработчика»</li>
        <li>Нажмите «Загрузить распакованное расширение»</li>
        <li>Выберите папку <code>extension/</code></li>
      </ol>
    `,
  },
};

/**
 * Контент для подвкладок расширения (ext-вкладка).
 * @type {Object<string, string>}
 */
const _EXT_SUB_CONTENT = {
  'ext-crx': `
    <h3>Установка из CRX (GitHub Releases)</h3>
    <ol>
      <li>Скачайте <code>flowlink-proxy.crx</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Положите файл рядом с бинарником бэкенда (или в папку с программой)</li>
      <li>Запустите бэкенд — он автоматически найдёт CRX и сможет запустить браузер с расширением</li>
      <li>В меню системного трея включите «Запуск с расширением» и нажмите «Запустить браузер»</li>
    </ol>
    <div class="note">
      <strong>Примечание:</strong> CRX-расширение не требует режима разработчика и не показывает предупреждений при запуске браузера.
    </div>
  `,
  'ext-store': `
    <p>Когда расширение будет опубликовано в Chrome Web Store, информация будет дополнена.
    Пока устанавливайте расширение из <strong>CRX</strong> (вкладка «Из CRX») или из исходного кода (вкладка «Из исходников»).</p>
  `,
  'ext-source': `
    <h3>Установка из исходников</h3>
    <ol>
      <li>Откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>)</li>
      <li>Включите «Режим разработчика»</li>
      <li>Нажмите «Загрузить распакованное расширение»</li>
      <li>Выберите папку <code>extension/</code> из исходного кода проекта</li>
    </ol>
    <div class="note">
      <strong>Примечание:</strong> Этот способ требует включённого режима разработчика. При каждом запуске браузера расширение нужно загружать заново (если не используется CRX).
    </div>
  `,
};

/** Подключаем контент ext-подвкладок к общей структуре _SUB_TEXTS. */
_SUB_TEXTS.ext = _EXT_SUB_CONTENT;

/**
 * Возвращает HTML-контент для подвкладки.
 * @param {string} os — 'linux' или 'macos'
 * @param {string} subId — идентификатор подвкладки
 * @returns {string}
 */
function _renderSubTabContent(os, subId) {
  return _SUB_TEXTS[os] && _SUB_TEXTS[os][subId]
    ? _SUB_TEXTS[os][subId]
    : '<p>Контент не найден.</p>';
}

/**
 * Устанавливает обработчик переключения подвкладок для linux/macos.
 * @param {string} os — 'linux' или 'macos'
 */
function _setupSubTabHandler(os) {
  const container = document.getElementById('help-content');
  if (!container) return;

  // Удаляем старый обработчик, если был
  const oldHandler = container._subTabHandler;
  if (oldHandler) {
    container.removeEventListener('click', oldHandler);
  }

  const handler = (e) => {
    const btn = e.target.closest('.help-sub-tab');
    if (!btn) return;
    const subId = btn.dataset.sub;
    if (!subId || !subId.startsWith(os)) return;

    // Переключаем активный класс у кнопок
    const parent = btn.closest('.help-sub-tabs');
    if (parent) {
      parent.querySelectorAll('.help-sub-tab').forEach(b => b.classList.remove('active'));
    }
    btn.classList.add('active');

    // Обновляем контент
    const contentEl = document.getElementById('help-sub-content-' + os);
    if (contentEl) {
      contentEl.innerHTML = _renderSubTabContent(os, subId);
    }
  };

  container.addEventListener('click', handler);
  container._subTabHandler = handler;
}
