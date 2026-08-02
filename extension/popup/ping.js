/**
 * @fileoverview
 * Пинг прокси-серверов.
 * Единственная ответственность: проверка доступности SOCKS5 прокси через API.
 */

import { apiPost } from '../shared/api.js';
import { setLoading } from '../shared/utils.js';

/** Флаг: подсказка про блокировку прокси уже показана (не спамим). */
let _blockHintShown = false;

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
        .then(result => ({ proxyId: p.proxyId, alive: result.alive, latency: result.latency, errorKind: result.errorKind }))
        .catch(() => ({ proxyId: p.proxyId, alive: false, latency: null, errorKind: null }))
    )
  );

  let blockedCount = 0;
  let totalCount = 0;
  for (const r of results) {
    if (r.status === 'fulfilled') {
      const value = r.value;
      state.pingResults.set(value.proxyId, { alive: value.alive, latency: value.latency });
      totalCount++;
      // timeout/reset — признаки блокировки (DPI, файрвол, недоступность из РФ)
      if (!value.alive && (value.errorKind === 'timeout' || value.errorKind === 'reset')) {
        blockedCount++;
      }
    }
  }

  renderProxyList();
  setLoading(btn, false);
  btn.textContent = 'Пинг';

  // При массовом отказе с признаками блокировки — подсказываем про VPN/прокси
  if (totalCount > 0 && blockedCount > 0 && blockedCount / totalCount >= 0.5) {
    _showBlockHint();
  }
}

/**
 * Показывает подсказку про возможную блокировку прокси.
 * Показывается один раз за сессию, чтобы не спамить пользователя.
 */
function _showBlockHint() {
  if (_blockHintShown) return;
  _blockHintShown = true;
  try {
    const showToast = window.__flowlinkShowToast;
    if (typeof showToast === 'function') {
      showToast(
        'Прокси не отвечают (таймаут/сброс). Возможно, соединение блокируется провайдером — используйте VPN или другой прокси.',
        'warning',
      );
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] Не удалось показать подсказку про блокировку:', e);
  }
}
