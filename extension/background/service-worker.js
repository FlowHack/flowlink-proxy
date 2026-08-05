/**
 * @fileoverview
 * Service Worker — фоновый процесс расширения.
 * Отвечает за SSE-соединение с бэкендом для realtime-уведомлений.
 *
 * При получении события config_changed кладёт флаг в chrome.storage,
 * чтобы popup знал, что данные изменились.
 */

import { getAuthToken, authHeaders, resetAuthToken } from '../shared/auth.js';

console.log('[FlowLink Proxy] Service Worker стартует');

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[FlowLink Proxy] Расширение установлено');
  }
});

// Keepalive-механизм: Chrome убивает MV3 service worker после ~30 сек
// бездействия, что рвёт SSE-соединение и останавливает setInterval.
// Alarm каждые 30 секунд будит service worker и восстанавливает
// соединение с бэкендом (минимальный период для Chrome — 0.5 минуты).
chrome.alarms.get('flowlink-keepalive').then((a) => {
  if (!a) {
    chrome.alarms.create('flowlink-keepalive', { periodInMinutes: 0.5 });
  }
}).catch(e => console.warn('[FlowLink Proxy] Ошибка проверки keepalive-alarm:', e));

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'flowlink-keepalive') {
    ensureSSEConnected();
  }
});

// Пробуждение от popup: при открытии popup шлёт { type: 'wake' },
// чтобы мгновенно восстановить SSE-соединение, не дожидаясь alarm.
chrome.runtime.onMessage.addListener((message) => {
  if (message && message.type === 'wake') {
    ensureSSEConnected();
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
}).catch((e) => {
  console.warn('[FlowLink Proxy] Не удалось загрузить порт из storage:', e);
  connectSSE();
});

// Слушаем изменения порта
chrome.storage.onChanged.addListener((changes) => {
  try {
    if (changes.apiPort && Number.isInteger(changes.apiPort.newValue)) {
      apiPort = changes.apiPort.newValue;
      connectSSE();
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Ошибка обработки изменения storage:', e);
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
    const token = await getAuthToken(`http://127.0.0.1:${apiPort}/api`);
    const res = await fetch(`http://127.0.0.1:${apiPort}/api/enabled`, {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify({ enabled }),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
      console.warn('[FlowLink Proxy] Бэкенд вернул HTTP', res.status, 'при отправке состояния');
      return;
    }
    console.log('[FlowLink Proxy] Отправлено состояние бэкенду:', enabled);
  } catch (e) {
    console.warn('[FlowLink Proxy] Не удалось отправить состояние бэкенду:', e);
  }
}

/** EventSource для SSE-подключения к бэкенду. */
let eventSource = null;
let _sseErrorCount = 0;

/**
 * Проверяет валидность токена через запрос к /api/version.
 * Возвращает true, если токен валиден (или сервер недоступен — пытаемся открыть SSE).
 * Возвращает false, если получен 401/403 — токен устарел.
 * @param {string} baseUrl — базовый URL API (http://127.0.0.1:port/api).
 * @param {string} token — токен авторизации.
 * @returns {Promise<boolean>}
 */
async function _verifyToken(baseUrl, token) {
  try {
    const res = await fetch(`${baseUrl}/version`, {
      method: 'GET',
      headers: authHeaders(token),
      signal: AbortSignal.timeout(3000),
    });
    // 401/403 — невалидный токен, остальные коды (включая 200/500) считаем валидными,
    // чтобы не блокировать попытку подключения к SSE.
    return res.status !== 401 && res.status !== 403;
  } catch (e) {
    // Сеть недоступна или таймаут — считаем токен валидным (попытка SSE всё равно будет)
    console.debug('[FlowLink Proxy] SSE: не удалось проверить токен:', (e && e.message) ? e.message : e);
    return true;
  }
}

/**
 * Подключается к SSE-эндпоинту бэкенда.
 * При получении config_changed — сохраняет флаг в storage.
 * Автоматически переподключается при обрыве.
 */
function connectSSE() {
  if (eventSource) {
    eventSource.close();
  }

  // EventSource не поддерживает кастомные заголовки, поэтому токен
  // передаётся в query-параметре. Бэкенд маскирует его в логах.
  const baseUrl = `http://127.0.0.1:${apiPort}/api`;
  getAuthToken(baseUrl).then(async (token) => {
    // Проверяем, что токен ещё валиден: бэкенд мог перезапуститься и сгенерировать новый
    if (token) {
      const isTokenValid = await _verifyToken(baseUrl, token);
      if (!isTokenValid) {
        console.warn('[FlowLink Proxy] SSE: токен устарел (401/403), сбрасываю и перезапрашиваю через bootstrap');
        await resetAuthToken();
        token = await getAuthToken(baseUrl);
      }
    }
    const url = token
      ? `${baseUrl}/events?token=${encodeURIComponent(token)}`
      : `${baseUrl}/events`;
    console.log('[FlowLink Proxy] SSE: подключаюсь к', url);
    _openEventSource(url);
  }).catch((e) => {
    console.warn('[FlowLink Proxy] SSE: не удалось получить токен:', e);
    _openEventSource(`${baseUrl}/events`);
  });
}

function _openEventSource(url) {
  if (eventSource) {
    eventSource.close();
  }

  try {
    eventSource = new EventSource(url);

    eventSource.addEventListener('config_changed', () => {
      console.log('[FlowLink Proxy] SSE: конфиг изменён');
      void chrome.storage.local.set({ configChanged: true, configChangedAt: Date.now() }).catch(e => console.warn('[FlowLink Proxy] SSE: ошибка записи в storage:', e));
    });

    // Изменение настроек браузера (автозапуск/путь) — тоже перезагружаем popup
    eventSource.addEventListener('browser_config_changed', () => {
      console.log('[FlowLink Proxy] SSE: конфигурация браузера изменена');
      void chrome.storage.local.set({ configChanged: true, configChangedAt: Date.now() }).catch(e => console.warn('[FlowLink Proxy] SSE: ошибка записи в storage:', e));
    });
    eventSource.addEventListener('autostart_browser_changed', () => {
      console.log('[FlowLink Proxy] SSE: автозапуск браузера изменён');
      void chrome.storage.local.set({ configChanged: true, configChangedAt: Date.now() }).catch(e => console.warn('[FlowLink Proxy] SSE: ошибка записи в storage:', e));
    });

    eventSource.addEventListener('need_update', (event) => {
      console.log('[FlowLink Proxy] SSE: симуляция обновления');
      let version = '';
      try {
        version = JSON.parse(event.data).version || '';
      } catch (e) {
        console.warn('[FlowLink Proxy] SSE: ошибка парсинга need_update:', e);
      }
      void chrome.storage.local.set({ needUpdate: true, needUpdateVersion: version, needUpdateAt: Date.now() }).catch(e => console.warn('[FlowLink Proxy] SSE: ошибка записи в storage:', e));
    });

    // Бэкенд перезапустился — расширение перечитывает конфиг
    eventSource.addEventListener('backend_ready', () => {
      console.log('[FlowLink Proxy] SSE: бэкенд готов, перечитываю конфиг');
      void chrome.storage.local.set({ configChanged: true, configChangedAt: Date.now() }).catch(e => console.warn('[FlowLink Proxy] SSE: ошибка записи в storage:', e));
    });

    eventSource.onerror = (err) => {
      _sseErrorCount++;
      if (_sseErrorCount % 5 === 0) {
        console.warn('[FlowLink Proxy] SSE: ошибка/разрыв', err);
      }
      // EventSource сам переподключается
    };

    eventSource.onopen = () => {
      console.log('[FlowLink Proxy] SSE: подключено');
      _sseErrorCount = 0;
      updateBadge(true);
      pushEnabledState();
    };
  } catch (e) {
    console.warn('[FlowLink Proxy] SSE: не удалось подключиться', e);
    // Пробуем снова через 5 секунд
    setTimeout(connectSSE, 5000);
  }
}

/**
 * Периодически проверяет, что SSE-соединение с бэкендом установлено.
 * Если бэкенд появился позже расширения (браузер запущен раньше),
 * EventSource может не переподключиться автоматически — здесь мы
 * принудительно пересоздаём соединение, когда бэкенд становится доступен.
 */
/**
 * Обновляет badge на иконке расширения.
 * При недоступности бэкенда — красный badge '!', при доступности — сброс.
 * @param {boolean} backendAvailable — доступен ли бэкенд.
 */
function updateBadge(backendAvailable) {
  try {
    if (backendAvailable) {
      void chrome.action.setBadgeText({ text: '' });
    } else {
      void chrome.action.setBadgeText({ text: '!' });
      void chrome.action.setBadgeBackgroundColor({ color: '#d32f2f' });
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Не удалось обновить badge:', e);
  }
}

function ensureSSEConnected() {
  // Если соединение уже открыто — не трогаем.
  // Если eventSource застрял в состоянии CONNECTING (бэкенд появился позже),
  // EventSource может не переподключиться сам — здесь мы принудительно
  // пересоздаём соединение, когда бэкенд становится доступен.
  if (eventSource && eventSource.readyState === EventSource.OPEN) {
    updateBadge(true);
    return;
  }
  // eventSource ещё не создан или закрыт — пробуем переподключиться
  // Проверяем, что бэкенд доступен, прежде чем переподключаться
  fetch(`http://127.0.0.1:${apiPort}/api/version`, { signal: AbortSignal.timeout(3000) })
    .then((res) => {
      if (res.ok) {
        console.log('[FlowLink Proxy] SSE: бэкенд доступен, переподключаюсь');
        updateBadge(true);
        connectSSE();
      } else {
        updateBadge(false);
      }
    })
    .catch((e) => {
      console.debug('[FlowLink Proxy] SSE: бэкенд недоступен, жду следующей проверки:', (e && e.message) ? e.message : e);
      updateBadge(false);
      // Бэкенд недоступен — ждём следующей проверки
    });
}

// Запускаем периодическую проверку SSE-соединения каждые 10 секунд
setInterval(ensureSSEConnected, 10000);
