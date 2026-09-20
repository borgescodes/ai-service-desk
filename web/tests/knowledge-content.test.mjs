import test from 'node:test';
import assert from 'node:assert/strict';
import { renderApprovedKnowledgeBody } from '../src/knowledge_content.mjs';

const SAFE_URL = 'https://mysignins.microsoft.com/security-info/password/change';

test('approved Central articles link from guidance without linking arbitrary content', () => {
  const article = { knowledge_id: 'KB-SYN-M365-PASSWORD-001', title: 'Redefinir sua senha do Microsoft 365', provenance: { status: 'APPROVED' } };
  const html = renderApprovedKnowledgeBody({ text: 'Orientação aprovada.', article });
  assert.match(html, /href="\/solucoes\/KB-SYN-M365-PASSWORD-001"/);
  assert.match(html, /Redefinir sua senha do Microsoft 365/);
  for (const invalid of [{ ...article, provenance: { status: 'DRAFT' } }, { ...article, knowledge_id: 'https://evil.example' }]) {
    assert.doesNotMatch(renderApprovedKnowledgeBody({ text: 'Orientação', article: invalid }), /<a /);
  }
});

test('approved numbered procedure keeps semantic ordered list and exact safe anchor', () => {
  const html = renderApprovedKnowledgeBody({
    text: 'Procedimento\n\n1. Acesse a página.\n2. Confirme sua identidade.\n\nDepois, teste novamente.',
    procedureUrl: SAFE_URL,
  });
  assert.match(html, /<ol class="procedure-steps">/);
  assert.match(html, new RegExp(`href="${SAFE_URL.replaceAll('/', '\\/')}"`));
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test('arbitrary URL is never promoted to an anchor', () => {
  const html = renderApprovedKnowledgeBody({
    text: '1. Acesse https://evil.example/test',
    procedureUrl: 'https://evil.example/test',
  });
  assert.doesNotMatch(html, /<a /);
  assert.match(html, /https:\/\/evil\.example\/test/);
});

test('knowledge body escapes active markup', () => {
  const html = renderApprovedKnowledgeBody({ text: '<img src=x onerror=alert(1)>', procedureUrl: null });
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});
