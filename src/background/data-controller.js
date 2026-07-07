/**
 * @fileoverview
 * Контроллер данных FlowLink Proxy.
 * Предоставляет CRUD-операции для ProxyTable и MaskTable,
 * а также управление состоянием расширения через chrome.storage.local.
 * Чувствительные поля (username, password) шифруются/дешифруются через CryptoService.
 */

import { STORAGE_KEYS, generateId, isValidPort, isValidIP, convertMaskIdn } from '../shared/constants.js';
import { CryptoService } from './crypto-service.js';

/**
 * Контроллер данных — единая точка доступа к chrome.storage.local.
 * Управляет прокси-серверами (ProxyTable), масками (MaskTable)
 * и общим статусом расширения.
 * Все публичные методы асинхронны и требуют предварительного вызова init().
 */
class DataController {
  constructor() {
    /** @private {CryptoKey|null} Импортированный мастер-ключ AES-GCM */
    this._masterKey = null;
    /** @private {boolean} Флаг готовности после вызова init() */
    this._ready = false;
  }

  /**
   * Инициализация DataController при запуске расширения.
   * При первом запуске (отсутствует мастер-ключ) генерирует ключ,
   * экспортирует в JWK, сохраняет в хранилище и создаёт пустые таблицы.
   * При повторных запусках загружает JWK из хранилища и импортирует ключ.
   *
   * @returns {Promise<void>}
   */
  async init() {
    const result = await chrome.storage.local.get([
      STORAGE_KEYS.MASTER_KEY,
      STORAGE_KEYS.PROXY_TABLE,
      STORAGE_KEYS.MASK_TABLE,
      STORAGE_KEYS.EXTENSION_STATUS
    ]);

    if (!result[STORAGE_KEYS.MASTER_KEY]) {
      /* Первый запуск — инициализация хранилища */
      const key = await CryptoService.generateMasterKey();
      const jwk = await CryptoService.exportMasterKey(key);
      await chrome.storage.local.set({
        [STORAGE_KEYS.MASTER_KEY]: jwk,
        [STORAGE_KEYS.PROXY_TABLE]: {},
        [STORAGE_KEYS.MASK_TABLE]: [],
        [STORAGE_KEYS.EXTENSION_STATUS]: true
      });
      this._masterKey = await CryptoService.importMasterKey(jwk);
    } else {
      /* Повторный запуск — загрузка существующего ключа */
      this._masterKey = await CryptoService.importMasterKey(
        result[STORAGE_KEYS.MASTER_KEY]
      );
    }

    this._ready = true;
  }

  /**
   * Проверяет, что DataController проинициализирован.
   * Выбрасывает ошибку, если init() не был вызван.
   * @private
   */
  async _ensureReady() {
    if (!this._ready) {
      throw new Error('DataController не инициализирован. Вызовите init()');
    }
  }

  /* ───── Вспомогательные методы для работы с хранилищем ───── */

  /** @private Загружает ProxyTable из chrome.storage.local */
  async _loadProxyTable() {
    const data = await chrome.storage.local.get(STORAGE_KEYS.PROXY_TABLE);
    return data[STORAGE_KEYS.PROXY_TABLE] || {};
  }

  /** @private Сохраняет ProxyTable в chrome.storage.local */
  async _saveProxyTable(table) {
    await chrome.storage.local.set({ [STORAGE_KEYS.PROXY_TABLE]: table });
  }

  /** @private Загружает MaskTable из chrome.storage.local */
  async _loadMaskTable() {
    const data = await chrome.storage.local.get(STORAGE_KEYS.MASK_TABLE);
    return data[STORAGE_KEYS.MASK_TABLE] || [];
  }

  /** @private Сохраняет MaskTable в chrome.storage.local */
  async _saveMaskTable(table) {
    await chrome.storage.local.set({ [STORAGE_KEYS.MASK_TABLE]: table });
  }

  /* ───── CRUD: ProxyTable ───── */

  /**
   * Возвращает список всех прокси с расшифрованными учётными данными.
   * Если расшифровка конкретного прокси не удалась (повреждённые данные),
   * этот прокси пропускается — остальные возвращаются без ошибки.
   * @returns {Promise<Array<{proxyId: string, host: string, port: number,
   *     username: string, password: string, isActive: boolean, isEnabled: boolean}>>}
   */
  async getAllProxies() {
    await this._ensureReady();
    const proxyTable = await this._loadProxyTable();
    const results = [];
    for (const [proxyId, entry] of Object.entries(proxyTable)) {
      try {
        const username = await CryptoService.decrypt(entry.username, this._masterKey);
        const password = await CryptoService.decrypt(entry.password, this._masterKey);
        results.push({
          proxyId,
          host: entry.host,
          port: entry.port,
          username,
          password,
          isActive: entry.isActive,
          isEnabled: entry.isEnabled
        });
      } catch (error) {
        console.warn(`[FlowLink Proxy] Ошибка расшифровки прокси ${proxyId}: ${error.message}`);
      }
    }
    return results;
  }

  /**
   * Возвращает один прокси по его ID с расшифрованными данными.
   * @param {string} proxyId - UUID прокси.
   * @returns {Promise<Object|null>} Объект прокси или null, если не найден/ошибка.
   */
  async getProxy(proxyId) {
    await this._ensureReady();
    const proxyTable = await this._loadProxyTable();
    const entry = proxyTable[proxyId];
    if (!entry) return null;
    try {
      const username = await CryptoService.decrypt(entry.username, this._masterKey);
      const password = await CryptoService.decrypt(entry.password, this._masterKey);
      return {
        proxyId,
        host: entry.host,
        port: entry.port,
        username,
        password,
        isActive: entry.isActive,
        isEnabled: entry.isEnabled
      };
    } catch (error) {
      console.warn(`[FlowLink Proxy] Ошибка расшифровки прокси ${proxyId}: ${error.message}`);
      return null;
    }
  }

  /**
   * Добавляет новый прокси-сервер.
   * Поля username и password шифруются AES-GCM перед записью в хранилище.
   *
   * @param {{host: string, port: number, username: string, password: string}} data
   * @returns {Promise<string>} Сгенерированный proxyId.
   * @throws {Error} Если порт некорректен.
   */
  async addProxy({ host, port, username, password }) {
    await this._ensureReady();
    if (!isValidIP(host)) {
      throw new Error('Введен неверный IP адрес');
    }
    if (!isValidPort(port)) {
      throw new Error('Порт должен быть целым числом в диапазоне от 1 до 65535');
    }
    if (!username) {
      throw new Error('Логин не может быть пустым');
    }
    if (!password) {
      throw new Error('Пароль не может быть пустым');
    }
    const proxyId = generateId();
    const encryptedUsername = await CryptoService.encrypt(username, this._masterKey);
    const encryptedPassword = await CryptoService.encrypt(password, this._masterKey);
    const proxyTable = await this._loadProxyTable();
    proxyTable[proxyId] = {
      host,
      port,
      username: encryptedUsername,
      password: encryptedPassword,
      isActive: true,
      isEnabled: true
    };
    await this._saveProxyTable(proxyTable);
    return proxyId;
  }

  /**
   * Частично обновляет поля существующего прокси.
   * Если username или password изменены — они перешифровываются.
   *
   * @param {string} proxyId - UUID прокси.
   * @param {{host?: string, port?: number, username?: string, password?: string,
   *     isActive?: boolean, isEnabled?: boolean}} fields - Обновляемые поля.
   * @throws {Error} Если прокси не найден или порт некорректен.
   */
  async updateProxy(proxyId, fields) {
    await this._ensureReady();
    const proxyTable = await this._loadProxyTable();
    const entry = proxyTable[proxyId];
    if (!entry) {
      throw new Error(`Прокси с ID ${proxyId} не найден`);
    }
    if (fields.host !== undefined) {
      if (!isValidIP(fields.host)) {
        throw new Error('Введен неверный IP адрес');
      }
      entry.host = fields.host;
    }
    if (fields.port !== undefined) {
      if (!isValidPort(fields.port)) {
        throw new Error('Порт должен быть целым числом в диапазоне от 1 до 65535');
      }
      entry.port = fields.port;
    }
    /* Перешифровываем только изменившиеся поля */
    if (fields.username !== undefined) {
      if (!fields.username) throw new Error('Логин не может быть пустым');
      entry.username = await CryptoService.encrypt(fields.username, this._masterKey);
    }
    if (fields.password !== undefined) {
      if (!fields.password) throw new Error('Пароль не может быть пустым');
      entry.password = await CryptoService.encrypt(fields.password, this._masterKey);
    }
    if (fields.isActive !== undefined) entry.isActive = fields.isActive;
    if (fields.isEnabled !== undefined) entry.isEnabled = fields.isEnabled;
    await this._saveProxyTable(proxyTable);
  }

  /**
   * Удаляет прокси и все связанные с ним маски.
   * Операция атомарна — обе таблицы загружаются и сохраняются за один раз.
   *
   * @param {string} proxyId - UUID прокси для удаления.
   * @throws {Error} Если прокси не найден.
   */
  async deleteProxy(proxyId) {
    await this._ensureReady();
    /* Загружаем обе таблицы одним запросом для атомарности */
    const result = await chrome.storage.local.get([
      STORAGE_KEYS.PROXY_TABLE,
      STORAGE_KEYS.MASK_TABLE
    ]);
    const proxyTable = result[STORAGE_KEYS.PROXY_TABLE] || {};
    if (!proxyTable[proxyId]) {
      throw new Error(`Прокси с ID ${proxyId} не найден`);
    }
    delete proxyTable[proxyId];
    /* Каскадное удаление масок, привязанных к этому прокси */
    const maskTable = result[STORAGE_KEYS.MASK_TABLE] || [];
    const filteredMasks = maskTable.filter(m => m.proxyId !== proxyId);
    await chrome.storage.local.set({
      [STORAGE_KEYS.PROXY_TABLE]: proxyTable,
      [STORAGE_KEYS.MASK_TABLE]: filteredMasks
    });
  }

  /**
   * Включает или отключает прокси (без удаления).
   * @param {string} proxyId - UUID прокси.
   * @param {boolean} isEnabled - Новое состояние.
   * @throws {Error} Если прокси не найден или isEnabled не boolean.
   */
  async toggleProxy(proxyId, isEnabled) {
    await this._ensureReady();
    if (typeof isEnabled !== 'boolean') {
      throw new Error('isEnabled должен быть boolean');
    }
    const proxyTable = await this._loadProxyTable();
    const entry = proxyTable[proxyId];
    if (!entry) {
      throw new Error(`Прокси с ID ${proxyId} не найден`);
    }
    entry.isEnabled = isEnabled;
    await this._saveProxyTable(proxyTable);
  }

  /* ───── CRUD: MaskTable ───── */

  /**
   * Возвращает все маски, привязанные к указанному прокси.
   * @param {string} proxyId - UUID прокси.
   * @returns {Promise<Array<{maskId: string, proxyId: string, regexString: string}>>}
   */
  async getMasksByProxy(proxyId) {
    await this._ensureReady();
    const maskTable = await this._loadMaskTable();
    return maskTable.filter(m => m.proxyId === proxyId);
  }

  /**
   * Возвращает все маски из хранилища.
   * @returns {Promise<Array<{maskId: string, proxyId: string, regexString: string}>>}
   */
  async getAllMasks() {
    await this._ensureReady();
    return this._loadMaskTable();
  }

  /**
   * Добавляет новую маску для указанного прокси.
   * @param {string} proxyId - UUID прокси, к которому привязывается маска.
   * @param {string} regexString - Строка регулярного выражения для сопоставления URL.
   * @returns {Promise<string>} Сгенерированный maskId.
   */
  async addMask(proxyId, regexString) {
    await this._ensureReady();
    const maskId = generateId();
    /* Punycode-конвертация IDN-доменов в маске */
    const punycodeStr = convertMaskIdn(regexString);
    const maskTable = await this._loadMaskTable();
    maskTable.push({ maskId, proxyId, regexString: punycodeStr });
    await this._saveMaskTable(maskTable);
    return maskId;
  }

  /**
   * Обновляет строку регулярного выражения для существующей маски.
   * @param {string} maskId - UUID маски.
   * @param {string} regexString - Новое регулярное выражение.
   * @throws {Error} Если маска не найдена.
   */
  async updateMask(maskId, regexString) {
    await this._ensureReady();
    /* Punycode-конвертация IDN-доменов в маске */
    const punycodeStr = convertMaskIdn(regexString);
    const maskTable = await this._loadMaskTable();
    const index = maskTable.findIndex(m => m.maskId === maskId);
    if (index === -1) {
      throw new Error(`Маска с ID ${maskId} не найдена`);
    }
    maskTable[index].regexString = punycodeStr;
    await this._saveMaskTable(maskTable);
  }

  /**
   * Удаляет маску по её ID.
   * @param {string} maskId - UUID маски.
   * @throws {Error} Если маска не найдена.
   */
  async deleteMask(maskId) {
    await this._ensureReady();
    const maskTable = await this._loadMaskTable();
    const filtered = maskTable.filter(m => m.maskId !== maskId);
    if (filtered.length === maskTable.length) {
      throw new Error(`Маска с ID ${maskId} не найдена`);
    }
    await this._saveMaskTable(filtered);
  }

  /**
   * Удаляет все маски для указанного прокси.
   * @param {string} proxyId - UUID прокси.
   */
  async clearMasksByProxy(proxyId) {
    await this._ensureReady();
    const maskTable = await this._loadMaskTable();
    const filtered = maskTable.filter(m => m.proxyId !== proxyId);
    await this._saveMaskTable(filtered);
  }

  /* ───── Управление статусом расширения ───── */

  /**
   * Возвращает текущее состояние расширения (включено/выключено).
   * @returns {Promise<boolean>} true — расширение активно.
   */
  async getExtensionStatus() {
    await this._ensureReady();
    const data = await chrome.storage.local.get(STORAGE_KEYS.EXTENSION_STATUS);
    return data[STORAGE_KEYS.EXTENSION_STATUS] ?? true;
  }

  /**
   * Устанавливает состояние расширения (включено/выключено).
   * @param {boolean} enabled - Новое состояние.
   */
  async setExtensionStatus(enabled) {
    await this._ensureReady();
    await chrome.storage.local.set({ [STORAGE_KEYS.EXTENSION_STATUS]: enabled });
  }
}

export { DataController };
