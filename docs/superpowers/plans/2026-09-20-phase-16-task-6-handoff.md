# Phase 16 — Task 6: Continuidade de conversa

## Status

PASS. Execução inline com **GPT-5.6 Terra / Medium**, sem subagents e sem escalada.

## Entrega

- O frontend mantém snapshots de apresentação em memória por `identity_id` de solicitante.
- Cada snapshot contém somente mensagens, entendimento, último status, rascunho e contexto de artigo; não replica requests, handoffs, dados operacionais, loading, ações pendentes ou erros transitórios.
- A troca solicitante → técnico salva o chat do solicitante e limpa a apresentação conversacional da superfície técnica.
- O retorno ao mesmo solicitante restaura o chat sem criar saudação sintética; solicitantes distintos permanecem isolados.
- Nova conversa chama o reset existente no backend e invalida somente o snapshot do solicitante ativo. Requests e handoffs continuam sob a autoridade do runtime.
- `identityRevision` permanece como guarda de respostas assíncronas. Uma mensagem em voo não é salva como estado consolidado nem aplicada após troca de identidade.

## Validações

- Frontend: **129 testes aprovados**, lint e build aprovados.
- Python focado: `tests/web/test_conversation_reset.py` com **3 aprovados**.
- Python completo com `PYTHONPATH=src`: **1358 aprovados, 32 skips** em 193,43 s.
- Ruff check, Ruff format check e `git diff --check` aprovados.
- Validação manual local: solicitante criou `REQ-000001`, técnico CDM viu a solicitação, o retorno ao solicitante preservou as mensagens e o contexto; `/requests` preservou a solicitação; Nova conversa limpou o chat e a solicitação continuou em `/requests`.

## Limitações

- A validação manual local enviou uma mensagem de CDM e percorreu todas as transições críticas; a cobertura automatizada cobre conversas, isolamento Ana/Carlos, CTA, rotas internas e resposta tardia.
- Nenhum teste Ollama foi executado porque runtime conversacional, grounding, interpreter e gerador de resposta não foram alterados.

## Próxima task

Task 7: começar com **GPT-5.6 Terra / Medium**. Escalar para Sol / Medium apenas se a tarefa exigir alteração cross-layer não prevista.
