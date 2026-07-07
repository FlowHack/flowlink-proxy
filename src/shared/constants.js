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

export { STORAGE_KEYS, generateId, isValidPort, isValidIP };
