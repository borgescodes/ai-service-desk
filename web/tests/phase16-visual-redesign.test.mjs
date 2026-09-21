import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  renderAppHeader,
  renderHandoffWorkspace,
  renderJupWorkspace,
} from '../src/components.mjs';
import { navIcon } from '../src/icons.mjs';
import { resolveRoute } from '../src/router.mjs';
import { corporateEmailFromName, personaPath } from '../src/state.mjs';
import { renderTrackingQueue, sortNewestFirst } from '../src/tracking.mjs';

const identities = [
  { identity_id: 'pedro-miranda', name: 'Requester', role: 'REQUESTER', area: 'Revenda' },
  { identity_id: 'tecnico-cdm', name: 'Técnico CDM', role: 'TECHNICIAN', area: 'TI' },
  { identity_id: 'tecnico-m365', name: 'Técnico Microsoft 365', role: 'TECHNICIAN', area: 'TI' },
  { identity_id: 'tecnico-geral', name: 'Técnico Geral', role: 'TECHNICIAN', area: 'TI' },
];

test('corporate email derives first and last normalized name segments', () => {
  assert.equal(corporateEmailFromName('  Fúlano   de Tal  '), 'fulano.tal@juparana.com.br');
  assert.equal(corporateEmailFromName('João'), 'joao@juparana.com.br');
  assert.equal(corporateEmailFromName('Ana-Maria D’Ávila'), 'anamaria.davila@juparana.com.br');
  assert.equal(corporateEmailFromName(' ... '), 'usuario@juparana.com.br');
});

test('user switcher exposes General technician and concise new-user form', () => {
  const html = renderAppHeader({ activeRoute: 'jup', identities, identity: identities[0] });
  assert.match(html, /Técnico Geral/);
  assert.match(html, />Novo usuário</);
  assert.match(html, /data-email-preview/);
  assert.match(html, /readonly/);
  assert.doesNotMatch(html, /Configurar usuário da demo|identidade sintética|nesta demonstração/i);
});

test('General technician has a dedicated authorized handoff route', () => {
  assert.equal(personaPath(identities[3]), '/demo/operacao/general');
  assert.equal(resolveRoute('/demo/operacao/general'), 'handoffs');
});

test('tracking queue sorts newest presentation timestamp first without mutating input', () => {
  const items = [
    { request_id: 'OLD', created_at: '2026-09-20T10:00:00Z', timeline: [] },
    { request_id: 'TIMELINE', created_at: '2026-09-20T08:00:00Z', timeline: [{ occurred_at: '2026-09-21T11:00:00Z' }] },
    { request_id: 'UPDATED', updated_at: '2026-09-21T12:00:00Z', timeline: [] },
  ];
  assert.deepEqual(sortNewestFirst(items).map(item => item.request_id), ['UPDATED', 'TIMELINE', 'OLD']);
  assert.deepEqual(items.map(item => item.request_id), ['OLD', 'TIMELINE', 'UPDATED']);
  assert.ok(renderTrackingQueue(items, 'UPDATED', true).indexOf('UPDATED') < renderTrackingQueue(items, 'UPDATED', true).indexOf('OLD'));
});

test('chat is conversation-first with honest timer and progressive approved source card', () => {
  const html = renderJupWorkspace({
    loading: true,
    messages: [{
      role: 'JUP',
      text: 'Consulte esta orientação.',
      article: {
        knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001',
        title: 'Como solicitar acesso ao CDM',
        provenance: { status: 'APPROVED' },
      },
    }],
  });
  assert.match(html, /data-thinking-seconds="0"/);
  assert.match(html, /Pensando · <span[^>]*>0<\/span>s/);
  assert.match(html, /class="message-source-card"/);
  assert.match(html, /Central de Suporte/);
  assert.match(html, /Abrir artigo/);
  assert.doesNotMatch(html, /chat-support-rail|data-reveal-response/);
});

test('handoff inbox separates queue, human context, conversation and technical metadata', () => {
  const html = renderHandoffWorkspace([{
    handoff_id: 'H-2',
    system: 'TI geral',
    created_at: '2026-09-21T12:00:00Z',
    requester: { name: 'Ana', area: 'Financeiro' },
    technician: { name: 'Técnico Geral' },
    technical_summary: 'Sistema/contexto: TI geral\nSintoma/pedido informado: Meu computador não liga.\nMotivos: IDENTITY_CONFIRMED',
    capability: 'GENERAL_IT_SUPPORT',
    source_conversation: [{ role: 'USER', text: 'Meu computador não liga.' }],
  }]);
  assert.match(html, /handoff-queue/);
  assert.match(html, /Contexto do solicitante/);
  assert.match(html, /Conversa/);
  assert.match(html, /Detalhes técnicos/);
  assert.match(html, /GENERAL_IT_SUPPORT/);
  assert.ok(html.indexOf('IDENTITY_CONFIRMED') > html.indexOf('<details class="technical-disclosure"'));
  assert.ok(html.indexOf('Meu computador não liga.') < html.indexOf('<details class="technical-disclosure"'));
});

test('icons use the locally hosted Boxicons filled family', () => {
  assert.match(navIcon('search'), /class="bx bxs-search/);
  assert.doesNotMatch(navIcon('search'), /<svg|data-lucide/);
});

test('motion loads local GSAP modules instead of relying on UMD globals or a CDN', () => {
  const appSource = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');
  const buildSource = readFileSync(new URL('../scripts/build.mjs', import.meta.url), 'utf8');
  const html = readFileSync(new URL('../src/index.html', import.meta.url), 'utf8');
  assert.match(appSource, /import\('\/vendor\/gsap\/index\.js'\)/);
  assert.match(appSource, /import\('\/vendor\/gsap\/Flip\.js'\)/);
  assert.match(buildSource, /gsap\/utils\/matrix\.js/);
  assert.doesNotMatch(html, /gsap\.min\.js|Flip\.min\.js|https?:\/\//);
});
