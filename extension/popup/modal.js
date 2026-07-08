/**
 * @fileoverview
 * Управление модальными окнами.
 * Единственная ответственность: show/hide модалок.
 */

/**
 * Показывает модальное окно по его ID, скрывая все остальные.
 * @param {string} id — ID элемента модалки.
 */
export function showModal(id) {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

/** Скрывает все модальные окна. */
export function closeModal() {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
}
