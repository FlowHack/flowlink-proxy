/**
 * @fileoverview
 * DOM-утилиты: экранирование, работа с элементами.
 * Единственная ответственность: вспомогательные функции для работы с DOM.
 */

/**
 * Экранирует HTML-спецсимволы в строке (XSS-безопасность).
 * @param {string|number|null|undefined} str — исходная строка (или любой тип).
 * @returns {string} — строка с экранированными < > & " '.
 */
export function escapeHtml(str) {
  if (str == null) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}
