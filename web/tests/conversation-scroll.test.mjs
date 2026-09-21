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

test('progressive delivery follows growth until the reader manually scrolls upward', async () => {
  const { createProgressiveScrollFollower } = await import('../src/conversation.mjs');
  assert.equal(typeof createProgressiveScrollFollower, 'function');
  const events = {};
  const thread = {
    scrollTop: 600,
    scrollHeight: 1000,
    clientHeight: 400,
    addEventListener(name, fn) { events[name] = fn; },
    removeEventListener() {},
  };
  const follower = createProgressiveScrollFollower(thread, true);

  thread.scrollHeight = 1120;
  follower.update();
  assert.equal(thread.scrollTop, 1120);

  thread.scrollTop = 520;
  events.scroll();
  thread.scrollHeight = 1280;
  follower.update();
  assert.equal(thread.scrollTop, 520);

  thread.scrollTop = 880;
  events.scroll();
  thread.scrollHeight = 1360;
  follower.update();
  assert.equal(thread.scrollTop, 1360);
  follower.stop();
});

test('upward wheel intent interrupts progressive following before the next animation frame', async () => {
  const { createProgressiveScrollFollower } = await import('../src/conversation.mjs');
  const events = {};
  const thread = {
    scrollTop: 600,
    scrollHeight: 1000,
    clientHeight: 400,
    addEventListener(name, fn) { events[name] = fn; },
    removeEventListener() {},
  };
  const follower = createProgressiveScrollFollower(thread, true);
  events.wheel({ deltaY: -12 });
  thread.scrollHeight = 1200;
  follower.update();
  assert.equal(thread.scrollTop, 600);
});
