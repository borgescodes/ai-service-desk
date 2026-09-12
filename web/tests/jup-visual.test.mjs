import test from 'node:test';
import assert from 'node:assert/strict';
import { visualStateFromUi } from '../src/jup_visual.mjs';

test('pending request always renders thinking', () => {
  assert.equal(visualStateFromUi({ pending: true, backendStatus: null, focused: true }), 'thinking');
});

test('backend outcome maps only to presentation states', () => {
  assert.equal(visualStateFromUi({ pending: false, backendStatus: 'SUPPORT_RESOLVED', focused: false }), 'success');
  assert.equal(visualStateFromUi({ pending: false, backendStatus: 'DENIED_POLICY', focused: false }), 'warning');
  assert.equal(visualStateFromUi({ pending: false, backendStatus: 'SUPPORT_HANDOFF_PENDING', focused: false }), 'escalation');
});

test('focused composer uses listening only when no stronger backend state is active', () => {
  assert.equal(visualStateFromUi({ pending: false, backendStatus: null, focused: true }), 'listening');
  assert.equal(visualStateFromUi({ pending: false, backendStatus: null, focused: false }), 'idle');
});
import { renderJupVisual } from '../src/jup_visual.mjs';
import { JUP_ASSETS } from '../src/jup_visual_assets.mjs';

test('six supplied visual assets render locally and warning has no face', () => {
  assert.deepEqual(Object.keys(JUP_ASSETS).sort(), ['escalation', 'idle', 'listening', 'success', 'thinking', 'warning']);
  assert.ok(Object.isFrozen(JUP_ASSETS));
  for (const state of Object.keys(JUP_ASSETS)) {
    const html = renderJupVisual({ state });
    assert.match(html, new RegExp(`data-state="${state}"`));
    assert.match(html, /src="\/assets\/jup\/jup-no-face.png"/);
    assert.doesNotMatch(html, /https?:/);
  }
  const warning = renderJupVisual({ state: 'warning' });
  assert.match(warning, /warning-triangle/);
  assert.doesNotMatch(warning, /eye-pill|mouth-line|open-face/);
  assert.match(renderJupVisual({ state: '<script>' }), /data-state="idle"/);
});
