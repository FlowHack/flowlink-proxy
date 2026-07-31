/**
 * @fileoverview
 * Тексты помощи и переключение вкладок модального окна.
 * Единственная ответственность: help-контент и управление его отображением.
 */

import { GITHUB_RELEASES_URL } from '../shared/constants.js';

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
 *   backend — установка бэкенда (с подвкладками windows/linux/macos/source).
 *   port — настройка порта и диагностика.
 *   ext — установка расширения (с подвкладками store/crx-auto/crx/source).
 *   updateExe/updateSource/updateExt — обновление (заголовок «Обновление»).
 *   autostartHelp — помощь по настройке автозапуска браузера.
 *   faq — ответы на частые вопросы (FAQ).
 */
const HELP_TEXTS = {
  backend: () => `
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
  ext: () => `
    <div class="help-sub-tabs" id="help-sub-tabs-ext">
      <button class="help-sub-tab active" data-sub="ext-store">Chrome Web Store</button>
      <button class="help-sub-tab" data-sub="ext-crx-auto">CRX (авто)</button>
      <button class="help-sub-tab" data-sub="ext-crx">CRX (вручную)</button>
      <button class="help-sub-tab" data-sub="ext-source">Из исходников</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-ext">
      ${_renderSubTabContent('ext', 'ext-store')}
    </div>
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
    <h4>Альтернативный способ — через меню трея</h4>
    <p>Тот же тумблер «Автозапуск браузера» доступен в меню системного трея бэкенда. Оба способа синхронизированы.</p>
    <h4>Как это работает</h4>
    <p>При запуске бэкенд проверяет настройки автозапуска. Если автозапуск включён и браузер выбран, бэкенд запускает браузер с необходимыми параметрами прокси. Вам не нужно запускать браузер вручную или использовать дополнительные скрипты.</p>
    <div class="note">
      <strong>Примечание:</strong> При автозапуске браузера через бэкенд используется отдельный чистый профиль (<code>--user-data-dir</code>). Данные основного профиля браузера (закладки, пароли, расширения) в нём недоступны — это политика Chromium. Основной профиль не затрагивается.
    </div>
    <h4>Если браузер не запускается</h4>
    <ul>
      <li>Убедитесь, что в настройках расширения выбран браузер и указан корректный путь.</li>
      <li>Проверьте, что бэкенд запущен (зелёный индикатор в popup).</li>
      <li>Попробуйте перезапустить бэкенд.</li>
    </ul>
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

    <h3>Запуск браузера с автоподкидыванием расширения</h3>
    <p>В меню трея есть пункт «Запуск с расширением». При запуске браузера через пункт «Запустить браузер» расширение подключается автоматически (CRX-автоподкидывание).</p>
    <p>Используйте этот вариант, если расширение не подключается вручную или нужно быстро запустить браузер с рабочим прокси.</p>
    <div class="note">
      <strong>Примечание:</strong> При запуске браузера через бэкенд используется отдельный чистый профиль (<code>--user-data-dir</code>). Данные основного профиля браузера (закладки, пароли, расширения) в нём недоступны — это политика Chromium. Основной профиль не затрагивается.
    </div>
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
    <p>После установки бэкенда перейдите на вкладку <strong>«Расширение»</strong> в этом окне помощи, чтобы установить расширение в браузер.</p>
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
 * Контент для подвкладок расширения (ext).
 * @type {Object<string, string>}
 */
const _EXT_SUB_CONTENT = {
  'ext-store': `
    <h3>Chrome Web Store</h3>
    <p>Расширение FlowLink Proxy будет опубликовано в Chrome Web Store после завершения проверки. Следите за обновлениями в <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a>.</p>
    <p>Пока вы можете установить расширение одним из способов ниже.</p>
  `,
  'ext-crx-auto': `
    <h3>Автоустановка через бэкенд</h3>
    <ol>
      <li>Скачайте <code>flowlink-proxy.crx</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Положите файл рядом с бинарником бэкенда (или в папку с программой)</li>
      <li>Запустите бэкенд — он автоматически найдёт CRX и сможет запустить браузер с расширением</li>
      <li>В меню системного трея включите «Запуск с расширением» и нажмите «Запустить браузер»</li>
    </ol>
    <div class="note">
      <strong>Примечание:</strong> CRX-расширение не требует режима разработчика и не показывает предупреждений при запуске браузера. При запуске браузера через бэкенд используется отдельный чистый профиль (<code>--user-data-dir</code>): ваши закладки, пароли и расширения из основного профиля в нём недоступны — это политика Chromium. Основной профиль не изменяется.
    </div>
  `,
  'ext-crx': `
    <h3>Установка CRX вручную</h3>
    <ol>
      <li>Скачайте <code>flowlink-proxy.crx</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>)</li>
      <li>Перетащите CRX-файл на страницу расширений</li>
      <li>Подтвердите установку</li>
    </ol>
    <div class="note">
      <strong>Примечание:</strong> CRX-расширение не требует режима разработчика.
    </div>
  `,
  'ext-source': `
    <h3>Установка из исходного кода</h3>
    <ol>
      <li>Клонируйте репозиторий: <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li>Откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>)</li>
      <li>Включите «Режим разработчика»</li>
      <li>Нажмите «Загрузить распакованное расширение»</li>
      <li>Выберите папку <code>extension/</code> из клонированного репозитория</li>
    </ol>
    <div class="note">
      <strong>Примечание:</strong> Этот способ требует включённого режима разработчика. При каждом запуске браузера расширение нужно загружать заново (если не используется CRX).
    </div>
  `,
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;
/** @type {boolean} True, когда модалка открыта в режиме «Автозапуск — помощь». */
let _isAutostartHelpMode = false;
/** @type {string} Тег доступного обновления (например 'v0.3.0') или пустая строка. */
let _updateTag = '';

/** Список вкладок help-модалки (порядок отображения). */
const _TABS = ['backend', 'port', 'ext', 'faq'];

/**
 * Открывает модальное окно помощи.
 * @param {string} [tab] — вкладка для открытия (по умолчанию 'backend').
 * @param {boolean} [isUpdate] — режим обновления.
 * @param {boolean} [isAutostartHelp] — режим помощи по автозапуску.
 * @param {string} [updateTag] — тег доступного обновления (например 'v0.3.0').
 */
export function openHelpModal(tab, isUpdate, isAutostartHelp, updateTag) {
  _isUpdateMode = !!isUpdate;
  _isAutostartHelpMode = !!isAutostartHelp;
  _updateTag = updateTag || '';
  const title = document.querySelector('#modal-help .modal-title');
  if (!title) return;
  if (isAutostartHelp) {
    title.textContent = 'Автозапуск браузера';
  } else if (isUpdate) {
    title.textContent = 'Обновление';
  } else {
    title.textContent = 'Настройка FlowLink Proxy';
  }
  showModal('modal-help');
  switchHelpTab(tab || 'backend');
}

/**
 * Переключает вкладку помощи.
 * @param {string} tab — имя вкладки ('backend', 'port', 'ext', 'faq').
 */
export function switchHelpTab(tab) {
  // Если открыт режим autostartHelp — показываем контент автозапуска
  if (_isAutostartHelpMode) {
    _showAutostartHelpContent();
    return;
  }

  // Если режим обновления — показываем контент обновления
  if (_isUpdateMode) {
    _showUpdateContent(tab);
    return;
  }

  // Переключаем активную вкладку
  _TABS.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.classList.toggle('active', t === tab);
  });

  const content = document.getElementById('help-content');
  if (!content) return;

  const text = HELP_TEXTS[tab];
  if (!text) return;

  // Если текст — функция, вызываем её
  content.innerHTML = typeof text === 'function' ? text() : text;

  // Привязываем обработчики подвкладок
  _setupSubTabHandler(tab);
}

/**
 * Настраивает обработчики для подвкладок.
 * @param {string} tab — имя основной вкладки.
 */
function _setupSubTabHandler(tab) {
  const container = document.getElementById('help-sub-tabs-' + tab);
  if (!container) return;

  container.querySelectorAll('.help-sub-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const sub = btn.dataset.sub;
      if (!sub) return;

      // Переключаем активную подвкладку
      container.querySelectorAll('.help-sub-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      // Рендерим контент подвкладки
      const contentContainer = document.getElementById('help-sub-content-' + tab);
      if (!contentContainer) return;
      contentContainer.innerHTML = _renderSubTabContent(tab, sub);

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
 * @param {string} tab — имя основной вкладки ('backend', 'ext').
 * @param {string} sub — имя подвкладки.
 * @returns {string} HTML-контент.
 */
function _renderSubTabContent(tab, sub) {
  if (tab === 'backend') {
    const text = _BACKEND_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return (typeof text === 'function' ? text() : text) + _EMAIL_FOOTER;
  }
  if (tab === 'ext') {
    const text = _EXT_SUB_CONTENT[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return text + _EMAIL_FOOTER;
  }
  // Вложенные подвкладки linux/macos
  if (tab === 'linux') {
    return _LINUX_SUB_TEXTS[sub] || '<p>Раздел в разработке.</p>';
  }
  if (tab === 'macos') {
    const text = _MACOS_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return typeof text === 'function' ? text() : text;
  }
  // Под-подвкладки macOS (macos-intel/macos-arm)
  if (tab === 'macos-intel' || tab === 'macos-arm') {
    const text = _MACOS_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return text;
  }
  return '<p>Раздел в разработке.</p>';
}

/**
 * Показывает контент помощи по автозапуску браузера.
 */
function _showAutostartHelpContent() {
  const content = document.getElementById('help-content');
  if (!content) return;
  content.innerHTML = HELP_TEXTS.autostartHelp;
}

/**
 * Показывает контент обновления.
 * @param {string} tab — не используется, оставлено для совместимости.
 */
function _showUpdateContent(tab) {
  const content = document.getElementById('help-content');
  if (!content) return;
  // Показываем универсальный контент обновления с версией (если известна)
  const tag = _updateTag || '';
  content.innerHTML = HELP_TEXTS.updateExe(tag) + HELP_TEXTS.updateSource(tag) + HELP_TEXTS.updateExt(tag);
}

// Экспорт только для тестов — в рантайме расширения не используется.
export { HELP_TEXTS, _TABS };
