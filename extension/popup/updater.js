/**
 * @fileoverview
 * Проверка обновлений и версии бэкенда.
 * Единственная ответственность: обновления.
 */

import { apiGet } from '../shared/api.js';
import { compareVersions } from '../shared/utils.js';
import { GITHUB_API_RELEASES, GITHUB_RELEASES_URL } from '../shared/constants.js';

let backendVersion = null;

/** Тег последнего доступного обновления (например 'v0.1.0') или пустая строка. */
let latestTag = null;

/** Флаг: подсказка про VPN/прокси уже показана (не спамим). */
let _vpnHintShown = false;

export { backendVersion, latestTag };

/**
 * Запрашивает версию бэкенда через /api/version.
 * Если версия бэкенда отличается от версии расширения — отображает обе.
 * @returns {Promise<boolean>} — true, если бэкенд ответил.
 */
export async function checkBackendVersion() {
  try {
    const resp = await apiGet('/version');
    backendVersion = resp.version;
    const extVer = document.getElementById('version-text');
    const extVersion = chrome.runtime.getManifest().version;
    if (extVer && resp.version && resp.version !== extVersion) {
      extVer.textContent = `Версия: ${chrome.runtime.getManifest().version} (бэкенд: ${resp.version})`;
    }
    return true;
  } catch (e) {
    console.warn('[FlowLink Proxy] Ошибка проверки версии бэкенда:', e);
    return false;
  }
}

/**
 * Проверяет GitHub API на наличие новой версии.
 * Если последний релиз новее текущей — показывает баннер с предложением обновления.
 * @param {boolean} [simulate=false] — если true, показывает баннер без обращения к GitHub.
 * @param {string} [simulateVersion=''] — версия для отображения в режиме симуляции.
 */
export async function checkForUpdates(simulate = false, simulateVersion = '') {
  if (simulate) {
    const tag = simulateVersion
      ? (simulateVersion.startsWith('v') ? simulateVersion : `v${simulateVersion}`)
      : 'v0.0.0';
    latestTag = tag;
    showUpdateBanner(tag, GITHUB_RELEASES_URL);
    return;
  }
  try {
    // Таймаут 8 секунд: при недоступности GitHub не блокируем popup
    const resp = await fetch(GITHUB_API_RELEASES, {
      signal: AbortSignal.timeout(8000),
    });
    if (!resp.ok) {
      _showVpnHint();
      return;
    }
    const release = await resp.json();
    latestTag = release.tag_name || '';
    if (!latestTag) return;
    if (backendVersion === null) return;
    const latestVer = latestTag.replace(/^v/, '');
    const currentVer = backendVersion || '0.0.0';
    if (compareVersions(latestVer, currentVer) > 0) {
      showUpdateBanner(latestTag, release.html_url);
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Ошибка проверки обновлений GitHub:', e);
    // GitHub может быть заблокирован (например, в РФ) — подсказываем про VPN
    _showVpnHint();
  }
}

/**
 * Показывает подсказку про VPN/прокси при недоступности GitHub API.
 * Показывается один раз за сессию, чтобы не спамить пользователя.
 */
function _showVpnHint() {
  if (_vpnHintShown) return;
  _vpnHintShown = true;
  try {
    const showToast = window.__flowlinkShowToast;
    if (typeof showToast === 'function') {
      showToast(
        'Не удалось проверить обновления. Возможно, GitHub заблокирован — используйте VPN или прокси.',
        'warning',
      );
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Не удалось показать подсказку про VPN:', e);
  }
}

/**
 * Отображает баннер с информацией о доступном обновлении.
 * @param {string} tag — тег релиза (например 'v0.1.0').
 * @param {string} url — URL релиза на GitHub.
 */
function showUpdateBanner(tag, url) {
  const banner = document.getElementById('update-banner');
  const updateText = document.getElementById('update-text');
  const downloadBtn = document.getElementById('btn-update-download');
  if (!banner || !updateText || !downloadBtn) return;
  if (!url || typeof url !== 'string' || !url.startsWith('https://')) return;
  updateText.textContent = `Доступно обновление ${tag}`;
  downloadBtn.href = url;
  banner.classList.remove('hidden');
}
