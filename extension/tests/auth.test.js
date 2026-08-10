/**
 * @fileoverview
 * Тесты модуля управления токеном аутентификации (auth.js).
 * Проверяют получение токена из storage, bootstrap-запрос и заголовки.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

// Мокаем глобальный chrome.storage.local и fetch ДО импорта auth.js
const storageData = {};
globalThis.chrome = {
  storage: {
    local: {
      async get(key) {
        if (typeof key === 'string') {
          return { [key]: storageData[key] };
        }
        return { ...storageData };
      },
      async set(obj) {
        Object.assign(storageData, obj);
      },
    },
  },
};

// Импортируем auth.js после мока chrome
const { getAuthToken, authHeaders, resetAuthTokenCache } = await import('../shared/auth.js');

test('authHeaders добавляет X-Auth-Token при наличии токена', () => {
  const headers = authHeaders('secret-token');
  assert.equal(headers['X-Auth-Token'], 'secret-token');
});

test('authHeaders не добавляет X-Auth-Token при null', () => {
  const headers = authHeaders(null);
  assert.equal(headers['X-Auth-Token'], undefined);
});

test('authHeaders сохраняет дополнительные заголовки', () => {
  const headers = authHeaders('token', { 'Content-Type': 'application/json' });
  assert.equal(headers['Content-Type'], 'application/json');
  assert.equal(headers['X-Auth-Token'], 'token');
});

test('getAuthToken возвращает токен из storage без bootstrap', async () => {
  resetAuthTokenCache();
  storageData.flowlinkAuthToken = 'stored-token';
  const token = await getAuthToken('http://127.0.0.1:8081/api');
  assert.equal(token, 'stored-token');
});

test('getAuthToken запрашивает bootstrap при отсутствии токена', async () => {
  resetAuthTokenCache();
  delete storageData.flowlinkAuthToken;

  // Мокаем fetch для bootstrap
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.match(url, /\/bootstrap$/);
    return {
      ok: true,
      async json() {
        return { token: 'bootstrap-token', apiPort: 8081 };
      },
    };
  };

  try {
    const token = await getAuthToken('http://127.0.0.1:8081/api');
    assert.equal(token, 'bootstrap-token');
    // Токен должен быть сохранён в storage
    assert.equal(storageData.flowlinkAuthToken, 'bootstrap-token');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('getAuthToken возвращает null при недоступном bootstrap', async () => {
  resetAuthTokenCache();
  delete storageData.flowlinkAuthToken;

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };

  try {
    const token = await getAuthToken('http://127.0.0.1:8081/api');
    assert.equal(token, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('getAuthToken возвращает null при HTTP-ошибке bootstrap', async () => {
  resetAuthTokenCache();
  delete storageData.flowlinkAuthToken;

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 500 });

  try {
    const token = await getAuthToken('http://127.0.0.1:8081/api');
    assert.equal(token, null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
