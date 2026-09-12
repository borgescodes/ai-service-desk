import test from 'node:test';
import assert from 'node:assert/strict';

// Minimal browser boundary: run the real app and API client; control only DOM storage and transport.
const tick = () => new Promise(resolve => setImmediate(resolve));
let serial = 0;
async function boot(path, respond) {
  const events = {};
  const field = { value: '', addEventListener() {} };
  const form = { addEventListener(name, handler) { events[name] = handler; }, querySelector() { return field; } };
  const root = { innerHTML: '', setAttribute() {}, querySelectorAll() { return []; }, querySelector(selector) { return selector === '#jup-form' ? form : selector === '#jup-message' ? field : null; } };
  const win = { location: new URL(`http://demo${path}`), addEventListener(name, fn) { events[name] = fn; } };
  globalThis.document = { querySelector(selector) { return selector === '#app' ? root : null; } };
  globalThis.window = win;
  globalThis.fetch = async (url, options) => {
    const payload = url === '/api/session/identities'
      ? ['pedro-miranda', 'tecnico-cdm', 'tecnico-m365', 'tecnico-geral'].map(identity_id => ({ identity_id }))
      : await respond(url, options);
    return new Response(JSON.stringify(payload), { status: 200 });
  };
  await import(`../src/app.mjs?test=${++serial}`); await tick();
  return { root, field, async go(path) { win.location = new URL(`http://demo${path}`); events.popstate(); await tick(); }, async send(text) { field.value = text; events.submit({ preventDefault() {}, currentTarget: form }); await tick(); } };
}

test('late FAQ response cannot replace an article after navigation', async () => {
  let finish;
  const ui = await boot('/', url => url === '/api/faq' ? new Promise(resolve => { finish = resolve; }) : { knowledge_id: 'KB', title: 'Artigo atual', answer: 'Resposta aprovada.' });
  await ui.go('/solucoes/KB');
  assert.match(ui.root.innerHTML, /Artigo atual/);
  finish({ groups: [] }); await tick();
  assert.match(ui.root.innerHTML, /Artigo atual/);
});

test('operational tabs preserve the Microsoft technician route', async () => {
  const ui = await boot('/demo/operacao/m365', () => []);
  assert.match(ui.root.innerHTML, /href="\/demo\/operacao\/m365" data-route-link="approvals"/);
});

test('late chat result is not shown under a different route identity', async () => {
  let finish;
  const ui = await boot('/jup', url => url === '/api/jup/messages' ? new Promise(resolve => { finish = resolve; }) : []);
  await ui.send('minha mensagem'); await ui.go('/demo/operacao/cdm');
  finish({ status: 'SUPPORT_RESOLVED', assistant_message: 'Resposta da sessão anterior' }); await tick();
  await ui.go('/jup');
  assert.doesNotMatch(ui.root.innerHTML, /Resposta da sessão anterior/);
  assert.match(ui.root.innerHTML, /data-state="idle"/);
});

test('transport failure keeps conversation and composer visible with warning state', async () => {
  const ui = await boot('/jup', () => { throw new Error('offline'); });
  await ui.send('Preciso de ajuda');
  assert.match(ui.root.innerHTML, /Preciso de ajuda/);
  assert.match(ui.root.innerHTML, /data-state="warning"/);
  assert.match(ui.root.innerHTML, /id="jup-form"/);
  assert.match(ui.root.innerHTML, /role="alert"/);
});
