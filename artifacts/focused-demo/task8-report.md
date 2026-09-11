# Task 8 — LOCAL_AI compacto e medido

## Resultado

Task 8 validada localmente em `2026-09-11T17:01:58-03:00` sobre o commit-base `8c73431e3c3f8acc502c58a2b3752d387282f548`.
O runtime usa `qwen3.5:4b` somente como interpretador linguístico, com contrato JSON mínimo
`scenario + signal`. Identidade, policy, autorização, IDs, routing, execução, knowledge e
resultados operacionais permanecem sob autoridade do backend.

Configuração final do payload LOCAL_AI:

- `think=false`
- `stream=false`
- `temperature=0`
- `keep_alive=30m`
- `num_ctx=1024`
- `num_predict=32`
- prompt compacto com 647 caracteres e `BUSINESS_CONTEXT_CURRENT`
- no máximo uma inferência por turno operacional
- zero inferências para greeting, fora de escopo e renderização de resultados já conhecidos

## TDD — RED → GREEN

RED inicial da Task 8:

- `tests/web/test_demo_local_ai.py`: **9 failed**
- causas observadas: payload antigo (`num_predict=384`), ausência de telemetry,
  ausência de fail-closed para JSON inválido/truncado e `OllamaError` vazando diretamente.

GREEN inicial:

- `tests/web/test_demo_local_ai.py`: **9 passed**
- `tests/web/test_focused_demo_contract.py`: **43 passed**

Ciclo de performance:

- RED com `num_predict <= 24`: falhou em `32 <= 24` antes do GREEN.
- GREEN experimental com `num_predict=24`, `num_ctx=1024` e prompt de 594 caracteres
  reduziu latência, mas a medição real apresentou **3 falhas de 5 inferências** por resposta
  fora do contrato compacto.
- RED de confiabilidade passou a exigir `32 <= num_predict <= 48`.
- GREEN final: `num_predict=32`, `num_ctx=1024`, prompt de 647 caracteres e
  `BUSINESS_CONTEXT_CURRENT` restaurado.

## Verificações funcionais finais

Comandos executados antes desta medição:

```powershell
python -m pytest tests/web/test_demo_local_ai.py -q
python -m pytest tests/web/test_focused_demo_contract.py -q
python -m pytest `
  tests/web/test_conversational_ai.py `
  tests/web/test_business_context_runtime.py `
  tests/web/test_business_qa_regressions.py `
  tests/web/test_demo_runtime.py `
  tests/web/test_conversation_authority.py `
  tests/web/test_demo_support_handoff.py `
  tests/web/test_demo_identity.py `
  -q
```

Resultados finais observados:

- LOCAL_AI: **9 passed**
- contrato focado: **43 passed**
- regressões ampliadas: **93 passed, 3 skipped**
- Ruff check: **PASS**
- Ruff format check: **PASS**
- `git diff --check`: sem erro de whitespace; apenas avisos locais LF → CRLF

Os três skips são QA explícita com Qwen local e permanecem opt-in para não tornar CI hospedado
não determinístico.

## Medição real — `qwen3.5:4b`

Ambiente: Python `3.14.7` em `Windows`.
Startup do runtime/model validation: **24.3 ms**.

| Variante | Chamadas / orçamento | Turno (ms) | Resultado |
| --- | ---: | ---: | --- |
| `greeting` | 0 / 0 | 0.0 | `SOCIAL` |
| `out_of_scope` | 0 / 0 | 0.0 | `OUT_OF_SCOPE` |
| `cdm_access` | 1 / 1 | 10292.0 | `REQUEST_CREATED` |
| `cdm_privileged` | 1 / 1 | 10236.7 | `DENIED_POLICY` |
| `m365_guidance` | 1 / 1 | 10001.2 | `KNOWLEDGE_FOUND` |
| `m365_success` | 0 / 0 | 2.3 | `SUPPORT_RESOLVED` |
| `m365_guidance_for_failure` | 1 / 1 | 3161.1 | `KNOWLEDGE_FOUND` |
| `m365_handoff` | 0 / 0 | 2.2 | `SUPPORT_HANDOFF_PENDING` |
| `generic_it` | 1 / 1 | 10959.2 | `NEEDS_CLARIFICATION` |

Estatísticas das 5 inferências reais:

- mínimo: **3149.1 ms**
- média: **8920.0 ms**
- p50: **10224.7 ms**
- p95: **10818.5 ms**
- máximo: **10952.8 ms**
- total de chamadas: **5**
- falhas de inferência: **0**
- turnos com zero chamadas: **4**
- turnos com uma chamada: **5**

Variantes exercitadas: greeting, fora de escopo, acesso CDM normal, acesso CDM privilegiado,
M365 senha esquecida com guidance APPROVED, confirmação de sucesso, repetição do guidance para
cenário de falha, handoff M365 após falha e problema genérico de TI.

## Invariantes preservados

- greeting e fora de escopo: 0 Qwen;
- resultado backend/knowledge/outcome/handoff: 0 Qwen extra;
- turno operacional complexo: <= 1 Qwen;
- nenhuma identidade, policy, role autorizada, request ID, routing ou execução é decidida pelo LLM;
- resposta compacta malformada, truncada ou com campos extras falha explicitamente;
- falha de transporte Ollama vira erro web explícito;
- telemetry registra somente duração, contagem e sucesso/falha, sem mensagem, prompt ou segredo;
- sem warm-up automático;
- sem alteração de engine/core ou integrações.

## Artefatos

- relatório versionado: `artifacts/focused-demo/task8-report.md`
- log bruto local, não adicionar ao Git: `artifacts/focused-demo/task8-local-ai-measurement.log`
