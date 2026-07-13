/**
 * @fileoverview
 * HTTP-хелперы для общения с Python API.
 * Единственная ответственность: HTTP-запросы к бэкенду.
 */

import { API_BASE } from './constants.js';

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
    if (err.error) msg = err.error;
  } catch { /* тело не JSON — оставляем стандартное сообщение */ }
  return msg;
}

/**
 * GET-запрос к API.
 * @param {string} endpoint — путь вида '/config', '/status' и т.д.
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
export async function apiGet(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    throw new Error(await _handleApiError(res, 'GET'));
  }
  try {
    return await res.json();
  } catch {
    throw new Error('Бэкенд вернул невалидный ответ. Попробуйте перезапустить бэкенд.');
  }
}

/**
 * POST-запрос к API с JSON-телом.
 * @param {string} endpoint — путь вида '/config', '/ping' и т.д.
 * @param {object} body — тело запроса (будет сериализовано в JSON).
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
export async function apiPost(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await _handleApiError(res, 'POST'));
  }
  try {
    return await res.json();
  } catch {
    throw new Error('Бэкенд вернул невалидный ответ. Попробуйте перезапустить бэкенд.');
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
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  try {
    const data = await res.json();
    return { status: res.status, data };
  } catch {
    return { status: res.status, data: {} };
  }
}
