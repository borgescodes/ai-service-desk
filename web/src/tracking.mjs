import { escapeHtml as esc, formatTimestamp, renderStatus, renderConfidence } from './render.mjs';
import { navIcon } from './icons.mjs';

const subject = item => item.purpose || item.requested_role || 'Solicitação de atendimento';
const timestamp = item => [item.updated_at, item.created_at, item.timeline?.at(-1)?.occurred_at]
  .filter(Boolean)
  .map(value => Date.parse(value))
  .filter(Number.isFinite)
  .sort((a, b) => b - a)[0] ?? 0;
const updated = item => {
  const value = timestamp(item);
  return value ? new Date(value).toISOString() : null;
};
const roleLabel = role => ({ SOLICITANTE: 'Solicitante', APROVADOR: 'Aprovador', ADMIN: 'Administrador', SUPERADMIN: 'Superadmin' }[role] || role || 'Não informado');

export function sortNewestFirst(items = []) {
  return [...items].sort((a, b) => timestamp(b) - timestamp(a));
}

export function renderTrackingQueue(items, selectedId, operational = false) {
  if (!items.length) return '<div class="tracking-empty"><strong>Nenhuma solicitação na fila</strong><p>Novos atendimentos atribuídos a você aparecerão aqui.</p></div>';
  return `<div class="tracking-queue">${sortNewestFirst(items).map(item => `<button type="button" class="${operational ? 'queue-row' : 'tracking-row'}" ${operational ? 'data-request-id' : 'data-request-select'}="${esc(item.request_id)}" aria-current="${item.request_id === selectedId}">
    <span class="tracking-row-top"><span class="tracking-system">${esc(item.system)}</span><small>${esc(item.request_id)}</small></span>
    ${operational ? `<strong class="tracking-requester">${esc(item.requester?.name)}</strong>` : ''}
    <span class="tracking-subject">${esc(subject(item))}</span>
    <span class="tracking-row-state">${renderStatus(item)}${updated(item) ? `<small class="tracking-updated">${navIcon('clock')} ${esc(formatTimestamp(updated(item)))}</small>` : ''}</span>
  </button>`).join('')}</div>`;
}

function renderTimeline(events = []) {
  if (!events.length) return '<p class="tracking-muted">Sem atualizações registradas.</p>';
  return `<ol class="tracking-timeline">${events.map((event, index) => `<li><span class="timeline-marker" aria-hidden="true">${navIcon(index === events.length - 1 ? 'clock' : 'check')}</span><div><strong>${esc(event.label || 'Atualização registrada')}</strong>${event.occurred_at ? `<time datetime="${esc(event.occurred_at)}">${esc(formatTimestamp(event.occurred_at))}</time>` : ''}</div></li>`).join('')}</ol>`;
}

function renderConfidenceReasons(confidence = {}) {
  const items = confidence.explanations || [];
  if (!items.length) return '<p class="tracking-muted">Sem evidências adicionais registradas.</p>';
  return `<ul class="confidence-reasons">${items.map(item => `<li data-kind="${esc(item.kind || 'missing')}"><span aria-hidden="true">${navIcon(item.kind === 'positive' ? 'check' : 'warning')}</span><span>${esc(item.text)}</span></li>`).join('')}</ul>`;
}

function renderBackendDecision(item) {
  const requiresApproval = item.policy?.requires_approval;
  const denied = item.policy?.decision === 'DENY' || item.state === 'DENIED_POLICY';
  const executionStarted = Boolean(item.execution_started_at || item.execution_finished_at || item.execution_result_code || item.execution_error_code);
  let decision = 'Revisão humana necessária';
  if (requiresApproval) decision = 'Aprovação humana necessária';
  if (denied) decision = 'Bloqueado por política';
  return `<section class="tracking-decision"><h3>Decisão do backend</h3><strong>${esc(decision)}</strong>${item.policy?.reason ? `<p>${esc(item.policy.reason)}</p>` : ''}<p>${executionStarted ? 'Há registro de execução neste atendimento.' : 'Nenhuma execução automática ocorreu até este momento.'}</p></section>`;
}

export function renderTrackingDetail(item, { operational = false, pendingAction = null } = {}) {
  if (!item) return '<div class="tracking-empty tracking-empty--detail"><strong>Selecione uma solicitação</strong><p>O resumo e o andamento aparecerão aqui.</p></div>';
  const busy = Boolean(pendingAction);
  const technicalRow = (label, value) => value ? `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>` : '';
  const expectedAction = item.policy?.decision === 'DENY' || item.state === 'DENIED_POLICY'
    ? 'Revisar o bloqueio registrado'
    : item.policy?.requires_approval
      ? 'Revisar e decidir a solicitação'
      : 'Dar continuidade ao atendimento';
  const jupSummary = item.policy?.reason
    || `Atendimento encaminhado para ${item.routing?.technician_name || 'a equipe responsável'}.`;
  const mismatch = item.scope_mismatch
    ? `<div class="tracking-mismatch"><strong>Divergência de contexto</strong><p>${item.scope_confirmed ? 'Confirmada pelo solicitante. O escopo pedido difere da área do perfil; revise antes de decidir.' : 'O escopo pedido difere da área do perfil e ainda aguarda confirmação.'}</p></div>`
    : '';
  return `<article class="tracking-detail${operational ? ' tracking-detail--operational' : ''}">
    <header class="tracking-detail-header"><div><p class="tracking-kicker">${esc(item.request_id)} <span>·</span> ${esc(item.system)}</p><h2>${operational ? 'Atendimento em análise' : 'Resumo da solicitação'}</h2></div>${renderStatus(item)}</header>
    ${operational ? `<section class="tracking-request-facts" aria-label="Solicitação"><h3>Solicitação</h3><p class="tracking-request-title">${esc(subject(item))}</p><dl>${technicalRow('Sistema', item.system)}${technicalRow('Perfil solicitado', roleLabel(item.requested_role))}${technicalRow('Escopo CDM', item.business_scope?.toLocaleUpperCase('pt-BR'))}</dl>${mismatch}</section>
    <section class="tracking-requester-card" aria-label="Solicitante"><h3>Solicitante</h3><div class="tracking-person"><span class="tracking-person-icon" aria-hidden="true">${esc((item.requester?.name || '?').slice(0, 1))}</span><div><strong>${esc(item.requester?.name)}</strong><p>${esc(item.requester?.email || '')}</p><div class="tracking-person-context"><span>${esc(item.requester?.job_title || '')}</span><span>${esc(item.requester?.area || '')}</span></div></div></div></section>
    <section class="tracking-summary-panel" aria-label="Resumo do Jup"><h3>Resumo do Jup</h3><p>${esc(jupSummary)}</p></section>` : `<p class="tracking-summary">${esc(subject(item))}</p>`}
    ${operational ? '' : `<section class="tracking-assignment"><h3>Responsável</h3><strong>${esc(item.routing?.technician_name || 'Aguardando atribuição')}</strong>${item.policy?.reason ? `<p>${esc(item.policy.reason)}</p>` : ''}</section>`}
    <section class="tracking-progress" aria-label="Andamento"><h3>Andamento</h3>${renderTimeline(item.timeline)}</section>
    ${operational ? `<section class="tracking-next-action" aria-label="Ação esperada"><div><h3>Ação esperada</h3><strong>${esc(expectedAction)}</strong><p>${esc(item.routing?.technician_name || 'Aguardando atribuição')}</p></div>${item.state === 'PENDING_APPROVAL' ? `<footer class="decision-bar"><button class="button button--secondary button--danger" data-action="reject" type="button"${busy ? ' disabled' : ''}>${pendingAction === 'reject' ? 'Rejeitando...' : 'Rejeitar'}</button><button class="button button--primary" data-action="approve" data-version="${esc(item.version)}" type="button"${busy ? ' disabled' : ''}>${pendingAction === 'approve' ? 'Aprovando solicitação...' : 'Aprovar solicitação'}</button></footer>` : ''}</section>
    <details class="technical-disclosure"><summary>Detalhes técnicos</summary><div class="technical-disclosure-body"><section class="tracking-analysis" aria-label="Análise do Jup"><h3>Análise do Jup</h3><div class="tracking-confidence"><span>Confiança</span>${renderConfidence(item.confidence)}</div><h4>Por que essa confiança?</h4>${renderConfidenceReasons(item.confidence)}</section>${renderBackendDecision(item)}<dl>${technicalRow('Policy', item.policy?.decision)}${technicalRow('Motivo técnico', item.policy?.reason_code)}${technicalRow('Routing', item.routing?.capability || item.capability)}${technicalRow('Origem da identidade', item.requester?.identity_source)}${technicalRow('Orientação de origem', item.knowledge_id)}${technicalRow('Perfil solicitado', item.requested_role)}${technicalRow('Resultado de execução', item.execution_result_code)}${technicalRow('Erro de execução', item.execution_error_code)}</dl></div></details>` : ''}
  </article>`;
}

export function renderTrackingWorkspace(items = [], selectedId = null) {
  if (!items.length) return '<section class="tracking-empty tracking-empty--requester"><strong>Nenhuma solicitação ainda</strong><p>Quando você iniciar um atendimento, poderá acompanhar o andamento por aqui.</p><a class="button button--primary" href="/jup" data-route="jup">Falar com o Jup →</a></section>';
  const sorted = sortNewestFirst(items);
  const selected = sorted.find(item => item.request_id === selectedId) || sorted[0];
  return `<div class="tracking-workspace"><section class="tracking-list" aria-label="Suas solicitações"><header class="tracking-list-header"><h2>Solicitações</h2><span>${sorted.length}</span></header>${renderTrackingQueue(sorted, selected.request_id)}</section><section aria-label="Detalhe da solicitação">${renderTrackingDetail(selected)}</section></div>`;
}
