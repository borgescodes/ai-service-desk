import { escapeHtml as esc, formatTimestamp, renderStatus, renderConfidence } from './render.mjs';

const subject = item => item.purpose || item.requested_role || 'Solicitação de atendimento';
const updated = item => item.updated_at || item.timeline?.at(-1)?.occurred_at || item.created_at;

export function renderTrackingQueue(items, selectedId, operational = false) {
  if (!items.length) return '<div class="tracking-empty"><strong>Nenhuma solicitação na fila</strong><p>Novos atendimentos atribuídos a você aparecerão aqui.</p></div>';
  return `<div class="tracking-queue">${items.map(item => `<button type="button" class="${operational ? 'queue-row' : 'tracking-row'}" ${operational ? 'data-request-id' : 'data-request-select'}="${esc(item.request_id)}" aria-current="${item.request_id === selectedId}">
    <span class="tracking-row-top"><span class="tracking-system">${esc(item.system)}</span><small>${esc(item.request_id)}</small></span>
    ${operational ? `<strong class="tracking-requester">${esc(item.requester?.name)}</strong>` : ''}
    <span class="tracking-subject">${esc(subject(item))}</span>
    ${renderStatus(item)}<small class="tracking-updated">Atualizado · ${esc(formatTimestamp(updated(item)))}</small>
  </button>`).join('')}</div>`;
}

function renderTimeline(events = []) {
  if (!events.length) return '<p class="tracking-muted">Sem atualizações registradas.</p>';
  return `<ol class="tracking-timeline">${events.map((event, index) => `<li><span class="timeline-marker" aria-hidden="true">${index === events.length - 1 ? '●' : '✓'}</span><div><strong>${esc(event.label || 'Atualização registrada')}</strong>${event.occurred_at ? `<time datetime="${esc(event.occurred_at)}">${esc(formatTimestamp(event.occurred_at))}</time>` : ''}</div></li>`).join('')}</ol>`;
}

export function renderTrackingDetail(item, { operational = false, pendingAction = null } = {}) {
  if (!item) return '<div class="tracking-empty tracking-empty--detail"><strong>Selecione uma solicitação</strong><p>O resumo e o andamento aparecerão aqui.</p></div>';
  const busy = Boolean(pendingAction);
  const technicalRow = (label, value) => value ? `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>` : '';
  return `<article class="tracking-detail">
    <header class="tracking-detail-header"><div><p class="tracking-kicker">${esc(item.request_id)} <span>·</span> ${esc(item.system)}</p><h2>${operational ? 'Resumo do Jup' : 'Resumo'}</h2></div>${renderStatus(item)}</header>
    <p class="tracking-summary">${esc(subject(item))}</p>
    ${operational ? `<div class="tracking-person"><span class="tracking-person-icon" aria-hidden="true">${esc((item.requester?.name || '?').slice(0, 1))}</span><div><strong>${esc(item.requester?.name)}</strong><p>${esc(item.requester?.area)}</p></div></div>` : ''}
    <section class="tracking-assignment"><h3>${operational ? 'Encaminhamento' : 'Responsável'}</h3><strong>${esc(item.routing?.technician_name || 'Aguardando atribuição')}</strong>${operational && item.policy?.reason ? `<p>${esc(item.policy.reason)}</p>` : ''}</section>
    <section class="tracking-progress"><h3>Andamento</h3>${renderTimeline(item.timeline)}</section>
    ${operational ? `<details class="technical-disclosure"><summary>Detalhes técnicos</summary><dl>${technicalRow('Policy', item.policy?.decision)}${technicalRow('Motivo técnico', item.policy?.reason_code)}${technicalRow('Routing', item.routing?.capability || item.capability)}<div><dt>Confiança</dt><dd>${renderConfidence(item.confidence)}</dd></div>${technicalRow('Orientação de origem', item.knowledge_id)}${technicalRow('Perfil solicitado', item.requested_role)}${technicalRow('Resultado de execução', item.execution_result_code)}${technicalRow('Erro de execução', item.execution_error_code)}</dl></details>` : ''}
    ${operational && item.state === 'PENDING_APPROVAL' ? `<footer class="decision-bar"><button class="button button--secondary button--danger" data-action="reject" type="button"${busy ? ' disabled' : ''}>${pendingAction === 'reject' ? 'Rejeitando...' : 'Rejeitar'}</button><button class="button button--primary" data-action="approve" data-version="${esc(item.version)}" type="button"${busy ? ' disabled' : ''}>${pendingAction === 'approve' ? 'Aprovando solicitação...' : 'Aprovar solicitação'}</button></footer>` : ''}
  </article>`;
}

export function renderTrackingWorkspace(items = [], selectedId = null) {
  if (!items.length) return '<section class="tracking-empty tracking-empty--requester"><strong>Nenhuma solicitação ainda</strong><p>Quando você iniciar um atendimento, poderá acompanhar o andamento por aqui.</p><a class="button button--primary" href="/jup" data-route="jup">Falar com o Jup →</a></section>';
  const selected = items.find(item => item.request_id === selectedId) || items[0];
  return `<div class="tracking-workspace"><section class="tracking-list" aria-label="Suas solicitações"><header class="tracking-list-header"><h2>Seus atendimentos</h2><span>${items.length}</span></header>${renderTrackingQueue(items, selected.request_id)}</section><section aria-label="Detalhe da solicitação">${renderTrackingDetail(selected)}</section></div>`;
}
