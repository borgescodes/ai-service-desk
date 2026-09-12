import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');

test('public identity is route controlled instead of a visible persisted selector', () => {
  assert.doesNotMatch(appSource, /jup-demo-identity/);
  assert.doesNotMatch(appSource, /#demo-identity/);
});
