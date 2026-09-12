import { renderJupVisual, visualStateFromUi } from './jup_visual.mjs';
import { createFaqSearch, renderSolutionDetail, renderSolutionsHome, renderSolutionsResults } from './solutions.mjs';
import { apiRequest, ApiError } from './api.mjs';
import {
  renderAppHeader,
  renderApprovalQueue,
  renderJupWorkspace,
  renderOperationDetail,
  renderPreventionList,
  renderRequestList,
} from './components.mjs';
import { escapeHtml, renderErrorState, renderUnauthorizedState } from './render.mjs';
import { demoIdentityForPath, resolveRoute, routeParams } from './router.mjs';
import { createInitialState, selectIdentity } from './state.mjs';

const app = document.querySelector('#app');
let state = {
  ...createInitialState(),
  route: resolveRoute(window.location.pathname),
  composerFocused: false,
  lastBackendStatus: null,
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

function operationTabs() {
  return `<nav class="operations-tabs" aria-label="Operação">
    <a href="/operations" data-route-link="approvals"${state.route === 'approvals' ? ' aria-current="page"' : ''}>Pendências</a>
    <a href="/operations/prevention" data-route-link="prevention"${state.route === 'prevention' ? ' aria-current="page"' : ''}>Prevenção</a>
  </nav>`;
}

function renderRoute() {
  if (state.transientError) {
    return state.transientError.kind === 'unauthorized'
      ? renderUnauthorizedState(state.transientError.message)
      : renderErrorState(state.transientError.message);
  }
  if (state.loading && !state.routeData.loaded) {
    return `<section class="state-panel" role="status" aria-live="polite"><div><strong>Carregando</strong><p>Buscando o estado atual no backend.</p></div></section>`;
  }

  if (state.route === 'solution') return renderSolutionDetail(state.routeData.detail);
  if (state.route === 'solutions') return renderSolutionsHome(faqOptions());

  if (state.route === 'jup') {
    return renderJupWorkspace({
      identity: selectedIdentity() ?? {},
      sourceContext: state.faqContext,
      visualState: visualStateFromUi({ pending: state.pendingAction === 'message', backendStatus: state.lastBackendStatus, focused: state.composerFocused }),
      messages: state.messages,
      understood: state.understood,
      loading: state.pendingAction === 'message',
    });
  }

  if (state.route === 'requests') {
    return `${pageHeading('Solicitações', 'Acompanhe somente os estados registrados pelo backend e o histórico real de cada solicitação.')}${renderRequestList(state.routeData.items ?? [])}`;
  }

  if (state.route === 'approvals') {
    const items = state.routeData.items ?? [];
    const selected = state.routeData.selected ?? items.find((item) => item.request_id === state.selectedRequestId) ?? items[0] ?? null;
    return `${pageHeading('Operação', 'Revise contexto, policy e routing antes de agir. A decisão continua sendo validada pelo backend.')}${operationTabs()}<div class="operation-split"><section aria-label="Fila de pendências">${renderApprovalQueue(items)}</section><section aria-label="Detalhe da pendência">${renderOperationDetail(selected, state)}</section></div>`;
  }

  const prevention = state.routeData.items ?? [];
  const selected = state.routeData.selected ?? prevention.find((item) => item.opportunity_id === state.selectedOpportunityId) ?? null;
  const detail = selected
    ? `<aside class="operation-detail prevention-detail"><header class="operation-detail-header"><div><p>${escapeHtml(selected.opportunity_id)}</p><h2>${escapeHtml(selected.category_label)}</h2></div></header><div class="evidence-grid"><section><span>Sistema</span><strong>${escapeHtml(selected.system)}</strong></section><section><span>Intent</span><strong>${escapeHtml(selected.intent)}</strong></section><section><span>Área</span><strong>${escapeHtml(selected.area || 'Não informada')}</strong></section><section><span>Ocorrências</span><strong>${escapeHtml(selected.occurrence_count)}</strong></section></div><p>${escapeHtml(selected.explanation)}</p>${selected.reason_codes?.length ? `<p><strong>Evidências:</strong> ${selected.reason_codes.map(escapeHtml).join(', ')}</p>` : ''}</aside>`
    : '';
  return `${pageHeading('Prevenção', 'Padrões recorrentes identificados pelo engine F11, apresentados sem recalcular categorias no navegador.')}${operationTabs()}${renderPreventionList(prevention)}${detail}`;
}

function render() {
  app.innerHTML = `${renderAppHeader({
    activeRoute: state.route,
    operational: ['approvals', 'prevention'].includes(state.route),
  })}<main id="main-content" class="main-content" tabindex="-1">${renderRoute()}</main>`;
  app.setAttribute('aria-busy', String(state.loading));
  bindInteractions();
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
  const desiredIdentityId = demoIdentityForPath(window.location.pathname);
  if (!state.identities.some((item) => item.identity_id === desiredIdentityId)) {
    throw new Error('Identidade de demonstração esperada não está disponível.');
  }
  if (state.identityId !== desiredIdentityId) {
    state = { ...selectIdentity(state, desiredIdentityId), messages: [], understood: null };
  }
}

async function loadRoute() {
  faqSearch.cancel();
  state.faqSearching = false;
  state = { ...state, transientError: null, loading: true, routeData: {} };
  render();
  try {
    syncRouteIdentity();
    if (state.route === 'solutions') {
      const payload = await apiRequest('/api/faq');
      state.faqGroups = payload.groups ?? [];
      state.routeData = { loaded: true };
    } else if (state.route === 'solution') {
      const { knowledgeId } = routeParams(window.location.pathname);
      const detail = await apiRequest(`/api/faq/${encodeURIComponent(knowledgeId)}`);
      state.routeData = { loaded: true, detail };
    } else if (state.route === 'jup') {
      state.faqContext = null;
      const sourceId = new URLSearchParams(window.location.search).get('from');
      if (sourceId) {
        try {
          const detail = await apiRequest(`/api/faq/${encodeURIComponent(sourceId)}`);
          state.faqContext = { knowledge_id: detail.knowledge_id, title: detail.title };
        } catch { /* Context is optional; an unavailable article must not block chat. */ }
      }
      state.routeData = { loaded: true };
    } else if (state.route === 'requests') {
      state.routeData = { items: await apiRequest('/api/requests', { identityId: state.identityId }), loaded: true };
    } else if (state.route === 'approvals') {
      const items = await apiRequest('/api/operations/approvals', { identityId: state.identityId });
      state.selectedRequestId = items[0]?.request_id ?? null;
      state.routeData = { items, selected: items[0] ?? null, loaded: true };
    } else if (state.route === 'prevention') {
      const items = await apiRequest('/api/operations/prevention', { identityId: state.identityId });
      state.routeData = { items, loaded: true };
    } else {
      state.routeData = { loaded: true };
    }
  } catch (error) {
    state.transientError = friendlyError(error);
  } finally {
    state.loading = false;
    render();
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

async function submitMessage(form) {
  const field = form.querySelector('#jup-message');
  const message = field?.value?.trim();
  if (!message || state.pendingAction) return;

  state.messages = [...state.messages, { role: 'USER', text: message }];
  state.lastBackendStatus = null;
  state.composerFocused = false;
  state.pendingAction = 'message';
  state.transientError = null;
  render();

  try {
    const result = await apiRequest('/api/jup/messages', {
      method: 'POST',
      identityId: state.identityId,
      body: { message },
    });
    state.lastBackendStatus = result.status;
    if (typeof result.assistant_message !== 'string' || !result.assistant_message.trim()) {
      throw new Error('Resposta conversacional ausente.');
    }
    if (result.request_id) {
      const detail = await apiRequest(`/api/requests/${encodeURIComponent(result.request_id)}`, {
        identityId: state.identityId,
      });
      state.understood = understoodFromRequest(detail);
    } else {
      state.understood = null;
    }
    state.messages = [
      ...state.messages,
      {
        role: 'JUP',
        text: result.assistant_message,
        procedure_url: result.procedure_url,
        support_handoff: result.support_handoff,
      },
    ];
  } catch (error) {
    state.transientError = friendlyError(error);
  } finally {
    state.pendingAction = null;
    render();
  }
}

async function selectApproval(requestId) {
  try {
    const selected = await apiRequest(
      `/api/operations/approvals/${encodeURIComponent(requestId)}`,
      { identityId: state.identityId },
    );
    state.selectedRequestId = requestId;
    state.routeData = { ...state.routeData, selected };
    render();
  } catch (error) {
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

  state.pendingAction = action;
  render();
  try {
    const final = await apiRequest(
      `/api/requests/${encodeURIComponent(item.request_id)}/${action === 'approve' ? 'approve' : 'reject'}`,
      {
        method: 'POST',
        identityId: state.identityId,
        body: { expected_version: item.version },
      },
    );
    const items = await apiRequest('/api/operations/approvals', {
      identityId: state.identityId,
    });
    state.routeData = { items, selected: final, loaded: true };
    state.selectedRequestId = final.request_id;
  } catch (error) {
    state.transientError = friendlyError(error);
  } finally {
    state.pendingAction = null;
    render();
  }
}

async function selectPrevention(opportunityId) {
  try {
    const selected = await apiRequest(
      `/api/operations/prevention/${encodeURIComponent(opportunityId)}`,
      { identityId: state.identityId },
    );
    state.selectedOpportunityId = opportunityId;
    state.routeData = { ...state.routeData, selected };
    render();
  } catch (error) {
    state.transientError = friendlyError(error);
    render();
  }
}

function faqOptions() {
  return { groups: state.faqGroups, searchQuery: state.faqSearchQuery,
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
    results.querySelector('[data-action="retry-search"]')?.addEventListener('click', () => faqSearch.input(state.faqSearchQuery));
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

function bindInteractions() {
  bindRouteLinks(app);
  app.querySelector('#faq-search')?.addEventListener('input', (event) => {
    state.faqSearchQuery = event.target.value;
    faqSearch.input(state.faqSearchQuery);
  });

  app.querySelector('#jup-form')?.addEventListener('submit', (event) => {
    event.preventDefault();
    void submitMessage(event.currentTarget);
  });
  for (const eventName of ['focus', 'blur']) {
    app.querySelector('#jup-message')?.addEventListener(eventName, () => {
      state.composerFocused = eventName === 'focus';
      const container = app.querySelector('.jup-welcome .jup-avatar, .conversation-visual .jup-avatar');
      if (container) container.outerHTML = renderJupVisual({
        state: visualStateFromUi({ pending: state.pendingAction === 'message', backendStatus: state.lastBackendStatus, focused: state.composerFocused }),
        compact: state.messages.length > 0,
      });
    });
  }
  app.querySelector('#jup-message')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
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
