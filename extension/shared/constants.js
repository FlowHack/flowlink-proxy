/**
 * @fileoverview
 * Константы расширения.
 * Единственная ответственность: хранение констант.
 */

import { isValidPort } from './utils.js';

// Базовый URL API бэкенда. Меняется через setApiPort() при кастомном порте.
// Используется let, а не const, потому что порт может изменяться через setApiPort.
let API_BASE = 'http://127.0.0.1:8081/api';

// URL страницы последнего релиза на GitHub (для кнопки "Скачать")
const GITHUB_RELEASES_URL = 'https://github.com/FlowHack/flowlink-proxy/releases/latest';
// URL GitHub API для проверки последней версии (для автообновления)
const GITHUB_API_RELEASES = 'https://api.github.com/repos/flowhack/flowlink-proxy/releases/latest';

// Заглушка: URL расширения в магазине (после публикации заменить на реальный)
// URL расширения в магазине. Будет добавлен после публикации.
const EXTENSION_STORE_URL = '';

/**
 * Изменяет порт API в базовом URL.
 * @param {number} port — новый порт (например 9091).
 */
function setApiPort(port) {
  if (!isValidPort(port)) {
    console.warn('[FlowLink Proxy] setApiPort: неверный порт:', port);
    return;
  }
  API_BASE = `http://127.0.0.1:${port}/api`;
}

export { API_BASE, setApiPort, GITHUB_RELEASES_URL, GITHUB_API_RELEASES, EXTENSION_STORE_URL };
