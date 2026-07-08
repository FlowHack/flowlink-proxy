/**
 * @fileoverview
 * Главный контроллер Popup — инициализация, загрузка данных, диспетчеризация событий.
 * Единственная ответственность: связывание UI с данными API.
 */

import { apiGet } from '../shared/api.js';
import { escapeHtml } from '../shared/dom.js';
import { API_BASE, setApiPort } from '../shared/constants.js';
import { handlePingAll } from './ping.js';
import { openHelpModal, switchHelpTab } from './help.js';
import { showModal, closeModal } from './modal.js';
import { openAddProxyModal, openEditProxyModal, handleSaveProxy, handleDeleteProxy, handleToggleProxy } from './crud-proxy.js';
import { openAddMaskModal, handleSaveMask, handleDeleteMask, handleClearMasks } from './crud-mask.js';
import { renderTabStatus } from './tab-status.js';
import { checkBackendVersion, checkForUpdates } from './updater.js';
import { handleSettingsSave } from './settings.js';

/** Глобальное состояние popup — прокси, маски, on/off, результаты пинга. */
const state = {
  proxies: [],
  masks: [],
  enabled: false,
  pingResults: new Map(),
  connected: false,
  selectedProxyId: null,
};

/** Показывает toast-уведомление на 2 секунды. */
function showToast(msg) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('visible');
  setTimeout(() => el.classList.remove('visible'), 2000);
}

/** Базовый интервал опроса бэкенда (мс). */
const POLL_INTERVAL = 3000;
/** Максимальный интервал при отказе (мс). */
const POLL_MAX = 30000;
/** Таймаут одного запроса (мс). */
const POLL_TIMEOUT = 3000;

let _pollTimer = null;
let _pollInterval = POLL_INTERVAL;

/** Загружает сохранённый порт из chrome.storage. */
async function loadStoredPort() {
  const result = await chrome.storage.local.get('apiPort');
  if (result.apiPort && Number.isInteger(result.apiPort)) {
    setApiPort(result.apiPort);
  }
}

/** Блокирует/разблокирует кнопки, зависящие от соединения с бэкендом. */
function updateConnectionUI(connected) {
  state.connected = connected;
  for (const id of ['btn-add-proxy', 'btn-settings-toggle']) {
    const btn = document.getElementById(id);
    if (!btn) continue;
    btn.classList.toggle('btn-disabled', !connected);
  }
}

/** Принудительная проверка бэкенда (для кнопки «Повторить»). */
async function handleRetry() {
  const ok = await quickPing();
  if (ok) {
    stopPolling();
    _pollInterval = POLL_INTERVAL;
    await loadAndRender();
    await checkBackendVersion();
    await checkForUpdates(false);
    if (state.connected) startPolling();
  } else {
    showError(true);
  }
}

/** Показывает/скрывает error-state и блокирует кнопки. */
function showError(visible) {
  const errorState = document.getElementById('error-state');
  if (!errorState) return;
  errorState.classList.toggle('hidden', !visible);
  document.getElementById('status-bar')?.classList.toggle('hidden', visible);
  updateConnectionUI(!visible);
  if (visible) {
    const retryBtn = document.getElementById('btn-retry');
    if (retryBtn) retryBtn.onclick = handleRetry;
    document.getElementById('btn-help-setup')?.addEventListener('click', openHelpModal, { once: true });
  }
}

/** Загружает данные из API (конфиг) и рендерит UI. */
async function loadAndRender() {
  try {
    const config = await apiGet('/config');
    state.proxies = config.proxies || [];
    state.masks = config.masks || [];
    state.enabled = config.isEnabled !== undefined ? config.isEnabled : true;
    showError(false);
    render(state);
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]?.url) renderTabStatus(tabs[0].url, state);
  } catch (e) {
    showError(true);
    console.error('[FlowLink] Ошибка загрузки конфига:', e);
  }
}

/** Быстрая проверка — доступен ли бэкенд (GET /api/version с таймаутом). */
async function quickPing() {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), POLL_TIMEOUT);
    const res = await fetch(`${API_BASE}/version`, { signal: ctrl.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

/** Опрашивает бэкенд и обновляет UI (с экспоненциальной задержкой при отказе). */
async function pollBackend() {
  const ok = await quickPing();
  if (ok && !state.connected) {
    // Бэкенд появился — перезагружаем всё
    _pollInterval = POLL_INTERVAL;
    showError(false);
    await loadAndRender();
  } else if (!ok && state.connected) {
    // Бэкенд пропал
    _pollInterval = Math.min(_pollInterval * 1.5, POLL_MAX);
    showError(true);
  } else if (ok && state.connected) {
    // Бэкенд жив — сброс интервала, проверяем флаг обновления конфига
    _pollInterval = POLL_INTERVAL;
    const storage = await chrome.storage.local.get('configChanged');
    if (storage.configChanged) {
      await chrome.storage.local.remove('configChanged');
      await loadAndRender();
    }
  } else {
    // Был не connected, всё ещё не connected — увеличиваем интервал
    _pollInterval = Math.min(_pollInterval * 1.5, POLL_MAX);
  }
  schedulePoll();
}

function schedulePoll() {
  stopPolling();
  _pollTimer = setTimeout(pollBackend, _pollInterval);
}

function startPolling() {
  _pollInterval = POLL_INTERVAL;
  schedulePoll();
}

function stopPolling() {
  if (_pollTimer) {
    clearTimeout(_pollTimer);
    _pollTimer = null;
  }
}

/**
 * Отрисовывает UI на основе состояния.
 * @param {object} state — глобальное состояние.
 */
function render(state) {
  renderProxyList();
  renderVersion();
  renderGlobalToggle();
  // Маски: фильтр по выбранному прокси или все
  const filtered = state.selectedProxyId
    ? state.masks.filter(m => m.proxyId === state.selectedProxyId)
    : state.masks;
  const subtitle = document.getElementById('modal-masks-subtitle');
  if (state.selectedProxyId) {
    const proxy = state.proxies.find(p => p.proxyId === state.selectedProxyId);
    subtitle.textContent = proxy ? `Маски для ${proxy.host}:${proxy.port}` : 'Маски';
  } else {
    subtitle.textContent = 'Все маски';
  }
  const masksContainer = document.getElementById('mask-list');
  const maskRows = filtered.map(m => {
    const proxy = state.proxies.find(p => p.proxyId === m.proxyId);
    return `<div class="mask-row">
      <span class="mask-pattern">${escapeHtml(m.pattern)}</span>
      <span class="mask-proxy-name">→ ${proxy ? `${proxy.host}:${proxy.port}` : '?'}</span>
      <button class="btn btn-icon btn-danger-mask" data-mask-id="${m.maskId}" title="Удалить маску">✕</button>
    </div>`;
  }).join('');
  masksContainer.innerHTML = maskRows || '<div class="mask-row list-empty">Масок нет</div>';
}

/** Отрисовывает версию расширения в футере. */
function renderVersion() {
  const ver = chrome.runtime.getManifest().version;
  document.getElementById('version-text').textContent = `Версия: ${ver}`;
}

/** Отрисовывает глобальный тоггл (on/off). */
function renderGlobalToggle() {
  const toggle = document.getElementById('global-toggle-input');
  if (!toggle) return;
  toggle.checked = state.enabled;
  toggle.addEventListener('change', async () => {
    try {
      const enabled = toggle.checked;
      await fetch(`${API_BASE}/enabled`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      chrome.storage.local.set({ extEnabled: enabled });
    } catch (e) {
      console.error('[FlowLink] Ошибка переключения:', e);
      toggle.checked = !toggle.checked;
    }
  });
}

/** Отрисовывает таблицу прокси с иконками статуса и кнопками. */
function renderProxyList() {
  const container = document.getElementById('proxy-list');
  const rows = state.proxies.map(p => {
    const ping = state.pingResults.get(p.proxyId);
    let pingHtml;
    if (!ping) {
      pingHtml = '<span class="proxy-ping ping-none">...</span>';
    } else if (ping.alive) {
      const ms = ping.latency != null ? `${ping.latency}ms` : '0ms';
      pingHtml = `<span class="proxy-ping ping-ok">${ms}</span>`;
    } else {
      pingHtml = '<span class="proxy-ping ping-fail">н/д</span>';
    }
    const label = escapeHtml(p.label || `${p.host}:${p.port}`);
    return `<div class="proxy-row ${!p.isEnabled ? 'proxy-disabled' : ''}" title="Клик — маски для ${label}">
      <label class="switch proxy-toggle-wrap">
        <input type="checkbox" class="proxy-toggle" data-proxy-id="${p.proxyId}" ${p.isEnabled ? 'checked' : ''}>
        <span class="slider"></span>
      </label>
      <button class="btn btn-icon btn-edit" data-proxy-id="${p.proxyId}" title="Редактировать">✎</button>
      <span class="proxy-ip">${label}</span>
      ${pingHtml}
      <button class="btn btn-icon btn-delete" data-proxy-id="${p.proxyId}" title="Удалить">✕</button>
    </div>`;
  }).join('');
  container.innerHTML = rows || '<div class="proxy-row list-empty">Прокси не добавлены</div>';
}

/** Привязывает обработчики событий к элементам UI. */
function attachGlobalListeners() {
  document.addEventListener('click', (e) => {
    // Открыть модалку помощи
    if (e.target.id === 'btn-help') openHelpModal();
    // Удаление прокси
    if (e.target.classList.contains('btn-delete')) {
      const proxyId = e.target.dataset.proxyId;
      handleDeleteProxy(proxyId, loadAndRender);
    }
    // Редактирование прокси
    if (e.target.classList.contains('btn-edit')) {
      const proxyId = e.target.dataset.proxyId;
      const proxy = state.proxies.find(p => p.proxyId === proxyId);
      if (proxy) openEditProxyModal(proxy);
    }
    // Открытие масок по клику на строку прокси (кроме кнопок)
    const proxyRow = e.target.closest('.proxy-row');
    if (proxyRow && !e.target.closest('button, label, .proxy-ping')) {
      const proxyId = proxyRow.querySelector('.proxy-toggle')?.dataset?.proxyId;
      if (proxyId) {
        state.selectedProxyId = proxyId;
        render(state);
        showModal('modal-masks');
      }
    }
    // Удаление маски
    if (e.target.classList.contains('btn-danger-mask')) {
      const maskId = e.target.dataset.maskId;
      handleDeleteMask(maskId, loadAndRender);
    }
  });

  document.addEventListener('change', (e) => {
    // Тоггл отдельного прокси
    if (e.target.classList.contains('proxy-toggle')) {
      handleToggleProxy(e.target.dataset.proxyId, loadAndRender);
    }
  });

  document.addEventListener('submit', (e) => {
    if (e.target.id === 'proxy-form') {
      e.preventDefault();
      handleSaveProxy(loadAndRender);
    }
    if (e.target.id === 'mask-form') {
      e.preventDefault();
      handleSaveMask(loadAndRender);
    }
    if (e.target.id === 'settings-form') {
      e.preventDefault();
      handleSettingsSave(loadAndRender);
    }
  });

  document.getElementById('btn-ping-all')?.addEventListener('click', () => handlePingAll(state, renderProxyList));
  document.getElementById('btn-add-proxy')?.addEventListener('click', () => {
    if (!state.connected) { showToast('Нет соединения с бэкендом'); return; }
    openAddProxyModal();
  });
  document.getElementById('btn-add-mask')?.addEventListener('click', () => openAddMaskModal(state));
  document.getElementById('btn-clear-masks')?.addEventListener('click', () => handleClearMasks(loadAndRender));
  document.getElementById('btn-settings-toggle')?.addEventListener('click', () => {
    if (!state.connected) { showToast('Нет соединения с бэкендом'); return; }
    document.getElementById('settings-row').classList.toggle('hidden');
  });
  // Закрытие модалок
  for (const id of ['btn-help-close', 'btn-help-close2', 'btn-proxy-cancel', 'btn-mask-cancel']) {
    document.getElementById(id)?.addEventListener('click', closeModal);
  }
  // Закрытие масок — дополнительно сбрасываем selectedProxyId
  document.getElementById('btn-masks-close')?.addEventListener('click', () => {
    state.selectedProxyId = null;
    closeModal();
  });
  document.getElementById('tab-windows')?.addEventListener('click', () => switchHelpTab('windows'));
  document.getElementById('tab-source')?.addEventListener('click', () => switchHelpTab('source'));

  // Переключение видимости пароля
  document.getElementById('btn-password-toggle')?.addEventListener('click', togglePasswordVisibility);
}

/** Переключает видимость пароля в форме прокси. */
function togglePasswordVisibility() {
  const input = document.getElementById('proxy-password');
  const btn = document.getElementById('btn-password-toggle');
  if (!input || !btn) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  btn.title = isPassword ? 'Скрыть пароль' : 'Показать пароль';
  btn.querySelector('.eye-closed').style.display = isPassword ? 'none' : '';
  btn.querySelector('.eye-open').style.display = isPassword ? '' : 'none';
}

/** Точка входа — инициализация. */
document.addEventListener('DOMContentLoaded', async () => {
  await loadStoredPort();
  attachGlobalListeners();

  // Проверяем, не изменился ли конфиг с прошлого открытия popup (SSE-уведомление)
  const storage = await chrome.storage.local.get(['configChanged', 'needUpdate']);
  if (storage.configChanged) {
    await chrome.storage.local.remove('configChanged');
  }

  // Если пришёл флаг need_update (симуляция обновления) — очищаем и форсируем проверку
  const simulateUpdate = !!storage.needUpdate;
  if (simulateUpdate) {
    await chrome.storage.local.remove('needUpdate');
  }

  // Первая загрузка — один раз, без поллинга
  await loadAndRender();
  // Если бэкенд ответил — проверяем версию и обновления
  const backendOk = await checkBackendVersion();
  if (backendOk) {
    await checkForUpdates(simulateUpdate);
  }
  // Запускаем поллинг для отслеживания изменений
  startPolling();
});
