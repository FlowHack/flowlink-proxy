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
   * Обновляет ссылки на релизы на странице.
   * @param {string} url — актуальный URL релизов.
   */
  function updateReleaseLinks(url) {
    document.querySelectorAll('a[href*="github.com/FlowHack/flowlink-proxy/releases"]')
      .forEach(function (a) {
        a.href = url;
      });
  }

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
