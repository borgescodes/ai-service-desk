import { renderApprovedKnowledgeBody } from './knowledge_content.mjs';
import { renderJupVisual } from './jup_visual.mjs';
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
  return `<aside class="demo-scenarios" aria-labelledby="demo-title"><div class="demo-scenarios__eyebrow">Comece por um exemplo</div><h2 id="demo-title">Experimente com o Jup</h2><p>Escolha uma situação para começar. Você pode editar antes de enviar.</p><ul>${DEMO_PROMPTS.map(prompt => `<li><a href="${draftPath(prompt)}" data-route="jup"><span>${escapeHtml(prompt)}</span><span aria-hidden="true">↗</span></a></li>`).join('')}</ul><small>Exemplos para conversar, sem solução pré-definida.</small></aside>`;
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

const CDM_FAQ_ID = 'KB-SYN-FAQ-CDM-REQUEST-001';

function solutionLink(item) {
  return `<a class="cdm-result" href="/solucoes/${encodeURIComponent(item.knowledge_id)}" data-solution-link data-knowledge-id="${escapeHtml(item.knowledge_id)}"><span class="cdm-result-symbol"><img src="/assets/brand/cdm-simbol.svg" alt="" width="54" height="54"></span><span><small>Acessos e rotinas · CDM</small><strong>${escapeHtml(item.title)}</strong><span>Consulte o passo a passo para solicitar seu acesso.</span></span><span class="solution-arrow" aria-hidden="true">→</span></a>`;
}

export function renderSolutionsResults({ groups = [], searchQuery = '', category = '', searchResults = null, searching = false, error = null }) {
  if (error) return `<p role="alert">${escapeHtml(error)}</p><button class="button button--secondary" data-action="retry-search">Tentar novamente</button>`;
  if (searching) return '<div class="search-loading" role="status"><p class="search-status">Buscando soluções...</p></div>';
  const searchingQuery = Boolean(searchQuery.trim() || category);
  const items = (searchingQuery ? searchResults ?? [] : groups.flatMap(group => group.items ?? [])).filter(item => item.knowledge_id === CDM_FAQ_ID);
  if (!items.length) return `<div class="faq-empty"><h2>Nenhuma solução encontrada.</h2><p>Tente buscar por CDM ou conte sua dúvida ao Jup.</p><a class="button button--primary" href="${draftPath(searchQuery)}" data-route="jup">Falar com o Jup →</a></div>`;
  return `${searchingQuery ? '<p class="search-status">1 solução encontrada</p>' : ''}<div class="solution-results">${items.map(solutionLink).join('')}</div>`;
}

export function renderSolutionsHome(options = {}) {
  return `<section class="solutions-home" aria-labelledby="solutions-title">
    <div class="faq-hero"><h1 id="solutions-title">Central de <span>Suporte</span></h1><p>Encontre a orientação que precisa para seguir com o seu trabalho.</p>
      <form id="faq-search-form" class="faq-search-control"><label class="sr-only" for="faq-search">O que você precisa resolver?</label><div class="search-field"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></svg><input id="faq-search" type="search" autocomplete="off" maxlength="300" placeholder="Busque uma dúvida ou sistema, como CDM" value="${escapeHtml(options.searchQuery || '')}" aria-controls="faq-results"><button class="search-shortcut" type="submit">Buscar</button></div></form>
    </div>
    <section class="help-articles" aria-label="Orientações disponíveis"><div class="results-heading"><h2>Orientações para sua rotina</h2><span>Acessos e rotinas</span></div><div id="faq-results" aria-live="polite" aria-busy="${Boolean(options.searching)}">${renderSolutionsResults(options)}</div></section>
    <aside class="jup-spotlight">${renderJupVisual({ state: 'idle' })}<div><h2>Precisa de uma mão?</h2><p>Fale com o Jup. Vamos encontrar o próximo passo juntos.</p></div><a class="button button--primary" href="/jup" data-route="jup">Falar com o Jup <span aria-hidden="true">→</span></a></aside>
  </section>`;
}

export function renderSolutionDetail(detail) {
  const officialUrl = detail.knowledge_id === CDM_FAQ_ID && detail.procedure_url === 'https://cdm.juparana.com.br/' ? detail.procedure_url : null;
  return `<article class="solution-detail">
    <nav class="breadcrumb" aria-label="Localização"><a href="/" data-route="solutions">Central de Suporte</a><span aria-hidden="true">/</span><span>CDM</span></nav>
    <header class="solution-article-header"><img class="article-symbol" src="/assets/brand/cdm-simbol.svg" width="64" height="64" alt="CDM"><p class="solution-category">Acessos e rotinas · ${escapeHtml(detail.system || 'CDM')}</p><h1>${escapeHtml(detail.title)}</h1><p>Siga as orientações abaixo para solicitar seu acesso.</p>${officialUrl ? `<a class="button button--primary" href="${officialUrl}" target="_blank" rel="noopener noreferrer">Abrir o CDM ↗</a>` : ''}</header>
    <div class="knowledge-body">${renderApprovedKnowledgeBody({ text: detail.answer, procedureUrl: detail.procedure_url, knowledgeId: detail.knowledge_id })}</div>
    <aside class="security-note"><strong>Cuide da sua segurança</strong><p>Não compartilhe senhas ou códigos de verificação. Use sempre o endereço oficial do sistema.</p></aside>
    <footer class="solution-outcome"><div><h2>Ainda precisa de ajuda?</h2><p>Continue o atendimento com o Jup.</p></div><a class="button button--primary" href="/jup?from=${encodeURIComponent(detail.knowledge_id)}" data-route="jup">Falar com o Jup →</a></footer>
  </article>`;
}
