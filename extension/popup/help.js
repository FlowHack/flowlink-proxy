/**
 * @fileoverview
 * Тексты помощи и переключение вкладок модального окна.
 * Единственная ответственность: help-контент и управление его отображением.
 */

import { GITHUB_RELEASES_URL } from '../shared/constants.js';

import { showModal } from './modal.js';
import { escapeHtml } from '../shared/dom.js';

/**
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
 *   backend — установка бэкенда (с подвкладками windows/linux/macos/source).
 *   port — настройка порта и диагностика.
 *   ext — установка расширения (с подвкладками store/crx/source).
 *   updateExe/updateSource/updateExt — обновление (заголовок «Обновление»).
 *   faq — ответы на частые вопросы (FAQ).
 */
const HELP_TEXTS = {
  backend: () => `
    <p class="help-intro">Для расширения требуется приложение FlowLink Proxy. Ниже — инструкции по установке на разные системы.</p>
    <div class="help-sub-tabs" id="help-sub-tabs-backend">
      <button class="help-sub-tab active" data-sub="backend-windows">Windows</button>
      <button class="help-sub-tab" data-sub="backend-linux">Linux</button>
      <button class="help-sub-tab" data-sub="backend-macos">macOS</button>
      <button class="help-sub-tab" data-sub="backend-source">Исходный код</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-backend">
      ${_renderSubTabContent('backend', 'backend-windows')}
    </div>
  `,
  browser: `
    <h3>Выбор браузера для автозапуска</h3>
    <p>Включён автозапуск браузера, но путь к браузеру не указан. Чтобы автозапуск работал, выберите браузер в меню бэкенда.</p>
    <div class="help-section">
      <h4>Как выбрать браузер</h4>
      <ol>
        <li>Откройте меню FlowLink Proxy в системном трее (иконка в правом нижнем углу экрана).</li>
        <li>Выберите пункт <strong>«Браузер»</strong> (или «Выбрать браузер»).</li>
        <li>В открывшемся списке укажите ваш браузер (Chrome, Firefox, Edge и т.д.).</li>
        <li>Если браузера нет в списке — нажмите «Указать вручную» и выберите исполняемый файл браузера.</li>
      </ol>
      <p>После выбора браузера автозапуск будет работать: при запуске бэкенда браузер откроется автоматически.</p>
    </div>
    <p>Если вы не хотите, чтобы браузер запускался автоматически, отключите автозапуск в меню бэкенда (пункт «Автозапуск браузера»).</p>
    ${_EMAIL_FOOTER}
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
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
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
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Через Git:</strong> <code>git pull</code></li>
      <li><strong>Или ZIP:</strong> скачайте новый архив, распакуйте поверх старой папки</li>
      <li>Остановите старый процесс, перезапустите: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER}
  `,
  updateExt: (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Из магазина:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked:</strong> откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>), нажмите «Обновить» (круглая стрелка)</li>
    </ol>
    ${_EMAIL_FOOTER}
  `,
  'update-backend': (tag) => `
    <div class="help-sub-tabs" id="help-sub-tabs-update-backend">
      <button class="help-sub-tab active" data-sub="update-windows">Windows</button>
      <button class="help-sub-tab" data-sub="update-linux">Linux</button>
      <button class="help-sub-tab" data-sub="update-macos">macOS</button>
      <button class="help-sub-tab" data-sub="update-source">Исходный код</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-backend">
      ${_renderUpdateSubTabContent('update-windows', tag)}
    </div>
  `,
  'update-ext': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Обновление расширения</h3>
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
  faq: `
    <h3>Отказоустойчивость меню бэкенда</h3>
    <p>Если меню в системном трее не может быть создано (например, отсутствует компонент <code>tkinter</code> или произошла ошибка), бэкенд автоматически переключается на альтернативный вариант отображения меню.</p>
    <p>Если и альтернативный вариант не работает — приложение завершается с записью причины в лог.</p>
    <h4>Что делать</h4>
    <ol>
      <li>Проверьте, что установлены все зависимости, включая <code>tkinter</code>.</li>
      <li>Посмотрите лог — там указана причина ошибки.</li>
      <li>При необходимости запустите бэкенд с флагом <code>--no-tkinter</code> — будет использован нативный fallback-вариант меню.</li>
    </ol>

    <h3>Принудительное завершение бэкенда</h3>
    <p>Если бэкенд завис или работает постоянно, его можно завершить корректно:</p>
    <ol>
      <li><strong>Через меню трея:</strong> пункт «Выход».</li>
      <li><strong>Если меню недоступно:</strong> через диспетчер задач (Windows) или <code>kill</code> процесса (Linux/macOS).</li>
    </ol>
    <p>Это может понадобиться при обновлении, при сбоях или при смене конфигурации.</p>
    ${_EMAIL_FOOTER}
  `,
};

/**
 * Контент для подвкладок бэкенда (backend).
 * @type {Object<string, Object<string, string>>}
 */
const _BACKEND_SUB_TEXTS = {
  'backend-windows': `
    <h3>1. Скачайте установщик</h3>
    <ol>
      <li>Перейдите по ссылке <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Скачайте <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Установите</h3>
    <ol>
      <li>Запустите установщик</li>
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
      <li>Бэкенд запустится автоматически</li>
    </ol>
  `,
  'backend-linux': () => `
    <div class="help-sub-tabs" id="help-sub-tabs-linux">
      <button class="help-sub-tab active" data-sub="linux-deb">Пакет (.deb)</button>
      <button class="help-sub-tab" data-sub="linux-rpm">Пакет (.rpm)</button>
      <button class="help-sub-tab" data-sub="linux-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-linux">
      ${_renderSubTabContent('linux', 'linux-deb')}
    </div>
  `,
  'backend-macos': () => `
    <div class="help-sub-tabs" id="help-sub-tabs-macos">
      <button class="help-sub-tab active" data-sub="macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos">
      ${_renderSubTabContent('macos', 'macos-intel')}
    </div>
  `,
  'backend-source': `
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
    ${_PORTS_DEFAULT_TABLE}
    ${_PORTS_TROUBLESHOOT}
  `,
};

/**
 * Контент для подвкладок Linux (вложенные в backend-linux).
 * @type {Object<string, string>}
 */
const _LINUX_SUB_TEXTS = {
  'linux-deb': `
    <h3>Пакет (.deb)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.deb</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'linux-rpm': `
    <h3>Пакет (.rpm)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.rpm</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo rpm -i FlowLink-Proxy-*.rpm</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'linux-bin': `
    <h3>Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Запустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
};

/**
 * Контент для подвкладок macOS (вложенные в backend-macos).
 * @type {Object<string, string>}
 */
const _MACOS_SUB_TEXTS = {
  'macos-intel': () => `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-intel">
      <button class="help-sub-tab active" data-sub="macos-intel-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-intel-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-intel">
      ${_renderSubTabContent('macos-intel', 'macos-intel-pkg')}
    </div>
  `,
  'macos-arm': () => `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-arm">
      <button class="help-sub-tab active" data-sub="macos-arm-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-arm-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-arm">
      ${_renderSubTabContent('macos-arm', 'macos-arm-pkg')}
    </div>
  `,
  'macos-intel-pkg': `
    <h3>Intel — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'macos-intel-bin': `
    <h3>Intel — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Запустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
  'macos-arm-pkg': `
    <h3>ARM — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'macos-arm-bin': `
    <h3>ARM — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Запустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
};

/**
 * Контент для подвкладок обновления бэкенда (update-backend).
 * @type {Object<string, Function|string>}
 */
const _UPDATE_SUB_TEXTS = {
  'update-windows': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>1. Скачайте новый установщик</h3>
    <ol>
      <li>Перейдите по ссылке <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Скачайте <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Обновите</h3>
    <ol>
      <li>Запустите установщик — он заменит файлы автоматически</li>
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
  'update-linux': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-linux">
      <button class="help-sub-tab active" data-sub="update-linux-deb">Пакет (.deb)</button>
      <button class="help-sub-tab" data-sub="update-linux-rpm">Пакет (.rpm)</button>
      <button class="help-sub-tab" data-sub="update-linux-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-linux">
      ${_renderUpdateSubTabContent('update-linux-deb', tag)}
    </div>
  `,
  'update-macos': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos">
      <button class="help-sub-tab active" data-sub="update-macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="update-macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos">
      ${_renderUpdateSubTabContent('update-macos-intel', tag)}
    </div>
  `,
  'update-source': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Через Git:</strong> <code>git pull</code></li>
      <li><strong>Или ZIP:</strong> скачайте новый архив, распакуйте поверх старой папки</li>
      <li>Остановите старый процесс, перезапустите: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER}
  `,
  'update-linux-deb': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Пакет (.deb)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.deb</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'update-linux-rpm': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Пакет (.rpm)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.rpm</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo rpm -U FlowLink-Proxy-*.rpm</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'update-linux-bin': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте поверх старой папки: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Перезапустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
  'update-macos-intel': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-intel">
      <button class="help-sub-tab active" data-sub="update-macos-intel-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-intel-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-intel">
      ${_renderUpdateSubTabContent('update-macos-intel-pkg', tag)}
    </div>
  `,
  'update-macos-arm': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-arm">
      <button class="help-sub-tab active" data-sub="update-macos-arm-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-arm-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-arm">
      ${_renderUpdateSubTabContent('update-macos-arm-pkg', tag)}
    </div>
  `,
  'update-macos-intel-pkg': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'update-macos-intel-bin': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте поверх старой папки: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Перезапустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
  'update-macos-arm-pkg': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
  'update-macos-arm-bin': (tag) => `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте поверх старой папки: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Перезапустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;
/** @type {string} Тег доступного обновления (например 'v0.3.0') или пустая строка. */
let _updateTag = '';

/** Список вкладок help-модалки (порядок отображения). */
const _TABS = ['backend', 'browser', 'port', 'faq'];

/**
 * Контексты открытия помощи и соответствующие им вкладки.
 * Каждый контекст показывает только релевантные вкладки.
 */
const _CONTEXT_TABS = {
  // Общая помощь (кнопка «Помощь» в popup) — все вкладки.
  general: ['backend', 'browser', 'port', 'faq'],
  // Помощь при невозможности подключения к бэкенду — без вкладки «Браузер».
  'backend-error': ['backend', 'port', 'faq'],
  // Помощь при неуказанном браузере — только содержимое вкладки «Браузер».
  'browser-warning': ['browser'],
  // Помощь при обновлении — своя помощь по обновлению.
  update: ['update-backend', 'update-ext'],
};

/** Текущий контекст открытой помощи. */
let _context = 'general';

/**
 * Открывает модальное окно помощи.
 * @param {string} [tab] — вкладка для открытия (по умолчанию 'backend').
 * @param {boolean} [isUpdate] — режим обновления.
 * @param {string} [updateTag] — тег доступного обновления (например 'v0.3.0').
 * @param {string} [context] — контекст открытия ('general', 'backend-error',
 *   'browser-warning', 'update').
 */
export function openHelpModal(tab, isUpdate, updateTag, context) {
  _isUpdateMode = !!isUpdate;
  _updateTag = updateTag || '';
  _context = context || 'general';
  const title = document.querySelector('#modal-help .modal-title');
  if (!title) {
    console.warn('[FlowLink Proxy] Заголовок модального окна помощи не найден');
    return;
  }
  if (isUpdate || _context === 'update') {
    title.textContent = 'Обновление';
  } else {
    title.textContent = 'Настройка FlowLink Proxy';
  }
  showModal('modal-help');
  switchHelpTab(tab || _defaultTabForContext());
}

/**
 * Возвращает вкладку по умолчанию для текущего контекста.
 * @returns {string} Имя вкладки по умолчанию.
 */
function _defaultTabForContext() {
  const tabs = _CONTEXT_TABS[_context] || _CONTEXT_TABS.general;
  return tabs[0] || 'backend';
}

/**
 * Переключает вкладку помощи.
 * @param {string} tab — имя вкладки ('backend', 'port', 'faq').
 */
export function switchHelpTab(tab) {
  // Если режим обновления — показываем контент обновления
  if (_isUpdateMode || _context === 'update') {
    _showUpdateContent(tab);
    return;
  }

  // Определяем вкладки, доступные в текущем контексте
  const visibleTabs = _CONTEXT_TABS[_context] || _CONTEXT_TABS.general;

  // Панель вкладок скрывается целиком, если контекст показывает
  // только одну вкладку (например, помощь при неуказанном браузере).
  const tabsBar = document.getElementById('modal-tabs');
  if (tabsBar) {
    tabsBar.classList.toggle('hidden', visibleTabs.length <= 1);
  }

  // Показываем/скрываем вкладки в зависимости от контекста
  _TABS.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (!el) {
      console.warn('[FlowLink Proxy] Элемент вкладки не найден:', 'tab-' + t);
      return;
    }
    const visible = visibleTabs.includes(t);
    el.classList.toggle('hidden', !visible);
    el.classList.toggle('active', visible && t === tab);
  });

  // В обычном контексте вкладки обновления всегда скрыты
  _CONTEXT_TABS.update.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.add('hidden');
  });

  // Если вкладка не входит в контекст — используем вкладку по умолчанию
  if (!visibleTabs.includes(tab)) {
    tab = _defaultTabForContext();
  }

  const content = document.getElementById('help-content');
  if (!content) {
    console.warn('[FlowLink Proxy] Элемент help-content не найден');
    return;
  }

  const text = HELP_TEXTS[tab];
  if (!text) {
    console.warn('[FlowLink Proxy] Текст для вкладки помощи не найден:', tab);
    return;
  }

  // Если текст — функция, вызываем её
  try {
    content.innerHTML = typeof text === 'function' ? text() : text;
  } catch (err) {
    console.error('[FlowLink Proxy] Ошибка рендеринга помощи:', err);
    content.innerHTML = '<p>Ошибка при отображении помощи. Попробуйте перезагрузить popup.</p>';
  }

  // Привязываем обработчики подвкладок
  _setupSubTabHandler(tab);
}

/**
 * Настраивает обработчики для подвкладок.
 * @param {string} tab — имя основной вкладки.
 */
function _setupSubTabHandler(tab) {
  const container = document.getElementById('help-sub-tabs-' + tab);
  if (!container) {
    console.warn('[FlowLink Proxy] Не найден контейнер help-sub-tabs-' + tab);
    return;
  }

  container.querySelectorAll('.help-sub-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const sub = btn.dataset.sub;
      if (!sub) return;

      // Переключаем активную подвкладку
      container.querySelectorAll('.help-sub-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Рендерим контент подвкладки
      const contentContainer = document.getElementById('help-sub-content-' + tab);
      if (!contentContainer) {
        console.warn('[FlowLink Proxy] Не найден контейнер help-sub-content-' + tab);
        return;
      }
      try {
        contentContainer.innerHTML = _renderSubTabContent(tab, sub);
      } catch (err) {
        console.error('[FlowLink Proxy] Ошибка рендеринга подвкладки help-sub-content:', err);
        contentContainer.innerHTML = '<p>Ошибка рендеринга. Перезагрузите popup.</p>';
      }

      // Если это backend-linux или backend-macos — настраиваем вложенные подвкладки
      if (sub === 'backend-linux') {
        _setupSubTabHandler('linux');
      } else if (sub === 'backend-macos') {
        _setupSubTabHandler('macos');
      } else if (sub === 'macos-intel') {
        _setupSubTabHandler('macos-intel');
      } else if (sub === 'macos-arm') {
        _setupSubTabHandler('macos-arm');
      }
    });
  });
}

/**
 * Возвращает HTML-контент для указанной подвкладки.
 * @param {string} tab — имя основной вкладки ('backend').
 * @param {string} sub — имя подвкладки.
 * @returns {string} HTML-контент.
 */
function _renderSubTabContent(tab, sub) {
  if (tab === 'backend') {
    const text = _BACKEND_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return (typeof text === 'function' ? text() : text) + _EMAIL_FOOTER;
  }
  // Вложенные подвкладки linux/macos
  if (tab === 'linux') {
    return _LINUX_SUB_TEXTS[sub] || '<p>Раздел в разработке.</p>';
  }
  if (tab === 'macos') {
    const text = _MACOS_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return (typeof text === 'function' ? text() : text) + _EMAIL_FOOTER;
  }
  // Под-подвкладки macOS (macos-intel/macos-arm)
  if (tab === 'macos-intel' || tab === 'macos-arm') {
    const text = _MACOS_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return typeof text === 'function' ? text() : text;
  }
  return '<p>Раздел в разработке.</p>';
}

/**
 * Возвращает HTML-контент для указанной подвкладки обновления.
 * @param {string} sub — имя подвкладки.
 * @param {string} tag — тег доступного обновления.
 * @returns {string} HTML-контент.
 */
function _renderUpdateSubTabContent(sub, tag) {
  const escapedTag = escapeHtml(tag);
  const text = _UPDATE_SUB_TEXTS[sub];
  if (!text) {
    console.warn('[FlowLink Proxy] Не найден контент для подвкладки обновления:', sub);
    return '<p>Раздел в разработке.</p>';
  }
  try {
    return typeof text === 'function' ? text(escapedTag) : text;
  } catch (err) {
    console.error('[FlowLink Proxy] Ошибка рендеринга подвкладки обновления:', err);
    return '<p>Ошибка рендеринга. Перезагрузите popup.</p>';
  }
}

/**
 * Показывает контент обновления.
 * @param {string} tab — имя вкладки ('update-backend', 'update-ext').
 */
function _showUpdateContent(tab) {
  const content = document.getElementById('help-content');
  if (!content) {
    console.warn('[FlowLink Proxy] help-content не найден при отображении обновления');
    return;
  }
  const tag = _updateTag || '';

  // Определяем вкладки обновления, доступные в контексте
  const visibleTabs = _CONTEXT_TABS.update;

  // Панель вкладок показывается (в контексте обновления 2 вкладки)
  const tabsBar = document.getElementById('modal-tabs');
  if (tabsBar) {
    tabsBar.classList.remove('hidden');
  }

  // Показываем/скрываем вкладки обновления
  visibleTabs.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (!el) {
      console.warn('[FlowLink Proxy] Элемент вкладки обновления не найден:', 'tab-' + t);
      return;
    }
    el.classList.toggle('hidden', false);
    el.classList.toggle('active', t === tab);
  });

  // Скрываем обычные вкладки
  _TABS.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.add('hidden');
  });

  // Если вкладка не входит в контекст обновления — используем первую
  if (!visibleTabs.includes(tab)) {
    tab = visibleTabs[0];
  }

  const text = HELP_TEXTS[tab];
  if (!text) {
    console.warn('[FlowLink Proxy] Текст для вкладки обновления не найден:', tab);
    return;
  }
  try {
    content.innerHTML = typeof text === 'function' ? text(tag) : text;
  } catch (err) {
    console.error('[FlowLink Proxy] Ошибка рендеринга обновления:', err);
    content.innerHTML = '<p>Ошибка при отображении обновления. Попробуйте перезагрузить popup.</p>';
  }

  // Привязываем обработчики подвкладок обновления
  _setupUpdateSubTabHandler(tab);
}

/**
 * Настраивает обработчики для подвкладок обновления.
 * @param {string} tab — имя основной вкладки обновления.
 */
function _setupUpdateSubTabHandler(tab) {
  const container = document.getElementById('help-sub-tabs-' + tab);
  if (!container) {
    console.warn('[FlowLink Proxy] Не найден контейнер help-sub-tabs-' + tab);
    return;
  }

  container.querySelectorAll('.help-sub-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const sub = btn.dataset.sub;
      if (!sub) return;

      // Переключаем активную подвкладку
      container.querySelectorAll('.help-sub-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Рендерим контент подвкладки
      const contentContainer = document.getElementById('help-sub-content-' + tab);
      if (!contentContainer) {
        console.warn('[FlowLink Proxy] Не найден контейнер help-sub-content-' + tab);
        return;
      }
      try {
        contentContainer.innerHTML = _renderUpdateSubTabContent(sub, _updateTag || '');
      } catch (err) {
        console.error('[FlowLink Proxy] Ошибка рендеринга обновления подвкладки:', err);
        contentContainer.innerHTML = '<p>Ошибка рендеринга. Перезагрузите popup.</p>';
      }

      // Вложенные подвкладки обновления
      if (sub === 'update-linux') {
        _setupUpdateSubTabHandler('update-linux');
      } else if (sub === 'update-macos') {
        _setupUpdateSubTabHandler('update-macos');
      } else if (sub === 'update-macos-intel') {
        _setupUpdateSubTabHandler('update-macos-intel');
      } else if (sub === 'update-macos-arm') {
        _setupUpdateSubTabHandler('update-macos-arm');
      }
    });
  });
}

// Экспорт только для тестов — в рантайме расширения не используется.
export { HELP_TEXTS, _TABS };
