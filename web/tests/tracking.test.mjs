import test from 'node:test';
import assert from 'node:assert/strict';
import { renderAppHeader, renderRequestList, renderOperationDetail, renderApprovalQueue } from '../src/components.mjs';
import * as presentation from '../src/render.mjs';
import { resolveRoute } from '../src/router.mjs';

const item = { request_id: 'REQ-1', system: 'CDM', purpose: 'Acesso para solicitar materiais', state: 'COMPLETED', requester: { name: 'Pedro', area: 'Revenda' }, routing: { technician_name: 'Técnico CDM', capability: '<script>routing</script>' }, policy: { decision: 'REQUIRE_APPROVAL' }, timeline: [{ label: 'Solicitação criada', occurred_at: '2026-09-14T04:02:38.037069+00:00' }] };

test('operational demo navigation has one destination and no prevention shortcut', () => {
  const html = renderAppHeader({ activeRoute: 'approvals', operational: true });
  assert.doesNotMatch(html, /Prevenção|prevention/);
  assert.equal((html.match(/Solicitações recebidas/g) || []).length, 1);
  assert.equal(resolveRoute('/demo/operacao/prevention'), 'prevention');
});
test('timestamps use explicit Sao Paulo timezone with stable Portuguese formatting', () => {
  assert.equal(presentation.formatTimestamp(item.timeline[0].occurred_at), '14 set · 01:02');
  assert.equal(presentation.formatTimestamp('invalid'), 'Data indisponível');
});
test('request tracking preserves a selectable list and one summary in the detail', () => {
  const html = renderRequestList([item]);
  assert.match(html, /data-request-select="REQ-1"/);
  assert.match(html, /Resumo/);
  assert.match(html, /Responsável/);
  assert.match(html, /14 set · 01:02/);
  assert.doesNotMatch(html.replace(/<[^>]*>/g, ''), /2026-09-14T/);
});
test('empty requester state has a chat CTA', () => {
  assert.match(renderRequestList([]), /href="\/jup"/);
});
test('completed operational detail hides actions and keeps escaped metadata in disclosure', () => {
  const html = renderOperationDetail(item);
  assert.doesNotMatch(html, /data-action="approve"|data-action="reject"|<script>/);
  assert.match(html, /<details class="technical-disclosure">/);
  assert.match(html, /&lt;script&gt;routing/);
  assert.equal((html.match(/Acesso para solicitar materiais/g) || []).length, 1);
});
test('pending actions depend on backend state and busy UI prevents duplicate actions', () => {
  assert.match(renderOperationDetail({ ...item, state: 'PENDING_APPROVAL' }), /data-action="approve"/);
  assert.match(renderOperationDetail({ ...item, state: 'PENDING_APPROVAL' }, { pendingAction: 'approve' }), /data-action="reject"[^>]*disabled/);
  assert.match(renderApprovalQueue([item], item.request_id), /aria-current="true"/);
});
