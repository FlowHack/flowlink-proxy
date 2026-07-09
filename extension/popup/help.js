/**
 * @fileoverview
 * Тексты помощи и переключение вкладок модального окна.
 * Единственная ответственность: help-контент и управление его отображением.
 */

import { GITHUB_RELEASES_URL, EXTENSION_STORE_URL } from '../shared/constants.js';
import { escapeHtml } from '../shared/dom.js';
import { showModal } from './modal.js';

/**
 * Тексты помощи для разных режимов.
 * Ключи:
 *   windows/source/ext — установка (заголовок «Настройка FlowLink Proxy»).
 *   updateExe/updateSource/updateExt — обновление (заголовок «Обновление»).
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
          <li><code>flowlink-proxy-run.bat</code> — запускает бэкенд и браузер с прокси</li>
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
  source: `
    <h3>1. Установите Python 3.10+</h3>
    <ol>
      <li>Скачайте Python с <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">официального сайта</a></li>
      <li>При установке обязательно отметьте «Add Python to PATH»</li>
      <li>Проверьте: <code>python --version</code></li>
    </ol>
    <h3>2. Получите исходный код</h3>
    <ol>
      <li><strong>Через Git:</strong> <code>git clone https://github.com/flowhack/flowlink-proxy.git</code></li>
      <li><strong>Или ZIP:</strong> скачайте со <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
    </ol>
    <h3>3. Запустите</h3>
    <ol>
      <li><code>cd flowlink-proxy</code></li>
      <li><code>./scripts/flowlink.sh</code> — скрипт создаст venv, установит зависимости и запустит сервер</li>
    </ol>
    <h3>Установка расширения</h3>
    <p>Откройте <code>chrome://extensions</code> → «Режим разработчика» → «Загрузить распакованное расширение» → папка <code>extension/</code>.</p>
  `,
  ext: `
    <p>Расширение уже установлено — вы пользуетесь им прямо сейчас.</p>
    <p>Для его работы нужен запущенный бэкенд FlowLink Proxy.</p>
    ${EXTENSION_STORE_URL
      ? `<p>Страница расширения: <a href="${escapeHtml(EXTENSION_STORE_URL)}" target="_blank" rel="noopener">открыть в магазине</a></p>`
      : ''
    }
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
  `,
  updateSource: (tag) => `
    <ol>
      <li><strong>Через Git:</strong> <code>git pull</code></li>
      <li><strong>Или ZIP:</strong> скачайте новый архив, распакуйте поверх старой папки</li>
      <li>Остановите старый процесс, перезапустите: <code>./scripts/flowlink.sh</code></li>
    </ol>
  `,
  updateExt: (tag) => `
    <ol>
      <li><strong>Из магазина:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked:</strong> откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>), нажмите «Обновить» (круглая стрелка)</li>
    </ol>
  `,
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;

/**
 * Открывает модальное окно помощи.
 * @param {string} [tab] — вкладка ('windows', 'source', 'ext').
 *   Если не указана, открывается в режиме установки.
 * @param {boolean} [isUpdate] — режим обновления.
 */
export function openHelpModal(tab, isUpdate) {
  _isUpdateMode = !!isUpdate;
  const isWindows = navigator.platform.includes('Win');
  const defaultTab = isWindows ? 'windows' : 'source';
  const title = document.querySelector('#modal-help .modal-title');
  if (!title) return;
  title.textContent = _isUpdateMode ? 'Обновление' : 'Настройка FlowLink Proxy';
  switchHelpTab(tab || defaultTab);
  showModal('modal-help');
}

/**
 * Переключает вкладку в окне помощи.
 * @param {string} tab — имя вкладки ('windows', 'source', 'ext').
 */
export function switchHelpTab(tab) {
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
