/**
 * @fileoverview
 * Управление токеном аутентификации для общения с бэкендом.
 * Единственная ответственность: получение и хранение токена.
 *
 * Бэкенд генерирует случайный токен при старте и отдаёт его через
 * открытый эндпоинт GET /api/bootstrap. Расширение сохраняет токен
 * в chrome.storage.local и добавляет его в заголовок X-Auth-Token
 * ко всем запросам (кроме /api/version и /api/bootstrap).
 */

/** Ключ хранения токена в chrome.storage.local. */
const TOKEN_STORAGE_KEY = 'flowlinkAuthToken';

/** Кэш токена в памяти (чтобы не читать storage на каждый запрос). */
let _cachedToken = null;

/**
 * Читает токен из chrome.storage.local.
 * @returns {Promise<string|null>} — токен или null, если его нет.
 */
async function getStoredToken() {
  try {
    const result = await chrome.storage.local.get(TOKEN_STORAGE_KEY);
    const token = result[TOKEN_STORAGE_KEY];
    return typeof token === 'string' && token.length > 0 ? token : null;
  } catch (e) {
    console.warn('[FlowLink Proxy] auth: не удалось прочитать токен из storage:', e);
    return null;
  }
}

/**
 * Сохраняет токен в chrome.storage.local и кэш.
 * @param {string} token — токен аутентификации.
 */
async function storeToken(token) {
  _cachedToken = token;
  try {
    await chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: token });
  } catch (e) {
    console.warn('[FlowLink Proxy] auth: не удалось сохранить токен в storage:', e);
  }
}

/**
 * Получает токен аутентификации.
 *
 * Сначала проверяет кэш, затем storage. Если токена нет — запрашивает
 * его через GET /api/bootstrap (открытый эндпоинт) и сохраняет.
 *
 * @param {string} apiBase — базовый URL API (например 'http://127.0.0.1:8081/api').
 * @returns {Promise<string|null>} — токен или null, если бэкенд недоступен.
 */
export async function getAuthToken(apiBase) {
  if (_cachedToken) {
    return _cachedToken;
  }

  const stored = await getStoredToken();
  if (stored) {
    _cachedToken = stored;
    return stored;
  }

  // Токена нет — запрашиваем через bootstrap
  try {
    const res = await fetch(`${apiBase}/bootstrap`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
      console.warn('[FlowLink Proxy] auth: bootstrap вернул HTTP', res.status);
      return null;
    }
    const data = await res.json();
    if (data && typeof data.token === 'string' && data.token.length > 0) {
      await storeToken(data.token);
      return data.token;
    }
    // Бэкенд без токена (auth_token=None) — возвращаем null, запросы без токена
    return null;
  } catch (e) {
    console.warn('[FlowLink Proxy] auth: не удалось получить токен через bootstrap:', e);
    return null;
  }
}

/**
 * Сбрасывает кэш токена (например, при смене порта бэкенда).
 * Токен из storage не удаляется — он перезапросится при необходимости.
 */
export function resetAuthTokenCache() {
  _cachedToken = null;
}

/**
 * Формирует заголовки запроса с токеном аутентификации.
 * @param {string|null} token — токен (может быть null — тогда без заголовка).
 * @param {object} [extra] — дополнительные заголовки (например Content-Type).
 * @returns {object} — объект заголовков для fetch.
 */
export function authHeaders(token, extra = {}) {
  const headers = { ...extra };
  if (token) {
    headers['X-Auth-Token'] = token;
  }
  return headers;
}
