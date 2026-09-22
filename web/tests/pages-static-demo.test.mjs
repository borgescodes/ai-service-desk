import test from 'node:test';
import assert from 'node:assert/strict';

import {
  appBasePath,
  resolveRoute,
  routePath,
  stripBasePath,
  withBasePath,
} from '../src/router.mjs';
import { isStaticDemo, staticApiRequest } from '../src/static_demo.mjs';

const pagesLocation = new URL('https://borgescodes.github.io/ai-service-desk/jup');

test('Pages base path is removed for routing and restored for links', () => {
  const originalWindow = globalThis.window;
  globalThis.window = { location: pagesLocation };
  try {
    assert.equal(appBasePath(pagesLocation), '/ai-service-desk');
    assert.equal(stripBasePath('/ai-service-desk/jup', pagesLocation), '/jup');
    assert.equal(resolveRoute('/ai-service-desk/jup'), 'jup');
    assert.equal(withBasePath('/requests', pagesLocation), '/ai-service-desk/requests');
    assert.equal(
      routePath('solution', { knowledgeId: 'KB A/B' }),
      '/ai-service-desk/solucoes/KB%20A%2FB',
    );
  } finally {
    globalThis.window = originalWindow;
  }
});

test('static demo activates only on Pages or explicit local opt-in', () => {
  assert.equal(isStaticDemo(pagesLocation), true);
  assert.equal(isStaticDemo(new URL('http://127.0.0.1:8080/?static-demo=1')), true);
  assert.equal(isStaticDemo(new URL('http://127.0.0.1:8000/')), false);
});

test('static demo exposes FAQ without backend transport', async () => {
  const home = await staticApiRequest('/api/faq');
  assert.ok(home.groups.length >= 4);

  const detail = await staticApiRequest('/api/faq/KB-SYN-M365-PASSWORD-001');
  assert.equal(detail.knowledge_id, 'KB-SYN-M365-PASSWORD-001');
  assert.match(detail.answer, /Microsoft 365/);
});

test('static demo supports requester to approval to completion', async () => {
  const created = await staticApiRequest('/api/jup/messages', {
    method: 'POST',
    identityId: 'pedro-miranda',
    body: { message: 'Preciso de acesso ao CDM para solicitar materiais para uma revenda.' },
  });
  assert.equal(created.status, 'PENDING_APPROVAL');

  const queue = await staticApiRequest('/api/operations/approvals', {
    identityId: 'tecnico-cdm',
  });
  const pending = queue.find(item => item.request_id === created.request_id);
  assert.ok(pending);

  const completed = await staticApiRequest(
    `/api/requests/${created.request_id}/approve`,
    {
      method: 'POST',
      identityId: 'tecnico-cdm',
      body: { expected_version: pending.version },
    },
  );
  assert.equal(completed.state, 'COMPLETED');

  const requesterItems = await staticApiRequest('/api/requests', {
    identityId: 'pedro-miranda',
  });
  assert.equal(
    requesterItems.find(item => item.request_id === created.request_id)?.state,
    'COMPLETED',
  );
});
