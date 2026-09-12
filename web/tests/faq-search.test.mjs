import test from 'node:test';
import assert from 'node:assert/strict';
import { createFaqSearch } from '../src/solutions.mjs';

test('search debounces input and ignores responses superseded by a newer query', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls = [], updates = [];
  const search = createFaqSearch({ request: (path) => new Promise((resolve) => calls.push({ path, resolve })), update: (value) => updates.push(value) });
  search.input('ci'); search.input('cigam');
  t.mock.timers.tick(139); assert.equal(calls.length, 0);
  t.mock.timers.tick(1); assert.equal(calls[0].path, '/api/faq/search?q=cigam');
  search.input('siagri');
  calls[0].resolve({ items: [{ title: 'CIGAM' }] }); await Promise.resolve();
  assert.equal(updates.at(-1).searching, true);
  t.mock.timers.tick(140); calls[1].resolve({ items: [{ title: 'SIAGRI' }] }); await Promise.resolve();
  assert.deepEqual(updates.at(-1).searchResults, [{ title: 'SIAGRI' }]);
  search.input(''); assert.equal(updates.at(-1).searchResults, null);
});

test('leaving solutions cancels pending search and errors remain recoverable', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const updates = []; let reject;
  const search = createFaqSearch({ request: () => new Promise((_, fail) => { reject = fail; }), update: (value) => updates.push(value) });
  search.input('cigam'); t.mock.timers.tick(140);
  reject(new Error('offline')); await Promise.resolve();
  assert.equal(updates.at(-1).error, 'Não foi possível buscar. Tente novamente.');
  search.input('new'); search.cancel(); const count = updates.length;
  t.mock.timers.tick(140); assert.equal(updates.length, count);
});
