/**
 * @fileoverview
 * Тесты модуля управления черновиками (draft.js).
 * Проверяют сохранение, восстановление и валидацию черновиков.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

// Мокаем глобальный chrome.storage.session и document ДО импорта draft.js
const sessionData = {};
globalThis.chrome = {
  storage: {
    session: {
      async get(key) {
        if (typeof key === 'string') {
          return { [key]: sessionData[key] };
        }
        return { ...sessionData };
      },
      async set(obj) {
        Object.assign(sessionData, obj);
      },
      async remove(key) {
        delete sessionData[key];
      },
    },
  },
};

// Мокаем document для DOM-зависимых функций
const elements = {
  'proxy-id': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'proxy-host': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'proxy-port': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'proxy-username': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'proxy-password': { value: '', type: 'password', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'proxy-label': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'btn-password-toggle': {
    title: '',
    querySelector: (selector) => {
      if (selector === '.eye-closed') return { classList: { remove: () => {}, add: () => {}, toggle: () => {} } };
      if (selector === '.eye-open') return { classList: { remove: () => {}, add: () => {}, toggle: () => {} } };
      return null;
    },
  },
  'mask-id': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'mask-pattern': { value: '', closest: () => ({ classList: { add: () => {}, remove: () => {} } }) },
  'modal-proxy': { classList: { add: () => {}, remove: () => {} } },
  'modal-mask': { classList: { add: () => {}, remove: () => {} } },
  'proxy-form': {},
  'mask-form': {},
  'modal-proxy-title': { textContent: '' },
  'modal-mask-title': { textContent: '' },
};

const mockDocument = {
  getElementById: (id) => elements[id] || null,
  querySelector: (selector) => {
    if (selector === '.modal-overlay:not(.hidden)') return { id: 'modal-proxy' };
    return null;
  },
  querySelectorAll: (selector) => {
    if (selector === '.field-error') return [{ classList: { add: () => {}, remove: () => {} } }];
    if (selector === '.field-group') return [{ classList: { add: () => {}, remove: () => {} } }];
    return [];
  },
};
globalThis.document = mockDocument;

// Импортируем draft.js после мока chrome и document
const {
  getDraft,
  clearDraft,
  saveDraft,
  isDraftEligible,
  captureProxyDraft,
  captureMaskDraft,
  applyProxyDraft,
  applyMaskDraft,
  restoreUiDraft,
  isDraftValid,
} = await import('../popup/draft.js');

// Импортируем реальную функцию t из модуля i18n.js
const { t } = await import('../shared/i18n.js');

test('clearDraft удаляет ключ из storage', async () => {
  sessionData.uiDraft = { version: 1, openModal: 'modal-proxy' };
  await clearDraft();
  assert.equal(sessionData.uiDraft, undefined);
});

test('getDraft возвращает null при отсутствии черновика', async () => {
  const draft = await getDraft();
  assert.equal(draft, null);
});

test('getDraft валидирует версию: невалидный draft (version: 99) → remove + null', async () => {
  sessionData.uiDraft = { version: 99, openModal: 'modal-proxy' };
  const draft = await getDraft();
  assert.equal(draft, null);
  assert.equal(sessionData.uiDraft, undefined);
});

test('isDraftEligible: add-черновик без touched и без id → false', () => {
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: { id: '', touched: [], values: {} },
    mask: { id: '', touched: [], values: {} },
  };
  assert.equal(isDraftEligible(draft), false);
});

test('isDraftEligible: add-черновик с touched → true', () => {
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: { id: '', touched: ['host'], values: { host: 'example.com' } },
    mask: { id: '', touched: [], values: {} },
  };
  assert.equal(isDraftEligible(draft), true);
});

test('isDraftEligible: edit с id и пустым touched → true', () => {
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: { id: 'proxy-1', touched: [], values: {} },
    mask: { id: '', touched: [], values: {} },
  };
  assert.equal(isDraftEligible(draft), true);
});

test('applyProxyDraft: edit с живым прокси → вернул true', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-1', host: 'example.com', port: 8080, username: 'user', password: 'pass', label: 'Example' }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: {
      id: 'proxy-1',
      touched: ['host', 'port'],
      values: { host: 'new-host.com', port: '9090' },
      passwordVisible: false,
    },
  };
  const success = applyProxyDraft(state, draft);
  assert.equal(success, true);
});

test('applyProxyDraft: edit с удалённым прокси → false', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-2', host: 'example.com', port: 8080 }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: {
      id: 'proxy-1',
      touched: ['host'],
      values: { host: 'new-host.com' },
      passwordVisible: false,
    },
  };
  const success = applyProxyDraft(state, draft);
  assert.equal(success, false);
});

test('applyProxyDraft: пароль НЕ перезаписан, если не в touched', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-1', host: 'example.com', port: 8080, username: 'user', password: 'old-pass', label: 'Example' }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: {
      id: 'proxy-1',
      touched: ['host'],
      values: { host: 'new-host.com' },
      passwordVisible: false,
    },
  };
  applyProxyDraft(state, draft);
  assert.equal(mockDocument.getElementById('proxy-password').value, 'old-pass');
});

test('applyMaskDraft: selectedProxyId мёртвого прокси → false', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-2', host: 'example.com', port: 8080 }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-mask',
    selectedProxyId: 'proxy-1',
    mask: {
      id: 'mask-1',
      touched: ['pattern'],
      values: { pattern: '*.example.com' },
    },
  };
  const success = applyMaskDraft(state, draft);
  assert.equal(success, false);
});

test('applyMaskDraft: selectedProxyId живого прокси → вернул true', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-1', host: 'example.com', port: 8080 }],
    masks: [{ maskId: 'mask-1', pattern: '*.example.com', proxyId: 'proxy-1' }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-mask',
    selectedProxyId: 'proxy-1',
    mask: {
      id: 'mask-1',
      touched: ['pattern'],
      values: { pattern: '*.new.com' },
    },
  };
  const success = applyMaskDraft(state, draft);
  assert.equal(success, true);
});

test('applyMaskDraft: mask.proxyId !== selectedProxyId → false', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-1', host: 'example.com', port: 8080 }],
    masks: [{ maskId: 'mask-1', pattern: '*.example.com', proxyId: 'proxy-2' }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-mask',
    selectedProxyId: 'proxy-1',
    mask: {
      id: 'mask-1',
      touched: ['pattern'],
      values: { pattern: '*.new.com' },
    },
  };
  const success = applyMaskDraft(state, draft);
  assert.equal(success, false);
});

test('restoreUiDraft: при недоступном бэкенде (state.connected=false) → не чистит черновик', async () => {
  sessionData.uiDraft = { version: 1, openModal: 'modal-proxy', proxy: { id: 'proxy-1', touched: [], values: {} } };
  const state = { connected: false, proxies: [], masks: [] };
  await restoreUiDraft(state);
  assert.notEqual(sessionData.uiDraft, undefined);
});

test('isDraftValid: draft без proxy при openModal=modal-proxy → false', () => {
  const draft = { version: 1, openModal: 'modal-proxy' };
  assert.equal(isDraftValid(draft), false);
});

test('isDraftValid: draft без mask при openModal=modal-mask → false', () => {
  const draft = { version: 1, openModal: 'modal-mask' };
  assert.equal(isDraftValid(draft), false);
});

test('DRAFT_FIELD_KEYS: ввод в proxy-host добавляет host в touched', () => {
  const DRAFT_FIELD_KEYS = {
    'proxy-host': 'host',
    'proxy-port': 'port',
    'proxy-username': 'username',
    'proxy-password': 'password',
    'proxy-label': 'label',
    'mask-pattern': 'pattern',
  };
  assert.equal(DRAFT_FIELD_KEYS['proxy-host'], 'host');
  assert.equal(DRAFT_FIELD_KEYS['proxy-port'], 'port');
  assert.equal(DRAFT_FIELD_KEYS['mask-pattern'], 'pattern');
});

test('applyProxyDraft: значения из touched восстанавливаются в DOM', () => {
  const state = {
    proxies: [{ proxyId: 'proxy-1', host: 'old-host.com', port: 8080 }],
  };
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: {
      id: 'proxy-1',
      touched: ['host'],
      values: { host: 'new-host.com' },
      passwordVisible: false,
    },
  };
  applyProxyDraft(state, draft);
  assert.equal(mockDocument.getElementById('proxy-host').value, 'new-host.com');
});

test('applyProxyDraft: заголовок модалки устанавливается по наличию id', () => {
  const state = { proxies: [{ proxyId: 'proxy-1', host: 'example.com', port: 8080 }] };
  const draft = {
    version: 1,
    openModal: 'modal-proxy',
    proxy: { id: 'proxy-1', touched: [], values: {}, passwordVisible: false },
  };
  applyProxyDraft(state, draft);
  assert.equal(mockDocument.getElementById('modal-proxy-title').textContent, t('editProxyTitle'));
});

test('applyMaskDraft: заголовок модалки устанавливается по наличию id', () => {
  const state = { proxies: [{ proxyId: 'proxy-1', host: 'example.com', port: 8080 }], masks: [{ maskId: 'mask-1', pattern: '*.example.com', proxyId: 'proxy-1' }] };
  const draft = {
    version: 1,
    openModal: 'modal-mask',
    selectedProxyId: 'proxy-1',
    mask: { id: 'mask-1', touched: [], values: {} },
  };
  applyMaskDraft(state, draft);
  assert.equal(mockDocument.getElementById('modal-mask-title').textContent, t('editMaskTitle'));
});

test('restoreUiDraft: при невалидном openModal → clearDraft', async () => {
  sessionData.uiDraft = { version: 1, openModal: 'invalid-modal' };
  const state = { proxies: [], masks: [] };
  await restoreUiDraft(state);
  assert.equal(sessionData.uiDraft, undefined);
});

test('restoreUiDraft: при отсутствии черновика → нет ошибок', async () => {
  const state = { proxies: [], masks: [] };
  await restoreUiDraft(state);
  assert.equal(sessionData.uiDraft, undefined);
});