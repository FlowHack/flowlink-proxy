/**
 * @fileoverview
 * Криптографический сервис для FlowLink Proxy.
 * Реализует шифрование и дешифрование AES-GCM 256 для полей username/password.
 * Мастер-ключ генерируется при первой установке и хранится в chrome.storage.local в формате JWK.
 */

/**
 * Преобразует ArrayBuffer в Base64-строку для хранения в JSON (chrome.storage.local).
 * @param {ArrayBuffer} buffer - Исходные бинарные данные.
 * @returns {string} Base64-представление.
 */
function _arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Преобразует Base64-строку обратно в ArrayBuffer для передачи в Web Crypto API.
 * @param {string} base64 - Строка в Base64.
 * @returns {ArrayBuffer} Бинарные данные.
 */
function _base64ToArrayBuffer(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Сервис шифрования AES-GCM для защиты учётных данных прокси.
 * Все методы статические — не требует создания экземпляра.
 */
class CryptoService {
  static ALGORITHM = { name: 'AES-GCM', length: 256 };
  static KEY_USAGES = ['encrypt', 'decrypt'];

  /**
   * Генерирует новый мастер-ключ AES-GCM 256 бит.
   * Ключ создаётся с флагом extractable: true, чтобы его можно было
   * экспортировать в JWK и сохранить в chrome.storage.local.
   * @returns {Promise<CryptoKey>} Сгенерированный мастер-ключ.
   */
  static async generateMasterKey() {
    return crypto.subtle.generateKey(
      CryptoService.ALGORITHM,
      true,
      CryptoService.KEY_USAGES
    );
  }

  /**
   * Экспортирует мастер-ключ в формат JWK для хранения в chrome.storage.local.
   * @param {CryptoKey} key - Мастер-ключ.
   * @returns {Promise<JsonWebKey>} JWK-представление ключа.
   */
  static async exportMasterKey(key) {
    return crypto.subtle.exportKey('jwk', key);
  }

  /**
   * Импортирует мастер-ключ из JWK для использования в операциях шифрования.
   * Флаг extractable: false — ключ не может быть повторно экспортирован,
   * что соответствует принципу минимальных привилегий.
   * @param {JsonWebKey} jwk - JWK-представление ключа.
   * @returns {Promise<CryptoKey>} Мастер-ключ для encrypt/decrypt.
   */
  static async importMasterKey(jwk) {
    return crypto.subtle.importKey(
      'jwk',
      jwk,
      CryptoService.ALGORITHM,
      false,
      CryptoService.KEY_USAGES
    );
  }

  /**
   * Шифрует строку алгоритмом AES-GCM.
   * Генерирует уникальный 12-байтный IV (crypto.getRandomValues) для каждого вызова.
   * IV и шифротекст возвращаются как Base64-строки для JSON-сериализации.
   * @param {string} plaintext - Открытый текст для шифрования.
   * @param {CryptoKey} key - Мастер-ключ.
   * @returns {Promise<{iv: string, ciphertext: string}>} IV и шифротекст в Base64.
   */
  static async encrypt(plaintext, key) {
    /* Защита от null/undefined — шифруем пустую строку */
    const safeInput = (plaintext == null) ? '' : plaintext;
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(safeInput);
    const ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      encoded
    );
    return {
      iv: _arrayBufferToBase64(iv),
      ciphertext: _arrayBufferToBase64(ciphertext)
    };
  }

  /**
   * Дешифрует данные, зашифрованные AES-GCM.
   * Принимает Base64-строки IV и шифротекста, возвращает исходную строку.
   * @param {{iv: string, ciphertext: string}} payload - IV и шифротекст в Base64.
   * @param {CryptoKey} key - Мастер-ключ.
   * @returns {Promise<string>} Расшифрованный текст.
   */
  static async decrypt(payload, key) {
    const iv = _base64ToArrayBuffer(payload.iv);
    const ciphertext = _base64ToArrayBuffer(payload.ciphertext);
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext
    );
    return new TextDecoder().decode(decrypted);
  }
}

export { CryptoService };
