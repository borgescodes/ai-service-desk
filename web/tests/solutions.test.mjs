import test from 'node:test';
import assert from 'node:assert/strict';
import { faqSearchPath, renderSolutionsHome } from '../src/solutions.mjs';

const groups = [
  {
    key: 'cigam',
    label: 'CIGAM',
    items: [
      {
        knowledge_id: 'KB-CIGAM',
        title: 'CIGAM não abre',
        question: 'Não consigo acessar o CIGAM.',
        system: 'CIGAM',
        category: 'CIGAM',
      },
    ],
  },
];

test('solutions home is task-first and does not contain marketing copy', () => {
  const html = renderSolutionsHome({ groups, searchQuery: '', searchResults: null, searching: false });
  assert.match(html, /Como podemos ajudar\?/);
  assert.match(html, /Pesquise por um problema, sistema ou dúvida/);
  assert.match(html, /CIGAM não abre/);
  assert.match(html, /Não encontrou o que precisa\?/);
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
  assert.match(html, /data-knowledge-id="KB-CIGAM"/);
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
