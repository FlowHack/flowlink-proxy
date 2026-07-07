/**
 * @fileoverview
 * Константы действий для обмена сообщениями между Popup и Service Worker.
 * Все коммуникации UI → Background выполняются через chrome.runtime.sendMessage
 * с одним из этих action-типов.
 */

const MESSAGES = Object.freeze({
  GET_ALL_PROXIES: 'getAllProxies',
  GET_PROXY: 'getProxy',
  ADD_PROXY: 'addProxy',
  UPDATE_PROXY: 'updateProxy',
  DELETE_PROXY: 'deleteProxy',
  TOGGLE_PROXY: 'toggleProxy',
  GET_MASKS_BY_PROXY: 'getMasksByProxy',
  ADD_MASK: 'addMask',
  UPDATE_MASK: 'updateMask',
  DELETE_MASK: 'deleteMask',
  GET_EXTENSION_STATUS: 'getExtensionStatus',
  SET_EXTENSION_STATUS: 'setExtensionStatus',
  PING_PROXY: 'pingProxy',
  GET_CURRENT_TAB_STATUS: 'getCurrentTabStatus',
  CHECK_MASK_CONFLICT: 'checkMaskConflict'
});

export { MESSAGES };
