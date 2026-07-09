/**
 * @fileoverview
 * Настройки расширения (порт API).
 * Единственная ответственность: управление настройками пользователя.
 */

import { setApiPort } from '../shared/constants.js';
import { setLoading } from '../shared/utils.js';

/**
 * Сохраняет кастомный порт API в chrome.storage и перезагружает данные.
 * @param {Function} loadAndRender — функция перезагрузки всех данных popup.
 */
export async function handleSettingsSave(loadAndRender) {
  const input = document.getElementById('settings-api-port');
  const port = Number(input.value);
  const saveBtn = document.getElementById('btn-settings-save');

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    input.focus();
    return;
  }

  setLoading(saveBtn, true);

  try {
    await chrome.storage.local.set({ apiPort: port });
    setApiPort(port);
    document.getElementById('settings-row').classList.add('hidden');
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка сохранения порта:', e);
  } finally {
    setLoading(saveBtn, false);
  }
}
