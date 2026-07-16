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

/** Блок troubleshooting по портам (используется в windows/source). */
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
 *   windows/source/ext — установка (заголовок «Настройка FlowLink Proxy»).
 *   updateExe/updateSource/updateExt — обновление (заголовок «Обновление»).
 *   autostartHelp — отсутствие скриптов запуска (режим помощи по автозапуску).
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
          <li><code>FlowLink Proxy.bat</code> — запускает бэкенд и браузер с прокси</li>
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
    ${_EMAIL_FOOTER}
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
      <li><code>./scripts/FlowLink Proxy Source.sh</code> — скрипт создаст venv, установит зависимости и запустит сервер</li>
    </ol>
    <h3>Установка расширения</h3>
    <p>Откройте <code>chrome://extensions</code> → «Режим разработчика» → «Загрузить распакованное расширение» → папка <code>extension/</code>.</p>
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
    ${_EMAIL_FOOTER}
  `,
  ext: `
    <p>Расширение уже установлено — вы пользуетесь им прямо сейчас.</p>
    <p>Для его работы нужен запущенный бэкенд FlowLink Proxy.</p>
    ${EXTENSION_STORE_URL
      ? `<p>Страница расширения: <a href="${escapeHtml(EXTENSION_STORE_URL)}" target="_blank" rel="noopener">открыть в магазине</a></p>`
      : ''
    }
    <h3>Устранение проблем с подключением</h3>
    <p>Если расширение не может подключиться к бэкенду (красная панель «Нет связи с бэкендом»):</p>
    <ol>
      <li><strong>Убедитесь, что бэкенд запущен.</strong>
        <ul>
          <li>Windows: нажмите «FlowLink Proxy» в меню «Пуск»</li>
          <li>Linux/macOS: <code>./scripts/FlowLink Proxy Source.sh</code></li>
        </ul>
      </li>
      <li><strong>Нажмите «Повторить»</strong> — расширение автоматически проверит соединение.</li>
      <li><strong>Автообнаружение порта.</strong> Если бэкенд запущен на нестандартном порту (например, <code>--api-port 9091</code>), расширение автоматически найдёт его при открытии — сканирует порты 8080–8090.</li>
      <li><strong>Ручная настройка порта.</strong> Если бэкенд на порту за пределами 8080–8090:
        <ol type="a">
          <li>Нажмите ⚙ (шестерёнка внизу)</li>
          <li>Введите порт API (должен совпадать с <code>--api-port</code> на бэкенде)</li>
          <li>Нажмите «Сохранить»</li>
        </ol>
      </li>
      <li><strong>Проверьте порт в терминале.</strong> Запустите бэкенд с <code>--debug</code> и посмотрите в логах какой порт используется:
        <br><code>python -m server --debug --api-port 9091</code>
      </li>
    </ol>
    ${_PORTS_DEFAULT_TABLE}
    ${_EMAIL_FOOTER}
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
      <li>Остановите старый процесс, перезапустите: <code>./scripts/FlowLink Proxy Source.sh</code></li>
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
    <h3>Скрипты запуска не найдены</h3>
    <p>Расширение не нашло файлы запуска (<code>FlowLink Proxy.bat</code>, <code>FlowLink Proxy.sh</code> или <code>FlowLink Proxy Source.sh</code>) рядом с бэкендом.</p>
    <p>Это означает, что автозапуск браузера вместе с бэкендом невозможен.</p>
    <h3>Как исправить</h3>
    <p>Скопируйте скрипт запуска в ту же папку, где находится <code>FlowLink Proxy.exe</code> (или бинарник):</p>

    <h3>Windows (.exe)</h3>
    <ol>
      <li>Перейдите на страницу <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Скачайте последний релиз и распакуйте</li>
      <li>Убедитесь, что <code>FlowLink Proxy.bat</code> лежит в одной папке с <code>FlowLink Proxy.exe</code></li>
      <li>Запустите бэкенд через <code>FlowLink Proxy.bat</code></li>
    </ol>

    <h3>Linux / macOS (бинарник)</h3>
    <ol>
      <li>Перейдите на страницу <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Скачайте архив для вашей ОС и распакуйте</li>
      <li>Скопируйте <code>FlowLink Proxy.sh</code> в ту же папку, что и бинарник</li>
      <li>Дайте права на исполнение: <code>chmod +x "FlowLink Proxy.sh"</code></li>
      <li>Запустите: <code>./"FlowLink Proxy.sh"</code></li>
    </ol>

    <h3>Исходный код (Python)</h3>
    <ol>
      <li>Скачайте исходный код: <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li>Убедитесь, что скрипт <code>scripts/FlowLink Proxy Source.sh</code> на месте</li>
      <li>Запустите: <code>./scripts/"FlowLink Proxy Source.sh"</code></li>
    </ol>

    <p>После размещения скрипта запуска рядом с бэкендом, перезапустите бэкенд и заново откройте расширение — тоггл автозапуска браузера станет доступен.</p>
    ${_EMAIL_FOOTER}
  `,
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;
/** @type {boolean} True, когда модалка открыта в режиме «Автозапуск — помощь». */
let _isAutostartHelpMode = false;

/**
 * Открывает модальное окно помощи.
 * @param {string} [tab] — вкладка ('windows', 'source', 'ext').
 *   Если не указана, открывается в режиме установки.
 * @param {boolean} [isUpdate] — режим обновления.
 * @param {boolean} [isTroubleshoot] — режим устранения проблем (вызывается из error-state).
 * @param {boolean} [isAutostartHelp] — режим помощи по отсутствию скриптов запуска.
 */
export function openHelpModal(tab, isUpdate, isTroubleshoot, isAutostartHelp) {
  _isUpdateMode = !!isUpdate;
  _isAutostartHelpMode = !!isAutostartHelp;
  const isWindows = navigator.platform.includes('Win');
  const defaultTab = isWindows ? 'windows' : 'source';
  const title = document.querySelector('#modal-help .modal-title');
  if (!title) return;
  if (isAutostartHelp) {
    title.textContent = 'Автозапуск браузера';
  } else if (isUpdate) {
    title.textContent = 'Обновление';
  } else if (isTroubleshoot) {
    title.textContent = 'Подключение к бэкенду';
  } else {
    title.textContent = 'Настройка FlowLink Proxy';
  }
  // При вызове из error-state — открываем вкладку «Расширение» (там troubleshooting)
  // При вызове из autostart-help — показываем контент напрямую (без вкладок)
  if (isAutostartHelp) {
    _hideTabs();
    _showAutostartHelpContent();
  } else {
    _showTabs();
    switchHelpTab(isTroubleshoot ? 'ext' : (tab || defaultTab));
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
 * @param {string} tab — имя вкладки ('windows', 'source', 'ext').
 */
export function switchHelpTab(tab) {
  // Если открыт режим autostartHelp — вкладки не нужны
  if (_isAutostartHelpMode) {
    _showAutostartHelpContent();
    return;
  }

  const tabs = ['windows', 'source', 'ext'];
  tabs.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.toggle('tab-active', t === tab);
  });

  const container = document.getElementById('help-content');
  if (!container) return;

  if (_isUpdateMode) {
    const key = tab === 'windows' ? 'updateExe'
      : tab === 'source' ? 'updateSource'
      : 'updateExt';
    const updateText = document.getElementById('update-text');
    const rawTag = updateText ? updateText.textContent
      .replace('Доступно обновление ', '') : '';
    const tag = escapeHtml(rawTag);
    container.innerHTML = `<h3>${tab === 'windows' ? 'Windows (.exe)' : tab === 'source' ? 'Исходный код' : 'Расширение'}</h3>`
      + HELP_TEXTS[key](tag);
  } else {
    container.innerHTML = HELP_TEXTS[tab];
  }
}
