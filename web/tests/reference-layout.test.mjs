import test from 'node:test';
import assert from 'node:assert/strict';
import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';
import { renderSolutionsHome, renderSolutionsResults } from '../src/solutions.mjs';

const groups = [
  { key: 'acessos-rotinas', items: [{ knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001', title: 'Como solicitar acesso ao CDM' }] },
  { key: 'impressao-office-aplicativos', items: [{ knowledge_id: 'KB-SYN-M365-PASSWORD-001', title: 'Redefinir sua senha do Microsoft 365' }] },
];

test('FAQ shares one global navigation with the rest of the product', () => {
  const html = renderAppHeader({ activeRoute: 'solutions' });
  assert.doesNotMatch(html, /app-sidebar/);
  assert.match(html, />Central de Suporte</);
  assert.match(html, />Falar com o Jup</);
  assert.match(html, /href="\/requests"[^>]*>[^]*?Minhas solicitações/);
});

test('chat navigation keeps reset and request tracking in the unified header', () => {
  const html = renderAppHeader({ activeRoute: 'jup' });
  const global = html.split('</header>')[0];
  assert.match(global, /href="\/requests"/);
  assert.match(html, /data-action="new-chat"[^>]*>[^]*?Nova conversa/);
  assert.match(html, /href="\/requests"[^>]*>[^]*?Minhas solicitações/);
  assert.doesNotMatch(html, /Artigos de ajuda/);
});

test('FAQ restores visual categories while the two approved articles are linked', () => {
  const html = renderSolutionsHome({ groups });
  assert.equal((html.match(/class="faq-category"/g) ?? []).length, 4);
  assert.match(html, /data-category="rede-internet"/);
  assert.match(html, /18 artigos/);
  assert.match(html, /Sistema não abre ou fecha sozinho/);
  assert.match(html, /aria-disabled="true"/);
  assert.match(html, /href="\/solucoes\/KB-SYN-M365-PASSWORD-001"/);
  assert.equal((html.match(/data-solution-link/g) ?? []).length, 2);
  assert.match(html, /Ainda não encontrou a resposta/);
});

test('category selection shows only that category with examples remaining inert', () => {
  const html = renderSolutionsResults({ groups, category: 'rede-internet' });
  assert.match(html, /Estou conectado ao Wi-Fi/);
  assert.doesNotMatch(html, /Como solicitar acesso ao CDM|data-solution-link/);
});

test('chat removes the permanent support rail and keeps honest pending feedback', () => {
  const html = renderJupWorkspace({ loading: true });
  assert.doesNotMatch(html, /conversation-header/);
  assert.doesNotMatch(html, /class="chat-support-rail"|Artigos relacionados/);
  assert.match(html, /data-state="thinking"/);
  assert.match(html, /<textarea[^>]*disabled/);
  assert.match(html, /Entendendo sua solicitação/);
});
