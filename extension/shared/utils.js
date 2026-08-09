/**
 * @fileoverview
 * Утилиты общего назначения.
 * Единственная ответственность: вспомогательные функции без состояния.
 */

import { t } from './i18n.js';

// Regex для проверки IPv4-адреса (четыре октета 0-255)
const IP_REGEX = /^(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})$/;

// Regex для проверки IPv6-адреса (полная и сжатая форма, без zone-id)
const IPV6_REGEX = /^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^(?:[0-9a-fA-F]{1,4}:){1,7}:$|^(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$|^(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}$|^(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}$|^(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}$|^(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}$|^[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}$|^:(?::[0-9a-fA-F]{1,4}){1,7}$|^::$/;

// Regex для проверки hostname (доменное имя): буквы, цифры, дефисы, точки.
// Сегменты не начинаются/не заканчиваются дефисом, длина сегмента 1-63.
const HOSTNAME_REGEX = /^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$/;

/**
 * Проверяет, является ли строка корректным IPv4-адресом.
 * @param {string} ip
 * @returns {boolean}
 */
export function isValidIP(ip) {
  return IP_REGEX.test(ip);
}

/**
 * Проверяет, является ли строка корректным хостом для прокси:
 * IPv4, IPv6 или доменное имя (hostname).
 * @param {string} host
 * @returns {boolean}
 */
export function isValidHost(host) {
  if (typeof host !== 'string' || host.length === 0 || host.length > 253) {
    return false;
  }
  // IPv4
  if (IP_REGEX.test(host)) return true;
  // IPv6 (без квадратных скобок)
  if (IPV6_REGEX.test(host)) return true;
  // Доменное имя
  return HOSTNAME_REGEX.test(host);
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
  if (typeof a !== 'string' || typeof b !== 'string') {
    console.warn('[FlowLink Proxy] compareVersions: неверный тип аргумента', { a, b });
    return 0;
  }
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
  if (!btnEl) return;
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
  if (typeof pattern !== 'string') return '';
  // Ограничиваем длину паттерна 255 символами для предотвращения ReDoS
  const truncated = pattern.slice(0, 255);
  // Схлопываем повторяющиеся звёздочки в одну
  const collapsed = truncated.replace(/\*{2,}/g, '*');
  let chars = collapsed.split('');
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

/**
 * Копирует email в буфер обмена и показывает toast-уведомление.
 * @param {string} email — адрес для копирования.
 * @param {function} [showToastFn] — функция показа toast (если не передана — без уведомления).
 */
export function copyEmailToClipboard(email, showToastFn) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(email)
      .then(() => { if (showToastFn) showToastFn(t('emailCopied', { email })); })
      .catch((err) => {
        console.warn('[FlowLink Proxy] Ошибка копирования в буфер обмена:', err);
        if (showToastFn) showToastFn(t('copyFailed', { email }));
      });
  } else if (showToastFn) {
    showToastFn(t('selectManually', { email }));
  }
}