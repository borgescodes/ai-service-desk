export function createInitialState() {
  return {
    identityId: null,
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
