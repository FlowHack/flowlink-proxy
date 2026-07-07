/**
 * @fileoverview
 * Маршрутизатор сообщений между Popup (UI) и Service Worker.
 * Принимает запросы от chrome.runtime.sendMessage, вызывает методы
 * DataController и ProxyController, возвращает результат.
 * Запрещает прямой доступ к chrome.storage из UI (TZ requirement).
 */

import { MESSAGES } from '../shared/messages.js';

/**
 * Маршрутизатор сообщений.
 * Регистрирует единый обработчик chrome.runtime.onMessage,
 * диспетчеризует действия на соответствующие методы контроллеров.
 */
class MessageRouter {
  /**
   * @param {DataController} dataController
   * @param {ProxyController} proxyController
   */
  constructor(dataController, proxyController) {
    this._dc = dataController;
    this._pc = proxyController;
    /** @private {boolean} Предотвращает повторную регистрацию слушателя */
    this._initialized = false;
    /**
     * @private {Promise<void>|null}
     * Промис инициализации DataController. Если передан в init(),
     * _handle ждёт его перед обработкой сообщения.
     */
    this._readyPromise = null;
  }

  /**
   * Регистрирует глобальный обработчик сообщений.
   * Guard от повторного вызова — не допускает дублирования onMessage.
   * @param {Promise<void>} [readyPromise] — опциональный промис готовности DataController.
   */
  init(readyPromise) {
    if (this._initialized) return;
    this._initialized = true;
    this._readyPromise = readyPromise || Promise.resolve();

    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      this._handle(message, sendResponse);
      return true; /* Асинхронный ответ */
    });
  }

  /**
   * Диспетчеризация сообщения по action.
   * @param {{action: string, data?: any}} message
   * @param {function} sendResponse
   */
  async _handle(message, sendResponse) {
    try {
      /* Ждём готовности DataController перед обработкой */
      if (this._readyPromise) {
        await this._readyPromise;
      }

      switch (message.action) {
        case MESSAGES.GET_ALL_PROXIES:
          sendResponse({ success: true, data: await this._dc.getAllProxies() });
          break;

        case MESSAGES.GET_PROXY:
          sendResponse({ success: true, data: await this._dc.getProxy(message.data.proxyId) });
          break;

        case MESSAGES.ADD_PROXY:
          const proxyId = await this._dc.addProxy(message.data);
          await this._pc.refresh();
          sendResponse({ success: true, data: proxyId });
          break;

        case MESSAGES.UPDATE_PROXY:
          await this._dc.updateProxy(message.data.proxyId, message.data.fields);
          await this._pc.refresh();
          sendResponse({ success: true });
          break;

        case MESSAGES.DELETE_PROXY:
          await this._dc.deleteProxy(message.data.proxyId);
          await this._pc.refresh();
          sendResponse({ success: true });
          break;

        case MESSAGES.TOGGLE_PROXY:
          await this._dc.toggleProxy(message.data.proxyId, message.data.isEnabled);
          await this._pc.refresh();
          sendResponse({ success: true });
          break;

        case MESSAGES.GET_MASKS_BY_PROXY:
          sendResponse({
            success: true,
            data: await this._dc.getMasksByProxy(message.data.proxyId)
          });
          break;

        case MESSAGES.ADD_MASK:
          const maskId = await this._dc.addMask(message.data.proxyId, message.data.regexString);
          await this._pc.refresh();
          sendResponse({ success: true, data: maskId });
          break;

        case MESSAGES.UPDATE_MASK:
          await this._dc.updateMask(message.data.maskId, message.data.regexString);
          await this._pc.refresh();
          sendResponse({ success: true });
          break;

        case MESSAGES.DELETE_MASK:
          await this._dc.deleteMask(message.data.maskId);
          await this._pc.refresh();
          sendResponse({ success: true });
          break;

        case MESSAGES.CLEAR_MASKS:
          await this._dc.clearMasksByProxy(message.data.proxyId);
          await this._pc.refresh();
          sendResponse({ success: true });
          break;

        case MESSAGES.GET_EXTENSION_STATUS:
          sendResponse({ success: true, data: await this._dc.getExtensionStatus() });
          break;

        case MESSAGES.SET_EXTENSION_STATUS:
          await this._pc.setExtensionEnabled(message.data.enabled);
          sendResponse({ success: true });
          break;

        case MESSAGES.PING_PROXY:
          sendResponse({ success: true, data: await this._pc.pingProxy(message.data.proxyId) });
          break;

        case MESSAGES.PING_ALL:
          sendResponse({ success: true, data: await this._pc.pingAllProxies() });
          break;

        case MESSAGES.PING_PROXY_SETUP:
          await this._pc.setTestProxy(message.data.host, message.data.port);
          sendResponse({ success: true });
          break;

        case MESSAGES.PING_PROXY_CLEANUP:
          await this._pc.restoreProxy();
          sendResponse({ success: true });
          break;

        case MESSAGES.GET_CURRENT_TAB_STATUS:
          sendResponse({ success: true, data: await this._getCurrentTabStatus() });
          break;

        case MESSAGES.CHECK_MASK_CONFLICT:
          sendResponse({
            success: true,
            data: await this._checkMaskConflict(message.data.proxyId, message.data.regexString)
          });
          break;

        default:
          sendResponse({ success: false, error: `Неизвестное действие: ${message.action}` });
      }
    } catch (error) {
      sendResponse({ success: false, error: error.message });
    }
  }

  /**
   * Определяет статус текущей активной вкладки.
   * Если вкладка открыта, проверяет URL по маскам и failoverState.
   * Возвращает: {hasTab, status, domain, proxyHost} или null.
   */
  async _getCurrentTabStatus() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0 || !tabs[0].url) {
      return { hasTab: false };
    }

    const url = tabs[0].url;
    try {
      const parsed = new URL(url);
      const domain = parsed.hostname;

      const match = this._pc.maskCache.findMatch(url);

      if (!match) {
        return { hasTab: true, status: 'allowed', domain, proxyHost: null };
      }

      const blocked = this._pc.isProxyBlocked(match.proxyId);

      return {
        hasTab: true,
        status: blocked ? 'blocked' : 'allowed',
        domain,
        proxyHost: match.host,
        blocked
      };
    } catch (error) {
      console.warn('[FlowLink Proxy] Ошибка определения статуса вкладки:', error);
      return { hasTab: true, status: 'allowed', domain: null, proxyHost: null };
    }
  }

  /**
   * Проверяет, не конфликтует ли новая маска с существующими.
   * Конфликт: маска включает или включена в другую маску.
   *
   * @param {string} proxyId - UUID прокси (исключается из проверки).
   * @param {string} newRegexStr - Новая маска.
   * @returns {Promise<string|null>} Текст ошибки или null, если конфликта нет.
   */
  async _checkMaskConflict(proxyId, newRegexStr) {
    const allMasks = await this._dc.getAllMasks();
    const otherMasks = allMasks.filter(m => m.proxyId !== proxyId);

    try {
      const newRegex = new RegExp(newRegexStr);
      const testUrls = [
        'http://a.com', 'https://a.com', 'http://www.a.com',
        'http://a.b.com', 'https://a.b.com/path',
        'http://test.org', 'https://test.org/page',
        'http://a-b.com', 'https://sub.domain.com'
      ];

      for (const mask of otherMasks) {
        try {
          const existingRegex = new RegExp(mask.regexString);

          for (const url of testUrls) {
            if (newRegex.test(url) && existingRegex.test(url)) {
              return 'Данная маска включает или включена в маску другого прокси';
            }
          }
        } catch {
          /* Пропускаем невалидные существующие маски */
        }
      }
    } catch {
      return 'Невалидное регулярное выражение';
    }

    return null;
  }
}

export { MessageRouter };
