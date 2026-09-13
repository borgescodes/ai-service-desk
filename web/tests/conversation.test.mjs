import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { renderJupWorkspace } from '../src/components.mjs';


test('assistant messages render multiple paragraphs semantically and escaped', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [
      {
        role: 'JUP',
        text: 'Primeiro parágrafo com <script>.\n\nSegundo parágrafo.',
      },
    ],
  });

  assert.match(html, /<p>Primeiro parágrafo com &lt;script&gt;\.<\/p>/);
  assert.match(html, /<p>Segundo parágrafo\.<\/p>/);
  assert.doesNotMatch(html, /<script>/);
});


test('submitMessage renders backend assistant_message instead of inventing domain copy', () => {
  const source = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');

  assert.match(source, /assistant_message/);
  assert.doesNotMatch(
    source,
    /Contexto recebido\. Continue descrevendo o que você precisa\./,
  );
  assert.doesNotMatch(source, /Solicitação \$\{detail\.request_id\} criada\./);
});
