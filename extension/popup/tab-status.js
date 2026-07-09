/**
 * @fileoverview
 * Отображение статуса текущей вкладки (через SOCKS5 или напрямую).
 * Единственная ответственность: проверка URL вкладки по маскам.
 */

/**
 * Проверяет URL активной вкладки по маскам и отображает статус (через прокси или напрямую).
 * @param {string} url — URL активной вкладки.
 * @param {object} state — глобальное состояние popup (state.masks, state.proxies).
 */
export async function renderTabStatus(url, state) {
  try {
    // Ищем первую маску, под которую попадает URL вкладки
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
      text.textContent = `Через SOCKS5 (${proxy ? proxy.host : 'неизвестно'})`;
      text.style.color = 'var(--accent-green)';
    } else {
      bar.classList.remove('hidden');
      icon.style.color = 'var(--accent-green)';
      text.textContent = 'Напрямую';
      text.style.color = 'var(--accent-green)';
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Ошибка статуса вкладки:', e);
  }
}
