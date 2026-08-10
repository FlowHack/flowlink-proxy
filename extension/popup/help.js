/**
 * @fileoverview
 * Тексты помощи и переключение вкладок модального окна.
 * Единственная ответственность: help-контент и управление его отображением.
 */

import { GITHUB_RELEASES_URL } from '../shared/constants.js';

import { showModal } from './modal.js';
import { escapeHtml } from '../shared/dom.js';
import { getCurrentLang } from '../shared/i18n.js';

/** Email поддержки — сноска внизу каждого раздела помощи. */
const _EMAIL = 'flowlink.proxy@atomicmail.io';
const _EMAIL_FOOTER = (lang = 'ru') => {
  const texts = {
    ru: 'Не удалось решить проблему? Напишите на {email} — поможем.',
    en: 'Could not solve the problem? Write to {email} — we will help.',
    sr: 'Niste uspeli da rešite problem? Pišite na {email} — pomoći ćemo.',
  };
  const titles = {
    ru: 'Нажмите, чтобы скопировать',
    en: 'Click to copy',
    sr: 'Kliknite da kopirate',
  };
  const text = texts[lang] || texts.ru;
  const title = titles[lang] || titles.ru;
  return `<p class="help-email-footer">${text.replace('{email}', `<span class="help-email-copy" data-email="${_EMAIL}" title="${title}">${_EMAIL}</span>`)}</p>`;
};

/** Блок с портами по умолчанию (используется в нескольких разделах). */
const _PORTS_DEFAULT_TABLE = (lang = 'ru') => {
  const titles = {
    ru: 'Порты по умолчанию',
    en: 'Default ports',
    sr: 'Podrazumevani portovi',
  };
  const proxyCell = {
    ru: 'Прокси-сервер (для браузера)',
    en: 'Proxy server (for browser)',
    sr: 'Proxy server (za pregledač)',
  };
  const apiCell = {
    ru: 'API-сервер (для расширения)',
    en: 'API server (for extension)',
    sr: 'API server (za ekstenziju)',
  };
  return `
    <h3>${titles[lang] || titles.ru}</h3>
    <table class="help-ports-table">
      <tr class="help-ports-row">
        <td class="help-ports-cell"><code>8080</code></td>
        <td class="help-ports-cell">${proxyCell[lang] || proxyCell.ru}</td>
      </tr>
      <tr>
        <td class="help-ports-cell"><code>8081</code></td>
        <td class="help-ports-cell">${apiCell[lang] || apiCell.ru}</td>
      </tr>
    </table>`;
};

/** Блок troubleshooting по портам (используется в windows/linux/macos/source). */
const _PORTS_TROUBLESHOOT = (lang = 'ru') => {
  const titles = {
    ru: 'Проблемы с портами',
    en: 'Port issues',
    sr: 'Problemi sa portovima',
  };
  const ifChanged = {
    ru: 'Если вы меняли порты через <code>--proxy-port</code> или <code>--api-port</code>:',
    en: 'If you changed ports via <code>--proxy-port</code> or <code>--api-port</code>:',
    sr: 'Ako ste menjali porte preko <code>--proxy-port</code> ili <code>--api-port</code>:',
  };
  const extNotFind = {
    ru: 'Расширение не находит бэкенд.',
    en: 'Extension cannot find the backend.',
    sr: 'Ekstenzija ne može da pronađe backend.',
  };
  const autoSearch = {
    ru: 'Автопоиск порта работает в диапазоне 8080–8090. Если API-порт за его пределами:',
    en: 'Auto port search works in the range 8080–8090. If the API port is outside this range:',
    sr: 'Automatsko pretraživanje porta radi u opsegu 8080–8090. Ako je API port izvan ovog opsega:',
  };
  const browserNotConnect = {
    ru: 'Браузер не может подключиться к прокси.',
    en: 'Browser cannot connect to the proxy.',
    sr: 'Pregledač ne može da se poveže sa proxyjem.',
  };
  const ensureMatch = {
    ru: 'Убедитесь, что <code>--proxy-port</code> на бэкенде совпадает с настройками прокси в браузере.',
    en: 'Ensure that <code>--proxy-port</code> on the backend matches the proxy settings in the browser.',
    sr: 'Uverite se da <code>--proxy-port</code> na backend-u odgovara podešavanjima proxyja u pregledču.',
  };
  const portBusy = {
    ru: 'Порт уже занят.',
    en: 'Port is already in use.',
    sr: 'Port je već zauzet.',
  };
  const checkPort = {
    ru: 'Другой процесс использует тот же порт. Проверьте:',
    en: 'Another process is using the same port. Check:',
    sr: 'Drugi proces koristi isti port. Proverite:',
  };
  const checkLogs = {
    ru: 'Посмотрите порты в логах.',
    en: 'Check the ports in the logs.',
    sr: 'Proverite porte u logovima.',
  };
  const runDebug = {
    ru: 'Запустите бэкенд с <code>--debug</code> — в логах будет указан фактический порт:',
    en: 'Run the backend with <code>--debug</code> — the actual port will be shown in the logs:',
    sr: 'Pokrenite backend sa <code>--debug</code> — stvarni port će biti prikazan u logovima:',
  };

  return `
    <h3>${titles[lang] || titles.ru}</h3>
    <p>${ifChanged[lang] || ifChanged.ru}</p>
    <ol>
      <li><strong>${extNotFind[lang] || extNotFind.ru}</strong>
        ${autoSearch[lang] || autoSearch.ru}
        <ol type="a">
          <li>Нажмите ⚙ (шестерёнка внизу popup)</li>
          <li>Введите порт API (должен совпадать с <code>--api-port</code> на бэкенде)</li>
          <li>Нажмите «Сохранить»</li>
        </ol>
      </li>
      <li><strong>${browserNotConnect[lang] || browserNotConnect.ru}</strong>
        ${ensureMatch[lang] || ensureMatch.ru}
        По умолчанию: <code>8080</code>.
      </li>
      <li><strong>${portBusy[lang] || portBusy.ru}</strong>
        ${checkPort[lang] || checkPort.ru}
        <br><code>lsof -i :8080</code> (Linux/macOS) или
        <code>netstat -ano | findstr :8080</code> (Windows)
      </li>
      <li><strong>${checkLogs[lang] || checkLogs.ru}</strong>
        ${runDebug[lang] || runDebug.ru}
        <br><code>python -m server --debug --api-port 9091</code>
      </li>
    </ol>`;
};

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
  backend: (lang = 'ru') => {
    const texts = {
      ru: `
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
      en: `
    <p class="help-intro">The extension requires the FlowLink Proxy application. Below are installation instructions for different systems.</p>
    <div class="help-sub-tabs" id="help-sub-tabs-backend">
      <button class="help-sub-tab active" data-sub="backend-windows">Windows</button>
      <button class="help-sub-tab" data-sub="backend-linux">Linux</button>
      <button class="help-sub-tab" data-sub="backend-macos">macOS</button>
      <button class="help-sub-tab" data-sub="backend-source">Source code</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-backend">
      ${_renderSubTabContent('backend', 'backend-windows')}
    </div>
  `,
      sr: `
    <p class="help-intro">Ekstenzija zahteva FlowLink Proxy aplikaciju. Ispod su uputstva za instalaciju na različitim sistemima.</p>
    <div class="help-sub-tabs" id="help-sub-tabs-backend">
      <button class="help-sub-tab active" data-sub="backend-windows">Windows</button>
      <button class="help-sub-tab" data-sub="backend-linux">Linux</button>
      <button class="help-sub-tab" data-sub="backend-macos">macOS</button>
      <button class="help-sub-tab" data-sub="backend-source">Izvorni kod</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-backend">
      ${_renderSubTabContent('backend', 'backend-windows')}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  browser: (lang = 'ru') => {
    const texts = {
      ru: `
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
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    <h3>Selecting a browser for autostart</h3>
    <p>Browser autostart is enabled, but the browser path is not specified. To make autostart work, select a browser in the backend menu.</p>
    <div class="help-section">
      <h4>How to select a browser</h4>
      <ol>
        <li>Open the FlowLink Proxy menu in the system tray (icon in the bottom right corner of the screen).</li>
        <li>Select the <strong>"Browser"</strong> item (or "Select browser").</li>
        <li>In the list that appears, specify your browser (Chrome, Firefox, Edge, etc.).</li>
        <li>If your browser is not in the list — click "Specify manually" and select the browser executable file.</li>
      </ol>
      <p>After selecting the browser, autostart will work: when the backend starts, the browser will open automatically.</p>
    </div>
    <p>If you do not want the browser to start automatically, disable autostart in the backend menu (item "Browser autostart").</p>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    <h3>Izbor pregledača za automatsko pokretanje</h3>
    <p>Automatsko pokretanje pregledača je omogućeno, ali putanja do pregledača nije navedena. Da bi automatsko pokretanje radilo, izaberite pregledač u meniju backend-a.</p>
    <div class="help-section">
      <h4>Kako izabrati pregledač</h4>
      <ol>
        <li>Otvorite FlowLink Proxy meni u sistemskoj traci (ikonica u donjem desnom uglu ekrana).</li>
        <li>Izaberite stavku <strong>"Pregledač"</strong> (ili "Izaberi pregledač").</li>
        <li>U listi koja se pojavi, navedite svoj pregledač (Chrome, Firefox, Edge, itd.).</li>
        <li>Ako vaš pregledač nije u listi — kliknite "Navedi ručno" i izaberite izvršnu datoteku pregledača.</li>
      </ol>
      <p>Nakon izbora pregledača, automatsko pokretanje će raditi: kada se backend pokrene, pregledač će se automatski otvoriti.</p>
    </div>
    <p>Ako ne želite da se pregledač automatski pokreće, isključite automatsko pokretanje u meniju backend-a (stavka "Automatsko pokretanje pregledača").</p>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  port: (lang = 'ru') => {
    const texts = {
      ru: `
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

    ${_PORTS_DEFAULT_TABLE(lang)}

    <p>Если проблема не решена — обратитесь в поддержку (ссылка ниже).</p>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    <h3>Port setup</h3>

    <div class="help-section" id="help-port">
      <h4>🔌 Auto detection</h4>
      <p>The backend listens on port <strong>8081</strong> by default. The extension automatically scans ports from 8080 to 8090 to find the backend.</p>
      <p>When you click "Retry", the extension will check the current port and then scan the range 8080–8090. If the backend is found on another port, the extension will connect to it automatically.</p>
    </div>

    <div class="help-section" id="help-port-manual">
      <h4>⚙ Manual port setup</h4>
      <ol>
        <li>Click the ⚙ button at the bottom of the popup.</li>
        <li>In the "API port" field, specify the port number on which the backend is running.</li>
        <li>Click "Save".</li>
        <li>The extension will reconnect to the new port.</li>
      </ol>
      <p><strong>Important:</strong> If you change the port in the extension, make sure the backend is running on the same port. The backend port can be changed via the command line argument: <code>--api-port 9090</code>.</p>
    </div>

    ${_PORTS_DEFAULT_TABLE(lang)}

    <p>If the problem is not resolved — contact support (link below).</p>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    <h3>Podešavanje porta</h3>

    <div class="help-section" id="help-port">
      <h4>🔌 Automatsko otkrivanje</h4>
      <p>Backend podrazumevano sluša na portu <strong>8081</strong>. Ekstenzija automatski skenira porte od 8080 do 8090 da pronađe backend.</p>
      <p>Kada kliknete "Pokušaj ponovo", ekstenzija će proveriti trenutni port i zatim skenirati opseg 8080–8090. Ako se backend pronađe na drugom portu, ekstenzija će se automatski povezati sa njim.</p>
    </div>

    <div class="help-section" id="help-port-manual">
      <h4>⚙ Ručno podešavanje porta</h4>
      <ol>
        <li>Kliknite na dugme ⚙ na dnu popup-a.</li>
        <li>U polju "API port" navedite broj porta na kojem je backend pokrenut.</li>
        <li>Kliknite "Sačuvaj".</li>
        <li>Ekstenzija će se ponovo povezati sa novim portom.</li>
      </ol>
      <p><strong>Važno:</strong> Ako menjate port u ekstenziji, uverite se da je backend pokrenut na istom portu. Port backend-a može se promeniti preko argumenta komandne linije: <code>--api-port 9090</code>.</p>
    </div>

    ${_PORTS_DEFAULT_TABLE(lang)}

    <p>Ako problem nije rešen — kontaktirajte podršku (link ispod).</p>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  updateExe: (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
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
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Installer</h3>
    <ol>
      <li>Download the new installer from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Run it — the installer will replace files automatically</li>
      <li>The backend will be restarted</li>
    </ol>
    <h3>Standalone binary</h3>
    <ol>
      <li>Download the new archive from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Stop the old process (system tray → "Exit")</li>
      <li>Replace the files and run the new one</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Instalater</h3>
    <ol>
      <li>Preuzmite novi instalater sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Pokrenite ga — instalater će automatski zameniti datoteke</li>
      <li>Backend će biti ponovo pokrenut</li>
    </ol>
    <h3>Standalone binarni fajl</h3>
    <ol>
      <li>Preuzmite novu arhivu sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Zaustavite stari proces (sistemska traka → "Izlaz")</li>
      <li>Zamenite datoteke i pokrenite novi</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  updateSource: (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Через Git:</strong> <code>git pull</code></li>
      <li><strong>Или ZIP:</strong> скачайте новый архив, распакуйте поверх старой папки</li>
      <li>Остановите старый процесс, перезапустите: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Via Git:</strong> <code>git pull</code></li>
      <li><strong>Or ZIP:</strong> download the new archive, unpack it over the old folder</li>
      <li>Stop the old process, restart: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Preko Git-a:</strong> <code>git pull</code></li>
      <li><strong>Ili ZIP:</strong> preuzmite novu arhivu, raspakujte je preko stare fascikle</li>
      <li>Zaustavite stari proces, ponovo pokrenite: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  updateExt: (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Из магазина:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked:</strong> откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>), нажмите «Обновить» (круглая стрелка)</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>From store:</strong> the extension will update automatically</li>
      <li><strong>Unpacked:</strong> open <code>chrome://extensions</code> (or <code>browser://extensions</code>), click "Update" (circular arrow)</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Iz prodavnice:</strong> ekstenzija će se ažurirati automatski</li>
      <li><strong>Unpacked:</strong> otvorite <code>chrome://extensions</code> (ili <code>browser://extensions</code>), kliknite "Ažuriraj" (kružna strelica)</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-backend': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
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
      en: `
    <div class="help-sub-tabs" id="help-sub-tabs-update-backend">
      <button class="help-sub-tab active" data-sub="update-windows">Windows</button>
      <button class="help-sub-tab" data-sub="update-linux">Linux</button>
      <button class="help-sub-tab" data-sub="update-macos">macOS</button>
      <button class="help-sub-tab" data-sub="update-source">Source code</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-backend">
      ${_renderUpdateSubTabContent('update-windows', tag)}
    </div>
  `,
      sr: `
    <div class="help-sub-tabs" id="help-sub-tabs-update-backend">
      <button class="help-sub-tab active" data-sub="update-windows">Windows</button>
      <button class="help-sub-tab" data-sub="update-linux">Linux</button>
      <button class="help-sub-tab" data-sub="update-macos">macOS</button>
      <button class="help-sub-tab" data-sub="update-source">Izvorni kod</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-backend">
      ${_renderUpdateSubTabContent('update-windows', tag)}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-ext': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Обновление расширения</h3>
    <ol>
      <li><strong>Из магазина:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked:</strong> откройте <code>chrome://extensions</code> (или <code>browser://extensions</code>), нажмите «Обновить» (круглая стрелка)</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Extension update</h3>
    <ol>
      <li><strong>From store:</strong> the extension will update automatically</li>
      <li><strong>Unpacked:</strong> open <code>chrome://extensions</code> (or <code>browser://extensions</code>), click "Update" (circular arrow)</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Ažuriranje ekstenzije</h3>
    <ol>
      <li><strong>Iz prodavnice:</strong> ekstenzija će se ažurirati automatski</li>
      <li><strong>Unpacked:</strong> otvorite <code>chrome://extensions</code> (ili <code>browser://extensions</code>), kliknite "Ažuriraj" (kružna strelica)</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  license: (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Лицензия</h3>
    <p>FlowLink Proxy распространяется под лицензией <strong>GNU AGPL v3</strong>.</p>
    <p>При использовании вы соглашаетесь с условиями
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">EULA.rtf</a>,
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">LICENSE.txt</a> и
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/PRIVACY_POLICY.md" target="_blank" rel="noopener">Политикой конфиденциальности</a>.
    </p>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    <h3>License</h3>
    <p>FlowLink Proxy is distributed under the <strong>GNU AGPL v3</strong> license.</p>
    <p>By using it you agree to the terms of
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">EULA.rtf</a>,
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">LICENSE.txt</a> and
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/PRIVACY_POLICY.md" target="_blank" rel="noopener">Privacy Policy</a>.
    </p>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    <h3>Licenca</h3>
    <p>FlowLink Proxy se distribuira pod <strong>GNU AGPL v3</strong> licencom.</p>
    <p>Korišćenjem prihvatate uslove
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">EULA.rtf</a>,
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">LICENSE.txt</a> i
      <a href="https://github.com/FlowHack/flowlink-proxy/blob/master/PRIVACY_POLICY.md" target="_blank" rel="noopener">Politiku privatnosti</a>.
    </p>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  faq: (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Отказоустойчивость меню бэкенда</h3>
    <p>Если меню в системном трее не может быть создано (например, произошла ошибка рендера), бэкенд не падает — ошибка записывается в лог.</p>
    <p>Для работы трея и диалогов бэкенда обязателен компонент <code>tkinter</code>. Если он не установлен, трей не запускается, а диалоги (выбор браузера, предупреждения) не отображаются.</p>
    <h4>Что делать</h4>
    <ol>
      <li>Проверьте, что установлены все зависимости, включая <code>tkinter</code>.</li>
      <li>Посмотрите лог — там указана причина ошибки.</li>
    </ol>

    <h3>Принудительное завершение бэкенда</h3>
    <p>Если бэкенд завис или работает постоянно, его можно завершить корректно:</p>
    <ol>
      <li><strong>Через меню трея:</strong> пункт «Выход».</li>
      <li><strong>Если меню недоступно:</strong> через диспетчер задач (Windows) или <code>kill</code> процесса (Linux/macOS).</li>
    </ol>
    <p>Это может понадобиться при обновлении, при сбоях или при смене конфигурации.</p>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    <h3>Backend menu fault tolerance</h3>
    <p>If the system tray menu cannot be created (for example, a rendering error occurred), the backend does not crash — the error is written to the log.</p>
    <p>The <code>tkinter</code> component is required for the tray and backend dialogs. If it is not installed, the tray does not start and dialogs (browser selection, warnings) are not displayed.</p>
    <h4>What to do</h4>
    <ol>
      <li>Check that all dependencies are installed, including <code>tkinter</code>.</li>
      <li>Look at the log — it indicates the cause of the error.</li>
    </ol>

    <h3>Forced backend termination</h3>
    <p>If the backend is frozen or runs constantly, it can be terminated gracefully:</p>
    <ol>
      <li><strong>Via tray menu:</strong> "Exit" item.</li>
      <li><strong>If the menu is unavailable:</strong> via Task Manager (Windows) or <code>kill</code> process (Linux/macOS).</li>
    </ol>
    <p>This may be needed during updates, failures, or configuration changes.</p>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    <h3>Otpornost menija backend-a na greške</h3>
    <p>Ako se meni u sistemskoj traci ne može kreirati (na primer, došlo je do greške pri renderovanju), backend ne pada — greška se upisuje u log.</p>
    <p>Za rad trake i dijaloga backend-a obavezna je komponenta <code>tkinter</code>. Ako nije instalirana, traka se ne pokreće, a dijalozi (izbor pregledača, upozorenja) se ne prikazuju.</p>
    <h4>Šta uraditi</h4>
    <ol>
      <li>Proverite da su instalirane sve zavisnosti, uključujući <code>tkinter</code>.</li>
      <li>Pogledajte log — tamo je naveden uzrok greške.</li>
    </ol>

    <h3>Prinudno zaustavljanje backend-a</h3>
    <p>Ako je backend zamrznut ili radi stalno, može se korektno zaustaviti:</p>
    <ol>
      <li><strong>Preko menija u traci:</strong> stavka "Izlaz".</li>
      <li><strong>Ako meni nije dostupan:</strong> preko Task Manager-a (Windows) ili <code>kill</code> procesa (Linux/macOS).</li>
    </ol>
    <p>Ovo može biti potrebno pri ažuriranju, kvarovima ili promeni konfiguracije.</p>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  license: (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Лицензия</h3>
    <p>FlowLink Proxy распространяется под лицензией <strong>GNU AGPL v3</strong>.</p>
    <p>Используя программу, вы соглашаетесь с условиями:</p>
    <ul>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">Лицензионное соглашение (EULA)</a></li>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">Полный текст AGPL-3.0 (LICENSE.txt)</a></li>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/PRIVACY_POLICY.md" target="_blank" rel="noopener">Политика конфиденциальности</a></li>
    </ul>
    <h4>Кратко об AGPL-3.0</h4>
    <ul>
      <li>Вы можете использовать, изучать, изменять и распространять программу</li>
      <li>При распространении (в том числе через сеть) необходимо предоставить исходный код</li>
      <li>Производные работы должны лицензироваться под AGPL-3.0</li>
      <li>Программа предоставляется «как есть», без каких-либо гарантий</li>
      <li>Автор не несёт ответственности за любые убытки от использования программы</li>
    </ul>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    <h3>License</h3>
    <p>FlowLink Proxy is distributed under the <strong>GNU AGPL v3</strong> license.</p>
    <p>By using the program, you agree to the terms of:</p>
    <ul>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">License Agreement (EULA)</a></li>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">Full AGPL-3.0 text (LICENSE.txt)</a></li>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/PRIVACY_POLICY.md" target="_blank" rel="noopener">Privacy Policy</a></li>
    </ul>
    <h4>AGPL-3.0 Summary</h4>
    <ul>
      <li>You may use, study, modify, and distribute the program</li>
      <li>When distributing (including over a network), you must provide the source code</li>
      <li>Derivative works must be licensed under AGPL-3.0</li>
      <li>The program is provided "as is", without any warranty</li>
      <li>The author is not liable for any damages arising from use</li>
    </ul>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    <h3>Licenca</h3>
    <p>FlowLink Proxy se distribuira pod <strong>GNU AGPL v3</strong> licencom.</p>
    <p>Korišćenjem programa, slažete se sa uslovima:</p>
    <ul>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/EULA.rtf" target="_blank" rel="noopener">Licencni ugovor (EULA)</a></li>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/LICENSE.txt" target="_blank" rel="noopener">Puni tekst AGPL-3.0 (LICENSE.txt)</a></li>
      <li><a href="https://github.com/FlowHack/flowlink-proxy/blob/master/PRIVACY_POLICY.md" target="_blank" rel="noopener">Politika privatnosti</a></li>
    </ul>
    <h4>Kratko o AGPL-3.0</h4>
    <ul>
      <li>Možete koristiti, proučavati, menjati i distribuirati program</li>
      <li>Pri distribuciji (uključujući preko mreže) morate obezbediti izvorni kod</li>
      <li>Izvodi moraju biti licencirani pod AGPL-3.0</li>
      <li>Program se pruža "kao što jeste", bez ikakvih garancija</li>
      <li>Autor ne snosi odgovornost za bilo kakvu štetu od korišćenja</li>
    </ul>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
};

/**
 * Контент для подвкладок бэкенда (backend).
 * @type {Object<string, Object<string, string>>}
 */
const _BACKEND_SUB_TEXTS = {
  'backend-windows': (lang = 'ru') => {
    const texts = {
      ru: `
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
          <li>Программу в <code>C:\Program Files\FlowHack\FlowLink Proxy\</code></li>
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
      en: `
    <h3>1. Download the installer</h3>
    <ol>
      <li>Go to <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Download <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Install</h3>
    <ol>
      <li>Run the installer</li>
      <li>The installer will create:
        <ul>
          <li>The program in <code>C:\Program Files\FlowHack\FlowLink Proxy\</code></li>
          <li>A shortcut in the Start menu and on the desktop</li>
          <li>Backend autostart on Windows login</li>
          <li>A shortcut to launch the backend</li>
        </ul>
      </li>
    </ol>
    <h3>3. Run</h3>
    <ol>
      <li>Click "FlowLink Proxy" in the Start menu or on the desktop</li>
      <li>The backend will start automatically</li>
    </ol>
  `,
      sr: `
    <h3>1. Preuzmite instalater</h3>
    <ol>
      <li>Idite na <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Preuzmite <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Instalirajte</h3>
    <ol>
      <li>Pokrenite instalater</li>
      <li>Instalater će kreirati:
        <ul>
          <li>Program u <code>C:\Program Files\FlowHack\FlowLink Proxy\</code></li>
          <li>Prečicu u Start meniju i na radnoj površini</li>
          <li>Automatsko pokretanje backend-a pri prijavi u Windows</li>
          <li>Prečicu za pokretanje backend-a</li>
        </ul>
      </li>
    </ol>
    <h3>3. Pokrenite</h3>
    <ol>
      <li>Kliknite "FlowLink Proxy" u Start meniju ili na radnoj površini</li>
      <li>Backend će se automatski pokrenuti</li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'backend-linux': (lang = 'ru') => {
    const texts = {
      ru: `
    <div class="help-sub-tabs" id="help-sub-tabs-linux">
      <button class="help-sub-tab active" data-sub="linux-deb">Пакет (.deb)</button>
      <button class="help-sub-tab" data-sub="linux-rpm">Пакет (.rpm)</button>
      <button class="help-sub-tab" data-sub="linux-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-linux">
      ${_renderSubTabContent('linux', 'linux-deb')}
    </div>
  `,
      en: `
    <div class="help-sub-tabs" id="help-sub-tabs-linux">
      <button class="help-sub-tab active" data-sub="linux-deb">Package (.deb)</button>
      <button class="help-sub-tab" data-sub="linux-rpm">Package (.rpm)</button>
      <button class="help-sub-tab" data-sub="linux-bin">Binary (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-linux">
      ${_renderSubTabContent('linux', 'linux-deb')}
    </div>
  `,
      sr: `
    <div class="help-sub-tabs" id="help-sub-tabs-linux">
      <button class="help-sub-tab active" data-sub="linux-deb">Paket (.deb)</button>
      <button class="help-sub-tab" data-sub="linux-rpm">Paket (.rpm)</button>
      <button class="help-sub-tab" data-sub="linux-bin">Binarni fajl (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-linux">
      ${_renderSubTabContent('linux', 'linux-deb')}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'backend-macos': (lang = 'ru') => {
    const texts = {
      ru: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos">
      <button class="help-sub-tab active" data-sub="macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos">
      ${_renderSubTabContent('macos', 'macos-intel')}
    </div>
  `,
      en: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos">
      <button class="help-sub-tab active" data-sub="macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos">
      ${_renderSubTabContent('macos', 'macos-intel')}
    </div>
  `,
      sr: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos">
      <button class="help-sub-tab active" data-sub="macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos">
      ${_renderSubTabContent('macos', 'macos-intel')}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'backend-source': (lang = 'ru') => {
    const texts = {
      ru: `
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
    ${_PORTS_DEFAULT_TABLE(lang)}
    ${_PORTS_TROUBLESHOOT(lang)}
  `,
      en: `
    <h3>1. Install Python 3.10+</h3>
    <ol>
      <li>Download Python from the <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">official website</a></li>
      <li>During installation, be sure to check "Add Python to PATH"</li>
      <li>Verify: <code>python --version</code></li>
    </ol>
    <h3>2. Get the source code</h3>
    <ol>
      <li><strong>Via Git:</strong> <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li><strong>Or ZIP:</strong> download from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
    </ol>
    <h3>3. Run</h3>
    <ol>
      <li><code>cd flowlink-proxy</code></li>
      <li>Create a virtual environment: <code>python -m venv venv</code></li>
      <li>Activate: <code>source venv/bin/activate</code> (Linux/macOS) or <code>venv\Scripts\activate</code> (Windows)</li>
      <li>Install dependencies: <code>pip install -r requirements.txt</code></li>
      <li>Run the backend: <code>python -m server</code></li>
    </ol>
    ${_PORTS_DEFAULT_TABLE(lang)}
    ${_PORTS_TROUBLESHOOT(lang)}
  `,
      sr: `
    <h3>1. Instalirajte Python 3.10+</h3>
    <ol>
      <li>Preuzmite Python sa <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">zvaničnog sajta</a></li>
      <li>Pri instalaciji obavezno označite "Add Python to PATH"</li>
      <li>Proverite: <code>python --version</code></li>
    </ol>
    <h3>2. Preuzmite izvorni kod</h3>
    <ol>
      <li><strong>Preko Git-a:</strong> <code>git clone https://github.com/FlowHack/flowlink-proxy.git</code></li>
      <li><strong>Ili ZIP:</strong> preuzmite sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
    </ol>
    <h3>3. Pokrenite</h3>
    <ol>
      <li><code>cd flowlink-proxy</code></li>
      <li>Kreirajte virtuelno okruženje: <code>python -m venv venv</code></li>
      <li>Aktivirajte: <code>source venv/bin/activate</code> (Linux/macOS) ili <code>venv\Scripts\activate</code> (Windows)</li>
      <li>Instalirajte zavisnosti: <code>pip install -r requirements.txt</code></li>
      <li>Pokrenite backend: <code>python -m server</code></li>
    </ol>
    ${_PORTS_DEFAULT_TABLE(lang)}
    ${_PORTS_TROUBLESHOOT(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
};

/**
 * Контент для подвкладок Linux (вложенные в backend-linux).
 * @type {Object<string, string>}
 */
const _LINUX_SUB_TEXTS = {
  'linux-deb': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Пакет (.deb)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.deb</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>Package (.deb)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-linux-x64.deb</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Install: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Run: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>Paket (.deb)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-linux-x64.deb</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Instalirajte: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'linux-rpm': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Пакет (.rpm)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.rpm</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo rpm -i FlowLink-Proxy-*.rpm</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>Package (.rpm)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-linux-x64.rpm</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Install: <code>sudo rpm -i FlowLink-Proxy-*.rpm</code></li>
      <li>Run: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>Paket (.rpm)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-linux-x64.rpm</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Instalirajte: <code>sudo rpm -i FlowLink-Proxy-*.rpm</code></li>
      <li>Pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'linux-bin': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Запустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>Binary (.tar.gz)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Unpack: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Run: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>Binarni fajl (.tar.gz)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Raspakujte: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Pokrenite: <code>./flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
};

/**
 * Контент для подвкладок macOS (вложенные в backend-macos).
 * @type {Object<string, string>}
 */
const _MACOS_SUB_TEXTS = {
  'macos-intel': (lang = 'ru') => {
    const texts = {
      ru: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-intel">
      <button class="help-sub-tab active" data-sub="macos-intel-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-intel-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-intel">
      ${_renderSubTabContent('macos-intel', 'macos-intel-pkg')}
    </div>
  `,
      en: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-intel">
      <button class="help-sub-tab active" data-sub="macos-intel-pkg">Package (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-intel-bin">Binary (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-intel">
      ${_renderSubTabContent('macos-intel', 'macos-intel-pkg')}
    </div>
  `,
      sr: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-intel">
      <button class="help-sub-tab active" data-sub="macos-intel-pkg">Paket (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-intel-bin">Binarni fajl (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-intel">
      ${_renderSubTabContent('macos-intel', 'macos-intel-pkg')}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'macos-arm': (lang = 'ru') => {
    const texts = {
      ru: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-arm">
      <button class="help-sub-tab active" data-sub="macos-arm-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-arm-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-arm">
      ${_renderSubTabContent('macos-arm', 'macos-arm-pkg')}
    </div>
  `,
      en: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-arm">
      <button class="help-sub-tab active" data-sub="macos-arm-pkg">Package (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-arm-bin">Binary (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-arm">
      ${_renderSubTabContent('macos-arm', 'macos-arm-pkg')}
    </div>
  `,
      sr: `
    <div class="help-sub-tabs" id="help-sub-tabs-macos-arm">
      <button class="help-sub-tab active" data-sub="macos-arm-pkg">Paket (.pkg)</button>
      <button class="help-sub-tab" data-sub="macos-arm-bin">Binarni fajl (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-macos-arm">
      ${_renderSubTabContent('macos-arm', 'macos-arm-pkg')}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'macos-intel-pkg': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Intel — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>Intel — Package (.pkg)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-x64.pkg</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Install: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Run: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>Intel — Paket (.pkg)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-x64.pkg</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Instalirajte: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'macos-intel-bin': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>Intel — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Запустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>Intel — Binary (.tar.gz)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Unpack: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Run: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>Intel — Binarni fajl (.tar.gz)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Raspakujte: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Pokrenite: <code>./flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'macos-arm-pkg': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>ARM — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Установите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Запустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>ARM — Package (.pkg)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-arm64.pkg</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Install: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Run: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>ARM — Paket (.pkg)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-arm64.pkg</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Instalirajte: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'macos-arm-bin': (lang = 'ru') => {
    const texts = {
      ru: `
    <h3>ARM — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Запустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    <h3>ARM — Binary (.tar.gz)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Unpack: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Run: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    <h3>ARM — Binarni fajl (.tar.gz)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Raspakujte: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Pokrenite: <code>./flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
};

/**
 * Контент для подвкладок обновления бэкенда (update-backend).
 * @type {Object<string, Function|string>}
 */
const _UPDATE_SUB_TEXTS = {
  'update-windows': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
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
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>1. Download the new installer</h3>
    <ol>
      <li>Go to <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Download <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Update</h3>
    <ol>
      <li>Run the installer — it will replace files automatically</li>
      <li>The backend will be restarted</li>
    </ol>
    <h3>Standalone binary</h3>
    <ol>
      <li>Download the new archive from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Stop the old process (system tray → "Exit")</li>
      <li>Replace the files and run the new one</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>1. Preuzmite novi instalater</h3>
    <ol>
      <li>Idite na <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Preuzmite <code>FlowLink-Proxy-vX.X.X-Setup.exe</code></li>
    </ol>
    <h3>2. Ažurirajte</h3>
    <ol>
      <li>Pokrenite instalater — on će automatski zameniti datoteke</li>
      <li>Backend će biti ponovo pokrenut</li>
    </ol>
    <h3>Standalone binarni fajl</h3>
    <ol>
      <li>Preuzmite novu arhivu sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Zaustavite stari proces (sistemska traka → "Izlaz")</li>
      <li>Zamenite datoteke i pokrenite novi</li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-linux': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
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
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-linux">
      <button class="help-sub-tab active" data-sub="update-linux-deb">Package (.deb)</button>
      <button class="help-sub-tab" data-sub="update-linux-rpm">Package (.rpm)</button>
      <button class="help-sub-tab" data-sub="update-linux-bin">Binary (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-linux">
      ${_renderUpdateSubTabContent('update-linux-deb', tag)}
    </div>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-linux">
      <button class="help-sub-tab active" data-sub="update-linux-deb">Paket (.deb)</button>
      <button class="help-sub-tab" data-sub="update-linux-rpm">Paket (.rpm)</button>
      <button class="help-sub-tab" data-sub="update-linux-bin">Binarni fajl (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-linux">
      ${_renderUpdateSubTabContent('update-linux-deb', tag)}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos">
      <button class="help-sub-tab active" data-sub="update-macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="update-macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos">
      ${_renderUpdateSubTabContent('update-macos-intel', tag)}
    </div>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos">
      <button class="help-sub-tab active" data-sub="update-macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="update-macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos">
      ${_renderUpdateSubTabContent('update-macos-intel', tag)}
    </div>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos">
      <button class="help-sub-tab active" data-sub="update-macos-intel">Intel</button>
      <button class="help-sub-tab" data-sub="update-macos-arm">ARM</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos">
      ${_renderUpdateSubTabContent('update-macos-intel', tag)}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-source': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Через Git:</strong> <code>git pull</code></li>
      <li><strong>Или ZIP:</strong> скачайте новый архив, распакуйте поверх старой папки</li>
      <li>Остановите старый процесс, перезапустите: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Via Git:</strong> <code>git pull</code></li>
      <li><strong>Or ZIP:</strong> download the new archive, unpack it over the old folder</li>
      <li>Stop the old process, restart: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <ol>
      <li><strong>Preko Git-a:</strong> <code>git pull</code></li>
      <li><strong>Ili ZIP:</strong> preuzmite novu arhivu, raspakujte je preko stare fascikle</li>
      <li>Zaustavite stari proces, ponovo pokrenite: <code>python -m server</code></li>
    </ol>
    ${_EMAIL_FOOTER(lang)}
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-linux-deb': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Пакет (.deb)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.deb</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Package (.deb)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-linux-x64.deb</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Update: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Restart: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Paket (.deb)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-linux-x64.deb</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Ažurirajte: <code>sudo dpkg -i FlowLink-Proxy-*.deb</code></li>
      <li>Ponovo pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-linux-rpm': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Пакет (.rpm)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.rpm</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo rpm -U FlowLink-Proxy-*.rpm</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Package (.rpm)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-linux-x64.rpm</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Update: <code>sudo rpm -U FlowLink-Proxy-*.rpm</code></li>
      <li>Restart: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Paket (.rpm)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-linux-x64.rpm</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Ažurirajte: <code>sudo rpm -U FlowLink-Proxy-*.rpm</code></li>
      <li>Ponovo pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-linux-bin': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте поверх старой папки: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Перезапустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Binary (.tar.gz)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Unpack over the old folder: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Restart: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Binarni fajl (.tar.gz)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-linux-x64.tar.gz</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Raspakujte preko stare fascikle: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Ponovo pokrenite: <code>./flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos-intel': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-intel">
      <button class="help-sub-tab active" data-sub="update-macos-intel-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-intel-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-intel">
      ${_renderUpdateSubTabContent('update-macos-intel-pkg', tag)}
    </div>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-intel">
      <button class="help-sub-tab active" data-sub="update-macos-intel-pkg">Package (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-intel-bin">Binary (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-intel">
      ${_renderUpdateSubTabContent('update-macos-intel-pkg', tag)}
    </div>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-intel">
      <button class="help-sub-tab active" data-sub="update-macos-intel-pkg">Paket (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-intel-bin">Binarni fajl (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-intel">
      ${_renderUpdateSubTabContent('update-macos-intel-pkg', tag)}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos-arm': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-arm">
      <button class="help-sub-tab active" data-sub="update-macos-arm-pkg">Пакет (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-arm-bin">Бинарник (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-arm">
      ${_renderUpdateSubTabContent('update-macos-arm-pkg', tag)}
    </div>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-arm">
      <button class="help-sub-tab active" data-sub="update-macos-arm-pkg">Package (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-arm-bin">Binary (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-arm">
      ${_renderUpdateSubTabContent('update-macos-arm-pkg', tag)}
    </div>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <div class="help-sub-tabs" id="help-sub-tabs-update-macos-arm">
      <button class="help-sub-tab active" data-sub="update-macos-arm-pkg">Paket (.pkg)</button>
      <button class="help-sub-tab" data-sub="update-macos-arm-bin">Binarni fajl (.tar.gz)</button>
    </div>
    <div class="help-sub-content" id="help-sub-content-update-macos-arm">
      ${_renderUpdateSubTabContent('update-macos-arm-pkg', tag)}
    </div>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos-intel-pkg': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Package (.pkg)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-x64.pkg</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Update: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Restart: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Paket (.pkg)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-x64.pkg</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Ažurirajte: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Ponovo pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos-intel-bin': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте поверх старой папки: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Перезапустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Binary (.tar.gz)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Unpack over the old folder: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Restart: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>Intel — Binarni fajl (.tar.gz)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-x64.tar.gz</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Raspakujte preko stare fascikle: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Ponovo pokrenite: <code>./flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos-arm-pkg': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Пакет (.pkg)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.pkg</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Обновите: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Перезапустите: <code>flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Package (.pkg)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-arm64.pkg</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Update: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Restart: <code>flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Paket (.pkg)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-arm64.pkg</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Ažurirajte: <code>sudo installer -pkg FlowLink-Proxy-*.pkg -target /</code></li>
      <li>Ponovo pokrenite: <code>flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
  'update-macos-arm-bin': (lang = 'ru') => (tag) => {
    const texts = {
      ru: `
    ${tag ? `<p>Доступна новая версия: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Бинарник (.tar.gz)</h3>
    <ol>
      <li>Скачайте <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте поверх старой папки: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Перезапустите: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      en: `
    ${tag ? `<p>New version available: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Binary (.tar.gz)</h3>
    <ol>
      <li>Download <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> from <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Unpack over the old folder: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Restart: <code>./flowlink-proxy</code></li>
    </ol>
  `,
      sr: `
    ${tag ? `<p>Dostupna nova verzija: <strong>${tag}</strong></p>` : ''}
    <h3>ARM — Binarni fajl (.tar.gz)</h3>
    <ol>
      <li>Preuzmite <code>FlowLink-Proxy-*-macos-arm64.tar.gz</code> sa <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Raspakujte preko stare fascikle: <code>tar -xzf FlowLink-Proxy-*.tar.gz</code></li>
      <li>Ponovo pokrenite: <code>./flowlink-proxy</code></li>
    </ol>
  `,
    };
    return texts[lang] || texts.ru;
  },
};

/** @type {boolean} True, когда модалка открыта в режиме «Обновление». */
let _isUpdateMode = false;
/** @type {string} Тег доступного обновления (например 'v0.1.0') или пустая строка. */
let _updateTag = '';
/** Текущий язык help-контента (обновляется при открытии модалки). */
let _currentHelpLang = 'ru';

/** Список вкладок help-модалки (порядок отображения). */
const _TABS = ['backend', 'browser', 'port', 'faq', 'license'];

/**
 * Контексты открытия помощи и соответствующие им вкладки.
 * Каждый контекст показывает только релевантные вкладки.
 */
const _CONTEXT_TABS = {
  // Общая помощь (кнопка «Помощь» в popup) — все вкладки.
  general: ['backend', 'browser', 'port', 'faq', 'license'],
  // Помощь при невозможности подключения к бэкенду — без вкладки «Браузер».
  'backend-error': ['backend', 'port', 'faq', 'license'],
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
 * @param {string} [updateTag] — тег доступного обновления (например 'v0.1.0').
 * @param {string} [context] — контекст открытия ('general', 'backend-error',
 *   'browser-warning', 'update').
 */
export function openHelpModal(tab, isUpdate, updateTag, context) {
  getCurrentLang().then(l => { _currentHelpLang = l; });
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

  const textFn = HELP_TEXTS[tab];
  if (!textFn) {
    console.warn('[FlowLink Proxy] Текст для вкладки помощи не найден:', tab);
    return;
  }

  // Все ключи HELP_TEXTS — функции (lang) => html
  try {
    content.innerHTML = textFn(_currentHelpLang);
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
    return (typeof text === 'function' ? text(_currentHelpLang) : text) + _EMAIL_FOOTER(_currentHelpLang);
  }
  // Вложенные подвкладки linux/macos
  if (tab === 'linux') {
    const text = _LINUX_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return (typeof text === 'function' ? text(_currentHelpLang) : text) + _EMAIL_FOOTER(_currentHelpLang);
  }
  if (tab === 'macos') {
    const text = _MACOS_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return (typeof text === 'function' ? text(_currentHelpLang) : text) + _EMAIL_FOOTER(_currentHelpLang);
  }
  // Под-подвкладки macOS (macos-intel/macos-arm)
  if (tab === 'macos-intel' || tab === 'macos-arm') {
    const text = _MACOS_SUB_TEXTS[sub];
    if (!text) return '<p>Раздел в разработке.</p>';
    return (typeof text === 'function' ? text(_currentHelpLang) : text) + _EMAIL_FOOTER(_currentHelpLang);
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
    // Update-под-словари — функции (lang) => (tag) => html
    return typeof text === 'function' ? text(_currentHelpLang)(escapedTag) : text;
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

  const textFn = HELP_TEXTS[tab];
  if (!textFn) {
    console.warn('[FlowLink Proxy] Текст для вкладки обновления не найден:', tab);
    return;
  }
  try {
    // Экранируем тег перед вставкой в HTML — защита от XSS (инъекция через tag)
    const escapedTag = escapeHtml(tag);
    // Update-ключи HELP_TEXTS — функции (lang) => (tag) => html
    content.innerHTML = textFn(_currentHelpLang)(escapedTag);
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
