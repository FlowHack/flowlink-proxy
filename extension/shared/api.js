/**
 * @fileoverview
 * HTTP-хелперы для общения с Python API.
 * Единственная ответственность: HTTP-запросы к бэкенду.
 */

import { API_BASE } from './constants.js';
import { getAuthToken, authHeaders, resetAuthToken } from './auth.js';

/**
 * Типизированная ошибка API.
 *
 * Поле `kind` позволяет различать тип ошибки:
 * - 'timeout' — таймаут запроса (AbortError)
 * - 'network' — сеть недоступна (TypeError 'Failed to fetch')
 * - 'http' — бэкенд ответил HTTP-кодом != 2xx
 * - 'json' — бэкенд вернул невалидный JSON
 *
 * Для обратной совместимости message сохраняет префикс 'NETWORK:'
 * для сетевых/таймаут-ошибок (проверяется в crud-proxy.js/crud-mask.js).
 */
export class ApiError extends Error {
  /**
   * @param {string} message — текст ошибки.
   * @param {'timeout'|'network'|'http'|'json'} kind — тип ошибки.
   */
  constructor(message, kind) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this._apiError = true;
  }
}

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
 * Классифицирует ошибку fetch по типу.
 * @param {Error} e — перехваченное исключение.
 * @returns {'timeout'|'network'} — тип ошибки.
 */
function _classifyFetchError(e) {
  if (e && e.name === 'AbortError') {
    return 'timeout';
  }
  return 'network';
}

/**
 * Выполняет HTTP-запрос к API с автоматическим сбросом токена при 401/403.
 *
 * При получении 401/403 (токен больше не валиден — бэкенд перезапущен):
 * 1. Сбрасывает старый токен (кэш + storage)
 * 2. Перезапрашивает токен через bootstrap
 * 3. Повторяет исходный запрос с новым токеном
 *
 * @param {string} method — HTTP-метод ('GET' или 'POST').
 * @param {string} endpoint — путь вида '/config', '/status'.
 * @param {object|null} body — тело запроса (null для GET).
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
async function _apiRequest(method, endpoint, body) {
  try {
    const token = await getAuthToken(API_BASE);
    const res = await _fetchWithAuth(method, endpoint, body, token);
    if (!res.ok && (res.status === 401 || res.status === 403)) {
      // Токен невалиден (401/403) — бэкенд мог перезапуститься, сбрасываем и пробуем ещё раз
      console.log('[FlowLink Proxy] api: получен ' + res.status + ', сбрасываю токен и перезапрашиваю');
      await resetAuthToken();
      const newToken = await getAuthToken(API_BASE);
      const retryRes = await _fetchWithAuth(method, endpoint, body, newToken);
      if (!retryRes.ok) {
        throw new ApiError(await _handleApiError(retryRes, method), 'http');
      }
      return await _parseJsonResponse(retryRes);
    }
    if (!res.ok) {
      throw new ApiError(await _handleApiError(res, method), 'http');
    }
    return await _parseJsonResponse(res);
  } catch (e) {
    if (e instanceof ApiError) {
      throw e;
    }
    const kind = _classifyFetchError(e);
    const prefix = kind === 'timeout' ? 'TIMEOUT:' : 'NETWORK:';
    throw new ApiError(prefix + (e.message || String(e)), kind);
  }
}

/**
 * Выполняет fetch с заданными параметрами.
 * @param {string} method — HTTP-метод.
 * @param {string} endpoint — путь API.
 * @param {object|null} body — тело запроса.
 * @param {string|null} token — токен аутентификации.
 * @returns {Promise<Response>}
 */
async function _fetchWithAuth(method, endpoint, body, token) {
  const headers = authHeaders(token);
  if (body !== null) {
    headers['Content-Type'] = 'application/json';
  }
  return await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(10000),
  });
}

/**
 * Парсит JSON-ответ, бросает ApiError при неудаче.
 * @param {Response} res — ответ fetch.
 * @returns {Promise<object>}
 */
async function _parseJsonResponse(res) {
  try {
    return await res.json();
  } catch (e) {
    console.warn('[FlowLink Proxy] api: невалидный JSON:', e);
    throw new ApiError('Бэкенд вернул невалидный ответ. Попробуйте перезапустить бэкенд.', 'json');
  }
}

export async function apiGet(endpoint) {
  return await _apiRequest('GET', endpoint, null);
}

/**
 * POST-запрос к API с JSON-телом.
 * @param {string} endpoint — путь вида '/config', '/ping' и т.д.
 * @param {object} body — тело запроса (будет сериализовано в JSON).
 * @returns {Promise<object>} — распарсенный JSON-ответ.
 */
export async function apiPost(endpoint, body) {
  return await _apiRequest('POST', endpoint, body);
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
    // Сетевая ошибка или таймаут — классифицируем
    const kind = _classifyFetchError(e);
    const prefix = kind === 'timeout' ? 'TIMEOUT:' : 'NETWORK:';
    throw new ApiError(prefix + (e.message || String(e)), kind);
  }
}
