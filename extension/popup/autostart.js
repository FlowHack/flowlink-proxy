/**
 * @fileoverview
 * Управление автозапуском браузера — загрузка, переключение, отображение.
 * Единственная ответственность: UI тоггла автозапуска браузера и баннер отсутствия скриптов.
 */

import { apiGet, apiPost } from '../shared/api.js';
import { setLoading } from '../shared/utils.js';

/** Состояние автозапуска браузера. */
let _autostartState = {
  autostartBrowser: true,
  launchScriptsFound: false,
  launchScripts: {},
};

/**
 * Возвращает текущее состояние автозапуска.
 * @returns {object} Копия состояния.
 */
export function getAutostartState() {
  return { ..._autostartState };
}

/**
 * Загружает статус автозапуска с бэкенда.
 * @returns {Promise<object>} Состояние автозапуска.
 */
export async function loadAutostartStatus() {
  try {
    const data = await apiGet('/autostart-browser');
    _autostartState = {
      autostartBrowser: data.autostartBrowser !== undefined
        ? data.autostartBrowser : true,
      launchScriptsFound: data.launchScriptsFound || false,
      launchScripts: data.launchScripts || {},
    };
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка загрузки autostart_browser:', e);
    // Оставляем значения по умолчанию при ошибке
  }
  return getAutostartState();
}

/**
 * Отрисовывает тоггл автозапуска браузера.
 * Вызывается из render() popup.js.
 */
export function renderAutostartToggle() {
  const toggle = document.getElementById('autostart-browser-input');
  if (toggle) {
    toggle.checked = _autostartState.autostartBrowser;
  }

  // Показываем/скрываем баннер, если скрипты запуска не найдены
  _renderLaunchScriptsBanner();

  // Показываем/скрываем тоггл (только если скрипты найдены)
  const wrap = document.getElementById('autostart-browser-wrap');
  if (wrap) {
    wrap.classList.toggle('hidden', !_autostartState.launchScriptsFound);
  }
}

/**
 * Обрабатывает переключение тоггла автозапуска браузера.
 * Отправляет POST на /api/autostart-browser со спиннером.
 * @param {HTMLInputElement} checkbox — элемент-тоггл.
 * @param {Function} showToast — функция показа toast-уведомления.
 */
export async function handleAutostartToggle(checkbox, showToast) {
  if (!checkbox) return;
  const value = checkbox.checked;
  const toggleWrap = checkbox.closest('.autostart-row') || checkbox.parentElement;
  const prevValue = !value;

  checkbox.disabled = true;

  try {
    const result = await apiPost('/autostart-browser', {
      autostartBrowser: value,
    });
    if (result.error) {
      throw new Error(result.error);
    }
    _autostartState.autostartBrowser = result.autostartBrowser !== undefined
      ? result.autostartBrowser : value;
    checkbox.checked = _autostartState.autostartBrowser;
    if (showToast) {
      showToast(
        _autostartState.autostartBrowser
          ? 'Автозапуск браузера включён'
          : 'Автозапуск браузера выключен',
      );
    }
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка переключения autostart_browser:', e);
    checkbox.checked = prevValue;
    if (showToast) {
      showToast(
        'Не удалось изменить настройку. '
        + 'Проверьте соединение с бэкендом. '
        + 'Подробности — в разделе «Помощь».',
      );
    }
  } finally {
    checkbox.disabled = false;
  }
}

/**
 * Отрисовывает баннер предупреждения, если скрипты запуска не найдены.
 * Баннер содержит кнопку «Помощь» с инструкцией по решению проблемы.
 */
function _renderLaunchScriptsBanner() {
  const banner = document.getElementById('autostart-scripts-banner');
  if (!banner) return;

  if (_autostartState.launchScriptsFound) {
    banner.classList.add('hidden');
    return;
  }

  banner.classList.remove('hidden');
}
