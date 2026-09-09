import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveRoute } from '../src/router.mjs';

for (const [path, expected] of [
  ['/', 'jup'],
  ['/jup', 'jup'],
  ['/requests', 'requests'],
  ['/operations', 'approvals'],
  ['/operations/prevention', 'prevention'],
  ['/unknown', 'jup'],
]) {
  test(`${path} resolves to ${expected}`, () => assert.equal(resolveRoute(path), expected));
}
