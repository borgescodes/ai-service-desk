# Phase 2A Competition Demo Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic 240-ticket real-data demo subset and validate the existing retrieval engine against it on the Dell in minutes rather than waiting for the 15,542-ticket scale index.

**Architecture:** Extend the existing Phase 2 corpus and smoke infrastructure. A new deterministic selector creates a real subset outside Git; a generic internal smoke core reuses the same index/retrieval safeguards for both the full corpus and the demo subset; the existing full-corpus path remains intact as Phase 2B.

**Tech Stack:** Python 3.14, pandas, NumPy, requests, pytest, Ruff, Ollama `qwen3.5:4b`, Ollama `qwen3-embedding:0.6b`.

**Spec:** `docs/superpowers/specs/2026-09-07-phase-2a-competition-demo-retrieval-design.md`

## Global Constraints

- Python remains `>=3.14,<3.15`.
- Runtime dependencies remain NumPy, pandas and requests only.
- The retrieval threshold remains exactly `0.65`.
- Real corpus, real subset, real index and real reports remain outside Git.
- No GitHub artifact may contain corporate data or the real subset/index/report.
- Hosted CI remains fully synthetic and must not contact Ollama.
- History remains `HISTORICO_NAO_VALIDADO` and is not displayed by automated smoke tests.
- Demo subset results must not be presented as precision, recall, coverage or global automation metrics.

---

### Task 1: Deterministic demo subset selector

**Files:**
- Create: `src/ai_service_desk/engine/demo_subset.py`
- Create: `tests/engine/test_demo_subset.py`

**Interfaces:**
- Consumes: `pandas.DataFrame`, `ai_service_desk.engine.index.corpus_bytes`, `ai_service_desk.engine.validation.normalize_text`.
- Produces: `build_demo_subset(data: pd.DataFrame, per_group: int = 40) -> tuple[pd.DataFrame, dict]`.
- Produces constant: `DEMO_RECIPE = "competition-demo-v1"`.

- [ ] **Step 1: Write failing tests for deterministic six-group selection**

Create synthetic rows that provide at least two candidates for each group and assert that `per_group=1` returns exactly six unique rows with group counts:

```python
{
    "cigam": 1,
    "siagri": 1,
    "printing": 1,
    "access": 1,
    "software": 1,
    "general": 1,
}
```

Run:

```bash
python -m pytest tests/engine/test_demo_subset.py -q
```

Expected: FAIL because `ai_service_desk.engine.demo_subset` does not exist.

- [ ] **Step 2: Add failing tests for reproducibility and no duplicate selection**

Call `build_demo_subset` twice with the same rows in different input order and assert equal selected `ticket_id` sequence after sorting by the selector's stored group/order fields. Assert every selected ticket is unique.

- [ ] **Step 3: Add failing tests for insufficient specific group capacity**

Use a fixture with zero SIAGRI candidates and assert:

```python
with pytest.raises(ValueError, match="siagri"):
    build_demo_subset(data, per_group=1)
```

- [ ] **Step 4: Implement the minimal selector**

Implement fixed group order:

```python
GROUPS = ("cigam", "siagri", "printing", "access", "software", "general")
```

Build normalized searchable text from `catalogo`, `area`, `item`, `title`, `texto_busca`.

Use group predicates equivalent to:

```python
cigam -> literal CIGAM
siagri -> literal SIAGRI
printing -> impressora | impressao | imprimir | printer
access -> acesso | login | autenticacao | entrar
software -> instalacao | instalar | software | programa | aplicativo
```

For every candidate compute:

```python
sha256(str(ticket_id).encode("utf-8")).hexdigest()
```

Select by ascending hash while excluding already-selected rows. Fill `general` from all remaining rows by the same hash. Raise `ValueError` when a specific group has fewer than `per_group` eligible rows.

The returned subset preserves the original corpus columns only. The report contains only counts, recipe, source row count, selected row count, per-group count, source canonical SHA-256 and subset canonical SHA-256.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/engine/test_demo_subset.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_service_desk/engine/demo_subset.py tests/engine/test_demo_subset.py
git commit -m "feat: add deterministic demo subset selector"
```

---

### Task 2: Add safe `demo-subset` CLI

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `build_demo_subset` from Task 1 and `ensure_external_path` from `engine.corpus`.
- Produces CLI command: `python -m ai_service_desk demo-subset`.

- [ ] **Step 1: Write failing parser/help test**

Extend `test_help_runs_without_ollama` to assert `demo-subset` appears.

- [ ] **Step 2: Write failing CLI behavior test**

Monkeypatch `OllamaClient` with a class that raises on construction. Use a synthetic corpus outside a synthetic checkout and invoke:

```text
demo-subset --file <source> --output <subset> --report <report> --checkout <repo> --per-group 1
```

Assert exit code 0, output/report exist, no Ollama client is created, stdout contains only aggregated row/group information and does not contain ticket text or ticket IDs.

- [ ] **Step 3: Write failing overwrite and inside-checkout tests**

Assert an existing output file is refused. Assert `--output` or `--report` inside the checkout is refused before file creation.

- [ ] **Step 4: Implement minimal CLI command**

Parser arguments:

```text
--file Path required
--output Path required
--report Path required
--checkout Path required
--per-group int default 40
```

Execution order:

1. validate `file`, `output`, `report` with `ensure_external_path`;
2. refuse existing output;
3. call `load_corpus`;
4. call `build_demo_subset`;
5. create output parent and write CSV with `sep=";"`, `encoding="utf-8-sig"`, `index=False`;
6. write report using `atomic_json`;
7. print only selected row count, per-group size and report path.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_service_desk/cli.py tests/test_cli.py
git commit -m "feat: add demo subset cli"
```

---

### Task 3: Reuse one smoke core for full corpus and demo subset

**Files:**
- Modify: `src/ai_service_desk/engine/real_smoke.py`
- Modify: `src/ai_service_desk/cli.py`
- Modify: `tests/engine/test_real_smoke.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Existing public interface retained: `run_real_smoke(...) -> dict`.
- New public interface: `run_demo_smoke(corpus_path, subset_report_path, index_directory, report_path, base_url, checkout) -> dict`.
- Internal shared interface: `_run_smoke(corpus_path, index_directory, report_path, base_url, checkout, expected: dict, corpus_report: dict) -> dict`.

- [ ] **Step 1: Write failing test that demo smoke accepts arbitrary expected row count/hash**

Use a fully synthetic corpus and fake Ollama/embedder/retrieval boundaries. The subset report provides `selected_rows` and `subset_canonical_sha256`. Assert `run_demo_smoke` validates those values rather than `15542`.

- [ ] **Step 2: Write failing test that full `run_real_smoke` keeps its current manifest contract**

Retain the existing full-corpus tests and assert they still use manifest `expected.rows` and `expected.canonical_sha256`.

- [ ] **Step 3: Refactor to shared core**

Move common path validation, Ollama setup, index construction, index validation, safe query execution, report creation and client close into `_run_smoke`.

`run_real_smoke` continues to audit against the versioned full-corpus manifest and passes the full expected values into `_run_smoke`.

`run_demo_smoke` reads the aggregate subset report and passes:

```python
{
    "rows": subset_report["selected_rows"],
    "canonical_sha256": subset_report["subset_canonical_sha256"],
}
```

The threshold remains `THRESHOLD = 0.65`.

- [ ] **Step 4: Add `demo-smoke` CLI command**

Arguments:

```text
--file Path required
--subset-report Path required
--index Path required
--report Path required
--checkout Path required
--url default http://127.0.0.1:11434
```

The command prints only `DEMO RETRIEVAL SMOKE OK` or `DEMO RETRIEVAL SMOKE REQUER REVISAO`, row/shape aggregate and report path.

- [ ] **Step 5: Run focused tests**

```bash
python -m pytest tests/engine/test_real_smoke.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_service_desk/engine/real_smoke.py src/ai_service_desk/cli.py tests/engine/test_real_smoke.py tests/test_cli.py
git commit -m "feat: add reusable demo retrieval smoke"
```

---

### Task 4: Competition demo workflow and documentation

**Files:**
- Create: `.github/workflows/demo-retrieval-smoke.yml`
- Modify: `tests/test_workflows.py`
- Modify: `README.md`
- Modify: `docs/environment/local-demo.md`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes the `demo-subset` and `demo-smoke` commands from Tasks 2 and 3.

- [ ] **Step 1: Write failing structural workflow test**

Assert the new workflow contains:

```text
workflow_dispatch
[self-hosted, Windows, X64, ai-service-desk, ollama]
demo-subset
demo-smoke
C:\ai-service-desk-data\phase-2\demo
```

Assert it does not contain `upload-artifact` or `--show-history`.

- [ ] **Step 2: Create the manual workflow**

Inputs:

```text
target_ref
corpus_path default C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv
demo_root default C:\ai-service-desk-data\phase-2\demo
```

Steps:

1. checkout target ref;
2. verify Python 3.14;
3. install project;
4. remove only prior demo subset/index/report under `demo_root` when an explicit `rebuild` input is true;
5. run `demo-subset` with `--per-group 40` when subset is absent;
6. run `demo-smoke` against `demo_subset.csv` and its aggregate subset report.

No upload step.

- [ ] **Step 3: Update documentation**

README and local demo docs must state:

- Fase 2A is the competition gate;
- the demo uses 240 deterministic real rows;
- it is not a quality metric;
- Fase 2B full 15,542-ticket index is optional evidence of scale and no longer blocks product work;
- demo files stay outside Git.

Roadmap must split the old Phase 2 entry into 2A competition demo and 2B full-corpus scale validation.

- [ ] **Step 4: Run workflow/docs tests**

```bash
python -m pytest tests/test_workflows.py tests/test_cli.py tests/engine/test_demo_subset.py tests/engine/test_real_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Run full hosted-quality equivalent**

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected: all commands PASS under Python 3.14 in hosted CI.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/demo-retrieval-smoke.yml tests/test_workflows.py README.md docs/environment/local-demo.md docs/roadmap.md
git commit -m "build: add competition demo retrieval smoke"
```

---

### Task 5: Dell homologation and PR gate

**Files:**
- No corporate data files are committed.
- PR metadata may be updated after verification.

- [ ] **Step 1: Confirm hosted CI is green**

Expected gates:

```text
Python 3.14 install = success
Ruff lint = success
Ruff format = success
pytest = success
```

- [ ] **Step 2: Run Phase 2A smoke on Dell**

Expected local paths:

```text
C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv
C:\ai-service-desk-data\phase-2\demo\demo_subset.csv
C:\ai-service-desk-data\phase-2\demo\index
C:\ai-service-desk-data\phase-2\demo\reports\subset.json
C:\ai-service-desk-data\phase-2\demo\reports\smoke.json
```

Expected aggregate evidence:

```text
selected_rows = 240
shape = [240, 1024]
complete = true
threshold = 0.65
five safe query cases complete
privacy.contains_ticket_content = false
privacy.contains_ticket_identifiers = false
```

- [ ] **Step 3: Review final PR diff**

Reject the PR if it contains `base_ti_preparada.csv`, `demo_subset.csv`, `documents.jsonl`, `embeddings.npy` or a real smoke JSON report.

- [ ] **Step 4: Mark PR ready and merge only after both hosted CI and Dell demo smoke are green**

The full 15,542-ticket Phase 2B index is not a merge gate for Phase 2A.