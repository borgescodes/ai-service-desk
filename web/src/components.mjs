import { renderTrackingQueue, renderTrackingDetail, renderRequesterWorkspace } from './tracking.mjs';
import { renderJupVisual, visualStateFromUi } from './jup_visual.mjs';
import { renderApprovedKnowledgeBody, renderMessageBody } from './knowledge_content.mjs';
import { navIcon } from './icons.mjs';
import { corporateEmailFromName } from './state.mjs';
import {
  escapeHtml,
  renderEmptyState,
} from './render.mjs';

export { navIcon };

export function renderJupAvatar({ compact = false } = {}) {
  return renderJupVisual({ compact });
}

function personaIconPresentation(identity) {
  if (identity.role === 'REQUESTER') return { modifier: 'requester', icon: 'user' };
  const technicians = {
    'tecnico-cdm': { modifier: 'cdm', icon: 'technician-cdm' },
    'tecnico-m365': { modifier: 'm365', icon: 'technician-m365' },
    'tecnico-geral': { modifier: 'general', icon: 'technician-general' },
  };
  return technicians[identity.identity_id] ?? { modifier: 'technician', icon: 'support' };
}

export function renderAppHeader({ activeRoute, operational = false, operationPath = '/demo/operacao/cdm', identities = [], identity = {}, pending = false, identityError = null }) {
  const globalItems = operational
    ? [[activeRoute, operationPath, activeRoute === 'handoffs' ? 'Encaminhamentos' : 'Solicitações recebidas']]
    : [['solutions', '/', 'Central de Suporte'], ['jup', '/jup', 'Falar com o Jup'], ['requests', '/requests', 'Minhas solicitações']];
  const initials = (identity.name || 'Jup').split(' ').slice(0, 2).map(word => word[0]).join('');
  const requester = identity.role === 'REQUESTER'
    ? identity
    : identities.find(item => item.role === 'REQUESTER') ?? {};
  const links = items => items.map(([route, href, label]) => `<a href="${href}" data-route="${route}"${activeRoute === route || (route === 'solutions' && activeRoute === 'solution') ? ' aria-current="page"' : ''}>${navIcon(route)}<span>${label}</span></a>`).join('');
  const labels = { 'tecnico-cdm': 'Técnico CDM', 'tecnico-m365': 'Técnico Microsoft 365', 'tecnico-geral': 'Técnico Geral' };
  const choices = identities.map(item => {
    const visual = personaIconPresentation(item);
    return `<button class="persona-choice" type="button" data-persona="${escapeHtml(item.identity_id)}"${pending ? ' disabled' : ''} aria-pressed="${item.identity_id === identity.identity_id}"><span class="persona-choice-icon persona-choice-icon--${visual.modifier}">${navIcon(visual.icon)}</span><span><strong>${escapeHtml(item.role === 'REQUESTER' ? 'Requester' : labels[item.identity_id] || item.name || item.identity_id)}</strong><small>${escapeHtml(item.name || item.area || '')}</small></span>${item.identity_id === identity.identity_id ? navIcon('check') : ''}</button>`;
  }).join('');
  const email = corporateEmailFromName(requester.name || '');
  return `<header class="app-header app-header--${operational ? 'operational' : 'public'}">
    <a class="brand-lockup" href="/" data-route="solutions" aria-label="Jup Resolve"><span class="brand-wordmark" aria-hidden="true"><span class="brand-wordmark__jup">Jup</span><span class="brand-wordmark__resolve">Resolve</span></span></a>
    <nav class="primary-nav" aria-label="Navegação principal">${links(globalItems)}</nav>
    <div class="header-actions">${activeRoute === 'jup' ? `<button class="header-new-chat" type="button" data-action="new-chat"${pending ? ' disabled' : ''}>${navIcon('plus')}<span>Nova conversa</span></button>` : ''}<details class="persona-menu"><summary><span class="user-avatar">${escapeHtml(initials)}</span><span class="user-copy"><strong>${escapeHtml(identity.name || 'Carregando')}</strong><small>${escapeHtml(identity.area || 'Juparanã')}</small></span>${navIcon('chevron')}</summary><div class="persona-options"><div class="persona-list"><p>Trocar usuário</p>${choices}</div><details class="demo-identity-config"${identityError ? ' open' : ''}><summary>${navIcon('plus')}Novo usuário</summary><form id="demo-identity-form"><label><span>Nome</span><input name="name" data-identity-name type="text" required maxlength="180" value="${escapeHtml(requester.name || '')}" autocomplete="off"></label><div class="identity-field-row"><label><span>Cargo</span><input name="job_title" type="text" required maxlength="180" value="${escapeHtml(requester.job_title || '')}" autocomplete="off"></label><label><span>Área de atuação</span><input name="area" type="text" required maxlength="180" value="${escapeHtml(requester.area || '')}" autocomplete="off"></label></div><label class="email-preview"><span>E-mail</span><input name="email" data-email-preview type="email" readonly value="${escapeHtml(email)}"></label>${identityError ? `<p class="identity-form-error" role="alert">${escapeHtml(identityError)}</p>` : ''}<button class="button button--primary identity-save" type="submit"${pending ? ' disabled' : ''}>${pending === 'identity' ? 'Criando...' : 'Criar usuário'}</button></form></details></div></details></div>
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

function renderRequestSummary(summary) {
  const items = Array.isArray(summary?.items) ? summary.items : [];
  if (!items.length) return '';
  return `<div class="request-summary-list" aria-label="Resumo das solicitações">${items.map(item => `<a class="request-summary-row" href="/requests" data-route="requests"><span class="request-summary-row__top"><strong>${escapeHtml(item.system || 'Solicitação')}</strong><small>${escapeHtml(item.request_id || '')}</small></span><span class="request-summary-row__bottom"><span class="request-summary-status">${escapeHtml(item.state_label || '')}</span><span class="request-summary-action" aria-hidden="true">${navIcon('arrow-right')}</span></span></a>`).join('')}</div>`;
}

function renderSourceCard(article) {
  if (!article?.knowledge_id || !article?.title || article.provenance?.status !== 'APPROVED') return '';
  return `<a class="message-source-strip" href="/solucoes/${encodeURIComponent(article.knowledge_id)}" data-solution-link data-knowledge-id="${escapeHtml(article.knowledge_id)}"><span class="source-strip-icon">${navIcon('solutions')}</span><span class="source-strip-copy"><small>Central de Suporte</small><strong>${escapeHtml(article.title)}</strong></span><span class="source-strip-action">Abrir artigo ${navIcon('arrow-right')}</span></a>`;
}

function renderMessage(message, { fresh = false, visualState = null, initials = '', flipId = null } = {}) {
  const role = message.role === 'USER' ? 'Você' : 'Jup';
  const klass = message.role === 'USER' ? 'conversation-message--user' : 'conversation-message--jup';
  const emote = message.thinking ? 'thinking' : visualState ?? message.visual_state ?? visualStateFromUi({ backendStatus: message.status, failed: message.failed });
  const context = message.context ? [message.context.system, message.context.next_step].filter(Boolean).map(escapeHtml).join(' · ') : '';
  const requestSummary = message.role === 'JUP' ? renderRequestSummary(message.request_summary) : '';
  const sourceCard = message.role === 'JUP' ? renderSourceCard(message.article) : '';
  const assistantText = requestSummary ? String(message.text ?? '').split(/\n\s*\n/, 1)[0] : message.text;
  const progressive = fresh && message.role === 'JUP' && !message.thinking && !message.failed;
  const primary = message.thinking
    ? `<div class="processing" role="status" aria-label="Jup está pensando"><div class="processing-status"><strong>Pensando · <span data-thinking-seconds="0">0</span>s</strong><span class="thinking-dots" aria-hidden="true"><span></span><span></span><span></span></span></div><p class="processing-activity">${escapeHtml(message.activity || 'Entendendo sua solicitação')}</p></div>`
    : message.failed
      ? `<p class="message-error" role="alert">${escapeHtml(message.text)}</p>`
      : message.role === 'JUP'
        ? `<div class="message-primary"${progressive ? ' data-progressive-response aria-hidden="true"' : ''}>${renderApprovedKnowledgeBody({ text: assistantText, procedureUrl: message.procedure_url, knowledgeId: message.knowledge_id })}</div>${progressive ? `<span class="sr-only response-announcement">${escapeHtml(assistantText)}</span>` : ''}`
        : renderMessageBody(message.text);
  const followupAttribute = progressive ? ' data-response-followup aria-hidden="true"' : '';
  return `<article class="conversation-message ${klass}${message.thinking ? ' conversation-message--thinking' : ''}${fresh ? ' is-new' : ''}">
    ${message.role === 'JUP' ? renderJupVisual({ state: emote, compact: true, flipId }) : ''}
    <div class="message-content"><div class="message-author"><strong>${role}</strong>${message.sentAt ? `<time datetime="${escapeHtml(message.sentAt)}">${escapeHtml(new Date(message.sentAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }))}</time>` : ''}</div>
    <div class="message-bubble">${primary}
    ${sourceCard ? `<div${followupAttribute}>${sourceCard}</div>` : ''}
    ${requestSummary ? `<div${followupAttribute}>${requestSummary}</div>` : ''}
    ${message.role === 'JUP' && message.support_handoff ? `<div${followupAttribute}>${renderSupportHandoff(message.support_handoff)}</div>` : ''}
    ${message.role === 'JUP' && message.requestCta === 'REQUESTS' ? `<div${followupAttribute}><a class="message-request-cta" href="/requests" data-route="requests">Ver todas as solicitações ${navIcon('arrow-right')}</a></div>` : ''}
    ${context ? `<div class="request-context">${context}</div>` : ''}</div></div>
    ${message.role === 'USER' && initials ? `<span class="message-user-avatar" aria-hidden="true">${escapeHtml(initials)}</span>` : ''}
  </article>`;
}

function renderChatWelcome(leaving, draft = '', identity = {}) {
  const listening = Boolean(String(draft).trim());
  const firstName = String(identity.name || '').trim().split(/\s+/)[0];
  return `<div class="chat-welcome${leaving ? ' chat-welcome--leaving' : ''}" data-listening="${listening}"${leaving ? ' aria-hidden="true"' : ''}>
    <div class="chat-welcome-avatar-stack" data-flip-id="jup-avatar" aria-live="polite">
      <div class="chat-welcome-avatar-state chat-welcome-avatar-state--idle" data-welcome-state="idle" aria-hidden="${listening}">${renderJupVisual({ state: 'idle' })}</div>
      <div class="chat-welcome-avatar-state chat-welcome-avatar-state--listening" data-welcome-state="listening" aria-hidden="${!listening}">${renderJupVisual({ state: 'listening' })}</div>
    </div>
    <h1><span class="welcome-line welcome-line--greeting" data-welcome-line>Olá${firstName ? `, <strong>${escapeHtml(firstName)}!</strong>` : '!'}</span><span class="welcome-line welcome-line--question" data-welcome-line>Como posso ajudar?</span></h1>
  </div>`;
}

export function renderJupWorkspace({ identity = {}, messages = [], understood = null, loading = false, processingActivity = null, sourceContext = null, visualState = null, messageError = null, draft = '', commandMenuOpen = true, animateFrom = messages.length } = {}) {
  const entering = loading && messages.length === 1 && animateFrom === 0;
  const welcome = (!messages.length && !loading) || entering;
  const initials = (identity.name || '').split(' ').slice(0, 2).map(word => word[0] || '').join('');
  const lastAssistant = messages.findLastIndex(message => message.role === 'JUP');
  const conversation = messages.length ? messages.map((message, index) => renderMessage(
    message.role === 'JUP' && index === lastAssistant && !message.context && understood ? { ...message, context: understood } : message,
    { fresh: index >= animateFrom, initials, visualState: index === lastAssistant && !loading ? visualState : null },
  )).join('') : '';
  return `<section class="jup-surface" aria-label="Atendimento com Jup">
    <div class="jup-workspace-frame">
      ${sourceContext ? `<p class="faq-source-context">Você estava vendo: <strong>${escapeHtml(sourceContext.title)}</strong></p>` : ''}
      <div class="jup-workspace-body">

        <div class="conversation-stage"><div class="jup-conversation"><div class="conversation-thread${entering ? ' conversation-thread--entering' : ''}" role="log" aria-label="Conversa com Jup" aria-live="polite" tabindex="0">${welcome ? renderChatWelcome(entering, draft, identity) : ''}${conversation}
          ${understood && lastAssistant < 0 ? renderMessage({ role: 'JUP', text: '', context: understood }) : ''}
          ${loading ? renderMessage({ role: 'JUP', thinking: true, activity: processingActivity || 'Entendendo sua solicitação' }, { fresh: true, flipId: entering ? 'jup-avatar' : null }) : ''}
          ${messageError ? renderMessage({ role: 'JUP', text: messageError, failed: true }, { fresh: true }) : ''}
          <div class="conversation-end" aria-hidden="true"></div></div>
          <button class="scroll-bottom" type="button" data-action="scroll-bottom" hidden aria-label="Voltar à última mensagem">Última mensagem ↓</button>
          <form id="jup-form" class="composer" aria-label="Enviar mensagem ao Jup" aria-busy="${loading}">
            ${commandMenuOpen && /^\/\S*$/.test(draft) ? '<div class="composer-command-menu" data-command-menu role="listbox" aria-label="Comandos"><button type="button" data-command="/solicitacoes" role="option" aria-label="/solicitacoes. Ver minhas solicitações e seus status"><strong>/solicitacoes</strong><span>Ver minhas solicitações e seus status</span></button></div>' : ''}
            <div class="composer-input-row"><span class="composer-leading-icon" data-composing="${Boolean(String(draft).trim())}" aria-hidden="true"><span class="composer-leading-icon__state composer-leading-icon__state--idle">${navIcon('message-circle-dots')}</span><span class="composer-leading-icon__state composer-leading-icon__state--typing">${navIcon('message-circle-edit')}</span></span><label class="sr-only" for="jup-message">Mensagem</label><textarea id="jup-message" name="message" rows="1" maxlength="3000" aria-describedby="composer-hint" placeholder="Digite sua mensagem aqui..."${loading ? ' disabled' : ''}>${escapeHtml(draft)}</textarea></div>
            <div class="composer-actions"><span id="composer-hint" class="composer-hint">Enter para enviar · Shift+Enter para nova linha</span><button class="button button--primary composer-send" type="submit" aria-label="Enviar mensagem"${loading ? ' disabled' : ''}><span class="sr-only">${loading ? 'Aguarde...' : 'Enviar'}</span>${navIcon('send')}</button></div>
          </form>
        </div></div>
      </div>
    </div>
  </section>`;
}

export function renderRequestList(items = [], selectedId = null) {
  return renderRequesterWorkspace(items, selectedId);
}

export function renderOperationDetail(item, uiState = {}) {
  return renderTrackingDetail(item, { operational: true, pendingAction: uiState.pendingAction });
}

export function renderApprovalQueue(items = [], selectedId = null) {
  return renderTrackingQueue(items, selectedId || items[0]?.request_id, true);
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
  return `<section class="handoff-inbox" aria-label="Encaminhamentos recebidos"><h2>Encaminhamentos</h2>${renderHandoffWorkspace(items)}</section>`;
}

function handoffTimestamp(item) {
  return Date.parse(item.updated_at || item.created_at || '') || 0;
}

function handoffPresentation(item) {
  const fields = Object.fromEntries(String(item.technical_summary || '').split(/\r?\n/).map(line => {
    const separator = line.indexOf(':');
    return separator > 0 ? [line.slice(0, separator).trim(), line.slice(separator + 1).trim()] : null;
  }).filter(Boolean));
  return {
    system: fields['Sistema/contexto'] || (item.system === 'GENERAL_IT' ? 'TI geral' : item.system || 'Atendimento de TI'),
    subject: fields['Sintoma/pedido informado'] || 'Encaminhamento para continuidade',
    approved: fields['Orientação aprovada encontrada'],
  };
}

function handoffUpdated(item) {
  const value = handoffTimestamp(item);
  return value ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(value) : '';
}

export function renderHandoffWorkspace(items = [], selectedId = null) {
  const sorted = [...items].sort((a, b) => handoffTimestamp(b) - handoffTimestamp(a));
  if (!sorted.length) return `<section class="tracking-empty handoff-empty">${navIcon('inbox')}<strong>Nenhum encaminhamento agora</strong><p>Novos atendimentos atribuídos a esta fila aparecerão aqui.</p></section>`;
  const selected = sorted.find(item => item.handoff_id === selectedId) || sorted[0];
  const selectedPresentation = handoffPresentation(selected);
  const conversation = (selected.source_conversation || []).map(entry => `<li><strong>${entry.role === 'USER' ? 'Solicitante' : 'Jup'}</strong><p>${escapeHtml(entry.text)}</p></li>`).join('');
  const queue = sorted.map((item) => {
    const summary = handoffPresentation(item);
    return `<button type="button" class="queue-row" data-handoff-id="${escapeHtml(item.handoff_id)}" aria-current="${item.handoff_id === selected.handoff_id}"><strong class="queue-row__subject">${escapeHtml(summary.subject)}</strong><span class="queue-row__meta"><span>${escapeHtml(item.requester?.name || 'Solicitante')}</span><small>${escapeHtml(item.handoff_id)}</small></span><span class="queue-row__state"><span class="status-badge">Encaminhado</span>${handoffUpdated(item) ? `<small class="tracking-updated">${navIcon('clock')} ${escapeHtml(handoffUpdated(item))}</small>` : ''}</span></button>`;
  }).join('');
  return `<div class="tracking-workspace handoff-workspace"><section class="tracking-list" aria-label="Fila de encaminhamentos"><header class="tracking-list-header"><h2>Fila</h2><span>${sorted.length}</span></header><div class="handoff-queue">${queue}</div></section><article class="tracking-detail handoff-detail"><header class="tracking-detail-header"><div><p class="tracking-kicker">${escapeHtml(selected.handoff_id)}</p><h2>${escapeHtml(selectedPresentation.subject)}</h2></div><span class="status-badge">Encaminhado</span></header><section aria-label="Contexto do solicitante"><h3>Contexto do solicitante</h3><div class="tracking-person"><span class="tracking-person-icon">${escapeHtml((selected.requester?.name || '?')[0])}</span><div><strong>${escapeHtml(selected.requester?.name || '')}</strong><p>${escapeHtml(selected.requester?.area || '')}</p></div></div></section><section aria-label="Resumo do Jup"><h3>Resumo do Jup</h3><p class="handoff-summary-text">${escapeHtml(selectedPresentation.subject)}</p>${selectedPresentation.approved ? `<p class="tracking-muted">Orientação aprovada encontrada: ${escapeHtml(selectedPresentation.approved)}</p>` : ''}</section><section aria-label="Conversa"><h3>Conversa</h3><ol class="handoff-conversation-list">${conversation}</ol></section><details class="technical-disclosure"><summary>Detalhes técnicos</summary><dl><div><dt>Responsável</dt><dd>${escapeHtml(selected.technician?.name || '')}</dd></div><div><dt>Capability</dt><dd>${escapeHtml(selected.capability || '')}</dd></div><div><dt>Confiança</dt><dd>${escapeHtml(selected.confidence?.label || '')}</dd></div><div><dt>Resumo original</dt><dd class="technical-summary-raw">${escapeHtml(selected.technical_summary || '')}</dd></div></dl></details></article></div>`;
}
