import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { renderJupWorkspace } from '../src/components.mjs';

const PASSWORD_RESET_URL = 'https://mysignins.microsoft.com/security-info/password/change';

const PROCEDURE_TEXT = `Vamos redefinir sua senha do Microsoft 365.

1. Acesse a página de redefinição de senha da Microsoft.
2. Informe seu e-mail corporativo e conclua a verificação exibida na tela.
3. Clique em Avançar.
4. Escolha um dos métodos de confirmação de identidade disponíveis para sua conta.
5. Confirme sua identidade usando o código ou a solicitação recebida.
6. Crie uma nova senha seguindo os requisitos apresentados.
7. Depois da alteração, tente entrar novamente no Outlook, Teams e demais aplicativos.

Faça esse procedimento e me diga se conseguiu acessar.`;

test('approved Microsoft 365 procedure renders semantic numbered steps and only the fixed safe link', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [
      {
        role: 'JUP',
        text: PROCEDURE_TEXT,
        procedure_url: PASSWORD_RESET_URL,
      },
    ],
  });

  assert.match(html, /<ol class="procedure-steps">/);
  assert.equal((html.match(/<li>/g) ?? []).length, 7);
  assert.match(html, /Acesse a página de redefinição de senha da Microsoft/);
  assert.ok(html.includes(`href="${PASSWORD_RESET_URL}"`));
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test('an arbitrary procedure URL is never turned into a link', () => {
  const malicious = 'https://example.invalid/reset?next=<script>alert(1)</script>';
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [
      {
        role: 'JUP',
        text: 'Orientação aprovada.',
        procedure_url: malicious,
      },
    ],
  });

  assert.doesNotMatch(html, /href="https:\/\/example\.invalid/);
  assert.doesNotMatch(html, /<script>/);
});

test('support handoff renders only safe backend fields and escapes the technical summary', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [
      {
        role: 'JUP',
        text: 'Encaminhei o atendimento para o especialista de Microsoft 365.',
        support_handoff: {
          handoff_id: 'DEMO-M365-HANDOFF-001',
          capability: 'MICROSOFT_365_SUPPORT_REQUEST',
          technician: {
            technician_id: 'TECH-M365',
            username: 'tecnico.m365',
            name: 'Técnico Microsoft 365',
            email: 'tecnico.m365@example.invalid',
          },
          requester: {
            username: 'pedro.miranda',
            name: 'Pedro Miranda',
            email: 'pedro.miranda@example.invalid',
            area: 'Revenda - Matriz',
          },
          technical_summary:
            'Falha após procedimento. <img src=x onerror=alert(1)> https://evil.invalid/x',
          source_conversation: [{ role: 'USER', text: 'segredo interno' }],
        },
      },
    ],
  });

  assert.match(html, /Encaminhamento técnico/);
  assert.match(html, /Técnico Microsoft 365/);
  assert.match(html, /Pedro Miranda/);
  assert.match(html, /Revenda - Matriz/);
  assert.match(html, /Falha após procedimento/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /href="https:\/\/evil\.invalid/);

  for (const forbidden of [
    'MICROSOFT_365_SUPPORT_REQUEST',
    'TECH-M365',
    'tecnico.m365@example.invalid',
    'pedro.miranda@example.invalid',
    'segredo interno',
  ]) {
    assert.doesNotMatch(html, new RegExp(forbidden.replaceAll('.', '\\\\.')));
  }
});

test('submitMessage keeps backend procedure and handoff metadata with the assistant message', () => {
  const source = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');

  assert.match(source, /procedure_url:\s*result\.procedure_url/);
  assert.match(source, /support_handoff:\s*result\.support_handoff/);
  assert.doesNotMatch(source, /\.\.\.result/);
});
