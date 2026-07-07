/**
 * @fileoverview
 * Контроллер прокси-маршрутизации FlowLink Proxy.
 * Управляет динамическим PAC-скриптом, кэшем масок, состоянием failover
 * и фоновым Health Check для обеспечения Strict Proxy Policy.
 */

import { MaskCache } from './mask-cache.js';

/** Имя константы для chrome.alarms */
const HEALTH_CHECK_ALARM = 'flowlink-health-check';

/** Таймаут Health Check в миллисекундах */
const HC_TIMEOUT_MS = 5000;

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

    /** @private {string|null} Текущий PAC-скрипт для восстановления после Health Check */
    this._currentPacScript = null;

    /** @private {boolean} Флаг, предотвращающий параллельные Health Check */
    this._healthCheckInProgress = false;

    /** @private {Promise<void>|null} Промис текущей пересборки */
    this._rebuildPromise = null;

    /** @private {Promise<void>|null} Замок для _testProxy — предотвращает конкурентные тесты PAC */
    this._testProxyLock = null;
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
      await this._rebuildAll();

      /* Регистрируем периодический Health Check (каждые 30 секунд) */
      chrome.alarms.create(HEALTH_CHECK_ALARM, { periodInMinutes: 0.5 });

      this._ready = true;
    } catch (error) {
      console.error('[FlowLink] Ошибка инициализации ProxyController:', error);
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

        /* Инициализируем failoverState из isActive */
        this._failoverState.clear();
        for (const proxy of proxies) {
          if (!proxy.isActive) {
            this._failoverState.set(proxy.proxyId, true);
          }
        }

        /* Строим и применяем PAC-скрипт */
        await this._buildAndApplyPac();
      })();

      await this._rebuildPromise;
    } catch (rebuildError) {
      console.error('[FlowLink] Ошибка пересборки PAC:', rebuildError);
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
      console.error('[FlowLink] Ошибка применения PAC-скрипта:', error);
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
      console.error('[FlowLink] Ошибка отключения прокси:', error);
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
    this._dc.updateProxy(proxyId, { isActive: false }).catch(() => {});

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

    this._dc.updateProxy(proxyId, { isActive: true }).catch(() => {});

    this._showNotification(proxyId, false);
    await this._buildAndApplyPac();
  }

  /* ───── Health Check ───── */

  /**
   * Запускает проверку всех прокси (активных и заблокированных).
   * Вызывается по аларму каждые 30 секунд.
   * - Заблокированные прокси: если тест успешен → восстановление.
   * - Активные прокси: если тест не удался → failover (блокировка).
   * Предотвращает параллельные запуски через _healthCheckInProgress.
   */
  async runHealthCheck() {
    if (this._healthCheckInProgress) return;
    if (!this._ready) return;
    this._healthCheckInProgress = true;

    try {
      const proxies = await this._dc.getAllProxies();
      if (!proxies || proxies.length === 0) return;

      for (const proxy of proxies) {
        const proxyId = proxy.proxyId;
        const isBlocked = this._failoverState.get(proxyId) || false;

        const proxyConfig = this._maskCache.getProxyConfig(proxyId);
        if (!proxyConfig) continue;

        const isAlive = await this._testProxy(proxyConfig.host, proxyConfig.port);

        if (isBlocked && isAlive) {
          /* Был заблокирован — теперь доступен */
          await this._handleRecovery(proxyId);
        } else if (!isBlocked && !isAlive) {
          /* Был активен — теперь недоступен */
          await this.handleFailover(proxyId);
        }
      }
    } catch (error) {
      console.error('[FlowLink] Ошибка Health Check:', error);
    } finally {
      this._healthCheckInProgress = false;
    }
  }

  /**
   * @private Проверяет доступность прокси через fetch с таймаутом.
   *
   * Временно устанавливает минимальный PAC-скрипт, направляющий
   * http://detectportal.firefox.com/success.txt через целевой прокси.
   * После проверки восстанавливает основной PAC-скрипт.
   *
   * Использует AbortController для принудительного таймаута в 5 секунд.
   *
   * @param {string} host - IP прокси-сервера.
   * @param {number} port - Порт прокси-сервера.
   * @returns {Promise<boolean>} true, если прокси доступен.
   */
  async _testProxy(host, port) {
    /* Ожидаем освобождения замка (последовательный доступ к PAC) */
    while (this._testProxyLock) {
      await this._testProxyLock;
    }

    const testPacScript = [
      'function FindProxyForURL(url, host) {',
      `  if (host === 'detectportal.firefox.com') return 'SOCKS5 ${host}:${port}';`,
      "  return 'DIRECT';",
      '}'
    ].join('\n');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), HC_TIMEOUT_MS);

    /** Устанавливаем замок — сохраняем промис текущего теста */
    this._testProxyLock = (async () => {
      try {
        /* Временно применяем тестовый PAC */
        await chrome.proxy.settings.set({
          value: {
            mode: 'pac_script',
            pacScript: { data: testPacScript }
          },
          scope: 'regular'
        });

        const response = await fetch(
          'http://detectportal.firefox.com/success.txt',
          { signal: controller.signal }
        );

        return response.ok;
      } catch {
        return false;
      } finally {
        clearTimeout(timeoutId);
        /* Восстанавливаем основной PAC (с try/catch, чтобы не потерять тестовый PAC) */
        try {
          await this._applyCurrentPac();
        } catch (restoreError) {
          console.error('[FlowLink] Ошибка восстановления PAC после теста:', restoreError);
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
        iconUrl: 'icons/icon48.png',
        title: 'FlowLink Proxy — Внимание',
        message
      });
    } catch (error) {
      console.warn('[FlowLink] Ошибка показа уведомления:', error);
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
