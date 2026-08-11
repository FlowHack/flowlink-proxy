// Модуль локализации для FlowLink Proxy
// Использует пользовательский словарь для переключения языка в рантайме

/**
 * Текущий язык (кэш)
 * @type {string}
 */
let _currentLang = 'ru';

/**
 * Словарь переводов
 * @type {Object.<string, Object.<string, string>>}
 */
const TRANSLATIONS = {
  ru: {
    appName: 'FlowLink Proxy',
    settings: 'Настройки',
    language: 'Язык',
    save: 'Сохранить',
    cancel: 'Отмена',
    close: 'Закрыть',
    loading: 'Загрузка...',
    error: 'Ошибка',
    success: 'Успешно',
    confirm: 'Подтвердить',
    delete: 'Удалить',
    add: 'Добавить',
    yes: 'Да',
    no: 'Нет',
    languageChanged: 'Язык изменён',
    on: 'Вкл',
    off: 'Выкл',
    toggle: 'Вкл/Выкл',
    download: 'Скачать',
    howToUpdate: 'Как обновить?',
    ping: 'Пинг',
    checking: 'Проверка...',
    noProxies: 'Нет добавленных прокси',
    addProxy: '+ Добавить прокси',
    supportProject: 'Поддержать проект',
    errorsSuggestions: 'Ошибки и предложения:',
    clickToCopy: 'Нажмите, чтобы скопировать',
    help: 'Помощь',
    connection: 'Подключение',
    apiPort: 'Порт API:',
    backend: 'Бэкенд',
    browser: 'Браузер',
    portSetup: 'Настройка порта',
    faq: 'FAQ',
    updateBackend: 'Обновление бэкенда',
    updateExt: 'Обновление расширения',
    addProxyTitle: 'Добавить прокси',
    editProxyTitle: 'Редактировать прокси',
    ipOrDomain: 'IP или домен',
    port: 'Порт',
    login: 'Логин',
    password: 'Пароль',
    showPassword: 'Показать пароль',
    hidePassword: 'Скрыть пароль',
    labelOptional: 'Название (необязательно)',
    cancelBtn: 'Отменить',
    masks: 'Маски',
    clear: 'Очистить',
    noMasks: 'Нет масок',
    addMask: '+ Добавить маску',
    addMaskTitle: 'Добавить маску',
    editMaskTitle: 'Редактировать маску',
    deleteMaskTitle: 'Удалить маску',
    maskExample: 'Например: *gemini.google.com* или *.google.com',
    retry: 'Повторить',
    version: 'Версия',
    na: 'н/д',
    edit: 'Редактировать',
    noProxiesAdded: 'Прокси не добавлены',
    noMasksAdded: 'Масок нет',
    clickForMasks: 'Клик — маски для {label}',
    disabled: 'Выключено',
    direct: 'Напрямую',
    viaSocks5: 'Через SOCKS5 ({host})',
    unknown: 'неизвестно',
    updateAvailable: 'Доступно обновление {tag}',
    versionBackend: 'Версия: {ext} (бэкенд: {be})',
    noBackendConn: 'Нет соединения с бэкендом. Проверьте, запущен ли FlowLink Proxy.',
    noBackendShort: 'Нет соединения с бэкендом',
    toggleFailed: 'Не удалось переключить состояние. Проверьте соединение с бэкендом.',
    browserAutostartWarning: 'Включён автозапуск браузера, но браузер не выбран. Настройте его, чтобы автозапуск работал.',
    enterHost: 'Введите хост',
    enterPort: 'Введите порт',
    portRange: 'Порт от 1 до 65535',
    invalidHost: 'Неверный формат хоста (IP или домен)',
    backendUnreachable: 'Не удалось связаться с бэкендом. Проверьте, запущен ли FlowLink Proxy.',
    deleteProxyFailed: 'Не удалось удалить прокси. Проверьте соединение с бэкендом.',
    toggleProxyFailed: 'Не удалось переключить прокси. Проверьте соединение с бэкендом.',
    enterMaskPattern: 'Введите паттерн маски',
    noProxySelected: 'Не выбран прокси для маски',
    deleteMaskFailed: 'Не удалось удалить маску. Проверьте соединение с бэкендом.',
    clearMasksFailed: 'Не удалось очистить маски. Проверьте соединение с бэкендом.',
    portInvalid: 'Порт должен быть числом от 1 до 65535',
    saveSettingsFailed: 'Не удалось сохранить настройки. Проверьте соединение с бэкендом.',
    updateCheckFailed: 'Не удалось проверить обновления. Возможно, GitHub заблокирован — используйте VPN или прокси.',
    proxyBlockedHint: 'Прокси не отвечают (таймаут/сброс). Возможно, соединение блокируется провайдером — используйте VPN или другой прокси.',
    invalidJson: 'Бэкенд вернул невалидный ответ. Попробуйте перезапустить бэкенд.',
    emailCopied: 'Email скопирован: {email}',
    copyFailed: 'Не удалось скопировать. Выделите вручную: {email}',
    selectManually: 'Выделите вручную: {email}',
    helpIntro: 'Для расширения требуется приложение FlowLink Proxy. Ниже — инструкции по установке на разные системы.',
    windows: 'Windows',
    linux: 'Linux',
    macos: 'macOS',
    sourceCode: 'Исходный код',
    update: 'Обновление',
    license: 'Лицензия',
    sectionInDev: 'Раздел в разработке.',
    renderError: 'Ошибка при отображении помощи. Попробуйте перезагрузить popup.',
    renderSubError: 'Ошибка рендеринга. Перезагрузите popup.',
    emailFooter: 'Не удалось решить проблему? Напишите на {email} — поможем.'
  },
  en: {
    appName: 'FlowLink Proxy',
    settings: 'Settings',
    language: 'Language',
    save: 'Save',
    cancel: 'Cancel',
    close: 'Close',
    loading: 'Loading...',
    error: 'Error',
    success: 'Success',
    confirm: 'Confirm',
    delete: 'Delete',
    add: 'Add',
    yes: 'Yes',
    no: 'No',
    languageChanged: 'Language changed',
    on: 'On',
    off: 'Off',
    toggle: 'On/Off',
    download: 'Download',
    howToUpdate: 'How to update?',
    ping: 'Ping',
    checking: 'Checking...',
    noProxies: 'No proxies added',
    addProxy: '+ Add proxy',
    supportProject: 'Support the project',
    errorsSuggestions: 'Errors and suggestions:',
    clickToCopy: 'Click to copy',
    help: 'Help',
    connection: 'Connection',
    apiPort: 'API port:',
    backend: 'Backend',
    browser: 'Browser',
    portSetup: 'Port setup',
    faq: 'FAQ',
    updateBackend: 'Update backend',
    updateExt: 'Update extension',
    addProxyTitle: 'Add proxy',
    editProxyTitle: 'Edit proxy',
    ipOrDomain: 'IP or domain',
    port: 'Port',
    login: 'Login',
    password: 'Password',
    showPassword: 'Show password',
    hidePassword: 'Hide password',
    labelOptional: 'Label (optional)',
    cancelBtn: 'Cancel',
    masks: 'Masks',
    clear: 'Clear',
    noMasks: 'No masks',
    addMask: '+ Add mask',
    addMaskTitle: 'Add mask',
    editMaskTitle: 'Edit mask',
    deleteMaskTitle: 'Delete mask',
    maskExample: 'Example: *gemini.google.com* or *.google.com',
    retry: 'Retry',
    version: 'Version',
    na: 'n/a',
    noProxiesAdded: 'No proxies added',
    noMasksAdded: 'No masks',
    clickForMasks: 'Click — masks for {label}',
    disabled: 'Disabled',
    direct: 'Direct',
    viaSocks5: 'Via SOCKS5 ({host})',
    unknown: 'unknown',
    updateAvailable: 'Update available {tag}',
    versionBackend: 'Version: {ext} (backend: {be})',
    noBackendConn: 'No connection to backend. Check if FlowLink Proxy is running.',
    noBackendShort: 'No connection to backend',
    toggleFailed: 'Failed to toggle state. Check connection to backend.',
    browserAutostartWarning: 'Browser autostart is enabled, but no browser is selected. Configure it for autostart to work.',
    enterHost: 'Enter host',
    enterPort: 'Enter port',
    portRange: 'Port from 1 to 65535',
    invalidHost: 'Invalid host format (IP or domain)',
    backendUnreachable: 'Failed to reach backend. Check if FlowLink Proxy is running.',
    deleteProxyFailed: 'Failed to delete proxy. Check connection to backend.',
    toggleProxyFailed: 'Failed to toggle proxy. Check connection to backend.',
    enterMaskPattern: 'Enter mask pattern',
    noProxySelected: 'No proxy selected for mask',
    deleteMaskFailed: 'Failed to delete mask. Check connection to backend.',
    clearMasksFailed: 'Failed to clear masks. Check connection to backend.',
    portInvalid: 'Port must be a number from 1 to 65535',
    saveSettingsFailed: 'Failed to save settings. Check connection to backend.',
    updateCheckFailed: 'Failed to check updates. GitHub may be blocked — use VPN or proxy.',
    proxyBlockedHint: 'Proxies are not responding (timeout/reset). Connection may be blocked by provider — use VPN or another proxy.',
    invalidJson: 'Backend returned invalid response. Try restarting the backend.',
    emailCopied: 'Email copied: {email}',
    copyFailed: 'Failed to copy. Select manually: {email}',
    selectManually: 'Select manually: {email}',
    helpIntro: 'The extension requires the FlowLink Proxy application. Below are installation instructions for different systems.',
    windows: 'Windows',
    linux: 'Linux',
    macos: 'macOS',
    sourceCode: 'Source code',
    update: 'Update',
    license: 'License',
    sectionInDev: 'Section under development.',
    renderError: 'Error displaying help. Try reloading the popup.',
    renderSubError: 'Rendering error. Reload the popup.',
    emailFooter: 'Could not solve the problem? Write to {email} — we will help.'
  },
  sr: {
    appName: 'FlowLink Proxy',
    settings: 'Podešavanja',
    language: 'Jezik',
    save: 'Sačuvaj',
    cancel: 'Otkaži',
    close: 'Zatvori',
    loading: 'Učitavanje...',
    error: 'Greška',
    success: 'Uspešno',
    confirm: 'Potvrdi',
    delete: 'Obriši',
    add: 'Dodaj',
    yes: 'Da',
    no: 'Ne',
    languageChanged: 'Jezik je promenjen',
    on: 'Uključeno',
    off: 'Isključeno',
    toggle: 'Uključi/Isključi',
    download: 'Preuzmi',
    howToUpdate: 'Kako ažurirati?',
    ping: 'Ping',
    checking: 'Provera...',
    noProxies: 'Nema dodatih proxyja',
    addProxy: '+ Dodaj proxy',
    supportProject: 'Podrži projekat',
    errorsSuggestions: 'Greške i predlozi:',
    clickToCopy: 'Kliknite da kopirate',
    help: 'Pomoć',
    connection: 'Veza',
    apiPort: 'API port:',
    backend: 'Backend',
    browser: 'Pregledač',
    portSetup: 'Podešavanje porta',
    faq: 'FAQ',
    updateBackend: 'Ažuriranje backend-a',
    updateExt: 'Ažuriranje ekstenzije',
    addProxyTitle: 'Dodaj proxy',
    editProxyTitle: 'Izmeni proxy',
    ipOrDomain: 'IP ili domen',
    port: 'Port',
    login: 'Korisničko ime',
    password: 'Lozinka',
    showPassword: 'Prikaži lozinku',
    hidePassword: 'Sakrij lozinku',
    labelOptional: 'Naziv (opciono)',
    cancelBtn: 'Otkaži',
    masks: 'Maske',
    clear: 'Očisti',
    noMasks: 'Nema maski',
    addMask: '+ Dodaj masku',
    addMaskTitle: 'Dodaj masku',
    editMaskTitle: 'Izmeni masku',
    deleteMaskTitle: 'Obriši masku',
    maskExample: 'Primer: *gemini.google.com* ili *.google.com',
    retry: 'Pokušaj ponovo',
    version: 'Verzija',
    na: 'n/p',
    noProxiesAdded: 'Nema dodatih proxyja',
    noMasksAdded: 'Nema maski',
    clickForMasks: 'Klik — maske za {label}',
    disabled: 'Isključeno',
    direct: 'Direktno',
    viaSocks5: 'Preko SOCKS5 ({host})',
    unknown: 'nepoznato',
    updateAvailable: 'Dostupno ažuriranje {tag}',
    versionBackend: 'Verzija: {ext} (backend: {be})',
    noBackendConn: 'Nema veze sa backend-om. Proverite da li je FlowLink Proxy pokrenut.',
    noBackendShort: 'Nema veze sa backend-om',
    toggleFailed: 'Neuspešno prebacivanje stanja. Proverite vezu sa backend-om.',
    browserAutostartWarning: 'Automatsko pokretanje pregledača je uključeno, ali pregledač nije izabran. Podesite ga da bi automatsko pokretanje radilo.',
    enterHost: 'Unesite host',
    enterPort: 'Unesite port',
    portRange: 'Port od 1 do 65535',
    invalidHost: 'Neispravan format hosta (IP ili domen)',
    backendUnreachable: 'Neuspešno povezivanje sa backend-om. Proverite da li je FlowLink Proxy pokrenut.',
    deleteProxyFailed: 'Neuspešno brisanje proxyja. Proverite vezu sa backend-om.',
    toggleProxyFailed: 'Neuspešno prebacivanje proxyja. Proverite vezu sa backend-om.',
    enterMaskPattern: 'Unesite pattern maske',
    noProxySelected: 'Nije izabran proxy za masku',
    deleteMaskFailed: 'Neuspešno brisanje maske. Proverite vezu sa backend-om.',
    clearMasksFailed: 'Neuspešno čišćenje maski. Proverite vezu sa backend-om.',
    portInvalid: 'Port mora biti broj od 1 do 65535',
    saveSettingsFailed: 'Neuspešno čuvanje podešavanja. Proverite vezu sa backend-om.',
    updateCheckFailed: 'Neuspešna provera ažuriranja. GitHub je možda blokiran — koristite VPN ili proxy.',
    proxyBlockedHint: 'Proxyji ne odgovaraju (timeout/reset). Veza je možda blokirana od strane provajdera — koristite VPN ili drugi proxy.',
    invalidJson: 'Backend je vratio neispravan odgovor. Pokušajte da restartujete backend.',
    emailCopied: 'Email kopiran: {email}',
    copyFailed: 'Neuspešno kopiranje. Izaberite ručno: {email}',
    selectManually: 'Izaberite ručno: {email}',
    helpIntro: 'Ekstenzija zahteva FlowLink Proxy aplikaciju. Ispod su uputstva za instalaciju na različitim sistemima.',
    windows: 'Windows',
    linux: 'Linux',
    macos: 'macOS',
    sourceCode: 'Izvorni kod',
    update: 'Ažuriranje',
    license: 'Licenca',
    sectionInDev: 'Sekcija u razvoju.',
    renderError: 'Greška pri prikazivanju pomoći. Pokušajte da ponovo učitate popup.',
    renderSubError: 'Greška pri renderovanju. Ponovo učitajte popup.',
    emailFooter: 'Niste uspeli da rešite problem? Pišite na {email} — pomoći ćemo.'
  }
};

/**
 * Нормализует код языка
 * @param {string} lang - Код языка (например, 'ru-RU', 'en-US')
 * @returns {string} Базовый код языка ('ru', 'en', 'sr')
 */
export function normalizeLang(lang) {
  if (!lang) return 'ru';
  const normalized = lang.toLowerCase().substring(0, 2);
  return ['ru', 'en', 'sr'].includes(normalized) ? normalized : 'ru';
}

/**
 * Возвращает текущий язык
 * @returns {Promise<string>} Текущий язык
 */
export async function getCurrentLang() {
  try {
    const result = await chrome.storage.local.get('language');
    const storedLang = result.language;
    if (storedLang) {
      _currentLang = normalizeLang(storedLang);
      return _currentLang;
    }
  } catch (e) {
    console.warn('[FlowLink Proxy] i18n: не удалось прочитать язык из storage:', e);
  }

  const browserLang = normalizeLang(navigator.language);
  _currentLang = browserLang;
  return _currentLang;
}

/**
 * Устанавливает язык
 * @param {string} lang - Код языка
 * @returns {Promise<void>}
 */
export async function setLang(lang) {
  const normalized = normalizeLang(lang);
  _currentLang = normalized;
  try {
    await chrome.storage.local.set({ language: normalized });
  } catch (e) {
    console.warn('[FlowLink Proxy] i18n: не удалось сохранить язык в storage:', e);
  }
}

/**
 * Возвращает доступные языки
 * @returns {string[]} Список доступных языков
 */
export function getAvailableLangs() {
  return Object.keys(TRANSLATIONS);
}

/**
 * Переводит строку по ключу
 * @param {string} key - Ключ перевода
 * @param {Object.<string, string>} [params] - Параметры для подстановки
 * @returns {string} Переведённая строка или ключ, если перевод не найден
 */
export function t(key, params = {}) {
  const translation = TRANSLATIONS[_currentLang]?.[key];
  if (!translation) {
    console.warn(`[FlowLink Proxy] i18n: отсутствует перевод для ключа '${key}'`);
    return key;
  }

  let result = translation;
  for (const [paramKey, paramValue] of Object.entries(params)) {
    const placeholder = new RegExp(`\{${paramKey}\}`, 'g');
    result = result.replace(placeholder, paramValue);
  }

  return result;
}

/**
 * Применяет локализацию ко всем элементам с атрибутами data-i18n
 * @returns {Promise<void>}
 */
export async function applyI18n() {
  await getCurrentLang();

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (key) {
      el.textContent = t(key);
    }
  });

  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    if (key) {
      el.placeholder = t(key);
    }
  });

  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    if (key) {
      el.title = t(key);
    }
  });
}