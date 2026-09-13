import {
  escapeHtml,
  renderConfidence,
  renderEmptyState,
  renderPrimaryNavigation,
  renderStatus,
} from './render.mjs';

const APPROVED_PROCEDURE_URL = 'https://mysignins.microsoft.com/security-info/password/change';

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
  return `<span class="jup-avatar${compact ? ' jup-avatar--compact' : ''}" aria-hidden="true"><span>J</span><i></i></span>`;
}

export function renderAppHeader({ activeRoute, selectedIdentityId, identities = [] }) {
  const identity = identities.find((item) => item.identity_id === selectedIdentityId) ?? identities[0] ?? {};
  const options = identities
    .map((item) => {
      const selected = item.identity_id === selectedIdentityId ? ' selected' : '';
      return `<option value="${escapeHtml(item.identity_id)}"${selected}>${escapeHtml(item.name)} · ${escapeHtml(item.area)}</option>`;
    })
    .join('');

  return `<header class="app-header">
    <div class="brand-lockup">
      ${renderJupAvatar({ compact: true })}
      <div><strong>Jup Resolve</strong><span>Assistente de IA da Juparanã</span></div>
    </div>
    ${renderPrimaryNavigation(activeRoute, identity)}
    <label class="identity-switcher"><span>Identidade demo</span><select id="demo-identity" aria-label="Selecionar identidade de demonstração">${options}</select></label>
  </header>`;
}

function renderMessageBody(text) {
  return String(text ?? '')
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join('');
}

function renderApprovedProcedure(message) {
  const text = String(message.text ?? '');
  if (message.role !== 'JUP' || message.procedure_url !== APPROVED_PROCEDURE_URL) {
    return renderMessageBody(text);
  }

  const intro = [];
  const steps = [];
  const outro = [];
  let section = 'intro';

  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*\d+\.\s+(.+?)\s*$/);
    if (match) {
      steps.push(match[1]);
      section = 'steps';
      continue;
    }
    if (section === 'steps' && line.trim()) section = 'outro';
    if (section === 'intro') intro.push(line);
    else if (section === 'outro') outro.push(line);
  }

  if (!steps.length) return renderMessageBody(text);

  const items = steps
    .map((step, index) => {
      const content =
        index === 0
          ? `<a href="${APPROVED_PROCEDURE_URL}" target="_blank" rel="noopener noreferrer">${escapeHtml(step)}</a>`
          : escapeHtml(step);
      return `<li>${content}</li>`;
    })
    .join('');

  return `${renderMessageBody(intro.join('\n'))}<div class="approved-procedure"><ol class="procedure-steps">${items}</ol></div>${renderMessageBody(outro.join('\n'))}`;
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
    ${technicalSummary ? `<p class="support-handoff__summary">${escapeHtml(technicalSummary)}</p>` : ''}
  </section>`;
}

function renderMessage(message) {
  const role = message.role === 'USER' ? 'Você' : 'Jup';
  const klass = message.role === 'USER' ? 'conversation-message--user' : 'conversation-message--jup';
  return `<article class="conversation-message ${klass}">
    <div class="message-author">${message.role === 'JUP' ? renderJupAvatar({ compact: true }) : `<span class="user-avatar" aria-hidden="true">${escapeHtml(initials(role))}</span>`}<strong>${role}</strong></div>
    ${message.role === 'JUP' ? renderApprovedProcedure(message) : renderMessageBody(message.text)}
    ${message.role === 'JUP' ? renderSupportHandoff(message.support_handoff) : ''}
  </article>`;
}

function understoodValue(label, value) {
  if (value == null || value === '') return '';
  return `<div class="understood-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

export function renderJupWorkspace({ identity = {}, messages = [], understood = null, loading = false }) {
  const name = identity.name?.split(' ')[0] || 'você';
  const conversation = messages.length
    ? `<div class="conversation-thread">${messages.map(renderMessage).join('')}${loading ? '<div class="thinking" aria-live="polite"><span></span><span></span><span></span><em>Jup está analisando</em></div>' : ''}</div>`
    : `<div class="jup-welcome">
        ${renderJupAvatar()}
        <p class="welcome-kicker">Jup Resolve</p>
        <h1>Olá, ${escapeHtml(name)}. O que você precisa resolver?</h1>
        <p>Explique o que aconteceu ou o que você precisa acessar. Eu organizo o contexto e conduzo a próxima etapa.</p>
      </div>`;

  let understoodPanel = '';
  if (understood) {
    understoodPanel = `<aside class="understood-panel" aria-labelledby="understood-title">
      <div class="understood-heading"><span class="context-spine" aria-hidden="true"></span><div><p>Contexto estruturado</p><h2 id="understood-title">O que entendi</h2></div></div>
      <dl>
        ${understoodValue('Sistema', understood.system)}
        ${understoodValue('Solicitação', understood.request)}
        ${understoodValue('Finalidade', understood.purpose)}
        ${understood.confidence ? `<div class="understood-row"><dt>Confiança</dt><dd>${renderConfidence(understood.confidence)}</dd></div>` : ''}
        ${understoodValue('Policy', understood.policy)}
        ${understoodValue('Próxima etapa', understood.next_step)}
      </dl>
    </aside>`;
  }

  return `<section class="jup-surface">
    <div class="jup-layout"><div class="jup-conversation">${conversation}
      <form id="jup-form" class="composer" aria-label="Enviar mensagem ao Jup">
        <label class="sr-only" for="jup-message">Mensagem</label>
        <textarea id="jup-message" name="message" rows="2" maxlength="3000" placeholder="Ex.: Preciso de acesso ao CDM para solicitar materiais para uma revenda."></textarea>
        <div class="composer-actions"><span>Enter para enviar · Shift+Enter para nova linha</span><button class="button button--primary" type="submit"${loading ? ' disabled' : ''}>Enviar</button></div>
      </form>
    </div>${understoodPanel}</div>
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
