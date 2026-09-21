import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');

test('configured identity stays backend controlled without browser persistence', () => {
  assert.doesNotMatch(appSource, /jup-demo-identity/);
  assert.doesNotMatch(appSource, /localStorage|sessionStorage/);
  assert.match(appSource, /api\/session\/identities/);
});

import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';

test('public header contains only requester navigation', () => {
  const html = renderAppHeader({ activeRoute: 'solutions', operational: false });
  assert.match(html, /Jup Resolve/);
  assert.match(html, />Central de Suporte</);
  assert.match(html, />Falar com o Jup</);
  assert.doesNotMatch(html, /Identidade demo|Operação|Prevenção|Assistente de IA|Inteligência para/i);
  assert.doesNotMatch(html, /<select/);
});

test('empty Jup workspace is concise and task-first', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [],
    understood: null,
    loading: false,
    sourceContext: null,
  });
  assert.match(html, /Olá, <strong>Pedro<\/strong>! Como posso ajudar\?/);
  assert.match(html, /Digite sua mensagem aqui/);
  assert.doesNotMatch(html, /Eu organizo o contexto|O que entendi|Contexto estruturado/i);
});

test('structured request context is compact instead of a permanent side panel', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [{ role: 'USER', text: 'Preciso de acesso ao CDM.' }],
    understood: { system: 'CDM', request: 'SOLICITANTE', next_step: 'Aguardando aprovação' },
    loading: false,
    sourceContext: null,
  });
  assert.match(html, /CDM/);
  assert.match(html, /Aguardando aprovação/);
  assert.doesNotMatch(html, /understood-panel/);
  assert.doesNotMatch(html, /Policy|Confiança/);
});

const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
test('desktop solutions use editorial columns and a readable article and chat measure', () => {
  assert.match(css, /\.solutions-home\s*\{/);
  assert.match(css, /\.solution-detail\s*\{/);
  assert.match(css, /prefers-reduced-motion/);
  assert.doesNotMatch(css, /linear-gradient|radial-gradient|backdrop-filter/);
});
test('Juparana brand tokens are exact', () => {
  const tokens = readFileSync(new URL('../src/tokens.css', import.meta.url), 'utf8');
  assert.match(tokens, /--color-primary:\s*#45813c/i);
  assert.match(tokens, /--color-accent:\s*#eeb41e/i);
  assert.match(tokens, /--color-canvas:\s*#f6f8f5/i);
});

test('handoff keeps its technical summary behind a native disclosure', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'JUP', text: 'Encaminhado.', support_handoff: { technician: { name: 'Especialista' }, technical_summary: 'Detalhe aprovado para continuidade.' } }] });
  assert.match(html, /<details[^>]*><summary>Resumo para o especialista<\/summary>/);
  assert.doesNotMatch(html, /<details[^>]*open/);
  assert.match(html, /Detalhe aprovado para continuidade/);
});

test('request-status response renders an explicit route CTA without inspecting its text', () => {
  const html = renderJupWorkspace({
    messages: [{ role: 'JUP', text: 'Você tem 1 solicitação em andamento.', requestCta: 'REQUESTS' }],
  });
  assert.match(html, /href="\/requests"[^>]*data-route/);
  assert.match(html, />Ver minhas solicitações</);
});

test('composer renders a compact slash menu only for command search', () => {
  const menu = renderJupWorkspace({ draft: '/', messages: [] });
  const plain = renderJupWorkspace({ draft: 'olá', messages: [] });
  assert.match(menu, /data-command-menu/);
  assert.match(menu, /\/solicitacoes/);
  assert.match(menu, /Ver minhas solicitações e seus status/);
  assert.doesNotMatch(plain, /data-command-menu/);
});
