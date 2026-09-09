# Phase 11 Learning and Prevention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar uma camada analítica determinística que coleta outcomes estruturados, agrega recorrência e produz oportunidades explicáveis de prevenção para revisão humana, sem alterar autorização, conteúdo oficial ou execução.

**Architecture:** A Fase 11 cria um domínio isolado em `learning_prevention.py`. Um `OutcomeRecord` imutável resume uma interação, um store com `RLock` garante idempotência e conflito fail closed, `PatternAggregator` agrupa por `(system, intent, capability, area)` e `OpportunityEngine` aplica regras explícitas com `MIN_RECURRENCE = 3`. Um smoke sintético de dez casos e workflow dedicado fecham a fase.

**Tech Stack:** Python 3.14, stdlib `dataclasses`, `collections`, `hashlib`, `json`, `threading.RLock`, pytest, Ruff 0.12.12, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-phase-11-learning-prevention-design.md`

## Global Constraints

- Base SHA: `81a748921ba01393285da2e2d2ebc9371c890e2c`.
- Historical baseline: exatamente `847` pytest node IDs.
- Branch: `phase-11-learning-prevention`.
- Nenhum dos 18 arquivos protegidos da spec pode mudar.
- Analytics é somente leitura das fases anteriores.
- `MIN_RECURRENCE = 3` e `LEARNING_RULES_VERSION = 1`.
- Sem LLM, embeddings, fuzzy matching, score, HTTP, CDM, ApprovalService, ExecutionEngine, PolicyEngine ou serviços mutadores de routing no runtime da Fase 11.
- Nenhuma mutação automática de Knowledge, Playbook, Policy, approval, routing ou execution.
- Nenhum transcript, answer, purpose, nome, username, email, token ou traceback em `OutcomeRecord` ou fixture.
- Fixture totalmente sintética.
- Store somente em memória, usando `RLock`.
- Mesma interação e mesmo payload são idempotentes. Mesmo ID e payload diferente falham com `OUTCOME_CONFLICT`.
- Todos os comportamentos de produto seguem teste RED antes de implementação mínima GREEN.
- Nenhum merge faz parte deste plano.

---

## File Map

### Create

```text
src/ai_service_desk/engine/learning_prevention.py
src/ai_service_desk/engine/learning_prevention_smoke.py
src/ai_service_desk/phase11_cli.py
tests/engine/test_outcome_store.py
tests/engine/test_outcome_collector.py
tests/engine/test_pattern_aggregator.py
tests/engine/test_opportunity_engine.py
tests/engine/test_phase11_security.py
tests/engine/test_learning_prevention_smoke.py
tests/test_phase11_cli.py
tests/test_phase11_workflow.py
tests/fixtures/phase11_learning_prevention_cases.jsonl
.github/workflows/phase11-learning-prevention.yml
```

### Modify

```text
src/ai_service_desk/__main__.py
```

### Protected and expected unchanged

Todos os 18 arquivos listados na seção 24 da spec.

---

### Task 1: Outcome contracts and idempotent store

**Files:**
- Create: `src/ai_service_desk/engine/learning_prevention.py`
- Create: `tests/engine/test_outcome_store.py`

**Interfaces:**
- Produces: `OutcomeRecord`, `Phase11LearningError`, `OutcomeValidationError`, `OutcomeConflictError`, `OutcomeNotFoundError`, `validate_outcome_record`, `InMemoryOutcomeStore`.
- Consumes: stdlib only.

- [ ] **Step 1: Write failing tests**

Tests require:

```text
OutcomeRecord frozen
valid record accepted
unknown outcome rejected
incoherent playbook fields rejected
first ingest stores
identical replay returns same record
identical replay keeps snapshot length 1
same interaction_id with different payload -> OUTCOME_CONFLICT
get missing -> OUTCOME_NOT_FOUND
snapshot tuple sorted by interaction_id
concurrent identical ingest -> one record
concurrent conflicting ingest -> one winner and one OUTCOME_CONFLICT
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/engine/test_outcome_store.py -q
```

Expected: import failure because `learning_prevention.py` does not exist.

- [ ] **Step 3: Implement minimal contracts and store**

Use exact constants:

```python
LEARNING_RULES_VERSION = 1
MIN_RECURRENCE = 3
OUTCOMES = frozenset({
    "RESOLVED_BY_KNOWLEDGE",
    "GUIDED_BY_PLAYBOOK",
    "ROUTED_TO_HUMAN",
    "APPROVED",
    "REJECTED",
    "DENIED_POLICY",
    "EXECUTION_COMPLETED",
    "EXECUTION_FAILED",
})
```

`InMemoryOutcomeStore.ingest(...)` validates before lock, then performs lookup, equality comparison and first write under one `RLock`.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/engine/test_outcome_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/engine/learning_prevention.py tests/engine/test_outcome_store.py
git commit -m "feat: add phase 11 outcome store"
```

### Task 2: Read-only collectors from existing evidence

**Files:**
- Modify: `src/ai_service_desk/engine/learning_prevention.py`
- Create: `tests/engine/test_outcome_collector.py`

**Interfaces:**
- Produces: `OutcomeCollector.from_knowledge`, `OutcomeCollector.from_playbook`, `OutcomeCollector.from_request`.
- Consumes: `TriageState`, `AccessRequestRecord`, `validate_access_request_record`, `RoutingAssignment`.

- [ ] **Step 1: Write failing collector tests**

Require exact cases:

```text
ANSWERED + KNOWLEDGE_FOUND -> RESOLVED_BY_KNOWLEDGE
non ANSWERED knowledge input rejected
PLAYBOOK_FOUND -> GUIDED_BY_PLAYBOOK with id/version
PENDING_APPROVAL without assignment rejected
PENDING_APPROVAL with compatible assignment -> ROUTED_TO_HUMAN
mismatched assignment rejected
APPROVED -> APPROVED
REJECTED -> REJECTED
DENIED_POLICY -> DENIED_POLICY using latest_policy.reason_code
COMPLETED -> EXECUTION_COMPLETED using execution_result_code
FAILED -> EXECUTION_FAILED using execution_error_code
TRIAGED/EXECUTING snapshots rejected
collector does not mutate triage, result, request or assignment
request projection does not copy purpose, username, email or technician data
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/engine/test_outcome_collector.py -q
```

Expected: missing `OutcomeCollector` behavior.

- [ ] **Step 3: Implement adapters only**

Use only immutable fields already present. Do not call policy, approval, execution, CDM or routing services.

- [ ] **Step 4: Run GREEN and regression of protected contracts**

```bash
python -m pytest tests/engine/test_outcome_collector.py tests/engine/test_phase10_security.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/engine/learning_prevention.py tests/engine/test_outcome_collector.py
git commit -m "feat: collect structured phase 11 outcomes"
```

### Task 3: Deterministic pattern aggregation

**Files:**
- Modify: `src/ai_service_desk/engine/learning_prevention.py`
- Create: `tests/engine/test_pattern_aggregator.py`

**Interfaces:**
- Produces: `PatternKey`, `PatternAggregate`, `PatternAggregator.aggregate`.
- Consumes: `OutcomeRecord` snapshots.

- [ ] **Step 1: Write RED tests**

Cover:

```text
exact grouping by system/intent/capability/area
knowledge_id does not split primary pattern
playbook_id does not split primary pattern
outcome appears in deterministic outcome_counts
empty IDs excluded from knowledge_ids/playbook_ids/reason_codes
same records reversed -> same aggregate tuple
patterns sorted by PatternKey
evidence IDs sorted and unique by store contract
occurrence_count exact
invalid record fails before aggregation
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/engine/test_pattern_aggregator.py -q
```

- [ ] **Step 3: Implement aggregation with `Counter` and canonical tuples**

No score, threshold logic or opportunity decision belongs in the aggregator.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/engine/test_pattern_aggregator.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/engine/learning_prevention.py tests/engine/test_pattern_aggregator.py
git commit -m "feat: aggregate deterministic learning patterns"
```

### Task 4: Explainable opportunity engine

**Files:**
- Modify: `src/ai_service_desk/engine/learning_prevention.py`
- Create: `tests/engine/test_opportunity_engine.py`

**Interfaces:**
- Produces: `PreventionOpportunity`, `OpportunityEngine.generate`.
- Consumes: `PatternAggregate`.

- [ ] **Step 1: Write RED tests**

Cover every rule from the spec:

```text
count 2 -> zero opportunity
recurrent knowledge resolved -> PREVENTION_CANDIDATE, no HUMAN_DEPENDENCY
all routed human with no knowledge -> KNOWLEDGE_GAP + HUMAN_DEPENDENCY + PREVENTION_CANDIDATE
all routed human with knowledge but no playbook -> PLAYBOOK_GAP + HUMAN_DEPENDENCY + PREVENTION_CANDIDATE
all routed human with one stable playbook/capability -> AUTOMATION_CANDIDATE + HUMAN_DEPENDENCY + PREVENTION_CANDIDATE
three execution failures -> EXECUTION_RELIABILITY_ISSUE + PREVENTION_CANDIDATE
mixed success/failure with three failures still -> EXECUTION_RELIABILITY_ISSUE
opportunity IDs stable
same patterns in different order -> same opportunities
output canonical order
opportunity evidence IDs exactly match supporting pattern
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/engine/test_opportunity_engine.py -q
```

- [ ] **Step 3: Implement exact rule table**

Category order:

```python
OPPORTUNITY_CATEGORIES = (
    "KNOWLEDGE_GAP",
    "PLAYBOOK_GAP",
    "HUMAN_DEPENDENCY",
    "AUTOMATION_CANDIDATE",
    "PREVENTION_CANDIDATE",
    "EXECUTION_RELIABILITY_ISSUE",
)
```

Create `opportunity_id` from SHA-256 of canonical JSON containing only category and `PatternKey` fields.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/engine/test_opportunity_engine.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/engine/learning_prevention.py tests/engine/test_opportunity_engine.py
git commit -m "feat: detect prevention opportunities"
```

### Task 5: Synthetic fixture and official ten-case smoke

**Files:**
- Create: `tests/fixtures/phase11_learning_prevention_cases.jsonl`
- Create: `src/ai_service_desk/engine/learning_prevention_smoke.py`
- Create: `tests/engine/test_learning_prevention_smoke.py`

**Interfaces:**
- Produces: `load_learning_cases`, `run_learning_prevention_smoke`.
- Consumes: `OutcomeRecord`, store, aggregator, opportunity engine.

- [ ] **Step 1: Create fixture and RED smoke tests**

Fixture contains four deterministic groups, at least three records each:

```text
POWER_BI recurring resolved by Knowledge
MICROSOFT_365 human-routed without Knowledge
HARDWARE human-routed with stable approved playbook/capability
CDM repeated execution failures
```

Add an ERP group with Knowledge present, no Playbook, routed to human to prove `PLAYBOOK_GAP`.

Tests require exact ten case IDs from the spec, closed fixture schema, synthetic IDs only, deterministic report and no transcript/email/token fields.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/engine/test_learning_prevention_smoke.py -q
```

- [ ] **Step 3: Implement smoke**

Report shape:

```text
ok
case_count
cases[].case_id
cases[].ok
cases[].expected
cases[].actual
```

No free-form evidence payload in report.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/engine/test_learning_prevention_smoke.py -q
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/phase11_learning_prevention_cases.jsonl src/ai_service_desk/engine/learning_prevention_smoke.py tests/engine/test_learning_prevention_smoke.py
git commit -m "test: add phase 11 learning prevention smoke"
```

### Task 6: Security and protected invariants

**Files:**
- Create: `tests/engine/test_phase11_security.py`

**Interfaces:**
- Consumes: Git object SHAs from spec and Phase 11 runtime modules.

- [ ] **Step 1: Add security tests**

Tests must prove:

```text
18 exact blobs using git rev-parse HEAD:<path>
learning modules have no requests/urllib/http.client/socket imports
learning modules have no CDM integration imports
learning_prevention.py has no PolicyEngine/ApprovalService/ExecutionEngine/RoutingService imports
OutcomeRecord fields exclude purpose/name/username/email/token/transcript/answer
fixture fields exclude those values
analytics generation leaves supplied immutable operational objects unchanged
MIN_RECURRENCE exactly 3
LEARNING_RULES_VERSION exactly 1
OUTCOMES and opportunity categories are closed
```

- [ ] **Step 2: Run security GREEN**

```bash
python -m pytest tests/engine/test_phase11_security.py -q
```

This task locks invariants already implemented and may fail only if a boundary was violated. If it fails, debug root cause before continuing.

- [ ] **Step 3: Run previous security regressions**

```bash
python -m pytest tests/engine/test_phase8_security.py tests/engine/test_phase9_security.py tests/engine/test_phase10_security.py -q
```

- [ ] **Step 4: Commit**

```bash
git add tests/engine/test_phase11_security.py
git commit -m "test: lock phase 11 security boundaries"
```

### Task 7: Minimal CLI

**Files:**
- Create: `src/ai_service_desk/phase11_cli.py`
- Modify: `src/ai_service_desk/__main__.py`
- Create: `tests/test_phase11_cli.py`

**Interfaces:**
- Produces command `learning-prevention-smoke`.
- Consumes `run_learning_prevention_smoke` and repository fixture path.

- [ ] **Step 1: Write RED CLI tests**

Require:

```text
phase11_cli.handles(["learning-prevention-smoke"]) is True
command returns zero when smoke ok
stdout contains LEARNING PREVENTION SMOKE OK
stdout contains Casos sinteticos: 10
Phase 11 dispatch runs before Phase 10, Phase 9 and legacy CLI
no Ollama or CDM token required
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_phase11_cli.py -q
```

- [ ] **Step 3: Implement minimal CLI and additive dispatcher**

`__main__.py` order:

```text
phase11_cli
phase10_cli
phase9_cli
legacy cli
```

- [ ] **Step 4: Run GREEN and prior CLI regressions**

```bash
python -m pytest tests/test_phase11_cli.py tests/test_phase10_cli.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/phase11_cli.py src/ai_service_desk/__main__.py tests/test_phase11_cli.py
git commit -m "feat: expose phase 11 learning smoke cli"
```

### Task 8: Dedicated workflow and final gates

**Files:**
- Create: `.github/workflows/phase11-learning-prevention.yml`
- Create: `tests/test_phase11_workflow.py`

**Interfaces:**
- Produces hosted Phase 11 homologation on `pull_request`.

- [ ] **Step 1: Write workflow contract RED**

Test requires literals for:

```text
pull_request
fetch-depth: 0
python-version: "3.14"
ruff==0.12.12
python -m ruff check .
python -m ruff format --check .
historical baseline SHA 81a748921ba01393285da2e2d2ebc9371c890e2c
historical expected count 847
full pytest
18 protected blob checks
Phase 8 security
Phase 9 security
Phase 10 security
Phase 11 security
routing-escalation-smoke
learning-prevention-smoke
git status --porcelain
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_phase11_workflow.py -q
```

- [ ] **Step 3: Implement workflow**

Historical script collects baseline and candidate node IDs, compares sets and prints exactly:

```text
historical_node_ids=847
candidate_node_ids=<n>
missing_historical_node_ids=0
new_node_ids=<n>
```

- [ ] **Step 4: Run focused GREEN**

```bash
python -m pytest tests/test_phase11_workflow.py -q
```

- [ ] **Step 5: Run final local-equivalent gates on one candidate**

```bash
python --version
python -m ruff --version
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m pytest tests/engine/test_phase8_security.py -q
python -m pytest tests/engine/test_phase9_security.py -q
python -m pytest tests/engine/test_phase10_security.py -q
python -m pytest tests/engine/test_phase11_security.py -q
python -m ai_service_desk routing-escalation-smoke
python -m ai_service_desk learning-prevention-smoke
python -m pytest --collect-only -q
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/phase11-learning-prevention.yml tests/test_phase11_workflow.py
git commit -m "ci: add phase 11 learning prevention gates"
```

## Final Homologation

Freeze one candidate SHA. If any subsequent correction changes the SHA, discard all previous candidate evidence and rerun every gate.

Required same-SHA evidence:

```text
Python 3.14.x
Ruff 0.12.12
Ruff lint PASS
Ruff format PASS
full pytest PASS
historical_node_ids=847
missing_historical_node_ids=0
new_node_ids=<real difference>
18 protected blobs PASS
Phase 8 security PASS
Phase 9 security PASS
Phase 10 security PASS
Phase 11 security PASS
Phase 10 routing smoke PASS
Phase 11 learning/prevention smoke PASS 10/10
working tree clean
```

Publish `phase-11-learning-prevention`, open Draft PR `Phase 11: learning and prevention`, keep it Draft, validate hosted CI and Phase 11 workflow on the exact head SHA, update PR body with evidence and do not merge.