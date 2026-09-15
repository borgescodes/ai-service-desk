import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { renderAppHeader } from '../src/components.mjs';
import { renderSolutionsHome } from '../src/solutions.mjs';

const groups = [{ items: [{ knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001' }] }];

test('FAQ categories are independent and the help CTA sits outside the natural category card', () => {
  const html = renderSolutionsHome({ groups, searchQuery: '', searchResults: null, searching: false });
  assert.doesNotMatch(html, /name="support-faq"/);
  assert.doesNotMatch(html, /class="faq-directory-scroll"/);
  assert.match(html, /<\/details><\/div><aside class="faq-help-strip"/);
});

test('FAQ catalog and shell use the shared Lucide icon registry', () => {
  const faq = renderSolutionsHome({ groups, searchQuery: '', searchResults: null, searching: false });
  const header = renderAppHeader({ activeRoute: 'jup', identity: { name: 'Pedro Miranda' } });
  assert.match(faq, /data-lucide="search"/);
  assert.match(faq, /data-lucide="chevron-down"/);
  assert.match(faq, /data-lucide="arrow-right"/);
  assert.match(header, /data-lucide="search"/);
  assert.match(header, /data-lucide="clipboard-list"/);
  assert.match(header, /data-lucide="plus"/);
});

test('utility icon rendering is centralized instead of being defined inside components', () => {
  const components = readFileSync(new URL('../src/components.mjs', import.meta.url), 'utf8');
  const solutions = readFileSync(new URL('../src/solutions.mjs', import.meta.url), 'utf8');
  assert.match(components, /from '\.\/icons\.mjs'/);
  assert.match(solutions, /from '\.\/icons\.mjs'/);
  assert.doesNotMatch(components, /export function navIcon|const paths = \{/);
});

test('FAQ interaction scrolls the page only when needed and does not close sibling categories', () => {
  const polish = readFileSync(new URL('../src/ui-polish.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(polish, /\.faq-directory-scroll/);
  assert.match(polish, /scrollTo\(/);
  assert.match(polish, /prefers-reduced-motion/);
  assert.doesNotMatch(polish, /item\.open\s*=\s*false/);
});

test('FAQ layout grows naturally with a separate CTA, and subtle motion', () => {
  const css = readFileSync(new URL('../src/desktop-responsive.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /\.faq-directory-scroll/);
  assert.match(css, /\.faq-help-strip[^}]*position:\s*relative/);
  assert.match(css, /\.faq-category-panel[^}]*transition:/);
  assert.match(css, /\.faq-category\[open\][^{]*>\s*summary/);
  assert.match(css, /prefers-reduced-motion/);
});


test('FAQ category headings omit decorative icons and keep expansion chevrons', () => {
  const html = renderSolutionsHome({ groups });
  const headings = [...html.matchAll(/<summary>(.*?)<\/summary>/gs)].map(match => match[1]);
  assert.equal(headings.length, 4);
  for (const heading of headings) {
    assert.doesNotMatch(heading, /faq-category-icon|key-round|circle-alert|printer|wifi/);
    assert.equal((heading.match(/data-lucide=/g) || []).length, 1);
    assert.match(heading, /chevron-down/);
  }
});
