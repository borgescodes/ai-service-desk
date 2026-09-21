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
  microsoft: 'bxl-microsoft',
});

export function navIcon(name) {
  return `<i class="bx ${ICONS[name] || ICONS.solutions} nav-icon" aria-hidden="true"></i>`;
}
