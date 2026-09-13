import { renderApprovedKnowledgeBody } from './knowledge_content.mjs';
import { escapeHtml } from './render.mjs';

export const FAQ_TOPICS = Object.freeze([
  ['acessos-rotinas', 'Acessos e rotinas'],
  ['erros-sistemas', 'Erros em sistemas'],
  ['impressao-office-aplicativos', 'Impressão, Office e aplicativos'],
  ['rede-internet', 'Rede e internet'],
]);

export const DEMO_PROMPTS = Object.freeze([
  'Preciso de acesso ao CDM', 'Meu Outlook não está sincronizando',
  'A impressora aparece offline', 'O CIGAM apresenta erro quando tento abrir',
  'Estou conectado ao Wi-Fi, mas sem internet', 'Não consigo entrar no Microsoft 365',
]);

export function draftPath(text) {
  return `/jup?draft=${encodeURIComponent(String(text ?? '').slice(0, 3000))}`;
}

export function renderDemoScenarios() {
  return `<aside class="demo-scenarios" aria-labelledby="demo-title"><h2 id="demo-title">Experimente com o Jup</h2><p>Escolha uma situação para começar. Você pode editar antes de enviar.</p><ul>${DEMO_PROMPTS.map(prompt => `<li><a href="${draftPath(prompt)}" data-route="jup"><span>${escapeHtml(prompt)}</span><span aria-hidden="true">↗</span></a></li>`).join('')}</ul><small>Exemplos para conversar, sem solução pré-definida.</small></aside>`;
}

export function faqSearchPath(query, category = '') {
  return `/api/faq/search?q=${encodeURIComponent(String(query ?? '').trim())}${category ? `&category=${encodeURIComponent(category)}` : ''}`;
}

export function createFaqSearch({ request, update }) {
  let timer, version = 0;
  const cancel = () => { clearTimeout(timer); version += 1; };
  return {
    cancel,
    input(query, category = '') {
      cancel();
      const current = version;
      if (!query.trim() && !category) { update({ searchResults: null, searching: false, error: null }); return; }
      update({ searching: true, searchResults: null, error: null });
      timer = setTimeout(async () => {
        try {
          const payload = await request(faqSearchPath(query, category));
          if (current === version) update({ searchResults: payload.items ?? [], searching: false, error: null });
        } catch {
          if (current === version) update({ searchResults: null, searching: false, error: 'Não foi possível buscar. Tente novamente.' });
        }
      }, 140);
    },
  };
}

function solutionLink(item) {
  return `<a href="/solucoes/${encodeURIComponent(item.knowledge_id)}" data-solution-link data-knowledge-id="${escapeHtml(item.knowledge_id)}"><span>${escapeHtml(item.title)}</span><span class="solution-arrow" aria-hidden="true">→</span></a>`;
}

export function renderSolutionsResults({ groups = [], searchQuery = '', category = '', searchResults = null, searching = false, error = null }) {
  if (error) return `<p role="alert">${escapeHtml(error)}</p><button class="button button--secondary" data-action="retry-search">Tentar novamente</button>`;
  if (searching) return '<div class="search-loading" role="status"><p class="search-status">Buscando soluções...</p><span></span><span></span><span></span></div>';
  if (searchQuery.trim() || category) {
    const items = searchResults ?? [];
    if (!items.length) return `<div class="faq-empty"><h2>Nenhuma solução encontrada.</h2><p>Tente outras palavras ou outro tópico. Se preferir, leve sua dúvida para a conversa.</p><a class="button button--primary" href="${draftPath(searchQuery)}" data-route="jup">Perguntar ao Jup →</a></div>`;
    return `<p class="search-status">${items.length === 1 ? '1 solução encontrada' : `${items.length} soluções encontradas`}</p><ul class="solution-results">${items.map(item => `<li>${solutionLink(item)}<small>${escapeHtml(item.category)}</small></li>`).join('')}</ul>`;
  }
  return `<div class="solution-groups">${groups.map(group => `<section class="solution-group"><h2>${escapeHtml(group.label)}</h2><ul>${group.items.map(item => `<li>${solutionLink(item)}</li>`).join('')}</ul></section>`).join('')}</div>`;
}

export function renderSolutionsHome(options = {}) {
  return `<section class="solutions-home" aria-labelledby="solutions-title">
    <div class="help-intro"><div class="help-title"><h1 id="solutions-title">Como podemos ajudar?</h1><p>Da primeira tarefa ao fim do expediente.<br>Encontre ajuda para seguir com o seu trabalho.</p></div><div class="field-lines" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
    <div class="faq-search-control"><label for="faq-search">O que você precisa resolver?</label><div class="search-field"><span aria-hidden="true" class="search-icon"></span><input id="faq-search" type="search" autocomplete="off" maxlength="300" placeholder="Pesquise por um problema, sistema ou dúvida..." value="${escapeHtml(options.searchQuery)}" aria-controls="faq-results"></div></div></div>
    <div class="faq-topics" role="group" aria-label="Filtrar por tópico">${[['', 'Todos os tópicos'], ...FAQ_TOPICS].map(([key, label]) => `<button type="button" data-category="${key}" aria-pressed="${(options.category || '') === key}" aria-controls="faq-results">${label}</button>`).join('')}</div>
    <div class="help-content"><section class="help-articles" aria-label="Soluções aprovadas"><div class="results-heading"><h2>Orientações para sua rotina</h2><span>FAQ de demonstração · conteúdo aprovado</span></div><div id="faq-results" aria-live="polite" aria-busy="${Boolean(options.searching)}">${renderSolutionsResults(options)}</div></section>${renderDemoScenarios()}</div>
    <aside class="jup-strip"><div><h2>Não encontrou o que precisa?</h2><p>Conte ao Jup. A conversa começa pelo seu problema.</p></div><a href="/jup" data-route="jup">Falar com o Jup <span aria-hidden="true">→</span></a></aside>
  </section>`;
}

export function renderSolutionDetail(detail) {
  return `<article class="solution-detail">
    <a class="back-link" href="/" data-route="solutions">← Todas as soluções</a>
    <header><p class="solution-category">${escapeHtml(detail.category || detail.system)}</p><h1>${escapeHtml(detail.title)}</h1></header>
    <div class="knowledge-body">${renderApprovedKnowledgeBody({ text: detail.answer, procedureUrl: detail.procedure_url, knowledgeId: detail.knowledge_id })}</div>
    ${detail.provenance ? `<p class="knowledge-provenance">Conteúdo de demonstração · ${escapeHtml(detail.provenance.source)} · ${escapeHtml(detail.provenance.status)} · versão ${escapeHtml(detail.provenance.version)}<br><small>${escapeHtml(detail.knowledge_id)}</small></p>` : ''}
    <footer class="solution-outcome"><h2>Resolveu?</h2><div><a class="button button--secondary" href="/" data-route="solutions">Sim</a><a class="button button--primary" href="/jup?from=${encodeURIComponent(detail.knowledge_id)}" data-route="jup">Ainda preciso de ajuda →</a></div></footer>
  </article>`;
}
