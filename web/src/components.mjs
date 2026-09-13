import { renderJupVisual } from './jup_visual.mjs';
import { renderApprovedKnowledgeBody, renderMessageBody } from './knowledge_content.mjs';
import {
  escapeHtml,
  renderConfidence,
  renderEmptyState,
  renderStatus,
} from './render.mjs';


function initials(name = 'Jup') {
  return String(name)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();
}

export function renderJupAvatar({ compact = false } = {}) {
  return renderJupVisual({ compact });
}

export function renderAppHeader({ activeRoute, operational = false, operationPath = '/demo/operacao/cdm' }) {
  const items = operational
    ? [['solutions', '/', 'Soluções'], ['approvals', operationPath, 'Operação'], ['prevention', '/demo/operacao/prevention', 'Prevenção']]
    : [['solutions', '/', 'Soluções'], ['jup', '/jup', 'Falar com o Jup']];
  return `<header class="app-header app-header--${operational ? 'operational' : 'public'}">
    <a class="brand-lockup" href="/" data-route="solutions">Jup Resolve</a>
    <nav class="primary-nav" aria-label="Navegação principal">${items.map(([route, href, label]) => `<a href="${href}" data-route="${route}"${activeRoute === route || (route === 'solutions' && activeRoute === 'solution') ? ' aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
  </header>`;
}

function renderSupportHandoff(handoff) {
  if (!handoff || typeof handoff !== 'object') return '';

  const technicianName = handoff.technician?.name;
  const requesterName = handoff.requester?.name;
  const requesterArea = handoff.requester?.area;
  const technicalSummary = handoff.technical_summary;
  if (!technicianName && !requesterName && !requesterArea && !technicalSummary) return '';

  const row = (label, value) =>
    value ? `<div class="handoff-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>` : '';

  return `<section class="support-handoff" aria-label="Encaminhamento técnico">
    <div class="support-handoff__heading"><span aria-hidden="true"></span><div><p>Continuidade do atendimento</p><h3>Encaminhamento técnico</h3></div></div>
    <dl>
      ${row('Especialista', technicianName)}
      ${row('Solicitante', requesterName)}
      ${row('Área', requesterArea)}
    </dl>
    ${technicalSummary ? `<details class="handoff-summary"><summary>Resumo para o especialista</summary><p class="support-handoff__summary">${escapeHtml(technicalSummary)}</p></details>` : ''}
  </section>`;
}

function renderMessage(message) {
  const role = message.role === 'USER' ? 'Você' : 'Jup';
  const klass = message.role === 'USER' ? 'conversation-message--user' : 'conversation-message--jup';
  return `<article class="conversation-message ${klass}">
    <div class="message-author">${message.role === 'JUP' ? renderJupAvatar({ compact: true }) : `<span class="user-avatar" aria-hidden="true">${escapeHtml(initials(role))}</span>`}<strong>${role}</strong></div>
    ${message.role === 'JUP' ? renderApprovedKnowledgeBody({ text: message.text, procedureUrl: message.procedure_url }) : renderMessageBody(message.text)}
    ${message.role === 'JUP' ? renderSupportHandoff(message.support_handoff) : ''}
  </article>`;
}

export function renderJupWorkspace({ messages = [], understood = null, loading = false, sourceContext = null, visualState = 'idle', messageError = null }) {
  const conversation = messages.length
    ? `<div class="conversation-visual">${renderJupVisual({ state: visualState, compact: true })}</div><div class="conversation-thread" role="log" aria-label="Conversa com Jup">${messages.map(renderMessage).join('')}${loading ? '<p class="thinking" role="status">Jup está analisando...</p>' : ''}</div>`
    : `<div class="jup-welcome">${renderJupVisual({ state: visualState })}<h1>Como posso ajudar?</h1></div>`;
  const context = understood ? [understood.system, understood.next_step].filter(Boolean).map(escapeHtml).join(' · ') : '';
  return `<section class="jup-surface" aria-label="Atendimento com Jup">
    <a class="back-link" href="/" data-route="solutions">← Soluções</a>
    ${sourceContext ? `<p class="faq-source-context">Você estava vendo: ${escapeHtml(sourceContext.title)}</p>` : ''}
    <div class="jup-conversation">${conversation}
      ${context ? `<p class="request-context">${context}</p>` : ''}
      ${messageError ? `<p class="message-error" role="alert">${escapeHtml(messageError)}</p>` : ''}
      <form id="jup-form" class="composer" aria-label="Enviar mensagem ao Jup">
        <label class="sr-only" for="jup-message">Mensagem</label>
        <textarea id="jup-message" name="message" rows="2" maxlength="3000" placeholder="Descreva o que aconteceu..."></textarea>
        <div class="composer-actions"><span>Enter para enviar · Shift+Enter para nova linha</span><button class="button button--primary" type="submit"${loading ? ' disabled' : ''}>Enviar</button></div>
      </form>
    </div>
  </section>`;
}

function timeline(events = []) {
  if (!events.length) return '';
  return `<ol class="timeline">${events
    .map((event) => `<li><span aria-hidden="true"></span><div><strong>${escapeHtml(event.label)}</strong>${event.occurred_at ? `<small>${escapeHtml(event.occurred_at)}</small>` : ''}</div></li>`)
    .join('')}</ol>`;
}

export function renderRequestList(items = []) {
  if (!items.length) {
    return renderEmptyState('Nenhuma solicitação ainda', 'Converse com o Jup para iniciar uma solicitação quando houver uma ação necessária.');
  }
  return `<div class="request-list">${items
    .map((item) => `<article class="request-row" data-request-id="${escapeHtml(item.request_id)}">
      <div class="request-row-main"><span class="system-mark">${escapeHtml(item.system)}</span><div><h3>${escapeHtml(item.purpose || item.requested_role || 'Solicitação')}</h3><p>${escapeHtml(item.request_id)}</p></div></div>
      <div class="request-row-status">${renderStatus(item)}</div>
      <div class="request-timeline">${timeline(item.timeline)}</div>
    </article>`)
    .join('')}</div>`;
}

export function renderOperationDetail(item, uiState = {}) {
  if (!item) return renderEmptyState('Selecione uma pendência', 'Abra uma solicitação da fila para revisar contexto, policy e routing.');
  const approving = uiState.pendingAction === 'approve';
  const rejecting = uiState.pendingAction === 'reject';
  const actionDisabled = approving || rejecting || item.state !== 'PENDING_APPROVAL';
  const policyReason = item.policy?.reason || item.policy?.decision || 'Sem detalhe adicional.';
  return `<article class="operation-detail">
    <header class="operation-detail-header"><div><p>${escapeHtml(item.request_id)}</p><h2>${escapeHtml(item.system)} · ${escapeHtml(item.purpose || item.requested_role)}</h2></div>${renderStatus(item)}</header>
    <div class="evidence-grid">
      <section><span>Solicitante</span><strong>${escapeHtml(item.requester?.name)}</strong><p>${escapeHtml(item.requester?.area)}</p></section>
      <section><span>Confidence</span>${renderConfidence(item.confidence)}</section>
      <section><span>Policy</span><strong>${escapeHtml(item.policy?.decision)}</strong><p>${escapeHtml(policyReason)}</p></section>
      <section><span>Routing</span><strong>${escapeHtml(item.routing?.technician_name || 'Não atribuído')}</strong></section>
    </div>
    ${timeline(item.timeline)}
    <div class="decision-bar">
      <button class="button button--secondary button--danger" data-action="reject" type="button"${actionDisabled ? ' disabled' : ''}>${rejecting ? 'Rejeitando...' : 'Rejeitar'}</button>
      <button class="button button--primary" data-action="approve" data-version="${escapeHtml(item.version)}" type="button"${actionDisabled ? ' disabled' : ''}>${approving ? 'Aprovando solicitação...' : 'Aprovar solicitação'}</button>
    </div>
  </article>`;
}

export function renderApprovalQueue(items = []) {
  if (!items.length) return renderEmptyState('Nenhuma pendência para você', 'Quando uma solicitação exigir sua aprovação e for roteada para você, ela aparecerá aqui.');
  return `<div class="approval-queue">${items
    .map((item) => `<button type="button" class="queue-row" data-request-id="${escapeHtml(item.request_id)}"><div><span>${escapeHtml(item.system)}</span><strong>${escapeHtml(item.requester?.name)}</strong><small>${escapeHtml(item.request_id)}</small></div>${renderStatus(item)}</button>`)
    .join('')}</div>`;
}

export function renderPreventionList(items = []) {
  if (!items.length) return renderEmptyState('Nenhuma oportunidade recorrente', 'O engine de prevenção ainda não encontrou um padrão com recorrência suficiente.');
  return `<div class="prevention-list">${items
    .map((item) => `<article class="prevention-row" data-opportunity-id="${escapeHtml(item.opportunity_id)}">
      <div class="prevention-count"><strong>${escapeHtml(item.occurrence_count)}</strong><span>ocorrências</span></div>
      <div class="prevention-main"><span>${escapeHtml(item.system)} · ${escapeHtml(item.intent)}</span><h3>${escapeHtml(item.category_label || item.category)}</h3><p>${escapeHtml(item.explanation)}</p></div>
      <button class="text-action" type="button" data-opportunity-id="${escapeHtml(item.opportunity_id)}">Ver explicação</button>
    </article>`)
    .join('')}</div>`;
}
