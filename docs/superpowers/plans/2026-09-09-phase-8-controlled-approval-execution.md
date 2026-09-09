# Phase 8 Controlled Approval and Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar aprovação humana e execução controlada stateful, auditável e fail-closed sobre os contratos homologados da Fase 7, usando somente repository e executor em memória.

**Architecture:** A Fase 8 introduz request lifecycle, repository com optimistic concurrency, autorização explícita de técnico, ApprovalService, auditoria append-only e ExecutionEngine com FakeActionExecutor. Policy e confidence da Fase 7 são reutilizadas sem duplicação, e qualquer integração HTTP/CDM permanece fora da fase.

**Tech Stack:** Python 3.14, dataclasses, typing/Protocol, threading local para exclusão mútua, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-09-phase-8-controlled-approval-execution-design.md`

## Global Constraints

- Spec canônica aprovada: `24d411987d991b1d7f8fce04131dd19afa2c7af5`.
- Regression baseline imutável: `2f583b5b4921cd7b40ddde2978a2852ecca2251d`.
- Historical baseline: exatamente `426` node IDs. Nenhum node ID histórico pode desaparecer, ser renomeado silenciosamente, removido ou convertido em skip.
- A implementação deve iniciar no head aprovado da própria branch depois do aceite deste plano. O worktree de implementação não pode ser resetado, movido ou destacado para a spec head ou para o regression baseline.
- Estados permitidos, sem qualquer estado adicional: `TRIAGED`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `DENIED_POLICY`, `EXECUTING`, `COMPLETED`, `FAILED`.
- Transições permitidas exclusivamente: `TRIAGED -> PENDING_APPROVAL`, `TRIAGED -> DENIED_POLICY`, `PENDING_APPROVAL -> APPROVED`, `PENDING_APPROVAL -> REJECTED`, `APPROVED -> EXECUTING`, `APPROVED -> DENIED_POLICY`, `EXECUTING -> COMPLETED`, `EXECUTING -> FAILED`.
- Estados terminais da Fase 8: `REJECTED`, `DENIED_POLICY`, `COMPLETED`, `FAILED`.
- `FAILED` não possui retry, requeue, reset para `APPROVED` nem nova transição para `EXECUTING`.
- `RequestLifecycleService.create_request(context)` valida o `AccessRequestContext` homologado, reavalia `PolicyEngine.evaluate(context)` e calcula `assess_confidence(context)` separadamente.
- `create_request` não aceita `PolicyDecision` fornecido pelo caller como autoridade.
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
- `ExecutionEngine.execute` segue exatamente: get request -> validar `expected_version` -> comparar com `current.version` -> se diferente `VERSION_CONFLICT` com zero policy/executor calls -> exigir `APPROVED` -> revalidar policy -> preparar `DENIED_POLICY` ou `EXECUTING` -> repository CAS novamente -> somente então executor.
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
- Fase 9 não pode ser antecipada: nenhum adapter, credential, lookup externo, idempotência externa, HTTP ou executor real de CDM.
- Fase 10 não pode ser antecipada: nenhum routing, seleção automática de técnico, fila automática ou distribuição de workload.
- Arquivos protegidos devem permanecer byte-equivalent ao regression baseline durante toda a implementação:
  - `src/ai_service_desk/engine/access_request.py`
  - `src/ai_service_desk/engine/policy.py`
  - `src/ai_service_desk/engine/confidence.py`
- Blobs homologados desses arquivos no spec head:
  - `access_request.py`: `f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d`
  - `policy.py`: `60a4f3ae785353009c30b37f71e1ce91865b899e`
  - `confidence.py`: `ffc0c212b455978f79a3591578f323ca0e9612dc`
- `tests/fixtures/phase2_corpus.csv` e `tests/fixtures/phase2_corpus_manifest.json` não podem ser alterados em Git.
- Escopo proibido: HTTP, `requests/httpx/urllib` para execução, `CDMAdapter`, API fake do CDM, SQLite, JSON persistente, banco, routing, frontend, LLM/Ollama/embedding e retry de `FAILED`.

---

## Existing Phase 7 Patterns Inspected

Antes da decomposição foram inspecionados os padrões homologados existentes e este plano os preserva:

- `src/ai_service_desk/cli.py`: comandos smoke são subcommands aditivos; `policy-smoke` recebe `--cases` e `--report` e retorna antes de qualquer construção de `OllamaClient`.
- `src/ai_service_desk/engine/policy_smoke.py`: loader JSONL com schema fechado, execução determinística, relatório agregado privacy-safe e escrita pelo helper `atomic_json`.
- `tests/engine/test_policy_smoke.py`: valida schema, quantidade exata de casos, privacy e runtime zero-external com monkeypatch de requests, subprocess, Ollama e embeddings.
- `tests/test_policy_cli.py`: valida parser, stdout seguro, ausência de dependências Ollama e exit code não-zero em smoke reprovado.
- `.github/workflows/phase7-policy-smoke.yml`: `workflow_dispatch`, `target_ref` exato, runner Windows self-hosted, Python 3.14, restauração byte-exact do fixture Phase 2 a partir do blob do próprio `HEAD`, Ruff, suíte completa e smoke.
- `tests/test_workflows.py`: valida workflows estruturalmente e proíbe export/artifacts e superfícies não autorizadas.
- `.github/workflows/ci.yml`: PR hosted CI usa Python 3.14, Ruff lint, Ruff format e pytest.
- Nenhum desses padrões autoriza refatoração dos três módulos protegidos da Fase 7.

---

## Planned File Map

### Create

- `src/ai_service_desk/engine/request_lifecycle.py`: estados, record, audit event, erros/invariantes, clock UTC e `RequestLifecycleService`.
- `src/ai_service_desk/engine/request_repository.py`: `RequestRepository`, `InMemoryRequestRepository`, IDs determinísticos, optimistic concurrency e append-only audit.
- `src/ai_service_desk/engine/technician_authorization.py`: identidade de técnico, entradas do registry, validação fail-closed, índices únicos e capability exata.
- `src/ai_service_desk/engine/approval.py`: `ApprovalService`, stale ordering, autorização e self-decision.
- `src/ai_service_desk/engine/execution.py`: `ActionExecutionResult`, `ActionExecutor`, `FakeActionExecutor` e `ExecutionEngine`.
- `src/ai_service_desk/engine/controlled_execution_smoke.py`: smoke sintético determinístico e privacy-safe.
- `tests/engine/phase8_helpers.py`: factories sintéticas compartilhadas pelos testes da Fase 8.
- `tests/engine/test_request_lifecycle.py`: state machine, record/audit contracts, criação e transições.
- `tests/engine/test_request_repository.py`: IDs, create/save, version e snapshots de audit.
- `tests/engine/test_phase8_audit_temporal.py`: timezone-awareness, cronologia e monotonicidade entre versões/eventos.
- `tests/engine/test_technician_authorization.py`: registry fail-closed, conflitos e autorização exata.
- `tests/engine/test_approval.py`: approve/reject, capability, self-decision e stale ordering.
- `tests/engine/test_execution.py`: gates de execução, policy revalidation, executor result e falhas seguras.
- `tests/engine/test_phase8_concurrency.py`: CAS concorrente, dupla decisão, dupla execução e `expected_version` em todos os entrypoints.
- `tests/engine/test_phase8_security.py`: protected blob hashes, forbidden surfaces e zero external execution.
- `tests/engine/test_controlled_execution_smoke.py`: schema, seis fluxos, privacy e runtime zero-external.
- `tests/test_controlled_execution_cli.py`: parser, stdout seguro e exit codes.
- `tests/fixtures/phase8_controlled_execution_cases.jsonl`: seis casos sintéticos sem dados corporativos.
- `.github/workflows/phase8-controlled-execution-smoke.yml`: workflow manual exact-head para Dell.

### Modify

- `src/ai_service_desk/cli.py`: adicionar somente `controlled-execution-smoke` e dispatch correspondente.
- `tests/test_workflows.py`: adicionar somente o contrato do workflow da Fase 8.

### Must remain untouched

- `src/ai_service_desk/engine/access_request.py`
- `src/ai_service_desk/engine/policy.py`
- `src/ai_service_desk/engine/confidence.py`
- `tests/fixtures/phase2_corpus.csv`
- `tests/fixtures/phase2_corpus_manifest.json`

---

## Execution Preflight

- [ ] **Preflight 1: registrar o execution start real**

Run:

```bash
git branch --show-current
git status --short
EXECUTION_START_HEAD="$(git rev-parse HEAD)"
printf 'execution_start_head=%s\n' "$EXECUTION_START_HEAD"
git merge-base --is-ancestor 24d411987d991b1d7f8fce04131dd19afa2c7af5 "$EXECUTION_START_HEAD"
git diff --name-only 24d411987d991b1d7f8fce04131dd19afa2c7af5 "$EXECUTION_START_HEAD"
```

Expected:

```text
branch = phase-8-controlled-approval-execution
git status --short = empty
git merge-base --is-ancestor exit = 0
diff from spec head to execution start contains only docs/superpowers/plans/2026-09-09-phase-8-controlled-approval-execution.md
```

- [ ] **Preflight 2: protected equality before implementation**

Run:

```bash
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d "$EXECUTION_START_HEAD" -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
```

Expected: exit `0` with empty diff.

- [ ] **Preflight 3: collect immutable historical baseline in a separate worktree**

Run:

```bash
REPO_ROOT="$(pwd)"
BASELINE_WORKTREE="$(dirname "$REPO_ROOT")/ai-service-desk-phase8-baseline"
BASELINE_IDS="$(mktemp)"
git worktree add --detach "$BASELINE_WORKTREE" 2f583b5b4921cd7b40ddde2978a2852ecca2251d
(
  cd "$BASELINE_WORKTREE"
  python -m pytest --collect-only -q | grep '::' | sort -u > "$BASELINE_IDS"
)
python - "$BASELINE_IDS" <<'PY'
from pathlib import Path
import sys
ids = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
print(f"baseline_nodeids={len(ids)}")
assert len(ids) == 426
PY
git worktree remove "$BASELINE_WORKTREE"
rm -f "$BASELINE_IDS"
```

Expected: prints `baseline_nodeids=426`, assertion succeeds, implementation worktree HEAD unchanged.

---

## Contract Matrix Coverage Map

Every numbered requirement from the canonical 87-case matrix is mapped below to an exact future test node or final gate.

| Case | Planned test/gate |
| ---: | --- |
| 1 | `test_create_request_require_approval_enters_pending_approval` |
| 2 | `test_create_request_deny_enters_auditable_denied_policy` |
| 3 | `test_denied_policy_rejects_human_decision_with_current_version[approve]` |
| 4 | `test_denied_policy_rejects_human_decision_with_current_version[reject]` |
| 5 | `test_technician_without_capability_cannot_decide[approve]` |
| 6 | `test_technician_without_capability_cannot_decide[reject]` |
| 7 | `test_unregistered_technician_cannot_decide` |
| 8 | `test_divergent_registered_identity_cannot_decide` |
| 9 | `test_requester_cannot_decide_own_request[username]` |
| 10 | `test_requester_cannot_decide_own_request[email]` |
| 11 | `test_requester_self_decision_normalization_is_casefolded_and_trimmed` |
| 12 | `test_authorized_technician_can_decide_pending_request[approve]` |
| 13 | `test_authorized_technician_can_decide_pending_request[reject]` |
| 14 | `test_approval_service_has_no_execution_dependency[approve]` |
| 15 | `test_approval_service_has_no_execution_dependency[reject]` |
| 16 | `test_execute_rejects_non_approved_states_without_executor[PENDING_APPROVAL]` |
| 17 | `test_execute_rejects_non_approved_states_without_executor[DENIED_POLICY]` |
| 18 | `test_execute_rejects_non_approved_states_without_executor[REJECTED]` |
| 19 | `test_execute_rejects_non_approved_states_without_executor[COMPLETED]` |
| 20 | `test_execute_rejects_non_approved_states_without_executor[FAILED]` |
| 21 | `test_execute_revalidates_policy_before_executor` |
| 22 | `test_revalidation_deny_moves_to_denied_policy_with_zero_executor_calls` |
| 23 | `test_revalidation_deny_moves_to_denied_policy_with_zero_executor_calls` |
| 24 | `test_executor_receives_already_persisted_executing_record` |
| 25 | `test_executor_success_completes_request` |
| 26 | `test_executor_failure_marks_request_failed` |
| 27 | `test_executor_exception_is_sanitized_into_failed` |
| 28 | `test_executor_exception_payload_is_absent_from_record_and_audit` |
| 29 | `test_invalid_executor_results_fail_closed_without_persisting_payload` |
| 30 | `test_failed_request_is_terminal_without_retry` |
| 31 | `test_request_id_sequence_is_deterministic_per_repository_instance[first]` |
| 32 | `test_request_id_sequence_is_deterministic_per_repository_instance[monotonic]` |
| 33 | `test_request_id_sequence_is_deterministic_per_repository_instance[new-instance]` |
| 34 | `test_stale_human_decision_fails_before_state_or_authorization[approve]` |
| 35 | `test_stale_human_decision_fails_before_state_or_authorization[reject]` |
| 36 | `test_two_human_decisions_only_one_final_cas_wins` |
| 37 | `test_two_execute_callers_make_exactly_one_executor_call` |
| 38 | `test_save_requires_exactly_next_version` |
| 39 | `test_persisted_timestamps_are_timezone_aware` |
| 40 | `test_naive_timestamps_are_rejected_before_write` |
| 41 | `test_audit_for_returns_tuple_snapshot` |
| 42 | `test_old_audit_snapshot_remains_immutable_prefix_after_append` |
| 43 | `test_repository_exposes_no_audit_update_or_delete_api` |
| 44 | `test_pending_creation_audit_is_request_created_then_policy_requires_approval` |
| 45 | `test_denied_creation_audit_is_request_created_then_policy_denied` |
| 46 | `test_completed_flow_has_canonical_audit_order` |
| 47 | `test_failed_flow_audits_execution_started_before_execution_failed` |
| 48 | `test_revalidation_updates_latest_policy_without_replacing_creation_policy` |
| 49 | `test_save_preserves_context_across_versions` |
| 50 | `test_save_preserves_confidence_across_versions` |
| 51 | `test_phase7_protected_files_keep_homologated_git_blob_hashes[access_request.py]` |
| 52 | `test_phase7_protected_files_keep_homologated_git_blob_hashes[policy.py]` |
| 53 | `test_phase7_protected_files_keep_homologated_git_blob_hashes[confidence.py]` |
| 54 | `test_phase8_runtime_sources_have_no_external_execution_surface[http]` |
| 55 | `test_phase8_runtime_sources_have_no_external_execution_surface[llm]` |
| 56 | `test_phase8_runtime_sources_have_no_real_persistence_surface` |
| 57 | `test_controlled_execution_smoke_passes_all_six_contract_flows` |
| 58 | Final Gate F3 requires `baseline_nodeids=426` and `missing_historical_nodeids=0` |
| 59 | `test_invalid_registry_entry_fails_closed_before_indexing` |
| 60 | `test_invalid_capability_configuration_is_rejected[non-string]` |
| 61 | `test_invalid_capability_configuration_is_rejected[wildcard-prefix-fuzzy]` |
| 62 | `test_normalized_identity_collisions_are_conflicts[technician_id]` |
| 63 | `test_normalized_identity_collisions_are_conflicts[username]` |
| 64 | `test_normalized_identity_collisions_are_conflicts[email]` |
| 65 | `test_invalid_registry_entry_precedes_duplicate_detection` |
| 66 | `test_invalid_executor_results_fail_closed_without_persisting_payload[success-int]` |
| 67 | `test_invalid_executor_results_fail_closed_without_persisting_payload[success-string]` |
| 68 | `test_invalid_executor_results_fail_closed_without_persisting_payload[empty-code]` |
| 69 | `test_invalid_executor_results_fail_closed_without_persisting_payload[spaced-code]` |
| 70 | `test_invalid_executor_results_fail_closed_without_persisting_payload[unhashable-code]` |
| 71 | `test_invalid_executor_results_fail_closed_without_persisting_payload[wrong-object]` |
| 72 | `test_record_chronology_regression_is_rejected_before_write[created-updated]` |
| 73 | `test_record_chronology_regression_is_rejected_before_write[created-decided]` |
| 74 | `test_record_chronology_regression_is_rejected_before_write[decided-started]` |
| 75 | `test_record_chronology_regression_is_rejected_before_write[started-finished]` |
| 76 | `test_audit_timestamp_cannot_move_backward` |
| 77 | `test_equal_timestamps_are_allowed_and_order_uses_version_and_append_order` |
| 78 | `test_expected_version_contract_is_enforced_by_every_entrypoint[True]` |
| 79 | `test_expected_version_contract_is_enforced_by_every_entrypoint[False]` |
| 80 | `test_expected_version_contract_is_enforced_by_every_entrypoint[float]` |
| 81 | `test_expected_version_contract_is_enforced_by_every_entrypoint[string]` |
| 82 | `test_expected_version_contract_is_enforced_by_every_entrypoint[None]` |
| 83 | `test_stale_execute_fails_before_policy_and_executor` |
| 84 | `test_updated_at_cannot_move_backward_between_versions` |
| 85 | `test_equal_updated_at_between_versions_is_allowed` |
| 86 | `test_pending_creation_reuses_one_initial_timestamp` |
| 87 | `test_denied_creation_reuses_one_initial_timestamp` |

---

### Task 1: Lifecycle domain contracts and closed state machine

**Files:**
- Create: `src/ai_service_desk/engine/request_lifecycle.py`
- Create: `tests/engine/phase8_helpers.py`
- Create: `tests/engine/test_request_lifecycle.py`

**Interfaces:**
- Consumes existing `AccessRequestContext`, `PolicyDecision`, `ConfidenceAssessment` by import only.
- Produces `RequestState`, `REQUEST_STATES`, `ALLOWED_TRANSITIONS`, `Phase8DomainError`, `InvalidStateTransitionError`, `RecordInvariantError`, `AuditEventValidationError`, `AccessRequestRecord`, `AuditEvent`, `utc_now()`, `validate_access_request_record(record)`, `validate_audit_event(event)`.
- `RequestLifecycleService` is defined only in Task 4, after `RequestRepository` exists.

- [ ] **Step 1: write the failing domain-contract tests**

In `tests/engine/test_request_lifecycle.py`, add exact-state and exact-transition assertions:

```python
EXPECTED_STATES = {
    "TRIAGED",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "DENIED_POLICY",
    "EXECUTING",
    "COMPLETED",
    "FAILED",
}
EXPECTED_TRANSITIONS = {
    ("TRIAGED", "PENDING_APPROVAL"),
    ("TRIAGED", "DENIED_POLICY"),
    ("PENDING_APPROVAL", "APPROVED"),
    ("PENDING_APPROVAL", "REJECTED"),
    ("APPROVED", "EXECUTING"),
    ("APPROVED", "DENIED_POLICY"),
    ("EXECUTING", "COMPLETED"),
    ("EXECUTING", "FAILED"),
}
```

Add `test_record_validation_rejects_state_field_incoherence` with these rows: pending plus decision fields, approved without decision fields, executing without start timestamp, completed without finish timestamp, completed without result code, failed without error code, creation-denied record with human decision fields.

Add `test_audit_event_validation_rejects_invalid_actor_and_version` covering invalid actor type, bool record version, nonpositive record version, malformed event type, malformed reason code and naive `occurred_at`.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: import/collection failure because `ai_service_desk.engine.request_lifecycle` does not exist.

- [ ] **Step 3: implement the minimal immutable domain contracts**

`request_lifecycle.py` must define the exact eight-value `RequestState` Literal, exact `REQUEST_STATES`, exact `ALLOWED_TRANSITIONS`, frozen `AccessRequestRecord`, frozen `AuditEvent`, timezone-aware validator and lifecycle error base carrying `.reason_code`.

`AccessRequestRecord` exact fields:

```text
request_id
version
state
context
creation_policy
latest_policy
confidence
created_at
updated_at
decided_by
decided_at
execution_started_at
execution_finished_at
execution_result_code
execution_error_code
```

`AuditEvent` exact fields:

```text
request_id
event_type
actor_type
actor_id
from_state
to_state
record_version
reason_code
policy_id
occurred_at
```

Use local symbolic-code regex `^[A-Z][A-Z0-9_]{2,119}$`. Reject bool as integer for `version` and `record_version`. Enforce the state/optional-field rows from Step 1. Task 3 adds chronological relations; Task 1 already rejects naive datetimes.

`tests/engine/phase8_helpers.py` defines synthetic `valid_access_context()`, `fixed_aware_datetime()`, `require_approval_policy_decision()`, `deny_policy_decision()` and `high_confidence()`, using only `example.invalid` identities.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: PASS with zero failures.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all commands exit `0`; protected diff is empty.

- [ ] **Step 6: commit Task 1**

```bash
git add src/ai_service_desk/engine/request_lifecycle.py tests/engine/phase8_helpers.py tests/engine/test_request_lifecycle.py
git diff --cached --name-only
git commit -m "feat: add phase 8 lifecycle contracts"
```

Expected staged files: exactly the three Task 1 files.

---

### Task 2: In-memory repository, deterministic IDs and sequential version contract

**Files:**
- Create: `src/ai_service_desk/engine/request_repository.py`
- Create: `tests/engine/test_request_repository.py`

**Interfaces:**
- Consumes Task 1 record/audit types and validators.
- Produces `RequestRepository`, `InMemoryRequestRepository`, `RequestNotFoundError`, `ExpectedVersionValidationError`, `ConcurrencyConflictError`, `validate_expected_version(value: object) -> int`.

`RequestRepository` public methods:

```text
allocate_request_id() -> str
create(record: AccessRequestRecord, audit_events: tuple[AuditEvent, ...]) -> AccessRequestRecord
get(request_id: str) -> AccessRequestRecord
save(record: AccessRequestRecord, expected_version: int, audit_events: tuple[AuditEvent, ...]) -> AccessRequestRecord
audit_for(request_id: str) -> tuple[AuditEvent, ...]
```

`audit_events` and `expected_version` are keyword-only in `create`/`save`.

- [ ] **Step 1: write RED repository tests**

Add:

```text
test_request_id_sequence_is_deterministic_per_repository_instance
test_create_requires_triaged_version_one_and_request_created_event
test_get_missing_request_raises_request_not_found
test_save_requires_exactly_next_version
test_stale_save_raises_version_conflict_without_mutation
test_save_preserves_request_id_context_creation_policy_confidence_created_at
test_save_preserves_context_across_versions
test_save_preserves_confidence_across_versions
test_audit_for_returns_tuple_snapshot
test_old_audit_snapshot_remains_immutable_prefix_after_append
test_repository_exposes_no_audit_update_or_delete_api
test_expected_version_validator_rejects_invalid_runtime_values
```

The ID test asserts `REQ-000001`, `REQ-000002`, `REQ-000003`, then a fresh repository starts again at `REQ-000001`.

The expected-version parameter rows are `True`, `False`, `3.0`, `"3"`, `None`, `0`, `-1`, all with `EXPECTED_VERSION_INVALID`.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_request_repository.py -q
```

Expected: import failure because `request_repository.py` does not exist.

- [ ] **Step 3: implement sequential repository semantics**

`validate_expected_version` must use exact-type validation:

```python
if type(value) is not int or value <= 0:
    raise ExpectedVersionValidationError(
        "EXPECTED_VERSION_INVALID",
        "expected_version deve ser int positivo sem coercao.",
    )
return value
```

Repository state:

```text
_records: dict[str, AccessRequestRecord]
_audit: dict[str, list[AuditEvent]]
_next_id: int
_lock: threading.RLock
```

Task 2 proves sequential semantics. `save` validates the expected version and current version before the final mutation section. This intentionally does not claim forced-interleaving atomicity yet; Task 8 introduces the deterministic concurrency RED and moves read/compare/validate/mutate into one lock scope.

`create` validates record and every event before mutation. `save` validates exact next version, immutable fields and event alignment. Task 3 adds chronology against current record and existing audit tail.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_request_repository.py -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 2**

```bash
git add src/ai_service_desk/engine/request_repository.py tests/engine/test_request_repository.py
git diff --cached --name-only
git commit -m "feat: add in-memory request repository"
```

Expected staged files: exactly the two Task 2 files.

---

### Task 3: Audit chronology and temporal invariants

**Files:**
- Modify: `src/ai_service_desk/engine/request_lifecycle.py`
- Modify: `src/ai_service_desk/engine/request_repository.py`
- Create: `tests/engine/test_phase8_audit_temporal.py`

**Interfaces:**
- Completes pre-write temporal validation. No new persistence API.

- [ ] **Step 1: write RED temporal tests**

Add:

```text
test_persisted_timestamps_are_timezone_aware
test_naive_timestamps_are_rejected_before_write
test_record_chronology_regression_is_rejected_before_write[created-updated]
test_record_chronology_regression_is_rejected_before_write[created-decided]
test_record_chronology_regression_is_rejected_before_write[decided-started]
test_record_chronology_regression_is_rejected_before_write[started-finished]
test_audit_timestamp_cannot_move_backward
test_equal_timestamps_are_allowed_and_order_uses_version_and_append_order
test_updated_at_cannot_move_backward_between_versions
test_equal_updated_at_between_versions_is_allowed
```

Every invalid record row asserts `RECORD_INVARIANT_INVALID`, stored record unchanged and audit tuple unchanged. Audit regression asserts `AUDIT_EVENT_INVALID` and zero append.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_phase8_audit_temporal.py -q
```

Expected: failures on missing cross-field chronology, audit-tail chronology or inter-version `updated_at` checks.

- [ ] **Step 3: implement chronology before mutation**

`validate_access_request_record` adds:

```text
created_at <= updated_at
created_at <= decided_at when decided_at exists
decided_at <= execution_started_at when both exist
execution_started_at <= execution_finished_at when both exist
```

`InMemoryRequestRepository.save` adds before mutation:

```text
new_record.updated_at >= current_record.updated_at
```

Audit batch validation compares the existing tail to the first new event and each pair inside the batch. Any backward timestamp raises `AUDIT_EVENT_INVALID`. Equality remains valid.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_phase8_audit_temporal.py tests/engine/test_request_repository.py tests/engine/test_request_lifecycle.py -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 3**

```bash
git add src/ai_service_desk/engine/request_lifecycle.py src/ai_service_desk/engine/request_repository.py tests/engine/test_phase8_audit_temporal.py
git diff --cached --name-only
git commit -m "feat: enforce phase 8 temporal invariants"
```

Expected staged files: exactly the three Task 3 files.

---

### Task 4: RequestLifecycleService creation and named transitions

**Files:**
- Modify: `src/ai_service_desk/engine/request_lifecycle.py`
- Modify: `tests/engine/phase8_helpers.py`
- Modify: `tests/engine/test_request_lifecycle.py`

**Interfaces:**
- Consumes `RequestRepository`, `PolicyEngine.evaluate(context)`, `assess_confidence(context)`.
- Produces `RequestLifecycleService`.
- Avoid circular import by importing `RequestRepository` only under `TYPE_CHECKING` and using a quoted annotation in `request_lifecycle.py`.

Exact public methods:

```text
create_request(context: AccessRequestContext) -> AccessRequestRecord
transition_to_approved(record, technician_id, expected_version, occurred_at) -> AccessRequestRecord
transition_to_rejected(record, technician_id, expected_version, occurred_at) -> AccessRequestRecord
transition_to_executing(record, policy, expected_version, occurred_at) -> AccessRequestRecord
transition_to_denied_policy(record, policy, expected_version, occurred_at) -> AccessRequestRecord
transition_to_completed(record, result_code, expected_version, occurred_at) -> AccessRequestRecord
transition_to_failed(record, error_code, result_code, expected_version, occurred_at) -> AccessRequestRecord
```

All arguments after `record` are keyword-only. No public generic `transition(to_state)` API is allowed.

- [ ] **Step 1: write RED lifecycle-service tests**

Add:

```text
test_create_request_require_approval_enters_pending_approval
test_create_request_deny_enters_auditable_denied_policy
test_create_request_calls_policy_engine_and_confidence_independently
test_pending_creation_reuses_one_initial_timestamp
test_denied_creation_reuses_one_initial_timestamp
test_pending_creation_audit_is_request_created_then_policy_requires_approval
test_denied_creation_audit_is_request_created_then_policy_denied
test_invalid_transition_is_rejected_without_write
```

For the one-timestamp tests, inject a clock that returns a later invalid/backward value on a second call. Assert the clock is called exactly once and both initial versions/events use the first timestamp.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_request_lifecycle.py -q
```

Expected: failures because `RequestLifecycleService` and named transition methods are absent.

- [ ] **Step 3: implement lifecycle service**

Creation order is exact:

```text
validate_access_request_context(context)
creation_policy = policy_engine.evaluate(context)
confidence = assess_confidence(context)
initial_timestamp = clock() exactly once
request_id = repository.allocate_request_id()
repository.create(TRIAGED version=1 + REQUEST_CREATED at initial_timestamp)
if creation_policy is DENY: TRIAGED -> DENIED_POLICY version=2 using initial_timestamp
if creation_policy is REQUIRE_APPROVAL: TRIAGED -> PENDING_APPROVAL version=2 using initial_timestamp
return persisted version=2
```

Named transition methods verify their exact source/destination pair, build a new frozen record with `version + 1`, preserve immutable fields, create one canonical audit event, then call `repository.save` with the supplied `expected_version`.

Canonical events:

```text
REQUEST_CREATED
POLICY_REQUIRES_APPROVAL
POLICY_DENIED_AT_CREATION
REQUEST_APPROVED
REQUEST_REJECTED
POLICY_DENIED_BEFORE_EXECUTION
EXECUTION_STARTED
EXECUTION_COMPLETED
EXECUTION_FAILED
```

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_request_lifecycle.py tests/engine/test_request_repository.py tests/engine/test_phase8_audit_temporal.py -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 4**

```bash
git add src/ai_service_desk/engine/request_lifecycle.py tests/engine/phase8_helpers.py tests/engine/test_request_lifecycle.py
git diff --cached --name-only
git commit -m "feat: add controlled request lifecycle service"
```

Expected staged files: exactly the three Task 4 files.

---

### Task 5: TechnicianAuthorizationRegistry fail-closed configuration

**Files:**
- Create: `src/ai_service_desk/engine/technician_authorization.py`
- Create: `tests/engine/test_technician_authorization.py`

**Interfaces:**
- Produces `TechnicianIdentity`, `TechnicianAuthorizationEntry`, `TechnicianRegistryConfigurationError`, `TechnicianAuthorizationError`, `TechnicianAuthorizationRegistry`.

Exact shapes:

```text
TechnicianIdentity(technician_id: str, username: str, name: str, email: str)
TechnicianAuthorizationEntry(identity: TechnicianIdentity, capabilities: tuple[str, ...])
TechnicianAuthorizationRegistry(entries: Sequence[TechnicianAuthorizationEntry])
require_capability(technician: TechnicianIdentity, capability: str) -> None
```

Identity bounds: `technician_id <= 120`, `username <= 120`, `name <= 180`, `email <= 320`.

- [ ] **Step 1: write RED registry tests**

Invalid configuration rows:

```text
non-TechnicianAuthorizationEntry
non-TechnicianIdentity identity
empty technician_id
empty username
empty name
empty email
oversized identity fields
capability runtime value []
empty capability
lowercase cdm_access_request
wildcard CDM_*
prefix expression CDM_ACCESS_*
fuzzy/spaced CDM ACCESS REQUEST
```

All produce `TECHNICIAN_REGISTRY_INVALID`.

Collision rows use valid entries whose normalized `technician_id`, `username` or `email` collide and must produce `TECHNICIAN_REGISTRY_CONFLICT`.

Add `test_invalid_registry_entry_precedes_duplicate_detection`: one invalid entry plus a valid duplicate pair must return `TECHNICIAN_REGISTRY_INVALID`, proving no index is built before full validation.

Authorization tests prove exact registered identity + exact capability passes; unregistered technician, divergent identity, missing capability and invalid runtime capability fail closed.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_technician_authorization.py -q
```

Expected: import failure because `technician_authorization.py` does not exist.

- [ ] **Step 3: implement two-pass validation/indexing**

Algorithm:

```text
source = tuple(entries)
validated = validate every source entry without building indexes
if any invalid entry: raise TECHNICIAN_REGISTRY_INVALID
build normalized technician_id, username, email indexes
if any normalized key already exists: raise TECHNICIAN_REGISTRY_CONFLICT
```

Capability validation checks `isinstance(value, str)` before regex or membership. Capability text is not normalized into validity. `require_capability` uses normalized technician ID for lookup, verifies the presented identity against the stored canonical identity, and checks exact capability membership.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_technician_authorization.py -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 5**

```bash
git add src/ai_service_desk/engine/technician_authorization.py tests/engine/test_technician_authorization.py
git diff --cached --name-only
git commit -m "feat: add technician authorization registry"
```

Expected staged files: exactly the two Task 5 files.

---

### Task 6: ApprovalService, self-decision and deterministic stale ordering

**Files:**
- Create: `src/ai_service_desk/engine/approval.py`
- Create: `tests/engine/test_approval.py`

**Interfaces:**
- Consumes repository, lifecycle, registry and `validate_expected_version`.
- Produces `SelfDecisionError`, `ApprovalService.approve`, `ApprovalService.reject`.

Exact constructor/API:

```text
ApprovalService(repository: RequestRepository, lifecycle: RequestLifecycleService,
                registry: TechnicianAuthorizationRegistry,
                clock: Callable[[], datetime] = utc_now)
approve(request_id: str, technician: TechnicianIdentity, expected_version: int) -> AccessRequestRecord
reject(request_id: str, technician: TechnicianIdentity, expected_version: int) -> AccessRequestRecord
```

`clock` and `expected_version` are keyword-only.

- [ ] **Step 1: write RED approval tests**

Add:

```text
test_denied_policy_rejects_human_decision_with_current_version[approve]
test_denied_policy_rejects_human_decision_with_current_version[reject]
test_technician_without_capability_cannot_decide[approve]
test_technician_without_capability_cannot_decide[reject]
test_unregistered_technician_cannot_decide
test_divergent_registered_identity_cannot_decide
test_requester_cannot_decide_own_request[username]
test_requester_cannot_decide_own_request[email]
test_requester_self_decision_normalization_is_casefolded_and_trimmed
test_authorized_technician_can_decide_pending_request[approve]
test_authorized_technician_can_decide_pending_request[reject]
test_approval_service_has_no_execution_dependency[approve]
test_approval_service_has_no_execution_dependency[reject]
test_stale_human_decision_fails_before_state_or_authorization[approve]
test_stale_human_decision_fails_before_state_or_authorization[reject]
test_invalid_expected_version_fails_before_state_and_authorization
```

The no-execution tests use `inspect.signature(ApprovalService.__init__)` and assert constructor parameters do not include `executor` or `execution_engine`; they also run approve/reject and verify only repository/audit state changed.

The stale tests intentionally combine stale version with a state/technician that would fail later and assert `VERSION_CONFLICT`, proving ordering.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_approval.py -q
```

Expected: import failure because `approval.py` does not exist.

- [ ] **Step 3: implement exact approval gate order**

Both methods share this sequence:

```text
record = repository.get(request_id)
validate_expected_version(expected_version)
if expected_version != record.version: VERSION_CONFLICT
if record.state != PENDING_APPROVAL: INVALID_STATE_TRANSITION
registry.require_capability(technician, record.context.capability)
compare technician/requester username and email via strip().casefold()
if either matches: SELF_DECISION_NOT_ALLOWED
occurred_at = clock()
call lifecycle transition_to_approved or transition_to_rejected
lifecycle calls repository.save with original expected_version for final CAS
```

No executor, policy, confidence or routing dependency is allowed in `ApprovalService`.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_approval.py tests/engine/test_technician_authorization.py -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 6**

```bash
git add src/ai_service_desk/engine/approval.py tests/engine/test_approval.py
git diff --cached --name-only
git commit -m "feat: add controlled human approval service"
```

Expected staged files: exactly the two Task 6 files.

---

### Task 7: ExecutionEngine, ActionExecutor contract and safe failure handling

**Files:**
- Create: `src/ai_service_desk/engine/execution.py`
- Create: `tests/engine/test_execution.py`

**Interfaces:**
- Consumes repository, lifecycle, `PolicyEngine`, `PolicyRule`, `validate_expected_version`.
- Produces `ActionExecutionResult`, `ActionExecutor`, `FakeActionExecutor`, `ExecutionEngine`.

Exact public API:

```text
ActionExecutionResult(success: bool, result_code: str)
ActionExecutor.execute(request: AccessRequestRecord) -> ActionExecutionResult
FakeActionExecutor(result: object, exception: Exception | None)
FakeActionExecutor.call_count -> int
FakeActionExecutor.calls -> tuple[str, ...]
ExecutionEngine(repository: RequestRepository, lifecycle: RequestLifecycleService,
                policy_engine: PolicyEngine, executor: ActionExecutor,
                clock: Callable[[], datetime] = utc_now)
ExecutionEngine.execute(request_id: str, expected_version: int) -> AccessRequestRecord
```

Constructor keyword defaults: fake result defaults to `ActionExecutionResult(True, "FAKE_EXECUTION_SUCCEEDED")`, exception defaults to `None`; service clock and execute expected_version are keyword-only.

- [ ] **Step 1: write RED execution tests**

Add:

```text
test_execute_rejects_non_approved_states_without_executor[PENDING_APPROVAL]
test_execute_rejects_non_approved_states_without_executor[DENIED_POLICY]
test_execute_rejects_non_approved_states_without_executor[REJECTED]
test_execute_rejects_non_approved_states_without_executor[COMPLETED]
test_execute_rejects_non_approved_states_without_executor[FAILED]
test_stale_execute_fails_before_policy_and_executor
test_execute_revalidates_policy_before_executor
test_revalidation_deny_moves_to_denied_policy_with_zero_executor_calls
test_executor_receives_already_persisted_executing_record
test_executor_success_completes_request
test_executor_failure_marks_request_failed
test_executor_exception_is_sanitized_into_failed
test_executor_exception_payload_is_absent_from_record_and_audit
test_invalid_executor_results_fail_closed_without_persisting_payload[success-int]
test_invalid_executor_results_fail_closed_without_persisting_payload[success-string]
test_invalid_executor_results_fail_closed_without_persisting_payload[empty-code]
test_invalid_executor_results_fail_closed_without_persisting_payload[spaced-code]
test_invalid_executor_results_fail_closed_without_persisting_payload[unhashable-code]
test_invalid_executor_results_fail_closed_without_persisting_payload[wrong-object]
test_failed_request_is_terminal_without_retry
test_completed_flow_has_canonical_audit_order
test_failed_flow_audits_execution_started_before_execution_failed
test_revalidation_updates_latest_policy_without_replacing_creation_policy
```

For revalidation DENY, construct a real custom `PolicyEngine` with one valid `PolicyRule` matching the CDM SOLICITANTE context and `decision="DENY"`.

For exception tests, use a unique marker in the exception message and assert the marker is absent from `repr(record)` and every persisted audit field.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_execution.py -q
```

Expected: import failure because `execution.py` does not exist.

- [ ] **Step 3: implement exact execution sequence and result validation**

Result validation order is exact:

```text
type(result) is ActionExecutionResult
type(result.success) is bool
isinstance(result.result_code, str)
result.result_code fullmatches ^[A-Z][A-Z0-9_]{2,119}$
```

Execution order:

```text
record = repository.get(request_id)
validate_expected_version(expected_version)
if expected_version != record.version: VERSION_CONFLICT
if record.state != APPROVED: INVALID_STATE_TRANSITION
policy = policy_engine.evaluate(record.context)
if policy.decision == DENY:
    lifecycle.transition_to_denied_policy using original expected_version
    return denied record
occurred_at = clock()
executing = lifecycle.transition_to_executing using original expected_version
result = executor.execute(executing) exactly once
valid success -> transition_to_completed using expected_version=executing.version
valid failure -> transition_to_failed(result_code=code, error_code=code, expected_version=executing.version)
invalid result -> transition_to_failed(result_code=None, error_code=EXECUTOR_INVALID_RESULT, expected_version=executing.version)
Exception -> transition_to_failed(result_code=None, error_code=EXECUTOR_EXCEPTION, expected_version=executing.version)
```

Catch `Exception`, never `BaseException`. Never persist exception message/class/traceback or invalid-result data.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_execution.py -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 7**

```bash
git add src/ai_service_desk/engine/execution.py tests/engine/test_execution.py
git diff --cached --name-only
git commit -m "feat: add fail-closed controlled execution engine"
```

Expected staged files: exactly the two Task 7 files.

---

### Task 8: Atomic CAS concurrency and expected_version on every entrypoint

**Files:**
- Modify: `src/ai_service_desk/engine/request_repository.py`
- Modify: `src/ai_service_desk/engine/execution.py`
- Create: `tests/engine/test_phase8_concurrency.py`

**Interfaces:**
- No new business API. Completes atomicity and makes fake call accounting thread-safe.

- [ ] **Step 1: write deterministic RED concurrency tests**

Add `test_repository_final_cas_is_atomic_under_forced_interleaving` with a test-only `BarrierLock`: `__enter__` waits on a two-party `threading.Barrier` before acquiring an underlying `RLock`; `__exit__` releases the underlying lock. Replace `repo._lock` only inside this test and run two direct concurrent `repo.save` calls against the same current version. RED expectation is one success and one `VERSION_CONFLICT`; the Task 2 implementation permits both to compare before the final lock, so the test fails deterministically.

Add:

```text
test_two_human_decisions_only_one_final_cas_wins
test_two_execute_callers_make_exactly_one_executor_call
test_expected_version_contract_is_enforced_by_every_entrypoint[True]
test_expected_version_contract_is_enforced_by_every_entrypoint[False]
test_expected_version_contract_is_enforced_by_every_entrypoint[float]
test_expected_version_contract_is_enforced_by_every_entrypoint[string]
test_expected_version_contract_is_enforced_by_every_entrypoint[None]
```

The expected-version test invokes all four surfaces for each value: `repository.save`, `approval.approve`, `approval.reject`, `execution.execute`. Every invocation raises `EXPECTED_VERSION_INVALID`; execute also proves zero policy and zero executor calls.

Double decision uses a barrier registry wrapper so both callers pass preliminary gates before final CAS. Double execution uses a barrier policy engine so both callers pass preliminary gates before final CAS. Exactly one executor call is permitted.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_phase8_concurrency.py -q
```

Expected: deterministic failure in `test_repository_final_cas_is_atomic_under_forced_interleaving` until current-read, compare, validation and mutation share one lock scope.

- [ ] **Step 3: make final CAS fully atomic**

`InMemoryRequestRepository.save` enters its instance `RLock` before reading current record and retains that lock through:

```text
read current
validate expected_version
compare current.version
validate candidate version and immutable fields
validate updated_at chronology
validate incoming audit against current audit tail
replace record
append events
return stored record
```

No retry loop is allowed. CAS loser receives `VERSION_CONFLICT`.

`FakeActionExecutor` adds a private lock only around call-history append/read; it does not serialize policy or repository operations.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_phase8_concurrency.py -q
```

Expected: PASS; double-execution test asserts exactly one executor call.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 8**

```bash
git add src/ai_service_desk/engine/request_repository.py src/ai_service_desk/engine/execution.py tests/engine/test_phase8_concurrency.py
git diff --cached --name-only
git commit -m "test: lock phase 8 concurrency guarantees"
```

Expected staged files: exactly the three Task 8 files.

---

### Task 9: Security boundaries, protected files and zero external execution

**Files:**
- Create: `tests/engine/test_phase8_security.py`

**Interfaces:**
- Consumes all five Phase 8 runtime modules already defined.
- Produces no runtime code.

- [ ] **Step 1: write RED security tests**

Implement a pure-Python Git blob hash helper:

```python
def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()
```

`test_phase7_protected_files_keep_homologated_git_blob_hashes` is parametrized with these exact pairs:

```text
src/ai_service_desk/engine/access_request.py -> f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d
src/ai_service_desk/engine/policy.py -> 60a4f3ae785353009c30b37f71e1ce91865b899e
src/ai_service_desk/engine/confidence.py -> ffc0c212b455978f79a3591578f323ca0e9612dc
```

`test_phase8_runtime_sources_have_no_external_execution_surface` scans:

```text
request_lifecycle.py
request_repository.py
technician_authorization.py
approval.py
execution.py
```

Forbidden patterns include `import requests`, `from requests`, `import httpx`, `from httpx`, `urllib.request`, `CDMAdapter`, `OllamaClient`, `LocalEmbedder`, `subprocess`, `sqlite3`, `sqlalchemy`, `psycopg`, HTTP URL literals, shell command launchers.

`test_phase8_runtime_sources_have_no_real_persistence_surface` rejects `open(`, `.write_text(`, `.write_bytes(` and `atomic_json(` in those five core runtime files.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_phase8_security.py -q
```

Expected: initial run fails if any current Phase 8 source violates the static boundary; if the runtime is already clean, add the runtime monkeypatch test in Step 1 before moving on so RED is caused by the missing smoke entrypoint from Task 10 only after Task 10 starts. Task 9 itself must not modify production code to manufacture a failure.

- [ ] **Step 3: resolve only genuine boundary violations**

If RED identifies a forbidden import or persistence surface in a Phase 8 runtime file, remove that usage without touching protected Phase 7 modules. If the only failing condition is the planned future smoke runtime guard, leave that guard for Task 10. Do not add adapters, wrappers or allowlists that weaken the prohibited surface.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_phase8_security.py -q
```

Expected: PASS for protected hashes and static Phase 8 boundaries.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 9**

```bash
git add tests/engine/test_phase8_security.py
git diff --cached --name-only
git commit -m "test: lock phase 8 security boundaries"
```

Expected staged file: only `tests/engine/test_phase8_security.py`.

---

### Task 10: Synthetic controlled-execution smoke

**Files:**
- Create: `src/ai_service_desk/engine/controlled_execution_smoke.py`
- Create: `tests/fixtures/phase8_controlled_execution_cases.jsonl`
- Create: `tests/engine/test_controlled_execution_smoke.py`
- Modify: `tests/engine/test_phase8_security.py`

**Interfaces:**
- Produces `load_controlled_execution_cases(path: str | Path) -> list[dict]` and `run_controlled_execution_smoke(cases_path: str | Path, report_path: str | Path) -> dict`.

Exact fixture fields:

```text
case_name
requested_role
flow
executor_mode
expected_state
expected_event_types
expected_executor_calls
expected_result_code
expected_error_code
```

Exact six case names/flows:

```text
approve_only -> APPROVED, zero executor calls
reject -> REJECTED, zero executor calls
deny_at_creation -> DENIED_POLICY, zero executor calls
execute_success -> COMPLETED, one executor call
execute_failure -> FAILED, one executor call
revalidation_deny -> DENIED_POLICY, zero executor calls
```

- [ ] **Step 1: write RED smoke tests and exact fixture**

Create six JSONL rows using roles `SOLICITANTE` except `deny_at_creation`, which uses `ADMIN`. Expected event sequences:

```text
approve_only: REQUEST_CREATED, POLICY_REQUIRES_APPROVAL, REQUEST_APPROVED
reject: REQUEST_CREATED, POLICY_REQUIRES_APPROVAL, REQUEST_REJECTED
deny_at_creation: REQUEST_CREATED, POLICY_DENIED_AT_CREATION
execute_success: REQUEST_CREATED, POLICY_REQUIRES_APPROVAL, REQUEST_APPROVED, EXECUTION_STARTED, EXECUTION_COMPLETED
execute_failure: REQUEST_CREATED, POLICY_REQUIRES_APPROVAL, REQUEST_APPROVED, EXECUTION_STARTED, EXECUTION_FAILED
revalidation_deny: REQUEST_CREATED, POLICY_REQUIRES_APPROVAL, REQUEST_APPROVED, POLICY_DENIED_BEFORE_EXECUTION
```

Add:

```text
test_load_controlled_execution_cases_requires_exactly_six_cases
test_load_controlled_execution_cases_rejects_invalid_schema
test_controlled_execution_smoke_passes_all_six_contract_flows
test_controlled_execution_smoke_report_is_privacy_safe
test_controlled_execution_smoke_makes_zero_external_calls
```

Privacy scan forbids synthetic names, `example.invalid`, raw purpose, `CDM_ACCESS_REQUEST`, knowledge/playbook IDs and exception marker in report output.

Runtime zero-external test monkeypatches `requests.Session.request`, `subprocess.run`, `OllamaClient.chat`, `LocalEmbedder.embed` to raise and still requires smoke PASS.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/engine/test_controlled_execution_smoke.py -q
```

Expected: import failure because `controlled_execution_smoke.py` does not exist.

- [ ] **Step 3: implement deterministic privacy-safe smoke**

Report envelope fields:

```text
schema_version = 1
phase = 8
domain = CONTROLLED_APPROVAL_EXECUTION
timestamp_utc
ok
cases
privacy.identity_included = false
privacy.raw_problem_text_included = false
privacy.purpose_included = false
privacy.capability_included = false
privacy.corporate_data_included = false
```

Per-case report fields are only `case_name`, `final_state`, `event_types`, `executor_calls`, `result_code`, `error_code`, `passed`.

Use fixed synthetic requester/technician identities in code with `example.invalid`, but never copy them to the report. Construct `AccessRequestContext` directly from protected Phase 7 contracts. Use `atomic_json` only for the caller-specified smoke report, never for request persistence.

For `revalidation_deny`, create with default `PolicyEngine`, approve, then construct a separate valid custom `PolicyEngine` containing a DENY `PolicyRule` matching the same context for `ExecutionEngine`.

Extend `test_phase8_security.py` so `controlled_execution_smoke.py` is included in the external-execution token scan, while file output is allowed only through `atomic_json` in this smoke module.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/engine/test_controlled_execution_smoke.py tests/engine/test_phase8_security.py -q
```

Expected: PASS, six cases, all privacy flags false, external-call monkeypatches untouched.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 10**

```bash
git add src/ai_service_desk/engine/controlled_execution_smoke.py tests/fixtures/phase8_controlled_execution_cases.jsonl tests/engine/test_controlled_execution_smoke.py tests/engine/test_phase8_security.py
git diff --cached --name-only
git commit -m "test: add phase 8 controlled execution smoke"
```

Expected staged files: exactly the four Task 10 files.

---

### Task 11: CLI integration for controlled-execution-smoke

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_controlled_execution_cli.py`

**Interfaces:**
- Consumes `run_controlled_execution_smoke`.
- Produces CLI command `controlled-execution-smoke --cases PATH --report PATH`.

- [ ] **Step 1: write RED CLI tests**

Parser test invokes:

```text
controlled-execution-smoke --cases cases.jsonl --report report.json
```

It asserts command name, both `Path` values, and absence of `url`, `knowledge_index`, `playbooks`, `work_directory` attributes.

Add `test_controlled_execution_smoke_cli_output_is_safe_and_does_not_construct_ollama`: monkeypatch smoke runner to a six-case passed report and `OllamaClient` constructor to raise. Expected stdout contains `CONTROLLED EXECUTION SMOKE OK` and `Casos sinteticos: 6`, while excluding identity, purpose and capability strings.

Add `test_controlled_execution_smoke_cli_returns_nonzero_when_report_is_not_ok` expecting return code `1`.

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/test_controlled_execution_cli.py -q
```

Expected: argparse invalid-choice failure because the command is absent.

- [ ] **Step 3: implement additive parser and early dispatch**

Parser:

```python
controlled_execution_smoke = sub.add_parser("controlled-execution-smoke")
controlled_execution_smoke.add_argument("--cases", type=Path, required=True)
controlled_execution_smoke.add_argument("--report", type=Path, required=True)
```

Dispatch before any Ollama construction:

```python
if args.command == "controlled-execution-smoke":
    report = run_controlled_execution_smoke(args.cases, args.report)
    print(
        "CONTROLLED EXECUTION SMOKE OK"
        if report["ok"]
        else "CONTROLLED EXECUTION SMOKE REQUER REVISAO"
    )
    print(f"Casos sinteticos: {len(report.get('cases', []))}")
    print("Relatorio agregado local: " + str(args.report))
    return 0 if report["ok"] else 1
```

Do not refactor existing CLI commands.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/test_controlled_execution_cli.py tests/test_policy_cli.py -q
```

Expected: PASS for new CLI and Phase 7 policy CLI regression.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: commit Task 11**

```bash
git add src/ai_service_desk/cli.py tests/test_controlled_execution_cli.py
git diff --cached --name-only
git commit -m "feat: add phase 8 controlled execution smoke cli"
```

Expected staged files: exactly the two Task 11 files.

---

### Task 12: Exact-head Dell workflow with Phase 2 byte restoration

**Files:**
- Create: `.github/workflows/phase8-controlled-execution-smoke.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Consumes Task 11 CLI and Task 10 fixture.
- Produces manual exact-head Dell workflow. No artifact upload, no Ollama call, no repository data persistence.

- [ ] **Step 1: write RED workflow contract test**

Add:

```python
PHASE8_WORKFLOW = ROOT / ".github" / "workflows" / "phase8-controlled-execution-smoke.yml"
```

`test_phase8_controlled_execution_workflow_is_exact_head_local_and_non_exporting` requires these strings:

```text
workflow_dispatch:
target_ref:
Exact candidate commit SHA to validate
self-hosted
Windows
X64
ai-service-desk
TARGET_REF: ${{ inputs.target_ref }}
git rev-parse HEAD
^[0-9a-f]{40}$
tests/fixtures/phase2_corpus.csv
HEAD:tests/fixtures/phase2_corpus.csv
phase2_corpus_manifest.json
raw_sha256
candidate_sha_after_fixture_restore
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m ai_service_desk controlled-execution-smoke
tests/fixtures/phase8_controlled_execution_cases.jsonl
```

It forbids:

```text
upload-artifact
Get-Content
python -m ai_service_desk doctor
knowledge-index
playbook-build
http://127.0.0.1:11434
CDMAdapter
PHASE8_CANDIDATE_SHA
```

- [ ] **Step 2: run RED**

```bash
python -m pytest tests/test_workflows.py::test_phase8_controlled_execution_workflow_is_exact_head_local_and_non_exporting -q
```

Expected: failure because workflow file does not exist.

- [ ] **Step 3: create exact-head workflow**

Required top-level YAML:

```yaml
name: Phase 8 controlled execution smoke

on:
  workflow_dispatch:
    inputs:
      target_ref:
        description: Exact candidate commit SHA to validate
        required: true
        type: string

permissions:
  contents: read

jobs:
  phase8-controlled-execution-smoke:
    runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
    timeout-minutes: 20
```

Checkout:

```yaml
- name: Checkout target ref
  uses: actions/checkout@v4
  with:
    ref: ${{ inputs.target_ref }}
    fetch-depth: 0
```

Immediately verify exact SHA in PowerShell: normalize `TARGET_REF`, require regex `^[0-9a-f]{40}$`, compute `(git rev-parse HEAD).Trim().ToLowerInvariant()` and throw on mismatch.

Restore only the Phase 2 CSV with this embedded Python:

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

After the Python block, PowerShell recomputes HEAD and throws unless it still equals `TARGET_REF`; on success print `candidate_sha_after_fixture_restore=$actual`.

Then run exact commands in the workflow:

```text
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Smoke step must construct its report path explicitly:

```powershell
$report = Join-Path $env:RUNNER_TEMP "phase8-controlled-$env:GITHUB_RUN_ID.json"
Remove-Item -Force $report -ErrorAction SilentlyContinue
python -m ai_service_desk controlled-execution-smoke `
  --cases tests/fixtures/phase8_controlled_execution_cases.jsonl `
  --report "$report"
```

The workflow never modifies the manifest and never restores another fixture.

- [ ] **Step 4: run GREEN**

```bash
python -m pytest tests/test_workflows.py::test_phase8_controlled_execution_workflow_is_exact_head_local_and_non_exporting -q
```

Expected: PASS.

- [ ] **Step 5: run regression and quality checks**

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git diff --check
git diff --name-only -- tests/fixtures/phase2_corpus.csv tests/fixtures/phase2_corpus_manifest.json
```

Expected: pytest/Ruff/diff-check commands exit `0`; protected diff empty; final command prints nothing.

- [ ] **Step 6: commit Task 12**

```bash
git add .github/workflows/phase8-controlled-execution-smoke.yml tests/test_workflows.py
git diff --cached --name-only
git commit -m "ci: add phase 8 exact-head Dell smoke"
```

Expected staged list exactly:

```text
.github/workflows/phase8-controlled-execution-smoke.yml
tests/test_workflows.py
```

---

## Final Gate: candidate freeze and evidence

Any correction after candidate freeze creates a new candidate SHA and requires rerunning F1 through F8 from the beginning.

### Gate F1: Freeze candidate and clean tree

Run:

```bash
git status --short
PHASE8_CANDIDATE_SHA="$(git rev-parse HEAD)"
printf 'candidate_head=%s\n' "$PHASE8_CANDIDATE_SHA"
```

Expected: `git status --short` prints nothing; candidate SHA prints as 40 hex characters.

### Gate F2: Ruff and full test suite

Run:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Expected: Ruff check PASS, Ruff format PASS, full pytest PASS. Do not hardcode the final test count.

### Gate F3: Historical node IDs and real new-node count

Run:

```bash
REPO_ROOT="$(pwd)"
BASELINE_WORKTREE="$(dirname "$REPO_ROOT")/ai-service-desk-phase8-baseline"
BASELINE_IDS="$(mktemp)"
CANDIDATE_IDS="$(mktemp)"
git worktree add --detach "$BASELINE_WORKTREE" 2f583b5b4921cd7b40ddde2978a2852ecca2251d
(
  cd "$BASELINE_WORKTREE"
  python -m pytest --collect-only -q | grep '::' | sort -u > "$BASELINE_IDS"
)
python -m pytest --collect-only -q | grep '::' | sort -u > "$CANDIDATE_IDS"
python - "$BASELINE_IDS" "$CANDIDATE_IDS" <<'PY'
from pathlib import Path
import sys
baseline = set(Path(sys.argv[1]).read_text(encoding="utf-8").splitlines())
candidate = set(Path(sys.argv[2]).read_text(encoding="utf-8").splitlines())
missing = sorted(baseline - candidate)
new = sorted(candidate - baseline)
print(f"baseline_nodeids={len(baseline)}")
print(f"final_nodeids={len(candidate)}")
print(f"missing_historical_nodeids={len(missing)}")
print(f"new_nodeids={len(new)}")
assert len(baseline) == 426
assert not missing
PY
git worktree remove "$BASELINE_WORKTREE"
rm -f "$BASELINE_IDS" "$CANDIDATE_IDS"
```

Expected: command prints `baseline_nodeids=426`, `missing_historical_nodeids=0`, and the actual `final_nodeids` and `new_nodeids` integers collected from the candidate.

### Gate F4: Protected Phase 7 byte equality

Run:

```bash
git diff --exit-code 2f583b5b4921cd7b40ddde2978a2852ecca2251d "$PHASE8_CANDIDATE_SHA" -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
python -m pytest tests/engine/test_phase8_security.py::test_phase7_protected_files_keep_homologated_git_blob_hashes -q
```

Expected: git diff exit `0`, hash test PASS.

### Gate F5: Zero external execution and Phase 9/10 boundary

Run:

```bash
python -m pytest tests/engine/test_phase8_security.py -q
git diff --name-only 2f583b5b4921cd7b40ddde2978a2852ecca2251d "$PHASE8_CANDIDATE_SHA"
```

Expected: security test PASS; changed files belong only to approved Phase 8 spec/plan/file map. No adapter, DB, routing or frontend file appears.

### Gate F6: Official Phase 8 smoke

Run:

```bash
PHASE8_REPORT="phase8-controlled-execution-report.json"
python -m ai_service_desk controlled-execution-smoke --cases tests/fixtures/phase8_controlled_execution_cases.jsonl --report "$PHASE8_REPORT"
python - "$PHASE8_REPORT" <<'PY'
import json
from pathlib import Path
import sys
report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["ok"] is True
assert len(report["cases"]) == 6
assert all(row["passed"] for row in report["cases"])
assert all(value is False for value in report["privacy"].values())
print("phase8_smoke_cases=6")
print("phase8_smoke_privacy=OK")
PY
rm -f "$PHASE8_REPORT"
```

Expected stdout includes:

```text
CONTROLLED EXECUTION SMOKE OK
Casos sinteticos: 6
phase8_smoke_cases=6
phase8_smoke_privacy=OK
```

### Gate F7: Hosted CI

Only after candidate freeze, implementation completion may create a draft PR. This plan-creation task does not create a PR.

Future one-shot creation command:

```bash
gh pr create --draft --base main --head phase-8-controlled-approval-execution --title "feat: phase 8 controlled approval and execution" --body "Phase 8 controlled approval/execution candidate. No merge until explicit acceptance."
```

Expected: GitHub prints the draft PR URL.

Do not poll GitHub Actions. After the operator reports hosted CI completion, inspect once:

```bash
PR_NUMBER="$(gh pr view phase-8-controlled-approval-execution --repo borgescodes/ai-service-desk --json number --jq .number)"
gh pr checks "$PR_NUMBER" --repo borgescodes/ai-service-desk
```

Expected: hosted `Python quality` check PASS, including Python 3.14, Ruff and full pytest.

### Gate F8: Dell exact-head

Dispatch official workflow once with frozen SHA:

```bash
gh workflow run phase8-controlled-execution-smoke.yml --repo borgescodes/ai-service-desk --ref phase-8-controlled-approval-execution -f target_ref="$PHASE8_CANDIDATE_SHA"
```

Do not poll. After the operator reports completion, inspect the latest matching run once:

```bash
RUN_ID="$(gh run list --repo borgescodes/ai-service-desk --workflow phase8-controlled-execution-smoke.yml --branch phase-8-controlled-approval-execution --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run view "$RUN_ID" --repo borgescodes/ai-service-desk --json conclusion,headSha,jobs
```

Required Dell evidence:

```text
workflow conclusion = success
checkout exact target SHA = frozen candidate SHA
Python = 3.14.x
fixture_raw_sha_after = manifest raw_sha256
candidate_sha_after_fixture_restore = frozen candidate SHA
Ruff check = PASS
Ruff format = PASS
full pytest = PASS
controlled execution smoke = PASS 6/6
```

The fixture restoration is working-tree-only. Fixture and manifest remain unchanged in Git.

### Final evidence fields for implementation completion

The executor reports the values emitted by F1-F8 under these exact labels:

```text
candidate head
historical baseline node IDs
final node IDs
missing historical node IDs
new node IDs
Ruff check
Ruff format
protected Phase 7 files
zero external execution
Phase 8 smoke
hosted CI
Dell exact-head
merge
```

`merge` remains `NOT PERFORMED` until a separate explicit merge authorization is received.

---

## Plan Self-Review

- Coverage integral da spec: PASS. Every one of the 87 numbered contractual cases maps to a concrete test or Final Gate F3.
- Placeholders: PASS. Commands use concrete paths, literal test names, shell variables assigned by prior commands and runtime-collected values; no unresolved content marker remains.
- Signatures consistentes: PASS. Every Phase 8 public type/method is defined before a later task consumes it.
- No undefined function/type references: PASS. Task 6 does not reference `FakeActionExecutor`; it is defined only in Task 7. `RequestRepository`/`RequestLifecycleService` circular typing is resolved explicitly with `TYPE_CHECKING`.
- Historical baseline: PASS as plan contract. Exactly 426 historical node IDs are collected from the immutable baseline and compared as a set in F3.
- Protected files intact: PASS as plan contract. Per-task diffs, blob-hash tests and F4 all guard byte equality.
- Fase 9 não antecipada: PASS. No HTTP, CDM adapter/API/credential/idempotency external or real executor is planned.
- Fase 10 não antecipada: PASS. No routing, queue, automatic technician selection or workload distribution is planned.
- Repository boundary: PASS. Request/audit state stays in memory. The only file output introduced is the caller-specified synthetic smoke report, matching the existing smoke pattern.
- Concurrency: PASS. Task 8 has a deterministic RED for non-atomic CAS, final CAS remains mandatory, and separate double-decision/double-execution tests prove race behavior.
- Temporal/audit: PASS. Timezone-awareness, intra-record chronology, inter-version `updated_at`, audit append chronology and equal-timestamp tie-breaks have dedicated tests.
- Executor invalid result: PASS. All six required invalid shapes map to `EXECUTOR_INVALID_RESULT` without arbitrary persistence.
- Exact-head workflow: PASS. Task 12 reuses the Phase 7 Dell discipline and restores only `tests/fixtures/phase2_corpus.csv` from the current `HEAD` blob before verification.
- Final Gate: PASS. It plans real node-ID collection, Ruff, full pytest, protected equality, zero external execution, six-case smoke, hosted CI and Dell exact-head.

Implementation must stop after the Final Gate and wait for explicit merge authorization.