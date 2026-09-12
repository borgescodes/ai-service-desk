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
