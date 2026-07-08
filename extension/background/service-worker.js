/**
 * @fileoverview
 * Service Worker — фоновый процесс расширения.
 * Отвечает за SSE-соединение с бэкендом для realtime-уведомлений.
 *
 * При получении события config_changed кладёт флаг в chrome.storage,
 * чтобы popup знал, что данные изменились.
 */

console.log('[FlowLink Proxy] Service Worker стартует');

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[FlowLink Proxy] Расширение установлено');
  }
});

/** Текущий порт API (берётся из chrome.storage). */
let apiPort = 8081;

// Загружаем сохранённый порт
chrome.storage.local.get('apiPort').then((result) => {
  if (result.apiPort && Number.isInteger(result.apiPort)) {
    apiPort = result.apiPort;
  }
  connectSSE();
});

// Слушаем изменения порта
chrome.storage.onChanged.addListener((changes) => {
  if (changes.apiPort) {
    apiPort = changes.apiPort.newValue;
    connectSSE();
  }
});

/**
 * Читает сохранённое состояние тогла из chrome.storage и пушит его на бэкенд.
 * Вызывается при (пере)подключении SSE.
 */
async function pushEnabledState() {
  try {
    const result = await chrome.storage.local.get('extEnabled');
    // По умолчанию расширение включено (true)
    const enabled = result.extEnabled !== undefined ? result.extEnabled : true;
    await fetch(`http://127.0.0.1:${apiPort}/api/enabled`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    console.log('[FlowLink Proxy] Отправлено состояние бэкенду:', enabled);
  } catch (e) {
    console.warn('[FlowLink Proxy] Не удалось отправить состояние бэкенду:', e);
  }
}

/** EventSource для SSE-подключения к бэкенду. */
let eventSource = null;

/**
 * Подключается к SSE-эндпоинту бэкенда.
 * При получении config_changed — сохраняет флаг в storage.
 * Автоматически переподключается при обрыве.
 */
function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }

  const url = `http://127.0.0.1:${apiPort}/api/events`;
  console.log('[FlowLink Proxy] SSE: подключаюсь к', url);

  try {
    eventSource = new EventSource(url);

    eventSource.addEventListener('config_changed', () => {
      console.log('[FlowLink Proxy] SSE: конфиг изменён');
      chrome.storage.local.set({ configChanged: true, configChangedAt: Date.now() });
    });

    eventSource.addEventListener('need_update', () => {
      console.log('[FlowLink Proxy] SSE: симуляция обновления');
      chrome.storage.local.set({ needUpdate: true, needUpdateAt: Date.now() });
    });

    eventSource.onerror = (err) => {
      console.warn('[FlowLink Proxy] SSE: ошибка/разрыв', err);
      // EventSource сам переподключается
    };

    eventSource.onopen = () => {
      console.log('[FlowLink Proxy] SSE: подключено');
      pushEnabledState();
    };
  } catch (e) {
    console.warn('[FlowLink Proxy] SSE: не удалось подключиться', e);
    // Пробуем снова через 5 секунд
    setTimeout(connectSSE, 5000);
  }
}
