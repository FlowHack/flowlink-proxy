/**
 * @fileoverview
 * Контроллер прокси-маршрутизации FlowLink Proxy.
 * Управляет динамическим PAC-скриптом, кэшем масок и состоянием failover
 * для обеспечения Strict Proxy Policy.
 */

import { MaskCache } from './mask-cache.js';

/** Таймаут пинга прокси в миллисекундах */
const PING_TIMEOUT_MS = 5000;

/**
 * Контроллер прокси — центральный компонент сетевого стека.
 * Отвечает за:
 * - Построение и применение динамического PAC-скрипта на основе масок
 * - Синхронный кэш масок (MaskCache) для быстрой маршрутизации
 * - Strict Proxy Policy (блокировка CANCEL при недоступном прокси)
 * - Фоновый Health Check через chrome.alarms
 * - Оповещение пользователя через chrome.notifications
 */
class ProxyController {
  constructor() {
    /** @private {MaskCache} */
    this._maskCache = new MaskCache();

    /** @private {DataController|null} */
    this._dc = null;

    /**
     * @private {Map<string, boolean>}
     * Карта заблокированных прокси: proxyId → true/false.
     * true — прокси недоступен, трафик блокируется.
     */
    this._failoverState = new Map();

    /** @private {boolean} Глобальное состояние расширения */
    this._extensionEnabled = true;

    /** @private {boolean} Флаг готовности */
    this._ready = false;

    /** @private {string|null} Текущий PAC-скрипт для восстановления после пинга */
    this._currentPacScript = null;

    /** @private {Promise<void>|null} Промис текущей пересборки */
    this._rebuildPromise = null;

    /** @private {Promise<void>|null} Замок для _testProxy — предотвращает конкурентные тесты PAC */
    this._testProxyLock = null;

    /** @private {number|null} Safety timer для автовосстановления PAC после пинга из popup */
    this._pingSafetyTimer = null;
  }

  /* ───── Инициализация ───── */

  /**
   * Инициализация ProxyController после DataController.
   * Загружает прокси и маски, строит кэш, применяет PAC-скрипт
   * и регистрирует периодический Health Check.
   *
   * @param {DataController} dataController - Инициализированный DataController.
   */
  async init(dataController) {
    this._dc = dataController;

    try {
      /* Загружаем начальное состояние */
      this._extensionEnabled = await this._dc.getExtensionStatus();

      /* Инициализируем failoverState из isActive (только при старте — чтобы не сбросить
       * блокировку при конкурентном handleFailover во время refresh) */
      const allProxies = await this._dc.getAllProxies();
      this._failoverState.clear();
      for (const proxy of allProxies) {
        if (!proxy.isActive) {
          this._failoverState.set(proxy.proxyId, true);
        }
      }

      await this._rebuildAll();

      this._ready = true;
    } catch (error) {
      console.error('[FlowLink Proxy] Ошибка инициализации ProxyController:', error);
      throw error;
    }
  }

  /**
   * Полный пересбор кэша и PAC-скрипта.
   * Вызывается при изменении данных (добавление/удаление прокси или масок).
   */
  async refresh() {
    if (!this._ready) return;
    await this._rebuildAll();
  }

  /**
   * @private Полная пересборка: загрузка данных → кэш → PAC-скрипт.
   * Если пересборка уже выполняется, текущий вызов дожидается её завершения,
   * затем запускается снова (чтобы гарантировать актуальность данных).
   */
  async _rebuildAll() {
    /**
     * Весь код в try/catch — если concurrent вызов await'ит rejected promise
     * из while, ошибка не улетает в refresh()/message-router, а логируется здесь.
     */
    try {
      /* Ожидаем завершения текущей пересборки, если она идёт */
      while (this._rebuildPromise) {
        await this._rebuildPromise;
      }

      this._rebuildPromise = (async () => {
        const proxies = await this._dc.getAllProxies();
        const masks = await this._dc.getAllMasks();

        /* Строим кэш только из включённых прокси */
        const enabledProxies = proxies.filter(p => p.isEnabled);
        this._maskCache.build(enabledProxies, masks);

        /* Очищаем устаревшие записи failover (для удалённых прокси) */
        const activeProxyIds = new Set(proxies.map(p => p.proxyId));
        for (const proxyId of this._failoverState.keys()) {
          if (!activeProxyIds.has(proxyId)) {
            this._failoverState.delete(proxyId);
          }
        }

        /* Строим и применяем PAC-скрипт */
        await this._buildAndApplyPac();
      })();

      await this._rebuildPromise;
    } catch (rebuildError) {
      console.error('[FlowLink Proxy] Ошибка пересборки PAC:', rebuildError);
    } finally {
      this._rebuildPromise = null;
    }
  }

  /* ───── PAC-скрипт ───── */

  /**
   * @private Строит PAC-скрипт из текущего кэша и применяет его.
   */
  async _buildAndApplyPac() {
    const pacScript = this._buildPacScript();
    this._currentPacScript = pacScript;
    await this._applyPacScript(pacScript);
  }

  /**
   * @private Генерирует PAC-скрипт с встроенными правилами маршрутизации.
   * Использует JSON.stringify для безопасной сериализации данных (защита от инъекций).
   * Неблокированные прокси располагаются первыми для приоритетной маршрутизации.
   *
   * @returns {string} Код PAC-скрипта.
   */
  _buildPacScript() {
    const ruleEntries = this._maskCache.rules.map(r => ({
      p: r.regexString,
      h: r.host,
      pt: r.port,
      b: this._failoverState.get(r.proxyId) || false
    }));

    /* Сортируем: неблокированные правила первыми */
    ruleEntries.sort((a, b) => (a.b ? 1 : 0) - (b.b ? 1 : 0));

    const rulesJson = JSON.stringify(ruleEntries);
    const enabledJson = JSON.stringify(this._extensionEnabled);

    return [
      `var RULES = ${rulesJson};`,
      `var ENABLED = ${enabledJson};`,
      '',
      'function FindProxyForURL(url, host) {',
      '  if (!ENABLED) return \'DIRECT\';',
      '  for (var i = 0; i < RULES.length; i++) {',
      '    var r = RULES[i];',
      '    try {',
      '      if (!new RegExp(r.p).test(url)) continue;',
      '    } catch(e) { continue; }',
      '    if (r.b) return \'PROXY 0.0.0.0:9\';',
      '    return \'SOCKS5 \' + r.h + \':\' + r.pt;',
      '  }',
      '  return \'DIRECT\';',
      '}'
    ].join('\n');
  }

  /**
   * @private Применяет PAC-скрипт через chrome.proxy.settings.
   * @param {string} pacScript - Код PAC-скрипта.
   */
  async _applyPacScript(pacScript) {
    try {
      await chrome.proxy.settings.set({
        value: {
          mode: 'pac_script',
          pacScript: { data: pacScript }
        },
        scope: 'regular'
      });
    } catch (error) {
      console.error('[FlowLink Proxy] Ошибка применения PAC-скрипта:', error);
    }
  }

  /**
   * @private Восстанавливает текущий PAC-скрипт (используется после Health Check).
   */
  async _applyCurrentPac() {
    if (this._currentPacScript) {
      await this._applyPacScript(this._currentPacScript);
    } else {
      await this._disableProxy();
    }
  }

  /**
   * @private Отключает прокси — переключает в режим system (DIRECT).
   */
  async _disableProxy() {
    /* При отключении очищаем кэш PAC, чтобы _applyCurrentPac() не восстановил старый */
    this._currentPacScript = null;
    try {
      await chrome.proxy.settings.set({
        value: { mode: 'system' },
        scope: 'regular'
      });
    } catch (error) {
      console.error('[FlowLink Proxy] Ошибка отключения прокси:', error);
    }
  }

  /* ───── Управление состоянием расширения ───── */

  /**
   * Включает или выключает расширение.
   * При выключении переключает прокси в system (DIRECT).
   * При включении восстанавливает PAC-скрипт.
   *
   * @param {boolean} enabled - Новое состояние.
   */
  async setExtensionEnabled(enabled) {
    this._extensionEnabled = enabled;
    await this._dc.setExtensionStatus(enabled);

    if (enabled) {
      await this._buildAndApplyPac();
    } else {
      await this._disableProxy();
    }
  }

  /* ───── Ping из popup (временная установка прокси) ───── */

  /**
   * Временно устанавливает фиксированный SOCKS5 прокси для пинга из popup.
   * После вызова restoreProxy() или через 10 секунд safety timer
   * восстанавливает основной PAC-скрипт.
   *
   * @param {string} host - IP прокси.
   * @param {number} port - Порт прокси.
   */
  async setTestProxy(host, port) {
    /* Отменяем предыдущий safety timer, если есть */
    if (this._pingSafetyTimer) {
      clearTimeout(this._pingSafetyTimer);
      this._pingSafetyTimer = null;
    }

    try {
      await chrome.proxy.settings.set({
        value: {
          mode: 'fixed_servers',
          rules: {
            singleProxy: {
              scheme: 'socks5',
              host,
              port
            }
          }
        },
        scope: 'regular'
      });
    } catch (error) {
      console.error('[FlowLink Proxy] Ошибка установки тестового прокси:', error);
    }

    /* Safety timer: автовосстановление через 10 секунд */
    this._pingSafetyTimer = setTimeout(() => {
      this._pingSafetyTimer = null;
      this.restoreProxy();
    }, 10000);
  }

  /**
   * Восстанавливает основной PAC-скрипт после пинга из popup.
   * Отменяет safety timer.
   */
  async restoreProxy() {
    if (this._pingSafetyTimer) {
      clearTimeout(this._pingSafetyTimer);
      this._pingSafetyTimer = null;
    }
    await this._applyCurrentPac();
  }

  /* ───── Failover ───── */

  /**
   * Обрабатывает отказ прокси: блокирует, уведомляет, обновляет PAC.
   * Guard от повторного вызова — если прокси уже заблокирован, ничего не делает.
   * @param {string} proxyId - UUID отказавшего прокси.
   */
  async handleFailover(proxyId) {
    if (this._failoverState.get(proxyId)) return; /* Уже заблокирован */
    this._failoverState.set(proxyId, true);

    /* Асинхронно сохраняем статус в DataController */
    this._dc.updateProxy(proxyId, { isActive: false }).catch(err => {
      console.warn('[FlowLink Proxy] Не удалось сохранить статус failover:', err);
    });

    this._showNotification(proxyId, true);
    await this._buildAndApplyPac();
  }

  /**
   * @private Обрабатывает восстановление прокси: разблокирует, уведомляет, обновляет PAC.
   * Guard от повторного вызова — если прокси уже активен, ничего не делает.
   * @param {string} proxyId - UUID восстановленного прокси.
   */
  async _handleRecovery(proxyId) {
    if (!this._failoverState.get(proxyId)) return; /* Уже активен */
    this._failoverState.set(proxyId, false);

    this._dc.updateProxy(proxyId, { isActive: true }).catch(err => {
      console.warn('[FlowLink Proxy] Не удалось сохранить статус восстановления:', err);
    });

    this._showNotification(proxyId, false);
    await this._buildAndApplyPac();
  }

  /* ───── Health Check (удалён — заменён событийным пингом) ───── */

  /* ───── Тест прокси через реальную вкладку браузера ───── */

  /**
   * @private Создаёт временную вкладку и навигирует на тестовый URL.
   * Вкладка — полноценный browser request, который:
   * - Уважает chrome.proxy.settings
   * - Использует кэшированные credentials SOCKS5 (или показывает диалог Chrome)
   *
   * @returns {Promise<boolean>} true, если тест пройден.
   */
  async _testProxyViaTab() {
    const TEST_URL = 'https://connectivitycheck.gstatic.com/generate_204';

    return new Promise((resolve) => {
      let settled = false;
      let targetTabId = null;
      let timeoutId = null;

      /**
       * Регистрируем onUpdated ДО создания вкладки, чтобы не пропустить
       * событие complete, если Chrome обработает навигацию быстрее колбэка create.
       */
      function onUpdated(tabId, changeInfo, tabInfo) {
        if (settled) return;
        /* Пропускаем about:blank и вкладки без URL */
        if (!tabInfo.url || tabInfo.url === 'about:blank') return;

        /* Если targetTabId ещё не назначен, идентифицируем вкладку по URL */
        if (targetTabId === null) {
          if (tabInfo.url === TEST_URL) targetTabId = tabId;
          else return;
        }
        if (tabId !== targetTabId || changeInfo.status !== 'complete') return;

        /* Проверяем, что итоговый URL — наш тестовый (успех), а не страница ошибки */
        if (tabInfo.url !== TEST_URL) return;

        settled = true;
        chrome.tabs.onUpdated.removeListener(onUpdated);
        if (timeoutId) clearTimeout(timeoutId);
        /* Вкладка успешно загрузила тестовый URL — прокси работает */
        chrome.tabs.remove(tabId).catch(() => {});
        resolve(true);
      }

      chrome.tabs.onUpdated.addListener(onUpdated);

      chrome.tabs.create({ url: TEST_URL, active: false }, (tab) => {
        if (chrome.runtime.lastError) {
          settled = true;
          chrome.tabs.onUpdated.removeListener(onUpdated);
          resolve(false);
          return;
        }

        targetTabId = tab.id;

        timeoutId = setTimeout(() => {
          if (settled) return;
          settled = true;
          chrome.tabs.onUpdated.removeListener(onUpdated);
          chrome.tabs.remove(targetTabId).catch(() => {});
          resolve(false);
        }, PING_TIMEOUT_MS);
      });
    });
  }

  /**
   * @private Проверяет доступность прокси через реальную вкладку браузера.
   *
   * Временно устанавливает фиксированный SOCKS5 прокси
   * (fixed_servers) для всего трафика.
   * После проверки восстанавливает основной PAC-скрипт.
   *
   * Вкладка браузера — единственный способ выполнить запрос,
   * который гарантированно проходит через chrome.proxy.settings
   * и корректно обрабатывает SOCKS5-аутентификацию (через диалог Chrome).
   *
   * @param {string} host - IP прокси-сервера.
   * @param {number} port - Порт прокси-сервера.
   * @returns {Promise<boolean>} true, если прокси доступен.
   */
  async _testProxy(host, port) {
    /* Если расширение выключено — не пингуем */
    if (!this._extensionEnabled) return false;
    /* Если popup тестирует прокси, не трогаем настройки — пропускаем */
    if (this._pingSafetyTimer) return false;

    /* Ожидаем освобождения замка (последовательный доступ к PAC) */
    while (this._testProxyLock) {
      await this._testProxyLock;
    }

    /** Устанавливаем замок — сохраняем промис текущего теста */
    this._testProxyLock = (async () => {
      try {
        /* Временно применяем фиксированный SOCKS5 прокси (без PAC) */
        await chrome.proxy.settings.set({
          value: {
            mode: 'fixed_servers',
            rules: {
              singleProxy: {
                scheme: 'socks5',
                host,
                port
              }
            }
          },
          scope: 'regular'
        });

        /* Небольшая задержка для применения прокси */
        await new Promise(r => setTimeout(r, 100));

        /* Тест через реальную вкладку браузера */
        const result = await this._testProxyViaTab();

        return result;
      } catch (err) {
        console.warn('[FlowLink Proxy] Ошибка теста прокси:', err);
        return false;
      } finally {
        /* Восстанавливаем основной PAC */
        try {
          await this._applyCurrentPac();
        } catch (restoreError) {
          console.error('[FlowLink Proxy] Ошибка восстановления прокси после теста:', restoreError);
        }
      }
    })();

    try {
      return await this._testProxyLock;
    } finally {
      this._testProxyLock = null;
    }
  }

  /* ───── Уведомления ───── */

  /**
   * @private Показывает уведомление пользователю через chrome.notifications.
   * При блокировке: сообщает о недоступности прокси.
   * При восстановлении: сообщает о доступности прокси.
   *
   * @param {string} proxyId - UUID прокси.
   * @param {boolean} blocked - true = блокировка, false = восстановление.
   */
  async _showNotification(proxyId, blocked) {
    const config = this._maskCache.getProxyConfig(proxyId);
    const host = config ? config.host : proxyId;

    const message = blocked
      ? `Прокси-сервер ${host} недоступен. Соединение заблокировано в целях безопасности.`
      : `Прокси-сервер ${host} снова доступен. Соединение восстановлено.`;

    try {
      await chrome.notifications.create(`flowlink-failover-${proxyId}`, {
        type: 'basic',
        iconUrl: chrome.runtime.getURL('icons/icon48.png'),
        title: 'FlowLink Proxy — Внимание',
        message
      });
    } catch (error) {
      console.warn('[FlowLink Proxy] Ошибка показа уведомления:', error);
    }
  }

  /* ───── Ping (для UI) ───── */

  /**
   * Выполняет ping указанного прокси и возвращает результат.
   * Не меняет failoverState — только диагностика.
   * Использует _testProxy() для проверки и замеряет время ответа.
   *
   * @param {string} proxyId - UUID прокси.
   * @returns {Promise<{proxyId: string, alive: boolean, latency: number|null}>}
   */
  async pingProxy(proxyId) {
    const proxy = await this._dc.getProxy(proxyId);
    if (!proxy) throw new Error(`Прокси с ID ${proxyId} не найден`);
    if (!this._extensionEnabled) return { proxyId, alive: false, latency: null };

    const startTime = performance.now();
    const alive = await this._testProxy(proxy.host, proxy.port);
    const latency = alive ? Math.round(performance.now() - startTime) : null;

    return { proxyId, alive, latency };
  }

  /**
   * Выполняет ping для всех прокси.
   * @returns {Promise<Array<{proxyId: string, alive: boolean, latency: number|null}>>}
   */
  async pingAllProxies() {
    const proxies = await this._dc.getAllProxies();
    const results = [];
    for (const proxy of proxies) {
      const result = await this.pingProxy(proxy.proxyId);
      results.push(result);
    }
    return results;
  }

  /* ───── Публичные геттеры для интеграции с UI ───── */

  /**
   * Возвращает состояние failover для указанного прокси.
   * @param {string} proxyId
   * @returns {boolean} true, если прокси заблокирован.
   */
  isProxyBlocked(proxyId) {
    return this._failoverState.get(proxyId) || false;
  }

  /** @returns {boolean} Расширение включено. */
  get extensionEnabled() {
    return this._extensionEnabled;
  }

  /** @returns {MaskCache} Ссылка на кэш масок. */
  get maskCache() {
    return this._maskCache;
  }
}

export { ProxyController };
