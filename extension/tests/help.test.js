/**
 * @fileoverview
 * Минимальные тесты help-модалки расширения.
 * Проверяют, что вкладка FAQ добавлена в HELP_TEXTS и _TABS.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { HELP_TEXTS, _TABS } from '../popup/help.js';

test('_TABS содержит вкладку faq', () => {
  assert.ok(
    _TABS.includes('faq'),
    '_TABS должен содержать "faq", фактический список: ' + _TABS.join(', '),
  );
});

test('HELP_TEXTS.faq определён', () => {
  assert.ok(
    HELP_TEXTS.faq,
    'HELP_TEXTS.faq должен быть определён',
  );
});

test('HELP_TEXTS.faq рендерит разделы FAQ', () => {
  const html = typeof HELP_TEXTS.faq === 'function' ? HELP_TEXTS.faq() : HELP_TEXTS.faq;
  assert.match(html, /Отказоустойчивость меню бэкенда/);
  assert.match(html, /Принудительное завершение бэкенда/);
  assert.match(html, /tkinter/);
});
