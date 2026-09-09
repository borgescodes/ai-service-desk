# Phase 8 Controlled Approval and Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar aprovação humana e execução controlada stateful, auditável e fail-closed sobre os contratos homologados da Fase 7, usando somente repository e executor em memória.

**Architecture:** A Fase 8 introduz request lifecycle, repository com optimistic concurrency, autorização explícita de técnico, ApprovalService, auditoria append-only e ExecutionEngine com FakeActionExecutor. Policy e confidence da Fase 7 são reutilizadas sem duplicação, e qualquer integração HTTP/CDM permanece fora da fase.

**Tech Stack:** Python 3.14, dataclasses, typing/Protocol, threading local para exclusão mútua, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-09-phase-8-controlled-approval-execution-design.md`

## Global Constraints

- Spec canônica aprovada e imutável: `24d411987d991b1d7f8fce04131dd19afa2c7af5`.
- Regression baseline imutável: `2f583b5b4921cd7b40ddde2978a2852ecca2251d`.
- Historical baseline: exatamente `426` node IDs. Nenhum node ID histórico pode desaparecer, ser renomeado silenciosamente, removido ou convertido em skip.
- A implementação deve iniciar no head aprovado da própria branch depois do aceite deste plano. O worktree de implementação não pode ser resetado, movido ou destacado para a spec head ou para o regression baseline.
- Estados permitidos, sem qualquer estado adicional: `TRIAGED`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `DENIED_POLICY`, `EXECUTING`, `COMPLETED`, `FAILED`.
- Transições permitidas exclusivamente: `TRIAGED -> PENDING_APPROVAL`, `TRIAGED -> DENIED_POLICY`, `PENDING_APPROVAL -> APPROVED`, `PENDING_APPROVAL -> REJECTED`, `APPROVED -> EXECUTING`, `APPROVED -> DENIED_POLICY`, `EXECUTING -> COMPLETED`, `EXECUTING -> FAILED`.
- Estados terminais da Fase 8: `REJECTED`, `DENIED_POLICY`, `COMPLETED`, `FAILED`.
- `FAILED` não possui retry, requeue, reset para `APPROVED` nem nova transição para `EXECUTING`.
- `RequestLifecycleService.create_request(context)` valida o `AccessRequestContext` homologado, reavalia `PolicyEngine.evaluate(context)` e calcula `assess_confidence(context)` separadamente.
- `create_request(...)` nunca aceita `PolicyDecision` fornecido pelo caller como autoridade.
- Policy de criação `DENY` cria registro auditável em `DENIED_POLICY`; policy `REQUIRE_APPROVAL` cria `PENDING_APPROVAL`.
- `DENIED_POLICY` nunca é aprovável nem rejeitável. Com versão vigente, decisão humana falha por estado inválido; caller stale falha antes com `VERSION_CONFLICT`.
- `AccessRequestRecord` é imutável. `request_id`, `context`, `creation_policy`, `confidence` e `created_at` nunca mudam depois da criação.
- `latest_policy` começa igual a `creation_policy` e só pode ser substituída pela policy revalidada antes da execução.
- `request_id` é determinístico por instância de `InMemoryRequestRepository`: `REQ-000001`, `REQ-000002`, `REQ-000003`. UUID, timestamp, email, username e hash de identidade são proibidos no ID.
- `version` começa em `1` no snapshot `TRIAGED`; toda transição persistida incrementa exatamente `+1`.
- Todo entrypoint que recebe `expected_version` valida antes de igualdade ou coerção: `type(expected_version) is int` e `expected_version > 0`.
- `True`, `False`, `3.0`, `"3"`, `None`, zero e inteiros negativos produzem `EXPECTED_VERSION_INVALID`, sem mutação, sem audit append, sem policy e sem executor quando aplicável.
- Depois da validação estrutural, `expected_version != current.version` produz `VERSION_CONFLICT`.
- `ApprovalService.approve/reject` segue exatamente: get request -> validar `expected_version` -> comparar com `current.version` -> se diferente `VERSION_CONFLICT` -> exigir `PENDING_APPROVAL` -> technician identity/capability -> self-decision -> lifecycle transition -> repository CAS novamente.
- `ExecutionEngine.execute` segue exatamente: get request -> validar `expected_version` -> comparar com `current.version` -> se diferente `VERSION_CONFLICT` com zero policy/executor calls -> exigir `APPROVED` -> revalidar policy -> capturar um único `operation_timestamp = clock()` -> preparar `DENIED_POLICY` ou `EXECUTING` -> repository CAS novamente -> somente então executor.
- `ExecutionEngine.execute(...)` chama o clock operacional exatamente uma vez em toda execução que ultrapassa expected_version/state e obtém uma policy revalidada. Stale execution e invalid-state falham antes desse clock.
- O mesmo `operation_timestamp` é passado explicitamente como `occurred_at=` a `transition_to_denied_policy`, `transition_to_executing`, `transition_to_completed` e `transition_to_failed` em qualquer caminho usado por `ExecutionEngine`.
- Em execução iniciada, `execution_started_at` e `execution_finished_at` podem ser iguais. Igualdade é válida e version/append order definem a ordem.
- O compare preliminar não substitui o CAS final. O CAS final fecha a race entre leitura/validações e persistência e garante no máximo uma executor call.
- `InMemoryRequestRepository.save(...)` exige `new_record.version == expected_version + 1`.
- `InMemoryRequestRepository.save(...)` exige `new_record.updated_at >= current_record.updated_at`; igualdade é permitida.
- Retrocesso de `updated_at` entre versões produz `RECORD_INVARIANT_INVALID`, zero escrita e zero audit append.
- Cronologia do record: `created_at <= updated_at`; `created_at <= decided_at` quando `decided_at` existir; `decided_at <= execution_started_at` quando ambos existirem; `execution_started_at <= execution_finished_at` quando ambos existirem.
- Todos os timestamps persistidos e auditados são timezone-aware: `timestamp.tzinfo is not None` e `timestamp.utcoffset() is not None`.
- `create_request(...)` captura um único timestamp timezone-aware e reutiliza esse valor nos snapshots/eventos `TRIAGED version=1` e na transição imediata para `PENDING_APPROVAL version=2` ou `DENIED_POLICY version=2`.
- `AuditEvent` é imutável e append-only. Não existe API de update/delete de audit.
- `audit_for(...)` retorna tuple/snapshot, nunca a lista interna mutável.
- `AuditEvent.occurred_at` não pode ser menor que o evento anterior do mesmo request; igualdade é permitida.
- Quando timestamps são iguais, `version` e ordem física de append são os desempates canônicos.
- Violação temporal de record produz `RECORD_INVARIANT_INVALID` antes da escrita.
- Violação temporal de audit produz `AUDIT_EVENT_INVALID` antes do append.
- Nenhuma falha de validação, concorrência ou cronologia pode produzir mutação parcial.
- `TechnicianAuthorizationRegistry` valida todas as entradas antes de construir qualquer índice.
- Configuração runtime inválida produz `TECHNICIAN_REGISTRY_INVALID`; nenhuma parte da configuração inválida pode operar.
- Somente depois de todas as entradas válidas são construídos os índices.
- `technician_id.strip().casefold()`, `username.strip().casefold()` e `email.strip().casefold()` devem ser únicos.
- Colisão normalizada produz `TECHNICIAN_REGISTRY_CONFLICT`; last-write-wins, merge silencioso e escolha arbitrária são proibidos.
- Capabilities do registry devem ser strings simbólicas válidas com `^[A-Z][A-Z0-9_]{2,119}$`.
- Wildcard, prefix expression, fuzzy token, lowercase, espaço ou valor não-string não autorizam e não podem ser convertidos em capability válida.
- `TechnicianAuthorizationRegistry.require_capability(...)` autoriza somente a capability exata.
- Técnico ausente, identidade divergente ou sem capability exata produz `TECHNICIAN_CAPABILITY_REQUIRED`.
- Requester não pode decidir o próprio request.
- Self-decision compara `technician.username.strip().casefold()` e `technician.email.strip().casefold()` com os equivalentes do requester. Coincidência em qualquer um produz `SELF_DECISION_NOT_ALLOWED` em approve e reject.
- `approve(...)` e `reject(...)` nunca executam ação.
- `ApprovalService` não recebe `ActionExecutor` nem `ExecutionEngine` como dependência.
- `ActionExecutionResult` válido exige `type(result) is ActionExecutionResult`, `type(result.success) is bool`, `isinstance(result.result_code, str)` e `result_code` compatível com `^[A-Z][A-Z0-9_]{2,119}$`.
- Retorno inválido do executor produz `FAILED`, `execution_result_code=None`, `execution_error_code=EXECUTOR_INVALID_RESULT`.
- Nenhum valor, texto, `repr` ou campo arbitrário de retorno inválido pode ser persistido em record ou audit.
- Exceção do executor captura `Exception`, nunca `BaseException`, e produz `FAILED / EXECUTOR_EXCEPTION` sem mensagem bruta, traceback ou nome de classe persistido.
- Executor válido com `success=True` produz `COMPLETED`.
- Executor válido com `success=False` produz `FAILED` com código seguro.
- Revalidation `DENY` produz `APPROVED -> DENIED_POLICY`, substitui apenas `latest_policy` e faz zero executor calls.
- Revalidation `REQUIRE_APPROVAL` exige persistência `APPROVED -> EXECUTING` e `EXECUTION_STARTED` antes de `ActionExecutor.execute(...)`.
- Confidence permanece informacional. `HIGH` ou `LOW` nunca autoriza, nega, remove aprovação nem altera execução.
- `InMemoryRequestRepository` é a única persistência de requests/audit da Fase 8.
- Execução externa é zero. O runtime da Fase 8 não pode usar HTTP, `requests`, `httpx`, `urllib.request`, `CDMAdapter`, API fake do CDM, subprocess, shell, PowerShell, Ollama, LLM, embedding, SQLite, banco, JSON persistente ou cache externo.
- `subprocess` é permitido exclusivamente nos testes de segurança para consultar objetos Git e no workflow para restaurar byte-exact o fixture Phase 2. Ele permanece proibido nos módulos runtime da Fase 8.
- Fase 9 não pode ser antecipada: nenhum adapter, credential, lookup externo, idempotência externa, HTTP ou executor real de CDM.
- Fase 10 não pode ser antecipada: nenhum routing, seleção automática de técnico, fila automática ou distribuição de workload.
- Arquivos protegidos devem permanecer byte-equivalent ao regression baseline durante toda a implementação:
  - `src/ai_service_desk/engine/access_request.py`
  - `src/ai_service_desk/engine/policy.py`
  - `src/ai_service_desk/engine/confidence.py`
- Blobs Git homologados desses arquivos:
  - `src/ai_service_desk/engine/access_request.py` = `f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d`
  - `src/ai_service_desk/engine/policy.py` = `60a4f3ae785353009c30b37f71e1ce91865b899e`
  - `src/ai_service_desk/engine/confidence.py` = `ffc0c212b455978f79a3591578f323ca0e9612dc`
- Testes de protected blob devem consultar o objeto Git de `HEAD` com `git rev-parse HEAD:<path>`. É proibido calcular blob SHA com `Path.read_bytes()` do working tree.
- `tests/fixtures/phase2_corpus.csv` e `tests/fixtures/phase2_corpus_manifest.json` não podem ser alterados em Git.
- Escopo proibido: HTTP, `requests/httpx/urllib` para execução, `CDMAdapter`, API fake do CDM, SQLite, JSON persistente, banco, routing, frontend, LLM/Ollama/embedding e retry de `FAILED`.

---

## Existing Phase 7 Patterns Inspected

O executor deste plano deve preservar os padrões já homologados:

- `src/ai_service_desk/cli.py`: smoke como subcommand aditivo e dispatch antes da construção de `OllamaClient`.
- `src/ai_service_desk/engine/policy_smoke.py`: JSONL sintético com schema fechado, execução determinística, relatório agregado privacy-safe e escrita por `atomic_json`.
- `tests/engine/test_policy_smoke.py`: schema, quantidade exata de casos, privacy e runtime zero-external.
- `tests/test_policy_cli.py`: parser, stdout seguro, exit code e garantia de não construir Ollama.
- `.github/workflows/phase7-policy-smoke.yml`: `workflow_dispatch`, `target_ref` exact-head, runner Windows self-hosted, Python 3.14, restauração byte-exact do fixture Phase 2, Ruff, suíte completa e smoke.
- `tests/test_workflows.py`: validação estrutural do workflow, sem upload/export e sem dependências proibidas.
- `.github/workflows/ci.yml`: hosted CI em PR com Python 3.14, Ruff lint, Ruff format e pytest.
- Nenhum padrão acima autoriza refatoração dos módulos protegidos da Fase 7.

---

## Planned File Map

### Create

- `src/ai_service_desk/engine/request_lifecycle.py`: estados, dataclasses, reason-code errors, validators, transition matrix e `RequestLifecycleService`.
- `src/ai_service_desk/engine/request_repository.py`: `RequestRepository`, `InMemoryRequestRepository`, IDs determinísticos, optimistic concurrency e audit append-only.
- `src/ai_service_desk/engine/technician_authorization.py`: `TechnicianIdentity`, registry entry, validação fail-closed, índices únicos e capability exata.
- `src/ai_service_desk/engine/approval.py`: `ApprovalService`, gate ordering, capability e self-decision.
- `src/ai_service_desk/engine/execution.py`: `ActionExecutionResult`, `ActionExecutor`, `FakeActionExecutor` e `ExecutionEngine`.
- `src/ai_service_desk/engine/controlled_execution_smoke.py`: smoke sintético determinístico e privacy-safe.
- `tests/engine/phase8_helpers.py`: factories sintéticas, clocks determinísticos e policy doubles.
- `tests/engine/test_request_lifecycle.py`: state machine, contracts, criação e lifecycle transitions.
- `tests/engine/test_request_repository.py`: IDs, create/save, expected_version e snapshots de audit.
- `tests/engine/test_phase8_audit_temporal.py`: timezone-awareness, cronologia e monotonicidade temporal.
- `tests/engine/test_technician_authorization.py`: registry fail-closed, conflitos normalizados e capability exata.
- `tests/engine/test_approval.py`: approve/reject, stale ordering, self-decision e zero execution.
- `tests/engine/test_execution.py`: state gate, policy revalidation, single operation timestamp, executor result e safe failure.
- `tests/engine/test_phase8_concurrency.py`: final CAS, dupla decisão, dupla execução e races.
- `tests/engine/test_phase8_security.py`: criado na Task 8 junto do RED de atomic CAS; consulta Git blobs via `git rev-parse`, static scans e runtime zero-external.
- `tests/engine/test_controlled_execution_smoke.py`: seis fluxos sintéticos, schema, privacy e zero-external.
- `tests/test_controlled_execution_cli.py`: parser, stdout seguro e exit codes.
- `tests/fixtures/phase8_controlled_execution_cases.jsonl`: seis casos sintéticos sem dados corporativos.
- `.github/workflows/phase8-controlled-execution-smoke.yml`: workflow manual exact-head para Dell.

### Modify

- `src/ai_service_desk/cli.py`: adicionar somente `controlled-execution-smoke` e seu dispatch.
- `tests/test_workflows.py`: adicionar somente o contrato estrutural do workflow da Fase 8.
- `tests/engine/test_phase8_security.py`: na Task 9, adicionar `controlled_execution_smoke.py` ao scan de superfícies externas; o arquivo é criado originalmente na Task 8.

### Must remain untouched

- `src/ai_service_desk/engine/access_request.py`
- `src/ai_service_desk/engine/policy.py`
- `src/ai_service_desk/engine/confidence.py`
- `tests/fixtures/phase2_corpus.csv`
- `tests/fixtures/phase2_corpus_manifest.json`

---

## Execution Preflight

- [ ] **Preflight 1: registrar execution start real**

Run:

```bash
git branch --show-current
git status --short
EXECUTION_START_HEAD="$(git rev-parse HEAD)"
printf 'execution_start_head=%s\n' "$EXECUTION_START_HEAD"
git merge-base --is-ancestor 24d411987d991b1d7f8fce04131dd19afa2c7af5 "$EXECUTION_START_HEAD"
git diff --name-only 24d411987d991b1d7f8fce04131dd19afa2c7af5 "$EXECUTION_START_HEAD"
```

Expected: branch `phase-8-controlled-approval-execution`; working tree clean; spec head é ancestral; diff spec-head -> execution-start contém somente o implementation plan aprovado.

- [ ] **Preflight 2: confirmar arquivos protegidos antes de código**

Run:

```bash
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d "$EXECUTION_START_HEAD" -- \
  src/ai_service_desk/engine/access_request.py \
  src/ai_service_desk/engine/policy.py \
  src/ai_service_desk/engine/confidence.py
```

Expected: exit `0`.

- [ ] **Preflight 3: confirmar baseline de 426 node IDs sem mover o worktree de implementação**

Run:

```bash
BASELINE_WORKTREE="../ai-service-desk-phase8-baseline"
git worktree add --detach "$BASELINE_WORKTREE" 2f583b5b4921cd7b40ddde2978a2852ecca2251d
cd "$BASELINE_WORKTREE"
python -m pytest --collect-only -q
```

Expected: exatamente `426 tests collected`. Depois voltar ao worktree de implementação e remover o worktree temporário com:

```bash
git worktree remove "$BASELINE_WORKTREE"
```

Expected: worktree temporário removido; branch de implementação continua no execution start.

---

## Contract Matrix Coverage Map

Cada requisito da matriz de 87 casos da spec aponta para uma verificação concreta.

| Caso | Verificação concreta |
| ---: | --- |
| 1 | `test_request_lifecycle.py::test_create_request_require_approval_enters_pending_approval` |
| 2 | `test_request_lifecycle.py::test_create_request_deny_enters_denied_policy_with_audit` |
| 3 | `test_approval.py::test_denied_policy_cannot_be_approved` |
| 4 | `test_approval.py::test_denied_policy_cannot_be_rejected` |
| 5 | `test_approval.py::test_technician_without_capability_cannot_approve` |
| 6 | `test_approval.py::test_technician_without_capability_cannot_reject` |
| 7 | `test_approval.py::test_unregistered_technician_cannot_decide` |
| 8 | `test_approval.py::test_registry_identity_mismatch_cannot_decide` |
| 9 | `test_approval.py::test_requester_username_cannot_approve_own_request` |
| 10 | `test_approval.py::test_requester_email_cannot_reject_own_request` |
| 11 | `test_approval.py::test_self_decision_normalizes_case_and_outer_whitespace` |
| 12 | `test_approval.py::test_authorized_technician_approves_pending_request` |
| 13 | `test_approval.py::test_authorized_technician_rejects_pending_request` |
| 14 | `test_approval.py::test_approve_makes_zero_executor_calls` |
| 15 | `test_approval.py::test_reject_makes_zero_executor_calls` |
| 16 | `test_execution.py::test_execute_rejects_pending_approval` |
| 17 | `test_execution.py::test_execute_rejects_denied_policy` |
| 18 | `test_execution.py::test_execute_rejects_rejected_request` |
| 19 | `test_execution.py::test_execute_rejects_completed_request` |
| 20 | `test_execution.py::test_execute_rejects_failed_request_without_retry` |
| 21 | `test_execution.py::test_execute_revalidates_policy_before_executor` |
| 22 | `test_execution.py::test_revalidation_deny_transitions_to_denied_policy` |
| 23 | `test_execution.py::test_revalidation_deny_makes_zero_executor_calls` |
| 24 | `test_execution.py::test_require_approval_persists_executing_before_executor_call` |
| 25 | `test_execution.py::test_executor_success_transitions_to_completed` |
| 26 | `test_execution.py::test_executor_failure_transitions_to_failed` |
| 27 | `test_execution.py::test_executor_exception_transitions_to_safe_failed` |
| 28 | `test_execution.py::test_executor_exception_text_is_not_persisted` |
| 29 | `test_execution.py::test_invalid_executor_result_transitions_to_executor_invalid_result` |
| 30 | `test_execution.py::test_failed_request_does_not_execute_again` |
| 31 | `test_request_repository.py::test_first_request_id_is_req_000001` |
| 32 | `test_request_repository.py::test_request_ids_are_monotonic` |
| 33 | `test_request_repository.py::test_new_repository_restarts_id_sequence` |
| 34 | `test_approval.py::test_stale_approval_conflicts_before_state_or_authorization` |
| 35 | `test_approval.py::test_stale_rejection_conflicts_before_state_or_authorization` |
| 36 | `test_phase8_concurrency.py::test_double_human_decision_persists_exactly_one_transition` |
| 37 | `test_phase8_concurrency.py::test_double_execution_calls_executor_exactly_once` |
| 38 | `test_request_lifecycle.py::test_every_persisted_transition_increments_version_by_one` |
| 39 | `test_phase8_audit_temporal.py::test_all_persisted_timestamps_are_timezone_aware` |
| 40 | `test_phase8_audit_temporal.py::test_naive_datetime_is_rejected` |
| 41 | `test_request_repository.py::test_audit_for_returns_tuple_snapshot` |
| 42 | `test_request_repository.py::test_existing_audit_remains_immutable_prefix_after_save` |
| 43 | `test_request_repository.py::test_repository_exposes_no_audit_update_or_delete_api` |
| 44 | `test_request_lifecycle.py::test_pending_creation_audit_is_request_created_then_policy_requires_approval` |
| 45 | `test_request_lifecycle.py::test_denied_creation_audit_is_request_created_then_policy_denied` |
| 46 | `test_execution.py::test_completed_flow_has_canonical_audit_order` |
| 47 | `test_execution.py::test_failed_flow_has_execution_started_before_execution_failed` |
| 48 | `test_execution.py::test_revalidation_updates_latest_policy_only` |
| 49 | `test_request_lifecycle.py::test_context_is_identical_across_versions` |
| 50 | `test_execution.py::test_confidence_does_not_change_policy_or_execution_gate` |
| 51 | `test_phase8_security.py::test_phase7_protected_git_blob_is_exact[access_request]` |
| 52 | `test_phase8_security.py::test_phase7_protected_git_blob_is_exact[policy]` |
| 53 | `test_phase8_security.py::test_phase7_protected_git_blob_is_exact[confidence]` |
| 54 | `test_phase8_security.py::test_phase8_runtime_has_no_http_or_cdm_adapter` |
| 55 | `test_phase8_security.py::test_phase8_runtime_has_no_llm_ollama_or_embedding` |
| 56 | `test_phase8_security.py::test_phase8_stateful_core_has_no_real_persistence` |
| 57 | `test_controlled_execution_smoke.py::test_controlled_execution_smoke_passes_all_six_flows` |
| 58 | Final Gate `historical baseline node IDs = 426` and `missing historical node IDs = 0` |
| 59 | `test_technician_authorization.py::test_registry_invalid_entry_fails_closed_before_indexing` |
| 60 | `test_technician_authorization.py::test_registry_invalid_capability_fails_closed` |
| 61 | `test_technician_authorization.py::test_registry_rejects_wildcard_prefix_and_fuzzy_capabilities` |
| 62 | `test_technician_authorization.py::test_registry_rejects_normalized_technician_id_conflict` |
| 63 | `test_technician_authorization.py::test_registry_rejects_normalized_username_conflict` |
| 64 | `test_technician_authorization.py::test_registry_rejects_normalized_email_conflict` |
| 65 | `test_technician_authorization.py::test_registry_invalid_entry_precedes_potential_conflict` |
| 66 | `test_execution.py::test_invalid_result_rejects_integer_success` |
| 67 | `test_execution.py::test_invalid_result_rejects_string_success` |
| 68 | `test_execution.py::test_invalid_result_rejects_empty_result_code` |
| 69 | `test_execution.py::test_invalid_result_rejects_result_code_with_space` |
| 70 | `test_execution.py::test_invalid_result_rejects_non_string_unhashable_result_code` |
| 71 | `test_execution.py::test_invalid_result_rejects_wrong_result_object_type` |
| 72 | `test_phase8_audit_temporal.py::test_created_at_after_updated_at_is_record_invariant_invalid` |
| 73 | `test_phase8_audit_temporal.py::test_created_at_after_decided_at_is_record_invariant_invalid` |
| 74 | `test_phase8_audit_temporal.py::test_decided_at_after_execution_started_at_is_record_invariant_invalid` |
| 75 | `test_phase8_audit_temporal.py::test_execution_started_at_after_finished_at_is_record_invariant_invalid` |
| 76 | `test_phase8_audit_temporal.py::test_audit_timestamp_regression_is_audit_event_invalid` |
| 77 | `test_phase8_audit_temporal.py::test_equal_timestamps_are_allowed_and_ordered_by_version_and_append` |
| 78 | `test_request_repository.py::test_expected_version_true_is_invalid` |
| 79 | `test_request_repository.py::test_expected_version_false_is_invalid` |
| 80 | `test_request_repository.py::test_expected_version_float_is_invalid` |
| 81 | `test_request_repository.py::test_expected_version_string_is_invalid` |
| 82 | `test_request_repository.py::test_expected_version_none_is_invalid` |
| 83 | `test_execution.py::test_stale_execute_conflicts_before_policy_clock_and_executor` |
| 84 | `test_phase8_audit_temporal.py::test_save_rejects_updated_at_regression_without_write_or_audit` |
| 85 | `test_phase8_audit_temporal.py::test_save_accepts_equal_updated_at_when_other_invariants_hold` |
| 86 | `test_request_lifecycle.py::test_pending_creation_uses_one_timestamp_for_version_one_and_two` |
| 87 | `test_request_lifecycle.py::test_denied_creation_uses_one_timestamp_for_version_one_and_two` |

Mandatory additional execution timestamp node: `test_execution.py::test_execute_uses_single_operation_timestamp`.

---

### Task 1: Lifecycle contracts and shared test factories

**Files:**
- Create: `src/ai_service_desk/engine/request_lifecycle.py`
- Create: `tests/engine/phase8_helpers.py`
- Create: `tests/engine/test_request_lifecycle.py`

**Interfaces produced:**
- `RequestState`
- `REQUEST_STATES`
- `ALLOWED_TRANSITIONS`
- `AccessRequestRecord`
- `AuditEvent`
- `Phase8DomainError(reason_code: str, message: str)`
- `RequestNotFoundError`, `InvalidStateTransitionError`, `ExpectedVersionValidationError`, `ConcurrencyConflictError`, `RecordInvariantError`, `AuditEventValidationError`
- `validate_expected_version(value: object) -> int`
- `validate_access_request_record(record: AccessRequestRecord) -> None`
- `validate_audit_event(event: AuditEvent) -> None`
- helpers sintéticos `make_context()`, `make_policy_decision()`, `make_record()`, `FixedClock`.

- [ ] **Step 1: RED de contratos inexistentes**

Add tests that import the symbols above and assert exactly eight states and the closed eight-transition matrix.

Run:

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: collection FAIL because `ai_service_desk.engine.request_lifecycle` does not exist.

- [ ] **Step 2: GREEN mínimo dos contracts**

Implement frozen dataclasses and reason-code errors. `validate_expected_version` must use:

```python
if type(value) is not int or value <= 0:
    raise ExpectedVersionValidationError(
        "EXPECTED_VERSION_INVALID",
        "expected_version deve ser inteiro positivo exato.",
    )
return value
```

Implement structural state-field validation and timezone-awareness, but defer cross-version/audit chronology details listed in Task 7 so that Task 7 has a real RED.

Run:

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

Run:

```bash
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/request_lifecycle.py tests/engine/phase8_helpers.py tests/engine/test_request_lifecycle.py
python -m ruff format --check src/ai_service_desk/engine/request_lifecycle.py tests/engine/phase8_helpers.py tests/engine/test_request_lifecycle.py
```

Expected: all commands exit `0`.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/engine/request_lifecycle.py tests/engine/phase8_helpers.py tests/engine/test_request_lifecycle.py
git commit -m "feat: add phase 8 lifecycle contracts"
```

Expected: one commit containing exactly the three Task 1 files.

---

### Task 2: In-memory repository, deterministic IDs and single-thread CAS semantics

**Files:**
- Create: `src/ai_service_desk/engine/request_repository.py`
- Create: `tests/engine/test_request_repository.py`

**Consumes:** Task 1 record/audit validators and errors.

**Produces:**
- `RequestRepository` Protocol with `allocate_request_id`, `create`, `get`, `save`, `audit_for`.
- `InMemoryRequestRepository`.
- Internal no-op seam `_before_final_cas(self) -> None`; it exists only to force deterministic interleaving in Task 8 and is never exposed by the Protocol.

- [ ] **Step 1: RED de repository inexistente**

Tests must cover deterministic IDs, immutable tuple audit, create/get/save, exact `expected_version`, wrong-version `VERSION_CONFLICT`, and cases 78-82.

Run:

```bash
python -m pytest tests/engine/test_request_repository.py -q
```

Expected: collection FAIL because `request_repository` does not exist.

- [ ] **Step 2: GREEN de semantics single-thread**

Implement in-memory dictionaries/lists, deterministic `REQ-%06d`, create validation and `save` validation. `save` must call `validate_expected_version(expected_version)` before equality. It must call `_before_final_cas()` after preliminary validation and before mutation. At this task, only single-thread correctness is required; Task 8 adds the final lock/re-read barrier proven by a deterministic RED.

Run:

```bash
python -m pytest tests/engine/test_request_repository.py -q
```

Expected: PASS, including `True`, `False`, `3.0`, `"3"`, `None` -> `EXPECTED_VERSION_INVALID`.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/engine/test_request_lifecycle.py tests/engine/test_request_repository.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/request_repository.py tests/engine/test_request_repository.py
python -m ruff format --check src/ai_service_desk/engine/request_repository.py tests/engine/test_request_repository.py
```

Expected: all exit `0`.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/engine/request_repository.py tests/engine/test_request_repository.py
git commit -m "feat: add in-memory access request repository"
```

Expected: exactly two Task 2 files committed.

---

### Task 3: RequestLifecycleService creation and closed transitions

**Files:**
- Modify: `src/ai_service_desk/engine/request_lifecycle.py`
- Modify: `tests/engine/test_request_lifecycle.py`

**Consumes:** `RequestRepository`, Phase 7 `PolicyEngine`, `assess_confidence`.

**Produces exact public/internal service API:**

```python
class RequestLifecycleService:
    def create_request(self, context: AccessRequestContext) -> AccessRequestRecord: ...
    def transition_to_pending_approval(self, record: AccessRequestRecord, *, expected_version: int, occurred_at: datetime) -> AccessRequestRecord: ...
    def transition_to_denied_policy(self, record: AccessRequestRecord, policy: PolicyDecision, *, expected_version: int, occurred_at: datetime) -> AccessRequestRecord: ...
    def transition_to_approved(self, record: AccessRequestRecord, technician_id: str, *, expected_version: int, occurred_at: datetime) -> AccessRequestRecord: ...
    def transition_to_rejected(self, record: AccessRequestRecord, technician_id: str, *, expected_version: int, occurred_at: datetime) -> AccessRequestRecord: ...
    def transition_to_executing(self, record: AccessRequestRecord, policy: PolicyDecision, *, expected_version: int, occurred_at: datetime) -> AccessRequestRecord: ...
    def transition_to_completed(self, record: AccessRequestRecord, result_code: str, *, expected_version: int, occurred_at: datetime) -> AccessRequestRecord: ...
    def transition_to_failed(self, record: AccessRequestRecord, error_code: str, *, expected_version: int, occurred_at: datetime, result_code: str | None = None) -> AccessRequestRecord: ...
```

`occurred_at` is mandatory, never optional, for every transition method.

- [ ] **Step 1: RED de lifecycle service**

Add concrete tests for cases 1, 2, 38, 44, 45, 49, 86 and 87. Use a clock double whose second call raises to prove creation uses one timestamp for v1 and v2.

Run:

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: FAIL because `RequestLifecycleService` and transition methods are absent.

- [ ] **Step 2: GREEN de creation and transitions**

`create_request` sequence must be exactly: validate context -> policy evaluate -> confidence -> `initial_timestamp = clock()` once -> allocate ID -> create `TRIAGED version=1` + `REQUEST_CREATED` -> immediate allowed transition to `PENDING_APPROVAL` or `DENIED_POLICY` with the same timestamp.

All transition methods must reject edges not in `ALLOWED_TRANSITIONS`, construct immutable `version + 1` snapshots, create the canonical `AuditEvent`, and delegate atomic persistence to `repository.save(... expected_version=...)`.

Run:

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/engine/test_request_repository.py tests/engine/test_request_lifecycle.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/request_lifecycle.py tests/engine/test_request_lifecycle.py
python -m ruff format --check src/ai_service_desk/engine/request_lifecycle.py tests/engine/test_request_lifecycle.py
```

Expected: exit `0` throughout.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/engine/request_lifecycle.py tests/engine/test_request_lifecycle.py
git commit -m "feat: add phase 8 request lifecycle service"
```

---

### Task 4: TechnicianAuthorizationRegistry fail-closed

**Files:**
- Create: `src/ai_service_desk/engine/technician_authorization.py`
- Create: `tests/engine/test_technician_authorization.py`

**Produces:**
- frozen `TechnicianIdentity(technician_id, username, name, email)`.
- frozen `TechnicianRegistryEntry(identity, capabilities)`.
- `TechnicianRegistryConfigurationError` with `TECHNICIAN_REGISTRY_INVALID` / `TECHNICIAN_REGISTRY_CONFLICT`.
- `TechnicianAuthorizationError` with `TECHNICIAN_CAPABILITY_REQUIRED`.
- `TechnicianAuthorizationRegistry(entries)`.
- `require_capability(technician, capability) -> None`.

- [ ] **Step 1: RED do registry**

Add cases 59-65 plus authorization identity mismatch/exact capability. Invalid input and potential duplicate in the same config must assert `TECHNICIAN_REGISTRY_INVALID`.

Run:

```bash
python -m pytest tests/engine/test_technician_authorization.py -q
```

Expected: collection FAIL because module does not exist.

- [ ] **Step 2: GREEN em duas passagens**

First pass validates every entry and every capability with `^[A-Z][A-Z0-9_]{2,119}$` without building indices. Second pass builds normalized `technician_id`, username and email indices and fails on any collision. No wildcard/prefix/fuzzy and no last-write-wins.

Run:

```bash
python -m pytest tests/engine/test_technician_authorization.py -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/engine/test_technician_authorization.py tests/engine/test_request_lifecycle.py tests/engine/test_request_repository.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/technician_authorization.py tests/engine/test_technician_authorization.py
python -m ruff format --check src/ai_service_desk/engine/technician_authorization.py tests/engine/test_technician_authorization.py
```

Expected: all exit `0`.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/engine/technician_authorization.py tests/engine/test_technician_authorization.py
git commit -m "feat: add technician authorization registry"
```

---

### Task 5: ApprovalService, stale ordering and self-decision

**Files:**
- Create: `src/ai_service_desk/engine/approval.py`
- Create: `tests/engine/test_approval.py`

**Produces:**

```python
class ApprovalService:
    def approve(self, request_id: str, technician: TechnicianIdentity, *, expected_version: int) -> AccessRequestRecord: ...
    def reject(self, request_id: str, technician: TechnicianIdentity, *, expected_version: int) -> AccessRequestRecord: ...
```

Constructor dependencies: repository, lifecycle service, technician registry, timezone-aware clock. No executor dependency.

- [ ] **Step 1: RED de approval**

Add exact tests for cases 3-15, 34 and 35. Stale tests must supply a technician that would otherwise fail authorization/state and prove `VERSION_CONFLICT` wins first after get + structural expected_version validation.

Run:

```bash
python -m pytest tests/engine/test_approval.py -q
```

Expected: collection FAIL because `approval` module does not exist.

- [ ] **Step 2: GREEN com gate order fechado**

Implement exact order: get -> `validate_expected_version` -> compare current version -> require `PENDING_APPROVAL` -> registry capability -> self-decision username/email normalized -> call clock once -> lifecycle transition -> repository final CAS through lifecycle. `approve/reject` never imports or receives execution classes.

Run:

```bash
python -m pytest tests/engine/test_approval.py -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/engine/test_approval.py tests/engine/test_technician_authorization.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/approval.py tests/engine/test_approval.py
python -m ruff format --check src/ai_service_desk/engine/approval.py tests/engine/test_approval.py
```

Expected: all exit `0`.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/engine/approval.py tests/engine/test_approval.py
git commit -m "feat: add controlled human approval service"
```

---

### Task 6: ExecutionEngine, executor result contract and single operation timestamp

**Files:**
- Create: `src/ai_service_desk/engine/execution.py`
- Create: `tests/engine/test_execution.py`

**Produces:**
- frozen `ActionExecutionResult(success: bool, result_code: str)`.
- `ActionExecutor` Protocol.
- `FakeActionExecutor` with deterministic success/failure/exception/invalid-result modes and call list.
- `ExecutionEngine.execute(request_id: str, *, expected_version: int) -> AccessRequestRecord`.

- [ ] **Step 1: RED de execution e timestamp único**

Add cases 16-30, 46-50, 66-71, 83 and this mandatory test:

```python
def test_execute_uses_single_operation_timestamp():
    operation_time = datetime(2026, 9, 9, 3, 0, tzinfo=UTC)
    clock = OneShotClock(operation_time)
    approved = make_approved_request_with_separate_setup_clock()
    engine = make_execution_engine(approved, clock=clock, executor_mode="success")

    result = engine.execute(approved.request_id, expected_version=approved.version)

    assert result.state == "COMPLETED"
    assert clock.calls == 1
    assert result.execution_started_at == operation_time
    assert result.execution_finished_at == operation_time
    events = engine.repository.audit_for(approved.request_id)
    execution_times = [
        event.occurred_at
        for event in events
        if event.event_type in {"EXECUTION_STARTED", "EXECUTION_COMPLETED"}
    ]
    assert execution_times == [operation_time, operation_time]
    assert execution_times == sorted(execution_times)
```

`OneShotClock.__call__` must raise `AssertionError("execution clock called more than once")` on its second call.

Also make stale and invalid-state tests assert `clock.calls == 0`.

Run:

```bash
python -m pytest tests/engine/test_execution.py -q
```

Expected: collection FAIL because `execution` module does not exist.

- [ ] **Step 2: GREEN do executor contract**

Validate returned object before persisting any returned field. Validity is exactly: `type(result) is ActionExecutionResult`, `type(result.success) is bool`, result_code is str and matches `^[A-Z][A-Z0-9_]{2,119}$`.

Invalid return -> `transition_to_failed(... error_code="EXECUTOR_INVALID_RESULT", result_code=None, occurred_at=operation_timestamp)`.

Exception -> `transition_to_failed(... error_code="EXECUTOR_EXCEPTION", result_code=None, occurred_at=operation_timestamp)` with no exception text.

- [ ] **Step 3: GREEN do timestamp operacional fechado**

Implement the operational core in this exact order:

```python
record = repository.get(request_id)
validate_expected_version(expected_version)
if expected_version != record.version:
    raise ConcurrencyConflictError("VERSION_CONFLICT", "Versao stale.")
if record.state != "APPROVED":
    raise InvalidStateTransitionError("INVALID_STATE_TRANSITION", "Request nao esta APPROVED.")
policy = policy_engine.evaluate(record.context)
operation_timestamp = clock()
```

After that line there are no additional `clock()` calls in `execute(...)`.

For `DENY`:

```python
return lifecycle.transition_to_denied_policy(
    record,
    policy,
    expected_version=expected_version,
    occurred_at=operation_timestamp,
)
```

For `REQUIRE_APPROVAL`:

```python
executing = lifecycle.transition_to_executing(
    record,
    policy,
    expected_version=expected_version,
    occurred_at=operation_timestamp,
)
```

Every completion/failure call uses `expected_version=executing.version` and the same explicit `occurred_at=operation_timestamp`.

Run:

```bash
python -m pytest tests/engine/test_execution.py -q
```

Expected: PASS, including clock calls `1`, equal start/finish timestamps, non-regressing audit and final `COMPLETED` in the single-timestamp success test.

- [ ] **Step 4: regressão**

```bash
python -m pytest tests/engine/test_execution.py tests/engine/test_approval.py tests/engine/test_request_lifecycle.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/execution.py tests/engine/test_execution.py
python -m ruff format --check src/ai_service_desk/engine/execution.py tests/engine/test_execution.py
```

Expected: all exit `0`.

- [ ] **Step 5: commit**

```bash
git add src/ai_service_desk/engine/execution.py tests/engine/test_execution.py
git commit -m "feat: add controlled execution engine"
```

---

### Task 7: Audit and temporal invariants

**Files:**
- Modify: `src/ai_service_desk/engine/request_lifecycle.py`
- Modify: `src/ai_service_desk/engine/request_repository.py`
- Create: `tests/engine/test_phase8_audit_temporal.py`

- [ ] **Step 1: RED de cronologia**

Add exact tests for cases 39, 40, 72-77, 84 and 85. Every failure test snapshots current record/audit before the invalid save and asserts zero mutation afterwards.

Run:

```bash
python -m pytest tests/engine/test_phase8_audit_temporal.py -q
```

Expected: FAIL because cross-field chronology, audit non-regression and cross-version `updated_at` are not fully enforced yet.

- [ ] **Step 2: GREEN before-write validation**

Before mutation, enforce timezone-awareness plus:

```text
created_at <= updated_at
created_at <= decided_at when present
decided_at <= execution_started_at when both present
execution_started_at <= execution_finished_at when both present
new_record.updated_at >= current_record.updated_at
new_audit_event.occurred_at >= previous_event.occurred_at
```

Equality is accepted. Record failure -> `RECORD_INVARIANT_INVALID`; audit failure -> `AUDIT_EVENT_INVALID`; no partial write/append.

Run:

```bash
python -m pytest tests/engine/test_phase8_audit_temporal.py -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/engine/test_phase8_audit_temporal.py tests/engine/test_request_repository.py tests/engine/test_execution.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/request_lifecycle.py src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_audit_temporal.py
python -m ruff format --check src/ai_service_desk/engine/request_lifecycle.py src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_audit_temporal.py
```

Expected: all exit `0`.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/engine/request_lifecycle.py src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_audit_temporal.py
git commit -m "feat: enforce phase 8 temporal invariants"
```

---

### Task 8: Atomic final CAS, concurrency and initial Phase 8 security boundary

**Files:**
- Modify: `src/ai_service_desk/engine/request_repository.py`
- Create: `tests/engine/test_phase8_concurrency.py`
- Create: `tests/engine/test_phase8_security.py`

This task has one real RED source only: `test_repository_final_cas_is_atomic_under_forced_interleaving`. Security tests are added in the same task but are not artificially made to fail.

- [ ] **Step 1: RED determinístico do final CAS**

Use the Task 2 private `_before_final_cas` seam. Force two threads to complete preliminary expected-version checks before either can reach final mutation:

```python
def test_repository_final_cas_is_atomic_under_forced_interleaving(monkeypatch):
    barrier = threading.Barrier(2)
    repository, current, next_record, events = make_repository_cas_fixture()
    monkeypatch.setattr(
        repository,
        "_before_final_cas",
        lambda: barrier.wait(timeout=5),
    )
    outcomes: list[str] = []

    def worker() -> None:
        try:
            repository.save(
                next_record,
                expected_version=current.version,
                audit_events=events,
            )
        except ConcurrencyConflictError as exc:
            assert exc.reason_code == "VERSION_CONFLICT"
            outcomes.append("conflict")
        else:
            outcomes.append("saved")

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert sorted(outcomes) == ["conflict", "saved"]
```

Run:

```bash
python -m pytest tests/engine/test_phase8_concurrency.py::test_repository_final_cas_is_atomic_under_forced_interleaving -q
```

Expected: FAIL with both callers observed as saved, proving the Task 2 check/write window is not yet atomic.

- [ ] **Step 2: GREEN do CAS final sob lock**

Use one repository-local `threading.RLock`. Keep the preliminary validation, then call `_before_final_cas()`, enter the lock, re-read `current_record`, compare `current_record.version` with `expected_version` again, and only then atomically replace record + append all already-validated audit events. Allocation uses the same lock.

Run:

```bash
python -m pytest tests/engine/test_phase8_concurrency.py::test_repository_final_cas_is_atomic_under_forced_interleaving -q
```

Expected: PASS with exactly one `saved` and one `VERSION_CONFLICT`.

- [ ] **Step 3: concurrency matrix GREEN**

Add cases 36, 37 and races where two services passed preliminary compare. Double execution must end with exactly one executor call.

Run:

```bash
python -m pytest tests/engine/test_phase8_concurrency.py -q
```

Expected: PASS.

- [ ] **Step 4: create initial `test_phase8_security.py` without manufacturing RED**

Protected blob strategy must be Git-object based and Windows-safe:

```python
PROTECTED_BLOBS = {
    "src/ai_service_desk/engine/access_request.py": "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
    "src/ai_service_desk/engine/policy.py": "60a4f3ae785353009c30b37f71e1ce91865b899e",
    "src/ai_service_desk/engine/confidence.py": "ffc0c212b455978f79a3591578f323ca0e9612dc",
}

@pytest.mark.parametrize(("path", "expected_sha"), PROTECTED_BLOBS.items(), ids=("access_request", "policy", "confidence"))
def test_phase7_protected_git_blob_is_exact(path: str, expected_sha: str) -> None:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == expected_sha
```

Do not use `shell=True`. Do not use `Path.read_bytes()` to calculate protected blob SHA.

Initial runtime scan set in this task:

```text
request_lifecycle.py
request_repository.py
technician_authorization.py
approval.py
execution.py
```

Static assertions cover cases 54-56. Runtime monkeypatch tests forbid HTTP, shell/subprocess, Ollama and embeddings while exercising create/approve/execute with `FakeActionExecutor`. `subprocess` inside this test module is permitted only for the separate Git-object blob query above.

Run:

```bash
python -m pytest tests/engine/test_phase8_security.py -q
```

Expected: PASS. This is a security regression gate, not the RED source for Task 8.

- [ ] **Step 5: regressão**

```bash
python -m pytest tests/engine/test_phase8_concurrency.py tests/engine/test_phase8_security.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_concurrency.py tests/engine/test_phase8_security.py
python -m ruff format --check src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_concurrency.py tests/engine/test_phase8_security.py
```

Expected: all exit `0`.

- [ ] **Step 6: commit**

```bash
git add src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_concurrency.py tests/engine/test_phase8_security.py
git commit -m "feat: enforce atomic phase 8 concurrency boundaries"
```

---

### Task 9: Controlled-execution synthetic smoke

**Files:**
- Create: `src/ai_service_desk/engine/controlled_execution_smoke.py`
- Create: `tests/engine/test_controlled_execution_smoke.py`
- Create: `tests/fixtures/phase8_controlled_execution_cases.jsonl`
- Modify: `tests/engine/test_phase8_security.py`

The six fixture flows are exactly: approved+completed, approved+executor-failed, approved+executor-exception, rejected, denied-at-creation, denied-on-revalidation. All identities use `example.invalid` and synthetic text only.

- [ ] **Step 1: RED do smoke inexistente**

Add loader/report tests and exactly six fixture rows.

Run:

```bash
python -m pytest tests/engine/test_controlled_execution_smoke.py -q
```

Expected: collection FAIL because `controlled_execution_smoke` does not exist.

- [ ] **Step 2: GREEN do smoke**

Implement closed JSONL schema, deterministic in-memory repository/registry/fake executor, safe aggregated report and `run_controlled_execution_smoke(cases_path, report_path) -> dict`. Report may expose only case name, final state, safe reason/result/error codes, executor call count and pass boolean. No requester identity, purpose, capability, provenance IDs or arbitrary exception/result values.

Run:

```bash
python -m pytest tests/engine/test_controlled_execution_smoke.py -q
```

Expected: PASS; six cases; privacy assertions PASS; external-call monkeypatch test PASS.

- [ ] **Step 3: extend security scan to the new runtime smoke module**

Modify only the external-execution scan list in `test_phase8_security.py` to include:

```text
src/ai_service_desk/engine/controlled_execution_smoke.py
```

Keep the real-persistence scan scoped to the stateful core modules so generated smoke report JSON is not confused with request persistence.

Run:

```bash
python -m pytest tests/engine/test_phase8_security.py tests/engine/test_controlled_execution_smoke.py -q
```

Expected: PASS.

- [ ] **Step 4: regressão**

```bash
python -m pytest -q
python -m ruff check src/ai_service_desk/engine/controlled_execution_smoke.py tests/engine/test_controlled_execution_smoke.py tests/engine/test_phase8_security.py
python -m ruff format --check src/ai_service_desk/engine/controlled_execution_smoke.py tests/engine/test_controlled_execution_smoke.py tests/engine/test_phase8_security.py
```

Expected: all exit `0`.

- [ ] **Step 5: commit**

```bash
git add src/ai_service_desk/engine/controlled_execution_smoke.py tests/engine/test_controlled_execution_smoke.py tests/engine/test_phase8_security.py tests/fixtures/phase8_controlled_execution_cases.jsonl
git commit -m "test: add phase 8 controlled execution smoke"
```

---

### Task 10: CLI command for Phase 8 smoke

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_controlled_execution_cli.py`

- [ ] **Step 1: RED do parser**

Add parser test for:

```text
controlled-execution-smoke --cases cases.jsonl --report report.json
```

and tests proving safe stdout, exit 0/1 and zero construction of `OllamaClient`.

Run:

```bash
python -m pytest tests/test_controlled_execution_cli.py -q
```

Expected: FAIL because argparse does not recognize `controlled-execution-smoke`.

- [ ] **Step 2: GREEN aditivo no CLI**

Import `run_controlled_execution_smoke`, add parser args `--cases` and `--report`, and handle the command before any code path constructs `OllamaClient`. Stdout on success must include only:

```text
CONTROLLED EXECUTION SMOKE OK
Casos sinteticos: 6
Relatorio agregado local: <report path supplied by caller>
```

No identity, purpose, capability or executor raw value.

Run:

```bash
python -m pytest tests/test_controlled_execution_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/test_controlled_execution_cli.py tests/engine/test_controlled_execution_smoke.py -q
python -m pytest -q
python -m ruff check src/ai_service_desk/cli.py tests/test_controlled_execution_cli.py
python -m ruff format --check src/ai_service_desk/cli.py tests/test_controlled_execution_cli.py
```

Expected: all exit `0`.

- [ ] **Step 4: commit**

```bash
git add src/ai_service_desk/cli.py tests/test_controlled_execution_cli.py
git commit -m "feat: add phase 8 controlled execution smoke cli"
```

---

### Task 11: Exact-head Dell workflow with Phase 2 byte restoration

**Files:**
- Create: `.github/workflows/phase8-controlled-execution-smoke.yml`
- Modify: `tests/test_workflows.py`

- [ ] **Step 1: RED estrutural do workflow**

Add a new `PHASE8_WORKFLOW` constant and test requiring `workflow_dispatch`, mandatory `target_ref`, exact SHA regex, self-hosted Windows X64 ai-service-desk runner, Python 3.14, Ruff lint, Ruff format, full pytest, controlled-execution smoke, Phase 2 blob restoration and post-restoration HEAD equality. Forbid `upload-artifact`, Ollama calls, HTTP/CDM integration and writes to the manifest.

Run:

```bash
python -m pytest tests/test_workflows.py::test_phase8_controlled_execution_workflow_is_exact_head_and_non_exporting -q
```

Expected: FAIL because `.github/workflows/phase8-controlled-execution-smoke.yml` does not exist.

- [ ] **Step 2: GREEN workflow exact-head**

Workflow begins with:

```yaml
on:
  workflow_dispatch:
    inputs:
      target_ref:
        description: Exact candidate commit SHA to validate
        required: true
        type: string
```

Checkout uses `${{ inputs.target_ref }}` and immediately validates a 40-char SHA equals `git rev-parse HEAD`.

The Phase 2 restoration step must restore only `tests/fixtures/phase2_corpus.csv` from the candidate Git object:

```python
import hashlib
import json
import subprocess
from pathlib import Path

path = Path("tests/fixtures/phase2_corpus.csv")
blob = subprocess.check_output(
    ["git", "show", "HEAD:tests/fixtures/phase2_corpus.csv"]
)
path.write_bytes(blob)
after = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads(
    Path("tests/fixtures/phase2_corpus_manifest.json").read_text(encoding="utf-8")
)
expected = manifest["expected"]["raw_sha256"]
print(f"fixture_raw_sha_after={after}")
print(f"fixture_manifest_sha={expected}")
if after != expected:
    raise SystemExit("exact Git blob bytes do not match fixture manifest")
```

Immediately after restoration, PowerShell must re-run `git rev-parse HEAD`, compare it with `TARGET_REF`, and print `candidate_sha_after_fixture_restore=` only if equal. The workflow never writes the manifest and never commits the restored working-tree bytes.

Then run exactly:

```text
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m ai_service_desk controlled-execution-smoke --cases tests/fixtures/phase8_controlled_execution_cases.jsonl --report "$report"
```

Run:

```bash
python -m pytest tests/test_workflows.py::test_phase8_controlled_execution_workflow_is_exact_head_and_non_exporting -q
```

Expected: PASS.

- [ ] **Step 3: regressão**

```bash
python -m pytest tests/test_workflows.py -q
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Expected: all exit `0`.

- [ ] **Step 4: commit**

```bash
git add .github/workflows/phase8-controlled-execution-smoke.yml tests/test_workflows.py
git commit -m "ci: add phase 8 exact-head smoke workflow"
```

---

## Final Gate Plan

The implementation is not a candidate until every gate below is executed on one frozen `CANDIDATE_HEAD`.

### Gate F1: freeze exact candidate

```bash
CANDIDATE_HEAD="$(git rev-parse HEAD)"
printf 'candidate_head=%s\n' "$CANDIDATE_HEAD"
git status --short
```

Expected: 40-char SHA and clean working tree. No source/test/docs/workflow changes after this point unless a new candidate SHA is generated and every gate is rerun.

### Gate F2: Ruff and full suite

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Expected: all PASS, zero failures.

### Gate F3: historical node-ID preservation and real new-node count

Create a baseline worktree and collect both sets:

```bash
BASELINE_WORKTREE="../ai-service-desk-phase8-final-baseline"
git worktree add --detach "$BASELINE_WORKTREE" 2f583b5b4921cd7b40ddde2978a2852ecca2251d
(cd "$BASELINE_WORKTREE" && python -m pytest --collect-only -q > /tmp/phase8-baseline-nodeids.txt)
python -m pytest --collect-only -q > /tmp/phase8-candidate-nodeids.txt
python - <<'PY'
from pathlib import Path

def node_ids(path: str) -> set[str]:
    return {
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if "::" in line and not line.startswith("=")
    }

baseline = node_ids("/tmp/phase8-baseline-nodeids.txt")
candidate = node_ids("/tmp/phase8-candidate-nodeids.txt")
missing = baseline - candidate
new = candidate - baseline
print(f"baseline_nodeids={len(baseline)}")
print(f"candidate_nodeids={len(candidate)}")
print(f"missing_historical_nodeids={len(missing)}")
print(f"new_nodeids={len(new)}")
assert len(baseline) == 426
assert not missing
PY
git worktree remove "$BASELINE_WORKTREE"
```

Expected:

```text
baseline_nodeids=426
missing_historical_nodeids=0
new_nodeids=<integer printed from the real set difference>
```

No numeric new-node floor is hardcoded beyond the real collected difference.

### Gate F4: protected Phase 7 equality, both Git-object and diff evidence

Run the security tests:

```bash
python -m pytest tests/engine/test_phase8_security.py -q
```

Expected: three `git rev-parse HEAD:<path>` blob checks match the homologated SHAs, plus static/runtime security checks PASS.

Then run the mandatory baseline/candidate diff:

```bash
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d "$CANDIDATE_HEAD" -- \
  src/ai_service_desk/engine/access_request.py \
  src/ai_service_desk/engine/policy.py \
  src/ai_service_desk/engine/confidence.py
```

Expected: exit `0` and no output.

### Gate F5: zero external execution

```bash
python -m pytest tests/engine/test_phase8_security.py tests/engine/test_controlled_execution_smoke.py -q
```

Expected: PASS; no HTTP, CDMAdapter, subprocess/shell from runtime Phase 8 modules, Ollama/LLM/embedding or real request persistence.

### Gate F6: official Phase 8 smoke

```bash
rm -f /tmp/phase8-controlled-execution-report.json
python -m ai_service_desk controlled-execution-smoke \
  --cases tests/fixtures/phase8_controlled_execution_cases.jsonl \
  --report /tmp/phase8-controlled-execution-report.json
```

Expected:

```text
CONTROLLED EXECUTION SMOKE OK
Casos sinteticos: 6
```

The report privacy test must already have passed in F5.

### Gate F7: hosted CI

Only after F1-F6 pass, create a draft PR for the implementation branch; do not merge. One exact CLI path is:

```bash
PR_URL="$(gh pr create --draft --base main --head phase-8-controlled-approval-execution --title 'feat: phase 8 controlled approval and execution' --body 'Phase 8 candidate for hosted CI and exact-head Dell validation.')"
printf 'pr_url=%s\n' "$PR_URL"
```

Do not poll GitHub Actions. After the operator reports completion, inspect once:

```bash
PR_NUMBER="${PR_URL##*/}"
gh pr checks "$PR_NUMBER"
```

Expected: hosted `Python quality` CI PASS for the frozen candidate source head.

### Gate F8: Dell exact-head workflow

Dispatch the official workflow with the frozen SHA:

```bash
gh workflow run phase8-controlled-execution-smoke.yml \
  --ref phase-8-controlled-approval-execution \
  -f target_ref="$CANDIDATE_HEAD"
```

Do not poll. After the operator reports run completion, inspect the completed run once. Required Dell evidence:

```text
checked out HEAD = CANDIDATE_HEAD
Python 3.14.x
fixture_raw_sha_after = manifest raw_sha256
candidate_sha_after_fixture_restore = CANDIDATE_HEAD
Ruff check = PASS
Ruff format = PASS
full pytest = PASS
Phase 8 smoke = PASS 6/6
```

The workflow restoration is working-tree-only and does not alter `tests/fixtures/phase2_corpus.csv`, its manifest, or the Git candidate.

### Gate F9: final candidate evidence

Required report fields:

```text
historical baseline node IDs = 426
missing historical node IDs = 0
new node IDs = real collected set difference
Ruff check = PASS
Ruff format = PASS
protected Phase 7 files = equality OK
protected Git blobs = exact homologated SHAs from HEAD
zero external execution = PASS
Phase 8 smoke = PASS 6/6
hosted CI = PASS
Dell exact-head = PASS
```

No merge occurs without a later explicit merge acceptance.

---

## Plan Self-Review

Self-review must be rerun immediately before execution handoff and must report PASS only if all statements below are true:

1. **Spec coverage:** all components, eight states, eight transitions, 87 contractual cases, reason codes, lifecycle rules and scope boundaries map to concrete tasks/tests/gates.
2. **Placeholder scan:** no unresolved marker, generic edge-case instruction, missing test body reference or undefined future work remains.
3. **Signature consistency:** transition signatures use mandatory `occurred_at`; ApprovalService/ExecutionEngine expected_version signatures match repository/lifecycle usage; every referenced type/function is defined by an earlier task or the same task.
4. **Deterministic RED per task:** Tasks 1-7 and 9-11 fail because their component/behavior is absent; Task 8 fails specifically and deterministically at `test_repository_final_cas_is_atomic_under_forced_interleaving`. `test_phase8_security.py` is created in Task 8 but is not deliberately broken to manufacture RED.
5. **Windows-safe protected blob checks:** tests call `subprocess.run(["git", "rev-parse", f"HEAD:{path}"], ...)` with argument list and no shell; they never hash working-tree bytes with `Path.read_bytes()`.
6. **Execution timestamp contract:** after valid expected_version/state and policy revalidation, `ExecutionEngine` calls `operation_timestamp = clock()` exactly once and passes it explicitly to every lifecycle transition it invokes. Stale/invalid-state paths call that clock zero times. Success test proves clock calls=1, `execution_started_at == execution_finished_at`, non-regressing audit and `COMPLETED`.
7. **426 baseline:** baseline is collected from immutable `2f583b5...`; final gate requires exactly 426 historical node IDs and zero missing IDs; new count is a real set difference, not a fixed estimate.
8. **Protected files:** three Phase 7 files are never modified by implementation; both HEAD-object SHA checks and `git diff --exit-code BASELINE CANDIDATE -- protected-files` are mandatory.
9. **Security placement:** there is no isolated security Task 9. Initial `test_phase8_security.py` belongs to Task 8; Task 9 smoke modifies its external-runtime scan to include `controlled_execution_smoke.py`.
10. **Phase boundaries:** no HTTP/CDMAdapter/API fake CDM/real persistence/routing/frontend/LLM/retry is implemented; Fase 9 and Fase 10 remain future boundaries.
11. **Task count:** exactly 11 implementation tasks.

Execution must not start until this corrected plan receives explicit approval.
