import { renderJupVisual, visualStateFromUi } from './jup_visual.mjs';
import { renderApprovedKnowledgeBody, renderMessageBody } from './knowledge_content.mjs';
import {
  escapeHtml,
  renderConfidence,
  renderEmptyState,
  renderStatus,
} from './render.mjs';


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

function renderMessage(message, { fresh = false, visualState = null } = {}) {
  const role = message.role === 'USER' ? 'Você' : 'Jup';
  const klass = message.role === 'USER' ? 'conversation-message--user' : 'conversation-message--jup';
  const emote = message.thinking ? 'thinking' : visualState ?? message.visual_state ?? visualStateFromUi({ backendStatus: message.status, failed: message.failed });
  const context = message.context ? [message.context.system, message.context.next_step].filter(Boolean).map(escapeHtml).join(' · ') : '';
  return `<article class="conversation-message ${klass}${message.thinking ? ' conversation-message--thinking' : ''}${fresh ? ' is-new' : ''}">
    ${message.role === 'JUP' ? renderJupVisual({ state: emote, compact: true }) : ''}
    <div class="message-content"><div class="message-author"><strong>${role}</strong></div>
    ${message.thinking ? '<div class="thinking-dots" role="status" aria-label="Jup está pensando"><span aria-hidden="true">.</span><span aria-hidden="true">.</span><span aria-hidden="true">.</span></div>' : message.failed ? `<p class="message-error" role="alert">${escapeHtml(message.text)}</p>` : message.role === 'JUP' ? renderApprovedKnowledgeBody({ text: message.text, procedureUrl: message.procedure_url, knowledgeId: message.knowledge_id }) : renderMessageBody(message.text)}
    ${message.role === 'JUP' ? renderSupportHandoff(message.support_handoff) : ''}
    ${context ? `<div class="request-context">${context}</div>` : ''}</div>
  </article>`;
}

export function renderJupWorkspace({ messages = [], understood = null, loading = false, sourceContext = null, visualState = null, messageError = null, draft = '', animateFrom = messages.length }) {
  const lastAssistant = messages.findLastIndex(message => message.role === 'JUP');
  const conversation = messages.length ? messages.map((message, index) => renderMessage(
    message.role === 'JUP' && index === lastAssistant && !message.context && understood ? { ...message, context: understood } : message,
    { fresh: index >= animateFrom, visualState: index === lastAssistant && !loading ? visualState : null },
  )).join('') : renderMessage({ role: 'JUP', text: 'Como posso ajudar?\n\nConte o que está acontecendo e em qual sistema. Vamos começar por aí.' }, { visualState: visualState || 'idle' });
  return `<section class="jup-surface" aria-label="Atendimento com Jup">
    <header class="conversation-header"><div><h1>Falar com o Jup</h1><p>Ajuda para seguir com o trabalho.</p></div><a class="back-link" href="/" data-route="solutions">← Soluções</a></header>
    ${sourceContext ? `<p class="faq-source-context">Você estava vendo: ${escapeHtml(sourceContext.title)}</p>` : ''}
    <div class="jup-conversation"><div class="conversation-thread" role="log" aria-label="Conversa com Jup" aria-live="polite" tabindex="0">${conversation}
      ${understood && lastAssistant < 0 ? renderMessage({ role: 'JUP', text: '', context: understood }) : ''}
      ${loading ? renderMessage({ role: 'JUP', thinking: true }, { fresh: true }) : ''}
      ${messageError ? renderMessage({ role: 'JUP', text: messageError, failed: true }, { fresh: true }) : ''}
      <div class="conversation-end" aria-hidden="true"></div></div>
      <button class="scroll-bottom" type="button" data-action="scroll-bottom" hidden aria-label="Voltar à última mensagem">Última mensagem ↓</button>
      <form id="jup-form" class="composer" aria-label="Enviar mensagem ao Jup" aria-busy="${loading}">
        <label class="sr-only" for="jup-message">Mensagem</label>
        <textarea id="jup-message" name="message" rows="2" maxlength="3000" placeholder="Descreva o que aconteceu..."${loading ? ' disabled' : ''}>${escapeHtml(draft)}</textarea>
        <div class="composer-actions"><span>Enter para enviar · Shift+Enter para nova linha</span><button class="button button--primary" type="submit"${loading ? ' disabled' : ''}>${loading ? 'Aguarde...' : 'Enviar ↑'}</button></div>
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
