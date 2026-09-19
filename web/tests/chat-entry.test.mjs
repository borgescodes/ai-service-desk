import test from 'node:test';
import assert from 'node:assert/strict';
import { renderJupWorkspace } from '../src/components.mjs';
import { resetConversation } from '../src/state.mjs';

test('empty chat welcomes inside the conversation without a synthetic message or fixed hero', () => {
  const html = renderJupWorkspace({ identity: { name: 'Ana da Silva' } });
  assert.match(html, /class="chat-welcome"/);
  assert.match(html, /Olá, <strong>Ana<\/strong>! Como posso ajudar\?/);
  assert.match(html, /Seu assistente virtual, sempre pronto para ajudar/);
  assert.doesNotMatch(html, /conversation-header|conversation-message--jup/);
  assert.match(html, /<textarea[^>]*(?<!disabled)>/);
});

test('first submission animates the welcome out before the first incoming messages', () => {
  const html = renderJupWorkspace({ messages: [{ role: 'USER', text: 'acesso CDM' }], loading: true, animateFrom: 0 });
  assert.match(html, /chat-welcome--leaving/);
  assert.match(html, /aria-hidden="true"[^>]*>[^]*?Como posso ajudar/);
  assert.match(html, /Buscando contexto CDM/);
});

test('ongoing chat does not restore welcome and short replies retain known context', () => {
  const html = renderJupWorkspace({ identity: { name: 'Ana da Silva' }, messages: [{ role: 'USER', text: 'Office não abre' }, { role: 'JUP', text: 'Qual erro?' }, { role: 'USER', text: 'senha' }], loading: true });
  assert.doesNotMatch(html, /chat-welcome/);
  assert.doesNotMatch(html, /Olá, <strong>Ana<\/strong>/);
  assert.match(html, /Buscando contexto 365/);
});

test('processing uses a neutral label for unknown or ambiguous systems', () => {
  for (const text of ['preciso de ajuda', 'CDM e Microsoft 365']) {
    const html = renderJupWorkspace({ messages: [{ role: 'USER', text }], loading: true });
    assert.match(html, /processing-activity">Buscando contexto<\/p>/);
  }
});

test('new conversation returns to welcome and retains existing request data', () => {
  const next = resetConversation({ messages: [{ role: 'USER', text: 'CDM' }], routeData: { items: ['REQ-1'] } });
  assert.match(renderJupWorkspace(next), /class="chat-welcome"/);
  assert.deepEqual(next.routeData.items, ['REQ-1']);
});
