/**
 * @fileoverview
 * Управление автозапуском и конфигурацией браузера.
 * Единственная ответственность: UI тогглов автозапуска, выбора браузера,
 * системного автозапуска и баннера отсутствия браузера.
 */

import { apiGet, apiPost, apiPostRaw } from '../shared/api.js';
import { setLoading } from '../shared/utils.js';

/**
 * @typedef {Object} BrowserInfo
 * @property {string} name - Название браузера.
 * @property {string} path - Путь к исполняемому файлу.
 * @property {string} platform - Платформа (win32, linux, darwin).
 */

/**
 * @typedef {Object} AutostartState
 * @property {boolean} autostartBrowser - Автозапуск браузера.
 * @property {boolean} systemAutostart - Запуск с системой.
 * @property {string} browserPath - Путь к браузеру.
 * @property {BrowserInfo[]} detectedBrowsers - Обнаруженные браузеры.
 * @property {boolean} loading - Флаг загрузки.
 */

/** Состояние модуля. */
let _state = {
  autostartBrowser: true,
  systemAutostart: false,
  browserPath: '',
  detectedBrowsers: [],
  loading: false,
};

/**
 * Возвращает текущее состояние.
 * @returns {AutostartState} Копия состояния.
 */
export function getAutostartState() {
  return { ..._state };
}

/**
 * Загружает все настройки автозапуска и браузера с бэкенда.
 * @returns {Promise<AutostartState>} Состояние.
 */
export async function loadAutostartStatus() {
  _state.loading = true;
  try {
    const [autostartData, browserConfig, systemData] = await Promise.all([
      apiGet('/autostart-browser'),
      apiGet('/browser-config'),
      apiGet('/system-autostart'),
    ]);

    _state.autostartBrowser = autostartData.autostartBrowser !== undefined
      ? autostartData.autostartBrowser : true;
    _state.browserPath = browserConfig.browserPath || '';
    _state.detectedBrowsers = browserConfig.detectedBrowsers || [];
    _state.systemAutostart = systemData.enabled || false;
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка загрузки настроек автозапуска:', e);
  } finally {
    _state.loading = false;
  }
  return getAutostartState();
}

/**
 * Отрисовывает все элементы автозапуска и выбора браузера.
 * Вызывается из render() popup.js.
 */
export function renderAutostartToggle() {
  // Тоггл автозапуска браузера
  const toggle = document.getElementById('autostart-browser-input');
  if (toggle) {
    toggle.checked = _state.autostartBrowser;
  }

  // Тоггл системного автозапуска
  const sysToggle = document.getElementById('system-autostart-input');
  if (sysToggle) {
    sysToggle.checked = _state.systemAutostart;
  }

  // Выпадающий список браузеров
  _renderBrowserSelector();

  // Путь к браузеру (текстовое поле)
  const pathInput = document.getElementById('browser-path-input');
  if (pathInput) {
    pathInput.value = _state.browserPath;
  }

  // Очистка ошибок валидации
  _clearBrowserPathError();

  // Баннер «браузер не выбран»
  _renderBrowserBanner();
}

/**
 * Обрабатывает переключение тоггла автозапуска браузера.
 * @param {HTMLInputElement} checkbox — элемент-тоггл.
 * @param {Function} showToast — функция показа toast-уведомления.
 */
export async function handleAutostartToggle(checkbox, showToast) {
  if (!checkbox) return;
  const value = checkbox.checked;
  const prevValue = !value;

  checkbox.disabled = true;

  try {
    const result = await apiPost('/autostart-browser', {
      autostartBrowser: value,
    });
    if (result.error) {
      throw new Error(result.error);
    }
    _state.autostartBrowser = result.autostartBrowser !== undefined
      ? result.autostartBrowser : value;
    checkbox.checked = _state.autostartBrowser;
    if (showToast) {
      showToast(
        _state.autostartBrowser
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
 * Обрабатывает переключение системного автозапуска.
 * @param {HTMLInputElement} checkbox — элемент-тоггл.
 * @param {Function} showToast — функция показа toast-уведомления.
 */
export async function handleSystemAutostartToggle(checkbox, showToast) {
  if (!checkbox) return;
  const value = checkbox.checked;
  const prevValue = !value;

  checkbox.disabled = true;

  try {
    const result = await apiPost('/system-autostart', { enabled: value });
    if (result.error) {
      throw new Error(result.error);
    }
    _state.systemAutostart = result.enabled !== undefined
      ? result.enabled : value;
    checkbox.checked = _state.systemAutostart;
    if (showToast) {
      showToast(
        _state.systemAutostart
          ? 'Автозапуск с системой включён'
          : 'Автозапуск с системой выключен',
      );
    }
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка переключения system_autostart:', e);
    checkbox.checked = prevValue;
    if (showToast) {
      showToast(
        'Не удалось изменить настройку автозапуска системы. '
        + 'Проверьте соединение с бэкендом.',
      );
    }
  } finally {
    checkbox.disabled = false;
  }
}

/**
 * Обрабатывает выбор браузера из выпадающего списка.
 * Валидирует путь, затем сохраняет.
 * @param {HTMLSelectElement} select — элемент select.
 * @param {Function} showToast — функция показа toast-уведомления.
 */
export async function handleBrowserSelect(select, showToast) {
  if (!select) return;
  const path = select.value;
  if (!path) return;

  // Очищаем предыдущую ошибку
  _clearBrowserPathError();

  try {
    const { status, data } = await apiPostRaw('/validate-browser', { browserPath: path });

    if (status === 200 && data.valid) {
      const result = await apiPost('/browser-path', { browserPath: path });
      if (result.error) {
        throw new Error(result.error);
      }
      _state.browserPath = result.browserPath || path;
      const pathInput = document.getElementById('browser-path-input');
      if (pathInput) {
        pathInput.value = _state.browserPath;
      }
      _renderBrowserBanner();
      if (showToast) {
        showToast('Путь к браузеру сохранён');
      }
      if (data.warnings && data.warnings.length > 0) {
        _showBrowserPathWarning(data.warnings[0]);
      }
    } else {
      const errorMsg = data.error || 'Неверный путь к браузеру';
      _showBrowserPathError(errorMsg);
      if (showToast) {
        showToast('Выбранный файл не является браузером');
      }
    }
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка выбора браузера:', e);
    if (showToast) {
      showToast('Не удалось сохранить путь к браузеру');
    }
  }
}

/**
 * Обрабатывает ручной ввод пути к браузеру.
 * Сначала валидирует путь, затем сохраняет.
 * @param {HTMLInputElement} input — элемент ввода.
 * @param {Function} showToast — функция показа toast-уведомления.
 */
export async function handleBrowserPathInput(input, showToast) {
  if (!input) return;
  const path = input.value.trim();

  // Очищаем предыдущую ошибку
  _clearBrowserPathError();

  // Пустой путь — разрешаем (сброс настроек)
  if (!path) {
    try {
      const result = await apiPost('/browser-path', { browserPath: '' });
      if (result.error) {
        throw new Error(result.error);
      }
      _state.browserPath = '';
      _renderBrowserBanner();
      if (showToast) {
        showToast('Путь к браузеру очищен');
      }
    } catch (e) {
      console.error('[FlowLink Proxy] Ошибка очистки пути браузера:', e);
      if (showToast) {
        showToast('Не удалось сохранить путь к браузеру');
      }
    }
    return;
  }

  // Валидация на бэкенде
  try {
    const { status, data } = await apiPostRaw('/validate-browser', { browserPath: path });

    if (status === 200 && data.valid) {
      // Валидация прошла — сохраняем
      const saveResult = await apiPost('/browser-path', { browserPath: path });
      if (saveResult.error) {
        throw new Error(saveResult.error);
      }
      _state.browserPath = saveResult.browserPath || path;
      _renderBrowserBanner();
      if (showToast) {
        showToast('Путь к браузеру сохранён');
      }
      // Показываем предупреждения, если есть
      if (data.warnings && data.warnings.length > 0) {
        _showBrowserPathWarning(data.warnings[0]);
      }
    } else {
      // Валидация не прошла — показываем ошибку в UI
      const errorMsg = data.error || 'Неверный путь к браузеру';
      _showBrowserPathError(errorMsg);
      if (showToast) {
        showToast('Путь не прошёл валидацию');
      }
    }
  } catch (e) {
    console.error('[FlowLink Proxy] Ошибка валидации/сохранения пути браузера:', e);
    if (showToast) {
      showToast('Не удалось проверить путь к браузеру. Проверьте соединение с бэкендом.');
    }
  }
}

/**
 * Отрисовывает выпадающий список обнаруженных браузеров.
 * @private
 */
function _renderBrowserSelector() {
  const select = document.getElementById('browser-select');
  if (!select) return;

  select.innerHTML = '';

  // Пустой option по умолчанию
  const emptyOpt = document.createElement('option');
  emptyOpt.value = '';
  emptyOpt.textContent = '— Выберите браузер —';
  select.appendChild(emptyOpt);

  for (const browser of _state.detectedBrowsers) {
    const opt = document.createElement('option');
    opt.value = browser.path;
    opt.textContent = `${browser.name} (${browser.path})`;
    if (browser.path === _state.browserPath) {
      opt.selected = true;
    }
    select.appendChild(opt);
  }

  // Если текущий путь не найден в списке — добавляем его как пользовательский
  if (
    _state.browserPath
    && !_state.detectedBrowsers.some((b) => b.path === _state.browserPath)
  ) {
    const opt = document.createElement('option');
    opt.value = _state.browserPath;
    opt.textContent = `${_state.browserPath} (пользовательский)`;
    opt.selected = true;
    select.appendChild(opt);
  }
}

/**
 * Отрисовывает баннер предупреждения, если браузер не выбран.
 * @private
 */
function _renderBrowserBanner() {
  const banner = document.getElementById('browser-not-found-banner');
  if (!banner) return;

  if (_state.browserPath) {
    banner.classList.add('hidden');
  } else {
    banner.classList.remove('hidden');
  }
}

/**
 * Показывает ошибку валидации пути к браузеру в UI.
 * @param {string} message — текст ошибки.
 * @private
 */
function _showBrowserPathError(message) {
  const el = document.getElementById('browser-path-error');
  if (el) {
    el.textContent = message;
    el.classList.remove('hidden');
  }
}

/**
 * Показывает предупреждение по пути к браузеру в UI.
 * @param {string} message — текст предупреждения.
 * @private
 */
function _showBrowserPathWarning(message) {
  const el = document.getElementById('browser-path-error');
  if (el) {
    el.textContent = message;
    el.classList.remove('hidden');
    el.classList.add('browser-path-warning');
  }
}

/**
 * Очищает ошибку/предупреждение пути к браузеру.
 * @private
 */
function _clearBrowserPathError() {
  const el = document.getElementById('browser-path-error');
  if (el) {
    el.textContent = '';
    el.classList.add('hidden');
    el.classList.remove('browser-path-warning');
  }
}
