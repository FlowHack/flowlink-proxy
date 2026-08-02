/**
 * @fileoverview
 * CRUD-операции с прокси (добавить, редактировать, удалить, включить/выключить).
 * Использует config-based API: GET /api/config → modify → POST /api/config.
 */

import { apiGet, apiPost } from '../shared/api.js';
import { isValidHost, isValidPort, setLoading } from '../shared/utils.js';
import { showModal, closeModal } from './modal.js';
import { showToast } from './popup.js';

/**
 * Открывает модальное окно добавления нового прокси.
 */
export function openAddProxyModal() {
  clearProxyForm();
  document.getElementById('modal-proxy-title').textContent = 'Добавить прокси';
  document.getElementById('proxy-id').value = '';
  showModal('modal-proxy');
}

/**
 * Открывает модальное окно редактирования существующего прокси.
 * @param {object} proxy — объект прокси (поля: proxyId, host, port, username, password, label).
 */
export function openEditProxyModal(proxy) {
  if (!proxy) return;
  // Сброс видимости пароля при открытии редактирования
  const pwdInput = document.getElementById('proxy-password');
  const pwdBtn = document.getElementById('btn-password-toggle');
  if (pwdInput) pwdInput.type = 'password';
  if (pwdBtn) {
    pwdBtn.title = 'Показать пароль';
    const closed = pwdBtn.querySelector('.eye-closed');
    const open = pwdBtn.querySelector('.eye-open');
    if (closed) closed.classList.remove('hidden');
    if (open) open.classList.add('hidden');
  }
  document.getElementById('modal-proxy-title').textContent = 'Редактировать прокси';
  document.getElementById('proxy-id').value = proxy.proxyId;
  document.getElementById('proxy-host').value = proxy.host;
  document.getElementById('proxy-port').value = proxy.port;
  document.getElementById('proxy-username').value = proxy.username || '';
  document.getElementById('proxy-password').value = proxy.password || '';
  document.getElementById('proxy-label').value = proxy.label || '';
  hideFieldErrors();
  showModal('modal-proxy');
}

/** Очищает форму прокси и скрывает ошибки валидации. */
function clearProxyForm() {
  document.getElementById('proxy-host').value = '';
  document.getElementById('proxy-port').value = '';
  document.getElementById('proxy-username').value = '';
  document.getElementById('proxy-password').value = '';
  document.getElementById('proxy-label').value = '';
  // Сбросить видимость пароля
  const pwdInput = document.getElementById('proxy-password');
  const pwdBtn = document.getElementById('btn-password-toggle');
  if (pwdInput) pwdInput.type = 'password';
  if (pwdBtn) {
    pwdBtn.title = 'Показать пароль';
    const closed = pwdBtn.querySelector('.eye-closed');
    const open = pwdBtn.querySelector('.eye-open');
    if (closed) closed.classList.remove('hidden');
    if (open) open.classList.add('hidden');
  }
  hideFieldErrors();
}

/** Скрывает все ошибки валидации на форме. */
function hideFieldErrors() {
  document.querySelectorAll('.field-error').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.field-group').forEach(el => el.classList.remove('field-error-border'));
}

/**
 * Показывает ошибку валидации для конкретного поля.
 * @param {string} fieldId — ID поля.
 * @param {string} message — текст ошибки.
 */
function showFieldError(fieldId, message) {
  const field = document.getElementById(fieldId);
  const error = field.parentElement.querySelector('.field-error');
  if (error) {
    error.textContent = message;
    error.classList.remove('hidden');
    field.closest('.field-group').classList.add('field-error-border');
  }
}

/**
 * Сохраняет прокси (создаёт или обновляет) через config-based API.
 * @param {Function} loadAndRender — функция перезагрузки всех данных.
 */
export async function handleSaveProxy(loadAndRender) {
  const proxyId = document.getElementById('proxy-id').value;
  const host = document.getElementById('proxy-host').value.trim();
  const port = Number(document.getElementById('proxy-port').value);
  const username = document.getElementById('proxy-username').value.trim();
  const password = document.getElementById('proxy-password').value;
  const label = document.getElementById('proxy-label').value.trim();

  hideFieldErrors();
  let hasError = false;
  if (!host) { showFieldError('proxy-host', 'Введите хост'); hasError = true; }
  if (!port || !isValidPort(port)) {
    showFieldError('proxy-port', port ? 'Порт от 1 до 65535' : 'Введите порт');
    hasError = true;
  }
  if (hasError) return;
  if (!isValidHost(host)) { showFieldError('proxy-host', 'Неверный формат хоста (IP или домен)'); return; }

  const saveBtn = document.getElementById('btn-proxy-save');
  setLoading(saveBtn, true);
  try {
    const config = await apiGet('/config');
    const proxies = config.proxies || [];

    // Проверка дубликата host:port
    const duplicates = proxies.filter(
      p => p.host === host && p.port === port && p.proxyId !== proxyId
    );
    if (duplicates.length > 0) {
      showFieldError('proxy-host', 'Прокси с таким host:port уже существует');
      return;
    }

    if (proxyId) {
      const idx = proxies.findIndex(p => p.proxyId === proxyId);
      if (idx !== -1) {
        proxies[idx] = { ...proxies[idx], host, port, username, password, label };
      }
    } else {
      proxies.push({
        proxyId: crypto.randomUUID(),
        host, port, username, password, label,
        isEnabled: true,
      });
    }
    config.proxies = proxies;
    await apiPost('/config', config);
    closeModal();
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка сохранения прокси:', e);
    // Типизированная ошибка (ApiError.kind) или обратная совместимость
    const isNetworkError = e.kind === 'network' || e.kind === 'timeout'
      || e.message.startsWith('NETWORK:') || e.message.startsWith('TIMEOUT:')
      || e.message.includes('Failed to fetch');
    const msg = isNetworkError
      ? 'Не удалось связаться с бэкендом. Проверьте, запущен ли FlowLink Proxy.'
      : e.message;
    showFieldError('proxy-host', msg);
  } finally {
    setLoading(saveBtn, false);
  }
}

/**
 * Удаляет прокси по ID (также удаляет связанные маски).
 * @param {string} proxyId
 * @param {Function} loadAndRender
 * @param {HTMLElement} btn — кнопка удаления (для спиннера).
 */
export async function handleDeleteProxy(proxyId, loadAndRender, btn) {
  setLoading(btn, true);
  try {
    const config = await apiGet('/config');
    config.proxies = (config.proxies || []).filter(p => p.proxyId !== proxyId);
    config.masks = (config.masks || []).filter(m => m.proxyId !== proxyId);
    await apiPost('/config', config);
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка удаления прокси:', e);
    showToast('Не удалось удалить прокси. Проверьте соединение с бэкендом.', 'error');
  } finally {
    setLoading(btn, false);
  }
}

/**
 * Включает/выключает прокси.
 * @param {string} proxyId
 * @param {Function} loadAndRender
 * @param {HTMLInputElement} checkbox — чекбокс-переключатель (блокируется на время запроса).
 */
export async function handleToggleProxy(proxyId, loadAndRender, checkbox) {
  checkbox.disabled = true;
  try {
    const config = await apiGet('/config');
    const proxy = (config.proxies || []).find(p => p.proxyId === proxyId);
    if (proxy) {
      proxy.isEnabled = !proxy.isEnabled;
      await apiPost('/config', config);
    }
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка переключения прокси:', e);
    showToast('Не удалось переключить прокси. Проверьте соединение с бэкендом.', 'error');
  } finally {
    checkbox.disabled = false;
  }
}
