/**
 * @fileoverview
 * Главный контроллер Popup — инициализация, загрузка данных, диспетчеризация событий.
 * Единственная ответственность: связывание UI с данными API.
 */

import { apiGet, apiPost } from '../shared/api.js';
import { escapeHtml } from '../shared/dom.js';
import { API_BASE, setApiPort } from '../shared/constants.js';
import { copyEmailToClipboard } from '../shared/utils.js';
import { handlePingAll } from './ping.js';
import { openHelpModal, switchHelpTab } from './help.js';
import { showModal, closeModal, attachModalOverlayClose } from './modal.js';
import { openAddProxyModal, openEditProxyModal, handleSaveProxy, handleDeleteProxy, handleToggleProxy } from './crud-proxy.js';
import { openAddMaskModal, openEditMaskModal, handleSaveMask, handleDeleteMask, handleClearMasks } from './crud-mask.js';
import { renderTabStatus } from './tab-status.js';
import { checkBackendVersion, checkForUpdates, backendVersion, latestTag } from './updater.js';
import { handleSettingsSave } from './settings.js';
import { discoverPort } from '../shared/port_discovery.js';

/** Глобальное состояние popup — прокси, маски, on/off, результаты пинга. */
const state = {
  proxies: [],
  masks: [],
  enabled: false,
  pingResults: new Map(),
  connected: false,
  selectedProxyId: null,
  autostartBrowser: false,
  browserPath: '',
};
// Экспортируем только сброс selectedProxyId для modal.js (без exposure паролей)
window.__flowlinkResetSelectedProxy = () => { state.selectedProxyId = null; };

/**
 * Показывает всплывающее уведомление (toast) с поддержкой разных типов.
 * @param {'error'|'warning'|'info'} type — тип уведомления (цвет).
 * @param {string} message — текст сообщения.
 * @param {object} [options] — опции.
 * @param {number} [options.duration=3000] — время показа в мс (0 = не скрывать).
 */
export function showNotification(type, message, options = {}) {
  const { duration = 3000 } = options;
  const el = document.getElementById('toast');
  if (!el) return;

  // Убираем старые классы типов
  el.classList.remove('toast-error', 'toast-warning', 'toast-info');
  // Добавляем класс типа
  el.classList.add(`toast-${type}`);

  el.textContent = message;
  el.classList.add('visible');

  // Очищаем предыдущий таймер
  if (el._hideTimer) clearTimeout(el._hideTimer);

  if (duration > 0) {
    el._hideTimer = setTimeout(() => el.classList.remove('visible'), duration);
  }
}

/** Показывает toast-уведомление на 2 секунды (алиас для обратной совместимости). */
export function showToast(msg, type = 'info') {
  showNotification(type, msg, { duration: 2000 });
}

// Глобальный доступ для help.js (избегает циклического импорта)
window.__flowlinkShowToast = showToast;

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
  for (const id of ['btn-add-proxy', 'btn-add-mask', 'btn-settings-toggle']) {
    const btn = document.getElementById(id);
    if (!btn) continue;
    btn.classList.toggle('btn-disabled', !connected);
  }
}

/**
 * Принудительная проверка бэкенда (для кнопки «Повторить»).
 * Если текущий порт недоступен — повторно сканирует порты 8080–8090,
 * чтобы найти бэкенд, запущенный на другом порту.
 */
async function handleRetry() {
  // Показываем спиннер на кнопке
  const btn = document.querySelector('#banner-connection-error .banner-action');
  if (btn) btn.classList.add('btn-loading');
  try {
    let ok = await quickPing();
    // Если текущий порт не отвечает — пробуем найти бэкенд на другом порту
    if (!ok) {
      console.log(
        '[FlowLink Proxy] Повторная попытка: текущий порт недоступен, сканирую...',
      );
      await discoverPort();
      // После смены порта — проверяем снова
      ok = await quickPing();
    }
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
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка в handleRetry:', e);
  } finally {
    if (btn) btn.classList.remove('btn-loading');
  }
}

/**
 * Универсальная функция отрисовки баннера.
 * @param {'error'|'warning'|'info'} type — тип баннера (красный/жёлтый/синий).
 * @param {string} message — текст сообщения.
 * @param {object} [options] — опции.
 * @param {string} [options.containerId='app'] — ID контейнера (prepend в него).
 * @param {boolean} [options.dismissable=false] — показывать кнопку «✕».
 * @param {string} [options.actionText] — текст кнопки действия.
 * @param {Function} [options.actionCallback] — обработчик кнопки действия.
 * @param {string} [options.bannerId] — ID баннера для повторного использования.
 */
function renderBanner(type, message, options = {}) {
  const {
    containerId = 'app',
    dismissable = false,
    actionText,
    actionCallback,
    helpText,
    helpCallback,
    bannerId,
  } = options;
  const container = document.getElementById(containerId);
  if (!container) return null;

  const id = bannerId || `banner-${type}-${containerId}`;
  let banner = document.getElementById(id);
  if (!banner) {
    banner = document.createElement('div');
    banner.id = id;
    banner.className = `banner banner-${type}`;
    // Вставляем после .header, а не в начало контейнера
    const header = container.querySelector('.header');
    if (header && header.nextSibling) {
      container.insertBefore(banner, header.nextSibling);
    } else {
      container.prepend(banner);
    }
  }

  banner.className = `banner banner-${type}`;
  let html = `<span class="banner-message">${escapeHtml(message)}</span>`;
  if (actionText) {
    html += `<button class="btn-small banner-action">${escapeHtml(actionText)}</button>`;
  }
  if (helpText) {
    html += `<button class="btn-small banner-help">${escapeHtml(helpText)}</button>`;
  }
  if (dismissable) {
    html += `<button class="btn-icon banner-dismiss" title="Закрыть">✕</button>`;
  }
  banner.innerHTML = html;
  banner.classList.remove('hidden');

  const actionBtn = banner.querySelector('.banner-action');
  if (actionBtn && actionCallback) {
    actionBtn.addEventListener('click', actionCallback);
  }
  const helpBtn = banner.querySelector('.banner-help');
  if (helpBtn && helpCallback) {
    helpBtn.addEventListener('click', helpCallback);
  }
  const dismissBtn = banner.querySelector('.banner-dismiss');
  if (dismissBtn) {
    dismissBtn.addEventListener('click', () => banner.classList.add('hidden'));
  }

  return banner;
}

// Глобальный доступ к renderBanner для других модулей (избегает циклического импорта)
window.__flowlinkRenderBanner = renderBanner;

/** Флаг соединения с бэкендом — глобальный для других модулей. */
window.__flowlinkConnected = false;

/** Показывает/скрывает баннер ошибки соединения и блокирует кнопки. */
function showError(visible) {
  window.__flowlinkConnected = !visible;
  updateConnectionUI(!visible);

  if (visible) {
    // Показываем баннер ошибки соединения через renderBanner
    renderBanner('error', 'Нет соединения с бэкендом. Проверьте, запущен ли FlowLink Proxy.', {
      bannerId: 'banner-connection-error',
      actionText: 'Повторить',
      actionCallback: handleRetry,
      helpText: 'Помощь',
      helpCallback: () => openHelpModal('backend', false, '', 'backend-error'),
    });
    // Скрываем всё, что требует бэкенд (нет данных — нет смысла показывать)
    document.getElementById('status-bar')?.classList.add('hidden');
  } else {
    // Скрываем баннер ошибки
    const banner = document.getElementById('banner-connection-error');
    if (banner) banner.classList.add('hidden');
    document.getElementById('status-bar')?.classList.remove('hidden');
  }
}

/** Загружает данные из API (конфиг) и рендерит UI. */
async function loadAndRender() {
  try {
    const config = await apiGet('/config');
    state.proxies = config.proxies || [];
    state.masks = config.masks || [];
    state.enabled = config.isEnabled !== undefined ? config.isEnabled : true;
    // Загружаем конфигурацию браузера (автозапуск и выбранный путь)
    try {
      const browserConfig = await apiGet('/browser-config');
      state.autostartBrowser = browserConfig.autostartBrowser === true;
      state.browserPath = browserConfig.browserPath || '';
    } catch (browserErr) {
      // Не критично — баннер о браузере просто не покажется
      console.warn('[FlowLink Proxy] Не удалось загрузить конфигурацию браузера:', browserErr);
    }
    window.__flowlinkConnected = true;
    showError(false);
    render(state);
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]?.url) renderTabStatus(tabs[0].url, state);
  } catch (e) {
    showError(true);
    console.error('[FlowLink Proxy] Ошибка загрузки конфига:', e);
  }
}

/**
 * Обрабатывает переключение глобального тоггла.
 * POST на /api/enabled, обновляет storage триггерит перезагрузку UI.
 */
async function handleGlobalToggle(checkbox) {
  if (!checkbox) return;
  const enabled = checkbox.checked;
  checkbox.disabled = true;
  // Сохраняем в storage ДО отправки на бэкенд, чтобы service-worker при обработке
  // SSE-события config_changed прочитал актуальное значение, а не устаревшее.
  await chrome.storage.local.set({ extEnabled: enabled }).catch(e => console.warn('[FlowLink Proxy] Ошибка записи в storage:', e));
  try {
    await apiPost('/enabled', { enabled });
    state.enabled = enabled;
    render(state);
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка переключения:', e);
    showNotification('error', 'Не удалось переключить состояние. Проверьте соединение с бэкендом.');
    chrome.storage.local.set({ extEnabled: !enabled }).catch(e => console.warn('[FlowLink Proxy] Ошибка записи в storage:', e));
    checkbox.checked = !enabled;
  } finally {
    checkbox.disabled = false;
  }
}

/** Быстрая проверка — доступен ли бэкенд (GET /api/version с таймаутом). */
async function quickPing() {
  const ctrl = new AbortController();
  // Таймаут устанавливается ДО запроса и гарантированно очищается в finally
  const timer = setTimeout(() => ctrl.abort(), POLL_TIMEOUT);
  try {
    const res = await fetch(`${API_BASE}/version`, { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    // ВСЕГДА очищаем таймер — даже при исключении fetch (сеть недоступна и т.п.)
    clearTimeout(timer);
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
      await chrome.storage.local.remove('configChanged').catch(e => console.warn('[FlowLink Proxy] Ошибка удаления из storage:', e));
      await loadAndRender();
    } else {
      // SSE может быть недоступно (service worker спит) — сами проверяем
      // browser-config, чтобы баннер «браузер не указан» скрывался
      // без ожидания SSE-события.
      await refreshBrowserConfig();
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
 * Перечитывает конфигурацию браузера и обновляет баннер «браузер не указан».
 * Вызывается при каждом поллинге: service worker может спать и не получать
 * SSE-события, поэтому popup сам проверяет актуальность browser-path/autostart.
 */
async function refreshBrowserConfig() {
  try {
    const browserConfig = await apiGet('/browser-config');
    const autostartBrowser = browserConfig.autostartBrowser === true;
    const browserPath = browserConfig.browserPath || '';
    if (autostartBrowser !== state.autostartBrowser || browserPath !== state.browserPath) {
      console.log('[FlowLink Proxy] Конфигурация браузера изменилась, обновляю UI');
      state.autostartBrowser = autostartBrowser;
      state.browserPath = browserPath;
      render(state);
    }
  } catch (e) {
    // Не критично — данные браузера просто не обновятся в этом цикле поллинга
    console.warn('[FlowLink Proxy] Не удалось проверить конфигурацию браузера:', e);
  }
}

/**
 * Мгновенная реакция на SSE-события бэкенда.
 * Service worker ставит флаг configChanged при получении config_changed,
 * browser_config_changed или autostart_browser_changed. Слушаем
 * storage.onChanged, чтобы перерисовать UI без ожидания поллинга (до 3 сек).
 *
 * Удаление флага внутри слушателя не вызывает рекурсию: при удалении
 * changes.configChanged.newValue === undefined и условие ниже не срабатывает.
 */
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes.configChanged || !changes.configChanged.newValue) {
    return;
  }
  console.log('[FlowLink Proxy] storage.onChanged: флаг configChanged установлен, перезагружаю данные');
  chrome.storage.local.remove('configChanged').catch(e => console.warn('[FlowLink Proxy] Ошибка удаления из storage:', e));
  if (document.readyState === 'loading') {
    // DOM ещё не готов — пропускаем: первичная загрузка в DOMContentLoaded
    // сама перечитает свежий конфиг.
    return;
  }
  loadAndRender();
});

/**
 * Показывает предупреждение, если включён автозапуск браузера,
 * но браузер не выбран. Предлагает помощь по настройке.
 */
function renderBrowserWarning() {
  const showWarning = state.autostartBrowser && !state.browserPath;
  const banner = document.getElementById('banner-browser-warning');
  if (!showWarning) {
    if (banner) banner.classList.add('hidden');
    return;
  }
  renderBanner('warning', 'Включён автозапуск браузера, но браузер не выбран. Настройте его, чтобы автозапуск работал.', {
    bannerId: 'banner-browser-warning',
    helpText: 'Помощь',
    helpCallback: () => openHelpModal('browser', false, '', 'browser-warning'),
  });
}

/**
 * Отрисовывает UI на основе состояния.
 * @param {object} state — глобальное состояние.
 */
function render(state) {
  renderBrowserWarning();
  renderProxyList();
  renderVersion();
  renderGlobalToggle();
  // Маски: фильтр по выбранному прокси или все
  const filtered = state.selectedProxyId
    ? state.masks.filter(m => m.proxyId === state.selectedProxyId)
    : state.masks;
  const masksContainer = document.getElementById('mask-list');
  const maskRows = filtered.map(m => {
    const escapedMaskId = escapeHtml(m.maskId);
    return `<div class="mask-row">
      <button class="btn btn-icon btn-edit-mask" data-mask-id="${escapedMaskId}" title="Редактировать маску">✎</button>
      <span class="mask-pattern">${escapeHtml(m.pattern)}</span>
      <button class="btn btn-icon btn-danger-mask" data-mask-id="${escapedMaskId}" title="Удалить маску">✕</button>
    </div>`;
  }).join('');
  masksContainer.innerHTML = maskRows || '<div class="mask-row list-empty">Масок нет</div>';
}

/** Отрисовывает версию расширения в футере. */
function renderVersion() {
  const ver = chrome.runtime.getManifest().version;
  const el = document.getElementById('version-text');
  if (el) el.textContent = `Версия: ${ver}`;
}

/** Отрисовывает глобальный тоггл (on/off). */
function renderGlobalToggle() {
  const toggle = document.getElementById('global-toggle-input');
  if (!toggle) return;
  toggle.checked = state.enabled;
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
      pingHtml = `<span class="proxy-ping ping-ok">${escapeHtml(ms)}</span>`;
    } else {
      pingHtml = '<span class="proxy-ping ping-fail">н/д</span>';
    }
    const label = escapeHtml(p.label || `${p.host}:${p.port}`);
    const escapedProxyId = escapeHtml(p.proxyId);
    return `<div class="proxy-row ${!p.isEnabled ? 'proxy-disabled' : ''}" title="Клик — маски для ${label}">
      <label class="switch proxy-toggle-wrap">
        <input type="checkbox" class="proxy-toggle" data-proxy-id="${escapedProxyId}" ${p.isEnabled ? 'checked' : ''}>
        <span class="slider"></span>
      </label>
      <button class="btn btn-icon btn-edit" data-proxy-id="${escapedProxyId}" title="Редактировать">✎</button>
      <span class="proxy-ip">${label}</span>
      ${pingHtml}
      <button class="btn btn-icon btn-delete" data-proxy-id="${escapedProxyId}" title="Удалить">✕</button>
    </div>`;
  }).join('');
  container.innerHTML = rows || '<div class="proxy-row list-empty">Прокси не добавлены</div>';
}

/** Привязывает обработчики событий к элементам UI. */
function attachGlobalListeners() {
  attachModalOverlayClose();
  document.addEventListener('click', (e) => {
    // Открыть модалку помощи
    if (e.target.id === 'btn-help') openHelpModal('port', false, '', 'general');
    // Удаление прокси
    if (e.target.classList.contains('btn-delete')) {
      const proxyId = e.target.dataset.proxyId;
      handleDeleteProxy(proxyId, loadAndRender, e.target);
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
        render();
        showModal('modal-masks');
      }
    }
    // Редактирование маски
    if (e.target.classList.contains('btn-edit-mask')) {
      const maskId = e.target.dataset.maskId;
      const mask = state.masks.find(m => m.maskId === maskId);
      if (mask) openEditMaskModal(state, mask);
    }
    // Удаление маски
    if (e.target.classList.contains('btn-danger-mask')) {
      const maskId = e.target.dataset.maskId;
      handleDeleteMask(maskId, loadAndRender, e.target);
    }
  });

  document.addEventListener('change', (e) => {
    // Тоггл отдельного прокси
    if (e.target.classList.contains('proxy-toggle')) {
      handleToggleProxy(e.target.dataset.proxyId, loadAndRender, e.target);
    }
    // Глобальный тоггл (on/off)
    if (e.target.id === 'global-toggle-input') {
      handleGlobalToggle(e.target);
    }
  });

  document.addEventListener('submit', (e) => {
    if (e.target.id === 'proxy-form') {
      e.preventDefault();
      handleSaveProxy(loadAndRender);
    }
    if (e.target.id === 'mask-form') {
      e.preventDefault();
      handleSaveMask(state, loadAndRender);
    }
    if (e.target.id === 'settings-form') {
      e.preventDefault();
      handleSettingsSave(loadAndRender, showToast);
    }
  });

  // Баннер обновления
  document.getElementById('btn-update-close')?.addEventListener('click', () => {
    document.getElementById('update-banner').classList.add('hidden');
  });
  document.getElementById('btn-update-help')?.addEventListener('click', () => openHelpModal('update-backend', true, latestTag, 'update'));

  document.getElementById('btn-ping-all')?.addEventListener('click', () => handlePingAll(state, renderProxyList));
  document.getElementById('btn-add-proxy')?.addEventListener('click', () => {
    if (!state.connected) { showNotification('error', 'Нет соединения с бэкендом'); return; }
    openAddProxyModal();
  });
  document.getElementById('btn-add-mask')?.addEventListener('click', () => openAddMaskModal(state));
  document.getElementById('btn-clear-masks')?.addEventListener('click', () => handleClearMasks(loadAndRender));
  document.getElementById('btn-settings-toggle')?.addEventListener('click', () => {
    if (!state.connected) { showNotification('error', 'Нет соединения с бэкендом'); return; }
    document.getElementById('settings-block').classList.toggle('hidden');
  });

  // Закрытие модалок
  for (const id of ['btn-help-close', 'btn-proxy-cancel', 'btn-mask-cancel']) {
    document.getElementById(id)?.addEventListener('click', closeModal);
  }
  // Закрытие масок — дополнительно сбрасываем selectedProxyId
  document.getElementById('btn-masks-close')?.addEventListener('click', () => {
    state.selectedProxyId = null;
    closeModal();
  });
  document.getElementById('tab-backend')?.addEventListener('click', () => switchHelpTab('backend'));
  document.getElementById('tab-browser')?.addEventListener('click', () => switchHelpTab('browser'));
  document.getElementById('tab-port')?.addEventListener('click', () => switchHelpTab('port'));
  document.getElementById('tab-faq')?.addEventListener('click', () => switchHelpTab('faq'));
  document.getElementById('tab-update-backend')?.addEventListener('click', () => switchHelpTab('update-backend'));
  document.getElementById('tab-update-ext')?.addEventListener('click', () => switchHelpTab('update-ext'));

  // Переключение видимости пароля
  document.getElementById('btn-password-toggle')?.addEventListener('click', togglePasswordVisibility);

  // Копирование email в буфер обмена (футер popup)
  document.getElementById('contact-email')?.addEventListener('click',
    () => copyEmailToClipboard('flowlink.proxy@atomicmail.io', showToast));

  // Копирование email в футере помощи (help-email-copy) — делегирование,
  // т.к. контент помощи рендерится динамически через innerHTML.
  document.addEventListener('click', (e) => {
    const emailEl = e.target.closest('.help-email-copy');
    if (emailEl && emailEl.dataset.email) {
      copyEmailToClipboard(emailEl.dataset.email, showToast);
    }
  });
}

/** Переключает видимость пароля в форме прокси. */
function togglePasswordVisibility() {
  const input = document.getElementById('proxy-password');
  const btn = document.getElementById('btn-password-toggle');
  if (!input || !btn) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  btn.title = isPassword ? 'Скрыть пароль' : 'Показать пароль';
  btn.querySelector('.eye-closed').classList.toggle('hidden', !isPassword);
  btn.querySelector('.eye-open').classList.toggle('hidden', isPassword);
}

/** Точка входа — инициализация. */
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // Будим service worker, чтобы он мгновенно восстановил SSE-соединение
    // (без ожидания keepalive-alarm).
    chrome.runtime.sendMessage({ type: 'wake' }).catch((e) => {
      console.warn('[FlowLink Proxy] Не удалось разбудить service worker:', e);
    });
    await loadStoredPort();
    await discoverPort();
    attachGlobalListeners();

    // Проверяем, не изменился ли конфиг с прошлого открытия popup (SSE-уведомление)
    const storage = await chrome.storage.local.get(['configChanged']);
    if (storage.configChanged) {
      await chrome.storage.local.remove('configChanged').catch(e => console.warn('[FlowLink Proxy] Ошибка удаления configChanged из storage:', e));
    }

    // Первая загрузка — один раз, без поллинга
    await loadAndRender();
    // Если бэкенд ответил — проверяем версию и обновления
    const backendOk = await checkBackendVersion();
    if (backendOk) {
      // 1. Проверка GitHub API (работает когда репозиторий публичный)
      await checkForUpdates(false);
      // 2. Дополнительная проверка флага от бэкенда (--need-update)
      try {
        const status = await apiGet('/status');
        if (status.needUpdate) {
          await checkForUpdates(true, backendVersion || '');
        }
      } catch (e) {
        console.warn('[FlowLink Proxy] Ошибка проверки статуса при инициализации:', e);
      }
    }
    // Запускаем поллинг для отслеживания изменений
    startPolling();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка инициализации:', e);
    showError(true);
  }
});
