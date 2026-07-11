/**
 * @fileoverview
 * Автообнаружение порта API-сервера бэкенда.
 * Единственная ответственность: поиск работающего бэкенда среди портов.
 *
 * Алгоритм:
 * 1. Проверить текущий (сохранённый) порт — если работает, вернуть его
 * 2. Сканировать порты 8080–8090 параллельно (таймаут 800мс на порт)
 * 3. Ничего не найдено → вернуть сохранённый (пусть ошибка покажется в UI)
 *
 * Безопасность:
 * - Запросы идут ТОЛЬКО на 127.0.0.1 (нет DNS-резолва, нет SSRF)
 * - Не используется тело ответа — только проверка status code
 * - Таймаут предотвращает зависание при недоступных портах
 */

import { API_BASE, setApiPort } from './constants.js';

/** Диапазон портов для сканирования (включительно). */
const SCAN_START = 8080;
const SCAN_END = 8090;

/** Таймаут одного запроса при сканировании (мс). */
const SCAN_TIMEOUT = 800;

/** Адрес для проверки портов (только localhost — нет риска SSRF). */
const PROBE_HOST = '127.0.0.1';

/** Префикс логов для идентификации в консоли. */
const LOG_PREFIX = '[FlowLink Proxy]';

/** Флаг предотвращения параллельного сканирования. */
let _isScanning = false;

/**
 * Проверяет, отвечает ли бэкенд на данном порту.
 *
 * Использует GET /api/version — лёгкий запрос, не нагружающий сервер.
 * Таймаут через AbortController предотвращает зависание на недоступных портах.
 *
 * @param {number} port — порт для проверки (1–65535).
 * @returns {Promise<boolean>} — true, если бэкенд доступен и вернул HTTP 200.
 */
async function isPortAlive(port) {
  // Валидация порта — не допускаем некорректные значения
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return false;
  }

  const ctrl = new AbortController();
  // Таймаут устанавливается ДО запроса и гарантированно очищается в finally
  const timer = setTimeout(() => ctrl.abort(), SCAN_TIMEOUT);

  try {
    const res = await fetch(`http://${PROBE_HOST}:${port}/api/version`, {
      signal: ctrl.signal,
    });
    return res.ok;
  } catch {
    // AbortError (таймаут), TypeError (сеть недоступна), любой другой — порт не жив
    return false;
  } finally {
    // ВСЕГДА очищаем таймер — даже при ошибке или AbortError.
    // Без finally: при exception таймер продолжает висеть до срабатывания,
    // а ctrl.abort() вызывается на уже завершённом контроллере (безвредно, но расточительно).
    clearTimeout(timer);
  }
}

/**
 * Сканирует диапазон портов и возвращает первый доступный.
 * Запросы выполняются параллельно для скорости (обычно < 1с на весь диапазон).
 *
 * @param {number} skipPort — порт, который уже проверен (пропускается, чтобы
 *   не делать дублирующий запрос).
 * @returns {Promise<number|null>} — найденный порт или null, если ни один не отвечает.
 */
async function scanPorts(skipPort) {
  const promises = [];
  for (let port = SCAN_START; port <= SCAN_END; port++) {
    if (port === skipPort) continue;
    promises.push(
      isPortAlive(port).then((alive) => (alive ? port : null)),
    );
  }
  const results = await Promise.all(promises);
  return results.find((p) => p !== null) ?? null;
}

/**
 * Обнаруживает порт API-сервера бэкенда.
 *
 * Порядок проверки:
 * 1. Сохранённый порт (из chrome.storage) — проверяется мгновенно
 * 2. Порты 8080–8090 — сканируются параллельно
 *
 * При нахождении нового порта — автоматически обновляет API_BASE
 * и сохраняет в chrome.storage для будущих запусков.
 *
 * Защита от параллельных вызовов: если сканирование уже идёт,
 * повторный вызов вернёт текущий порт без дублирования запросов.
 *
 * @returns {Promise<number>} — обнаруженный порт (сохранённый или новый).
 */
export async function discoverPort() {
  // Guard: если сканирование уже выполняется — не запускаем повторно
  if (_isScanning) {
    const currentPort = extractPortFromBase(API_BASE);
    console.log(
      `${LOG_PREFIX} Сканирование уже выполняется, повторный вызов пропущен`,
    );
    return currentPort;
  }

  _isScanning = true;
  const currentPort = extractPortFromBase(API_BASE);

  try {
    // Шаг 1: проверяем текущий порт — быстрая проверка (< 1с)
    if (await isPortAlive(currentPort)) {
      console.log(
        `${LOG_PREFIX} Текущий порт ${currentPort} доступен`,
      );
      return currentPort;
    }

    console.log(
      `${LOG_PREFIX} Порт ${currentPort} недоступен, сканирую порты ${SCAN_START}–${SCAN_END}...`,
    );

    // Шаг 2: сканируем диапазон параллельно
    const foundPort = await scanPorts(currentPort);
    if (foundPort !== null) {
      console.log(
        `${LOG_PREFIX} Найден бэкенд на порту ${foundPort}, подключаюсь`,
      );
      // setApiPort — безопасная операция (присваивание модуля), но на всякий случай
      try {
        setApiPort(foundPort);
      } catch (e) {
        console.error(
          `${LOG_PREFIX} Ошибка обновления порта API:`,
          e,
        );
      }
      // Сохраняем порт для будущих запусков popup
      try {
        await chrome.storage.local.set({ apiPort: foundPort });
      } catch (e) {
        // storage.local может быть недоступен в edge-кейсах — не критично
        console.warn(
          `${LOG_PREFIX} Не удалось сохранить порт ${foundPort} в storage:`,
          e,
        );
      }
      return foundPort;
    }

    // Ничего не найдено — логируем для отладки
    console.warn(
      `${LOG_PREFIX} Бэкенд не найден в диапазоне ${SCAN_START}–${SCAN_END}. ` +
      `Убедитесь, что бэкенд запущен.`,
    );
    return currentPort;
  } finally {
    _isScanning = false;
  }
}

/**
 * Извлекает номер порта из строки API_BASE.
 *
 * Использует стандартный URL-конструктор для надёжного парсинга.
 * Не бросает исключений — при любых ошибках возвращает порт по умолчанию.
 *
 * @param {string} baseUrl — например 'http://127.0.0.1:8091/api'.
 * @returns {number} — порт (например 8091) или 8081 по умолчанию.
 */
function extractPortFromBase(baseUrl) {
  try {
    const url = new URL(baseUrl);
    const port = parseInt(url.port, 10);
    // url.port — пустая строка для стандартных портов (80/443),
    // поэтому проверяем результат parseInt
    return (Number.isInteger(port) && port > 0 && port <= 65535) ? port : 8081;
  } catch {
    return 8081;
  }
}
