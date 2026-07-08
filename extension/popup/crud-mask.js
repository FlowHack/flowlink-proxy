/**
 * @fileoverview
 * CRUD-операции с масками (добавить, удалить, очистить).
 * Использует config-based API: GET /api/config → modify → POST /api/config.
 */

import { apiGet, apiPost } from '../shared/api.js';
import { convertWildcardToRegex, setLoading } from '../shared/utils.js';
import { showModal, closeModal } from './modal.js';

/**
 * Открывает модальное окно добавления маски.
 * @param {object} state — глобальное состояние (state.proxies для выпадающего списка).
 */
export function openAddMaskModal(state) {
  openMaskModal(state);
}

/**
 * Открывает модальное окно маски (добавление).
 * @param {object} state — глобальное состояние.
 * @param {object|null} [existingMask=null] — если задан, режим редактирования.
 */
function openMaskModal(state, existingMask) {
  const select = document.getElementById('mask-proxy');
  select.innerHTML = state.proxies.map(p =>
    `<option value="${p.proxyId}" ${existingMask && existingMask.proxyId === p.proxyId ? 'selected' : ''}>${p.host}:${p.port}</option>`
  ).join('');
  document.getElementById('mask-pattern').value = existingMask ? existingMask.pattern : '';
  document.getElementById('mask-id').value = existingMask ? existingMask.maskId : '';
  document.getElementById('mask-error').classList.add('hidden');
  showModal('modal-mask');
}

/**
 * Проверяет пересечение паттернов: один pattern является подстрокой другого после удаления *.
 * @param {string} pattern — новый паттерн.
 * @param {Array} existingMasks — существующие маски.
 * @returns {string|null} — сообщение об ошибке или null.
 */
function checkMaskOverlap(pattern, existingMasks) {
  const normalized = pattern.replace(/\*/g, '').toLowerCase();
  for (const m of existingMasks) {
    const existing = m.pattern.replace(/\*/g, '').toLowerCase();
    if (normalized.includes(existing) || existing.includes(normalized)) {
      return `Маска пересекается с существующей: ${m.pattern}`;
    }
  }
  return null;
}

/**
 * Сохраняет маску (создаёт) через config-based API.
 * @param {Function} loadAndRender — функция перезагрузки всех данных.
 */
export async function handleSaveMask(loadAndRender) {
  const pattern = document.getElementById('mask-pattern').value.trim();
  const proxyId = document.getElementById('mask-proxy').value;
  const errorEl = document.getElementById('mask-error');
  const saveBtn = document.getElementById('btn-mask-save');

  if (!pattern) {
    errorEl.textContent = 'Введите паттерн маски';
    errorEl.classList.remove('hidden');
    return;
  }

  setLoading(saveBtn, true);
  try {
    const config = await apiGet('/config');
    const masks = config.masks || [];

    // Проверка пересечения масок
    const overlap = checkMaskOverlap(pattern, masks);
    if (overlap) {
      errorEl.textContent = overlap;
      errorEl.classList.remove('hidden');
      setLoading(saveBtn, false);
      return;
    }

    const regexString = convertWildcardToRegex(pattern);
    masks.push({ maskId: crypto.randomUUID(), pattern, regexString, proxyId });
    config.masks = masks;
    await apiPost('/config', config);
    closeModal();
    await loadAndRender();
  } catch (e) {
    errorEl.textContent = e.message;
    errorEl.classList.remove('hidden');
  } finally {
    setLoading(saveBtn, false);
  }
}

/**
 * Удаляет маску по ID.
 * @param {string} maskId
 * @param {Function} loadAndRender
 */
export async function handleDeleteMask(maskId, loadAndRender) {
  try {
    const config = await apiGet('/config');
    config.masks = (config.masks || []).filter(m => m.maskId !== maskId);
    await apiPost('/config', config);
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink] Ошибка удаления маски:', e);
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
    console.error('[FlowLink] Ошибка очистки масок:', e);
  } finally {
    setLoading(btn, false);
  }
}
