/**
 * @fileoverview
 * CRUD-операции с масками (добавить, удалить, очистить, редактировать).
 * Использует config-based API: GET /api/config → modify → POST /api/config.
 */

import { apiGet, apiPost } from '../shared/api.js';
import { convertWildcardToRegex, setLoading } from '../shared/utils.js';
import { showModal, closeModal } from './modal.js';
import { showToast } from './popup.js';

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
  title.textContent = existingMask ? 'Редактировать маску' : 'Добавить маску';
  document.getElementById('mask-pattern').value = existingMask ? existingMask.pattern : '';
  document.getElementById('mask-id').value = existingMask ? existingMask.maskId : '';
  document.getElementById('mask-error').classList.add('hidden');
  showModal('modal-mask');
}

/**
 * Проверяет пересечение паттернов масок.
 *
 * Двухуровневая проверка:
 * 1. Substring — после удаления `*` один паттерн содержит другой (быстро, ловит ~90%).
 * 2. Сегментная — разбивает паттерны на не-wildcard сегменты по `*` и проверяет
 *    каждый сегмент длиной >= 3 символов на вхождение в сегменты другого паттерна.
 *    Ловит случаи вроде `*.example.com` vs `example.com/*`.
 *
 * @param {string} pattern — новый паттерн.
 * @param {Array} existingMasks — существующие маски.
 * @param {string|null} excludeMaskId — ID маски для исключения (при редактировании).
 * @returns {string|null} — сообщение об ошибке или null.
 */
function checkMaskOverlap(pattern, existingMasks, excludeMaskId) {
  const normalized = pattern.replace(/\*/g, '').toLowerCase();
  const segments = pattern.split('*').filter(Boolean);

  for (const m of existingMasks) {
    if (m.maskId === excludeMaskId) continue;

    // Уровень 1: substring-проверка
    const existing = m.pattern.replace(/\*/g, '').toLowerCase();
    if (normalized.includes(existing) || existing.includes(normalized)) {
      return `Маска пересекается с существующей: ${m.pattern}`;
    }

    // Уровень 2: сегментная проверка (сегменты от 3+ символов)
    const existingSegments = m.pattern.split('*').filter(Boolean);
    for (const seg of segments) {
      if (seg.length < 3) continue;
      for (const es of existingSegments) {
        if (es.length < 3) continue;
        if (seg.includes(es) || es.includes(seg)) {
          return `Маска пересекается с существующей: ${m.pattern}`;
        }
      }
    }
  }
  return null;
}

/**
 * Сохраняет маску (создаёт или редактирует) через config-based API.
 * @param {object} state — глобальное состояние (нужен state.selectedProxyId).
 * @param {Function} loadAndRender — функция перезагрузки всех данных.
 */
export async function handleSaveMask(state, loadAndRender) {
  const pattern = document.getElementById('mask-pattern').value.trim();
  const maskId = document.getElementById('mask-id').value;
  const errorEl = document.getElementById('mask-error');
  const saveBtn = document.getElementById('btn-mask-save');

  if (!pattern) {
    errorEl.textContent = 'Введите паттерн маски';
    errorEl.classList.remove('hidden');
    return;
  }

  if (!state.selectedProxyId) {
    errorEl.textContent = 'Не выбран прокси для маски';
    errorEl.classList.remove('hidden');
    return;
  }

  setLoading(saveBtn, true);
  try {
    const config = await apiGet('/config');
    const masks = config.masks || [];

    // Проверка пересечения масок (исключаем редактируемую)
    const overlap = checkMaskOverlap(pattern, masks, maskId);
    if (overlap) {
      errorEl.textContent = overlap;
      errorEl.classList.remove('hidden');
      setLoading(saveBtn, false);
      return;
    }

    const regexString = convertWildcardToRegex(pattern);

    if (maskId) {
      // Редактирование существующей маски
      const idx = masks.findIndex(m => m.maskId === maskId);
      if (idx !== -1) {
        masks[idx] = { ...masks[idx], pattern, regexString };
      }
    } else {
      // Новая маска
      masks.push({ maskId: crypto.randomUUID(), pattern, regexString, proxyId: state.selectedProxyId });
    }

    config.masks = masks;
    await apiPost('/config', config);
    // Форма очищается при следующем открытии в openMaskModal,
    // здесь не сбрасываем — иначе пользователь увидит пустой инпут
    // до переключения на список масок.
    await loadAndRender();
    showModal('modal-masks');
  } catch (e) {
    const msg = e.message.includes('Failed to fetch') || e.message.includes('HTTP')
      ? 'Не удалось связаться с бэкендом. Проверьте, запущен ли FlowLink Proxy.'
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
    const config = await apiGet('/config');
    config.masks = (config.masks || []).filter(m => m.maskId !== maskId);
    await apiPost('/config', config);
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка удаления маски:', e);
    showToast('Не удалось удалить маску. Проверьте соединение с бэкендом.');
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
    showToast('Не удалось очистить маски. Проверьте соединение с бэкендом.');
  } finally {
    setLoading(btn, false);
  }
}
