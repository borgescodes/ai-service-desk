import test from 'node:test';
import assert from 'node:assert/strict';
import { faqSearchPath, renderSolutionsHome } from '../src/solutions.mjs';

const groups = [
  {
    key: 'cigam',
    label: 'CIGAM',
    items: [
      {
        knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001',
        title: 'Como solicitar acesso ao CDM',
        question: 'Não consigo acessar o CIGAM.',
        system: 'CIGAM',
        category: 'CIGAM',
      },
    ],
  },
];

test('solutions home is task-first and does not contain marketing copy', () => {
  const html = renderSolutionsHome({ groups, searchQuery: '', searchResults: null, searching: false });
  assert.match(html, /Central de <span>Suporte/);
  assert.match(html, /Busque uma dúvida ou sistema/);
  assert.match(html, /Como solicitar acesso ao CDM/);
  assert.match(html, /Precisa de uma mão\?/);
  assert.match(html, /Falar com o Jup/);
  assert.doesNotMatch(html, /Assistente de IA|Inteligência para|transforme|revolucione/i);
});

test('solutions home renders result mode without category card grid', () => {
  const html = renderSolutionsHome({
    groups,
    searchQuery: 'cigam',
    searchResults: groups[0].items,
    searching: false,
  });
  assert.match(html, /1 solução encontrada/);
  assert.match(html, /data-knowledge-id="KB-SYN-FAQ-CDM-REQUEST-001"/);
  assert.doesNotMatch(html, /dashboard-card|metric-card|feature-card/);
});

test('empty search result leads directly to Jup', () => {
  const html = renderSolutionsHome({
    groups,
    searchQuery: 'xyz',
    searchResults: [],
    searching: false,
  });
  assert.match(html, /Nenhuma solução encontrada/);
  assert.match(html, /href="\/jup"/);
});

test('faq search path encodes the query', () => {
  assert.equal(faqSearchPath('cigam azul'), '/api/faq/search?q=cigam%20azul');
});

import { renderSolutionDetail } from '../src/solutions.mjs';

test('solution detail uses literal approved answer and continuation action', () => {
  const html = renderSolutionDetail({
    knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001',
    title: 'Como solicitar acesso ao CDM',
    answer: 'Feche a sessão e tente novamente.',
    system: 'CIGAM',
    category: 'CIGAM',
    procedure_url: null,
  });
  assert.match(html, /Como solicitar acesso ao CDM/);
  assert.match(html, /Feche a sessão e tente novamente\./);
  assert.match(html, /Ainda precisa de ajuda\?/);
  assert.match(html, /Falar com o Jup/);
  assert.match(html, /\/jup\?from=KB-SYN-FAQ-CDM-REQUEST-001/);
});
