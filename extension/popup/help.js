/**
 * @fileoverview
 * Тексты помощи и переключение вкладок модального окна.
 * Единственная ответственность: help-контент и управление его отображением.
 */

import { GITHUB_RELEASES_URL } from '../shared/constants.js';
import { escapeHtml } from '../shared/dom.js';
import { showModal } from './modal.js';

/**
 * Тексты помощи для разных вкладок модального окна.
 * windows — инструкция для Windows (.exe)
 * source — инструкция для запуска из исходников
 * update(tag) — инструкция по обновлению
 */
const HELP_TEXTS = {
  windows: `
    <h3>1. Скачайте последний релиз</h3>
    <ol>
      <li>Перейдите по ссылке <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Найдите последнюю версию и скачайте <code>FlowLink-Proxy-vX.X.X.zip</code></li>
      <li>Распакуйте ZIP в <strong>отдельную папку</strong> (например <code>C:\\FlowLink\\</code>)</li>
    </ol>
    <h3>2. Запустите gateway</h3>
    <ol>
      <li>Откройте папку и запустите <code>FlowLink Proxy.exe</code></li>
      <li>В окне консоли должны появиться строки «Прокси-сервер запущен» и «API сервер запущен»</li>
      <li>Не закрывайте это окно — оно должно быть открыто всё время работы</li>
    </ol>
    <h3>3. Настройте браузер</h3>
    <ol>
      <li>Найдите ярлык браузера → правый клик → <strong>Свойства</strong></li>
      <li>В поле «Объект» допишите <strong>после кавычки</strong>: <code>--proxy-server=127.0.0.1:8080</code></li>
      <li>Пример: <code>"C:\\Program Files\\Yandex\\YandexBrowser\\Application\\browser.exe" --proxy-server=127.0.0.1:8080</code></li>
      <li>Нажмите «Применить» и запускайте браузер только через этот ярлык</li>
    </ol>
    <h3>4. Автозагрузка (чтобы не запускать вручную)</h3>
    <ol>
      <li>Нажмите <code>Win+R</code>, введите <code>shell:startup</code>, нажмите Enter</li>
      <li>Создайте ярлык для <code>FlowLink Proxy.exe</code> и поместите его в открывшуюся папку</li>
      <li>Теперь FlowLink будет запускаться автоматически при входе в Windows</li>
    </ol>
  `,
  source: `
    <h3>1. Установите Python 3.10+</h3>
    <ol>
      <li>Скачайте Python с <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">python.org</a></li>
      <li>При установке отметьте «Add Python to PATH»</li>
    </ol>
    <h3>2. Клонируйте репозиторий</h3>
    <ol>
      <li>Откройте терминал (cmd / PowerShell): <code>git clone https://github.com/flowhack/flowlink-proxy.git</code></li>
      <li>Перейдите в папку: <code>cd flowlink-proxy</code></li>
    </ol>
    <h3>3. Установите и запустите</h3>
    <ol>
      <li>Создайте виртуальное окружение: <code>python -m venv venv</code></li>
      <li>Активируйте: <code>venv\\Scripts\\activate</code> (Windows) или <code>source venv/bin/activate</code> (Linux/macOS)</li>
      <li>Установите зависимости: <code>pip install -r server/requirements.txt</code></li>
      <li>Запустите: <code>python -m server</code></li>
    </ol>
    <h3>4. Настройте браузер</h3>
    <ol>
      <li>Добавьте флаг к ярлыку браузера: <code>--proxy-server=127.0.0.1:8080</code></li>
      <li>Инструкция — на вкладке «Windows (.exe)», шаг 3</li>
    </ol>
  `,
  update: (tag) => `
    <h3>Обновление до ${tag}</h3>
    <p>Релиз содержит обновлённый <strong>бэкенд</strong> (Python / .exe) и <strong>расширение</strong> (если используете unpacked).</p>
    <h3>Если используете .exe</h3>
    <ol>
      <li>Скачайте последний релиз со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте ZIP, замените старый <code>FlowLink Proxy.exe</code> новым в вашей папке</li>
      <li>Остановите старый процесс (закройте окно), запустите новый .exe</li>
    </ol>
    <h3>Если используете исходный код</h3>
    <ol>
      <li>Откройте терминал в папке проекта: <code>git pull</code></li>
      <li>Перезапустите: <code>python -m server</code> или <code>./scripts/flowlink.sh</code></li>
    </ol>
    <h3>Обновление расширения</h3>
    <ol>
      <li><strong>Из Chrome Web Store:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked (режим разработчика):</strong> откройте <code>chrome://extensions</code>, нажмите «Обновить» (круглая стрелка)</li>
    </ol>
    <p><em>Бэкенд и расширение должны быть одной версии. Сначала обновите бэкенд, потом расширение.</em></p>
  `,
};

/**
 * Открывает модальное окно помощи.
 * @param {string} [tab] — вкладка ('windows', 'source' или 'update').
 */
export function openHelpModal(tab) {
  const isWindows = navigator.platform.includes('Win');
  const defaultTab = isWindows ? 'windows' : 'source';
  switchHelpTab(tab || defaultTab);
  showModal('modal-help');
}

/**
 * Переключает вкладку в окне помощи.
 * @param {string} tab — имя вкладки ('windows', 'source', 'update').
 */
export function switchHelpTab(tab) {
  const tabsContainer = document.getElementById('modal-tabs');
  document.getElementById('tab-windows').classList.toggle('tab-active', tab === 'windows');
  document.getElementById('tab-source').classList.toggle('tab-active', tab === 'source');
  tabsContainer.classList.toggle('hidden', tab === 'update');
  const container = document.getElementById('help-content');
  if (tab === 'update') {
    const tag = document.getElementById('update-text').textContent.replace('Доступно обновление ', '');
    container.innerHTML = HELP_TEXTS.update(escapeHtml(tag));
  } else {
    container.innerHTML = HELP_TEXTS[tab];
  }
}
