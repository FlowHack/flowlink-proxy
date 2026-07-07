/**
 * @fileoverview
 * Контроллер Popup — напрямую общается с Python API (localhost:8081).
 * Никаких сообщений через Service Worker.
 */

import { API_BASE, setApiPort, isValidIP, isValidPort, convertWildcardToRegex, APP_VERSION, GITHUB_RELEASES_URL, GITHUB_API_RELEASES } from '../shared/constants.js';

let state = {
  proxies: [],
  masks: [],
  isEnabled: true,
  pingResults: new Map(),
  editingProxyId: null,
  masksProxyId: null,
  backendVersion: null,
};

/* ───── HTTP API helpers ───── */

async function apiGet(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

async function apiPost(endpoint, body) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

/* ───── Спиннер ───── */

function setLoading(btnEl, loading) {
  if (loading) {
    btnEl.classList.add('btn-loading');
    btnEl.disabled = true;
  } else {
    btnEl.classList.remove('btn-loading');
    btnEl.disabled = false;
  }
}

/* ───── Инициализация ───── */

document.addEventListener('DOMContentLoaded', async () => {
  await loadStoredPort();
  await loadAndRender();
  attachGlobalListeners();
});

async function loadStoredPort() {
  try {
    const result = await chrome.storage.local.get('apiPort');
    if (result.apiPort) {
      setApiPort(result.apiPort);
      document.getElementById('settings-api-port').value = result.apiPort;
    }
  } catch (e) {
    console.warn('[FlowLink] Не удалось загрузить порт из storage:', e);
  }
}

async function loadAndRender() {
  try {
    const cfg = await apiGet('/config');
    state.proxies = cfg.proxies || [];
    state.masks = cfg.masks || [];
    state.isEnabled = cfg.isEnabled !== false;
    render();
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs?.[0]?.url) renderTabStatus(tabs[0].url);
    await checkBackendVersion();
    const status = await apiGet('/status');
    if (status.debug) {
      const vEl = document.getElementById('version-text');
      vEl.textContent += ' [DEV]';
      vEl.style.color = 'var(--accent-orange)';
    } else {
      await checkForUpdates();
    }
  } catch (e) {
    console.error('[FlowLink] Ошибка загрузки:', e);
    document.getElementById('error-state').classList.remove('hidden');
  }
}

async function checkBackendVersion() {
  try {
    const resp = await apiGet('/version');
    state.backendVersion = resp.version;
    const extVer = document.getElementById('version-text');
    if (extVer && resp.version && resp.version !== APP_VERSION) {
      extVer.textContent = `Версия: ${chrome.runtime.getManifest().version} (бэкенд: ${resp.version})`;
    }
  } catch {}
}

async function checkForUpdates() {
  try {
    const resp = await fetch(GITHUB_API_RELEASES);
    if (!resp.ok) return;
    const release = await resp.json();
    const latestTag = release.tag_name || '';
    if (!latestTag) return;
    const latestVer = latestTag.replace(/^v/, '');
    const currentVer = state.backendVersion || APP_VERSION;
    if (compareVersions(latestVer, currentVer) > 0) {
      showUpdateBanner(latestTag, release.html_url);
    }
  } catch {}
}

function compareVersions(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const na = pa[i] || 0;
    const nb = pb[i] || 0;
    if (na > nb) return 1;
    if (na < nb) return -1;
  }
  return 0;
}

function showUpdateBanner(tag, url) {
  const banner = document.getElementById('update-banner');
  document.getElementById('update-text').textContent = `Доступно обновление ${tag}`;
  document.getElementById('btn-update-download').href = url;
  banner.classList.remove('hidden');
}

function render() {
  renderVersion();
  renderGlobalToggle(state.isEnabled);
  renderProxyList(state.proxies);
  document.getElementById('error-state').classList.add('hidden');
}

/* ───── Рендер ───── */

function renderVersion() {
  const el = document.getElementById('version-text');
  const v = chrome.runtime.getManifest().version;
  el.textContent = `Версия: ${v}`;
}

function renderGlobalToggle(enabled) {
  document.getElementById('global-toggle-input').checked = enabled;
}

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
        <label class="switch proxy-toggle" title="Вкл/Выкл прокси">
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

  container.querySelectorAll('.proxy-item').forEach(el => {
    const proxyId = el.dataset.proxyId;
    el.querySelector('.proxy-toggle input')?.addEventListener('change', () => handleToggleProxy(proxyId));
    el.querySelector('[data-action="edit"]')?.addEventListener('click', () => openEditProxyModal(proxyId));
    el.querySelector('[data-action="delete"]')?.addEventListener('click', () => handleDeleteProxy(proxyId));
    el.querySelector('[data-action="masks"]')?.addEventListener('click', () => openMaskModal(proxyId));
  });
}

/* ───── Глобальные обработчики ───── */

function attachGlobalListeners() {
  document.getElementById('global-toggle-input').addEventListener('change', async (e) => {
    try {
      const cfg = await apiGet('/config');
      cfg.isEnabled = e.target.checked;
      await apiPost('/config', cfg);
      state.isEnabled = e.target.checked;
    } catch (err) {
      console.error('[FlowLink] Ошибка переключения:', err);
      e.target.checked = !e.target.checked;
    }
  });

  document.getElementById('btn-ping-all').addEventListener('click', handlePingAll);

  document.getElementById('btn-retry').addEventListener('click', async () => {
    const btn = document.getElementById('btn-retry');
    setLoading(btn, true);
    btn.textContent = 'Загрузка...';
    await loadAndRender();
    setLoading(btn, false);
    btn.textContent = 'Повторить';
  });

  document.getElementById('btn-help-setup').addEventListener('click', () => openHelpModal('windows'));
  document.getElementById('btn-help-close').addEventListener('click', closeModal);
  document.getElementById('btn-help-close2').addEventListener('click', closeModal);
  document.getElementById('tab-windows').addEventListener('click', () => switchHelpTab('windows'));
  document.getElementById('tab-source').addEventListener('click', () => switchHelpTab('source'));

  document.getElementById('btn-update-help').addEventListener('click', () => openHelpModal('update'));
  document.getElementById('btn-update-close').addEventListener('click', () => {
    document.getElementById('update-banner').classList.add('hidden');
  });

  document.getElementById('btn-add-proxy').addEventListener('click', () => openAddProxyModal());
  document.getElementById('btn-proxy-cancel').addEventListener('click', closeModal);
  document.getElementById('btn-proxy-save').addEventListener('click', handleSaveProxy);
  document.getElementById('btn-masks-close').addEventListener('click', closeModal);
  document.getElementById('btn-add-mask').addEventListener('click', () => openAddMaskModal());
  document.getElementById('btn-mask-cancel').addEventListener('click', () => {
    document.getElementById('modal-mask').classList.add('hidden');
  });
  document.getElementById('btn-mask-save').addEventListener('click', handleSaveMask);

  document.getElementById('btn-settings-toggle').addEventListener('click', () => {
    const row = document.getElementById('settings-row');
    row.classList.toggle('hidden');
  });

  document.getElementById('btn-settings-save').addEventListener('click', handleSettingsSave);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal();
      const row = document.getElementById('settings-row');
      if (!row.classList.contains('hidden')) row.classList.add('hidden');
    }
  });
}

/* ───── Пинг ───── */

async function handlePingAll() {
  const btn = document.getElementById('btn-ping-all');
  setLoading(btn, true);
  btn.textContent = 'Проверка...';
  state.pingResults.clear();

  for (const p of state.proxies) {
    try {
      const result = await apiPost('/ping', { proxyId: p.proxyId });
      state.pingResults.set(p.proxyId, { alive: result.alive, latency: result.latency });
    } catch {
      state.pingResults.set(p.proxyId, { alive: false, latency: null });
    }
  }

  renderProxyList(state.proxies);
  setLoading(btn, false);
  btn.textContent = 'Пинг';
}

/* ───── Действия с прокси ───── */

async function handleToggleProxy(proxyId) {
  const proxy = state.proxies.find(p => p.proxyId === proxyId);
  if (!proxy) return;
  proxy.isEnabled = !proxy.isEnabled;
  try {
    const cfg = await apiGet('/config');
    const p = cfg.proxies.find(x => x.proxyId === proxyId);
    if (p) p.isEnabled = proxy.isEnabled;
    await apiPost('/config', cfg);
  } catch (err) {
    console.error('[FlowLink] Ошибка toggle:', err);
    proxy.isEnabled = !proxy.isEnabled;
    renderProxyList(state.proxies);
  }
}

async function handleDeleteProxy(proxyId) {
  const proxy = state.proxies.find(p => p.proxyId === proxyId);
  const label = proxy ? `${proxy.host}:${proxy.port}` : proxyId;
  if (!confirm(`Удалить прокси ${label}?`)) return;

  try {
    const cfg = await apiGet('/config');
    cfg.proxies = cfg.proxies.filter(p => p.proxyId !== proxyId);
    cfg.masks = cfg.masks.filter(m => m.proxyId !== proxyId);
    await apiPost('/config', cfg);
    state.proxies = state.proxies.filter(p => p.proxyId !== proxyId);
    state.pingResults.delete(proxyId);
    renderProxyList(state.proxies);
  } catch (err) {
    console.error('[FlowLink] Ошибка удаления:', err);
  }
}

/* ───── Модал: Добавление/редактирование прокси ───── */

function openAddProxyModal() {
  state.editingProxyId = null;
  document.getElementById('modal-proxy-title').textContent = 'Добавить прокси';
  clearProxyForm();
  showModal('modal-proxy');
}

function openEditProxyModal(proxyId) {
  state.editingProxyId = proxyId;
  const proxy = state.proxies.find(p => p.proxyId === proxyId);
  if (!proxy) return;
  document.getElementById('modal-proxy-title').textContent = `Редактировать ${proxy.host}:${proxy.port}`;
  document.getElementById('proxy-ip').value = proxy.host || '';
  document.getElementById('proxy-port').value = proxy.port || '';
  document.getElementById('proxy-username').value = proxy.username || '';
  document.getElementById('proxy-password').value = proxy.password || '';
  hideFieldErrors();
  showModal('modal-proxy');
}

function clearProxyForm() {
  ['proxy-ip', 'proxy-port', 'proxy-username', 'proxy-password'].forEach(id => {
    document.getElementById(id).value = '';
  });
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

async function handleSaveProxy() {
  const ip = document.getElementById('proxy-ip').value.trim();
  const portStr = document.getElementById('proxy-port').value.trim();
  const username = document.getElementById('proxy-username').value.trim();
  const password = document.getElementById('proxy-password').value;
  const port = Number(portStr);

  hideFieldErrors();
  let hasError = false;

  if (!ip) { showFieldError('proxy-ip-error', 'Введите IP адрес'); hasError = true; }
  else if (!isValidIP(ip)) { showFieldError('proxy-ip-error', 'Неверный IP адрес'); hasError = true; }

  if (!portStr) { showFieldError('proxy-port-error', 'Введите порт'); hasError = true; }
  else if (!isValidPort(port)) { showFieldError('proxy-port-error', 'Порт 1-65535'); hasError = true; }

  if (!username) { showFieldError('proxy-username-error', 'Введите логин'); hasError = true; }
  if (!password) { showFieldError('proxy-password-error', 'Введите пароль'); hasError = true; }

  if (hasError) return;

  const saveBtn = document.getElementById('btn-proxy-save');
  setLoading(saveBtn, true);

  try {
    const cfg = await apiGet('/config');

    if (state.editingProxyId) {
      const idx = cfg.proxies.findIndex(p => p.proxyId === state.editingProxyId);
      if (idx !== -1) {
        cfg.proxies[idx] = { ...cfg.proxies[idx], host: ip, port, username, password };
      }
    } else {
      cfg.proxies.push({
        proxyId: crypto.randomUUID(),
        host: ip,
        port,
        username,
        password,
        isEnabled: true,
        isActive: true,
      });
    }

    await apiPost('/config', cfg);
    await loadAndRender();
    closeModal();
  } catch (err) {
    console.error('[FlowLink] Ошибка сохранения:', err);
    showFieldError('proxy-ip-error', err.message);
  } finally {
    setLoading(saveBtn, false);
  }
}

function openAddMaskModal() {
  document.getElementById('mask-input').value = '';
  document.getElementById('mask-error').classList.add('hidden');
  showModal('modal-mask');
}

/* ───── Модал: Маски ───── */

async function openMaskModal(proxyId) {
  state.masksProxyId = proxyId;
  const proxy = state.proxies.find(p => p.proxyId === proxyId);
  const subtitle = document.getElementById('modal-masks-subtitle');
  if (subtitle) subtitle.textContent = proxy ? `Прокси ${proxy.host}:${proxy.port}` : '';
  try {
    await refreshMaskList(proxyId);
  } catch (e) {
    console.error('[FlowLink] Ошибка загрузки масок:', e);
  }
  showModal('modal-masks');
}

async function refreshMaskList(proxyId) {
  const masks = state.masks.filter(m => m.proxyId === proxyId);
  const container = document.getElementById('mask-list');
  const clearBtn = document.getElementById('btn-clear-masks');

  if (masks.length === 0) {
    container.innerHTML = '<div class="empty-state small">Нет масок</div>';
    if (clearBtn) clearBtn.classList.add('hidden');
    return;
  }

  if (clearBtn) clearBtn.classList.remove('hidden');

  container.innerHTML = masks.map(mask => `
    <div class="mask-item" data-mask-id="${mask.maskId}">
      <span class="mask-text">${escapeHtml(mask.regexString)}</span>
      <button class="btn-icon delete-icon mask-delete" data-action="delete-mask" title="Удалить маску">✕</button>
    </div>
  `).join('');

  container.querySelectorAll('.mask-item').forEach(el => {
    const maskId = el.dataset.maskId;
    el.querySelector('[data-action="delete-mask"]')?.addEventListener('click', async () => {
      if (!confirm('Удалить маску?')) return;
      try {
        const cfg = await apiGet('/config');
        cfg.masks = cfg.masks.filter(m => m.maskId !== maskId);
        await apiPost('/config', cfg);
        state.masks = cfg.masks;
        await refreshMaskList(proxyId);
      } catch (err) {
        console.error('[FlowLink] Ошибка удаления маски:', err);
      }
    });
  });
}

async function handleSaveMask() {
  const raw = document.getElementById('mask-input').value.trim();
  const errorEl = document.getElementById('mask-error');
  errorEl.classList.add('hidden');

  if (!raw) {
    errorEl.textContent = 'Заполните поле';
    errorEl.classList.remove('hidden');
    return;
  }

  const regexString = convertWildcardToRegex(raw);

  try {
    new RegExp(regexString);
  } catch {
    errorEl.textContent = 'Неверное регулярное выражение';
    errorEl.classList.remove('hidden');
    return;
  }

  const saveBtn = document.getElementById('btn-mask-save');
  setLoading(saveBtn, true);

  try {
    const cfg = await apiGet('/config');
    cfg.masks.push({
      maskId: crypto.randomUUID(),
      proxyId: state.masksProxyId,
      regexString,
    });
    await apiPost('/config', cfg);
    state.masks = cfg.masks;
    await refreshMaskList(state.masksProxyId);
    document.getElementById('modal-mask').classList.add('hidden');
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove('hidden');
  } finally {
    setLoading(saveBtn, false);
  }
}

/* ───── Настройки: порт API ───── */

async function handleSettingsSave() {
  const input = document.getElementById('settings-api-port');
  const port = Number(input.value);
  const saveBtn = document.getElementById('btn-settings-save');

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    input.focus();
    return;
  }

  setLoading(saveBtn, true);

  try {
    await chrome.storage.local.set({ apiPort: port });
    setApiPort(port);
    document.getElementById('settings-row').classList.add('hidden');
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink] Ошибка сохранения порта:', e);
  } finally {
    setLoading(saveBtn, false);
  }
}

/* ───── Модал: помощь ───── */

const HELP_TEXTS = {
  windows: `
    <h3>1. Скачайте последний релиз</h3>
    <ol>
      <li>Перейдите по ссылке <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub → Releases</a></li>
      <li>Найдите последнюю версию и скачайте <code>FlowLink-Proxy-vX.X.X.zip</code></li>
      <li>Распакуйте ZIP в <strong>отдельную папку</strong> (например <code>C:\\FlowLink\\</code>)</li>
    </ol>
    <h3>2. Запустите gateway</h3>
    <ol>
      <li>Откройте папку и запустите <code>flowlink-gateway.exe</code></li>
      <li>В окне консоли должны появиться строки «Прокси-сервер запущен» и «API сервер запущен»</li>
      <li>Не закрывайте это окно — оно должно быть открыто всё время работы</li>
    </ol>
    <h3>3. Настройте браузер</h3>
    <ol>
      <li>Найдите ярлык браузера → правый клик → <strong>Свойства</strong></li>
      <li>В поле «Объект» допишите <strong>после кавычки</strong>: <code>--proxy-server=127.0.0.1:8080</code></li>
      <li>Пример: <code>"C:\\Program Files\\Yandex\\YandexBrowser\\Application\\browser.exe" --proxy-server=127.0.0.1:8080</code></li>
      <li>Нажмите «Применить» и запускайте браузер только через этот ярлык</li>
    </ol>
    <h3>4. Автозагрузка (чтобы не запускать вручную)</h3>
    <ol>
      <li>Нажмите <code>Win+R</code>, введите <code>shell:startup</code>, нажмите Enter</li>
      <li>Создайте ярлык для <code>flowlink-gateway.exe</code> и поместите его в открывшуюся папку</li>
      <li>Теперь FlowLink будет запускаться автоматически при входе в Windows</li>
    </ol>
  `,
  source: `
    <h3>1. Установите Python 3.10+</h3>
    <ol>
      <li>Скачайте Python с <a href="https://www.python.org/downloads/" target="_blank" rel="noopener">python.org</a></li>
      <li>При установке отметьте «Add Python to PATH»</li>
    </ol>
    <h3>2. Клонируйте репозиторий</h3>
    <ol>
      <li>Откройте терминал (cmd / PowerShell): <code>git clone https://github.com/flowhack/flowlink-proxy.git</code></li>
      <li>Перейдите в папку: <code>cd flowlink-proxy</code></li>
    </ol>
    <h3>3. Установите и запустите</h3>
    <ol>
      <li>Создайте виртуальное окружение: <code>python -m venv venv</code></li>
      <li>Активируйте: <code>venv\\Scripts\\activate</code> (Windows) или <code>source venv/bin/activate</code> (Linux/macOS)</li>
      <li>Установите зависимости: <code>pip install -r server/requirements.txt</code></li>
      <li>Запустите: <code>python -m server</code></li>
    </ol>
    <h3>4. Настройте браузер</h3>
    <ol>
      <li>Добавьте флаг к ярлыку браузера: <code>--proxy-server=127.0.0.1:8080</code></li>
      <li>Инструкция — на вкладке «Windows (.exe)», шаг 3</li>
    </ol>
  `,
  update: (tag) => `
    <h3>Обновление до ${tag}</h3>
    <p>Релиз содержит обновлённый <strong>бэкенд</strong> (Python / .exe) и <strong>расширение</strong> (если используете unpacked).</p>
    <h3>Если используете .exe</h3>
    <ol>
      <li>Скачайте последний релиз со страницы <a href="${GITHUB_RELEASES_URL}" target="_blank" rel="noopener">GitHub Releases</a></li>
      <li>Распакуйте ZIP, замените старый <code>flowlink-gateway.exe</code> новым в вашей папке</li>
      <li>Остановите старый процесс (закройте окно), запустите новый .exe</li>
    </ol>
    <h3>Если используете исходный код</h3>
    <ol>
      <li>Откройте терминал в папке проекта: <code>git pull</code></li>
      <li>Перезапустите: <code>python -m server</code> или <code>./scripts/flowlink.sh</code></li>
    </ol>
    <h3>Обновление расширения</h3>
    <ol>
      <li><strong>Из Chrome Web Store:</strong> расширение обновится автоматически</li>
      <li><strong>Unpacked (режим разработчика):</strong> откройте <code>chrome://extensions</code>, нажмите «Обновить» (круглая стрелка)</li>
    </ol>
    <p><em>Бэкенд и расширение должны быть одной версии. Сначала обновите бэкенд, потом расширение.</em></p>
  `,
};

function openHelpModal(tab) {
  const isWindows = navigator.platform.includes('Win');
  const defaultTab = isWindows ? 'windows' : 'source';
  switchHelpTab(tab || defaultTab);
  showModal('modal-help');
}

function switchHelpTab(tab) {
  const tabsContainer = document.getElementById('modal-tabs');
  document.getElementById('tab-windows').classList.toggle('tab-active', tab === 'windows');
  document.getElementById('tab-source').classList.toggle('tab-active', tab === 'source');
  tabsContainer.classList.toggle('hidden', tab === 'update');
  const container = document.getElementById('help-content');
  if (tab === 'update') {
    const tag = document.getElementById('update-text').textContent.replace('Доступно обновление ', '');
    container.innerHTML = HELP_TEXTS.update(tag);
  } else {
    container.innerHTML = HELP_TEXTS[tab];
  }
}

/* ───── Модалки ───── */

function showModal(id) {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function closeModal() {
  document.querySelectorAll('.modal-overlay').forEach(el => el.classList.add('hidden'));
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ───── Текущий сайт (статус-бар) ───── */
async function renderTabStatus(url) {
  try {
    const matchedMask = state.masks.find(m => {
      try { return new RegExp(m.regexString).test(url); } catch { return false; }
    });
    const bar = document.getElementById('status-bar');
    const icon = document.getElementById('status-icon');
    const text = document.getElementById('status-text');
    if (matchedMask) {
      const proxy = state.proxies.find(p => p.proxyId === matchedMask.proxyId);
      bar.classList.remove('hidden');
      icon.style.color = 'var(--accent-green)';
      text.textContent = `Через SOCKS5 (${proxy ? proxy.host : ''})`;
      text.style.color = 'var(--accent-green)';
    } else {
      bar.classList.remove('hidden');
      icon.style.color = 'var(--accent-green)';
      text.textContent = 'Напрямую';
      text.style.color = 'var(--accent-green)';
    }
  } catch (e) {
    console.warn('[FlowLink] Ошибка статуса вкладки:', e);
  }
}
