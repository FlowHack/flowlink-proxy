/**
 * @fileoverview
 * Отображение статуса текущей вкладки (через SOCKS5 или напрямую).
 * Единственная ответственность: проверка URL вкладки по маскам.
 */

import { t } from '../shared/i18n.js';
import { convertWildcardToRegex } from '../shared/utils.js';

/**
 * Проверяет URL активной вкладки по маскам и отображает статус (через прокси или напрямую).
 * @param {string} url — URL активной вкладки.
 * @param {object} state — глобальное состояние popup (state.masks, state.proxies, state.enabled).
 */
export async function renderTabStatus(url, state) {
  try {
    const bar = document.getElementById('status-bar');
    const icon = document.getElementById('status-icon');
    const text = document.getElementById('status-text');
    if (!bar || !icon || !text) return;
    if (!state.enabled) {
      bar.classList.remove('hidden');
      icon.style.color = 'var(--accent-orange)';
      text.textContent = t('disabled');
      text.style.color = 'var(--accent-orange)';
      return;
    }
    // Ищем первую маску, под которую попадает URL вкладки
    const matchedMask = state.masks.find(m => {
      // Regex пересобираем из pattern через convertWildcardToRegex: она
      // ограничивает длину паттерна (255 символов), что исключает ReDoS даже
      // при ручном редактировании config.json. Значению regexString из конфига
      // не доверяем (оно может содержать произвольный regex).
      if (typeof m.pattern !== 'string' || !m.pattern) {
        return false;
      }
      try {
        return new RegExp(convertWildcardToRegex(m.pattern)).test(url);
      } catch (e) {
        // Невалидный паттерн — маска не матчится, но не роняем popup
        console.warn('[FlowLink Proxy] Невалидный паттерн маски:', m.pattern, e);
        return false;
      }
    });
    if (matchedMask) {
      const proxy = state.proxies.find(p => p.proxyId === matchedMask.proxyId);
      bar.classList.remove('hidden');
      icon.style.color = 'var(--accent-green)';
      text.textContent = t('viaSocks5', { host: proxy ? proxy.host : t('unknown') });
      text.style.color = 'var(--accent-green)';
    } else {
      bar.classList.remove('hidden');
      icon.style.color = 'var(--accent-green)';
      text.textContent = t('direct');
      text.style.color = 'var(--accent-green)';
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Ошибка статуса вкладки:', e);
  }
}