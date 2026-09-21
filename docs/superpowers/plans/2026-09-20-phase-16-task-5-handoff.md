# Phase 16 — Task 5: Minhas solicitações

## Status

PASS. Execução inline com **GPT-5.6 Terra / Medium**, sem subagents e sem escalada.

## Entrega

- Consultas em linguagem natural sobre solicitações usam a mesma capacidade autoritativa baseada em `DemoRuntime.list_requests(identity_id)`.
- `/solicitacoes` registra a ação no chat e segue caminho determinístico, sem chamada ao Qwen.
- O resumo expõe somente identificador, sistema e `state_label` apresentados pelo backend; não expõe enums técnicos.
- O CTA explícito `Ver minhas solicitações` abre `/requests`; a tela continua consumindo `GET /api/requests`.
- O composer apresenta somente o menu compacto de `/solicitacoes`, com mouse, teclado e Escape.
- A resposta preserva a autorização atual: técnico não pode consultar a capacidade de solicitante e uma identidade não recebe registros de outra.

## Validações

- Suíte Python: **1358 passed, 32 skipped** em 203,62 s, com `PYTHONPATH=src` para garantir a importação do checkout local.
- Ruff check e format check aprovados; `git diff --check` aprovado.
- Frontend: **126 testes aprovados**, lint e build aprovados.
- Ollama real com `qwen3.5:4b` e `qwen3-embedding:0.6b`: **1 passed** em 50,48 s para as consultas “Como estão minhas solicitações?” e “Tenho algum pedido pendente?”, com uma solicitação CDM materializada.

## Limitações

- A inspeção visual pelo browser integrado foi bloqueada pelo cliente (`ERR_BLOCKED_BY_CLIENT` para o servidor local). A estrutura, CTA e interações foram validados pelos testes de renderização e integração do frontend.
- A continuidade da conversa entre personas permanece fora de escopo para a Task 6.

## Próxima task

Task 6: **GPT-5.6 Terra / Medium**. Escalar para Sol / Medium somente se a correção de continuidade exigir mudança compartilhada não trivial de estado entre rotas e personas.
