/**
 * @fileoverview
 * HTTP-хелперы для общения с Python API.
 * Единственная ответственность: HTTP-запросы к бэкенду.
 */

import { API_BASE } from './constants.js';
import { getAuthToken, authHeaders } from './auth.js';

/**
 * Извлекает сообщение об ошибке из ответа сервера.
 * Пытается распарсить JSON-тело и вернуть поле `error`.
 * При неудаче — возвращает стандартное сообщение с HTTP-кодом.
 * @param {Response} res — объект ответа fetch.
 * @param {string} method — HTTP-метод для сообщения (GET/POST).
 * @returns {string} — текст ошибки для отображения пользователю.
 */
async function _handleApiError(res, method) {
  let msg = `${method} — HTTP ${res.status}`;
  try {
    const err = await res.json();
    if (err.error) {
      msg = typeof err.error === 'string' ? err.error : JSON.stringify(err.error);
    }
  } catch (e) {
    console.debug('[FlowLink Proxy] _handleApiError: тело ответа не JSON:', e);
  }
  return msg;
}

/**
 * GET-запрос к API.
 * @param {string} endpoint — путь вида '/config', '/status' и т.д.
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
export async function apiGet(endpoint) {
  try {
    const token = await getAuthToken(API_BASE);
    const res = await fetch(`${API_BASE}${endpoint}`, {
      headers: authHeaders(token),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) {
      throw Object.assign(new Error(await _handleApiError(res, 'GET')), { _apiError: true });
    }
    try {
      return await res.json();
    } catch (e) {
      console.warn('[FlowLink Proxy] apiGet: невалидный JSON:', e);
      throw Object.assign(new Error('Бэкенд вернул невалидный ответ. Попробуйте перезапустить бэкенд.'), { _apiError: true });
    }
  } catch (e) {
    // Если ошибка возникла внутри нашего try (HTTP/JSON) — пробрасываем без префикса NETWORK
    if (e._apiError) {
      throw e;
    }
    throw new Error('NETWORK:' + (e.message || String(e)));
  }
}

/**
 * POST-запрос к API с JSON-телом.
 * @param {string} endpoint — путь вида '/config', '/ping' и т.д.
 * @param {object} body — тело запроса (будет сериализовано в JSON).
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
export async function apiPost(endpoint, body) {
  try {
    const token = await getAuthToken(API_BASE);
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) {
      throw Object.assign(new Error(await _handleApiError(res, 'POST')), { _apiError: true });
    }
    try {
      return await res.json();
    } catch (e) {
      console.warn('[FlowLink Proxy] apiPost: невалидный JSON:', e);
      throw Object.assign(new Error('Бэкенд вернул невалидный ответ. Попробуйте перезапустить бэкенд.'), { _apiError: true });
    }
  } catch (e) {
    // Если ошибка возникла внутри нашего try (HTTP/JSON) — пробрасываем без префикса NETWORK
    if (e._apiError) {
      throw e;
    }
    throw new Error('NETWORK:' + (e.message || String(e)));
  }
}

/**
 * POST-запрос к API с возвратом HTTP-кода.
 * Используется для обработки 422 (валидация).
 * @param {string} endpoint — путь вида '/validate-browser'.
 * @param {object} body — тело запроса.
 * @returns {Promise<{status: number, data: object}>} — код + тело.
 */
export async function apiPostRaw(endpoint, body) {
  try {
    const token = await getAuthToken(API_BASE);
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    });
    try {
      const data = await res.json();
      return { status: res.status, data };
    } catch (e) {
      console.warn('[FlowLink Proxy] apiPostRaw: невалидный JSON:', e);
      return { status: res.status, data: {} };
    }
  } catch (e) {
    // Сетевая ошибка или непредвиденное исключение — добавляем префикс NETWORK
    throw new Error('NETWORK:' + (e.message || String(e)));
  }
}
