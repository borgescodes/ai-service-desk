import test from 'node:test';
import assert from 'node:assert/strict';
import { createInitialState, selectIdentity } from '../src/state.mjs';

test('selected identity is explicit state and switching clears transient errors', () => {
  const initial = createInitialState();
  assert.equal(initial.identityId, null);
  const withError = { ...initial, transientError: 'falha', routeData: { stale: true } };
  const next = selectIdentity(withError, 'pedro-miranda');
  assert.equal(next.identityId, 'pedro-miranda');
  assert.equal(next.transientError, null);
  assert.deepEqual(next.routeData, {});
});

test('client state exports no domain decision functions', async () => {
  const stateModule = await import('../src/state.mjs');
  for (const forbidden of ['evaluatePolicy', 'routeRequest', 'approveRequest', 'executeRequest']) {
    assert.equal(forbidden in stateModule, false);
  }
});
