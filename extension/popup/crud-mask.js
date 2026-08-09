/**
 * @fileoverview
 * CRUD-операции с масками (добавить, удалить, очистить, редактировать).
 * Использует config-based API: GET /api/config → modify → POST /api/config.
 */

import { apiPatch, apiPost, apiDelete } from '../shared/api.js';
import { convertWildcardToRegex, setLoading } from '../shared/utils.js';
import { showModal, closeModal } from './modal.js';
import { showToast } from './popup.js';
import { t } from '../shared/i18n.js';

/**
 * Открывает модальное окно добавления маски.
 * @param {object} state — глобальное состояние (нужен state.selectedProxyId).
 */
export function openAddMaskModal(state) {
  openMaskModal(state);
}

/**
 * Открывает модальное окно редактирования маски.
 * @param {object} state — глобальное состояние.
 * @param {object} mask — существующая маска.
 */
export function openEditMaskModal(state, mask) {
  openMaskModal(state, mask);
}

/**
 * Открывает модальное окно маски (добавление или редактирование).
 * @param {object} state — глобальное состояние.
 * @param {object|null} [existingMask=null] — если задан, режим редактирования.
 */
function openMaskModal(state, existingMask) {
  const title = document.getElementById('modal-mask-title');
  title.textContent = existingMask ? t('editMaskTitle') : t('addMaskTitle');
  document.getElementById('mask-pattern').value = existingMask ? existingMask.pattern : '';
  document.getElementById('mask-id').value = existingMask ? existingMask.maskId : '';
  document.getElementById('mask-error').classList.add('hidden');
  showModal('modal-mask');
}

/**
 * Сохраняет маску (создаёт или редактирует) через config-based API.
 *
 * Валидация конфликтов масок выполняется на сервере (HTTP 422):
 * в группе конфликтующих прокси может быть включён только один.
 * Ошибка сервера выводится в #mask-error.
 * @param {object} state — глобальное состояние (нужен state.selectedProxyId).
 * @param {Function} loadAndRender — функция перезагрузки всех данных.
 */
export async function handleSaveMask(state, loadAndRender) {
  const pattern = document.getElementById('mask-pattern').value.trim();
  const maskId = document.getElementById('mask-id').value;
  const errorEl = document.getElementById('mask-error');
  const saveBtn = document.getElementById('btn-mask-save');

  if (!pattern) {
    errorEl.textContent = t('enterMaskPattern');
    errorEl.classList.remove('hidden');
    return;
  }

  if (!state.selectedProxyId) {
    errorEl.textContent = t('noProxySelected');
    errorEl.classList.remove('hidden');
    return;
  }

  setLoading(saveBtn, true);
  try {
    const regexString = convertWildcardToRegex(pattern);

    if (maskId) {
      // Редактирование существующей маски — точечный PATCH
      await apiPatch(`/mask/${encodeURIComponent(maskId)}`, { pattern, regexString });
    } else {
      // Новая маска — точечный POST
      await apiPost('/masks', { pattern, regexString, proxyId: state.selectedProxyId });
    }
    // Форма очищается при следующем открытии в openMaskModal,
    // здесь не сбрасываем — иначе пользователь увидит пустой инпут
    // до переключения на список масок.
    await loadAndRender();
    showModal('modal-masks');
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка сохранения маски:', e);
    // Типизированная ошибка (ApiError.kind) или обратная совместимость
    const isNetworkError = e.kind === 'network' || e.kind === 'timeout'
      || e.message.startsWith('NETWORK:') || e.message.startsWith('TIMEOUT:')
      || e.message.includes('Failed to fetch');
    const msg = isNetworkError
      ? t('backendUnreachable')
      : e.message;
    errorEl.textContent = msg;
    errorEl.classList.remove('hidden');
  } finally {
    setLoading(saveBtn, false);
  }
}

/**
 * Удаляет маску по ID.
 * @param {string} maskId
 * @param {Function} loadAndRender
 * @param {HTMLElement} btn — кнопка удаления (для спиннера).
 */
export async function handleDeleteMask(maskId, loadAndRender, btn) {
  setLoading(btn, true);
  try {
    await apiDelete(`/mask/${encodeURIComponent(maskId)}`);
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка удаления маски:', e);
    showToast(t('deleteMaskFailed'), 'error');
  } finally {
    setLoading(btn, false);
  }
}

/**
 * Очищает все маски через API.
 * @param {Function} loadAndRender
 */
export async function handleClearMasks(loadAndRender) {
  const btn = document.getElementById('btn-clear-masks');
  setLoading(btn, true);
  try {
    const config = await apiGet('/config');
    config.masks = [];
    await apiPost('/config', config);
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка очистки масок:', e);
    showToast(t('clearMasksFailed'), 'error');
  } finally {
    setLoading(btn, false);
  }
}