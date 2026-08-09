/**
 * Тесты валидации портов расширения.
 *
 * Покрывает унифицированную проверку isValidPort (utils.js) и извлечение
 * порта из базового URL (extractPortFromBase в port_discovery.js).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { isValidPort } from '../shared/utils.js';
import { extractPortFromBase } from '../shared/port_discovery.js';

test('isValidPort принимает корректные порты', () => {
  assert.equal(isValidPort(1), true);
  assert.equal(isValidPort(65535), true);
  assert.equal(isValidPort(8081), true);
});

test('isValidPort отклоняет некорректные значения', () => {
  assert.equal(isValidPort(0), false);
  assert.equal(isValidPort(-1), false);
  assert.equal(isValidPort(65536), false);
  assert.equal(isValidPort(8081.5), false);
  assert.equal(isValidPort('8081'), false);
  assert.equal(isValidPort(null), false);
  assert.equal(isValidPort(undefined), false);
});

test('extractPortFromBase извлекает порт из базового URL', () => {
  assert.equal(extractPortFromBase('http://127.0.0.1:8091/api'), 8091);
  assert.equal(extractPortFromBase('http://127.0.0.1:8081/api'), 8081);
});

test('extractPortFromBase возвращает 8081 для некорректного порта', () => {
  assert.equal(extractPortFromBase('http://127.0.0.1:99999/api'), 8081);
  assert.equal(extractPortFromBase('http://example.com/api'), 8081);
  assert.equal(extractPortFromBase('invalid'), 8081);
});
