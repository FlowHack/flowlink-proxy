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
  // Чекбокс автозапуска браузера
  const autostartCheckbox = document.getElementById('browser-autostart-toggle');
  if (autostartCheckbox) {
    autostartCheckbox.checked = _state.autostartBrowser;
  }

  // Поля выбора браузера и пути — показываем только если автозапуск включён
  const autostartFields = document.getElementById('browser-autostart-fields');
  if (autostartFields) {
    autostartFields.classList.toggle('hidden', !_state.autostartBrowser);
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

  // Чекбокс системного автозапуска
  const systemCheckbox = document.getElementById('system-autostart-toggle');
  if (systemCheckbox) {
    systemCheckbox.checked = _state.systemAutostart;
  }

  // Баннер «браузер не выбран»
  _renderBrowserBanner();
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
 * Использует renderBanner из popup.js.
 * @private
 */
function _renderBrowserBanner() {
  const renderBanner = window.__flowlinkRenderBanner;

  // Если нет соединения с бэкендом — не показываем баннер (не можем знать, выбран ли браузер)
  if (!window.__flowlinkConnected) {
    const banner = document.getElementById('banner-warning-app');
    if (banner) banner.classList.add('hidden');
    return;
  }

  if (_state.browserPath) {
    // Браузер выбран — скрываем баннер
    const banner = document.getElementById('banner-warning-app');
    if (banner) banner.classList.add('hidden');
  } else if (renderBanner) {
    // Браузер не выбран — показываем баннер через renderBanner
    renderBanner('warning', 'Браузер не выбран. Автозапуск недоступен.', {
      containerId: 'app',
      bannerId: 'banner-warning-app',
      actionText: 'Помощь',
      actionCallback: () => {
        import('./help.js').then(({ openHelpModal }) => {
          openHelpModal(null, false, true);
        });
      },
    });
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
