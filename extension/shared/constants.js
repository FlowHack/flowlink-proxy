let API_BASE = 'http://127.0.0.1:8081/api';

const APP_VERSION = '0.2.0';
const GITHUB_RELEASES_URL = 'https://github.com/flowhack/flowlink-proxy/releases/latest';
const GITHUB_API_RELEASES = 'https://api.github.com/repos/flowhack/flowlink-proxy/releases/latest';

function setApiPort(port) {
  API_BASE = `http://127.0.0.1:${port}/api`;
}

function generateId() {
  return crypto.randomUUID();
}

function isValidPort(port) {
  return Number.isInteger(port) && port >= 1 && port <= 65535;
}

const IP_REGEX = /^(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})$/;

function isValidIP(ip) {
  return IP_REGEX.test(ip);
}

function convertMaskIdn(mask) {
  if (!/[^\x20-\x7E]/.test(mask)) return mask;
  try {
    const ED = '\x00ED\x00';
    const withMarkers = mask.replace(/\\\./g, ED);
    const parts = withMarkers.split('.');
    const converted = parts.map(part => {
      if (!/[^\x20-\x7E]/.test(part)) return part;
      try {
        const url = new URL('http://' + part);
        return url.hostname;
      } catch {
        return part;
      }
    });
    return converted.join('.').split(ED).join('\\.');
  } catch {
    return mask;
  }
}

function convertWildcardToRegex(pattern) {
  let chars = pattern.split('');
  let escaped = '';
  for (let i = 0; i < chars.length; i++) {
    const c = chars[i];
    if ('*?.+^${}()|[]\\'.includes(c)) {
      if (c === '*') {
        escaped += '.*';
      } else if (c === '?') {
        escaped += '.';
      } else {
        escaped += '\\' + c;
      }
    } else {
      escaped += c;
    }
  }
  return escaped;
}

export { API_BASE, setApiPort, generateId, isValidPort, isValidIP, convertMaskIdn, convertWildcardToRegex, APP_VERSION, GITHUB_RELEASES_URL, GITHUB_API_RELEASES };
