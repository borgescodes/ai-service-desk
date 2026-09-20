import assert from 'node:assert/strict';
import test from 'node:test';

import { renderTrackingDetail } from '../src/tracking.mjs';

function pendingRequest() {
  return {
    request_id: 'REQ-000001',
    version: 1,
    state: 'PENDING_APPROVAL',
    state_label: 'Aguardando aprovação',
    requester: {
      name: 'Fulano de Tal',
      username: 'fulano.tal',
      email: 'fulano.tal@juparana.com.br',
      area: 'Revenda - Matriz',
      identity_source: 'BACKEND_SESSION_PROVIDER',
    },
    system: 'CDM',
    intent: 'PROBLEMA_ACESSO',
    requested_role: 'SOLICITANTE',
    purpose: 'Preciso de acesso ao CDM para solicitar materiais para revenda',
    confidence: {
      level: 'HIGH',
      label: 'Alta',
      percent: null,
      explanations: [
        { code: 'AREA_MATCH_REVENDA', kind: 'positive', text: 'Área de atuação compatível com Revenda.' },
        { code: 'PURPOSE_MATCH_MATERIAL_REQUEST', kind: 'positive', text: 'Finalidade de solicitação de materiais confirmada.' },
      ],
    },
    policy: {
      decision: 'REQUIRE_APPROVAL',
      requires_approval: true,
      reason: 'Acesso de solicitante ao CDM exige aprovação humana antes da execução.',
      reason_code: 'CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL',
    },
    routing: { technician_name: 'Técnico CDM', capability: 'CDM_ACCESS_REQUEST' },
    timeline: [],
    created_at: '2026-09-14T12:00:00-03:00',
  };
}

test('technician detail explains trusted requester, request, confidence and backend decision', () => {
  const html = renderTrackingDetail(pendingRequest(), { operational: true });

  assert.match(html, /Fulano de Tal/);
  assert.match(html, /fulano\.tal@juparana\.com\.br/);
  assert.match(html, /Revenda - Matriz/);
  assert.match(html, /Perfil solicitado/);
  assert.match(html, /Solicitante/i);
  assert.match(html, /Análise do Jup/);
  assert.match(html, /Por que essa confiança\?/);
  assert.match(html, /Área de atuação compatível com Revenda/);
  assert.match(html, /Finalidade de solicitação de materiais confirmada/);
  assert.match(html, /Decisão do backend/);
  assert.match(html, /Aprovação humana/i);
  assert.doesNotMatch(html, /87%|95%/);
});

test('technician detail presents the demo reading order and progressively discloses internals', () => {
  const html = renderTrackingDetail(pendingRequest(), { operational: true });
  const requester = html.indexOf('aria-label="Solicitante"');
  const request = html.indexOf('aria-label="Solicitação"');
  const summary = html.indexOf('aria-label="Resumo do Jup"');
  const progress = html.indexOf('aria-label="Andamento"');
  const action = html.indexOf('aria-label="Ação esperada"');
  const disclosure = html.indexOf('<details class="technical-disclosure"');
  const analysis = html.indexOf('Análise do Jup');
  const backendDecision = html.indexOf('Decisão do backend');

  assert.ok(requester < request, 'requester should precede the request');
  assert.ok(request < summary, 'the request should precede the Jup summary');
  assert.ok(summary < progress, 'the summary should precede progress');
  assert.ok(progress < action, 'progress should precede the expected action');
  assert.ok(action < disclosure, 'the primary action should precede technical detail');
  assert.ok(disclosure < analysis, 'confidence analysis should be progressively disclosed');
  assert.ok(disclosure < backendDecision, 'backend decision should be progressively disclosed');
});

test('technician sees trusted job title and explicit scope mismatch', () => {
  const item = pendingRequest();
  item.requester.job_title = 'Analista';
  item.business_scope = 'ubs';
  item.scope_mismatch = true;
  item.scope_confirmed = true;
  const html = renderTrackingDetail(item, { operational: true });
  assert.match(html, /Analista/);
  assert.match(html, /Escopo CDM/);
  assert.match(html, /ubs/i);
  assert.match(html, /Divergência/);
  assert.match(html, /Confirmada pelo solicitante/);
});
