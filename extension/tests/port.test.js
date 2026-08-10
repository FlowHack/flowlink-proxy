/**
 * Тесты валидации портов и автопоиска бэкенда расширения.
 *
 * Покрывает:
 * - унифицированную проверку isValidPort (utils.js);
 * - извлечение порта из базового URL (extractPortFromBase в port_discovery.js);
 * - ядро автопоиска: isPortAlive (идентификация бэкенда FlowLink), scanPorts
 *   (детерминированный выбор порта) и discoverPort (обновление API_BASE,
 *   сохранение порта в storage, дедупликация параллельных вызовов).
 */
import { test, describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';

import { isValidPort } from '../shared/utils.js';
import { API_BASE, setApiPort } from '../shared/constants.js';
import {
  extractPortFromBase,
  isPortAlive,
  scanPorts,
  discoverPort,
} from '../shared/port_discovery.js';

// ---------------------------------------------------------------------------
// Mock chrome.storage (session + local) и глобального fetch
// ---------------------------------------------------------------------------

/** Хранилище chrome.storage.session (mock). */
const sessionData = {};
/** Хранилище chrome.storage.local (mock) — сюда discoverPort пишет apiPort. */
const localData = {};

globalThis.chrome = {
  storage: {
    session: {
      async get(key) {
        if (typeof key === 'string') return { [key]: sessionData[key] };
        return { ...sessionData };
      },
      async set(obj) {
        Object.assign(sessionData, obj);
      },
      async remove(key) {
        delete sessionData[key];
      },
    },
    local: {
      async get(key) {
        if (typeof key === 'string') return { [key]: localData[key] };
        return { ...localData };
      },
      async set(obj) {
        Object.assign(localData, obj);
      },
      async remove(key) {
        delete localData[key];
      },
    },
  },
};

/** Список URL, на которые обращался fetch (для проверки счётчиков вызовов). */
const fetchCalls = [];
/** Настройки ответов mock-сервера по портам: Map<port, {status, json|error}>. */
const portResponses = new Map();

/**
 * Задаёт ответ mock-сервера для конкретного порта.
 * @param {number} port — порт.
 * @param {{status?: number, json?: object|Function, error?: Error}} cfg —
 *   status (по умолч. 200), json (объект или функция: возвращает тело либо
 *   бросает ошибку парсинга), error (заставить fetch бросить исключение).
 */
function mockFetchSet(port, cfg) {
  portResponses.set(port, cfg);
}

/** Сбрасывает счётчик вызовов fetch и все настройки ответов. */
function mockFetchReset() {
  fetchCalls.length = 0;
  portResponses.clear();
}

/** Сколько раз fetch обращался к заданному порту. */
function fetchCountForPort(port) {
  return fetchCalls.filter((url) => new URL(url).port === String(port)).length;
}

// Mock глобального fetch: порты без настройки считаем недоступными —
// fetch бросает TypeError, как при отсутствии слушающего процесса.
globalThis.fetch = async (url) => {
  const urlStr = String(url);
  fetchCalls.push(urlStr);
  const port = Number(new URL(urlStr).port);
  const cfg = portResponses.get(port);
  if (!cfg) {
    throw new TypeError('fetch failed');
  }
  if (cfg.error) {
    throw cfg.error;
  }
  const status = cfg.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    // json: функция позволяет эмулировать ошибку парсинга тела ответа.
    json: async () => (typeof cfg.json === 'function' ? cfg.json() : cfg.json),
  };
};

beforeEach(() => {
  // Сбрасываем счётчики и настройки ответов между тестами
  mockFetchReset();
  // Восстанавливаем API_BASE на порт по умолчанию 8081
  setApiPort(8081);
  // Очищаем mock-хранилища
  for (const key of Object.keys(localData)) delete localData[key];
  for (const key of Object.keys(sessionData)) delete sessionData[key];
});

test('isValidPort принимает корректные порты', () => {
  assert.equal(isValidPort(1), true);
  assert.equal(isValidPort(65535), true);
  assert.equal(isValidPort(8081), true);
});

test('isValidPort отклоняет некорректные значения', () => {
  assert.equal(isValidPort(0), false);
  assert.equal(isValidPort(-1), false);
  assert.equal(isValidPort(65536), false);
  assert.equal(isValidPort(8081.5), false);
  assert.equal(isValidPort('8081'), false);
  assert.equal(isValidPort(null), false);
  assert.equal(isValidPort(undefined), false);
});

test('extractPortFromBase извлекает порт из базового URL', () => {
  assert.equal(extractPortFromBase('http://127.0.0.1:8091/api'), 8091);
  assert.equal(extractPortFromBase('http://127.0.0.1:8081/api'), 8081);
});

test('extractPortFromBase возвращает 8081 для некорректного порта', () => {
  assert.equal(extractPortFromBase('http://127.0.0.1:99999/api'), 8081);
  assert.equal(extractPortFromBase('http://example.com/api'), 8081);
  assert.equal(extractPortFromBase('invalid'), 8081);
});

// ---------------------------------------------------------------------------
// isPortAlive — идентификация бэкенда FlowLink (2xx + строковое поле version)
// ---------------------------------------------------------------------------

describe('isPortAlive', () => {
  it('возвращает false для невалидного порта и не вызывает fetch', async () => {
    assert.equal(await isPortAlive(0), false);
    assert.equal(await isPortAlive(65536), false);
    // Валидация происходит до сетевого запроса
    assert.equal(fetchCalls.length, 0);
  });

  it('считает порт живым при 2xx и строковом поле version', async () => {
    mockFetchSet(8081, { status: 200, json: { version: '1.4.0' } });
    assert.equal(await isPortAlive(8081), true);
  });

  it('отклоняет 2xx без поля version (чужая служба)', async () => {
    mockFetchSet(8081, { status: 200, json: { foo: 1 } });
    assert.equal(await isPortAlive(8081), false);
  });

  it('отклоняет 2xx с невалидным JSON', async () => {
    // json задан функцией, которая бросает ошибку парсинга
    mockFetchSet(8081, {
      status: 200,
      json: () => {
        throw new SyntaxError('Unexpected token');
      },
    });
    assert.equal(await isPortAlive(8081), false);
  });

  it('отклоняет 2xx с version не строкового типа', async () => {
    mockFetchSet(8081, { status: 200, json: { version: 123 } });
    assert.equal(await isPortAlive(8081), false);
  });

  it('отклоняет ответ 500 (сканер требует 2xx, в отличие от quickPing)', async () => {
    mockFetchSet(8081, { status: 500, json: { version: '1.4.0' } });
    assert.equal(await isPortAlive(8081), false);
  });

  it('возвращает false при сетевой ошибке (TypeError)', async () => {
    // Порт не настроен в mock — fetch выбрасывает TypeError по умолчанию
    assert.equal(await isPortAlive(8081), false);
  });
});

// ---------------------------------------------------------------------------
// scanPorts — детерминированный выбор порта по порядку диапазона 8080–8090
// ---------------------------------------------------------------------------

describe('scanPorts', () => {
  it('возвращает null, когда все порты диапазона мёртвые', async () => {
    const result = await scanPorts(8081);
    assert.equal(result, null);
    // 11 портов в диапазоне, 8081 пропущен как skipPort
    assert.equal(fetchCalls.length, 10);
  });

  it('возвращает первый живой порт по порядку диапазона (детерминизм)', async () => {
    // Живы 8085 и 8080 — должен быть выбран 8080 как первый по порядку
    mockFetchSet(8085, { status: 200, json: { version: '1.0.0' } });
    mockFetchSet(8080, { status: 200, json: { version: '1.0.0' } });
    const result = await scanPorts(8081);
    assert.equal(result, 8080);
  });

  it('пропускает skipPort: не возвращает его и не делает запрос к нему', async () => {
    mockFetchSet(8085, { status: 200, json: { version: '1.0.0' } });
    const result = await scanPorts(8085);
    assert.equal(result, null);
    // skipPort исключён из сканирования — запрос к нему не выполнялся
    assert.equal(fetchCountForPort(8085), 0);
    assert.equal(fetchCalls.length, 10);
  });

  it('находит порт 8080 на нижней границе диапазона (включительно)', async () => {
    mockFetchSet(8080, { status: 200, json: { version: '1.0.0' } });
    const result = await scanPorts(8081);
    assert.equal(result, 8080);
  });

  it('находит порт 8090 на верхней границе диапазона (включительно)', async () => {
    mockFetchSet(8090, { status: 200, json: { version: '1.0.0' } });
    const result = await scanPorts(8081);
    assert.equal(result, 8090);
  });
});

// ---------------------------------------------------------------------------
// discoverPort — обновление API_BASE, сохранение порта, дедупликация
// ---------------------------------------------------------------------------

describe('discoverPort', () => {
  it('возвращает текущий порт, если он жив, и не сканирует остальные', async () => {
    mockFetchSet(8081, { status: 200, json: { version: '1.0.0' } });
    const result = await discoverPort();
    assert.equal(result, 8081);
    // Сделан ровно один запрос — к текущему порту, сканирование не запускалось
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCountForPort(8081), 1);
  });

  it('находит новый порт, обновляет API_BASE и сохраняет порт в storage', async () => {
    mockFetchSet(8087, { status: 200, json: { version: '1.0.0' } });
    const result = await discoverPort();
    assert.equal(result, 8087);
    assert.equal(extractPortFromBase(API_BASE), 8087);
    assert.equal(localData.apiPort, 8087);
  });

  it('возвращает текущий порт и не меняет API_BASE, если бэкенд не найден', async () => {
    const result = await discoverPort();
    assert.equal(result, 8081);
    assert.equal(extractPortFromBase(API_BASE), 8081);
    // Ничего не найдено — порт не сохраняется в storage
    assert.equal(localData.apiPort, undefined);
  });

  it('дедуплицирует параллельные вызовы: повторный вызов не запускает сканирование', async () => {
    mockFetchSet(8087, { status: 200, json: { version: '1.0.0' } });
    // Два вызова без await между ними — второй должен вернуть тот же Promise
    const first = discoverPort();
    const second = discoverPort();
    const [r1, r2] = await Promise.all([first, second]);
    assert.equal(r1, r2);
    assert.equal(r1, 8087);
    // 1 запрос к текущему порту (8081, мёртв) + 10 запросов сканирования
    assert.equal(fetchCalls.length, 11);
  });
});
