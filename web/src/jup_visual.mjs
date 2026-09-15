import { JUP_ASSETS, JUP_SHELL } from './jup_visual_assets.mjs';

const STATUS_TO_VISUAL = Object.freeze({
  SUPPORT_RESOLVED: 'success', KNOWLEDGE_FOUND: 'success', REQUEST_CREATED: 'success',
  DENIED_POLICY: 'warning', LOCAL_AI_INFERENCE_FAILED: 'warning', LOCAL_AI_RESPONSE_INVALID: 'warning',
  SUPPORT_HANDOFF_PENDING: 'escalation',
});
const LABELS = Object.freeze({ idle: 'Jup disponível', listening: 'Jup ouvindo', thinking: 'Jup analisando', success: 'Jup, resposta recebida', warning: 'Atenção no atendimento', escalation: 'Encaminhamento técnico' });
export function visualStateFromUi({ pending = false, backendStatus = null, focused = false, failed = false } = {}) {
  if (pending) return 'thinking';
  if (failed) return 'warning';
  if (Object.hasOwn(STATUS_TO_VISUAL, backendStatus)) return STATUS_TO_VISUAL[backendStatus];
  return focused ? 'listening' : 'idle';
}
export function renderJupVisual({ state = 'idle', compact = false } = {}) {
  const safeState = Object.hasOwn(JUP_ASSETS, state) ? state : 'idle';
  return `<div class="jup-avatar${compact ? ' jup-avatar--compact' : ''}" data-state="${safeState}" role="img" aria-label="${LABELS[safeState]}"><div class="jup-avatar__body"><div class="jup-avatar__surface"></div><svg class="jup-face" viewBox="0 0 1600 1600" aria-hidden="true"><g class="jup-face__ink">${JUP_ASSETS[safeState]}</g></svg><img class="jup-avatar__shell" src="${JUP_SHELL}" alt="" width="3919" height="3919" draggable="false"></div></div>`;
}
