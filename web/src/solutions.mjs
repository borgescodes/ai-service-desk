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

const TOPIC_PRESENTATION = Object.freeze({
  'acessos-rotinas': ['access', 'Acessos, permissões e rotinas para continuar o trabalho.'],
  'erros-sistemas': ['errors', 'Falhas, mensagens de erro e comportamentos inesperados.'],
  'impressao-office-aplicativos': ['apps', 'Office, impressão e aplicativos usados no dia a dia.'],
  'rede-internet': ['network', 'Conectividade, Wi-Fi, rede corporativa e acesso web.'],
});

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

function solutionLink(item) {
  return `<a href="/solucoes/${encodeURIComponent(item.knowledge_id)}" data-solution-link data-knowledge-id="${escapeHtml(item.knowledge_id)}"><span>${escapeHtml(item.title)}</span><span class="solution-arrow" aria-hidden="true">→</span></a>`;
}

function topicIcon(name) {
  const paths = {
    access: '<path d="M7.5 10V7.6a4.5 4.5 0 0 1 9 0V10"/><rect x="4.5" y="10" width="15" height="10" rx="2.5"/><path d="M12 14v2.5"/>',
    errors: '<path d="M12 3.5 21 19H3L12 3.5Z"/><path d="M12 9v4.5"/><circle cx="12" cy="16.5" r=".8" fill="currentColor" stroke="none"/>',
    apps: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    network: '<circle cx="5" cy="12" r="2.2"/><circle cx="19" cy="6" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="m7 11 9.8-4.2M7 13l9.8 4.2"/>',
  };
  return `<span class="faq-topic-icon" data-topic-icon="${name}" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name] ?? ''}</svg></span>`;
}

function renderTopicCard([key, label], selectedCategory) {
  const [icon, description] = TOPIC_PRESENTATION[key];
  return `<button class="faq-topic-card" type="button" data-category="${key}" aria-pressed="${selectedCategory === key}" aria-controls="faq-results">${topicIcon(icon)}<span class="faq-topic-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(description)}</span></span><span class="faq-topic-arrow" aria-hidden="true">→</span></button>`;
}

export function renderSolutionsResults({ groups = [], searchQuery = '', category = '', searchResults = null, searching = false, error = null }) {
  if (error) return `<p role="alert">${escapeHtml(error)}</p><button class="button button--secondary" data-action="retry-search">Tentar novamente</button>`;
  if (searching) return '<div class="search-loading" role="status"><p class="search-status">Buscando soluções...</p><span></span><span></span><span></span></div>';
  if (searchQuery.trim() || category) {
    const items = searchResults ?? [];
    if (!items.length) return `<div class="faq-empty"><h2>Nenhuma solução encontrada.</h2><p>Tente outras palavras ou outro tópico. Se preferir, leve sua dúvida para a conversa.</p><a class="button button--primary" href="${draftPath(searchQuery)}" data-route="jup">Perguntar ao Jup →</a></div>`;
    return `<p class="search-status">${items.length === 1 ? '1 solução encontrada' : `${items.length} soluções encontradas`}</p><ul class="solution-results">${items.map(item => `<li>${solutionLink(item)}<small>${escapeHtml(item.category)}</small></li>`).join('')}</ul>`;
  }
  return `<div class="solution-groups">${groups.map(group => `<section class="solution-group"><h3>${escapeHtml(group.label)}</h3><ul>${group.items.map(item => `<li>${solutionLink(item)}</li>`).join('')}</ul></section>`).join('')}</div>`;
}

export function renderSolutionsHome(options = {}) {
  const selectedCategory = options.category || '';
  return `<section class="solutions-home" aria-labelledby="solutions-title">
    <div class="help-intro">
      <div class="help-intro__content"><div class="help-kicker"><span aria-hidden="true"></span>Central de suporte Juparanã</div><div class="help-title"><h1 id="solutions-title">Como podemos ajudar?</h1><p>Encontre uma orientação aprovada ou converse com o Jup para seguir com o trabalho.</p></div></div>
      <div class="field-lines" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
      <div class="faq-search-control"><label for="faq-search">O que você precisa resolver?</label><div class="search-field"><span aria-hidden="true" class="search-icon"></span><input id="faq-search" type="search" autocomplete="off" maxlength="300" placeholder="Pesquise por um problema, sistema ou dúvida..." value="${escapeHtml(options.searchQuery)}" aria-controls="faq-results"><span class="search-shortcut" aria-hidden="true">Buscar</span></div></div>
    </div>
    <section class="faq-discovery" aria-labelledby="topic-title"><div class="faq-discovery__heading"><div><span class="section-label">Atalhos por assunto</span><h2 id="topic-title">Comece pelo que está impedindo seu trabalho</h2></div><button class="faq-topic-all" type="button" data-category="" aria-pressed="${selectedCategory === ''}" aria-controls="faq-results">Todos os tópicos <span aria-hidden="true">↗</span></button></div><div class="faq-topic-grid">${FAQ_TOPICS.map(topic => renderTopicCard(topic, selectedCategory)).join('')}</div></section>
    <div class="help-content"><section class="help-articles" aria-label="Soluções aprovadas"><div class="results-heading"><div><span class="section-label">Base aprovada</span><h2>Orientações para sua rotina</h2></div><span>Conteúdo revisado para demonstração</span></div><div id="faq-results" aria-live="polite" aria-busy="${Boolean(options.searching)}">${renderSolutionsResults(options)}</div></section>${renderDemoScenarios()}</div>
    <aside class="jup-spotlight"><div class="jup-spotlight__mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M16 25V13" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M16 16c-5.5 0-8.5-3-8.5-7.5 5.5 0 8.5 3 8.5 7.5Z" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M16 12.5C16 8 19 5 24.5 5c0 4.5-3 7.5-8.5 7.5Z" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M8 26h16" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg></div><div class="jup-spotlight__copy"><span>Jup Resolve</span><h2>Não encontrou o que precisa?</h2><p>Conte o que aconteceu. O Jup começa pelo seu problema e conduz o próximo passo.</p></div><a href="/jup" data-route="jup">Falar com o Jup <span aria-hidden="true">→</span></a></aside>
  </section>`;
}

export function renderSolutionDetail(detail) {
  const category = detail.category || detail.system || 'Orientação';
  const version = detail.provenance?.version;
  return `<article class="solution-detail">
    <a class="back-link" href="/" data-route="solutions"><span aria-hidden="true">←</span> Todas as soluções</a>
    <div class="solution-detail-layout">
      <section class="solution-article-card"><header class="solution-article-header"><div class="solution-article-kicker"><span class="solution-article-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3.5h7l4 4V20a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 20V5A1.5 1.5 0 0 1 7.5 3.5Z"/><path d="M14 3.5V8h4M9 12h6M9 16h5"/></svg></span><div><p class="solution-category">${escapeHtml(category)}</p><span>Orientação para consulta</span></div></div><h1>${escapeHtml(detail.title)}</h1><p class="solution-article-summary">Siga o procedimento abaixo na ordem apresentada.</p></header>
      <div class="knowledge-body">${renderApprovedKnowledgeBody({ text: detail.answer, procedureUrl: detail.procedure_url, knowledgeId: detail.knowledge_id })}</div>
      <footer class="solution-outcome"><div class="solution-outcome-card"><div><span class="section-label">Próximo passo</span><h2>Resolveu?</h2><p>Se a situação continuar, leve o contexto para o Jup e siga com o atendimento.</p></div><div class="solution-outcome-actions"><a class="button button--secondary" href="/" data-route="solutions">Sim</a><a class="button button--primary" href="/jup?from=${encodeURIComponent(detail.knowledge_id)}" data-route="jup">Ainda preciso de ajuda <span aria-hidden="true">→</span></a></div></div></footer></section>
      <aside class="solution-detail-aside"><section class="solution-meta-card"><div class="solution-meta-status"><span aria-hidden="true"></span><strong>Conteúdo aprovado</strong></div><dl><div><dt>Sistema</dt><dd>${escapeHtml(detail.system || 'Corporativo')}</dd></div><div><dt>Categoria</dt><dd>${escapeHtml(category)}</dd></div>${version ? `<div><dt>Versão</dt><dd>${escapeHtml(version)}</dd></div>` : ''}<div><dt>Canal</dt><dd>${detail.procedure_url ? 'Link oficial validado' : 'Orientação interna'}</dd></div></dl>${detail.provenance ? `<p class="knowledge-provenance">Demonstração · ${escapeHtml(detail.provenance.source)} · ${escapeHtml(detail.provenance.status)}<br><small>${escapeHtml(detail.knowledge_id)}</small></p>` : ''}</section><section class="solution-context-card"><span class="solution-context-icon" aria-hidden="true">↳</span><div><strong>Precisa continuar?</strong><p>O Jup pode usar esta orientação como contexto da conversa.</p></div></section></aside>
    </div>
  </article>`;
}
