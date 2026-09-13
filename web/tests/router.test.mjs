import test from 'node:test';
import assert from 'node:assert/strict';
import { demoIdentityForPath, resolveRoute, routeParams, routePath } from '../src/router.mjs';

for (const [path, expected] of [
  ['/', 'solutions'],
  ['/jup', 'jup'],
  ['/solucoes/KB-SYN-CIGAM-ACCESS-001', 'solution'],
  ['/requests', 'requests'],
  ['/demo/operacao/cdm', 'approvals'],
  ['/demo/operacao/m365', 'approvals'],
  ['/demo/operacao/prevention', 'prevention'],
  ['/operations', 'approvals'],
  ['/operations/prevention', 'prevention'],
  ['/unknown', 'solutions'],
]) {
  test(`${path} resolves to ${expected}`, () => assert.equal(resolveRoute(path), expected));
}

test('solution route extracts a decoded knowledge id', () => {
  assert.deepEqual(routeParams('/solucoes/KB-SYN-CIGAM-ACCESS-001'), {
    knowledgeId: 'KB-SYN-CIGAM-ACCESS-001',
  });
});

test('public and operational paths resolve only fixed demo identities', () => {
  assert.equal(demoIdentityForPath('/'), 'pedro-miranda');
  assert.equal(demoIdentityForPath('/jup'), 'pedro-miranda');
  assert.equal(demoIdentityForPath('/demo/operacao/cdm'), 'tecnico-cdm');
  assert.equal(demoIdentityForPath('/demo/operacao/m365'), 'tecnico-m365');
  assert.equal(demoIdentityForPath('/demo/operacao/prevention'), 'tecnico-geral');
});

test('routePath builds a dedicated solution path', () => {
  assert.equal(
    routePath('solution', { knowledgeId: 'KB A/B' }),
    '/solucoes/KB%20A%2FB',
  );
});
