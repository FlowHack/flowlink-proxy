/**
 * @fileoverview
 * Контроллер Popup-интерфейса FlowLink Proxy.
 * Управляет отрисовкой списка прокси, модальными окнами,
 * валидацией форм и коммуникацией с Service Worker через сообщения.
 *
 * Запрещён прямой доступ к chrome.storage — только через MessageRouter.
 */

import { MESSAGES } from '../shared/messages.js';
import { isValidIP, isValidPort } from '../shared/constants.js';

/* ───── Состояние UI ───── */
let state = {
  proxies: [],
  pingResults: new Map(),   /* proxyId → { alive, latency } */
  editingProxyId: null,      /* ID прокси при редактировании */
  editingMaskId: null,       /* ID маски при редактировании */
  masksProxyId: null         /* ID прокси, чьи маски просматриваются */
};

/* ───── Утилиты ───── */

/**
 * Отправляет сообщение в Service Worker и возвращает результат.
 * @param {string} action
 * @param {*} [data]
 * @returns {Promise<*>}
 */
function sendMessage(action, data) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ action, data }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
      } else if (!response || !response.success) {
        reject(new Error(response?.error || 'Неизвестная ошибка'));
      } else {
        resolve(response.data);
      }
    });
  });
}

/* ───── Инициализация ───── */

document.addEventListener('DOMContentLoaded', async () => {
  await loadAndRender();
  attachGlobalListeners();
});

/** Флаг — true, если loadAndRender не смог загрузить данные */
let _loadFailed = false;

/**
 * Загружает все данные с сервис-воркера и рендерит UI.
 */
async function loadAndRender() {
  /** Каждый запрос обрабатываем отдельно — один отказ не ломает весь UI */
  let proxies = [];
  let extensionEnabled = true;
  let tabStatus = null;

  try {
    proxies = await sendMessage(MESSAGES.GET_ALL_PROXIES);
    state.proxies = proxies;
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка загрузки прокси:', error);
  }

  try {
    extensionEnabled = await sendMessage(MESSAGES.GET_EXTENSION_STATUS);
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка загрузки статуса:', error);
  }

  try {
    tabStatus = await sendMessage(MESSAGES.GET_CURRENT_TAB_STATUS);
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка загрузки статуса вкладки:', error);
  }

  renderVersion();
  renderGlobalToggle(extensionEnabled);
  renderStatusBar(tabStatus);
  renderProxyList(proxies);

  /* Показываем error-state только если не загрузилось ничего */
  const errorEl = document.getElementById('error-state');
  if (!proxies.length && !tabStatus) {
    _loadFailed = true;
    errorEl.classList.remove('hidden');
  } else {
    _loadFailed = false;
    errorEl.classList.add('hidden');
  }

  /* Авто-пинг при открытии popup (только если расширение включено) */
  if (extensionEnabled && proxies.length > 0) {
    handlePingAll();
  }
}

/* ───── Рендер ───── */

function renderVersion() {
  const el = document.getElementById('version-text');
  const manifest = chrome.runtime.getManifest();
  el.textContent = `Версия: ${manifest.version}`;
}

/**
 * Рендерит глобальный переключатель расширения.
 * @param {boolean} enabled
 */
function renderGlobalToggle(enabled) {
  const input = document.getElementById('global-toggle-input');
  input.checked = enabled;
}

/**
 * Рендерит статус-бар для текущей вкладки.
 * @param {{hasTab: boolean, status?: string, domain?: string}} tabStatus
 */
function renderStatusBar(tabStatus) {
  const bar = document.getElementById('status-bar');
  const icon = document.getElementById('status-icon');
  const text = document.getElementById('status-text');

  if (!tabStatus || !tabStatus.hasTab) {
    bar.classList.add('hidden');
    return;
  }

  bar.classList.remove('hidden');

  if (tabStatus.status === 'blocked') {
    icon.style.color = 'var(--accent-red)';
    text.textContent = `Заблокировано — ${tabStatus.domain || ''}`;
    text.style.color = 'var(--accent-red)';
  } else {
    icon.style.color = 'var(--accent-green)';
    text.textContent = 'Доступно';
    text.style.color = 'var(--accent-green)';
  }
}

/**
 * Рендерит список прокси.
 * @param {Array} proxies
 */
function renderProxyList(proxies) {
  const container = document.getElementById('proxy-list');

  if (!proxies || proxies.length === 0) {
    container.innerHTML = '<div class="empty-state">Нет добавленных прокси</div>';
    return;
  }

  const items = proxies.map(proxy => {
    const ping = state.pingResults.get(proxy.proxyId);
    const pingHtml = ping
      ? `<span class="proxy-ping ${ping.alive ? 'ping-ok' : 'ping-fail'}">${ping.alive ? ping.latency + 'мс' : 'н/д'}</span>`
      : '<span class="proxy-ping"></span>';

    return `
      <div class="proxy-item" data-proxy-id="${proxy.proxyId}">
        <label class="switch proxy-toggle" data-action="toggle" title="Вкл/Выкл прокси">
          <input type="checkbox" ${proxy.isEnabled ? 'checked' : ''}>
          <span class="slider"></span>
        </label>
        <button class="btn-icon edit-icon" data-action="edit" title="Редактировать">✏</button>
        <span class="proxy-ip" data-action="masks" title="Управление масками">${escapeHtml(proxy.host)}:${escapeHtml(String(proxy.port))}</span>
        ${pingHtml}
        <button class="btn-icon delete-icon" data-action="delete" title="Удалить">✕</button>
      </div>
    `;
  }).join('');

  container.innerHTML = items;

  /* Навешиваем обработчики на каждый элемент */
  container.querySelectorAll('.proxy-item').forEach(el => {
    const proxyId = el.dataset.proxyId;

    el.querySelector('[data-action="toggle"]')?.addEventListener('click', (e) => {
      e.stopPropagation();
      handleToggleProxy(proxyId, el);
    });

    el.querySelector('[data-action="edit"]')?.addEventListener('click', (e) => {
      e.stopPropagation();
      openEditProxyModal(proxyId);
    });

    el.querySelector('[data-action="delete"]')?.addEventListener('click', (e) => {
      e.stopPropagation();
      handleDeleteProxy(proxyId);
    });

    el.querySelector('[data-action="masks"]')?.addEventListener('click', () => {
      openMaskModal(proxyId);
    });
  });
}

/* ───── Глобальные обработчики ───── */

/**
 * Привязывает глобальные обработчики (кнопки, переключатели, модальные окна).
 */
function attachGlobalListeners() {
  /* Глобальный переключатель */
  document.getElementById('global-toggle-input').addEventListener('change', async (e) => {
    try {
      await sendMessage(MESSAGES.SET_EXTENSION_STATUS, { enabled: e.target.checked });
    } catch (error) {
      console.error('[FlowLink Proxy] Ошибка переключения расширения:', error);
      e.target.checked = !e.target.checked;
    }
  });

  /* Пинг всех */
  document.getElementById('btn-ping-all').addEventListener('click', handlePingAll);

  /* Повторная попытка загрузки */
  document.getElementById('btn-retry').addEventListener('click', async () => {
    const btn = document.getElementById('btn-retry');
    btn.disabled = true;
    btn.textContent = 'Загрузка...';
    await loadAndRender();
    btn.disabled = false;
    btn.textContent = 'Повторить';
  });

  /* Добавить прокси */
  document.getElementById('btn-add-proxy').addEventListener('click', () => openAddProxyModal());

  /* Модал прокси */
  document.getElementById('btn-proxy-cancel').addEventListener('click', closeModal);
  document.getElementById('btn-proxy-save').addEventListener('click', handleSaveProxy);

  /* Модал масок */
  document.getElementById('btn-masks-close').addEventListener('click', closeModal);
  document.getElementById('btn-add-mask').addEventListener('click', () => openAddMaskModal());
  document.getElementById('btn-clear-masks').addEventListener('click', handleClearMasks);

  /* Модал маски: Отмена → возврат к списку масок, а не на главный экран */
  document.getElementById('btn-mask-cancel').addEventListener('click', () => {
    document.getElementById('modal-mask').classList.add('hidden');
  });
  document.getElementById('btn-mask-save').addEventListener('click', handleSaveMask);

  /* Закрытие по Escape */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
}

/* ───── Пинг ───── */

async function handlePingAll() {
  const btn = document.getElementById('btn-ping-all');
  btn.disabled = true;
  btn.textContent = 'Проверка...';

  state.pingResults.clear();

  try {
    /* Каждый прокси тестируем последовательно через SW (который создаёт вкладку) */
    for (const p of state.proxies) {
      try {
        const r = await sendMessage(MESSAGES.PING_PROXY, { proxyId: p.proxyId });
        state.pingResults.set(r.proxyId, { alive: r.alive, latency: r.latency });
      } catch (pingError) {
        console.warn(`[FlowLink Proxy] Ошибка пинга прокси ${p.proxyId}:`, pingError);
        state.pingResults.set(p.proxyId, { alive: false, latency: null });
      }
    }

    renderProxyList(state.proxies);
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка пинга:', error);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Пинг всех';
  }
}

/* ───── Действия с прокси ───── */

/**
 * Переключает состояние прокси (вкл/выкл).
 * @param {string} proxyId
 * @param {HTMLElement} itemEl - Элемент .proxy-item
 */
async function handleToggleProxy(proxyId, itemEl) {
  const input = itemEl.querySelector('.proxy-toggle input');
  const newState = input.checked;

  try {
    await sendMessage(MESSAGES.TOGGLE_PROXY, { proxyId, isEnabled: newState });
    /* Обновляем локальное состояние */
    const proxy = state.proxies.find(p => p.proxyId === proxyId);
    if (proxy) proxy.isEnabled = newState;
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка переключения прокси:', error);
    input.checked = !newState;
  }
}

/**
 * Удаляет прокси после подтверждения.
 * @param {string} proxyId
 */
async function handleDeleteProxy(proxyId) {
  const proxy = state.proxies.find(p => p.proxyId === proxyId);
  const label = proxy ? `${proxy.host}:${proxy.port}` : proxyId;

  if (!confirm(`Удалить прокси ${label}?`)) return;

  try {
    await sendMessage(MESSAGES.DELETE_PROXY, { proxyId });
    state.proxies = state.proxies.filter(p => p.proxyId !== proxyId);
    state.pingResults.delete(proxyId);
    renderProxyList(state.proxies);
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка удаления:', error);
  }
}

/* ───── Модал: Добавление/редактирование прокси ───── */

function openAddProxyModal() {
  state.editingProxyId = null;
  document.getElementById('modal-proxy-title').textContent = 'Добавить прокси';
  clearProxyForm();
  showModal('modal-proxy');
}

async function openEditProxyModal(proxyId) {
  state.editingProxyId = proxyId;

  try {
    const proxy = await sendMessage(MESSAGES.GET_PROXY, { proxyId });
    if (!proxy) throw new Error('Прокси не найден');

    document.getElementById('modal-proxy-title').textContent = `Редактировать ${proxy.host}:${proxy.port}`;
    document.getElementById('proxy-ip').value = proxy.host || '';
    document.getElementById('proxy-port').value = proxy.port || '';
    document.getElementById('proxy-username').value = proxy.username || '';
    document.getElementById('proxy-password').value = proxy.password || '';
    hideFieldErrors();

    showModal('modal-proxy');
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка загрузки прокси:', error);
  }
}

function clearProxyForm() {
  document.getElementById('proxy-ip').value = '';
  document.getElementById('proxy-port').value = '';
  document.getElementById('proxy-username').value = '';
  document.getElementById('proxy-password').value = '';
  hideFieldErrors();
}

function hideFieldErrors() {
  document.querySelectorAll('.field-error').forEach(el => el.classList.add('hidden'));
}

function showFieldError(id, message) {
  const el = document.getElementById(id);
  el.textContent = message;
  el.classList.remove('hidden');
}

/**
 * Обработчик сохранения прокси (добавление или редактирование).
 */
async function handleSaveProxy() {
  const ip = document.getElementById('proxy-ip').value.trim();
  const portStr = document.getElementById('proxy-port').value.trim();
  const username = document.getElementById('proxy-username').value.trim();
  const password = document.getElementById('proxy-password').value;
  const port = Number(portStr);

  hideFieldErrors();

  /* Валидация */
  let hasError = false;

  if (!ip) {
    showFieldError('proxy-ip-error', 'Введите IP адрес');
    hasError = true;
  } else if (!isValidIP(ip)) {
    showFieldError('proxy-ip-error', 'Введен неверный IP адрес');
    hasError = true;
  }

  if (!portStr) {
    showFieldError('proxy-port-error', 'Введите порт');
    hasError = true;
  } else if (!isValidPort(port)) {
    showFieldError('proxy-port-error', 'Порт должен быть целым числом в диапазоне от 1 до 65535');
    hasError = true;
  }

  if (!username) {
    showFieldError('proxy-username-error', 'Введите логин');
    hasError = true;
  }

  if (!password) {
    showFieldError('proxy-password-error', 'Введите пароль');
    hasError = true;
  }

  if (hasError) return;

  /* Блокируем кнопку на время сохранения */
  const saveBtn = document.getElementById('btn-proxy-save');
  saveBtn.disabled = true;

  try {
    if (state.editingProxyId) {
      await sendMessage(MESSAGES.UPDATE_PROXY, {
        proxyId: state.editingProxyId,
        fields: { host: ip, port, username, password }
      });
      await loadAndRender();
    } else {
      await sendMessage(MESSAGES.ADD_PROXY, { host: ip, port, username, password });
      await loadAndRender();
    }
    closeModal();
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка сохранения прокси:', error);
    /* Парсим ошибку и показываем в нужном поле */
    const msg = error.message;
    if (msg.includes('IP')) {
      showFieldError('proxy-ip-error', msg);
    } else if (msg.includes('Порт')) {
      showFieldError('proxy-port-error', msg);
    } else if (msg.includes('Логин')) {
      showFieldError('proxy-username-error', msg);
    } else if (msg.includes('Пароль')) {
      showFieldError('proxy-password-error', msg);
    } else {
      showFieldError('proxy-ip-error', msg);
    }
  } finally {
    saveBtn.disabled = false;
  }
}

/* ───── Модал: Управление масками ───── */

/**
 * @private Обновляет список масок для указанного прокси без закрытия модала.
 * @param {string} proxyId
 */
async function _refreshMaskList(proxyId) {
  try {
    const masks = await sendMessage(MESSAGES.GET_MASKS_BY_PROXY, { proxyId });
    const container = document.getElementById('mask-list');

    const clearBtn = document.getElementById('btn-clear-masks');

    if (!masks || masks.length === 0) {
      container.innerHTML = '<div class="empty-state small">Нет масок</div>';
      clearBtn.classList.add('hidden');
      return;
    }

    clearBtn.classList.remove('hidden');

    container.innerHTML = masks.map(mask => `
      <div class="mask-item" data-mask-id="${mask.maskId}">
        <span class="mask-text" data-action="edit-mask">${escapeHtml(mask.regexString)}</span>
        <button class="btn-icon delete-icon mask-delete" data-action="delete-mask" title="Удалить маску">✕</button>
      </div>
    `).join('');

    container.querySelectorAll('.mask-item').forEach(el => {
      const maskId = el.dataset.maskId;

      el.querySelector('[data-action="edit-mask"]')?.addEventListener('click', () => {
        const mask = masks.find(m => m.maskId === maskId);
        if (mask) openEditMaskModal(maskId, mask.regexString);
      });

      el.querySelector('[data-action="delete-mask"]')?.addEventListener('click', async () => {
        if (!confirm('Удалить маску?')) return;
        try {
          await sendMessage(MESSAGES.DELETE_MASK, { maskId });
          await _refreshMaskList(proxyId);
        } catch (error) {
          console.error('[FlowLink Proxy] Ошибка удаления маски:', error);
        }
      });
    });
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка загрузки масок:', error);
  }
}

/**
 * Удаляет все маски текущего прокси.
 */
async function handleClearMasks() {
  if (!state.masksProxyId) return;
  if (!confirm('Удалить все маски для этого прокси?')) return;

  try {
    await sendMessage(MESSAGES.CLEAR_MASKS, { proxyId: state.masksProxyId });
    await _refreshMaskList(state.masksProxyId);
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка очистки масок:', error);
  }
}

async function openMaskModal(proxyId) {
  state.masksProxyId = proxyId;
  const proxy = state.proxies.find(p => p.proxyId === proxyId);
  document.getElementById('modal-masks-subtitle').textContent = proxy
    ? `Прокси ${proxy.host}:${proxy.port}`
    : '';

  await _refreshMaskList(proxyId);
  showModal('modal-masks');
}

/* ───── Модал: Добавление/редактирование маски ───── */

function openAddMaskModal() {
  state.editingMaskId = null;
  document.getElementById('modal-mask-title').textContent = 'Добавить маску';
  document.getElementById('mask-input').value = '';
  document.getElementById('mask-error').classList.add('hidden');
  showModal('modal-mask');
}

function openEditMaskModal(maskId, regexString) {
  state.editingMaskId = maskId;
  document.getElementById('modal-mask-title').textContent = 'Редактировать маску';
  document.getElementById('mask-input').value = regexString;
  document.getElementById('mask-error').classList.add('hidden');
  showModal('modal-mask');
}

/**
 * Авто-экранирует пользовательский ввод в regex.
 * - Экранирует точки (\.), если они не экранированы
 * - Конвертирует * в .* (glob-стиль)
 *
 * @param {string} str - Ввод пользователя.
 * @returns {string} Строка, безопасная для new RegExp().
 */
function autoEscapeMaskInput(str) {
  let result = '';
  for (let i = 0; i < str.length; i++) {
    const ch = str[i];
    const next = str[i + 1];

    if (ch === '\\' && next === '.') {
      /* Уже экранировано — пропускаем оба символа */
      result += '\\.';
      i++;
    } else if (ch === '.') {
      /* Неэкранированная точка — экранируем */
      result += '\\.';
    } else if (ch === '*') {
      /* Glob wildcard — конвертируем в regex */
      result += '.*';
    } else {
      result += ch;
    }
  }
  return result;
}

/**
 * Обработчик сохранения маски.
 * Проверяет на конфликты с другими масками.
 */
async function handleSaveMask() {
  let regexString = document.getElementById('mask-input').value.trim();
  const errorEl = document.getElementById('mask-error');
  errorEl.classList.add('hidden');

  if (!regexString) {
    errorEl.textContent = 'Заполните поле';
    errorEl.classList.remove('hidden');
    return;
  }

  /* Авто-экранирование: упрощает ввод для не-regex пользователей */
  const autoEscaped = autoEscapeMaskInput(regexString);

  try {
    /* Валидация: проверяем что RegExp компилируется */
    new RegExp(autoEscaped);
    /* Если авто-экранирование изменило строку — используем его, иначе оригинал */
    regexString = autoEscaped;
  } catch {
    /* Авто-экранирование не помогло — показываем ошибку */
    errorEl.textContent = 'Неверное регулярное выражение';
    errorEl.classList.remove('hidden');
    return;
  }

  /* Проверка на конфликт масок */
  try {
    const conflict = await sendMessage(MESSAGES.CHECK_MASK_CONFLICT, {
      proxyId: state.masksProxyId,
      regexString
    });
    if (conflict) {
      errorEl.textContent = conflict;
      errorEl.classList.remove('hidden');
      return;
    }
  } catch (error) {
    console.warn('[FlowLink Proxy] Ошибка проверки конфликта маски:', error);
  }

  try {
    if (state.editingMaskId) {
      await sendMessage(MESSAGES.UPDATE_MASK, {
        maskId: state.editingMaskId,
        regexString
      });
    } else {
      await sendMessage(MESSAGES.ADD_MASK, {
        proxyId: state.masksProxyId,
        regexString
      });
    }

    /* Возвращаемся к списку масок и обновляем его */
    if (state.masksProxyId) {
      showModal('modal-masks');
      await _refreshMaskList(state.masksProxyId);
    }
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.classList.remove('hidden');
  }
}

/* ───── Модальные окна (управление) ───── */

function showModal(id) {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function closeModal() {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
}

/* ───── Утилиты ───── */

/**
 * Экранирует HTML-спецсимволы для безопасной вставки.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
