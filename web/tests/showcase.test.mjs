import test from 'node:test';
import assert from 'node:assert/strict';
import * as solutions from '../src/solutions.mjs';
import { renderJupWorkspace } from '../src/components.mjs';
import { renderApprovedKnowledgeBody } from '../src/knowledge_content.mjs';

test('four functional topic filters preserve the query and combine request parameters', () => {
  const html = solutions.renderSolutionsHome({ searchQuery: 'Outlook', category: 'rede-internet' });
  for (const label of ['Acessos e rotinas', 'Erros em sistemas', 'Impressão, Office e aplicativos', 'Rede e internet']) assert.ok(html.includes(label));
  assert.match(html, /data-category="rede-internet"[^>]*aria-pressed="true"/);
  assert.match(html, /value="Outlook"/);
  assert.equal(solutions.faqSearchPath(' Wi-Fi ', 'rede-internet'), '/api/faq/search?q=Wi-Fi&category=rede-internet');
});

test('topic-only search requests results and cannot leak a previous topic', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls = [], updates = [];
  const search = solutions.createFaqSearch({ request: path => new Promise(resolve => calls.push({ path, resolve })), update: value => updates.push(value) });
  search.input('', 'rede-internet'); t.mock.timers.tick(140);
  assert.equal(calls.length, 1);
  search.input('Outlook', 'impressao-office-aplicativos');
  calls[0].resolve({ items: [{ title: 'Rede' }] }); await Promise.resolve();
  assert.equal(updates.at(-1).searching, true);
  t.mock.timers.tick(140);
  calls[1].resolve({ items: [{ title: 'Outlook' }] }); await Promise.resolve();
  assert.deepEqual(updates.at(-1).searchResults, [{ title: 'Outlook' }]);
});

test('filtered results show only response items and empty search offers editable draft', () => {
  const html = solutions.renderSolutionsResults({ category: 'rede-internet', searchResults: [{ knowledge_id: 'KB-WIFI', title: 'Wi-Fi', category: 'Rede e internet' }], groups: [{ label: 'Old', items: [{ title: 'Outlook' }] }] });
  assert.match(html, /Wi-Fi/); assert.doesNotMatch(html, /Outlook/);
  const empty = solutions.renderSolutionsResults({ searchQuery: 'zzzz', searchResults: [] });
  assert.match(empty, /Perguntar ao Jup/); assert.match(empty, /draft=zzzz/);
});

test('demo scenarios are drafts with no official knowledge identifiers', () => {
  const html = solutions.renderDemoScenarios();
  assert.match(html, /Experimente com o Jup/);
  assert.match(html, /\/jup\?draft=/);
  assert.doesNotMatch(html, /knowledge_id|data-knowledge-id|data-solution-link/);
});

test('conversation owns contextual avatars and thinking message with three dots', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'USER', text: 'Olá' }, { role: 'JUP', text: 'Olá, como posso ajudar?' }], loading: true });
  assert.match(html, /conversation-message--user/);
  assert.match(html, /conversation-message--jup[^]*?jup-avatar/);
  assert.doesNotMatch(html, /conversation-visual|jup-welcome/);
  assert.match(html, /conversation-message--thinking[^]*?data-state="thinking"/);
  assert.match(html, /thinking-dots[^]*?<span[^>]*>\.<\/span><span[^>]*>\.<\/span><span[^>]*>\.<\/span>/);
  assert.match(html, /data-action="scroll-bottom"/);
  assert.match(html, /<textarea[^>]*disabled/);
});

test('backend emotes and request context remain attached to their own messages', () => {
  const html = renderJupWorkspace({ messages: [
    { role: 'JUP', text: 'Negado.', status: 'DENIED_POLICY' },
    { role: 'JUP', text: 'Encaminhado.', status: 'SUPPORT_HANDOFF_PENDING', context: { system: 'CDM', next_step: 'Aguardando aprovação' } },
  ] });
  assert.match(html, /data-state="warning"/);
  assert.match(html, /data-state="escalation"/);
  assert.match(html, /Encaminhado\.[^]*?request-context[^]*?Aguardando aprovação[^]*?<\/article>/);
});

test('composer renders a draft as escaped text without starting a pending message', () => {
  const html = renderJupWorkspace({ draft: 'Preciso de acesso <CDM>' });
  assert.match(html, /<textarea[^>]*>Preciso de acesso &lt;CDM&gt;<\/textarea>/);
  assert.doesNotMatch(html, /conversation-message--thinking/);
});

test('CDM link needs the exact tutorial identity and backend URL; arbitrary URLs stay text', () => {
  const text = '1. Acesse https://cdm.juparana.com.br/.\n2. Não abra https://arbitrary.invalid/.';
  const good = renderApprovedKnowledgeBody({ text, procedureUrl: 'https://cdm.juparana.com.br/', knowledgeId: 'KB-SYN-FAQ-CDM-REQUEST-001' });
  assert.match(good, /href="https:\/\/cdm.juparana.com.br\/"/);
  assert.doesNotMatch(good, /href="https:\/\/arbitrary/);
  for (const options of [{ procedureUrl: 'https://arbitrary.invalid/' }, { procedureUrl: 'https://cdm.juparana.com.br/', knowledgeId: 'OTHER' }]) {
    assert.doesNotMatch(renderApprovedKnowledgeBody({ text, ...options }), /<a /);
  }
});
