/**
 * @fileoverview
 * Пинг прокси-серверов.
 * Единственная ответственность: проверка доступности SOCKS5 прокси через API.
 */

import { apiPost } from '../shared/api.js';
import { setLoading } from '../shared/utils.js';

/**
 * Пингует все прокси из state.proxies последовательно.
 * Результаты сохраняются в state.pingResults, после чего вызывается renderProxyList().
 * @param {object} state — глобальное состояние popup.
 * @param {Function} renderProxyList — функция перерисовки списка прокси.
 */
export async function handlePingAll(state, renderProxyList) {
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

  renderProxyList();
  setLoading(btn, false);
  btn.textContent = 'Пинг';
}
