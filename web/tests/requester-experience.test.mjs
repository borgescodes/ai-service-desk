import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');

test('public identity is route controlled instead of a visible persisted selector', () => {
  assert.doesNotMatch(appSource, /jup-demo-identity/);
  assert.doesNotMatch(appSource, /#demo-identity/);
});

import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';

test('public header contains only requester navigation', () => {
  const html = renderAppHeader({ activeRoute: 'solutions', operational: false });
  assert.match(html, /Jup Resolve/);
  assert.match(html, />Soluções</);
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
  assert.match(html, /Como posso ajudar\?/);
  assert.match(html, /Descreva o que aconteceu/);
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
