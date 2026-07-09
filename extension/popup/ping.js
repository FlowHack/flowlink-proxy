/**
 * @fileoverview
 * Пинг прокси-серверов.
 * Единственная ответственность: проверка доступности SOCKS5 прокси через API.
 */

import { apiPost } from '../shared/api.js';
import { setLoading } from '../shared/utils.js';

/**
 * Пингует все прокси из state.proxies параллельно через Promise.allSettled.
 * Результаты сохраняются в state.pingResults, после чего вызывается renderProxyList().
 * @param {object} state — глобальное состояние popup.
 * @param {Function} renderProxyList — функция перерисовки списка прокси.
 */
export async function handlePingAll(state, renderProxyList) {
  const btn = document.getElementById('btn-ping-all');
  if (!btn) return;
  setLoading(btn, true);
  btn.textContent = 'Проверка...';
  state.pingResults.clear();

  const results = await Promise.allSettled(
    state.proxies.map(p =>
      apiPost('/ping', { proxyId: p.proxyId })
        .then(result => ({ proxyId: p.proxyId, alive: result.alive, latency: result.latency }))
        .catch(() => ({ proxyId: p.proxyId, alive: false, latency: null }))
    )
  );

  for (const r of results) {
    if (r.status === 'fulfilled') {
      state.pingResults.set(r.value.proxyId, { alive: r.value.alive, latency: r.value.latency });
    }
  }

  renderProxyList();
  setLoading(btn, false);
  btn.textContent = 'Пинг';
}
