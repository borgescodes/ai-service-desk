# Phase 4 Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated approved-knowledge layer that validates synthetic FAQ content, indexes only `APPROVED` articles through the existing vector infrastructure, enforces fail-closed `APPROVED_KNOWLEDGE` provenance, and returns only literal approved answers when system, intent and score gates pass.

**Architecture:** Keep the public knowledge domain independent from ticket semantics. `knowledge.py` owns schema validation, approved filtering, the private projection required by `build_index`, knowledge provenance, and safe index loading. `knowledge_retrieval.py` owns context-gated similarity search and literal answer return. Existing `index.py`, `retrieval.py` and `classification.py` remain unchanged unless a reproducible blocking test proves the dedicated layer cannot satisfy the approved spec.

**Tech Stack:** Python 3.14, standard library, pandas, NumPy, pytest, Ruff, existing Ollama client, `qwen3.5:4b`, `qwen3-embedding:0.6b`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-07-phase-4-knowledge-base-design.md`

## Global Constraints

- Python remains `>=3.14,<3.15`.
- Runtime threshold remains exactly `0.65` by default.
- Public knowledge fields are `knowledge_id`, `title`, `question`, `answer`, `system`, `intent`, `tags`, `source`, `status`, `reviewed_by`, `reviewed_at`, `version`.
- `build_index` and `load_index` are infrastructure only. Ticket-shaped names introduced by the adapter are private implementation details.
- Only `APPROVED` articles may enter a knowledge index. `DRAFT` and `RETIRED` never enter `documents.jsonl` and never produce official guidance.
- Official guidance is the exact stored `answer`. No LLM rewrite, summary, completion or invented procedure is allowed in Phase 4.
- Knowledge search must fail closed unless the index is unequivocally identified as `APPROVED_KNOWLEDGE` and provenance matches the loaded manifest and documents.
- A historical ticket index must always be rejected by knowledge search.
- No fallback between systems or intents. Unknown system, ambiguous context, mismatch and low evidence all abstain.
- No corporate ticket data, real identifiers or real histories enter Git, fixtures, logs or GitHub artifacts.
- Phase 4 fixtures are fully synthetic.
- Do not modify `src/ai_service_desk/engine/index.py`, `retrieval.py` or `classification.py` without first presenting a reproducible failing test, technical cause, minimal required change and regression risk.

---

### Task 1: Knowledge schema, loader and private projection round trip

**Files:**
- Create: `src/ai_service_desk/engine/knowledge.py`
- Create: `tests/engine/test_knowledge.py`
- Create: `knowledge/phase4_synthetic_faq.jsonl`

**Interfaces:**
- Consumes: `ALLOWED_INTENTS` from `classification.py`, `build_index`, `load_index`, `atomic_json`, `RECIPE` from `index.py`.
- Produces:
  - `load_knowledge(path: str | Path) -> list[dict]`
  - `approved_articles(articles: list[dict]) -> list[dict]`
  - private `_project_approved_articles(articles: list[dict]) -> pandas.DataFrame`
  - constants `KNOWLEDGE_SCHEMA_VERSION = 1`, `KNOWLEDGE_DOMAIN = "APPROVED_KNOWLEDGE"`, `PROJECTION_RECIPE = "knowledge-search-v1"`.

- [ ] **Step 1: Write RED tests for the public schema**

Tests must prove valid JSONL loads and invalid content rejects the entire file. Cover duplicate IDs, unknown fields, invalid status, empty answer, invalid intent, bad tags, invalid positive integer version, and `APPROVED` without reviewer or timezone-aware review timestamp.

```python
def test_load_knowledge_requires_review_metadata_for_approved(tmp_path: Path) -> None:
    article = valid_article()
    article["reviewed_by"] = ""
    path = write_articles(tmp_path, [article])
    with pytest.raises(ValueError, match="review"):
        load_knowledge(path)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
pytest tests/engine/test_knowledge.py -v
```

Expected: collection/import failure because `knowledge.py` does not yet exist.

- [ ] **Step 3: Implement the minimal schema loader and approved filter**

Use exact field-set validation and reject partial loading. Parse `reviewed_at` with `datetime.fromisoformat`; when status is `APPROVED`, require a non-empty reviewer and timezone-aware datetime. Do not add transitions between statuses.

- [ ] **Step 4: Write RED tests for private projection**

Require:

```python
projected = _project_approved_articles(articles)
assert projected.ticket_id.tolist() == projected.knowledge_id.tolist()
assert projected.status.eq("APPROVED").all()
assert "answer" in projected.columns
assert projected.iloc[0].texto_busca == (
    title + "\n" + question + "\n" + system + "\n" + intent + "\n" + " ".join(tags)
)
```

Also assert the answer is not part of `texto_busca`.

- [ ] **Step 5: Implement private projection only in `knowledge.py`**

The projected `DataFrame` contains internal `ticket_id` and `texto_busca`, plus every public knowledge field. `ticket_id` is exactly `knowledge_id`. Tags are serialized deterministically so `corpus_bytes` remains reproducible.

- [ ] **Step 6: Write the mandatory round-trip RED test using real `build_index` and `load_index`**

Use a deterministic fake embedder and a fixture containing one `APPROVED`, one `DRAFT` and one `RETIRED` article. Build only the approved projection, load it back, then assert:

```python
assert loaded.loc[0, "knowledge_id"] == approved["knowledge_id"]
assert loaded.loc[0, "answer"] == approved["answer"]
assert loaded.loc[0, "system"] == approved["system"]
assert loaded.loc[0, "intent"] == approved["intent"]
assert loaded.loc[0, "status"] == "APPROVED"
assert loaded.loc[0, "reviewed_by"] == approved["reviewed_by"]
assert loaded.loc[0, "reviewed_at"] == approved["reviewed_at"]
assert int(loaded.loc[0, "version"]) == approved["version"]
assert loaded.loc[0, "ticket_id"] == approved["knowledge_id"]
assert len(loaded) == 1
```

Add a second build where only `answer` changes. Assert `manifest["source_hash"]` changes even though the projected `texto_busca` stays equal.

- [ ] **Step 7: Run the round-trip gate**

Run:

```bash
pytest tests/engine/test_knowledge.py -v
```

Do not advance if preservation fails. If it fails because of `build_index` behavior, stop and report the required blocking evidence before any foundation change.

- [ ] **Step 8: Add the versioned synthetic FAQ source and commit**

Include a small fully fictitious set covering CIGAM access, SIAGRI access, printer, VPN/network, software install and Outlook guidance, plus at least one `DRAFT` and one `RETIRED` article to exercise exclusion.

Commit:

```bash
git add src/ai_service_desk/engine/knowledge.py tests/engine/test_knowledge.py knowledge/phase4_synthetic_faq.jsonl
git commit -m "feat: add approved knowledge schema and projection"
```

---

### Task 2: Fail-closed provenance and knowledge index lifecycle

**Files:**
- Modify: `src/ai_service_desk/engine/knowledge.py`
- Modify: `tests/engine/test_knowledge.py`

**Interfaces:**
- Produces:
  - `build_knowledge_index(source: str | Path, directory: str | Path, embedder, batch_size: int = 10) -> dict`
  - `load_knowledge_index(directory: str | Path) -> tuple[pandas.DataFrame, numpy.ndarray, dict]`
  - `knowledge-provenance.json` with `domain == "APPROVED_KNOWLEDGE"`.

- [ ] **Step 1: Write RED tests for index creation**

Require `build_knowledge_index` to load and validate the source, filter only `APPROVED`, reject a source with zero approved articles, project privately, call the existing `build_index`, and create provenance only after a complete manifest exists.

- [ ] **Step 2: Write RED tests for provenance binding**

Build a knowledge index then assert provenance contains and matches:

```text
version = 1
domain = APPROVED_KNOWLEDGE
knowledge_schema_version = 1
projection_recipe = knowledge-search-v1
approved_only = true
source_hash = manifest.source_hash
matrix_hash = manifest.matrix_hash
rows = manifest.rows
dimensions = manifest.dimensions
model = manifest.model
model_digest = manifest.model_digest
index_recipe = manifest.recipe
```

- [ ] **Step 3: Implement atomic provenance creation**

Reuse `atomic_json`. If an existing provenance sidecar is present, validate it before reuse. Never silently overwrite a divergent sidecar.

- [ ] **Step 4: Write RED fail-closed tests**

Each condition must raise a clear `ValueError` before search is possible:

- sidecar missing;
- invalid JSON;
- wrong `domain`;
- `approved_only` false;
- wrong projection recipe;
- source or matrix hash mismatch;
- rows, dimensions, model, digest or index recipe mismatch;
- document missing a required public field;
- document with `status != APPROVED`;
- `ticket_id != knowledge_id`;
- duplicate `knowledge_id`;
- empty answer.

- [ ] **Step 5: Prove historical index rejection**

Build a normal historical index with `build_index` from a ticket-like `DataFrame`, then call `load_knowledge_index`. Expected: explicit rejection for missing valid `APPROVED_KNOWLEDGE` provenance. There is no fallback.

- [ ] **Step 6: Implement strict `load_knowledge_index`**

Call the existing `load_index`, then validate the sidecar and every loaded document against the knowledge contract. Return loaded data, matrix and provenance only after all checks pass.

- [ ] **Step 7: Run GREEN and foundation regression guard**

Run:

```bash
pytest tests/engine/test_knowledge.py tests/engine/test_index.py -v
```

Confirm `index.py` remains byte-for-byte unchanged in the branch diff.

- [ ] **Step 8: Commit**

```bash
git add src/ai_service_desk/engine/knowledge.py tests/engine/test_knowledge.py
git commit -m "feat: enforce approved knowledge provenance"
```

---

### Task 3: Context-gated knowledge retrieval with literal answers

**Files:**
- Create: `src/ai_service_desk/engine/knowledge_retrieval.py`
- Create: `tests/engine/test_knowledge_retrieval.py`

**Interfaces:**
- Consumes: `classify_ticket`, `explicit_systems`, `SYSTEM_ALIASES`, `load_knowledge_index`, embedder.
- Produces:
  - `retrieve_knowledge(data, matrix, query, classification, text, threshold=0.65) -> dict`
  - `KnowledgeEngine(index_directory, client, embedder, threshold=0.65)` with `search(text: str) -> dict`
  - `format_knowledge_result(result: dict) -> str`.

- [ ] **Step 1: Write RED tests for pure retrieval**

Use a tiny synthetic `DataFrame` and normalized matrix. Require exact system and intent matching, no fallback, highest eligible score, and threshold `0.65`.

- [ ] **Step 2: Cover required abstention reasons**

Tests must require `status == "NO_APPROVED_KNOWLEDGE"` for:

```text
CONTEXTO_AMBIGUO
UNKNOWN_SYSTEM
SYSTEM_MISMATCH
INTENT_MISMATCH
BELOW_THRESHOLD
```

A query with no established system may only search generic articles where `system == ""`.

- [ ] **Step 3: Implement pure retrieval**

Validate matrix/query dimensions and finite values. Build the eligible pool before scoring. Never widen the pool to another system or intent. Return at most one official knowledge article in Phase 4.

- [ ] **Step 4: Prove literal answer behavior**

Write a test with punctuation and wording that would be visibly changed by rewriting:

```python
answer = "Passo 1: use APENAS o ambiente ficticio. Depois, confirme: OK?"
result = retrieve_knowledge(...)
assert result["knowledge"]["answer"] == answer
assert "ticket_id" not in result["knowledge"]
```

- [ ] **Step 5: Implement `KnowledgeEngine`**

Constructor must call `load_knowledge_index`, thereby enforcing provenance before any search. `search` classifies once and embeds once only when an eligible pool exists. It uses the existing classifier and embedder without a parallel pipeline.

- [ ] **Step 6: Add ambiguous and unknown system engine tests**

Use fakes to prove ambiguous context does not embed and unknown system does not borrow another system article.

- [ ] **Step 7: Run GREEN**

```bash
pytest tests/engine/test_knowledge_retrieval.py tests/engine/test_knowledge.py -v
```

- [ ] **Step 8: Commit**

```bash
git add src/ai_service_desk/engine/knowledge_retrieval.py tests/engine/test_knowledge_retrieval.py
git commit -m "feat: add safe knowledge retrieval"
```

---

### Task 4: Knowledge CLI contracts

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_knowledge_cli.py`
- Modify: `tests/test_cli.py` only for the help-command assertion if necessary.

**Interfaces:**
- `knowledge-validate --file <knowledge.jsonl>`
- `knowledge-index --file <knowledge.jsonl> --index <dir> --batch-size 10 --url <loopback>`
- `knowledge-search --index <dir> --query <text> --threshold 0.65 --url <loopback>`
- `knowledge-smoke --index <dir> --report <path> --url <loopback>` after Task 5 provides the smoke runner.

- [ ] **Step 1: Write RED CLI parser tests**

Assert help lists `knowledge-validate`, `knowledge-index`, `knowledge-search` and later `knowledge-smoke`. Verify the default threshold is `0.65`.

- [ ] **Step 2: Write RED validation behavior test**

`knowledge-validate` must not instantiate `OllamaClient`. It prints counts only, such as total, approved, draft and retired. It does not print full answers.

- [ ] **Step 3: Implement `knowledge-validate`**

Use `load_knowledge` and aggregate statuses locally.

- [ ] **Step 4: Write RED index forwarding test and implement `knowledge-index`**

Instantiate `OllamaClient` and `LocalEmbedder` only for the index path. Call `build_knowledge_index`. Print safe metadata, never article content.

- [ ] **Step 5: Write RED search fail-closed test and implement `knowledge-search`**

A missing or historical index must surface a clear `ERRO:` and return exit code 1. A successful search prints the literal approved answer through `format_knowledge_result`.

- [ ] **Step 6: Run GREEN**

```bash
pytest tests/test_knowledge_cli.py tests/test_cli.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/ai_service_desk/cli.py tests/test_knowledge_cli.py tests/test_cli.py
git commit -m "feat: add knowledge base CLI"
```

---

### Task 5: Competition smoke and synthetic acceptance cases

**Files:**
- Create: `src/ai_service_desk/engine/knowledge_smoke.py`
- Create: `tests/engine/test_knowledge_smoke.py`
- Modify: `tests/test_knowledge_cli.py`

**Interfaces:**
- Produces `run_knowledge_smoke(index, report_path, base_url="http://127.0.0.1:11434") -> dict`.

- [ ] **Step 1: Write RED smoke contract tests using fakes**

The smoke report is aggregate and synthetic. It must not include article answers, query text or corporate identifiers.

- [ ] **Step 2: Define at least five official synthetic acceptance cases**

Cover:

1. known CIGAM access problem finds the approved CIGAM FAQ;
2. same semantic problem targeting SIAGRI never returns CIGAM knowledge;
3. a question corresponding only to a `DRAFT` article abstains;
4. unknown question or weak evidence abstains;
5. explicit CIGAM plus SIAGRI context abstains without automatic answer.

Add an optional sixth case for `RETIRED` exclusion.

- [ ] **Step 3: Implement safe smoke runner**

The report may store case names, statuses, reasons, expected/actual knowledge IDs when synthetic, scores and pass booleans. Do not include answers or raw query text.

- [ ] **Step 4: Wire `knowledge-smoke` CLI**

The command writes the report and prints only aggregate pass/fail information.

- [ ] **Step 5: Run GREEN**

```bash
pytest tests/engine/test_knowledge_smoke.py tests/test_knowledge_cli.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/ai_service_desk/engine/knowledge_smoke.py tests/engine/test_knowledge_smoke.py tests/test_knowledge_cli.py src/ai_service_desk/cli.py
git commit -m "test: add phase 4 knowledge smoke"
```

---

### Task 6: Documentation and Dell homologation workflow

**Files:**
- Create: `docs/knowledge/phase-4.md`
- Create: `.github/workflows/phase4-knowledge-smoke.yml`
- Modify: `README.md`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Manual Dell workflow uses only the synthetic versioned knowledge source and local Ollama.
- No upload artifact and no printing complete answers.

- [ ] **Step 1: Write RED workflow policy test**

Require:

```text
workflow_dispatch:
target_ref:
self-hosted
Windows
X64
ai-service-desk
ollama
python -m ai_service_desk knowledge-index
python -m ai_service_desk knowledge-smoke
knowledge/phase4_synthetic_faq.jsonl
http://127.0.0.1:11434
```

Forbid `upload-artifact`, `Get-Content` and `--show-history`.

- [ ] **Step 2: Implement manual Phase 4 workflow**

Checkout requested ref, verify Python 3.14, install project, verify models with `doctor`, build the synthetic knowledge index in `RUNNER_TEMP`, run `knowledge-smoke`, and keep any generated report local to the runner temp directory.

- [ ] **Step 3: Document Phase 4**

Explain public schema, status semantics, private projection, fail-closed provenance, literal answer rule, threshold `0.65`, CLI examples and competition smoke. State explicitly that historical retrieval remains evidence and cannot become official knowledge automatically.

- [ ] **Step 4: Update README without changing Phase 3 claims**

Add the knowledge commands and the conceptual separation between historical evidence and approved knowledge.

- [ ] **Step 5: Run GREEN**

```bash
pytest tests/test_workflows.py -v
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/phase4-knowledge-smoke.yml docs/knowledge/phase-4.md README.md tests/test_workflows.py
git commit -m "docs: document phase 4 knowledge base"
```

---

### Task 7: Full verification, regression review and pull request

**Files:**
- Review every changed Phase 4 file.
- Do not modify `index.py`, `retrieval.py`, or `classification.py` unless an approved blocking process has occurred.

**Interfaces:**
- Hosted CI on the PR is the Python 3.14 lint, format and pytest gate.
- Dell Phase 4 smoke is the real Ollama compatibility gate.

- [ ] **Step 1: Run full local verification**

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

- [ ] **Step 2: Verify foundation files remain untouched**

```bash
git diff main...HEAD -- src/ai_service_desk/engine/index.py src/ai_service_desk/engine/retrieval.py src/ai_service_desk/engine/classification.py
```

Expected: empty diff.

- [ ] **Step 3: Verify no unsafe generated files or real data entered the branch**

Inspect changed filenames and grep for `documents.jsonl`, `embeddings.npy`, real ticket IDs, histories and secrets. Only the intentionally synthetic knowledge fixture may contain article content.

- [ ] **Step 4: Open the PR against `main`**

PR title:

```text
feat: add phase 4 approved knowledge base
```

The description must summarize schema, approved-only indexing, fail-closed provenance, safe retrieval, synthetic smoke, test evidence, and explicitly state that Phase 1 to 3 foundation modules were not changed.

- [ ] **Step 5: Require hosted CI green**

Inspect the PR commit workflow run. Hosted CI must pass Ruff and the full pytest suite on Python 3.14.

- [ ] **Step 6: Run or inspect Dell Phase 4 smoke**

The manual/self-hosted validation must use `qwen3.5:4b` and `qwen3-embedding:0.6b`, produce no GitHub artifact with knowledge contents, and pass all official Phase 4 synthetic cases.

- [ ] **Step 7: Final review**

Review PR diff for scope creep, public leakage of ticket semantics, hidden fallback, answer rewriting, provenance bypass, threshold drift and unsafe logging. Resolve concrete defects with a new failing test first.

- [ ] **Step 8: Stop at 95%**

Report PR number, head SHA, hosted CI result, Dell homologation evidence, total tests, and unchanged foundation files. Do not merge. Phase 4 reaches 100% only after the user's explicit merge approval.
