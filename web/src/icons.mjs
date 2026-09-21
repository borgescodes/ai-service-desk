const ICONS = Object.freeze({
  search: 'bxs-search', key: 'bxs-key', 'key-round': 'bxs-key',
  errors: 'bxs-error-circle', 'circle-alert': 'bxs-error-circle', printer: 'bxs-printer',
  wifi: 'bxs-wifi', support: 'bxs-headphone', headset: 'bxs-headphone', send: 'bxs-send',
  plus: 'bx-plus', solutions: 'bxs-book-open', 'book-open-text': 'bxs-book-open',
  jup: 'bxs-message-rounded-dots', 'message-circle': 'bxs-message-rounded-dots',
  requests: 'bxs-receipt', 'clipboard-list': 'bxs-receipt', approvals: 'bxs-inbox', inbox: 'bxs-inbox',
  'panel-top': 'bxs-inbox', prevention: 'bxs-bar-chart-alt-2',
  'chart-no-axes-column-increasing': 'bxs-bar-chart-alt-2', chevron: 'bx-chevron-down',
  'chevron-down': 'bx-chevron-down', 'arrow-right': 'bx-right-arrow-alt', clock: 'bxs-time-five',
  check: 'bxs-check-circle', warning: 'bxs-error', user: 'bxs-user', request: 'bxs-file',
  pending: 'bxs-time', rejected: 'bxs-x-circle', blocked: 'bxs-lock-alt', sync: 'bx-sync',
  failed: 'bxs-error-circle', dot: 'bxs-circle',
  microsoft: 'bxl-microsoft', 'technician-cdm': 'bxs-user-badge',
  'technician-m365': 'bxs-user-detail', 'technician-general': 'bxs-user-voice',
});

const SVG_ICONS = Object.freeze({
  'message-circle-dots': '<path d="m12,2C6.49,2,2,6.49,2,12c0,2.12.68,4.19,1.93,5.9l-1.75,2.53c-.21.31-.24.7-.06,1.03.17.33.51.54.89.54h9c5.51,0,10-4.49,10-10S17.51,2,12,2Zm-4,11c-.55,0-1-.45-1-1s.45-1,1-1,1,.45,1,1-.45,1-1,1Zm4,0c-.55,0-1-.45-1-1s.45-1,1-1,1,.45,1,1-.45,1-1,1Zm4,0c-.55,0-1-.45-1-1s.45-1,1-1,1,.45,1,1-.45,1-1,1Z"/>',
  'message-circle-edit': '<path d="m12,2C6.49,2,2,6.49,2,12c0,2.12.68,4.19,1.93,5.9l-1.75,2.53c-.21.31-.24.7-.06,1.03.17.33.51.54.89.54h9c5.51,0,10-4.49,10-10S17.51,2,12,2Zm1,11l-3,3h-2s0-2,0-2l3-3,1.15-1.15,2,2-1.15,1.15Zm1.85-1.85l-2-2,1.15-1.15,1,1,1,1-1.15,1.15Z"/>',
});

export function navIcon(name) {
  if (SVG_ICONS[name]) return `<svg class="boxicon nav-icon" data-boxicon="${name}" viewBox="0 0 24 24" aria-hidden="true">${SVG_ICONS[name]}</svg>`;
  return `<i class="bx ${ICONS[name] || ICONS.solutions} nav-icon" aria-hidden="true"></i>`;
}
