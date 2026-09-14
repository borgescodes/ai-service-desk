import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as solutions from '../src/solutions.mjs';
import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';
import { renderApprovedKnowledgeBody } from '../src/knowledge_content.mjs';

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
  const html = solutions.renderSolutionsResults({ category: 'acessos-rotinas', searchResults: [{ knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001', title: 'CDM', category: 'Acessos e rotinas' }], groups: [{ label: 'Old', items: [{ title: 'Outlook' }] }] });
  assert.match(html, /CDM/); assert.doesNotMatch(html, /Outlook/);
  const empty = solutions.renderSolutionsResults({ searchQuery: 'zzzz', searchResults: [] });
  assert.match(empty, /Falar com o Jup/); assert.match(empty, /draft=zzzz/);
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

test('Jup desktop workspace has product frame and composer without permanent hero', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'USER', text: 'Preciso de acesso ao CDM' }, { role: 'JUP', text: 'Posso ajudar com isso.' }] });
  assert.match(html, /class="jup-workspace-frame"/);
  assert.doesNotMatch(html, /class="conversation-status"/);
  assert.match(html, /class="conversation-stage"/);
  assert.match(html, /class="composer-leading-icon"/);
  assert.match(html, /class="composer-hint"/);
});

test('one visual foundation is loaded together with the original animated avatar', () => {
  const html = readFileSync(new URL('../src/index.html', import.meta.url), 'utf8');
  assert.match(html, /href="\/tokens.css"/);
  assert.match(html, /href="\/styles.css"/);
  assert.match(html, /href="\/desktop-responsive.css"/);
  assert.match(html, /src="\/ui-polish.mjs"/);
  assert.match(html, /href="\/assets\/jup\/jup-avatar.css"/);
  assert.doesNotMatch(html, /premium.css|showcase-desktop.css/);
});

test('FAQ accordion is exclusive, animated and catalog rows do not expose demo labels', () => {
  const html = solutions.renderSolutionsHome({
    groups: [{ items: [{ knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001' }] }],
    searchQuery: '',
    searchResults: null,
    searching: false,
  });
  assert.match(html, /<details class="faq-category" name="support-faq"/);
  assert.match(html, /class="faq-category-panel"/);
  assert.doesNotMatch(html, /Exemplo visual/);
  assert.match(html, /Como entrar no CDM depois da aprovação[^]*?class="solution-arrow"/);
});

test('Jup contextual sidebar keeps only new conversation and request tracking', () => {
  const html = renderAppHeader({ activeRoute: 'jup', identity: { name: 'Pedro Miranda' } });
  assert.match(html, /Nova conversa/);
  assert.match(html, /Acompanhar chamado/);
  assert.doesNotMatch(html, /Artigos de ajuda/);
});

test('welcome tagline is typewriter-ready and draft content switches the welcome avatar to listening', () => {
  const idle = renderJupWorkspace({ draft: '' });
  const listening = renderJupWorkspace({ draft: 'oi' });
  assert.match(idle, /class="chat-welcome-tagline"/);
  assert.match(idle, /data-listening="false"/);
  assert.match(idle, /chat-welcome[^]*?data-state="idle"/);
  assert.match(listening, /data-listening="true"/);
  assert.match(listening, /chat-welcome[^]*?data-state="listening"/);
});

test('desktop shell prevents FAQ page overflow and gives conversation a branded minimal scrollbar', () => {
  const baseCss = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
  const responsiveCss = readFileSync(new URL('../src/desktop-responsive.css', import.meta.url), 'utf8');
  const css = `${baseCss}\n${responsiveCss}`;
  assert.match(css, /scrollbar-gutter:\s*stable/);
  assert.match(css, /body:has\(\.solutions-home\)[^}]*overflow:\s*hidden/);
  assert.match(css, /\.conversation-thread[^}]*scrollbar-color:/);
  assert.match(css, /\.chat-welcome-tagline/);
});
