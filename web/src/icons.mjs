const ICONS = Object.freeze({
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  'key-round': '<path d="m15.5 7.5 2.8-2.8"/><circle cx="8.5" cy="15.5" r="5.5"/><path d="m14 10 1.5-1.5 2 2L20 8"/>',
  'circle-alert': '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
  printer: '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect width="12" height="8" x="6" y="14"/>',
  wifi: '<path d="M12 20h.01M2 8.82a15 15 0 0 1 20 0M5 12.86a10 10 0 0 1 14 0M8.5 16.43a5 5 0 0 1 7 0"/>',
  headset: '<path d="M3 14h3a2 2 0 0 1 2 2v5H6a3 3 0 0 1-3-3v-4ZM21 14h-3a2 2 0 0 0-2 2v5h2a3 3 0 0 0 3-3v-4ZM3 14v-2a9 9 0 0 1 18 0v2"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  plus: '<path d="M5 12h14M12 5v14"/>',
  'book-open-text': '<path d="M12 7v14M3 18a1 1 0 0 1-1-1V5a2 2 0 0 1 2-2h5a3 3 0 0 1 3 3v15a3 3 0 0 0-3-3ZM21 18a1 1 0 0 0 1-1V5a2 2 0 0 0-2-2h-5a3 3 0 0 0-3 3v15a3 3 0 0 1 3-3Z"/><path d="M6 8h2M6 12h2M16 8h2M16 12h2"/>',
  'message-circle': '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"/><path d="M8 9h8M8 13h5"/>',
  'clipboard-list': '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M12 11h4M12 16h4M8 11h.01M8 16h.01"/>',
  'panel-top': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/>',
  'chart-no-axes-column-increasing': '<path d="M5 21v-6M12 21V9M19 21V3"/>',
  'chevron-down': '<path d="m6 9 6 6 6-6"/>',
  'arrow-right': '<path d="M5 12h14M13 6l6 6-6 6"/>',
});

const ALIASES = Object.freeze({
  key: 'key-round',
  errors: 'circle-alert',
  support: 'headset',
  solutions: 'book-open-text',
  jup: 'message-circle',
  requests: 'clipboard-list',
  approvals: 'panel-top',
  prevention: 'chart-no-axes-column-increasing',
  chevron: 'chevron-down',
});

export function navIcon(name) {
  const canonical = ALIASES[name] ?? (ICONS[name] ? name : 'book-open-text');
  return `<svg class="nav-icon" data-lucide="${canonical}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[canonical]}</svg>`;
}
