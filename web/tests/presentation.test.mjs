import test from 'node:test';
import assert from 'node:assert/strict';
import { revealTextNodes, pageScrollTarget, createWelcomeEntry } from '../src/presentation.mjs';
import { renderJupWorkspace } from '../src/components.mjs';

test('progressive text preserves exact content, whitespace and node identity', () => {
  const nodes = [{ data: 'Posso ajudar você. ' }, { data: '1. Acesse o CDM\n' }];
  const original = nodes.map(node => node.data);
  const tasks = [];
  const finish = revealTextNodes(nodes, { schedule: fn => { tasks.push(fn); return tasks.length; }, cancel: () => {} });
  assert.deepEqual(nodes.map(node => node.data), ['', '']);
  tasks.shift()();
  assert.equal(nodes[0].data, 'Posso ');
  assert.equal(nodes[1].data, '');
  finish();
  assert.deepEqual(nodes.map(node => node.data), original);
  tasks.shift()?.();
  assert.deepEqual(nodes.map(node => node.data), original);
});
test('tagline uses characters and reduced motion shows all text immediately', () => {
  const nodes = [{ data: 'Olá Jup' }], tasks = [];
  revealTextNodes(nodes, { characters: true, schedule: fn => tasks.push(fn), cancel: () => {} });
  tasks.shift()(); assert.equal(nodes[0].data, 'O');
  const instant = [{ data: 'Completo' }];
  revealTextNodes(instant, { reducedMotion: true, schedule: () => assert.fail('No animation') });
  assert.equal(instant[0].data, 'Completo');
});
test('page scroll only moves for a partially hidden opening category', () => {
  assert.equal(pageScrollTarget({ top: 100, bottom: 400 }, 900, 0), null);
  assert.equal(pageScrollTarget({ top: 700, bottom: 1200 }, 900, 100), 684);
});
test('only new successful assistant messages receive the reveal marker', () => {
  const messages = [{ role: 'JUP', text: 'Antiga' }, { role: 'USER', text: 'Oi' }, { role: 'JUP', text: 'Nova' }];
  assert.equal((renderJupWorkspace({ messages, animateFrom: 2 }).match(/data-reveal-response/g) || []).length, 1);
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
