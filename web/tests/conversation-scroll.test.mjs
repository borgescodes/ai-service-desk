import test from 'node:test';
import assert from 'node:assert/strict';

test('conversation follows the end only when reader was already near it', async () => {
  const module = await import('../src/conversation.mjs').catch(() => ({}));
  assert.equal(typeof module.captureConversationScroll, 'function');
  assert.deepEqual(module.captureConversationScroll({ scrollTop: 100, scrollHeight: 1000, clientHeight: 400 }), { top: 100, atEnd: false });
  assert.equal(module.captureConversationScroll({ scrollTop: 550, scrollHeight: 1000, clientHeight: 400 }).atEnd, true);
});

test('restoring a reading position exposes bottom action and respects reduced motion', async () => {
  const module = await import('../src/conversation.mjs').catch(() => ({}));
  assert.equal(typeof module.restoreConversationScroll, 'function');
  const events = {}, calls = [];
  const thread = { scrollTop: 0, scrollHeight: 1200, clientHeight: 400, addEventListener(name, fn) { events[name] = fn; }, scrollTo(options) { calls.push(options); } };
  const button = { hidden: true, addEventListener(name, fn) { events['button-' + name] = fn; } };
  module.restoreConversationScroll(thread, button, { top: 100, atEnd: false }, true);
  assert.equal(thread.scrollTop, 100); assert.equal(button.hidden, false);
  events['button-click'](); assert.deepEqual(calls[0], { top: 1200, behavior: 'auto' });
  thread.scrollTop = 800; events.scroll(); assert.equal(button.hidden, true);
  module.restoreConversationScroll(thread, button, { top: 100, atEnd: true }, false);
  assert.equal(thread.scrollTop, 1200);
});
