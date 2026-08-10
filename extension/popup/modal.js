/**
 * @fileoverview
 * Управление модальными окнами.
 * Единственная ответственность: show/hide модалок.
 */

import { clearDraft } from './draft.js';

/**
 * Показывает модальное окно по его ID, скрывая все остальные.
 * @param {string} id — ID элемента модалки.
 */
export function showModal(id) {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
  const el = document.getElementById(id);
  if (!el) {
    console.warn('[FlowLink Proxy] Модальное окно не найдено:', id);
    return;
  }
  el.classList.remove('hidden');
}

/** Скрывает все модальные окна. */
export function closeModal() {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
  // Закрытие модалки = осознанное завершение редактирования, черновик стираем
  clearDraft().catch(e => console.warn('[FlowLink Proxy] modal: ошибка очистки черновика:', e));
}

/**
 * Привязывает обработчик клика по overlay для закрытия модалок.
 * Должен быть вызван один раз при инициализации.
 */
export function attachModalOverlayClose() {
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        // Сброс selectedProxyId при закрытии modal-masks
        const masksModal = document.getElementById('modal-masks');
        if (masksModal && !masksModal.classList.contains('hidden')) {
          if (window.__flowlinkResetSelectedProxy) {
            window.__flowlinkResetSelectedProxy();
          }
        }
        closeModal();
      }
    });
  });
}
