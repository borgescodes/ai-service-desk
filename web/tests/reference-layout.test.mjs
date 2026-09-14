import test from 'node:test';
import assert from 'node:assert/strict';
import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';
import { renderSolutionsHome, renderSolutionsResults } from '../src/solutions.mjs';

const groups = [{ key: 'acessos-rotinas', items: [{ knowledge_id: 'KB-SYN-FAQ-CDM-REQUEST-001', title: 'Como solicitar acesso ao CDM' }] }];

test('FAQ has two global destinations and no sidebar or global request link', () => {
  const html = renderAppHeader({ activeRoute: 'solutions' });
  assert.doesNotMatch(html, /app-sidebar|Minhas solicitações|href="\/requests"/);
  assert.match(html, />Soluções</);
  assert.match(html, />Falar com o Jup</);
});

test('chat navigation keeps reset and request tracking in the contextual sidebar', () => {
  const html = renderAppHeader({ activeRoute: 'jup' });
  const global = html.split('</header>')[0];
  assert.doesNotMatch(global, /href="\/requests"/);
  assert.match(html, /data-action="new-chat"[^>]*>[^]*?Nova conversa/);
  assert.match(html, /href="\/requests"[^>]*>[^]*?Acompanhar chamado/);
  assert.doesNotMatch(html, /Artigos de ajuda/);
});

test('FAQ restores visual categories while only the backend CDM article is linked', () => {
  const html = renderSolutionsHome({ groups });
  assert.equal((html.match(/class="faq-category"/g) ?? []).length, 4);
  assert.match(html, /data-category="rede-internet"/);
  assert.match(html, /17 artigos/);
  assert.match(html, /Sistema não abre ou fecha sozinho/);
  assert.match(html, /aria-disabled="true"/);
  assert.equal((html.match(/data-solution-link/g) ?? []).length, 1);
  assert.match(html, /Ainda não encontrou a resposta/);
});

test('category selection shows only that category with examples remaining inert', () => {
  const html = renderSolutionsResults({ groups, category: 'rede-internet' });
  assert.match(html, /Estou conectado ao Wi-Fi/);
  assert.doesNotMatch(html, /Como solicitar acesso ao CDM|data-solution-link/);
});

test('chat preserves right support rail without a permanent hero or changing pending composer', () => {
  const html = renderJupWorkspace({ loading: true });
  assert.doesNotMatch(html, /conversation-header/);
  assert.match(html, /class="chat-support-rail"/);
  assert.match(html, /Artigos relacionados/);
  assert.match(html, /href="\/solucoes\/KB-SYN-FAQ-CDM-REQUEST-001"/);
  assert.match(html, /data-state="thinking"/);
  assert.match(html, /<textarea[^>]*disabled/);
  assert.match(html, /Buscando contexto/);
});
