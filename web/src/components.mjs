import { renderTrackingQueue, renderTrackingDetail, renderTrackingWorkspace } from './tracking.mjs';
import { renderJupVisual, visualStateFromUi } from './jup_visual.mjs';
import { renderApprovedKnowledgeBody, renderMessageBody } from './knowledge_content.mjs';
import { navIcon } from './icons.mjs';
import {
  escapeHtml,
  renderEmptyState,
} from './render.mjs';

export { navIcon };

export function renderJupAvatar({ compact = false } = {}) {
  return renderJupVisual({ compact });
}

export function renderAppHeader({ activeRoute, operational = false, operationPath = '/demo/operacao/cdm', identities = [], identity = {}, pending = false, identityError = null }) {
  const globalItems = operational ? [] : [['solutions', '/', 'Soluções'], ['jup', '/jup', 'Falar com o Jup']];
  const sidebarItems = operational
    ? [['approvals', operationPath, 'Solicitações recebidas']]
    : [['requests', '/requests', 'Minhas solicitações']];
  const initials = (identity.name || 'Jup').split(' ').slice(0, 2).map(word => word[0]).join('');
  const requester = identity.role === 'REQUESTER'
    ? identity
    : identities.find(item => item.role === 'REQUESTER') ?? {};
  const links = items => items.map(([route, href, label]) => `<a href="${href}" data-route="${route}"${activeRoute === route || (route === 'solutions' && activeRoute === 'solution') ? ' aria-current="page"' : ''}>${navIcon(route)}<span>${label}</span></a>`).join('');
  const showSidebar = !['solutions', 'solution'].includes(activeRoute);
  const choices = identities.filter(item => item.identity_id !== 'tecnico-geral').map(item => `<button class="persona-choice" type="button" data-persona="${escapeHtml(item.identity_id)}"${pending ? ' disabled' : ''} aria-pressed="${item.identity_id === identity.identity_id}"><span><strong>${escapeHtml(item.name || item.identity_id)}</strong><small>${escapeHtml(item.area || '')}</small></span>${item.identity_id === identity.identity_id ? '<em>Ativo</em>' : ''}</button>`).join('');
  return `<header class="app-header app-header--${operational ? 'operational' : 'public'}">
    <a class="brand-lockup" href="/" data-route="solutions"><img src="/assets/brand/jup-resolve-logo.svg" width="168" height="42" alt="Jup Resolve"></a>
    ${operational ? '<div></div>' : `<nav class="primary-nav" aria-label="Navegação principal">${links(globalItems)}</nav>`}
    <div class="header-actions"><a class="header-search" href="/" data-route="solutions" aria-label="Buscar artigos">${navIcon('search')}</a><details class="persona-menu"><summary><span class="user-avatar">${escapeHtml(initials)}</span><span class="user-copy"><strong>${escapeHtml(identity.name || 'Carregando')}</strong><small>${escapeHtml(identity.area || 'Juparanã')}</small></span>${navIcon('chevron')}</summary><div class="persona-options"><div class="persona-list"><p>Trocar usuário</p>${choices}</div><details class="demo-identity-config"${identityError ? ' open' : ''}><summary>Configurar usuário da demo</summary><form id="demo-identity-form"><p>Crie uma identidade sintética confiável para esta sessão.</p><label><span>Nome</span><input name="name" type="text" required maxlength="180" value="${escapeHtml(requester.name || '')}" autocomplete="off"></label><label><span>E-mail corporativo</span><input name="email" type="email" required maxlength="320" pattern="[^@]+@juparana[.]com[.]br" title="Use um e-mail @juparana.com.br" value="${escapeHtml(requester.email || '')}" autocomplete="off"></label><div class="identity-field-row"><label><span>Cargo</span><input name="job_title" type="text" required maxlength="180" value="${escapeHtml(requester.job_title || '')}" autocomplete="off"></label><label><span>Área de atuação</span><input name="area" type="text" required maxlength="180" value="${escapeHtml(requester.area || '')}" autocomplete="off"></label></div>${identityError ? `<p class="identity-form-error" role="alert">${escapeHtml(identityError)}</p>` : ''}<button class="button button--primary identity-save" type="submit"${pending ? ' disabled' : ''}>${pending === 'identity' ? 'Configurando...' : 'Criar e ativar usuário'}</button></form></details></div></details></div>
  </header>${showSidebar ? `<aside class="app-sidebar" aria-label="Menu contextual"><nav>
  ${operational ? '<p class="sidebar-label">Painel operacional</p>' : `<button class="sidebar-new" type="button" data-action="new-chat"${pending ? ' disabled' : ''}>${navIcon('plus')}Nova conversa</button>`}
  ${links(sidebarItems)}</nav></aside>` : ''}`;
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

function renderMessage(message, { fresh = false, visualState = null, initials = '' } = {}) {
  const role = message.role === 'USER' ? 'Você' : 'Jup';
  const klass = message.role === 'USER' ? 'conversation-message--user' : 'conversation-message--jup';
  const emote = message.thinking ? 'thinking' : visualState ?? message.visual_state ?? visualStateFromUi({ backendStatus: message.status, failed: message.failed });
  const context = message.context ? [message.context.system, message.context.next_step].filter(Boolean).map(escapeHtml).join(' · ') : '';
  return `<article class="conversation-message ${klass}${message.thinking ? ' conversation-message--thinking' : ''}${fresh ? ' is-new' : ''}">
    ${message.role === 'JUP' ? renderJupVisual({ state: emote, compact: true }) : ''}
    <div class="message-content"><div class="message-author"><strong>${role}</strong>${message.sentAt ? `<time datetime="${escapeHtml(message.sentAt)}">${escapeHtml(new Date(message.sentAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }))}</time>` : ''}</div>
    <div class="message-bubble"${fresh && message.role === 'JUP' && !message.thinking && !message.failed ? ' data-reveal-response' : ''}>${message.thinking ? `<div class="processing" role="status" aria-label="Jup está pensando"><strong>Pensando<span class="thinking-dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span></strong><p class="processing-activity">${escapeHtml(message.activity || 'Buscando contexto')}</p></div>` : message.failed ? `<p class="message-error" role="alert">${escapeHtml(message.text)}</p>` : message.role === 'JUP' ? renderApprovedKnowledgeBody({ text: message.text, procedureUrl: message.procedure_url, knowledgeId: message.knowledge_id, article: message.article }) : renderMessageBody(message.text)}
    ${message.role === 'JUP' ? renderSupportHandoff(message.support_handoff) : ''}
    ${message.role === 'JUP' && message.requestCta === 'REQUESTS' ? '<a class="button button--secondary message-request-cta" href="/requests" data-route="requests">Ver minhas solicitações</a>' : ''}
    ${context ? `<div class="request-context">${context}</div>` : ''}</div></div>
    ${message.role === 'USER' && initials ? `<span class="message-user-avatar" aria-hidden="true">${escapeHtml(initials)}</span>` : ''}
  </article>`;
}

function renderChatWelcome(leaving, draft = '', identity = {}) {
  const listening = Boolean(String(draft).trim());
  const firstName = String(identity.name || '').trim().split(/\s+/)[0];
  return `<div class="chat-welcome${leaving ? ' chat-welcome--leaving' : ''}" data-listening="${listening}"${leaving ? ' aria-hidden="true"' : ''}>
    <div class="chat-welcome-avatar-stack" aria-live="polite">
      <div class="chat-welcome-avatar-state chat-welcome-avatar-state--idle" data-welcome-state="idle" aria-hidden="${listening}">${renderJupVisual({ state: 'idle' })}</div>
      <div class="chat-welcome-avatar-state chat-welcome-avatar-state--listening" data-welcome-state="listening" aria-hidden="${!listening}">${renderJupVisual({ state: 'listening' })}</div>
    </div>
    <h1>Olá${firstName ? `, <strong>${escapeHtml(firstName)}</strong>` : ''}! Como posso ajudar?</h1>
    <p class="chat-welcome-tagline">Seu assistente virtual, sempre pronto para ajudar</p>
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
          ${loading ? renderMessage({ role: 'JUP', thinking: true, activity: processingActivity || 'Entendendo sua solicitação' }, { fresh: true }) : ''}
          ${messageError ? renderMessage({ role: 'JUP', text: messageError, failed: true }, { fresh: true }) : ''}
          <div class="conversation-end" aria-hidden="true"></div></div>
          <button class="scroll-bottom" type="button" data-action="scroll-bottom" hidden aria-label="Voltar à última mensagem">Última mensagem ↓</button>
          <form id="jup-form" class="composer" aria-label="Enviar mensagem ao Jup" aria-busy="${loading}">
            ${commandMenuOpen && /^\/\S*$/.test(draft) ? '<div class="composer-command-menu" data-command-menu role="listbox" aria-label="Comandos"><button type="button" data-command="/solicitacoes" role="option" aria-label="/solicitacoes. Ver minhas solicitações e seus status"><strong>/solicitacoes</strong><span>Ver minhas solicitações e seus status</span></button></div>' : ''}
            <div class="composer-input-row"><span class="composer-leading-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17.5V7.8A2.8 2.8 0 0 1 6.8 5h10.4A2.8 2.8 0 0 1 20 7.8v6.4a2.8 2.8 0 0 1-2.8 2.8H9l-5 3v-2.5Z"/><path d="M8 9.5h8M8 13h5"/></svg></span><label class="sr-only" for="jup-message">Mensagem</label><textarea id="jup-message" name="message" rows="1" maxlength="3000" aria-describedby="composer-hint" placeholder="Digite sua mensagem aqui..."${loading ? ' disabled' : ''}>${escapeHtml(draft)}</textarea></div>
            <div class="composer-actions"><span id="composer-hint" class="composer-hint">Enter para enviar · Shift+Enter para nova linha</span><button class="button button--primary composer-send" type="submit" aria-label="Enviar mensagem"${loading ? ' disabled' : ''}><span class="sr-only">${loading ? 'Aguarde...' : 'Enviar'}</span>${navIcon('send')}</button></div>
          </form>
        </div></div>
        ${renderChatSupportRail()}
      </div>
    </div>
  </section>`;
}

export function renderRequestList(items = [], selectedId = null) {
  return renderTrackingWorkspace(items, selectedId);
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
  return `<section class="handoff-inbox" aria-label="Encaminhamentos recebidos"><h2>Encaminhados pelo Jup</h2>${items.map(item => `<article class="operation-detail"><header class="operation-detail-header"><div><p>${escapeHtml(item.handoff_id)}</p><h2>${escapeHtml(item.system)} · ${escapeHtml(item.requester?.name)}</h2></div><span class="status-badge">Encaminhado para suporte</span></header><div class="evidence-grid"><section><span>Responsável</span><strong>${escapeHtml(item.technician?.name)}</strong></section><section><span>Área do solicitante</span><strong>${escapeHtml(item.requester?.area)}</strong></section><section><span>Routing</span><strong>${escapeHtml(item.capability)}</strong></section></div><h3>Resumo técnico</h3><p class="technical-summary">${escapeHtml(item.technical_summary)}</p><details class="handoff-conversation"><summary>Ver contexto da conversa</summary>${(item.source_conversation ?? []).map(entry => `<p><strong>${entry.role === 'USER' ? 'Solicitante' : 'Jup'}:</strong> ${escapeHtml(entry.text)}</p>`).join('')}</details></article>`).join('')}</section>`;
}

function renderChatSupportRail() {
  return `<aside class="chat-support-rail" aria-label="Apoio ao atendimento"><section class="related-articles"><header><span class="support-icon">${navIcon('solutions')}</span><h2>Artigos relacionados</h2><a href="/" data-route="solutions">Ver todos →</a></header><a class="related-article" href="/solucoes/KB-SYN-FAQ-CDM-REQUEST-001" data-solution-link><span>Como solicitar acesso ao CDM</span><span aria-hidden="true">›</span></a>${['Como entrar no CDM depois da aprovação', 'Redefinir sua senha', 'Erro de login no CDM'].map(title => `<div class="related-article related-article--example" aria-disabled="true"><span>${title}</span><small>Exemplo</small></div>`).join('')}</section><section class="support-assistance"><div><span class="support-icon">${navIcon('support')}</span><div><h2>Ainda precisa de ajuda?</h2><p>Conte ao Jup o que aconteceu para iniciar seu atendimento.</p></div></div><a class="button button--secondary" href="/jup?draft=Preciso%20de%20ajuda%20com%20um%20sistema." data-route="jup">${navIcon('jup')}Solicitar atendimento</a></section></aside>`;
}
