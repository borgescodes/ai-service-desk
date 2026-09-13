import test from 'node:test';
import assert from 'node:assert/strict';

const tick = () => new Promise(resolve => setImmediate(resolve));
let serial = 0;
async function boot(path, respond) {
  const events = {}, fieldEvents = {};
  const field = { value: '', addEventListener(name, handler) { fieldEvents[name] = handler; } };
  const form = { addEventListener(name, handler) { events[name] = handler; }, querySelector() { return field; } };
  const topics = ['', 'rede-internet'].map(category => ({
    dataset: { category }, addEventListener(name, handler) { this[name] = handler; }, setAttribute() {},
  }));
  const results = { innerHTML: '', setAttribute() {}, querySelectorAll() { return []; }, querySelector() { return null; } };
  const root = { innerHTML: '', setAttribute() {},
    querySelectorAll(selector) { return selector === '[data-category]' ? topics : []; },
    querySelector(selector) { return ({ '#jup-form': path.startsWith('/jup') ? form : null, '#jup-message': path.startsWith('/jup') ? field : null, '#faq-search': field, '#faq-results': results })[selector] ?? null; },
  };
  const win = { location: new URL('http://demo' + path), addEventListener(name, handler) { events[name] = handler; } };
  globalThis.document = { querySelector(selector) { return selector === '#app' ? root : null; } };
  globalThis.window = win;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(url === '/api/session/identities'
      ? [{ identity_id: 'pedro-miranda' }] : await respond(url, options)), { status: 200 });
  };
  await import('../src/app.mjs?showcase=' + ++serial); await tick();
  return { root, results, field, fieldEvents, topics, calls };
}

test('opening a scenario draft renders editable composer without a POST or identity from query', async () => {
  const ui = await boot('/jup?draft=Preciso%20de%20acesso%20ao%20CDM&identity=admin', () => ({}));
  assert.match(ui.root.innerHTML, /<textarea[^>]*>Preciso de acesso ao CDM<\/textarea>/);
  assert.equal(ui.calls.filter(call => call.options.method === 'POST').length, 0);
});

test('clicking a topic combines its key with the preserved search field', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const ui = await boot('/', url => url === '/api/faq' ? { groups: [] } : { items: [{ title: 'Wi-Fi', knowledge_id: 'KB-WIFI', category: 'Rede e internet' }] });
  ui.field.value = 'Wi-Fi'; ui.fieldEvents.input({ target: ui.field });
  assert.equal(typeof ui.topics[1].click, 'function');
  ui.topics[1].click(); t.mock.timers.tick(140); await tick();
  assert.ok(ui.calls.some(call => call.url === '/api/faq/search?q=Wi-Fi&category=rede-internet'));
  assert.match(ui.results.innerHTML, /Wi-Fi/);
  assert.equal(ui.field.value, 'Wi-Fi');
});
