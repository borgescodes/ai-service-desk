import test from 'node:test';
import assert from 'node:assert/strict';
import {
  escapeHtml,
  renderConfidence,
  renderEmptyState,
  renderErrorState,
  renderPrimaryNavigation,
  renderStatus,
  renderUnauthorizedState,
} from '../src/render.mjs';

test('escapeHtml neutralizes active markup and quotes', () => {
  assert.equal(
    escapeHtml('<script>alert("x")</script>&\''),
    '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;&#39;'
  );
});

test('HIGH confidence uses confidence semantics instead of approval or success semantics', () => {
  const html = renderConfidence({ level: 'HIGH', label: 'Alta', percent: 92, tone: 'confidence' });
  assert.match(html, /Confiança/);
  assert.match(html, /92%/);
  assert.doesNotMatch(html, /success|aprovad/i);
});

test('status carries text and icon, never color alone', () => {
  const html = renderStatus({ state: 'COMPLETED', state_label: 'Concluída' });
  assert.match(html, /Concluída/);
  assert.match(html, /aria-hidden="true"/);
});

test('error state gives a recovery action', () => {
  const html = renderErrorState('Não foi possível carregar.');
  assert.match(html, /Tentar novamente/);
});

test('unauthorized state is explicit and points to identity recovery', () => {
  const html = renderUnauthorizedState('Esta identidade não tem acesso a esta operação.');
  assert.match(html, /Perfil sem acesso/);
  assert.match(html, /Soluções/);
  assert.doesNotMatch(html, /Tentar novamente/);
});

test('empty state explains the next useful action', () => {
  const html = renderEmptyState('Nenhuma solicitação', 'Converse com o Jup para começar.');
  assert.match(html, /Nenhuma solicitação/);
  assert.match(html, /Converse com o Jup/);
});

test('operation navigation depends only on server can_operate capability', () => {
  const requester = renderPrimaryNavigation('jup', { can_operate: false });
  const operator = renderPrimaryNavigation('jup', { can_operate: true });
  assert.doesNotMatch(requester, />Operação</);
  assert.match(operator, />Operação</);
});

import {
  renderAppHeader,
  renderJupWorkspace,
  renderOperationDetail,
  renderPreventionList,
  renderRequestList,
} from '../src/components.mjs';

test('header shows public navigation and the bounded demo identity tool', () => {
  const requester = { identity_id: 'pedro-miranda', name: 'Pedro Miranda', email: 'pedro.miranda@juparana.com.br', job_title: 'Analista', area: 'Revenda - Matriz', role: 'REQUESTER', can_operate: false };
  const html = renderAppHeader({
    activeRoute: 'jup',
    identity: requester,
    identities: [requester],
  });
  assert.match(html, /Jup Resolve/);
  assert.match(html, /Falar com o Jup/);
  assert.doesNotMatch(html, /<select/);
  assert.match(html, /id="demo-identity-form"/);
  assert.match(html, /data-email-preview/);
  assert.doesNotMatch(html, /username|capabilit/i);
});

test('Jup workspace renders conversation and compact backend state', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [
      { role: 'USER', text: 'Preciso de acesso ao CDM.' },
      { role: 'JUP', text: 'Criei a solicitação REQ-000001.' },
    ],
    understood: {
      system: 'CDM',
      request: 'Acesso de solicitante',
      purpose: 'Solicitar materiais',
      confidence: { level: 'HIGH', label: 'Alta', percent: 92, tone: 'confidence' },
      policy: 'Requer aprovação',
      next_step: 'Aguardar aprovação técnica',
    },
  });
  assert.doesNotMatch(html, /O que entendi|Confiança|Policy/);
  assert.match(html, /CDM/);
  assert.match(html, /Aguardar aprovação técnica/);
  assert.doesNotMatch(html, /KPI|dashboard/i);
});

test('request list renders only server timeline events and explicit status', () => {
  const html = renderRequestList([
    {
      request_id: 'REQ-000001',
      system: 'CDM',
      purpose: 'Solicitar materiais',
      state: 'COMPLETED',
      state_label: 'Concluída',
      timeline: [
        { event_type: 'REQUEST_CREATED', label: 'Solicitação criada' },
        { event_type: 'EXECUTION_COMPLETED', label: 'Execução concluída' },
      ],
    },
  ]);
  assert.match(html, /REQ-000001/);
  assert.match(html, /Solicitação criada/);
  assert.match(html, /Execução concluída/);
  assert.doesNotMatch(html, /Aprovação necessária.*Aprovada.*Em execução/s);
});

test('operation detail exposes server evidence and action state without deciding it', () => {
  const html = renderOperationDetail(
    {
      request_id: 'REQ-000001',
      version: 2,
      state: 'PENDING_APPROVAL',
      state_label: 'Aguardando aprovação',
      requester: { name: 'Pedro Miranda', area: 'Revenda - Matriz' },
      system: 'CDM',
      purpose: 'Solicitar materiais',
      confidence: { level: 'HIGH', label: 'Alta', percent: 92, tone: 'confidence' },
      policy: { decision: 'REQUIRE_APPROVAL', reason: 'Aprovação humana necessária.' },
      routing: { technician_name: 'Técnico CDM' },
      timeline: [],
    },
    { pendingAction: null },
  );
  assert.match(html, /Aprovar solicitação/);
  assert.match(html, /Rejeitar/);
  assert.match(html, /Técnico CDM/);
  assert.match(html, /Aprovação humana necessária/);
});

test('prevention list is an operational editorial list, not a KPI wall', () => {
  const html = renderPreventionList([
    {
      opportunity_id: 'OPP-123',
      category: 'PREVENTION_CANDIDATE',
      category_label: 'Candidato à prevenção',
      occurrence_count: 4,
      system: 'OFFICE 365',
      intent: 'PROBLEMA_ACESSO',
      explanation: '4 ocorrências recorrentes foram identificadas pelo engine F11.',
    },
  ]);
  assert.match(html, /Candidato à prevenção/);
  assert.match(html, /4 ocorrências/);
  assert.match(html, /OFFICE 365/);
  assert.doesNotMatch(html, /KPI|taxa|percentual/i);
});
