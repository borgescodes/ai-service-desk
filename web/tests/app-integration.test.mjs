import test from 'node:test';
import assert from 'node:assert/strict';

// Minimal browser boundary: run the real app and API client; control only DOM storage and transport.
const tick = () => new Promise(resolve => setImmediate(resolve));
let serial = 0;
async function boot(path, respond) {
  const events = {};
  const newChat = { addEventListener(name, handler) { events.newChat = handler; } };
  const queueRow = { dataset: { requestId: 'R-1' }, addEventListener(name, handler) { events.selectApproval = handler; } };
  const persona = { dataset: { persona: 'tecnico-cdm' }, addEventListener(name, handler) { events.persona = handler; } };
  const field = { value: '', addEventListener() {} };
  const form = { addEventListener(name, handler) { events[name] = handler; }, querySelector() { return field; } };
  const root = { innerHTML: '', setAttribute() {}, querySelectorAll(selector) { return selector === '.queue-row[data-request-id]' ? [queueRow] : selector === '[data-persona]' ? [persona] : []; }, querySelector(selector) { return selector === '[data-action="new-chat"]' ? newChat : selector === '#jup-form' ? form : selector === '#jup-message' ? field : null; } };
  const win = { location: new URL(`http://demo${path}`), addEventListener(name, fn) { events[name] = fn; } };
  win.history = { pushState(_a, _b, path) { win.location = new URL(path, win.location); } };
  globalThis.document = { querySelector(selector) { return selector === '#app' ? root : null; } };
  globalThis.window = win;
  globalThis.fetch = async (url, options) => {
    const payload = url === '/api/session/identities'
      ? ['pedro-miranda', 'tecnico-cdm', 'tecnico-m365', 'tecnico-geral'].map(identity_id => ({ identity_id }))
      : await respond(url, options);
    return new Response(JSON.stringify(payload), { status: 200 });
  };
  await import(`../src/app.mjs?test=${++serial}`); await tick();
  return { root, field, async selectApproval() { events.selectApproval(); await tick(); }, async reset() { await events.newChat?.(); await tick(); }, async switchPersona() { await events.persona?.(); await tick(); }, async go(path) { win.location = new URL(`http://demo${path}`); events.popstate(); await tick(); }, async send(text) { field.value = text; events.submit({ preventDefault() {}, currentTarget: form }); await tick(); } };
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


test('new chat resets backend conversation and clears the visible draft', async () => {
  const calls = [];
  const ui = await boot('/jup', (url, options) => { calls.push([url, options]); return {}; });
  ui.field.value = 'rascunho';
  await ui.reset();
  assert.ok(calls.some(([url]) => url === '/api/jup/conversation/reset'));
  assert.ok(!calls.some(([url]) => url === '/api/demo/reset'));
  assert.match(ui.root.innerHTML, /data-state="idle"/);
});

test('persona control loads the assigned technician queue with backend identity', async () => {
  const calls = [];
  const ui = await boot('/jup', (url, options) => { calls.push([url, options]); return []; });
  await ui.switchPersona();
  const queue = calls.find(([url]) => url === '/api/operations/approvals');
  assert.ok(queue);
  assert.equal(queue[1].headers['X-Demo-Identity'], 'tecnico-cdm');
});

test('fast successful replies wait for bounded presentation time', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const ui = await boot('/jup', () => ({ status: 'SOCIAL', assistant_message: 'Olá, Pedro!' }));
  await ui.send('Olá');
  assert.match(ui.root.innerHTML, /Pensando/);
  assert.doesNotMatch(ui.root.innerHTML, /Olá, Pedro!/);
  t.mock.timers.tick(2500); await tick();
  assert.match(ui.root.innerHTML, /Olá, Pedro!/);
  assert.doesNotMatch(ui.root.innerHTML, /conversation-message--thinking/);
});

test('late operational detail cannot leak into another persona', async () => {
  let finish;
  const ui = await boot('/demo/operacao/cdm', url => url === '/api/operations/approvals/R-1'
    ? new Promise(resolve => { finish = resolve; }) : []);
  await ui.selectApproval();
  await ui.go('/demo/operacao/m365');
  finish({ request_id: 'R-1', purpose: 'Contexto privado CDM', state: 'PENDING_APPROVAL' });
  await tick();
  assert.doesNotMatch(ui.root.innerHTML, /Contexto privado CDM/);
});
