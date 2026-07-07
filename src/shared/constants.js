/**
 * @fileoverview
 * Константы и вспомогательные функции общего назначения для FlowLink Proxy.
 * Ключи хранилища, генератор UUID, валидаторы порта и IP-адреса.
 */

/**
 * Ключи для chrome.storage.local, используемые во всём расширении.
 * @enum {string}
 */
const STORAGE_KEYS = Object.freeze({
  MASTER_KEY: 'flowlink_masterKey',
  PROXY_TABLE: 'flowlink_proxyTable',
  MASK_TABLE: 'flowlink_maskTable',
  EXTENSION_STATUS: 'flowlink_extensionEnabled'
});

/**
 * Генерирует уникальный идентификатор (UUID v4) для прокси или маски.
 * @returns {string} UUID-строка.
 */
function generateId() {
  return crypto.randomUUID();
}

/**
 * Проверяет, что значение является корректным номером порта (1–65535).
 * @param {*} port - Проверяемое значение.
 * @returns {boolean} true, если порт корректен.
 */
function isValidPort(port) {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

/**
 * Регулярное выражение для валидации IPv4-адреса.
 * Совпадает с маской из ТЗ: 0.0.0.0 – 255.255.255.255.
 */
const IP_REGEX = /^(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})$/;

/**
 * Проверяет, является ли строка корректным IPv4-адресом.
 * @param {string} ip - Строка IP-адреса для проверки.
 * @returns {boolean} true, если IP корректен.
 */
function isValidIP(ip) {
  return IP_REGEX.test(ip);
}

/**
 * Преобразует IDN-домены (с кириллицей и другими не-ASCII символами)
 * в Punycode-формат внутри строки регулярного выражения маски.
 * Например: ".*\\.сайт\\.рф" → ".*\\.xn--80aswg\\.xn--p1ai"
 *
 * Алгоритм:
 * 1. Заменяет экранированные точки (\\.) на маркер, чтобы не разбить escape-последовательность
 * 2. Разбивает остаток по реальным точкам
 * 3. Каждый сегмент с не-ASCII символами пытается преобразовать через new URL()
 * 4. Собирает результат обратно
 *
 * @param {string} mask - Строка регулярного выражения маски.
 * @returns {string} Маска с Punycode-преобразованными IDN-доменами.
 */
function convertMaskIdn(mask) {
  /* Если нет не-ASCII символов — возврат без изменений */
  if (!/[^\x20-\x7E]/.test(mask)) return mask;

  try {
    /* Маркер для экранированных точек */
    const ED = '\x00ED\x00';
    const withMarkers = mask.replace(/\\\./g, ED);

    /* Разбиваем по незаэкранированным точкам */
    const parts = withMarkers.split('.');
    const converted = parts.map(part => {
      /* Если нет не-ASCII — пропускаем */
      if (!/[^\x20-\x7E]/.test(part)) return part;

      try {
        /* Пытаемся декодировать как IDN-метку */
        const url = new URL('http://' + part);
        return url.hostname;
      } catch {
        /* Не удалось — оставляем как есть */
        return part;
      }
    });

    /* Склеиваем обратно и восстанавливаем экранированные точки */
    return converted.join('.').split(ED).join('\\.');
  } catch {
    /* Любая ошибка парсинга — возвращаем исходную маску */
    return mask;
  }
}

export { STORAGE_KEYS, generateId, isValidPort, isValidIP, convertMaskIdn };
