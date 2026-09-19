import { presentChat, dismissThinking, createWelcomeEntry } from './presentation.mjs';
import { renderJupVisual, visualStateFromUi } from './jup_visual.mjs';
import { captureConversationScroll, restoreConversationScroll } from './conversation.mjs';
import { createFaqSearch, renderSolutionDetail, renderSolutionsHome, renderSolutionsResults } from './solutions.mjs';
import { apiRequest, ApiError } from './api.mjs';
import {
  renderAppHeader,
  renderApprovalQueue,
  renderHandoffs,
  renderJupWorkspace,
  renderOperationDetail,
  renderRequestList,
} from './components.mjs';
import { escapeHtml, renderErrorState, renderUnauthorizedState } from './render.mjs';
import { demoIdentityForPath, resolveRoute, routeParams } from './router.mjs';
import { createInitialState, selectIdentity, resetConversation, personaPath } from './state.mjs';

const app = document.querySelector('#app');
let identityRevision = 0;
let renderedMessageCount = 0;
let finishPresentation = () => {};
const welcomeEntry = createWelcomeEntry();
// IDs only, scoped to the current page session and technician. Details are always reauthorized.
const knownOperationalRequests = new Map();
async function loadOperationalItems(identityId) {
  const pending = await apiRequest('/api/operations/approvals', { identityId });
  const known = knownOperationalRequests.get(identityId) || new Set();
  pending.forEach(item => known.add(item.request_id));
  knownOperationalRequests.set(identityId, known);
  const currentIds = new Set(pending.map(item => item.request_id));
  const previous = await Promise.all([...known].filter(id => !currentIds.has(id)).map(async id => {
    try { return await apiRequest(`/api/operations/approvals/${encodeURIComponent(id)}`, { identityId }); }
    catch (error) {
      if (error instanceof ApiError && [403, 404].includes(error.status)) { known.delete(id); return null; }
      throw error;
    }
  }));
  return [...pending, ...previous.filter(Boolean)];
}
let state = {
  ...createInitialState(),
  route: resolveRoute(window.location.pathname),
  composerFocused: false,
  composerDraft: '',
  faqCategory: '',
  lastBackendStatus: null,
  messageError: null,
  identityConfigError: null,
  messages: [],
  understood: null,
  loading: false,
  selectedRequestId: null,
  selectedOpportunityId: null,
};

function selectedIdentity() {
  return state.identities.find((item) => item.identity_id === state.identityId) ?? null;
}

function pageHeading(title, description) {
  return `<div class="page-heading"><div><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p></div></div>`;
}

function operationPath() {
  return state.identityId === 'tecnico-m365' ? '/demo/operacao/m365' : '/demo/operacao/cdm';
}

function renderRoute() {
  if (state.transientError) {
    return state.transientError.kind === 'unauthorized'
      ? renderUnauthorizedState(state.transientError.message)
      : renderErrorState(state.transientError.message);
  }
  if (state.loading && !state.routeData.loaded) {
    return `<section class="state-panel" role="status" aria-live="polite"><div><strong>Carregando</strong><p>Atualizando informações.</p></div></section>`;
  }

  if (state.route === 'solution') return renderSolutionDetail(state.routeData.detail);
  if (state.route === 'solutions') return renderSolutionsHome(faqOptions());

  if (state.route === 'jup') {
    return renderJupWorkspace({
      identity: selectedIdentity() ?? {},
      sourceContext: state.faqContext,
      messageError: state.messageError,
      visualState: state.composerFocused && !state.pendingAction ? 'listening' : null,
      draft: state.composerDraft,
      animateFrom: renderedMessageCount,
      messages: state.messages,
      understood: state.understood,
      loading: state.pendingAction === 'message',
    });
  }

  if (state.route === 'requests') {
    return `${pageHeading('Acompanhar chamados', 'Acompanhe o andamento dos seus atendimentos.')}${renderRequestList(state.routeData.items ?? [], state.selectedRequestId)}`;
  }

  if (state.route === 'approvals') {
    const items = state.routeData.items ?? [];
    const selected = state.routeData.selected ?? items.find((item) => item.request_id === state.selectedRequestId) ?? items[0] ?? null;
    return `${pageHeading('Solicitações recebidas', 'Revise o contexto e dê continuidade ao atendimento.')}<div class="tracking-workspace"><section class="tracking-list" aria-label="Fila de solicitações"><header class="tracking-list-header"><h2>Fila de atendimento</h2><span>${items.length}</span></header>${renderApprovalQueue(items, selected?.request_id)}</section><section aria-label="Detalhe da pendência">${renderOperationDetail(selected, state)}</section></div>${renderHandoffs(state.routeData.handoffs ?? [])}`;
  }

  return '<section class="tracking-empty"><strong>Área não disponível nesta demonstração</strong><p>Use o menu de usuários para acessar uma fila de atendimento.</p></section>';
}

function render() {
  finishPresentation();
  const scroll = captureConversationScroll(app.querySelector('.conversation-thread'));
  const focused = document.activeElement?.id === 'jup-message';
  app.innerHTML = `${renderAppHeader({
    activeRoute: state.route,
    identities: state.identities, identity: selectedIdentity() ?? {}, pending: state.pendingAction || false,
    operational: ['approvals', 'prevention'].includes(state.route),
    operationPath: operationPath(),
    identityError: state.identityConfigError,
  })}<main id="main-content" class="main-content main-content--${['solutions', 'solution'].includes(state.route) ? 'public' : 'workspace'}" tabindex="-1">${renderRoute()}</main>`;
  app.setAttribute('aria-busy', String(state.loading));
  bindInteractions();
  const hasWelcome = Boolean(app.querySelector('.chat-welcome:not(.chat-welcome--leaving)'));
  finishPresentation = presentChat(app, { welcome: welcomeEntry.update(hasWelcome), followConversation: scroll?.atEnd ?? true, reducedMotion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false });
  renderedMessageCount = state.messages.length;
  restoreConversationScroll(app.querySelector('.conversation-thread'), app.querySelector('[data-action="scroll-bottom"]'), scroll, window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
  if (focused && !state.pendingAction) app.querySelector('#jup-message')?.focus?.({ preventScroll: true });
}

function friendlyError(error) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return {
        kind: 'unauthorized',
        message: 'Identidade de demonstração indisponível. Recarregue a página.',
      };
    }
    if (error.status === 403) {
      return {
        kind: 'unauthorized',
        message: 'Esta identidade não tem acesso a esta operação.',
      };
    }
    if (error.status === 409) {
      return {
        kind: 'error',
        message: 'O estado mudou. Recarregue os dados e tente novamente.',
      };
    }
    return { kind: 'error', message: error.message };
  }
  return {
    kind: 'error',
    message: 'Não foi possível falar com o Jup Resolve. Tente novamente.',
  };
}

function syncRouteIdentity() {
  const routeIdentityId = demoIdentityForPath(window.location.pathname);
  const currentIdentity = selectedIdentity();
  const desiredIdentityId = ['solutions', 'solution', 'jup', 'requests'].includes(state.route)
    && currentIdentity?.role === 'REQUESTER'
    ? currentIdentity.identity_id
    : routeIdentityId;
  if (!state.identities.some((item) => item.identity_id === desiredIdentityId)) {
    throw new Error('Identidade de demonstração esperada não está disponível.');
  }
  if (state.identityId !== desiredIdentityId) {
    identityRevision += 1;
    Object.assign(state, selectIdentity(state, desiredIdentityId), {
      messages: [], understood: null, lastBackendStatus: null, composerFocused: false, composerDraft: '', messageError: null,
    });
  }
}

async function loadRoute() {
  faqSearch.cancel();
  state.faqSearching = false;
  state = { ...state, transientError: null, loading: true, routeData: {} };
  const routeState = state;
  render();
  try {
    syncRouteIdentity();
    if (routeState.route === 'solutions') {
      const payload = await apiRequest('/api/faq');
      routeState.faqGroups = payload.groups ?? [];
      routeState.routeData = { loaded: true };
    } else if (routeState.route === 'solution') {
      const { knowledgeId } = routeParams(window.location.pathname);
      const detail = await apiRequest(`/api/faq/${encodeURIComponent(knowledgeId)}`);
      routeState.routeData = { loaded: true, detail };
    } else if (routeState.route === 'jup') {
      routeState.faqContext = null;
      const draft = new URLSearchParams(window.location.search).get('draft');
      if (draft !== null) routeState.composerDraft = draft.slice(0, 3000);
      const sourceId = new URLSearchParams(window.location.search).get('from');
      if (sourceId) {
        try {
          const detail = await apiRequest(`/api/faq/${encodeURIComponent(sourceId)}`);
          routeState.faqContext = { knowledge_id: detail.knowledge_id, title: detail.title };
        } catch { /* Context is optional; an unavailable article must not block chat. */ }
      }
      routeState.routeData = { loaded: true };
    } else if (routeState.route === 'requests') {
      routeState.routeData = { items: await apiRequest('/api/requests', { identityId: routeState.identityId }), loaded: true };
    } else if (routeState.route === 'approvals') {
      const items = await loadOperationalItems(routeState.identityId);
      routeState.selectedRequestId = items[0]?.request_id ?? null;
      const handoffs = await apiRequest('/api/operations/handoffs', { identityId: routeState.identityId });
      routeState.routeData = { items, handoffs, selected: items[0] ?? null, loaded: true };
    } else if (routeState.route === 'prevention') {
      const items = await apiRequest('/api/operations/prevention', { identityId: routeState.identityId });
      routeState.routeData = { items, loaded: true };
    } else {
      routeState.routeData = { loaded: true };
    }
  } catch (error) {
    routeState.transientError = friendlyError(error);
  } finally {
    routeState.loading = false;
    if (routeState === state) {
      render();
      if (state.route === 'solutions' && (state.faqSearchQuery.trim() || state.faqCategory)) faqSearch.input(state.faqSearchQuery, state.faqCategory);
    }
  }
}

async function navigate(path) {
  if (window.location.pathname + window.location.search !== path) window.history.pushState({}, '', path);
  state.route = resolveRoute(window.location.pathname);
  await loadRoute();
  document.querySelector('#main-content')?.focus({ preventScroll: true });
}

function understoodFromRequest(detail) {
  return {
    system: detail.system,
    request: detail.requested_role,
    purpose: detail.purpose,
    confidence: detail.confidence,
    policy: detail.policy?.decision,
    next_step: detail.state_label,
  };
}

function settleSuccessAvatar(message) {
  if (!message || visualStateFromUi({ backendStatus: message.status }) !== 'success') return;
  setTimeout(() => {
    message.visual_state = 'idle';
    if (state.route !== 'jup' || state.messages.at(-1) !== message || state.pendingAction || state.messageError) return;
    const avatars = app.querySelectorAll('.conversation-message--jup > .jup-avatar');
    const avatar = avatars[avatars.length - 1];
    if (avatar) avatar.outerHTML = renderJupVisual({ state: state.composerFocused ? 'listening' : 'idle', compact: true });
  }, 1200);
}

async function submitMessage(form) {
  const field = form.querySelector('#jup-message');
  const message = field?.value?.trim();
  if (!message || state.pendingAction) return;

  const revision = identityRevision;
  const identityId = state.identityId;
  const presentationReady = new Promise(resolve => setTimeout(resolve, 2400));
  state.messages = [...state.messages, { role: 'USER', text: message, sentAt: new Date().toISOString() }];
  state.composerDraft = '';
  state.lastBackendStatus = null;
  state.messageError = null;
  state.composerFocused = false;
  state.pendingAction = 'message';
  state.transientError = null;
  render();

  try {
    const result = await apiRequest('/api/jup/messages', {
      method: 'POST',
      identityId,
      body: { message },
    });
    if (revision !== identityRevision) return;
    state.lastBackendStatus = result.status;
    if (typeof result.assistant_message !== 'string' || !result.assistant_message.trim()) {
      throw new Error('Resposta conversacional ausente.');
    }
    if (result.request_id) {
      const detail = await apiRequest(`/api/requests/${encodeURIComponent(result.request_id)}`, {
        identityId,
      });
      if (revision !== identityRevision) return;
      state.understood = understoodFromRequest(detail);
    } else {
      state.understood = null;
    }
    await presentationReady;
    if (revision !== identityRevision) return;
    await dismissThinking(app, window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
    if (revision !== identityRevision) return;
    state.messages = [
      ...state.messages,
      {
        role: 'JUP',
        sentAt: new Date().toISOString(),
        status: result.status,
        context: state.understood,
        knowledge_id: result.knowledge?.knowledge_id,
        text: result.assistant_message,
        procedure_url: result.procedure_url,
        support_handoff: result.support_handoff,
      },
    ];
  } catch (error) {
    if (revision !== identityRevision) return;
    state.messageError = friendlyError(error).message;
  } finally {
    if (revision === identityRevision) {
      state.pendingAction = null;
      render();
      if (state.route === 'jup') {
        app.querySelector('#jup-message')?.focus?.({ preventScroll: true });
        settleSuccessAvatar(state.messages.at(-1));
      }
    }
  }
}

async function selectApproval(requestId) {
  const requestState = state;
  try {
    const selected = await apiRequest(
      `/api/operations/approvals/${encodeURIComponent(requestId)}`,
      { identityId: state.identityId },
    );
    if (state !== requestState) return;
    state.selectedRequestId = requestId;
    state.routeData = { ...state.routeData, items: (state.routeData.items || []).map(item => item.request_id === selected.request_id ? selected : item), selected };
    render();
  } catch (error) {
    if (state !== requestState) return;
    state.transientError = friendlyError(error);
    render();
  }
}

async function decide(action) {
  const item =
    state.routeData.selected ??
    state.routeData.items?.find(
      (candidate) => candidate.request_id === state.selectedRequestId,
    ) ??
    state.routeData.items?.[0];
  if (!item || item.state !== 'PENDING_APPROVAL' || state.pendingAction) return;
  if (
    action === 'reject' &&
    !window.confirm('Rejeitar esta solicitação? A execução não será iniciada.')
  ) {
    return;
  }

  const requestState = state;
  const identityId = state.identityId;
  state.pendingAction = action;
  render();
  try {
    const final = await apiRequest(
      `/api/requests/${encodeURIComponent(item.request_id)}/${action === 'approve' ? 'approve' : 'reject'}`,
      {
        method: 'POST',
        identityId,
        body: { expected_version: item.version },
      },
    );
    if (state !== requestState) return;
    const items = await loadOperationalItems(identityId);
    if (state !== requestState) return;
    state.routeData = { ...state.routeData, items: [...items.filter(item => item.request_id !== final.request_id), final], selected: final, loaded: true };
    state.selectedRequestId = final.request_id;
  } catch (error) {
    if (state !== requestState) return;
    state.transientError = friendlyError(error);
  } finally {
    if (state === requestState) {
      state.pendingAction = null;
      render();
    }
  }
}

async function selectPrevention(opportunityId) {
  const requestState = state;
  try {
    const selected = await apiRequest(
      `/api/operations/prevention/${encodeURIComponent(opportunityId)}`,
      { identityId: state.identityId },
    );
    if (state !== requestState) return;
    state.selectedOpportunityId = opportunityId;
    state.routeData = { ...state.routeData, selected };
    render();
  } catch (error) {
    if (state !== requestState) return;
    state.transientError = friendlyError(error);
    render();
  }
}

function faqOptions() {
  return { groups: state.faqGroups, searchQuery: state.faqSearchQuery,
    category: state.faqCategory,
    searchResults: state.faqSearchResults, searching: state.faqSearching, error: state.faqSearchError };
}

const faqSearch = createFaqSearch({
  request: apiRequest,
  update({ searchResults, searching, error }) {
    state.faqSearchResults = searchResults;
    state.faqSearching = searching;
    state.faqSearchError = error;
    const results = app.querySelector('#faq-results');
    if (!results || state.route !== 'solutions') return;
    results.innerHTML = renderSolutionsResults(faqOptions());
    results.setAttribute('aria-busy', String(searching));
    bindRouteLinks(results);
    results.querySelector('[data-action="retry-search"]')?.addEventListener('click', () => faqSearch.input(state.faqSearchQuery, state.faqCategory));
  },
});

function bindRouteLinks(root) {
  root.querySelectorAll('a[data-route], a[data-route-link], a[data-solution-link]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      void navigate(link.getAttribute('href'));
    });
  });
}

async function newChat() {
  if (state.pendingAction) return;
  const revision = identityRevision;
  state.pendingAction = 'reset';
  render();
  try {
    await apiRequest('/api/jup/conversation/reset', { method: 'POST', identityId: state.identityId });
    if (revision !== identityRevision) return;
    identityRevision += 1;
    state = resetConversation(state);
    renderedMessageCount = 0;
    welcomeEntry.reset();
    await navigate('/jup');
  } catch (error) {
    if (revision !== identityRevision) return;
    state.pendingAction = null;
    state.messageError = friendlyError(error).message;
    state.transientError = state.route === 'jup' ? null : friendlyError(error);
    render();
  }
}

async function configureDemoIdentity(form) {
  if (state.pendingAction) return;
  const formData = new FormData(form);
  const body = Object.fromEntries(['name', 'email', 'job_title', 'area'].map(key => [key, formData.get(key)]));
  state.pendingAction = 'identity';
  state.identityConfigError = null;
  render();
  try {
    const configured = await apiRequest('/api/session/identities', { method: 'POST', body });
    identityRevision += 1;
    state = resetConversation(selectIdentity({
      ...state,
      identities: [...state.identities, configured],
    }, configured.identity_id));
    state.identityConfigError = null;
    renderedMessageCount = 0;
    welcomeEntry.reset();
    await navigate('/jup');
  } catch (error) {
    state.pendingAction = null;
    state.identityConfigError = friendlyError(error).message;
    render();
  }
}

function bindInteractions() {
  bindRouteLinks(app);
  app.querySelector('[data-action="new-chat"]')?.addEventListener('click', newChat);
  app.querySelector('#demo-identity-form')?.addEventListener('submit', event => {
    event.preventDefault();
    void configureDemoIdentity(event.currentTarget);
  });
  app.querySelectorAll('[data-persona]').forEach(button => {
    button.addEventListener('click', async () => {
      if (state.pendingAction) return;
      const identity = state.identities.find(item => item.identity_id === button.dataset.persona);
      const path = personaPath(identity);
      if (!path) return;
      if (identity?.role === 'REQUESTER' && identity.identity_id !== state.identityId) {
        identityRevision += 1;
        state = resetConversation(selectIdentity(state, identity.identity_id));
        renderedMessageCount = 0;
        welcomeEntry.reset();
      }
      await navigate(path);
    });
  });
  app.querySelectorAll('[data-category]').forEach(button => {
    button.addEventListener('click', () => {
      state.faqCategory = button.dataset.category;
      app.querySelectorAll('[data-category]').forEach(topic => topic.setAttribute('aria-pressed', String(topic.dataset.category === state.faqCategory)));
      faqSearch.input(state.faqSearchQuery, state.faqCategory);
    });
  });
  app.querySelector('#faq-search-form')?.addEventListener('submit', event => {
    event.preventDefault();
    faqSearch.input(state.faqSearchQuery, state.faqCategory);
  });
  app.querySelector('#faq-search')?.addEventListener('input', (event) => {
    state.faqSearchQuery = event.target.value;
    faqSearch.input(state.faqSearchQuery, state.faqCategory);
  });
  app.querySelector('#jup-message')?.addEventListener('input', event => { state.composerDraft = event.target.value; });

  app.querySelector('#jup-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    void submitMessage(event.currentTarget);
  });
  for (const eventName of ['focus', 'blur']) {
    app.querySelector('#jup-message')?.addEventListener(eventName, () => {
      state.composerFocused = eventName === 'focus';
      const avatars = app.querySelectorAll('.conversation-message--jup > .jup-avatar');
      const container = avatars[avatars.length - 1];
      if (container) container.outerHTML = renderJupVisual({
        state: visualStateFromUi({ pending: state.pendingAction === 'message', backendStatus: state.messages.at(-1)?.visual_state === 'idle' ? null : state.lastBackendStatus, focused: state.composerFocused, failed: Boolean(state.messageError) }),
        compact: true,
      });
    });
  }
  app.querySelector('#jup-message')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  });

  app.querySelectorAll('[data-request-select]').forEach(button => {
    button.addEventListener('click', () => { state.selectedRequestId = button.dataset.requestSelect; render(); });
  });
  app.querySelectorAll('.queue-row[data-request-id]').forEach((button) => {
    button.addEventListener('click', () => void selectApproval(button.dataset.requestId));
  });
  app.querySelector('[data-action="approve"]')?.addEventListener('click', () =>
    void decide('approve'),
  );
  app.querySelector('[data-action="reject"]')?.addEventListener('click', () =>
    void decide('reject'),
  );
  app.querySelectorAll('.text-action[data-opportunity-id]').forEach((button) => {
    button.addEventListener('click', () => void selectPrevention(button.dataset.opportunityId));
  });
  app.querySelector('[data-action="retry"]')?.addEventListener('click', () => void loadRoute());
}

window.addEventListener('popstate', () => {
  state.route = resolveRoute(window.location.pathname);
  void loadRoute();
});

async function bootstrap() {
  try {
    const identities = await apiRequest('/api/session/identities');
    state.identities = identities;
    await loadRoute();
  } catch (error) {
    state.transientError = friendlyError(error);
    state.loading = false;
    state.routeData = { loaded: true };
    render();
  }
}

void bootstrap();
