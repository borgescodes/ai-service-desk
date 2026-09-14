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

export function renderAppHeader({ activeRoute, operational = false, operationPath = '/demo/operacao/cdm', identities = [], identity = {}, pending = false }) {
  const items = operational
    ? [['approvals', operationPath, 'Solicitações recebidas'], ['prevention', '/demo/operacao/prevention', 'Prevenção']]
    : [['solutions', '/', 'Central de Suporte'], ['jup', '/jup', 'Falar com o Jup'], ['requests', '/requests', 'Minhas solicitações']];
  const initials = (identity.name || 'Jup').split(' ').slice(0, 2).map(word => word[0]).join('');
  const links = items.map(([route, href, label]) => `<a href="${href}" data-route="${route}"${activeRoute === route || (route === 'solutions' && activeRoute === 'solution') ? ' aria-current="page"' : ''}>${navIcon(route)}<span>${label}</span></a>`).join('');
  return `<header class="app-header app-header--${operational ? 'operational' : 'public'}">
    <a class="brand-lockup" href="/" data-route="solutions"><img src="/assets/brand/jup-resolve-logo.svg" width="168" height="42" alt="Jup Resolve"></a>
    <nav class="primary-nav" aria-label="Navegação principal">${links}</nav>
    <details class="persona-menu"><summary><span class="user-avatar">${escapeHtml(initials)}</span><span class="user-copy"><strong>${escapeHtml(identity.name || 'Carregando')}</strong><small>${escapeHtml(identity.area || 'Juparanã')}</small></span>${navIcon('chevron')}</summary><div class="persona-options"><p>Trocar usuário</p>${identities.map(item => `<button type="button" data-persona="${escapeHtml(item.identity_id)}"${pending ? ' disabled' : ''} aria-pressed="${item.identity_id === identity.identity_id}"><strong>${escapeHtml(item.name || item.identity_id)}</strong><small>${escapeHtml(item.area || '')}</small></button>`).join('')}</div></details>
  </header><aside class="app-sidebar" aria-label="Menu contextual"><nav>
  ${operational ? '<p class="sidebar-label">Painel operacional</p>' : `<button class="sidebar-new" type="button" data-action="new-chat"${pending ? ' disabled' : ''}>${navIcon('plus')}Novo chat</button>`}
  ${links}</nav><div class="sidebar-footer"><img src="/assets/brand/jup-tagline.svg" alt="Jup Resolve" width="150" height="32"><p>Suporte para seguir em frente.</p></div></aside>`;
}

export function navIcon(name) {
  const paths = {
    plus: '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
    solutions: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    jup: '<path d="M21 11a9 9 0 0 1-9 9H4l-2 2v-11a9 9 0 0 1 19 0Z"/><path d="M7 11h10M7 15h6"/>',
    requests: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v4H9zM9 11h6M9 15h6"/>',
    approvals: '<path d="M3 5h18v15H3zM3 10h18M9 10v10"/>',
    prevention: '<path d="M3 18h18M5 14l4-4 4 3 6-8"/>',
    chevron: '<path d="m7 10 5 5 5-5"/>',
  };
  return `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.solutions}</svg>`;
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
    <div class="message-content"><div class="message-author"><strong>${role}</strong>${message.sentAt ? `<time datetime="${escapeHtml(message.sentAt)}">${escapeHtml(new Date(message.sentAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }))}</time>` : ''}</div>
    ${message.thinking ? '<div class="processing" role="status" aria-label="Jup está pensando"><strong>Pensando<span class="thinking-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span></strong><p class="processing-activity">Processando sua mensagem</p></div>' : message.failed ? `<p class="message-error" role="alert">${escapeHtml(message.text)}</p>` : message.role === 'JUP' ? renderApprovedKnowledgeBody({ text: message.text, procedureUrl: message.procedure_url, knowledgeId: message.knowledge_id }) : renderMessageBody(message.text)}
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
    <div class="jup-workspace-frame">
      <header class="conversation-header">${renderJupVisual({ state: loading ? 'thinking' : visualState || 'idle' })}<div class="conversation-header__copy"><h1>Olá, eu sou o <strong>Jup</strong></h1><p>Seu assistente virtual, pronto para ajudar.</p></div><div class="conversation-header__actions"><div class="conversation-status" data-state="${loading ? 'thinking' : 'ready'}"><span aria-hidden="true"></span>${loading ? 'Analisando sua mensagem' : 'Jup disponível'}</div><a class="back-link" href="/" data-route="solutions">Central de Suporte</a></div></header>
      ${sourceContext ? `<p class="faq-source-context">Você estava vendo: <strong>${escapeHtml(sourceContext.title)}</strong></p>` : ''}
      <div class="jup-workspace-body">

        <div class="conversation-stage"><div class="jup-conversation"><div class="conversation-thread" role="log" aria-label="Conversa com Jup" aria-live="polite" tabindex="0">${conversation}
          ${understood && lastAssistant < 0 ? renderMessage({ role: 'JUP', text: '', context: understood }) : ''}
          ${loading ? renderMessage({ role: 'JUP', thinking: true }, { fresh: true }) : ''}
          ${messageError ? renderMessage({ role: 'JUP', text: messageError, failed: true }, { fresh: true }) : ''}
          <div class="conversation-end" aria-hidden="true"></div></div>
          <button class="scroll-bottom" type="button" data-action="scroll-bottom" hidden aria-label="Voltar à última mensagem">Última mensagem ↓</button>
          <form id="jup-form" class="composer" aria-label="Enviar mensagem ao Jup" aria-busy="${loading}">
            <div class="composer-input-row"><span class="composer-leading-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17.5V7.8A2.8 2.8 0 0 1 6.8 5h10.4A2.8 2.8 0 0 1 20 7.8v6.4a2.8 2.8 0 0 1-2.8 2.8H9l-5 3v-2.5Z"/><path d="M8 9.5h8M8 13h5"/></svg></span><label class="sr-only" for="jup-message">Mensagem</label><textarea id="jup-message" name="message" rows="2" maxlength="3000" placeholder="Descreva o que aconteceu..."${loading ? ' disabled' : ''}>${escapeHtml(draft)}</textarea></div>
            <div class="composer-actions"><span class="composer-hint">Enter para enviar · Shift+Enter para nova linha</span><button class="button button--primary" type="submit"${loading ? ' disabled' : ''}>${loading ? 'Aguarde...' : 'Enviar ↑'}</button></div>
          </form>
        </div></div>
      </div>
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
      <details class="request-timeline"><summary>Ver detalhes da solicitação</summary><p>${escapeHtml(item.purpose)}</p>${item.routing?.technician_name ? `<p>Responsável: ${escapeHtml(item.routing.technician_name)}</p>` : ''}${timeline(item.timeline)}</details>
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
      <section><span>Confiança da classificação</span>${renderConfidence(item.confidence)}</section>
      <section><span>Policy</span><strong>${escapeHtml(item.policy?.decision)}</strong><p>${escapeHtml(policyReason)}</p></section>
      <section><span>Routing</span><strong>${escapeHtml(item.routing?.technician_name || 'Não atribuído')}</strong><p>${escapeHtml(item.routing?.capability)}</p></section>
    </div>
    <section class="technical-context"><h3>Contexto da solicitação</h3><p>${escapeHtml(item.purpose)}</p><dl><dt>Perfil solicitado</dt><dd>${escapeHtml(item.requested_role)}</dd><dt>Orientação de origem</dt><dd>${escapeHtml(item.knowledge_id)}</dd></dl></section>
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

export function renderHandoffs(items = []) {
  if (!items.length) return '';
  return `<section class="handoff-inbox" aria-label="Encaminhamentos recebidos"><h2>Encaminhados pelo Jup</h2>${items.map(item => `<article class="operation-detail"><header class="operation-detail-header"><div><p>${escapeHtml(item.handoff_id)}</p><h2>${escapeHtml(item.system)} · ${escapeHtml(item.requester?.name)}</h2></div><span class="status-badge">Encaminhado para suporte</span></header><div class="evidence-grid"><section><span>Responsável</span><strong>${escapeHtml(item.technician?.name)}</strong></section><section><span>Área do solicitante</span><strong>${escapeHtml(item.requester?.area)}</strong></section><section><span>Routing</span><strong>${escapeHtml(item.capability)}</strong></section></div><h3>Resumo técnico</h3><p class="technical-summary">${escapeHtml(item.technical_summary)}</p><details class="handoff-conversation"><summary>Ver contexto da conversa</summary>${(item.source_conversation ?? []).map(entry => `<p><strong>${entry.role === 'USER' ? 'Solicitante' : 'Jup'}:</strong> ${escapeHtml(entry.text)}</p>`).join('')}</details></article>`).join('')}</section>`;
}
