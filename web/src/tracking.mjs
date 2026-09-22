import { escapeHtml as esc, formatTimestamp, renderStatus, renderConfidence } from './render.mjs';
import { navIcon } from './icons.mjs';
import { routePath } from './router.mjs';

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
  if (operational) {
    return `<div class="tracking-queue tracking-queue--operational">${sortNewestFirst(items).map(item => `<button type="button" class="queue-row" data-request-id="${esc(item.request_id)}" aria-current="${item.request_id === selectedId}">
      <span class="queue-row__subject">${esc(subject(item))}</span>
      <span class="queue-row__meta"><strong>${esc(item.requester?.name || 'Solicitante')}</strong><small>${esc(item.request_id)}</small></span>
      <span class="queue-row__state">${renderStatus(item)}${updated(item) ? `<small class="tracking-updated">${navIcon('clock')} ${esc(formatTimestamp(updated(item)))}</small>` : ''}</span>
    </button>`).join('')}</div>`;
  }
  return `<div class="tracking-queue">${sortNewestFirst(items).map(item => `<button type="button" class="tracking-row" data-request-select="${esc(item.request_id)}" aria-current="${item.request_id === selectedId}"><span class="tracking-row-top"><span class="tracking-system">${esc(item.system)}</span><small>${esc(item.request_id)}</small></span><span class="tracking-subject">${esc(subject(item))}</span><span class="tracking-row-state">${renderStatus(item)}${updated(item) ? `<small class="tracking-updated">${navIcon('clock')} ${esc(formatTimestamp(updated(item)))}</small>` : ''}</span></button>`).join('')}</div>`;
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
  return `<section class="tracking-decision"><h3>Decisão</h3><strong>${esc(decision)}</strong>${item.policy?.reason ? `<p>${esc(item.policy.reason)}</p>` : ''}${executionStarted ? '<p>Há registro de execução neste atendimento.</p>' : ''}</section>`;
}

export function renderTrackingDetail(item, { operational = false, pendingAction = null } = {}) {
  if (!item) return '<div class="tracking-empty tracking-empty--detail"><strong>Selecione uma solicitação</strong><p>O resumo e o andamento aparecerão aqui.</p></div>';
  const busy = Boolean(pendingAction);
  const technicalRow = (label, value) => value ? `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>` : '';
  const jupSummary = item.policy?.reason
    || `Atendimento encaminhado para ${item.routing?.technician_name || 'a equipe responsável'}.`;
  const mismatch = item.scope_mismatch
    ? `<div class="tracking-mismatch"><strong>Divergência de contexto</strong><p>${item.scope_confirmed ? 'Confirmada pelo solicitante. O escopo pedido difere da área do perfil; revise antes de decidir.' : 'O escopo pedido difere da área do perfil e ainda aguarda confirmação.'}</p></div>`
    : '';
  if (!operational) return `<article class="tracking-detail"><header class="tracking-detail-header"><div><p class="tracking-kicker">${esc(item.request_id)}</p><h2>${esc(subject(item))}</h2></div>${renderStatus(item)}</header><section class="tracking-assignment"><h3>Responsável</h3><strong>${esc(item.routing?.technician_name || 'Aguardando atribuição')}</strong></section><section class="tracking-progress" aria-label="Andamento"><h3>Andamento</h3>${renderTimeline(item.timeline)}</section></article>`;
  const scope = item.business_scope?.toLocaleUpperCase('pt-BR') || roleLabel(item.requested_role);
  return `<article class="tracking-detail tracking-detail--operational">
    <header class="tracking-detail-header tracking-detail-header--compact"><div><p class="tracking-kicker">${esc(item.request_id)}</p><h2>${esc(subject(item))}</h2></div>${renderStatus(item)}</header>
    <section class="tracking-essential-meta" aria-label="Contexto essencial"><div><span>Solicitante</span><strong>${esc(item.requester?.name || 'Não informado')}</strong>${item.requester?.email ? `<small>${esc(item.requester.email)}</small>` : ''}</div><div><span>Área</span><strong>${esc(item.requester?.area || 'Não informada')}</strong>${item.requester?.job_title ? `<small>${esc(item.requester.job_title)}</small>` : ''}</div><div><span>Escopo solicitado</span><strong>${esc(scope)}</strong></div></section>
    ${mismatch}
    <section class="tracking-summary-panel" aria-label="Resumo do Jup"><h3>Resumo do Jup</h3><p>${esc(jupSummary)}</p></section>
    <section class="tracking-progress" aria-label="Andamento"><h3>Andamento</h3>${renderTimeline(item.timeline)}</section>
    <section class="tracking-next-action" aria-label="Ação"><h3>Ação</h3>${item.state === 'PENDING_APPROVAL' ? `<footer class="decision-bar"><button class="button button--secondary button--danger" data-action="reject" type="button"${busy ? ' disabled' : ''}>${pendingAction === 'reject' ? 'Rejeitando...' : 'Rejeitar'}</button><button class="button button--primary" data-action="approve" data-version="${esc(item.version)}" type="button"${busy ? ' disabled' : ''}>${pendingAction === 'approve' ? 'Aprovando solicitação...' : 'Aprovar solicitação'}</button></footer>` : '<p class="tracking-muted">Nenhuma ação pendente.</p>'}</section>
    <details class="technical-disclosure"><summary>Detalhes técnicos</summary><div class="technical-disclosure-body"><section class="tracking-analysis" aria-label="Análise do Jup"><h3>Confiança</h3><div class="tracking-confidence">${renderConfidence(item.confidence)}</div><h4>Por que essa confiança?</h4>${renderConfidenceReasons(item.confidence)}</section>${renderBackendDecision(item)}<section class="technical-metadata"><h3>Metadados técnicos</h3><dl>${technicalRow('Policy', item.policy?.decision)}${technicalRow('Motivo', item.policy?.reason_code)}${technicalRow('Routing', item.routing?.capability || item.capability)}${technicalRow('Origem', item.requester?.identity_source)}${technicalRow('Conhecimento', item.knowledge_id)}${technicalRow('Perfil', item.requested_role)}${technicalRow('Resultado', item.execution_result_code)}${technicalRow('Erro', item.execution_error_code)}</dl></section></div></details>
  </article>`;
}

export function renderRequesterWorkspace(items = [], selectedId = null) {
  if (!items.length) return `<section class="requester-requests"><h1 class="sr-only">Minhas solicitações</h1><div class="tracking-empty tracking-empty--requester"><strong>Nenhuma solicitação ainda</strong><p>Quando você iniciar um atendimento, poderá acompanhar o andamento por aqui.</p><a class="button button--primary" href="${routePath('jup')}" data-route="jup">Falar com o Jup</a></div></section>`;
  const sorted = sortNewestFirst(items);
  const selected = sorted.find(item => item.request_id === selectedId) || sorted[0];
  return `<section class="requester-requests"><h1 class="sr-only">Minhas solicitações</h1><div class="requester-request-list" aria-label="Suas solicitações"><div class="requester-request-columns" aria-hidden="true"><span>Sistema e assunto</span><span>Solicitação</span><span>Status</span><span>Atualização</span><span>Responsável</span></div>${sorted.map(item => `<button type="button" class="requester-request-row" data-request-select="${esc(item.request_id)}" aria-current="${item.request_id === selected.request_id}"><span class="requester-request-main"><strong>${esc(item.system || 'Atendimento')}</strong><span>${esc(subject(item))}</span></span><small>${esc(item.request_id)}</small>${renderStatus(item)}<span class="requester-request-time">${updated(item) ? `${navIcon('clock')} ${esc(formatTimestamp(updated(item)))}` : 'Sem atualização'}</span><strong class="requester-request-owner">${esc(item.routing?.technician_name || 'Aguardando atribuição')}</strong></button>`).join('')}</div><div class="requester-request-detail" aria-label="Detalhe da solicitação">${renderTrackingDetail(selected)}</div></section>`;
}
