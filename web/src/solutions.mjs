import { escapeHtml } from './render.mjs';

export function faqSearchPath(query) {
  return `/api/faq/search?q=${encodeURIComponent(String(query ?? '').trim())}`;
}

export function createFaqSearch({ request, update }) {
  let timer, version = 0;
  const cancel = () => { clearTimeout(timer); version += 1; };
  return {
    cancel,
    input(query) {
      cancel();
      const current = version;
      if (!query.trim()) { update({ searchResults: null, searching: false, error: null }); return; }
      update({ searching: true, searchResults: null, error: null });
      timer = setTimeout(async () => {
        try {
          const payload = await request(faqSearchPath(query));
          if (current === version) update({ searchResults: payload.items ?? [], searching: false, error: null });
        } catch {
          if (current === version) update({ searchResults: null, searching: false, error: 'Não foi possível buscar. Tente novamente.' });
        }
      }, 140);
    },
  };
}

function solutionLink(item) {
  return `<a href="/solucoes/${encodeURIComponent(item.knowledge_id)}" data-solution-link data-knowledge-id="${escapeHtml(item.knowledge_id)}">${escapeHtml(item.title)}</a>`;
}

export function renderSolutionsResults({ groups = [], searchQuery = '', searchResults = null, searching = false, error = null }) {
  if (error) return `<p role="alert">${escapeHtml(error)}</p><button class="button button--secondary" data-action="retry-search">Tentar novamente</button>`;
  if (searching) return '<p class="search-status">Buscando soluções...</p>';
  if (searchQuery.trim()) {
    const items = searchResults ?? [];
    if (!items.length) return '<p>Nenhuma solução encontrada.</p><a href="/jup" data-route="jup">Falar com o Jup →</a>';
    return `<p class="search-status">${items.length === 1 ? '1 solução encontrada' : `${items.length} soluções encontradas`}</p><ul class="solution-results">${items.map(item => `<li><span>${escapeHtml(item.system)}</span>${solutionLink(item)}<small>${escapeHtml(item.category)}</small></li>`).join('')}</ul>`;
  }
  return `<div class="solution-groups">${groups.map(group => `<section class="solution-group"><h2>${escapeHtml(group.label)}</h2><ul>${group.items.map(item => `<li>${solutionLink(item)}</li>`).join('')}</ul></section>`).join('')}</div>`;
}

export function renderSolutionsHome(options = {}) {
  return `<section class="solutions-home" aria-labelledby="solutions-title">
    <h1 id="solutions-title">Como podemos ajudar?</h1>
    <div class="faq-search-control"><label class="sr-only" for="faq-search">Pesquisar soluções</label><input id="faq-search" type="search" autocomplete="off" maxlength="300" placeholder="Pesquise por um problema, sistema ou dúvida..." value="${escapeHtml(options.searchQuery)}" aria-controls="faq-results"></div>
    <div id="faq-results" aria-live="polite" aria-busy="${Boolean(options.searching)}">${renderSolutionsResults(options)}</div>
    <aside class="jup-strip"><p>Não encontrou o que precisa?</p><a href="/jup" data-route="jup">Falar com o Jup <span aria-hidden="true">→</span></a></aside>
  </section>`;
}
