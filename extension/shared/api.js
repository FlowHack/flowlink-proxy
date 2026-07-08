/**
 * @fileoverview
 * HTTP-хелперы для общения с Python API.
 * Единственная ответственность: HTTP-запросы к бэкенду.
 */

import { API_BASE } from './constants.js';

/**
 * GET-запрос к API.
 * @param {string} endpoint — путь вида '/config', '/status' и т.д.
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
export async function apiGet(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
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
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}
