import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  renderAppHeader,
  renderJupWorkspace,
  renderRequestList,
} from '../src/components.mjs';
import { navIcon } from '../src/icons.mjs';
import * as presentation from '../src/presentation.mjs';
import { renderConfidence } from '../src/render.mjs';
import { renderTrackingDetail, renderTrackingQueue } from '../src/tracking.mjs';

const request = (id, createdAt) => ({
  request_id: id,
  created_at: createdAt,
  system: 'CDM',
  purpose: 'Preciso de acesso ao CDM',
  state: 'PENDING_APPROVAL',
  state_label: 'Aguardando aprovação',
  requester: { name: 'Fulano de Tal', area: 'Revenda - Matriz' },
  routing: { technician_name: 'Técnico CDM' },
  confidence: { level: 'LOW', label: 'Baixa', explanations: [] },
  policy: { decision: 'REQUIRE_APPROVAL', requires_approval: true },
  timeline: [],
});

test('welcome has two explicit lines and no tagline', () => {
  const html = renderJupWorkspace({ identity: { name: 'Fulano de Tal' } });
  assert.match(html, /welcome-line--greeting[^>]*>Olá, <strong>Fulano!<\/strong>/);
  assert.match(html, /welcome-line--question[^>]*>Como posso ajudar\?/);
  assert.doesNotMatch(html, /Seu assistente virtual|chat-welcome-tagline/);
});

test('composer uses the exact filled Boxicons message circle assets for idle and typing states', () => {
  const idle = renderJupWorkspace({ draft: '' });
  const typing = renderJupWorkspace({ draft: 'Preciso de ajuda' });

  assert.match(navIcon('message-circle-dots'), /data-boxicon="message-circle-dots"/);
  assert.match(navIcon('message-circle-edit'), /data-boxicon="message-circle-edit"/);
  assert.doesNotMatch(`${idle}${typing}`, /message-rounded-(?:dots|edit)/);
  assert.match(idle, /composer-leading-icon[^>]*data-composing="false"[^]*data-boxicon="message-circle-dots"[^]*data-boxicon="message-circle-edit"/);
  assert.match(typing, /composer-leading-icon[^>]*data-composing="true"/);
});

test('persona selector gives each technician a filled user-family icon and semantic color role', () => {
  const identities = [
    { identity_id: 'requester', role: 'REQUESTER', name: 'Fulano' },
    { identity_id: 'tecnico-cdm', role: 'TECHNICIAN', name: 'CDM' },
    { identity_id: 'tecnico-m365', role: 'TECHNICIAN', name: 'Microsoft 365' },
    { identity_id: 'tecnico-geral', role: 'TECHNICIAN', name: 'Geral' },
  ];
  const html = renderAppHeader({ activeRoute: 'jup', identities, identity: identities[0] });

  assert.match(html, /persona-choice-icon persona-choice-icon--requester[^]*?bxs-user/);
  assert.match(html, /persona-choice-icon persona-choice-icon--cdm[^]*?bxs-user-badge/);
  assert.match(html, /persona-choice-icon persona-choice-icon--m365[^]*?bxs-user-detail/);
  assert.match(html, /persona-choice-icon persona-choice-icon--general[^]*?bxs-user-voice/);
});

test('thinking contains no processing context tile', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'USER', text: 'Ajuda' }], loading: true });
  assert.match(html, /Pensando ·/);
  assert.doesNotMatch(html, /processing-context/);
});

test('wordmark remains textual and exposes distinct Jup and Resolve classes', () => {
  const html = renderAppHeader({ activeRoute: 'jup', identity: { name: 'Fulano' } });
  const wordmark = html.match(/<span class="brand-wordmark"[^]*?<\/span><\/span>/)?.[0] || '';
  assert.match(wordmark, /brand-wordmark__jup">Jup/);
  assert.match(wordmark, /brand-wordmark__resolve">Resolve/);
  assert.doesNotMatch(wordmark, /<img|<svg/);
});

test('chat request summary is a compact editorial list, not tracking cards', () => {
  const html = renderJupWorkspace({
    messages: [{ role: 'JUP', text: 'Você tem 1 solicitação para acompanhar.', request_summary: { items: [request('REQ-000001', '2026-09-21T12:00:00Z')] }, requestCta: 'REQUESTS' }],
    animateFrom: 0,
  });
  assert.match(html, /request-summary-row/);
  assert.match(html, /request-summary-action/);
  assert.match(html, /Ver todas as solicitações/);
  assert.doesNotMatch(html, /request-summary-row[^>]*tracking-row|message-request-cta[^>]*button/);
});

test('requester surface uses an editorial list and keeps its heading screen-reader-only', () => {
  const html = renderRequestList([request('REQ-2', '2026-09-21T12:00:00Z'), request('REQ-1', '2026-09-20T12:00:00Z')], 'REQ-2');
  assert.match(html, /<h1 class="sr-only">Minhas solicitações<\/h1>/);
  assert.match(html, /requester-request-list/);
  assert.match(html, /requester-request-detail/);
  assert.doesNotMatch(html, /class="tracking-workspace"/);
});

test('operational queue stays newest-first and uses compact work rows', () => {
  const html = renderTrackingQueue([
    request('REQ-OLD', '2026-09-20T12:00:00Z'),
    request('REQ-NEW', '2026-09-21T12:00:00Z'),
  ], 'REQ-NEW', true);
  assert.ok(html.indexOf('REQ-NEW') < html.indexOf('REQ-OLD'));
  assert.match(html, /queue-row__subject/);
  assert.match(html, /queue-row__meta/);
  assert.doesNotMatch(html, /tracking-system">CDM/);
});

test('confidence label is rendered once with a three-segment meter', () => {
  const html = renderConfidence({ level: 'LOW', label: 'Baixa', percent: 31 });
  assert.equal((html.match(/Baixa/g) || []).length, 1);
  assert.equal((html.match(/confidence-meter__segment/g) || []).length, 3);
  assert.doesNotMatch(html, /Confiança\s+Baixa/);

  const detail = renderTrackingDetail(request('REQ-1', '2026-09-21T12:00:00Z'), { operational: true });
  assert.doesNotMatch(detail, /Confiança[^<]*Confiança/);
  assert.match(detail, />Decisão<\/h3>/);
  assert.doesNotMatch(detail, /Decisão do backend/);
});

test('progressive reveal duration is bounded by response length', () => {
  assert.equal(typeof presentation.responseRevealDuration, 'function');
  assert.ok(presentation.responseRevealDuration(12) >= 700 && presentation.responseRevealDuration(12) <= 1200);
  assert.ok(presentation.responseRevealDuration(70) >= 1200 && presentation.responseRevealDuration(70) <= 2000);
  assert.ok(presentation.responseRevealDuration(600) >= 2200 && presentation.responseRevealDuration(600) <= 3000);
});

test('only a fresh Jup response is marked for progressive presentation', () => {
  const messages = [
    { role: 'JUP', text: 'Histórico' },
    { role: 'USER', text: 'Pergunta' },
    { role: 'JUP', text: 'Resposta nova' },
  ];
  const html = renderJupWorkspace({ messages, animateFrom: 2 });
  assert.equal((html.match(/data-progressive-response/g) || []).length, 1);
  assert.match(html, /response-announcement[^>]*>Resposta nova/);
});

test('reduced motion immediately exposes a fresh response', () => {
  const primary = { removeAttribute(name) { this.removed = name; } };
  const followup = { removeAttribute(name) { this.removed = name; } };
  const announcement = { remove() { this.wasRemoved = true; } };
  const message = {
    querySelector(selector) {
      if (selector === '[data-progressive-response]') return primary;
      if (selector === '.response-announcement') return announcement;
      return null;
    },
    querySelectorAll(selector) { return selector === '[data-response-followup]' ? [followup] : []; },
  };
  const root = {
    querySelectorAll(selector) {
      return selector.includes('conversation-message.is-new') ? [message] : [];
    },
    querySelector() { return null; },
  };
  assert.doesNotThrow(() => presentation.presentChat(root, { reducedMotion: true }));
  assert.equal(primary.removed, 'aria-hidden');
  assert.equal(followup.removed, 'aria-hidden');
  assert.equal(announcement.wasRemoved, true);
});

test('redundant visual page headings are absent from request routes', () => {
  const source = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /pageHeading\('Minhas solicitações'/);
  assert.doesNotMatch(source, /pageHeading\('Solicitações recebidas'/);
});
