export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function renderConfidence(confidence = {}) {
  const label = escapeHtml(confidence.label ?? confidence.level ?? 'Não informada');
  const percent = Number.isFinite(confidence.percent) ? ` · ${confidence.percent}%` : '';
  return `<span class="confidence-chip" data-tone="confidence"><span class="confidence-dot" aria-hidden="true"></span>Confiança ${label}${percent}</span>`;
}

const STATUS_ICONS = {
  PENDING_APPROVAL: '○',
  APPROVED: '✓',
  REJECTED: '×',
  DENIED_POLICY: '!',
  EXECUTING: '↻',
  COMPLETED: '✓',
  FAILED: '!',
};

export function renderStatus(item = {}) {
  const state = escapeHtml(item.state ?? 'UNKNOWN');
  const label = escapeHtml(item.state_label ?? ({ PENDING_APPROVAL: 'Aguardando aprovação', APPROVED: 'Aprovada', REJECTED: 'Rejeitada', DENIED_POLICY: 'Não autorizada', EXECUTING: 'Em andamento', COMPLETED: 'Concluída', FAILED: 'Não concluída' })[item.state] ?? 'Estado indisponível');
  const icon = escapeHtml(STATUS_ICONS[item.state] ?? '•');
  return `<span class="status-badge" data-state="${state}"><span aria-hidden="true">${icon}</span><span>${label}</span></span>`;
}

export function renderErrorState(message, retryLabel = 'Tentar novamente') {
  return `<section class="state-panel state-panel--error" role="alert"><div><strong>Não foi possível concluir</strong><p>${escapeHtml(message)}</p></div><button class="button button--secondary" type="button" data-action="retry">${escapeHtml(retryLabel)}</button></section>`;
}

export function renderUnauthorizedState(message) {
  return `<section class="state-panel state-panel--unauthorized" role="alert"><span class="state-mark" aria-hidden="true">!</span><div><strong>Perfil sem acesso</strong><p>${escapeHtml(message)}</p><p><a href="/" data-route="solutions">Voltar para Soluções</a></p></div></section>`;
}

export function renderEmptyState(title, message) {
  return `<section class="state-panel state-panel--empty"><span class="state-mark" aria-hidden="true">○</span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(message)}</p></div></section>`;
}

export function renderPrimaryNavigation(activeRoute, identity = {}) {
  const items = [
    ['jup', '/jup', 'Jup'],
    ['requests', '/requests', 'Solicitações'],
  ];
  if (identity.can_operate === true) items.push(['approvals', '/operations', 'Operação']);
  return `<nav class="primary-nav" aria-label="Navegação principal">${items
    .map(([route, href, label]) => {
      const current = activeRoute === route || (activeRoute === 'prevention' && route === 'approvals');
      return `<a href="${href}" data-route="${route}"${current ? ' aria-current="page"' : ''}>${label}</a>`;
    })
    .join('')}</nav>`;
}

// Fixed timezone and month names avoid host locale and clock dependencies.
export function formatTimestamp(value) {
  if (!value) return 'Data indisponível';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return 'Data indisponível';
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(date);
  const get = name => parts.find(part => part.type === name)?.value;
  const months = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  return `${get('day')} ${months[Number(get('month')) - 1]} · ${get('hour')}:${get('minute')}`;
}
