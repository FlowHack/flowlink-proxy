/**
 * @fileoverview
 * Скрипт страницы установки расширения (help.html).
 * Подставляет актуальный URL релизов из shared/constants.js вместо хардкода.
 *
 * Примечание: страница может открываться как через chrome-extension://,
 * так и через file:// (webbrowser.open). В контексте file:// chrome.runtime
 * недоступен — в этом случае используется резервный хардкод URL.
 */

(function () {
  'use strict';

  // Резервный URL релизов (используется, если constants.js недоступен)
  const FALLBACK_RELEASES_URL = 'https://github.com/FlowHack/flowlink-proxy/releases/latest';

  /**
   * Словарь переводов для страницы установки расширения.
   * Страница открывается через file:// (webbrowser.open), где chrome.i18n
   * недоступен, поэтому используется embedded-словарь с определением языка
   * через navigator.language.
   */
  const TRANSLATIONS = {
    ru: {
      title: 'FlowLink Proxy — Установка расширения',
      intro: 'Бэкенд запущен, но расширение Chrome не подключено. Выполните следующие шаги:',
      step1Title: 'Откройте Chrome',
      step1Text: ' и перейдите на страницу расширения:',
      step2Title: 'Установите расширение',
      step2Text: ' одним из способов:',
      manualCrx: 'Вручную (CRX):',
      manualCrxText: ' скачайте FlowLink-Proxy-vX.X.X.crx со страницы релизов и перетащите на chrome://extensions.',
      fromSource: 'Из исходников:',
      fromSourceText: ' включите режим разработчика, нажмите «Загрузить распакованное расширение» и выберите папку extension.',
      note1Title: 'Примечание:',
      note1Text: ' после установки расширения вручную нажмите «Обновить» (круглая стрелка) на странице chrome://extensions, чтобы применить изменения.',
      helpHint: 'Подробная справка по настройке доступна в расширении: нажмите на иконку FlowLink Proxy → «Помощь».',
      note2Title: 'Примечание:',
      note2Text: ' Возможно, потребуется VPN или прокси для доступа к GitHub (для пользователей в России).',
      support: 'Поддержка:',
    },
    en: {
      title: 'FlowLink Proxy — Extension Installation',
      intro: 'The backend is running, but the Chrome extension is not connected. Follow these steps:',
      step1Title: 'Open Chrome',
      step1Text: ' and go to the extension page:',
      step2Title: 'Install the extension',
      step2Text: ' in one of the following ways:',
      manualCrx: 'Manually (CRX):',
      manualCrxText: ' download FlowLink-Proxy-vX.X.X.crx from the releases page and drag it onto chrome://extensions.',
      fromSource: 'From source:',
      fromSourceText: ' enable developer mode, click "Load unpacked extension" and select the extension folder.',
      note1Title: 'Note:',
      note1Text: ' after installing the extension manually, click "Update" (circular arrow) on the chrome://extensions page to apply changes.',
      helpHint: 'Detailed setup help is available in the extension: click the FlowLink Proxy icon → "Help".',
      note2Title: 'Note:',
      note2Text: ' A VPN or proxy may be required to access GitHub (for users in Russia).',
      support: 'Support:',
    },
    sr: {
      title: 'FlowLink Proxy — Instalacija ekstenzije',
      intro: 'Backend je pokrenut, ali Chrome ekstenzija nije povezana. Pratite sledeće korake:',
      step1Title: 'Otvorite Chrome',
      step1Text: ' i idite na stranicu ekstenzije:',
      step2Title: 'Instalirajte ekstenziju',
      step2Text: ' na jedan od sledećih načina:',
      manualCrx: 'Ručno (CRX):',
      manualCrxText: ' preuzmite FlowLink-Proxy-vX.X.X.crx sa stranice izdanja i prevucite ga na chrome://extensions.',
      fromSource: 'Iz izvornog koda:',
      fromSourceText: ' uključite režim za programere, kliknite "Učitaj raspakovanu ekstenziju" i izaberite fasciklu extension.',
      note1Title: 'Napomena:',
      note1Text: ' nakon ručne instalacije ekstenzije, kliknite "Ažuriraj" (kružna strelica) na stranici chrome://extensions da primenite izmene.',
      helpHint: 'Detaljna pomoć za podešavanje dostupna je u ekstenziji: kliknite na ikonicu FlowLink Proxy → "Pomoć".',
      note2Title: 'Napomena:',
      note2Text: ' VPN ili proxy mogu biti potrebni za pristup GitHub-u (za korisnike u Rusiji).',
      support: 'Podrška:',
    },
  };

  /**
   * Определяет язык страницы по navigator.language.
   * @returns {string} Код языка ('ru' | 'en' | 'sr').
   */
  function detectLang() {
    const navLang = (navigator.language || 'ru').toLowerCase().substring(0, 2);
    return ['ru', 'en', 'sr'].includes(navLang) ? navLang : 'ru';
  }

  /**
   * Применяет локализацию ко всем элементам с атрибутом data-i18n.
   * @param {string} lang — код языка.
   */
  function applyI18n(lang) {
    const dict = TRANSLATIONS[lang] || TRANSLATIONS.ru;
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      const key = el.getAttribute('data-i18n');
      if (key && dict[key] !== undefined) {
        el.textContent = dict[key];
      }
    });
    document.documentElement.lang = lang;
    document.documentElement.setAttribute('data-lang', lang);
  }

  /**
   * Обновляет ссылки на релизы на странице.
   * @param {string} url — актуальный URL релизов.
   */
  function updateReleaseLinks(url) {
    document.querySelectorAll('a[href*="github.com/FlowHack/flowlink-proxy/releases"]')
      .forEach(function (a) {
        a.href = url;
      });
  }

  // Применяем локализацию при загрузке страницы
  applyI18n(detectLang());

  // Пытаемся получить актуальный URL из constants.js
  try {
    if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL) {
      fetch(chrome.runtime.getURL('shared/constants.js'))
        .then(function (r) { return r.text(); })
        .then(function (code) {
          const match = code.match(/GITHUB_RELEASES_URL\s*=\s*'([^']+)'/);
          if (match && match[1]) {
            updateReleaseLinks(match[1]);
          } else {
            updateReleaseLinks(FALLBACK_RELEASES_URL);
          }
        })
        .catch(function () {
          // constants.js недоступен (например, file://) — используем резерв
          updateReleaseLinks(FALLBACK_RELEASES_URL);
        });
    } else {
      // chrome.runtime недоступен (file://) — используем резерв
      updateReleaseLinks(FALLBACK_RELEASES_URL);
    }
  } catch (e) {
    // Любая ошибка — не ломаем страницу, оставляем хардкод
    updateReleaseLinks(FALLBACK_RELEASES_URL);
  }
})();
