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
  const label = escapeHtml(item.state_label ?? item.state ?? 'Estado desconhecido');
  const icon = escapeHtml(STATUS_ICONS[item.state] ?? '•');
  return `<span class="status-badge" data-state="${state}"><span aria-hidden="true">${icon}</span><span>${label}</span></span>`;
}

export function renderErrorState(message, retryLabel = 'Tentar novamente') {
  return `<section class="state-panel state-panel--error" role="alert"><div><strong>Não foi possível concluir</strong><p>${escapeHtml(message)}</p></div><button class="button button--secondary" type="button" data-action="retry">${escapeHtml(retryLabel)}</button></section>`;
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
