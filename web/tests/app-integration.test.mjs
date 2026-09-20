import test from 'node:test';
import assert from 'node:assert/strict';

// Minimal browser boundary: run the real app and API client; control only DOM storage and transport.
const tick = () => new Promise(resolve => setImmediate(resolve));
let serial = 0;
async function boot(path, respond, identities = [
  { identity_id: 'pedro-miranda', name: 'Fulano de Tal', email: 'fulano.tal@juparana.com.br', job_title: 'Colaborador', area: 'Revenda - Matriz', role: 'REQUESTER' },
  { identity_id: 'tecnico-cdm', name: 'Técnico CDM', role: 'TECHNICIAN' },
  { identity_id: 'tecnico-m365', name: 'Técnico Microsoft 365', role: 'TECHNICIAN' },
  { identity_id: 'tecnico-geral', name: 'Técnico Geral', role: 'TECHNICIAN' },
]) {
  const events = {};
  const identityValues = { name: 'Ana da Silva', email: 'ana.silva@juparana.com.br', job_title: 'Analista UBS', area: 'UBS' };
  const identityForm = { addEventListener(name, handler) { events.configureIdentity = handler; } };
  const newChat = { addEventListener(name, handler) { events.newChat = handler; } };
  const queueRow = { dataset: { requestId: 'R-1' }, addEventListener(name, handler) { events.selectApproval = handler; } };
  const approve = { addEventListener(name, handler) { events.approve = handler; } };
  const personas = identities.map(({ identity_id: identityId }) => ({
    dataset: { persona: identityId },
    addEventListener(name, handler) { if (name === 'click') events[`persona-${identityId}`] = handler; },
  }));
  const command = { addEventListener(name, handler) { events[`command-${name}`] = handler; }, focus() {} };
  const field = { value: '', addEventListener(name, handler) { events[`field-${name}`] = handler; }, focus() {} };
  const form = { addEventListener(name, handler) { events[name] = handler; }, querySelector() { return field; } };
  const root = { innerHTML: '', setAttribute() {}, querySelectorAll(selector) { return selector === '.queue-row[data-request-id]' ? [queueRow] : selector === '[data-persona]' ? personas : []; }, querySelector(selector) { return selector === '[data-action="approve"]' ? approve : selector === '[data-action="new-chat"]' ? newChat : selector === '#demo-identity-form' ? identityForm : selector === '#jup-form' ? form : selector === '#jup-message' ? field : selector === '[data-command="/solicitacoes"]' || selector === '[data-command-menu] [data-command]' ? command : null; } };
  const win = { location: new URL(`http://demo${path}`), addEventListener(name, fn) { events[name] = fn; } };
  win.history = { pushState(_a, _b, path) { win.location = new URL(path, win.location); } };
  globalThis.document = { querySelector(selector) { return selector === '#app' ? root : null; } };
  globalThis.window = win;
  globalThis.FormData = class { get(name) { return identityValues[name]; } };
  globalThis.fetch = async (url, options) => {
    const payload = url === '/api/session/identities' && (!options || options.method === 'GET')
      ? identities
      : await respond(url, options);
    return new Response(JSON.stringify(payload), { status: 200 });
  };
  await import(`../src/app.mjs?test=${++serial}`); await tick();
  return { root, field, async approve() { await events.approve(); await tick(); }, async selectApproval() { events.selectApproval(); await tick(); }, async reset() { await events.newChat?.(); await tick(); }, async configureIdentity() { events.configureIdentity?.({ preventDefault() {}, currentTarget: identityForm }); await tick(); }, async switchPersona() { await events['persona-tecnico-cdm']?.(); await tick(); }, async switchTo(identityId) { await events[`persona-${identityId}`]?.(); await tick(); }, async go(path) { win.location = new URL(`http://demo${path}`); events.popstate(); await tick(); }, async send(text) { field.value = text; events.submit({ preventDefault() {}, currentTarget: form }); await tick(); }, async type(text) { field.value = text; events['field-input']?.({ target: field }); await tick(); }, async selectCommand() { events['command-click']?.(); await tick(); }, async escapeCommand() { events['field-keydown']?.({ key: 'Escape', preventDefault() {}, currentTarget: field }); await tick(); } };
}

test('late FAQ response cannot replace an article after navigation', async () => {
  let finish;
  const ui = await boot('/', url => url === '/api/faq' ? new Promise(resolve => { finish = resolve; }) : { knowledge_id: 'KB', title: 'Artigo atual', answer: 'Resposta aprovada.' });
  await ui.go('/solucoes/KB');
  assert.match(ui.root.innerHTML, /Artigo atual/);
  finish({ groups: [] }); await tick();
  assert.match(ui.root.innerHTML, /Artigo atual/);
});

test('operational sidebar preserves the Microsoft technician route', async () => {
  const ui = await boot('/demo/operacao/m365', () => []);
  assert.match(ui.root.innerHTML, /href="\/demo\/operacao\/m365" data-route="approvals"/);
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

test('requester chat and understood context survive technician navigation', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const ui = await boot('/jup', url => {
    if (url === '/api/jup/messages') return { status: 'PENDING_APPROVAL', assistant_message: 'Seu pedido foi encaminhado.', request_id: 'R-1' };
    if (url === '/api/requests/R-1') return { system: 'CDM', requested_role: 'SOLICITANTE', purpose: 'Materiais', confidence: 0.9, policy: { decision: 'PENDING_APPROVAL' }, state_label: 'Aguardando aprovação' };
    return [];
  });
  await ui.send('Preciso de acesso ao CDM');
  t.mock.timers.tick(2500); await tick();
  await ui.switchPersona();
  assert.doesNotMatch(ui.root.innerHTML, /Preciso de acesso ao CDM/);
  await ui.switchTo('pedro-miranda');
  assert.match(ui.root.innerHTML, /Preciso de acesso ao CDM/);
  assert.match(ui.root.innerHTML, /Seu pedido foi encaminhado/);
  assert.match(ui.root.innerHTML, /Aguardando aprovação/);
});

test('requester histories remain isolated and reset only the active requester', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const identities = [
    { identity_id: 'pedro-miranda', name: 'Ana', role: 'REQUESTER' },
    { identity_id: 'carlos', name: 'Carlos', role: 'REQUESTER' },
    { identity_id: 'tecnico-cdm', name: 'Técnico CDM', role: 'TECHNICIAN' },
  ];
  const calls = [];
  const ui = await boot('/jup', (url, options) => {
    calls.push([url, options]);
    if (url === '/api/jup/messages') return { status: 'SOCIAL', assistant_message: `Resposta para ${options.headers['X-Demo-Identity']}` };
    return [];
  }, identities);
  await ui.send('Mensagem da Ana'); t.mock.timers.tick(2500); await tick();
  await ui.switchTo('carlos');
  assert.doesNotMatch(ui.root.innerHTML, /Mensagem da Ana/);
  await ui.send('Mensagem do Carlos'); t.mock.timers.tick(2500); await tick();
  await ui.switchTo('pedro-miranda');
  assert.match(ui.root.innerHTML, /Mensagem da Ana/);
  assert.doesNotMatch(ui.root.innerHTML, /Mensagem do Carlos/);
  await ui.switchTo('carlos');
  await ui.reset();
  assert.doesNotMatch(ui.root.innerHTML, /Mensagem do Carlos/);
  await ui.switchTo('pedro-miranda');
  assert.match(ui.root.innerHTML, /Mensagem da Ana/);
  const reset = calls.find(([url]) => url === '/api/jup/conversation/reset');
  assert.equal(reset[1].headers['X-Demo-Identity'], 'carlos');
});

test('requester chat survives requests, article, and request CTA navigation', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const ui = await boot('/jup', url => {
    if (url === '/api/jup/messages') return { status: 'REQUESTS_LISTED', assistant_message: 'Veja suas solicitações.', presentation: { cta: 'REQUESTS' } };
    if (url === '/api/faq/KB-1') return { knowledge_id: 'KB-1', title: 'Artigo', answer: 'Resposta aprovada.' };
    return [];
  });
  await ui.send('/solicitacoes'); t.mock.timers.tick(2500); await tick();
  await ui.go('/requests'); await ui.go('/jup');
  assert.match(ui.root.innerHTML, /Veja suas solicitações/);
  await ui.go('/solucoes/KB-1'); await ui.go('/jup');
  assert.match(ui.root.innerHTML, /Veja suas solicitações/);
});

test('slash command is selectable by keyboard-ready menu control and sends the deterministic message', async () => {
  const calls = [];
  const ui = await boot('/jup', (url, options) => {
    calls.push([url, options]);
    return { status: 'REQUESTS_LISTED', assistant_message: 'Você ainda não tem solicitações para acompanhar.', presentation: { cta: null } };
  });
  await ui.type('/');
  assert.match(ui.root.innerHTML, /data-command-menu/);
  await ui.selectCommand();
  const request = calls.find(([url]) => url === '/api/jup/messages');
  assert.equal(JSON.parse(request[1].body).message, '/solicitacoes');
  assert.match(ui.root.innerHTML, /\/solicitacoes/);
});

test('Escape closes slash command menu without clearing the composer field', async () => {
  const ui = await boot('/jup', () => []);
  await ui.type('/');
  await ui.escapeCommand();
  assert.equal(ui.field.value, '/');
  assert.doesNotMatch(ui.root.innerHTML, /data-command-menu/);
});

test('demo identity form creates and activates a trusted requester', async () => {
  const calls = [];
  const configured = { identity_id: 'demo-requester-1', name: 'Ana da Silva', email: 'ana.silva@juparana.com.br', job_title: 'Analista UBS', area: 'UBS', role: 'REQUESTER' };
  const ui = await boot('/jup', (url, options) => {
    calls.push([url, options]);
    if (url === '/api/session/identities') return configured;
    return {};
  });

  await ui.configureIdentity();

  const creation = calls.find(([url]) => url === '/api/session/identities');
  assert.ok(creation);
  assert.deepEqual(JSON.parse(creation[1].body), {
    name: 'Ana da Silva',
    email: 'ana.silva@juparana.com.br',
    job_title: 'Analista UBS',
    area: 'UBS',
  });
  assert.match(ui.root.innerHTML, /Ana da Silva/);
  assert.match(ui.root.innerHTML, /Olá, <strong>Ana<\/strong>! Como posso ajudar\?/);

  await ui.reset();
  const reset = calls.find(([url]) => url === '/api/jup/conversation/reset');
  assert.equal(reset[1].headers['X-Demo-Identity'], 'demo-requester-1');
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


test('completed server result remains selectable after leaving and reopening the queue', async () => {
  const pending = { request_id: 'R-1', state: 'PENDING_APPROVAL', purpose: 'Materiais', version: 1 };
  const final = { ...pending, state: 'COMPLETED', version: 3 };
  let completed = false;
  const ui = await boot('/demo/operacao/cdm', url => {
    if (url === '/api/requests/R-1/approve') { completed = true; return final; }
    if (url === '/api/operations/approvals/R-1') return completed ? final : pending;
    if (url === '/api/operations/approvals') return completed ? [] : [pending];
    return [];
  });
  await ui.approve();
  assert.match(ui.root.innerHTML, /class="queue-row"[^>]*data-request-id="R-1"/);
  assert.doesNotMatch(ui.root.innerHTML, /data-action="approve"/);
  await ui.go('/'); await ui.go('/demo/operacao/cdm');
  assert.match(ui.root.innerHTML, /class="queue-row"[^>]*data-request-id="R-1"/);
  assert.match(ui.root.innerHTML, /Concluída/);
});


test('selecting an externally completed request updates both its row and detail', async () => {
  const item = { request_id: 'R-1', state: 'PENDING_APPROVAL', purpose: 'Materiais' };
  const ui = await boot('/demo/operacao/cdm', url => url === '/api/operations/approvals/R-1' ? { ...item, state: 'COMPLETED' } : url === '/api/operations/approvals' ? [item] : []);
  await ui.selectApproval();
  const row = ui.root.innerHTML.match(/class="queue-row"[^]*?<\/button>/)?.[0];
  assert.match(row, /Concluída/);
  assert.doesNotMatch(ui.root.innerHTML, /data-action="approve"/);
});
