/**
 * @fileoverview
 * DOM-утилиты: экранирование, работа с элементами.
 * Единственная ответственность: вспомогательные функции для работы с DOM.
 */

/**
 * Экранирует HTML-спецсимволы в строке (XSS-безопасность).
 * @param {string} str — исходная строка.
 * @returns {string} — строка с экранированными < > & " '.
 */
export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
