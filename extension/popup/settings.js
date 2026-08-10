/**
 * @fileoverview
 * Настройки расширения (порт API).
 * Единственная ответственность: управление настройками пользователя.
 */

import { setApiPort } from '../shared/constants.js';
import { setLoading } from '../shared/utils.js';
import { t, setLang, applyI18n, getCurrentLang } from '../shared/i18n.js';
import { apiPost } from '../shared/api.js';

/**
 * Сохраняет кастомный порт API в chrome.storage и перезагружает данные.
 * @param {Function} loadAndRender — функция перезагрузки всех данных popup.
 * @param {Function} [showToast] — функция показа toast-уведомления.
 */
export async function handleSettingsSave(loadAndRender, showToast) {
  const input = document.getElementById('settings-api-port');
  const port = Number(input.value);
  const saveBtn = document.getElementById('btn-settings-save');

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    input.focus();
    if (showToast) showToast(t('portInvalid'), 'error');
    return;
  }

  setLoading(saveBtn, true);

  try {
    await chrome.storage.local.set({ apiPort: port });
    setApiPort(port);
    document.getElementById('settings-block').classList.add('hidden');
    await loadAndRender();
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка сохранения порта:', e);
    if (showToast) showToast(t('saveSettingsFailed'), 'error');
  } finally {
    setLoading(saveBtn, false);
  }
}

/**
 * Инициализирует выпадающий список языка текущим значением.
 * Вызывается при открытии popup.
 */
export async function initLanguageSelect() {
  const select = document.getElementById('settings-language');
  if (!select) return;
  const lang = await getCurrentLang();
  select.value = lang;
}

/**
 * Обрабатывает смену языка в выпадающем списке.
 * Сохраняет язык в chrome.storage, применяет локализацию к UI
 * и отправляет язык на бэкенд через /api/language.
 * @param {Function} [showToast] — функция показа toast-уведомления.
 */
export async function handleLanguageChange(showToast) {
  const select = document.getElementById('settings-language');
  if (!select) return;
  const lang = select.value;

  // Сохраняем язык локально и применяем локализацию
  await setLang(lang);
  await applyI18n();

  // Отправляем язык на бэкенд (не критично, если бэкенд недоступен)
  try {
    await apiPost('/language', { language: lang });
  } catch (e) {
    console.warn('[FlowLink Proxy] Не удалось отправить язык на бэкенд:', e);
  }

  if (showToast) showToast(t('languageChanged'), 'info');
}