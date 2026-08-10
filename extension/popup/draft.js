/**
 * @fileoverview
 * Управление черновиками форм (сохранение и восстановление состояния).
 * Использует chrome.storage.session для временного хранения данных.
 */

import { debounce } from '../shared/utils.js';
import { showModal } from './modal.js';
import { t } from '../shared/i18n.js';

/**
 * Множество полей, которые были изменены пользователем (для отслеживания touched-полей).
 * @type {Set<string>}
 */
let _touchedFields = new Set();

/**
 * Флаг успешного восстановления черновика: предотвращает повторное
 * применение после оживления бэкенда (см. restoreUiDraft).
 * @type {boolean}
 */
let _draftRestored = false;

/**
 * Маппинг DOM-id полей на короткие ключи для черновика.
 * @type {Object<string, string>}
 */
export const DRAFT_FIELD_KEYS = {
  'proxy-host': 'host',
  'proxy-port': 'port',
  'proxy-username': 'username',
  'proxy-password': 'password',
  'proxy-label': 'label',
  'mask-pattern': 'pattern',
};

/**
 * Ключи полей формы прокси (для фильтрации touched-полей).
 * @type {Set<string>}
 */
const PROXY_FIELDS = new Set(['host', 'port', 'username', 'password', 'label']);

/**
 * Ключи полей формы маски (для фильтрации touched-полей).
 * @type {Set<string>}
 */
const MASK_FIELDS = new Set(['pattern']);

/**
 * Сбрасывает множество изменённых полей.
 */
export function resetTouchedFields() {
  _touchedFields.clear();
}

/**
 * Схема черновика.
 * @typedef {Object} UiDraft
 * @property {number} version — версия схемы (1).
 * @property {'modal-proxy'|'modal-mask'} openModal — ID активной модалки.
 * @property {string|null} selectedProxyId — выбранный прокси для масок.
 * @property {Object} proxy — данные формы прокси.
 * @property {string} proxy.id — ID прокси (пустая строка для нового).
 * @property {string[]} proxy.touched — список изменённых полей.
 * @property {Object} proxy.values — значения полей (только для touched).
 * @property {boolean} proxy.passwordVisible — видимость пароля.
 * @property {Object} mask — данные формы маски.
 * @property {string} mask.id — ID маски (пустая строка для новой).
 * @property {string[]} mask.touched — список изменённых полей.
 * @property {Object} mask.values — значения полей (только для touched).
 */

/**
 * Читает черновик из chrome.storage.session.
 * @returns {Promise<UiDraft|null>} — черновик или null, если не найден или невалиден.
 */
export async function getDraft() {
  try {
    const result = await chrome.storage.session.get('uiDraft');
    const draft = result.uiDraft;
    if (!draft) {
      return null;
    }
    if (!isDraftValid(draft)) {
      await chrome.storage.session.remove('uiDraft');
      return null;
    }
    return draft;
  } catch (e) {
    console.warn('[FlowLink Proxy] draft: не удалось прочитать черновик из storage:', e);
    return null;
  }
}

/**
 * Проверяет валидность черновика.
 * @param {UiDraft} draft — черновик для проверки.
 * @returns {boolean} — true, если черновик валиден.
 */
export function isDraftValid(draft) {
  if (!draft || draft.version !== 1) {
    return false;
  }
  if (draft.openModal !== 'modal-proxy' && draft.openModal !== 'modal-mask') {
    return false;
  }
  if (draft.openModal === 'modal-proxy' && (!draft.proxy || typeof draft.proxy !== 'object')) {
    return false;
  }
  if (draft.openModal === 'modal-mask' && (!draft.mask || typeof draft.mask !== 'object')) {
    return false;
  }
  if (draft.proxy) {
    if (!Array.isArray(draft.proxy.touched) || typeof draft.proxy.values !== 'object') {
      return false;
    }
  }
  if (draft.mask) {
    if (!Array.isArray(draft.mask.touched) || typeof draft.mask.values !== 'object') {
      return false;
    }
  }
  return true;
}

/**
 * Удаляет черновик из chrome.storage.session.
 * @returns {Promise<void>}
 */
export async function clearDraft() {
  try {
    await chrome.storage.session.remove('uiDraft');
  } catch (e) {
    console.warn('[FlowLink Proxy] draft: не удалось удалить черновик из storage:', e);
  } finally {
    resetTouchedFields();
  }
}

/**
 * Сохраняет черновик в chrome.storage.session.
 * @param {UiDraft} draft — черновик для сохранения.
 * @returns {Promise<void>}
 */
export async function saveDraft(draft) {
  try {
    await chrome.storage.session.set({ uiDraft: draft });
  } catch (e) {
    console.warn('[FlowLink Proxy] draft: не удалось сохранить черновик в storage:', e);
  }
}

/**
 * Проверяет, подлежит ли черновик сохранению.
 * @param {UiDraft} draft — черновик для проверки.
 * @returns {boolean} — true, если черновик содержит значимые данные.
 */
export function isDraftEligible(draft) {
  if (!draft || draft.version !== 1) {
    return false;
  }
  const hasProxyData = draft.proxy && (draft.proxy.touched && draft.proxy.touched.length > 0 || draft.proxy.id !== '');
  const hasMaskData = draft.mask && (draft.mask.touched && draft.mask.touched.length > 0 || draft.mask.id !== '');
  return hasProxyData || hasMaskData;
}

/**
 * Собирает данные формы прокси в черновик.
 * @param {string|null} selectedProxyId — выбранный прокси для масок.
 * @returns {Object} — часть черновика для прокси.
 */
function captureProxyForm(selectedProxyId) {
  const proxyId = document.getElementById('proxy-id')?.value || '';
  const host = document.getElementById('proxy-host')?.value || '';
  const port = document.getElementById('proxy-port')?.value || '';
  const username = document.getElementById('proxy-username')?.value || '';
  const password = document.getElementById('proxy-password')?.value || '';
  const label = document.getElementById('proxy-label')?.value || '';
  const passwordVisible = document.getElementById('proxy-password')?.type === 'text';

  // Фильтруем touched по полям прокси-формы: общее множество
  // _touchedFields может содержать ключи полей маски (см. DRAFT_FIELD_KEYS)
  const touched = Array.from(_touchedFields).filter(f => PROXY_FIELDS.has(f));
  const values = {};
  if (touched.includes('host')) values.host = host;
  if (touched.includes('port')) values.port = port;
  if (touched.includes('username')) values.username = username;
  if (touched.includes('password')) values.password = password;
  if (touched.includes('label')) values.label = label;

  return {
    id: proxyId,
    touched,
    values,
    passwordVisible,
  };
}

/**
 * Собирает данные формы маски в черновик.
 * @returns {Object} — часть черновика для маски.
 */
function captureMaskForm() {
  const maskId = document.getElementById('mask-id')?.value || '';
  const pattern = document.getElementById('mask-pattern')?.value || '';

  // Фильтруем touched по полям маски: общее множество _touchedFields
  // может содержать ключи полей прокси-формы (см. DRAFT_FIELD_KEYS)
  const touched = Array.from(_touchedFields).filter(f => MASK_FIELDS.has(f));
  const values = {};
  if (touched.includes('pattern')) values.pattern = pattern;

  return {
    id: maskId,
    touched,
    values,
  };
}

/**
 * Собирает черновик для формы прокси.
 * @param {string|null} selectedProxyId — выбранный прокси для масок.
 * @returns {UiDraft} — черновик.
 */
export function captureProxyDraft(selectedProxyId) {
  const proxy = captureProxyForm(selectedProxyId);
  return {
    version: 1,
    openModal: 'modal-proxy',
    selectedProxyId,
    proxy,
    mask: { id: '', touched: [], values: {} },
  };
}

/**
 * Собирает черновик для формы маски.
 * @param {string|null} selectedProxyId — выбранный прокси для масок.
 * @returns {UiDraft} — черновик.
 */
export function captureMaskDraft(selectedProxyId) {
  const mask = captureMaskForm();
  return {
    version: 1,
    openModal: 'modal-mask',
    selectedProxyId,
    proxy: { id: '', touched: [], values: {} },
    mask,
  };
}

/**
 * Восстанавливает форму прокси из черновика.
 * @param {Object} state — глобальное состояние.
 * @param {UiDraft} draft — черновик.
 * @returns {boolean} — true, если восстановление успешно.
 */
export function applyProxyDraft(state, draft) {
  const proxyId = draft.proxy.id;
  const proxy = proxyId ? state.proxies.find(p => p.proxyId === proxyId) : null;

  if (proxyId && !proxy) {
    return false;
  }

  const form = document.getElementById('proxy-form');
  if (!form) {
    return false;
  }

  const title = document.getElementById('modal-proxy-title');
  if (title) {
    title.textContent = proxyId ? t('editProxyTitle') : t('addProxyTitle');
  }

  if (proxyId) {
    document.getElementById('proxy-id').value = proxyId;
    document.getElementById('proxy-host').value = proxy.host;
    document.getElementById('proxy-port').value = proxy.port;
    document.getElementById('proxy-username').value = proxy.username || '';
    document.getElementById('proxy-password').value = proxy.password || '';
    document.getElementById('proxy-label').value = proxy.label || '';
  } else {
    document.getElementById('proxy-id').value = '';
    document.getElementById('proxy-host').value = '';
    document.getElementById('proxy-port').value = '';
    document.getElementById('proxy-username').value = '';
    document.getElementById('proxy-password').value = '';
    document.getElementById('proxy-label').value = '';
  }

  const touched = draft.proxy.touched || [];
  const values = draft.proxy.values || {};
  if (touched.includes('host') && values.host !== undefined) {
    document.getElementById('proxy-host').value = values.host;
  }
  if (touched.includes('port') && values.port !== undefined) {
    document.getElementById('proxy-port').value = values.port;
  }
  if (touched.includes('username') && values.username !== undefined) {
    document.getElementById('proxy-username').value = values.username;
  }
  if (touched.includes('password') && values.password !== undefined) {
    document.getElementById('proxy-password').value = values.password;
  }
  if (touched.includes('label') && values.label !== undefined) {
    document.getElementById('proxy-label').value = values.label;
  }

  const passwordVisible = draft.proxy.passwordVisible || false;
  const passwordInput = document.getElementById('proxy-password');
  const passwordToggle = document.getElementById('btn-password-toggle');
  if (passwordInput && passwordToggle) {
    passwordInput.type = passwordVisible ? 'text' : 'password';
    passwordToggle.title = passwordVisible ? t('hidePassword') : t('showPassword');
    const eyeClosed = passwordToggle.querySelector('.eye-closed');
    const eyeOpen = passwordToggle.querySelector('.eye-open');
    if (eyeClosed && eyeOpen) {
      eyeClosed.classList.toggle('hidden', passwordVisible);
      eyeOpen.classList.toggle('hidden', !passwordVisible);
    }
  }

  showModal('modal-proxy');
  return true;
}

/**
 * Восстанавливает форму маски из черновика.
 * @param {Object} state — глобальное состояние.
 * @param {UiDraft} draft — черновик.
 * @returns {boolean} — true, если восстановление успешно.
 */
export function applyMaskDraft(state, draft) {
  const selectedProxyId = draft.selectedProxyId;
  const proxyExists = selectedProxyId ? state.proxies.some(p => p.proxyId === selectedProxyId) : false;

  if (selectedProxyId && !proxyExists) {
    return false;
  }

  const maskId = draft.mask.id;
  const mask = maskId ? state.masks.find(m => m.maskId === maskId) : null;

  if (maskId && !mask) {
    return false;
  }

  if (maskId && mask.proxyId !== selectedProxyId) {
    return false;
  }

  const form = document.getElementById('mask-form');
  if (!form) {
    return false;
  }

  const title = document.getElementById('modal-mask-title');
  if (title) {
    title.textContent = maskId ? t('editMaskTitle') : t('addMaskTitle');
  }

  if (maskId) {
    document.getElementById('mask-id').value = maskId;
    document.getElementById('mask-pattern').value = mask.pattern;
  } else {
    document.getElementById('mask-id').value = '';
    document.getElementById('mask-pattern').value = '';
  }

  const touched = draft.mask.touched || [];
  const values = draft.mask.values || {};
  if (touched.includes('pattern') && values.pattern !== undefined) {
    document.getElementById('mask-pattern').value = values.pattern;
  }

  showModal('modal-mask');
  return true;
}

/**
 * Восстанавливает UI из черновика.
 * @param {Object} state — глобальное состояние.
 * @returns {Promise<void>}
 */
export async function restoreUiDraft(state) {
  const draft = await getDraft();
  if (!draft) {
    // Черновика нет (или он был невалиден и удалён) — восстанавливать нечего
    _draftRestored = true;
    return;
  }

  if (!state.connected) {
    return;
  }

  if (draft.openModal === 'modal-proxy') {
    const success = applyProxyDraft(state, draft);
    if (!success) {
      await clearDraft();
    }
  } else if (draft.openModal === 'modal-mask') {
    const success = applyMaskDraft(state, draft);
    if (!success) {
      await clearDraft();
    }
  } else {
    await clearDraft();
  }
  // Черновик применён или очищен — повторное восстановление не требуется
  _draftRestored = true;
}

/**
 * Возвращает true, если черновик уже был восстановлен (или отсутствовал).
 * @returns {boolean} — true, если повторное восстановление не требуется.
 */
export function isDraftRestored() {
  return _draftRestored;
}

/**
 * Сбрасывает флаг восстановления черновика.
 * Используется в тестах: в проде флаг живёт до перезагрузки popup.
 */
export function resetDraftRestored() {
  _draftRestored = false;
}

/**
 * Инициализирует автосохранение черновика.
 * @param {Object} state — глобальное состояние.
 */
export function initDraftAutoSave(state) {
  const debouncedSave = debounce(async () => {
    const activeModal = document.querySelector('.modal-overlay:not(.hidden)')?.id;
    if (!activeModal) {
      return;
    }

    let draft;
    if (activeModal === 'modal-proxy') {
      draft = captureProxyDraft(state.selectedProxyId);
    } else if (activeModal === 'modal-mask') {
      draft = captureMaskDraft(state.selectedProxyId);
    }

    if (draft && isDraftEligible(draft)) {
      await saveDraft(draft);
    } else {
      await clearDraft();
    }
  }, 150);

  document.addEventListener('input', (e) => {
    const input = e.target;
    if (!input.id) {
      return;
    }
    const key = DRAFT_FIELD_KEYS[input.id];
    if (!key) {
      return;
    }
    _touchedFields.add(key);
    debouncedSave();
  });

  const flushDraft = async () => {
    const activeModal = document.querySelector('.modal-overlay:not(.hidden)')?.id;
    if (!activeModal) {
      return;
    }

    let draft;
    if (activeModal === 'modal-proxy') {
      draft = captureProxyDraft(state.selectedProxyId);
    } else if (activeModal === 'modal-mask') {
      draft = captureMaskDraft(state.selectedProxyId);
    }

    if (draft && isDraftEligible(draft)) {
      await saveDraft(draft);
    }
  };

  window.addEventListener('pagehide', flushDraft);
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState === 'hidden') {
      await flushDraft();
    }
  });
}
