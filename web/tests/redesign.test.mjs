import test from 'node:test';
import assert from 'node:assert/strict';
import * as session from '../src/state.mjs';
import * as components from '../src/components.mjs';
const { renderAppHeader, renderJupWorkspace } = components;
import { renderSolutionsHome, renderSolutionsResults } from '../src/solutions.mjs';

test('new chat clears conversation and draft while keeping identity and request data', () => {
  assert.equal(typeof session.resetConversation, 'function');
  const previous = { identityId: 'pedro-miranda', messages: ['old'], composerDraft: 'old',
    pendingAction: null, understood: {}, messageError: 'error', faqContext: {}, routeData: { items: ['request'] } };
  const next = session.resetConversation(previous);
  assert.equal(next.identityId, previous.identityId);
  assert.equal(next.routeData, previous.routeData);
  assert.deepEqual(next.messages, []);
  assert.equal(next.composerDraft, '');
  assert.equal(next.messageError, null);
  assert.equal(next.understood, null);
  assert.equal(next.faqContext, null);
});

test('persona destinations use only supported identities returned by the provider', () => {
  assert.equal(typeof session.personaPath, 'function');
  assert.equal(session.personaPath({ identity_id: 'pedro-miranda' }), '/jup');
  assert.equal(session.personaPath({ identity_id: 'tecnico-cdm' }), '/demo/operacao/cdm');
  assert.equal(session.personaPath({ identity_id: 'tecnico-m365' }), '/demo/operacao/m365');
  assert.equal(session.personaPath({ identity_id: 'demo-requester-1', role: 'REQUESTER' }), '/jup');
  assert.equal(session.personaPath({ identity_id: 'unknown' }), null);
});

test('header exposes backend persona choices and a real new-chat control', () => {
  const identities = [{ identity_id: 'pedro-miranda', name: 'Pedro Miranda', email: 'pedro@juparana.com.br', job_title: 'Analista', area: 'Revenda', role: 'REQUESTER' }, { identity_id: 'tecnico-cdm', name: 'Técnico CDM', role: 'TECHNICIAN' }];
  const html = renderAppHeader({ activeRoute: 'jup', identities, identity: identities[0] });
  assert.match(html, /Pedro Miranda/);
  assert.match(html, /data-persona="tecnico-cdm"/);
  assert.match(html, /data-action="new-chat"/);
  assert.match(html, /Acompanhar chamado/);
  assert.match(html, /id="demo-identity-form"/);
  assert.match(html, /Configurar usuário da demo/);
  assert.match(html, /pattern="\[\^@\]\+@juparana\[\.\]com\[\.\]br"/);
  assert.match(html, /name="job_title"/);
  assert.match(html, /name="area"[^>]*type="text"/);
});

test('central presents only the available CDM tutorial, including search results', () => {
  const items = [{ knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001', title: 'Como solicitar acesso ao CDM' },
    { knowledge_id: 'OTHER', title: 'Outro conteúdo' }];
  const html = renderSolutionsHome({ groups: [{ label: 'Acessos', items }] });
  assert.match(html.replace(/<[^>]+>/g, ''), /Central de Suporte/);
  assert.match(html, /Como solicitar acesso ao CDM/);
  assert.doesNotMatch(html, /Outro conteúdo|0 orientações|Conteúdo revisado para demonstração/);
  const results = renderSolutionsResults({ searchQuery: 'outro', searchResults: [items[1]] });
  assert.match(results, /Nenhuma solução encontrada/);
});

test('messages show presentation time and honest processing status', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'USER', text: 'Oi', sentAt: '2026-09-14T13:42:00Z' }], loading: true });
  assert.match(html, /<time datetime="2026-09-14T13:42:00Z"/);
  assert.match(html, /Pensando/);
  assert.match(html, /Buscando contexto/);
  assert.doesNotMatch(html, /Verificando política|Conferindo responsável/);
});

test('technician can inspect actual handoff summary without approval actions', () => {
  assert.equal(typeof components.renderHandoffs, 'function');
  const html = components.renderHandoffs([{ handoff_id: 'H-1', system: 'MICROSOFT_365',
    technician: { name: 'Técnico Microsoft 365' }, requester: { name: 'Pedro Miranda', area: 'Revenda' },
    technical_summary: 'Procedimento não resolveu o acesso.', capability: 'MICROSOFT_365_SUPPORT_REQUEST',
    source_conversation: [{ role: 'USER', text: 'Não resolveu.' }] }]);
  assert.match(html, /Técnico Microsoft 365/);
  assert.match(html, /Procedimento não resolveu o acesso/);
  assert.match(html, /Não resolveu/);
  assert.doesNotMatch(html, /data-action="approve"/);
});

test('central search has a submit action for keyboard and pointer use', () => {
  const html = renderSolutionsHome();
  assert.match(html, /<form[^>]*id="faq-search-form"/);
  assert.match(html, /<button[^>]*type="submit"[^>]*>Buscar/);
});
