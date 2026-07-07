/**
 * @fileoverview
 * Минимальный Service Worker — только логирование жизненного цикла.
 * Вся сетевая логика в Python proxy-gateway (localhost:8081).
 */
console.log('[FlowLink Proxy] Service Worker стартует');

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[FlowLink Proxy] Расширение установлено');
  }
});
