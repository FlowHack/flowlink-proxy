/**
 * @fileoverview
 * Кэш масок в памяти (Memory Cache) для синхронного поиска совпадений.
 * Хранит предкомпилированные RegExp, сгруппированные по proxyId.
 * Используется внутри onRequest (синхронно) и для генерации PAC-скрипта.
 */

/**
 * Кэш масок — синхронное хранилище скомпилированных RegExp и конфигураций прокси.
 * Метод build() собирает данные из сырых массивов ProxyTable и MaskTable.
 * findMatch() выполняет синхронный линейный поиск по плоскому списку правил.
 */
class MaskCache {
  constructor() {
    /** @private Map<string, {host: string, port: number, scheme: string}> */
    this._proxyMap = new Map();

    /**
     * @private Array<{proxyId: string, regex: RegExp, regexString: string,
     *   host: string, port: number, scheme: string}>
     * Плоский список правил для быстрого последовательного перебора.
     */
    this._ruleList = [];
  }

  /**
   * Собирает кэш из сырых данных, полученных от DataController.
   * Каждая маска компилируется в RegExp. Невалидные маски пропускаются с предупреждением.
   *
   * @param {Array<{proxyId: string, host: string, port: number, isEnabled: boolean}>} proxies
   * @param {Array<{maskId: string, proxyId: string, regexString: string}>} masks
   */
  build(proxies, masks) {
    this.flush();

    /* Собираем карту прокси для быстрого доступа */
    for (const proxy of proxies) {
      this._proxyMap.set(proxy.proxyId, {
        host: proxy.host,
        port: proxy.port,
        scheme: 'SOCKS5'
      });
    }

    /* Группируем маски по proxyId */
    const masksByProxy = new Map();
    for (const mask of masks) {
      if (!masksByProxy.has(mask.proxyId)) {
        masksByProxy.set(mask.proxyId, []);
      }
      masksByProxy.get(mask.proxyId).push(mask);
    }

    /* Компилируем RegExp для каждой маски */
    for (const [proxyId, maskList] of masksByProxy) {
      const proxyConfig = this._proxyMap.get(proxyId);
      if (!proxyConfig) continue; /* Прокси удалён, но маска осталась — пропускаем */

      for (const mask of maskList) {
        try {
          const regex = new RegExp(mask.regexString);

          this._ruleList.push({
            proxyId,
            regex,
            regexString: mask.regexString,
            host: proxyConfig.host,
            port: proxyConfig.port,
            scheme: proxyConfig.scheme
          });
        } catch (error) {
          console.warn(
            `[FlowLink Proxy] Невалидная маска ${mask.maskId}: "${mask.regexString}" — ${error.message}`
          );
        }
      }
    }
  }

  /**
   * Синхронный поиск первого совпадения URL среди всех правил.
   * Вызывается внутри PAC-генерации или для отладки.
   *
   * @param {string} url - URL запроса.
   * @returns {{proxyId: string, host: string, port: number, scheme: string} | null}
   */
  findMatch(url) {
    for (const rule of this._ruleList) {
      try {
        if (rule.regex.test(url)) {
          return {
            proxyId: rule.proxyId,
            host: rule.host,
            port: rule.port,
            scheme: rule.scheme
          };
        }
      } catch {
        /* Пропускаем маску, вызвавшую ошибку при тесте */
        continue;
      }
    }
    return null;
  }

  /**
   * Возвращает конфигурацию прокси по ID.
   * @param {string} proxyId
   * @returns {{host: string, port: number, scheme: string} | null}
   */
  getProxyConfig(proxyId) {
    return this._proxyMap.get(proxyId) || null;
  }

  /** Полная очистка всех структур кэша. */
  flush() {
    this._proxyMap.clear();
    this._ruleList = [];
  }

  /** @returns {boolean} true, если кэш не содержит правил. */
  get isEmpty() {
    return this._ruleList.length === 0;
  }

  /**
   * Возвращает плоский список правил для генерации PAC-скрипта.
   * Каждое правило содержит строку regex (не компилированный RegExp).
   * @returns {Array<{proxyId: string, regexString: string, host: string, port: number, scheme: string}>}
   */
  get rules() {
    return this._ruleList.map(r => ({
      proxyId: r.proxyId,
      regexString: r.regexString,
      host: r.host,
      port: r.port,
      scheme: r.scheme
    }));
  }

  /** @returns {number} Количество правил в кэше. */
  get size() {
    return this._ruleList.length;
  }
}

export { MaskCache };
