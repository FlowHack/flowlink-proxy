/**
 * @fileoverview
 * Точка входа Service Worker расширения FlowLink Proxy.
 * Инициализирует DataController, ProxyController и MessageRouter при старте SW.
 * Регистрирует глобальный обработчик chrome.notifications (клик по уведомлению).
 *
 * ВАЖНО: MessageRouter.init() вызывается на каждый старт Service Worker,
 * а НЕ только внутри onInstalled. В MV3 onInstalled не гарантирован
 * при перезапуске SW (idle → wake).
 */

import { DataController } from './data-controller.js';
import { ProxyController } from './proxy-controller.js';
import { MessageRouter } from './message-router.js';

/** Единственный экземпляр контроллера данных */
const dataController = new DataController();

/** Единственный экземпляр контроллера прокси */
const proxyController = new ProxyController();

/** Единственный экземпляр маршрутизатора сообщений */
const messageRouter = new MessageRouter(dataController, proxyController);

/* Промис инициализации данных — передаётся в messageRouter,
 * чтобы _handle() ждал готовности DataController перед обработкой */
const initPromise = (async () => {
  try {
    await dataController.init();
    await proxyController.init(dataController);
  } catch (error) {
    console.error('[FlowLink Proxy] Ошибка инициализации:', error);
  }
})();

/* Синхронная регистрация обработчика onMessage — обязательна при каждом старте SW */
messageRouter.init(initPromise);

/**
 * Обработчик установки/обновления расширения.
 * onInstalled НЕ вызывается при каждом старте SW, поэтому инициализация
 * данных вынесена на верхний уровень. Здесь — только логирование.
 */
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[FlowLink Proxy] Расширение установлено');
  }
});

/**
 * Обработчик клика по уведомлению — закрывает уведомление.
 */
chrome.notifications.onClicked.addListener((notificationId) => {
  chrome.notifications.clear(notificationId);
});
