# Phase 3 Evaluation and Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible synthetic evaluation harness, threshold sweep, safe reporting, and a conservative calibration decision for the competition track without claiming real-corpus accuracy.

**Architecture:** Add one focused `evaluation.py` module that consumes the existing classifier, embedder, index and `retrieve` contract. Keep corporate data outside Git, use a synthetic ground-truth benchmark for relevance metrics, use the real 240-ticket demo only for safety invariants, and keep runtime threshold `0.65` unless a real human-labeled gold set exists.

**Tech Stack:** Python 3.14, pandas, NumPy, pytest, Ruff, Ollama `qwen3.5:4b`, Ollama `qwen3-embedding:0.6b`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-07-phase-3-evaluation-calibration-design.md`

## Global Constraints

- Python remains `>=3.14,<3.15`.
- No new runtime dependency unless strictly required; standard library, NumPy and pandas are sufficient.
- Do not modify the retrieval algorithm to improve benchmark scores.
- Runtime threshold remains `0.65` unless a real human-labeled gold set satisfies the versioned policy.
- `confidence` from the classifier is not a calibrated probability and must not drive threshold selection.
- Corporate ticket text, history, IDs, demo subset, embeddings and real index remain outside Git and GitHub artifacts.
- Hosted CI must not require Ollama or corporate data.
- Reports for real-data evaluation must not include query text or candidate identifiers/content.
- Synthetic metrics must never be described as real-corpus precision, recall, coverage or automation rate.

---

### Task 1: Version the synthetic benchmark contract

**Files:**
- Create: `tests/fixtures/phase3_eval_corpus.csv`
- Create: `tests/fixtures/phase3_eval_cases.jsonl`
- Create: `tests/engine/test_evaluation.py`
- Create: `src/ai_service_desk/engine/evaluation.py`

**Interfaces:**
- Consumes: `ALLOWED_INTENTS` from `classification.py`.
- Produces: `load_evaluation_cases(path: str | Path) -> list[dict]`.

- [ ] **Step 1: Write failing schema tests**

Add tests that require unique IDs, non-empty queries, official intents, `must_abstain` consistency and valid statuses.

```python
def test_load_evaluation_cases_validates_schema(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"a","query":"CIGAM falhou","expected_intent":"ERRO_SISTEMA",'
        '"expected_system":"CIGAM","relevant_ticket_ids":["SYN-CIG-01"],'
        '"must_abstain":false}\n',
        encoding="utf-8",
    )
    cases = load_evaluation_cases(path)
    assert cases[0]["id"] == "a"


def test_load_evaluation_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '{"id":"a","query":"um","expected_intent":"OUTRO","expected_system":"",'
        '"relevant_ticket_ids":[],"must_abstain":true}\n'
        '{"id":"a","query":"dois","expected_intent":"OUTRO","expected_system":"",'
        '"relevant_ticket_ids":[],"must_abstain":true}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id"):
        load_evaluation_cases(path)
```

- [ ] **Step 2: Run RED**

Run hosted CI through the draft PR. Expected failure: `ai_service_desk.engine.evaluation` is missing.

- [ ] **Step 3: Implement minimal case loader**

Create `evaluation.py` with validation for:

```python
OFFICIAL_STATUSES = {"ENCONTRADOS", "SEM_EVIDENCIA", "SEM_CONTEXTO", "CONTEXTO_AMBIGUO"}


def load_evaluation_cases(path: str | Path) -> list[dict]: ...
```

Validate required fields, duplicate IDs, query length, official intents, statuses and `must_abstain=true` with no relevant IDs.

- [ ] **Step 4: Add synthetic corpus and 24-32 cases**

The fixture must contain only fictitious IDs prefixed `SYN-`. Cover CIGAM, SIAGRI, printer, network, access, install, orientation, unknown system, ambiguous context and weak-evidence cases.

- [ ] **Step 5: Run GREEN and commit**

Run Ruff and pytest in hosted CI. Commit only synthetic fixtures, loader and tests.

---

### Task 2: Implement pure evaluation metrics

**Files:**
- Modify: `src/ai_service_desk/engine/evaluation.py`
- Modify: `tests/engine/test_evaluation.py`

**Interfaces:**
- Consumes: normalized case dictionaries and result summaries.
- Produces: `compute_metrics(cases: list[dict], results: list[dict], k: int = 3) -> dict`.

- [ ] **Step 1: Write failing metric tests**

```python
def test_compute_metrics_counts_hit_mrr_and_abstention() -> None:
    cases = [
        {
            "id": "a",
            "expected_intent": "ERRO_SISTEMA",
            "expected_system": "CIGAM",
            "relevant_ticket_ids": ["SYN-1"],
            "must_abstain": False,
        },
        {
            "id": "b",
            "expected_intent": "OUTRO",
            "expected_system": "",
            "relevant_ticket_ids": [],
            "must_abstain": True,
            "expected_status": "SEM_CONTEXTO",
        },
    ]
    results = [
        {
            "id": "a",
            "actual_intent": "ERRO_SISTEMA",
            "actual_system": "CIGAM",
            "status": "ENCONTRADOS",
            "candidate_ids": ["SYN-1", "SYN-2"],
            "system_leakage": False,
            "total_seconds": 1.0,
        },
        {
            "id": "b",
            "actual_intent": "OUTRO",
            "actual_system": "",
            "status": "SEM_CONTEXTO",
            "candidate_ids": [],
            "system_leakage": False,
            "total_seconds": 2.0,
        },
    ]
    metrics = compute_metrics(cases, results)
    assert metrics["intent_accuracy"] == 1.0
    assert metrics["system_accuracy"] == 1.0
    assert metrics["hit_at_1"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["correct_abstention_rate"] == 1.0
    assert metrics["unsafe_accept_count"] == 0
```

- [ ] **Step 2: Run RED**

Expected failure: `compute_metrics` is missing.

- [ ] **Step 3: Implement metrics with zero-division safety**

Implement:

```python
def compute_metrics(cases: list[dict], results: list[dict], k: int = 3) -> dict: ...
```

Return counts plus `intent_accuracy`, `system_accuracy`, `hit_at_1`, `hit_at_3`, `mrr`, `precision_at_3`, `correct_abstention_rate`, `unsafe_accept_count`, `system_leakage_count`, `p50_total_seconds`, `p95_total_seconds`, and `execution_failures`.

- [ ] **Step 4: Add edge-case tests**

Cover no relevance cases, no abstention cases, wrong ranking, wrong system, accepted case that should abstain, failed case result, and invalid `k`.

- [ ] **Step 5: Run GREEN and commit**

Run Ruff and full pytest.

---

### Task 3: Implement threshold sweep without duplicate model calls

**Files:**
- Modify: `src/ai_service_desk/engine/evaluation.py`
- Modify: `tests/engine/test_evaluation.py`

**Interfaces:**
- Consumes: index data/matrix, classifier client, embedder, cases, thresholds.
- Produces:
  - `evaluate_thresholds(...) -> dict[float, dict]`
  - `recommend_synthetic_threshold(metrics_by_threshold: dict[float, dict]) -> float | None`
  - `calibration_decision(recommendation: float | None, has_real_gold: bool) -> dict`

- [ ] **Step 1: Write failing tests proving one classify/embed per case**

Use counting fakes and two thresholds:

```python
def test_threshold_sweep_reuses_classification_and_embedding() -> None:
    ...
    report = evaluate_thresholds(..., thresholds=[0.60, 0.65])
    assert fake_client.chat_calls == len(cases)
    assert fake_embedder.text_count == len(cases)
    assert set(report) == {0.60, 0.65}
```

- [ ] **Step 2: Run RED**

Expected failure: threshold sweep interfaces are missing.

- [ ] **Step 3: Implement cached preparation and repeated `retrieve`**

For each case:

```python
classification = classify_ticket(case["query"], client.chat)
query_vector = embedder.embed([case["query"]])[0]
```

Then reuse those values across all thresholds and call existing `retrieve` unchanged.

- [ ] **Step 4: Implement hard-gate recommendation**

A threshold is eligible only when:

```text
system_leakage_count == 0
unsafe_accept_count == 0
ambiguous_context_failures == 0
unknown_system_failures == 0
```

Among eligible thresholds, sort by descending abstention accuracy, hit@3, MRR, then ascending threshold.

- [ ] **Step 5: Implement calibration HOLD policy**

```python
def calibration_decision(recommendation: float | None, has_real_gold: bool) -> dict:
    if not has_real_gold:
        return {
            "decision": "HOLD",
            "runtime_threshold": 0.65,
            "reason": "no_real_labeled_gold_set",
            "synthetic_recommendation": recommendation,
        }
    ...
```

Do not implement automatic runtime-threshold mutation in Phase 3.

- [ ] **Step 6: Run GREEN and commit**

Run Ruff and full pytest.

---

### Task 4: Add safe CLI evaluation and report

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Modify: `src/ai_service_desk/engine/evaluation.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/engine/test_evaluation.py`

**Interfaces:**
- Produces CLI command `evaluate`.
- Produces aggregate report writer output with no query text or corporate candidate identifiers.

- [ ] **Step 1: Write failing CLI tests**

Require parser fields:

```text
--index
--cases
--report
--checkout
--url
```

Mock the evaluator and assert CLI output contains only aggregate fields.

- [ ] **Step 2: Run RED**

Expected failure: `evaluate` command is missing.

- [ ] **Step 3: Implement CLI command**

The command loads cases, constructs local client/embedder, evaluates the default sweep `[0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]`, writes aggregate JSON and prints only counts/metrics/recommendation/decision.

- [ ] **Step 4: Add privacy regression tests**

Assert stdout and report never contain fixture query text. For a real-data mode, candidate IDs must not be included in the persisted report.

- [ ] **Step 5: Run GREEN and commit**

Run Ruff and full pytest.

---

### Task 5: Add Phase 3 workflow, documentation and Dell verification

**Files:**
- Create: `.github/workflows/phase3-evaluation.yml`
- Modify: `tests/test_workflows.py`
- Create: `docs/evaluation/phase-3.md`
- Modify: `README.md`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Permanent manual workflow `phase3-evaluation.yml` on Dell.

- [ ] **Step 1: Write failing structural workflow test**

Require:

```text
workflow_dispatch:
self-hosted
Windows
X64
ai-service-desk
ollama
python -m ai_service_desk evaluate
phase3_eval_corpus.csv
phase3_eval_cases.jsonl
```

Forbid:

```text
upload-artifact
--show-history
Get-Content
```

- [ ] **Step 2: Run RED**

Expected failure: workflow is absent.

- [ ] **Step 3: Create permanent workflow**

Workflow steps:

1. checkout target ref;
2. verify Python 3.14;
3. install project;
4. build synthetic evaluation index in `RUNNER_TEMP` using existing `index` command;
5. execute `evaluate` with actual local Ollama;
6. fail if hard gates fail;
7. run safe behavior checks against the existing 240-ticket demo index without writing candidate content;
8. keep real report under `C:\ai-service-desk-data\phase-3\reports`;
9. no artifact upload.

- [ ] **Step 4: Document interpretation**

`docs/evaluation/phase-3.md` must state clearly:

```text
Synthetic benchmark metrics are regression evidence, not real-corpus accuracy.
Runtime threshold remains 0.65 because no real human-labeled gold set exists.
```

Update README and roadmap with Phase 3 status and the calibration decision.

- [ ] **Step 5: Run hosted GREEN**

Confirm Python 3.14 setup, Ruff lint, Ruff format and full pytest all succeed.

- [ ] **Step 6: Run Dell evaluation**

Use a temporary push-trigger helper only if the connector still cannot dispatch the permanent `workflow_dispatch` workflow. Remove helper after the run. Verify the actual local models and synthetic benchmark complete successfully.

- [ ] **Step 7: Record decision and final review**

Update documentation with aggregate results only. Confirm no corporate data files are in the PR.

- [ ] **Step 8: Merge PR**

After final review and green checks, merge into `main`. Do not delete local corporate data or the Phase 2 demo index.

---

## Self-review result

- Spec coverage: all benchmark, metric, threshold, privacy, workflow and calibration-decision requirements map to Tasks 1-5.
- Placeholder scan: no TODO/TBD implementation placeholders are used.
- Type consistency: loader, metrics, sweep, recommendation and calibration interfaces are defined once and consumed consistently.
- Scope control: no RAG, KB, reranker, model training, new vector database, UI or runtime threshold mutation is included.
