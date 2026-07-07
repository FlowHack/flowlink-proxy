/**
 * @fileoverview
 * Offscreen-документ для тестирования SOCKS5 прокси.
 * Service Worker не может использовать fetch() напрямую (SW fetch()
 * не проходит через chrome.proxy.settings).
 *
 * Offscreen-страница — обычная страница расширения, её fetch()
 * корректно использует глобальные настройки chrome.proxy.settings.
 *
 * Протокол:
 * 1. SW (ProxyController._testProxy) отправляет сообщение:
 *    { action: 'EXEC_PROXY_TEST' }
 * 2. Данный скрипт выполняет fetch() тестового URL.
 * 3. Возвращает ответ:
 *    { alive: true/false }
 */

const TEST_URL = 'https://connectivitycheck.gstatic.com/generate_204';

/**
 * Обрабатывает запрос на тест прокси от Service Worker.
 * Выполняет fetch тестового URL и возвращает результат.
 */
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action === 'EXEC_PROXY_TEST') {
    fetch(TEST_URL)
      .then(resp => sendResponse({ alive: resp.ok }))
      .catch(() => sendResponse({ alive: false }));

    /* Сообщаем Chrome, что ответ будет отправлен асинхронно */
    return true;
  }

  /* Все остальные сообщения игнорируем */
  return false;
});
