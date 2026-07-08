/**
 * @fileoverview
 * Утилиты общего назначения.
 * Единственная ответственность: вспомогательные функции без состояния.
 */

// Regex для проверки IPv4-адреса (четыре октета 0-255)
const IP_REGEX = /^(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})$/;

/**
 * Проверяет, является ли строка корректным IPv4-адресом.
 * @param {string} ip
 * @returns {boolean}
 */
export function isValidIP(ip) {
  return IP_REGEX.test(ip);
}

/**
 * Проверяет, является ли число корректным портом (1–65535).
 * @param {number} port
 * @returns {boolean}
 */
export function isValidPort(port) {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

/**
 * Сравнивает две semver-строки ('1.2.3' и '1.10.0').
 * @param {string} a
 * @param {string} b
 * @returns {number} — 1 если a > b, -1 если a < b, 0 если равны.
 */
export function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na > nb) return 1;
    if (na < nb) return -1;
  }
  return 0;
}

/**
 * Устанавливает/снимает состояние загрузки на кнопке.
 * @param {HTMLElement} btnEl — элемент кнопки.
 * @param {boolean} loading — true для блокировки, false для разблокировки.
 */
export function setLoading(btnEl, loading) {
  if (loading) {
    btnEl.classList.add('btn-loading');
    btnEl.disabled = true;
  } else {
    btnEl.classList.remove('btn-loading');
    btnEl.disabled = false;
  }
}

/**
 * Конвертирует wildcard-паттерн (*, ?) в regex-строку.
 * @param {string} pattern — wildcard (например '*.example.com').
 * @returns {string} — эквивалентный regex ('.*\\.example\\.com').
 */
export function convertWildcardToRegex(pattern) {
  let chars = pattern.split('');
  let escaped = '';
  for (let i = 0; i < chars.length; i++) {
    const c = chars[i];
    if ('*?.+^${}()|[]\\'.includes(c)) {
      if (c === '*') {
        escaped += '.*';
      } else if (c === '?') {
        escaped += '.';
      } else {
        escaped += '\\' + c;
      }
    } else {
      escaped += c;
    }
  }
  return escaped;
}
