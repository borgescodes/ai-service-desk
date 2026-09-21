export function createInitialState() {
  return {
    identityId: null,
    faqGroups: [],
    faqSearchQuery: '',
    faqSearchResults: null,
    faqSearching: false,
    faqSearchError: null,
    faqContext: null,
    identities: [],
    routeData: {},
    transientError: null,
    pendingAction: null,
    requesterChatState: {},
  };
}

const CHAT_PRESENTATION_FIELDS = [
  'messages',
  'understood',
  'lastBackendStatus',
  'composerDraft',
  'faqContext',
];

function chatPresentation(state) {
  const presentation = Object.fromEntries(CHAT_PRESENTATION_FIELDS.map(field => [field, state[field]]));
  if (state.pendingAction === 'message') presentation.messages = state.messages.slice(0, -1);
  return presentation;
}

export function activateIdentity(state, identity) {
  const current = state.identities.find(item => item.identity_id === state.identityId);
  const requesterChatState = current?.role === 'REQUESTER'
    ? { ...(state.requesterChatState ?? {}), [current.identity_id]: chatPresentation(state) }
    : (state.requesterChatState ?? {});
  const selected = selectIdentity({ ...state, requesterChatState }, identity.identity_id);
  if (identity.role !== 'REQUESTER') return resetConversation(selected);
  const saved = requesterChatState[identity.identity_id];
  if (!saved) return resetConversation(selected);
  return {
    ...selected,
    ...saved,
    composerFocused: false,
    commandMenuOpen: /^\/\S*$/.test(saved.composerDraft ?? ''),
  };
}

export function clearRequesterChatState(state, identityId) {
  const { [identityId]: _discarded, ...requesterChatState } = state.requesterChatState ?? {};
  return { ...state, requesterChatState };
}

export function selectIdentity(state, identityId) {
  return {
    ...state,
    identityId,
    routeData: {},
    transientError: null,
    pendingAction: null,
  };
}

export function resetConversation(state) {
  return { ...state, messages: [], composerDraft: '', composerFocused: false,
    understood: null, lastBackendStatus: null, messageError: null, faqContext: null,
    pendingAction: null, transientError: null };
}

export function personaPath(identity) {
  if (identity?.role === 'REQUESTER') return '/jup';
  return ({ 'pedro-miranda': '/jup', 'tecnico-cdm': '/demo/operacao/cdm',
    'tecnico-m365': '/demo/operacao/m365', 'tecnico-geral': '/demo/operacao/general' })[identity?.identity_id] ?? null;
}

export function corporateEmailFromName(name) {
  const segments = String(name ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR')
    .split(/\s+/)
    .map(segment => segment.replace(/[^a-z0-9]/g, ''))
    .filter(Boolean);
  const local = segments.length > 1 ? `${segments[0]}.${segments.at(-1)}` : segments[0] || 'usuario';
  return `${local.replace(/\.+/g, '.').replace(/^\.|\.$/g, '')}@juparana.com.br`;
}
