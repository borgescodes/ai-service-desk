import test from 'node:test';
import assert from 'node:assert/strict';
import * as solutions from '../src/solutions.mjs';
import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';
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

test('solution groups use h3 under the guidance h2', () => {
  const html = solutions.renderSolutionsHome({ groups: [{ key: 'acessos-rotinas', label: 'Acessos e rotinas', items: [] }] });
  assert.match(html, /<div class="results-heading">[^]*?<h2>Orientações para sua rotina<\/h2>/);
  assert.match(html, /<section class="solution-group"><h3>Acessos e rotinas<\/h3>/);
  assert.doesNotMatch(html, /<section class="solution-group"><h2>/);
});

test('desktop showcase uses premium visual hierarchy with icon-led topics', () => {
  const html = solutions.renderSolutionsHome({
    groups: [{ key: 'acessos-rotinas', label: 'Acessos e rotinas', items: [{ knowledge_id: 'KB-ACCESS', title: 'Solicitar acesso', category: 'Acessos e rotinas' }] }],
  });
  assert.match(html, /class="help-kicker"/);
  assert.match(html, /class="faq-topic-grid"/);
  const topicCards = html.match(/class="faq-topic-card/g) ?? [];
  assert.equal(topicCards.length, 4);
  for (const icon of ['access', 'errors', 'apps', 'network']) assert.match(html, new RegExp(`data-topic-icon="${icon}"`));
  assert.match(html, /class="jup-spotlight"/);
  assert.match(html, /class="field-lines"/);
});

test('desktop article detail has reading surface metadata rail and resolution panel', () => {
  const html = solutions.renderSolutionDetail({
    knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001', title: 'Como solicitar acesso ao CDM', category: 'Acessos e rotinas', category_key: 'acessos-rotinas', system: 'CDM',
    answer: 'Para solicitar seu acesso ao CDM:\n\n1. Acesse https://cdm.juparana.com.br/.\n2. Clique em Solicitar Acesso.', procedure_url: 'https://cdm.juparana.com.br/',
    provenance: { source: 'SYNTHETIC_DEMO', status: 'APPROVED', version: 1 },
  });
  assert.match(html, /class="solution-detail-layout"/);
  assert.match(html, /class="solution-article-card"/);
  assert.match(html, /class="solution-detail-aside"/);
  assert.match(html, /class="solution-meta-card"/);
  assert.match(html, /Conteúdo aprovado/);
  assert.match(html, /CDM/);
  assert.match(html, /class="solution-outcome-card"/);
});

test('Jup desktop workspace has product frame status and elevated composer', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'USER', text: 'Preciso de acesso ao CDM' }, { role: 'JUP', text: 'Posso ajudar com isso.' }] });
  assert.match(html, /class="jup-workspace-frame"/);
  assert.match(html, /class="conversation-status"/);
  assert.match(html, /class="conversation-stage"/);
  assert.match(html, /class="composer-leading-icon"/);
  assert.match(html, /class="composer-hint"/);
});

test('public header has a visual brand symbol without changing navigation authority', () => {
  const html = renderAppHeader({ activeRoute: 'solutions' });
  assert.match(html, /class="brand-symbol"/);
  assert.match(html, /class="brand-wordmark"/);
  assert.match(html, /<svg[^>]*aria-hidden="true"/);
  assert.match(html, /href="\/" data-route="solutions"/);
  assert.match(html, /href="\/jup" data-route="jup"/);
});
