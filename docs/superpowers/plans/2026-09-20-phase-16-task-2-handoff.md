# Phase 16 — Task 2: catálogo e escopo CDM

Baseline: `4e9cd54f8f8ff8e9039307d0d6b7dce91c96fc43`, branch `phase-16-demo-readiness`.
Execução inline, GPT-6 Astra / Low, sem subagents e sem escalada.

## Contrato entregue

- `SessionIdentity.area` continua texto livre e confiável; nome, e-mail e cargo permanecem na identidade.
- `CDMScopeCatalog` é o catálogo único, injetável no runtime e no adapter/fake. O catálogo local contém `revenda`, `ubs` e `fazenda`. `Revenda - Matriz` é um alias explícito de área para preservar a persona homologada. Não há aproximação por palavras contidas na área.
- `prepare_access_request` resolve o escopo por correspondência exata ou intenção explícita validada. Entidades inferidas pelo modelo não fornecem papel, área ou escopo.
- `AccessRequestContext` registra `business_scope`, `scope_source`, `scope_mismatch` e `scope_confirmed`, sem substituir `requester.area`.
- Área sem correspondência retorna `NEEDS_CLARIFICATION` / `CDM_SCOPE_REQUIRED`, sem contexto executável e sem materialização.
- Divergência retorna `NEEDS_CONFIRMATION`; o runtime pergunta, mantém o pedido pendente e materializa somente após confirmação explícita. A policy e o executor bloqueiam divergência não confirmada. Confirmar intenção não concede acesso: aprovação humana e revalidação continuam obrigatórias.
- Respostas curtas de escopo reutilizam a finalidade e o papel originais. Novo pedido de papel privilegiado é reavaliado pelas regras existentes. Nova conversa descarta a pendência.
- O fake transporta/persiste `business_scopes`, inclui o escopo na idempotência e não trata acesso existente em outro escopo como sucesso.
- Payload e detalhe técnico exibem cargo, área confiável, papel, escopo e divergência. Nenhum redesign ou regra de negócio foi introduzido no frontend.

## Compatibilidade e decisões

A extensão dos dataclasses e do protocolo fake é aditiva. Consumidores internos legados ainda podem construir contextos sem os novos campos e usar o protocolo fake anterior; o caminho conversacional da demo sempre passa pela preparação com catálogo. Não foi integrada a API real CDM. Papéis internos continuam com a convenção existente em maiúsculas; aprovador/admin/superadmin continuam bloqueados pela policy existente.

Fixtures antigas com `Revenda Sintetica` passaram a usar `Revenda` exata. Casos Financeiro que anteriormente esperavam materialização agora exigem esclarecimento, fortalecendo o contrato aprovado. Testes de policy/confiança continuam verificando sua independência. Os testes por hash mantêm comparação exata: `phase16_authorized_blobs.py` registra as extensões autorizadas, e os arquivos alterados são verificados no working tree antes e depois do commit. Nenhum teste de proteção foi removido ou ignorado.

O Python global apontava para o checkout do runner. Todos os testes desta task usam `PYTHONPATH` apontando para o `src` deste repositório; o checkout do runner não foi alterado.

## Aceite determinístico

| Caso | Evidência |
|---|---|
| UBS e Revenda + pedido genérico | Escopo correspondente, solicitante, sem divergência |
| Financeiro, Logística, Controladoria, UBS Financeiro | Nenhum escopo aproximado e nenhuma solicitação criada |
| Revenda + pedido UBS | UBS preservado, divergência e confirmação obrigatória |
| Técnico após confirmação/aprovação | Identidade, cargo, escopo e divergência preservados; fake recebe UBS |
| Catálogo futuro | Financeiro no domínio e Logística até execução fake, sem nova regra central |
| Tentativa de alterar identidade | Área confiável permanece; reducer rejeita fatos operacionais fabricados |
| Identidade configurável e Nova conversa | Provider da Task 1 reutilizado; pendência descartada no reset |
| Papel privilegiado durante pendência | Novo pedido reavaliado e negado; não herda solicitante |
| CDM normal, M365, general IT e ownership | Suíte de regressão existente |

## Validação manual local

Exercício real de `DemoRuntime` em `LOCAL_AI`, com `qwen3.5:4b` e `qwen3-embedding:0.6b`: UBS genérico, Financeiro sem correspondência e Revenda solicitando UBS. Os três estados esperados foram confirmados. O último caso seguiu por confirmação, aprovação técnica e execução fake `COMPLETED`, mantendo a divergência. Logs locais em `reports/task2/`, ignorados pelo Git.

A renderização técnica foi validada por testes de HTML, sem inspeção visual de navegador nesta task. Revisão de código realizada inline pelo próprio implementador, conforme a instrução de não usar subagents.

## Limitações e próxima task

A conversa usa formas determinísticas delimitadas para selecionar/confirmar escopo; refinamento conversacional completo permanece na Task 3. No exercício Qwen, uma resposta acrescentou que a equipe havia sido notificada e que haveria acompanhamento, sem fato correspondente no backend. Isso não alterou identidade, escopo, aprovação nem execução, mas deve entrar na revisão do texto/grounding da Task 3. Não foi feita uma bateria extensa Qwen.

Confiança heurística anterior foi preservada; não concede autorização e não substitui o indicador explícito de divergência. API real, persistência e polish permanecem fora do escopo. A pasta `jup-apresentation` não foi alterada.

Recomendação para Task 3: **GPT-6 Astra / Medium**, por envolver continuidade conversacional e grounding de respostas, além dos estados determinísticos entregues aqui.

## Arquivos alterados

- `docs/superpowers/plans/2026-09-20-phase-16-task-2-handoff.md`
- `src/ai_service_desk/engine/access_request.py`
- `src/ai_service_desk/engine/cdm_execution.py`
- `src/ai_service_desk/engine/cdm_scope.py`
- `src/ai_service_desk/engine/policy.py`
- `src/ai_service_desk/integrations/cdm.py`
- `src/ai_service_desk/integrations/cdm_fake_api.py`
- `src/ai_service_desk/web/business_context.py`
- `src/ai_service_desk/web/conversation_state.py`
- `src/ai_service_desk/web/demo_runtime.py`
- `src/ai_service_desk/web/presentation.py`
- `tests/engine/phase16_authorized_blobs.py`
- `tests/engine/test_access_request.py`
- `tests/engine/test_cdm_execution.py`
- `tests/engine/test_phase10_security.py`
- `tests/engine/test_phase11_security.py`
- `tests/engine/test_phase8_security.py`
- `tests/engine/test_phase9_security.py`
- `tests/engine/test_policy_security.py`
- `tests/fixtures/phase7_policy_cases.jsonl`
- `tests/integrations/test_cdm_adapter.py`
- `tests/integrations/test_cdm_fake_store.py`
- `tests/web/test_cdm_scope_runtime.py`
- `tests/web/test_conversation_state.py`
- `tests/web/test_demo_runtime.py`
- `tests/web/test_presentation.py`
- `web/src/tracking.mjs`
- `web/tests/technician-explainability.test.mjs`

## Resultado das verificações

- `python -m pytest`: **1299 passed, 27 skipped**, 76 avisos de depreciação FastAPI, 178,95 s. Os skips são homologações Qwen opt-in já existentes; nenhum skip foi introduzido nesta task.
- Ciclo TDD observado nos testes novos de domínio, runtime, idempotência, confirmação/policy e apresentação. Rodadas focadas finais: 69, 74, 43 e 85 testes aprovados nos respectivos conjuntos; todas as alterações de produto estão incluídas na suíte completa final.
- `python -m ruff check .`: aprovado.
- `python -m ruff format --check .`: 179 arquivos formatados corretamente.
- `npm test`: 121 testes aprovados.
- `npm run build` e `npm run lint`: aprovados.
- `git diff --check`: aprovado.
- Ollama real: três casos CDM e confirmação/aprovação/execução fake aprovados.

Status: **PASS** para os critérios da Task 2. Nenhum critério de aceite foi flexibilizado. Sem push, PR, merge ou alteração de main. O SHA do checkpoint é fornecido no encerramento da tarefa.
