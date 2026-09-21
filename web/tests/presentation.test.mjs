import test from 'node:test';
import assert from 'node:assert/strict';
import { pageScrollTarget, createWelcomeEntry, captureJupFlip, presentChat } from '../src/presentation.mjs';
import { renderJupWorkspace } from '../src/components.mjs';

test('reduced motion keeps the complete response visible without scheduling animation', () => {
  const root = { querySelectorAll: () => [{ textContent: 'Resposta completa' }] };
  assert.doesNotThrow(() => presentChat(root, { reducedMotion: true }));
  assert.equal(root.querySelectorAll()[0].textContent, 'Resposta completa');
});
test('Flip capture is skipped for reduced motion', () => {
  const root = { querySelector: () => ({}) };
  assert.equal(captureJupFlip(root, true), null);
});
test('page scroll only moves for a partially hidden opening category', () => {
  assert.equal(pageScrollTarget({ top: 100, bottom: 400 }, 900, 0), null);
  assert.equal(pageScrollTarget({ top: 700, bottom: 1200 }, 900, 100), 684);
});
test('new messages use a block-level entrance marker without simulated typing', () => {
  const messages = [{ role: 'JUP', text: 'Antiga' }, { role: 'USER', text: 'Oi' }, { role: 'JUP', text: 'Nova' }];
  assert.equal((renderJupWorkspace({ messages, animateFrom: 2 }).match(/is-new/g) || []).length, 1);
  assert.doesNotMatch(renderJupWorkspace({ messages }), /data-reveal-response/);
});

test('empty chat navigation and new conversation share the same welcome entry', () => {
  const entry = createWelcomeEntry();
  assert.equal(entry.update(false), false); // Solutions.
  assert.equal(entry.update(true), true); // Enter empty Jup.
  assert.equal(entry.update(true), false); // Ordinary rerender.
  entry.update(false); // Leave for Solutions.
  assert.equal(entry.update(true), true); // Reenter empty Jup.
  entry.reset(); // Successful New conversation.
  assert.equal(entry.update(true), true);
});

test('active conversation and navigation never request a welcome animation', () => {
  const entry = createWelcomeEntry();
  entry.update(true);
  for (const visible of [false, false, false]) assert.equal(entry.update(visible), false);
});
