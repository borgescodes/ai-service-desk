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
  };
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
    'tecnico-m365': '/demo/operacao/m365', 'tecnico-geral': '/demo/operacao/prevention' })[identity?.identity_id] ?? null;
}
