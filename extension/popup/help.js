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
      <li>Создайте виртуальное окружение: <code>python -m venv venv</code></li>
      <li>Активируйте: <code>source venv/bin/activate</code> (Linux/macOS) или <code>venv\Scripts\activate</code> (Windows)</li>
      <li>Установите зависимости: <code>pip install -r requirements.txt</code></li>
      <li>Запустите бэкенд: <code>python -m server</code></li>
    </ol>
    <h3>Установка расширения</h3>
    <p>Откройте <code>chrome://extensions</code> → «Режим разработчика» → «Загрузить распакованное расширение» → папка <code>extension/</code>.</p>
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
    ${_EMAIL_FOOTER}
  `,
  ext: `
    <h3>Нет подключения к бэкенду</h3>
      <p>Расширение не может связаться с бэкендом FlowLink Proxy.</p>
      <p><strong>Убедитесь, что бэкенд запущен.</strong> Если нет — откройте вкладку «Windows (.exe)» или «Исходный код» для инструкций по установке и запуску.</p>

      <div class="help-section" id="help-port">
        <h4>🔌 Настройка порта</h4>
        <p>Бэкенд по умолчанию слушает порт <strong>8081</strong>. Расширение автоматически сканирует порты с 8080 по 8090 для поиска бэкенда.</p>
        <h5>Автоматическое обнаружение</h5>
        <p>При нажатии «Повторить» расширение проверит текущий порт, а затем просканирует диапазон 8080–8090. Если бэкенд найден на другом порту, расширение подключится к нему автоматически.</p>
        <h5>Ручная настройка порта</h5>
        <ol>
          <li>Нажмите кнопку ⚙ внизу popup.</li>
          <li>В поле «Порт API» укажите номер порта, на котором запущен бэкенд.</li>
          <li>Нажмите «Сохранить».</li>
          <li>Расширение переподключится к новому порту.</li>
        </ol>
        <p><strong>Важно:</strong> Если вы меняете порт в расширении, убедитесь, что бэкенд запущен на том же порту. Порт бэкенда можно изменить через аргумент командной строки: <code>--port 9090</code>.</p>
      </div>

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

      <div class="help-section" id="help-unresolved">
        <h4>❓ Не удалось решить проблему?</h4>
        <p>Напишите на <span class="help-email-copy" data-email="${_EMAIL}" title="Нажмите, чтобы скопировать">${_EMAIL}</span> — поможем.</p>
        <p>Опишите вашу проблему и приложите логи бэкенда (правый клик на иконке в трее → «Посмотреть логи»).</p>
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
  const isWindows = (navigator.userAgentData?.platform || navigator.platform).includes('Win');
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
  // При вызове из error-state — показываем ext-контент напрямую (без вкладок)
  // При вызове из autostart-help — показываем контент напрямую (без вкладок)
  if (isAutostartHelp) {
    _hideTabs();
    _showAutostartHelpContent();
  } else if (isTroubleshoot) {
    _hideTabs();
    _showTroubleshootContent();
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

/** Показывает контент troubleshooting — только ext-раздел, без вкладок. */
function _showTroubleshootContent() {
  const container = document.getElementById('help-content');
  if (!container) return;
  container.innerHTML = HELP_TEXTS.ext;
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
    const rawTag = updateText
      ? updateText.textContent.replace(/^Доступно обновление\s*/i, '').trim()
      : '';
    const tag = escapeHtml(rawTag);
    container.innerHTML = `<h3>${tab === 'windows' ? 'Windows (.exe)' : tab === 'source' ? 'Исходный код' : 'Расширение'}</h3>`
      + HELP_TEXTS[key](tag);
  } else {
    container.innerHTML = HELP_TEXTS[tab];
  }
}
