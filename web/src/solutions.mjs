import { navIcon } from './icons.mjs';
import { APPROVED_PROCEDURE_URL, renderApprovedKnowledgeBody } from './knowledge_content.mjs';
import { renderJupVisual } from './jup_visual.mjs';
import { escapeHtml } from './render.mjs';
import { routePath } from './router.mjs';

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
  return `${routePath('jup')}?draft=${encodeURIComponent(String(text ?? '').slice(0, 3000))}`;
}

export function renderDemoScenarios() {
  return `<aside class="demo-scenarios" aria-labelledby="demo-title"><div class="demo-scenarios__eyebrow">Comece por um exemplo</div><h2 id="demo-title">Experimente com o Jup</h2><ul>${DEMO_PROMPTS.map(prompt => `<li><a href="${draftPath(prompt)}" data-route="jup"><span>${escapeHtml(prompt)}</span>${navIcon('arrow-right')}</a></li>`).join('')}</ul></aside>`;
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

const FUNCTIONAL_ARTICLES = Object.freeze({
  'KB-SYN-FAQ-CDM-REQUEST-001': { category: 'acessos-rotinas', symbol: 'cdm-simbol.svg', intro: 'Siga as orientações abaixo para solicitar seu acesso.', officialLabel: 'Abrir o CDM' },
  'KB-SYN-M365-PASSWORD-001': { category: 'impressao-office-aplicativos', icon: 'key-round', intro: 'Siga as orientações aprovadas para redefinir sua senha.', officialLabel: 'Abrir página oficial da Microsoft' },
});

const VISUAL_EXAMPLES = Object.freeze([
  ['acessos-rotinas', 'Acessos e rotinas', 'key-round', ['Como solicitar acesso ao CDM', 'Como entrar no CDM depois da aprovação', 'Como acompanhar uma solicitação feita pelo Jup', 'Como pedir acesso a um sistema corporativo']],
  ['erros-sistemas', 'Erros em sistemas', 'circle-alert', ['Sistema não abre ou fecha sozinho', 'O CIGAM apresenta erro ao iniciar', 'Sistema web fica em tela branca', 'O que informar ao suporte quando uma tela apresenta erro', 'O sistema apresentou erro ao salvar uma operação']],
  ['impressao-office-aplicativos', 'Impressão, Office e aplicativos', 'printer', ['Impressora aparece offline', 'Outlook não envia ou recebe mensagens', 'Teams está sem áudio ou microfone', 'Aplicativo do Office pede autenticação repetidamente']],
  ['rede-internet', 'Rede e internet', 'wifi', ['Estou conectado ao Wi-Fi, mas sem internet', 'Computador conectado por cabo está sem rede', 'Apenas um site ou sistema não abre', 'Como identificar se o problema está na internet ou no sistema']],
]);

function arrowIcon() {
  return `<span class="solution-arrow" aria-hidden="true">${navIcon('arrow-right')}</span>`;
}

function visualArticle(article) {
  const metadata = article.knowledge_id && FUNCTIONAL_ARTICLES[article.knowledge_id];
  if (metadata) {
    const icon = metadata.symbol ? `<img src="/assets/brand/${metadata.symbol}" alt="" width="24" height="24">` : navIcon(metadata.icon);
    return `<a class="faq-item faq-item--available" href="${routePath('solution', { knowledgeId: article.knowledge_id })}" data-solution-link data-knowledge-id="${article.knowledge_id}"><span class="faq-item-icon">${icon}</span><strong>${escapeHtml(article.title)}</strong>${arrowIcon()}</a>`;
  }
  return `<div class="faq-item faq-item--catalog" role="link" aria-disabled="true"><span class="faq-item-icon">${navIcon('book-open-text')}</span><span>${escapeHtml(article.title)}</span>${arrowIcon()}</div>`;
}

function renderFaqHelpStrip() {
  return `<aside class="faq-help-strip">${renderJupVisual({ state: 'idle' })}<h2>Ainda não encontrou a resposta?</h2><a class="button button--primary" href="${routePath('jup')}" data-route="jup">${navIcon('message-circle')}Falar com o Jup</a></aside>`;
}

function renderFaqDirectory(content, countLabel = '') {
  return `${countLabel ? `<p class="directory-count">${countLabel}</p>` : ''}<div class="faq-directory">${content}</div>${renderFaqHelpStrip()}`;
}

export function renderSolutionsResults({ groups = [], searchQuery = '', category = '', searchResults = null, searching = false, error = null }) {
  if (error) {
    return renderFaqDirectory(`<div class="faq-empty"><p role="alert">${escapeHtml(error)}</p><button class="button button--secondary" data-action="retry-search">Tentar novamente</button></div>`);
  }
  if (searching) {
    return renderFaqDirectory('<div class="search-loading" role="status"><p class="search-status">Buscando soluções...</p></div>');
  }
  const query = searchQuery.trim();
  const normalize = text => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  const available = query ? searchResults ?? [] : groups.flatMap(group => group.items ?? []);
  const categories = VISUAL_EXAMPLES.filter(([key]) => !category || category === key)
    .map(([key, label, icon, titles]) => {
      const functional = available.filter(article => FUNCTIONAL_ARTICLES[article.knowledge_id]?.category === key);
      const functionalTitles = new Set(functional.filter(article => article.title).map(article => normalize(article.title)));
      const catalog = titles.map(title => ({ title })).filter(article => !functionalTitles.has(normalize(article.title)) && (!query || normalize(article.title).includes(normalize(query))));
      return [key, label, icon, [...functional, ...catalog]];
    }).filter(([, , , articles]) => articles.length);
  const count = categories.reduce((sum, [, , , articles]) => sum + articles.length, 0);
  if (!count) {
    return renderFaqDirectory(`<div class="faq-empty"><h2>Nenhuma solução encontrada.</h2><p>Tente outras palavras ou conte sua dúvida ao Jup.</p><a class="button button--primary" href="${draftPath(searchQuery)}" data-route="jup">${navIcon('message-circle')}Falar com o Jup</a></div>`);
  }
  const countLabel = `${query && available.length ? `${available.length} ${available.length === 1 ? 'solução encontrada' : 'soluções encontradas'} · ` : ''}${count} ${count === 1 ? 'artigo' : 'artigos'}`;
  const details = categories.map(([key, label, icon, articles], index) => `<details class="faq-category"${index === 0 ? ' open' : ''}><summary><strong>${label}</strong><small>${articles.length} artigos</small>${navIcon('chevron-down')}</summary><div class="faq-category-panel"><div class="faq-category-items">${articles.map(visualArticle).join('')}</div></div></details>`).join('');
  return renderFaqDirectory(details, countLabel);
}

export function renderSolutionsHome(options = {}) {
  return `<section class="solutions-home" aria-labelledby="solutions-title">
    <div class="faq-hero"><h1 id="solutions-title">Central de Suporte<span>.</span></h1>
      <form id="faq-search-form" class="faq-search-control"><label class="sr-only" for="faq-search">O que você precisa resolver?</label><div class="search-field">${navIcon('search')}<input id="faq-search" type="search" autocomplete="off" maxlength="300" placeholder="Busque por sistema, erro ou assunto" value="${escapeHtml(options.searchQuery || '')}" aria-controls="faq-results"><button class="search-shortcut" type="submit">Buscar ${navIcon('arrow-right')}</button></div></form>
      <nav class="faq-category-pills" aria-label="Categorias de ajuda">${[['', 'Todos'], ...FAQ_TOPICS].map(([key, label]) => `<button type="button" data-category="${key}" aria-pressed="${(options.category || '') === key}" aria-controls="faq-results">${label}</button>`).join('')}</nav>
    </div>
    <section class="help-articles" aria-label="Artigos por categoria"><div id="faq-results" aria-live="polite" aria-busy="${Boolean(options.searching)}">${renderSolutionsResults(options)}</div></section>
  </section>`;
}

export function renderSolutionDetail(detail) {
  const metadata = FUNCTIONAL_ARTICLES[detail.knowledge_id];
  const officialUrl = detail.procedure_url === APPROVED_PROCEDURE_URL || (detail.knowledge_id === 'KB-SYN-FAQ-CDM-REQUEST-001' && detail.procedure_url === 'https://cdm.juparana.com.br/') ? detail.procedure_url : null;
  const icon = metadata?.symbol ? `<img class="article-symbol" src="/assets/brand/${metadata.symbol}" width="64" height="64" alt="${escapeHtml(detail.system || '')}">` : `<span class="article-symbol">${navIcon(metadata?.icon || 'book-open-text')}</span>`;
  return `<article class="solution-detail">
    <nav class="breadcrumb" aria-label="Localização"><a href="${routePath('solutions')}" data-route="solutions">Central de Suporte</a><span aria-hidden="true">/</span><span>${escapeHtml(detail.category || '')}</span><span aria-hidden="true">/</span><span>${escapeHtml(detail.system || '')}</span></nav>
    <header class="solution-article-header">${icon}<p class="solution-category">${escapeHtml(detail.category || '')} · ${escapeHtml(detail.system || '')}</p><h1>${escapeHtml(detail.title)}</h1><p>${metadata?.intro || 'Siga as orientações abaixo.'}</p>${officialUrl ? `<a class="button button--primary" href="${officialUrl}" target="_blank" rel="noopener noreferrer">${metadata?.officialLabel || 'Abrir referência oficial ↗'}</a>` : ''}</header>
    <div class="knowledge-body">${renderApprovedKnowledgeBody({ text: detail.answer, procedureUrl: detail.procedure_url, knowledgeId: detail.knowledge_id })}</div>
    <aside class="security-note"><strong>Cuide da sua segurança</strong><p>Não compartilhe senhas ou códigos de verificação. Use sempre o endereço oficial do sistema.</p></aside>
    <footer class="solution-outcome"><div><h2>Ainda precisa de ajuda?</h2><p>Continue o atendimento com o Jup.</p></div><a class="button button--primary" href="${routePath('jup')}?from=${encodeURIComponent(detail.knowledge_id)}" data-route="jup">Falar com o Jup ${navIcon('arrow-right')}</a></footer>
  </article>`;
}
