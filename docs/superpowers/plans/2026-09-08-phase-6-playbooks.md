# Phase 6 Playbooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic, declarative, human-approved playbooks resolved only by exact `knowledge_id`, with fail-closed provenance, no execution, and a stable machine contract for Phase 7.

**Architecture:** Phase 6 is a new domain after Phase 5. A strict JSONL source is validated, compiled against an already validated `APPROVED_KNOWLEDGE` index into a deterministic catalog plus provenance sidecar, loaded fail-closed, and resolved only by exact `knowledge_id`. The production trust chain obtains knowledge provenance by calling the existing fail-closed `load_knowledge_index(...)`; no public Phase 6 API accepts a plain caller-supplied provenance mapping as evidence of integrity.

**Tech Stack:** Python 3.14, stdlib `json`, `hashlib`, `datetime`, `pathlib`, `re`, existing pandas dependency used by the validated knowledge index, `pytest`, Ruff, existing `ai_service_desk.engine.knowledge.load_knowledge_index`, existing `atomic_json`, GitHub Actions, Dell self-hosted Windows runner.

**Spec:** `docs/superpowers/specs/2026-09-08-phase-6-playbooks-design.md`

**Approved spec head:** `849d4e6017ba54cf839971556366c4c8ead5f8dc`

**Phase 5 base:** `96fc2fd8b7c867fa7340dc75fddcbc37cbcff5c7`

## Global Constraints

- Association is exclusively by exact `knowledge_id`.
- `knowledge APPROVED -> 0..1 playbook APPROVED`.
- `playbook APPROVED -> 1..N knowledge APPROVED`.
- Two `APPROVED` playbooks for the same `knowledge_id` are an integrity error. No priority, score, tie-break, ordering preference, LLM, or probabilistic choice exists.
- Phase 6 code performs zero LLM calls, zero embeddings, zero second classification, and zero executor calls.
- A Phase 4 `knowledge-index` build may still be used as prerequisite setup in workflow/homologation. That upstream setup is not playbook selection and does not authorize Phase 6 to call embeddings itself.
- Phase 6 must not execute shell, PowerShell, scripts, processes, HTTP/API actions, commands, registry changes, or capability implementations.
- Step types are exactly `INSTRUCTION`, `CHECK`, and `ACTION_PROPOSAL`.
- `ACTION_PROPOSAL` requires symbolic `capability` matching `^[A-Z][A-Z0-9_]{2,119}$`.
- `INSTRUCTION` and `CHECK` require `capability == ""`.
- `DRAFT` and `RETIRED` never contribute title, description, instruction, capability, or step text to the operational catalog.
- `PLAYBOOK_UNAVAILABLE` is only a normal lifecycle result from a valid catalog. Corruption, conflict, schema failure, and provenance mismatch raise explicit errors before resolution.
- `playbook-provenance.json` is written only after the complete catalog has been atomically written, re-read, structurally validated, and hashed.
- Production build/load/runtime obtains current knowledge trust from `load_knowledge_index(...)` or an already validated `KnowledgeEngine`. This plan chooses the simpler public runtime contract that receives `knowledge_index_directory` and calls `load_knowledge_index(...)` internally.
- Tests may monkeypatch the imported `load_knowledge_index` boundary with controlled doubles. No production API accepts `knowledge_provenance: dict`.
- Phase 6 result owns only `status`, `reason`, `knowledge_id`, and `playbook`. It does not duplicate `answer`, `question`, `system`, `intent`, `score`, or `threshold`.
- Machine results include `capability`; user-facing formatting does not expose it automatically.
- All Phase 6 committed fixtures and playbooks are synthetic. No real corporate history, ticket text, ticket IDs, hostnames, credentials, or procedures enter Git.
- Protected Phase 1-5 files remain unchanged unless a focused failing test proves a technical blocker first: `classification.py`, `retrieval.py`, `index.py`, `knowledge.py`, `knowledge_retrieval.py`, `triage.py`.
- Gates 1 through 8 require observed RED before production implementation for that gate, followed by focused GREEN.
- Merge is forbidden until full regression, hosted CI, exact-head Dell homologation, final review, and explicit user approval.

---

## File Map

### Create

- `src/ai_service_desk/engine/playbook.py`
  - strict source schema;
  - lifecycle rules;
  - canonical JSON/hash helpers;
  - reference/cardinality validation;
  - deterministic catalog build;
  - provenance build;
  - fail-closed catalog/provenance load.

- `src/ai_service_desk/engine/playbook_resolution.py`
  - `PlaybookEngine`;
  - exact resolution;
  - machine result;
  - Phase 7 action descriptor;
  - user formatter.

- `src/ai_service_desk/engine/playbook_smoke.py`
  - strict 10-case smoke loader;
  - controlled source/catalog mutations for negative cases;
  - aggregate-only report.

- `playbooks/phase6_synthetic_playbooks.jsonl`
- `tests/fixtures/phase6_playbook_cases.jsonl`
- `tests/engine/test_playbook.py`
- `tests/engine/test_playbook_resolution.py`
- `tests/engine/test_playbook_smoke.py`
- `tests/test_playbook_cli.py`
- `.github/workflows/phase6-playbook-smoke.yml`
- `docs/playbooks/phase-6.md`

### Modify

- `src/ai_service_desk/cli.py`
- `tests/test_workflows.py`
- `README.md`

### Protected and expected unchanged

- `src/ai_service_desk/engine/classification.py`
- `src/ai_service_desk/engine/retrieval.py`
- `src/ai_service_desk/engine/index.py`
- `src/ai_service_desk/engine/knowledge.py`
- `src/ai_service_desk/engine/knowledge_retrieval.py`
- `src/ai_service_desk/engine/triage.py`

---

## Locked Interfaces

Use these exact public names unless a focused RED test proves a blocker and the plan is amended before implementation continues.

### `src/ai_service_desk/engine/playbook.py`

```text
PLAYBOOK_SCHEMA_VERSION = 1
PLAYBOOK_CATALOG_SCHEMA_VERSION = 1
PLAYBOOK_DOMAIN = "APPROVED_PLAYBOOK"
CATALOG_RECIPE = "playbook-catalog-v1"
PLAYBOOK_CATALOG_FILE = "playbook-catalog.json"
PLAYBOOK_PROVENANCE_FILE = "playbook-provenance.json"
ALLOWED_PLAYBOOK_STATUSES = {"DRAFT", "APPROVED", "RETIRED"}
ALLOWED_STEP_TYPES = {"INSTRUCTION", "CHECK", "ACTION_PROPOSAL"}

load_playbooks(path: str | Path) -> list[dict]
canonical_json_bytes(payload: object) -> bytes
sha256_bytes(payload: bytes) -> str
build_playbook_catalog(source: str | Path, knowledge_index_directory: str | Path, output_directory: str | Path) -> dict
load_playbook_catalog(directory: str | Path, knowledge_index_directory: str | Path) -> tuple[dict, dict]
```

`build_playbook_catalog(...)` and `load_playbook_catalog(...)` call the existing `load_knowledge_index(...)` internally. Neither accepts a provenance mapping from a public caller.

### `src/ai_service_desk/engine/playbook_resolution.py`

```text
PlaybookEngine(catalog_directory: str | Path, knowledge_index_directory: str | Path)
PlaybookEngine.resolve(knowledge: Mapping[str, object]) -> dict
PlaybookEngine.resolve_knowledge_id(knowledge_id: str) -> dict
action_proposal_descriptor(knowledge_id: str, playbook: Mapping[str, object], step: Mapping[str, object]) -> dict
format_playbook_result(result: Mapping[str, object]) -> str
```

Machine result keys are always exactly:

```text
status
reason
knowledge_id
playbook
```

Normal statuses/reasons:

```text
KNOWLEDGE_ONLY / NO_PLAYBOOK
PLAYBOOK_FOUND / MATCH
PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED
PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED
```

Integrity errors are exceptions, never normal statuses.

### Phase 7 descriptor

For an `ACTION_PROPOSAL`, the projection keys are exactly:

```text
knowledge_id
playbook_id
playbook_version
step_id
type
capability
```

---

## Shared Test Helpers Required by Gates 1-6

Define these concrete helpers in `tests/engine/test_playbook.py` and reuse equivalent data in `tests/engine/test_playbook_resolution.py`. Do not create a production fixture module just for tests.

```python
import json
from pathlib import Path

import pandas as pd
import pytest


def valid_step(
    step_id: str = "STEP-01",
    step_type: str = "INSTRUCTION",
    capability: str = "",
) -> dict:
    return {
        "step_id": step_id,
        "type": step_type,
        "title": "Passo sintetico",
        "instruction": "Execute apenas a verificacao ficticia descrita.",
        "capability": capability,
    }


def valid_playbook(
    playbook_id: str = "PB-SYN-001",
    status: str = "APPROVED",
    knowledge_ids: list[str] | None = None,
    steps: list[dict] | None = None,
) -> dict:
    return {
        "playbook_id": playbook_id,
        "title": "Playbook sintetico",
        "description": "Procedimento totalmente sintetico para testes.",
        "knowledge_ids": knowledge_ids or ["KB-SYN-PRINT-001"],
        "steps": steps or [valid_step()],
        "source": "SYNTHETIC_DEMO",
        "status": status,
        "reviewed_by": "synthetic-reviewer" if status == "APPROVED" else "",
        "reviewed_at": "2026-09-08T01:00:00-03:00" if status == "APPROVED" else "",
        "version": 1,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def trusted_knowledge_provenance(source_hash: str = "b" * 64) -> dict:
    return {
        "version": 1,
        "domain": "APPROVED_KNOWLEDGE",
        "knowledge_schema_version": 1,
        "projection_recipe": "knowledge-search-v1",
        "approved_only": True,
        "source_hash": source_hash,
        "matrix_hash": "c" * 64,
        "rows": 2,
        "dimensions": 1024,
        "model": "qwen3-embedding:0.6b",
        "model_digest": "d" * 64,
        "index_recipe": "semantic-index-v1",
    }


def trusted_index_double(ids: list[str], source_hash: str = "b" * 64):
    data = pd.DataFrame({"knowledge_id": ids})
    return data, object(), trusted_knowledge_provenance(source_hash)
```

If the actual Phase 4 `RECIPE` constant differs from the illustrative `"semantic-index-v1"`, the test helper must import `RECIPE` from `ai_service_desk.engine.index` instead of hard-coding a different value. Do not modify the protected constant.

---

# Gate 1 - Schema and Structural Validation

### Task 1: Strict source loader

**Files:**
- Create: `src/ai_service_desk/engine/playbook.py`
- Create: `tests/engine/test_playbook.py`

**Produces:** `load_playbooks`, source constants, canonical JSON/hash helpers.

- [ ] **Step 1: Write the first failing tests**

Create these exact tests with full bodies:

```python
def test_load_playbooks_accepts_strict_valid_source(tmp_path: Path) -> None:
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    rows = load_playbooks(source)
    assert len(rows) == 1
    assert rows[0]["playbook_id"] == "PB-SYN-001"


def test_load_playbooks_rejects_missing_field(tmp_path: Path) -> None:
    row = valid_playbook()
    row.pop("description")
    source = tmp_path / "missing.jsonl"
    write_jsonl(source, [row])
    with pytest.raises(ValueError, match="campos de playbook invalidos"):
        load_playbooks(source)


def test_load_playbooks_rejects_extra_field(tmp_path: Path) -> None:
    row = valid_playbook()
    row["unexpected"] = True
    source = tmp_path / "extra.jsonl"
    write_jsonl(source, [row])
    with pytest.raises(ValueError, match="campos de playbook invalidos"):
        load_playbooks(source)
```

- [ ] **Step 2: Run RED**

```bash
pytest tests/engine/test_playbook.py::test_load_playbooks_accepts_strict_valid_source tests/engine/test_playbook.py::test_load_playbooks_rejects_missing_field tests/engine/test_playbook.py::test_load_playbooks_rejects_extra_field -v
```

Expected: import or missing-function failure. Do not write production implementation before observing this failure.

- [ ] **Step 3: Add the exact schema test matrix**

Add one test per row below. Each test mutates `valid_playbook()`, writes one JSONL source, calls `load_playbooks`, and asserts `ValueError`.

| Test name | Mutation | Expected failure theme |
| --- | --- | --- |
| `test_rejects_duplicate_playbook_id` | write same `playbook_id` twice | duplicate ID |
| `test_rejects_empty_source` | zero nonblank lines | empty base |
| `test_rejects_invalid_utf8` | write invalid bytes | UTF-8 |
| `test_rejects_invalid_json` | write `{not-json}` | invalid JSON |
| `test_rejects_invalid_status` | `status="ACTIVE"` | lifecycle |
| `test_rejects_approved_without_reviewer` | blank `reviewed_by` | approval review |
| `test_rejects_approved_without_reviewed_at` | blank `reviewed_at` | approval review |
| `test_rejects_reviewed_at_without_timezone` | `2026-09-08T01:00:00` | timezone |
| `test_rejects_boolean_version` | `version=True` | positive integer |
| `test_rejects_zero_version` | `version=0` | positive integer |
| `test_rejects_duplicate_knowledge_id_inside_playbook` | same ID twice | duplicate link |
| `test_rejects_empty_knowledge_ids` | `[]` | 1..20 links |
| `test_rejects_more_than_20_knowledge_ids` | 21 synthetic IDs | 1..20 links |
| `test_rejects_empty_steps` | `[]` | 1..20 steps |
| `test_rejects_more_than_20_steps` | 21 unique synthetic steps | 1..20 steps |
| `test_rejects_duplicate_step_id` | two `STEP-01` | duplicate step ID |
| `test_rejects_invalid_step_type` | `type="EXECUTE"` | official type |
| `test_action_proposal_requires_capability` | action with empty capability | symbolic capability |
| `test_instruction_rejects_capability` | instruction with `DEMO_X` | empty capability |
| `test_check_rejects_capability` | check with `DEMO_X` | empty capability |
| `test_rejects_invalid_capability` | `pwsh.exe` | regex |
| `test_rejects_overlong_playbook_id` | 121 chars | limit 120 |
| `test_rejects_overlong_title` | 181 chars | limit 180 |
| `test_rejects_overlong_description` | 1001 chars | limit 1000 |
| `test_rejects_overlong_step_instruction` | 1501 chars | limit 1500 |

Also add positive lifecycle tests for all three statuses and positive step-type tests for `INSTRUCTION`, `CHECK`, and `ACTION_PROPOSAL` with a valid capability for the last type.

- [ ] **Step 4: Implement the strict validator**

Production constants and exact field sets:

```python
PLAYBOOK_SCHEMA_VERSION = 1
PLAYBOOK_CATALOG_SCHEMA_VERSION = 1
PLAYBOOK_DOMAIN = "APPROVED_PLAYBOOK"
CATALOG_RECIPE = "playbook-catalog-v1"
PLAYBOOK_CATALOG_FILE = "playbook-catalog.json"
PLAYBOOK_PROVENANCE_FILE = "playbook-provenance.json"
ALLOWED_PLAYBOOK_STATUSES = {"DRAFT", "APPROVED", "RETIRED"}
ALLOWED_STEP_TYPES = {"INSTRUCTION", "CHECK", "ACTION_PROPOSAL"}
CAPABILITY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,119}$")
PLAYBOOK_FIELDS = {
    "playbook_id", "title", "description", "knowledge_ids", "steps",
    "source", "status", "reviewed_by", "reviewed_at", "version",
}
STEP_FIELDS = {"step_id", "type", "title", "instruction", "capability"}
```

Limits:

```text
playbook_id 1..120
playbook title 1..180
description 1..1000
knowledge_ids 1..20, each 1..120
steps 1..20
step_id 1..120
step title 1..180
instruction 1..1500
capability 0..120
source 1..120
reviewed_by 0..120
reviewed_at 0..80
version positive non-bool int
```

Canonical helpers are exactly:

```python
def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
```

- [ ] **Step 5: Run GREEN**

```bash
pytest tests/engine/test_playbook.py -v
ruff check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
ruff format --check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
```

Expected: all pass.

- [ ] **Step 6: Commit Gate 1**

```bash
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: validate declarative playbook schema"
```

---

# Gate 2 - Build Against APPROVED_KNOWLEDGE, References, and Cardinality

### Task 2: Reference validation and active ownership

**Files:**
- Modify: `src/ai_service_desk/engine/playbook.py`
- Modify: `tests/engine/test_playbook.py`

**Produces:** `build_playbook_catalog(...)` reference/cardinality layer.

- [ ] **Step 1: Write RED trust-boundary test**

```python
def test_build_uses_validated_knowledge_index_loader(monkeypatch, tmp_path: Path) -> None:
    calls: list[Path] = []

    def fake_load_knowledge_index(path):
        calls.append(Path(path))
        return trusted_index_double(["KB-SYN-PRINT-001"])

    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        fake_load_knowledge_index,
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert calls == [tmp_path / "knowledge"]
```

- [ ] **Step 2: Run RED**

```bash
pytest tests/engine/test_playbook.py::test_build_uses_validated_knowledge_index_loader -v
```

Expected: missing `build_playbook_catalog`.

- [ ] **Step 3: Add concrete reference tests**

```python
def test_build_accepts_reference_present_in_approved_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    provenance = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert provenance["active_links"] == 1


def test_build_rejects_reference_absent_from_approved_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-OTHER-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    with pytest.raises(ValueError, match="referencia de knowledge nao elegivel"):
        build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
```

Add a signature test using `inspect.signature(build_playbook_catalog)` and assert its parameter names are exactly `source`, `knowledge_index_directory`, `output_directory`. This proves raw knowledge source and provenance mappings are not part of the build API.

- [ ] **Step 4: Add concrete cardinality tests**

Use two approved knowledge IDs in the trusted index.

```python
def test_one_approved_playbook_can_link_multiple_knowledge_ids(monkeypatch, tmp_path: Path) -> None:
    ids = ["KB-SYN-CIGAM-ACCESS-001", "KB-SYN-SIAGRI-ACCESS-001"]
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(ids),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook(knowledge_ids=ids)])
    provenance = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert provenance["active_links"] == 2


def test_two_approved_playbooks_for_same_knowledge_reject_build(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(
        source,
        [valid_playbook("PB-SYN-A"), valid_playbook("PB-SYN-B")],
    )
    with pytest.raises(ValueError, match="mais de um playbook APPROVED"):
        build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
```

Also add one test proving a DRAFT and RETIRED may coexist for the same approved knowledge without creating an active conflict.

- [ ] **Step 5: Implement compilation rules**

Private compiler contract:

```text
_compile_catalog_rows(playbooks: list[dict], eligible_ids: set[str]) -> dict
```

Compilation rules:

1. every referenced ID from every lifecycle must exist in `eligible_ids`;
2. only APPROVED populates full `playbooks` and `active_by_knowledge_id`;
3. DRAFT/RETIRED populate only `playbook_id`, `status`, `version` in `inactive_by_knowledge_id`;
4. second APPROVED owner for one knowledge ID raises before output write;
5. no inactive title, description, steps, instruction, or capability is copied.

Build begins with:

```python
data, _, knowledge_provenance = load_knowledge_index(knowledge_index_directory)
eligible_ids = set(data["knowledge_id"].astype(str).tolist())
playbooks = load_playbooks(source)
```

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook.py -v
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: bind playbooks to approved knowledge ids"
```

---

# Gate 3 - Deterministic Catalog and Provenance

### Task 3: Atomic build and cryptographic binding

**Files:**
- Modify: `src/ai_service_desk/engine/playbook.py`
- Modify: `tests/engine/test_playbook.py`

- [ ] **Step 1: Write RED deterministic build test**

```python
def test_build_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    first = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "first")
    second = build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "second")
    assert first == second
    assert first["catalog_hash"] == second["catalog_hash"]
    first_catalog = json.loads((tmp_path / "first" / "playbook-catalog.json").read_text(encoding="utf-8"))
    second_catalog = json.loads((tmp_path / "second" / "playbook-catalog.json").read_text(encoding="utf-8"))
    assert first_catalog == second_catalog
```

- [ ] **Step 2: Run RED**

Run only this test. Expected failure because Gate 2 does not yet publish the final provenance shape.

- [ ] **Step 3: Add exact provenance binding tests**

Verify these fields are present and no extras exist:

```text
version
domain
playbook_schema_version
catalog_schema_version
catalog_recipe
source_hash
catalog_hash
approved_playbooks
active_links
inactive_links
knowledge_domain
knowledge_schema_version
knowledge_source_hash
knowledge_provenance_hash
```

Add assertions:

```python
assert provenance["domain"] == "APPROVED_PLAYBOOK"
assert provenance["source_hash"] == catalog["source_hash"]
assert provenance["knowledge_domain"] == catalog["knowledge_binding"]["domain"]
assert provenance["knowledge_schema_version"] == catalog["knowledge_binding"]["schema_version"]
assert provenance["knowledge_source_hash"] == catalog["knowledge_binding"]["source_hash"]
assert provenance["knowledge_provenance_hash"] == catalog["knowledge_binding"]["provenance_hash"]
assert provenance["catalog_hash"] == sha256_bytes(canonical_json_bytes(catalog))
```

- [ ] **Step 4: Write sidecar ordering test with complete setup**

```python
def test_provenance_sidecar_is_last_write(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])

    from ai_service_desk.engine import playbook as module

    writes: list[str] = []
    real_atomic = module.atomic_json

    def recording_atomic(path, payload):
        writes.append(Path(path).name)
        return real_atomic(path, payload)

    monkeypatch.setattr(module, "atomic_json", recording_atomic)
    build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert writes == ["playbook-catalog.json", "playbook-provenance.json"]
```

- [ ] **Step 5: Implement exact catalog shape**

Top-level catalog keys:

```text
catalog_schema_version
domain
source_hash
knowledge_binding
eligible_knowledge_ids
playbooks
active_by_knowledge_id
inactive_by_knowledge_id
```

`knowledge_binding` keys:

```text
domain
schema_version
source_hash
provenance_hash
```

Hash rules:

- `source_hash`: SHA-256 over exact playbook JSONL bytes.
- `catalog_hash`: SHA-256 over `canonical_json_bytes(parsed_catalog)`.
- `knowledge_provenance_hash`: SHA-256 over `canonical_json_bytes(validated_knowledge_provenance)`.

Build ordering:

1. validated knowledge load;
2. source validation;
3. reference/cardinality compilation;
4. construct catalog;
5. `atomic_json(catalog_path, catalog)`;
6. re-read and validate catalog structure;
7. calculate catalog hash;
8. construct provenance;
9. `atomic_json(sidecar_path, provenance)`;
10. re-read both and validate pair before success return.

If step 9 fails, a catalog without sidecar may remain. Gate 4 must reject that state explicitly.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook.py -v
ruff check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
ruff format --check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: build deterministic playbook catalog"
```

---

# Gate 4 - Fail-Closed Load and Corruption

### Task 4: Reject every integrity ambiguity before resolution

**Files:**
- Modify: `src/ai_service_desk/engine/playbook.py`
- Modify: `tests/engine/test_playbook.py`

**Produces:** `load_playbook_catalog(directory, knowledge_index_directory)`.

- [ ] **Step 1: Write missing-sidecar RED test**

```python
def test_load_rejects_missing_sidecar(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook.load_knowledge_index",
        lambda path: trusted_index_double(["KB-SYN-PRINT-001"]),
    )
    source = tmp_path / "playbooks.jsonl"
    out = tmp_path / "catalog"
    write_jsonl(source, [valid_playbook()])
    build_playbook_catalog(source, tmp_path / "knowledge", out)
    (out / "playbook-provenance.json").unlink()
    with pytest.raises(ValueError, match="provenance"):
        load_playbook_catalog(out, tmp_path / "knowledge")
```

- [ ] **Step 2: Run RED**

Expected: missing `load_playbook_catalog` or missing fail-closed behavior.

- [ ] **Step 3: Add exact corruption test matrix**

Each row is a separate test. Build a valid catalog first, mutate only the described part, then assert `ValueError` from `load_playbook_catalog`.

| Test | Mutation |
| --- | --- |
| `test_load_rejects_sidecar_from_other_catalog` | replace sidecar with one from catalog built from a different source hash |
| `test_load_rejects_catalog_hash_mismatch` | edit valid catalog JSON after sidecar creation |
| `test_load_rejects_truncated_catalog` | replace catalog bytes with first half |
| `test_load_rejects_partial_catalog_schema` | delete `active_by_knowledge_id` and recalculate no sidecar field |
| `test_load_rejects_wrong_catalog_domain` | set catalog domain to `HISTORICO_NAO_VALIDADO` |
| `test_load_rejects_wrong_sidecar_domain` | set sidecar domain to another string |
| `test_load_rejects_extra_provenance_field` | add one unknown sidecar key |
| `test_load_rejects_wrong_knowledge_source_hash` | change sidecar knowledge source hash |
| `test_load_rejects_wrong_knowledge_provenance_hash` | change sidecar knowledge provenance hash |
| `test_load_rejects_catalog_sidecar_binding_mismatch` | change catalog `knowledge_binding` only |
| `test_load_rejects_active_link_to_missing_playbook` | active map points to nonexistent playbook |
| `test_load_rejects_active_link_outside_eligible_ids` | active map includes non-eligible ID |
| `test_load_rejects_inactive_instruction` | add `instruction` to inactive metadata |
| `test_load_rejects_inactive_capability` | add `capability` to inactive metadata |
| `test_load_rejects_two_approved_owners_even_if_active_map_has_one` | add second approved playbook claiming same knowledge ID while active map still names one |

For mutations where `catalog_hash` would otherwise fail first, update the sidecar `catalog_hash` to the tampered catalog's canonical hash so the test reaches the deeper structural invariant. This proves each invariant independently.

- [ ] **Step 4: Add runtime knowledge trust-chain test**

```python
def test_load_revalidates_current_knowledge_index(monkeypatch, tmp_path: Path) -> None:
    calls: list[Path] = []
    trusted = trusted_index_double(["KB-SYN-PRINT-001"])

    def fake_loader(path):
        calls.append(Path(path))
        return trusted

    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", fake_loader)
    source = tmp_path / "playbooks.jsonl"
    out = tmp_path / "catalog"
    write_jsonl(source, [valid_playbook()])
    build_playbook_catalog(source, tmp_path / "knowledge", out)
    calls.clear()
    load_playbook_catalog(out, tmp_path / "knowledge")
    assert calls == [tmp_path / "knowledge"]
```

Also assert with `inspect.signature(load_playbook_catalog)` that public parameters are exactly `directory` and `knowledge_index_directory`.

- [ ] **Step 5: Implement load validation in this exact order**

1. require `playbook-provenance.json`;
2. parse sidecar and validate closed field set/domain/schema;
3. parse catalog and validate closed top-level field set/domain/schema;
4. compare catalog `source_hash` to sidecar;
5. recompute canonical `catalog_hash` and compare;
6. verify sidecar counters equal catalog counts;
7. validate approved playbook internal schema;
8. reconstruct approved owners from each approved playbook `knowledge_ids` and enforce 0..1;
9. verify reconstructed ownership equals `active_by_knowledge_id`;
10. verify all active IDs are eligible;
11. verify inactive metadata has exactly `playbook_id`, `status`, `version` and status is DRAFT/RETIRED;
12. call `load_knowledge_index(knowledge_index_directory)`;
13. hash the returned validated knowledge provenance;
14. compare current knowledge domain/schema/source/provenance hash with both sidecar and catalog binding;
15. return `(catalog, provenance)` only after every check passes.

No failure returns a business status.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook.py -v
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: fail closed on playbook catalog integrity"
```

---

# Gate 5 - Resolution by knowledge_id

### Task 5: Deterministic business resolution

**Files:**
- Create: `src/ai_service_desk/engine/playbook_resolution.py`
- Create: `tests/engine/test_playbook_resolution.py`

- [ ] **Step 1: Write production-constructor RED test**

```python
def test_engine_loads_through_validated_catalog_loader(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, Path]] = []
    catalog = {
        "eligible_knowledge_ids": ["KB-SYN-VPN-001"],
        "playbooks": {},
        "active_by_knowledge_id": {},
        "inactive_by_knowledge_id": {},
    }

    def fake_loader(directory, knowledge_index_directory):
        calls.append((Path(directory), Path(knowledge_index_directory)))
        return catalog, {"domain": "APPROVED_PLAYBOOK"}

    monkeypatch.setattr(
        "ai_service_desk.engine.playbook_resolution.load_playbook_catalog",
        fake_loader,
    )
    PlaybookEngine(tmp_path / "catalog", tmp_path / "knowledge")
    assert calls == [(tmp_path / "catalog", tmp_path / "knowledge")]
```

- [ ] **Step 2: Run RED**

Expected: module/class missing.

- [ ] **Step 3: Add exact resolution tests with a concrete loaded catalog double**

Use this catalog in tests:

```python
catalog = {
    "eligible_knowledge_ids": [
        "KB-SYN-PRINT-001",
        "KB-SYN-VPN-001",
        "KB-SYN-SOFTWARE-001",
        "KB-SYN-OUTLOOK-001",
    ],
    "playbooks": {
        "PB-SYN-PRINT-001": {
            "playbook_id": "PB-SYN-PRINT-001",
            "title": "Impressao sintetica",
            "description": "Procedimento aprovado ficticio.",
            "knowledge_ids": ["KB-SYN-PRINT-001"],
            "version": 1,
            "steps": [
                {
                    "step_id": "STEP-01",
                    "type": "CHECK",
                    "title": "Verificar fila ficticia",
                    "instruction": "Confirme o estado da fila ficticia.",
                    "capability": "",
                }
            ],
        }
    },
    "active_by_knowledge_id": {"KB-SYN-PRINT-001": "PB-SYN-PRINT-001"},
    "inactive_by_knowledge_id": {
        "KB-SYN-SOFTWARE-001": [
            {"playbook_id": "PB-SYN-SOFTWARE-DRAFT-001", "status": "DRAFT", "version": 1}
        ],
        "KB-SYN-OUTLOOK-001": [
            {"playbook_id": "PB-SYN-OUTLOOK-RETIRED-001", "status": "RETIRED", "version": 1}
        ],
    },
}
```

Tests and exact expected results:

```text
KB-SYN-PRINT-001 -> PLAYBOOK_FOUND / MATCH / PB-SYN-PRINT-001
KB-SYN-VPN-001 -> KNOWLEDGE_ONLY / NO_PLAYBOOK / playbook=None
KB-SYN-SOFTWARE-001 -> PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED / playbook=None
KB-SYN-OUTLOOK-001 -> PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED / playbook=None
```

Add one catalog double with both DRAFT and RETIRED metadata for the same ID and assert DRAFT reason takes deterministic precedence.

- [ ] **Step 4: Add input-domain isolation tests**

Concrete assertions:

```python
knowledge = {
    "knowledge_id": "KB-SYN-VPN-001",
    "title": "must not copy",
    "answer": "must not copy",
    "system": "must not copy",
    "intent": "must not copy",
}
result = engine.resolve(knowledge)
assert set(result) == {"status", "reason", "knowledge_id", "playbook"}
assert "title" not in result
assert "answer" not in result
```

Also assert `ValueError` for non-mapping input, missing ID, blank ID, over-120 ID, and ID not in `eligible_knowledge_ids`.

- [ ] **Step 5: Implement resolver**

`PlaybookEngine.__init__` stores only the validated catalog/provenance returned by `load_playbook_catalog(catalog_directory, knowledge_index_directory)`.

`resolve(knowledge)` validates Mapping and delegates only the `knowledge_id` value.

`resolve_knowledge_id` uses only exact dictionary membership. No normalization, aliases, fuzzy match, score, classifier, LLM, or embedding.

For `PLAYBOOK_FOUND`, project source playbook `version` to runtime `playbook_version` and return only:

```text
playbook_id
title
description
playbook_version
steps
```

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook_resolution.py -v
git add src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
git commit -m "feat: resolve approved playbooks by knowledge id"
```

---

# Gate 6 - Machine Result, Formatter, and Phase 7 Projection

### Task 6: Separate machine and user-facing contracts

**Files:**
- Modify: `src/ai_service_desk/engine/playbook_resolution.py`
- Modify: `tests/engine/test_playbook_resolution.py`

- [ ] **Step 1: Add ACTION_PROPOSAL to the concrete approved test playbook and write RED machine test**

Append this step in the test catalog:

```python
{
    "step_id": "STEP-02",
    "type": "ACTION_PROPOSAL",
    "title": "Considerar limpeza ficticia",
    "instruction": "A limpeza ficticia pode ser considerada como proxima acao.",
    "capability": "DEMO_PRINT_QUEUE_CLEAR",
}
```

Assert:

```python
result = engine.resolve_knowledge_id("KB-SYN-PRINT-001")
action = result["playbook"]["steps"][1]
assert result["playbook"]["playbook_version"] == 1
assert action["type"] == "ACTION_PROPOSAL"
assert action["capability"] == "DEMO_PRINT_QUEUE_CLEAR"
```

- [ ] **Step 2: Run RED for missing descriptor/formatter behavior**

Call `action_proposal_descriptor` and `format_playbook_result` in tests before implementing them. Expected: import/missing-function failure.

- [ ] **Step 3: Write exact Phase 7 descriptor test**

```python
descriptor = action_proposal_descriptor(
    "KB-SYN-PRINT-001",
    result["playbook"],
    action,
)
assert descriptor == {
    "knowledge_id": "KB-SYN-PRINT-001",
    "playbook_id": "PB-SYN-PRINT-001",
    "playbook_version": 1,
    "step_id": "STEP-02",
    "type": "ACTION_PROPOSAL",
    "capability": "DEMO_PRINT_QUEUE_CLEAR",
}
```

Add one test passing the CHECK step and assert `ValueError("step nao e ACTION_PROPOSAL")`.

- [ ] **Step 4: Write exact formatter secrecy tests**

For `PLAYBOOK_FOUND`, assert formatted text contains:

```text
Impressao sintetica
Procedimento aprovado ficticio.
Verificar fila ficticia
Confirme o estado da fila ficticia.
Acao proposta:
A limpeza ficticia pode ser considerada como proxima acao.
```

Assert it does not contain:

```text
DEMO_PRINT_QUEUE_CLEAR
APPROVED_PLAYBOOK
reviewed_by
knowledge_source_hash
```

For `PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED`, assert formatter returns a generic unavailable message that does not contain the literal `PLAYBOOK_RETIRED`.

For `KNOWLEDGE_ONLY`, assert formatter returns an empty string so Phase 6 does not duplicate the Phase 5 answer.

- [ ] **Step 5: Add explicit zero-execution tests**

Runtime static check in the test reads only:

```text
src/ai_service_desk/engine/playbook.py
src/ai_service_desk/engine/playbook_resolution.py
```

and asserts none of these tokens occur:

```text
import subprocess
from subprocess
os.system
Popen(
shell=True
powershell
pwsh
import requests
import httpx
urllib.request
```

Runtime dynamic test monkeypatches `subprocess.run` to raise `AssertionError`, resolves the action playbook, produces its descriptor, and formats it. The test passes only if the sentinel remains uncalled.

- [ ] **Step 6: Implement formatter and descriptor**

Rules:

- descriptor accepts only `ACTION_PROPOSAL`;
- descriptor uses IDs and capability fields directly, never `instruction` parsing;
- formatter shows approved title/description/step title/instruction in source order;
- action step is prefixed with `Acao proposta:`;
- formatter never claims permission or execution;
- formatter never emits capability or provenance.

- [ ] **Step 7: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook_resolution.py -v
ruff check src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
ruff format --check src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
git add src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
git commit -m "feat: expose playbook machine and display contracts"
```

---

# Gate 7 - Synthetic Fixtures and 10-Case Smoke

### Task 7: Official synthetic gate

**Files:**
- Create: `playbooks/phase6_synthetic_playbooks.jsonl`
- Create: `tests/fixtures/phase6_playbook_cases.jsonl`
- Create: `src/ai_service_desk/engine/playbook_smoke.py`
- Create: `tests/engine/test_playbook_smoke.py`

- [ ] **Step 1: Write RED fixture-loader tests before creating fixture files**

`phase6_playbook_cases.jsonl` has exactly these fields:

```text
case_name
mode
knowledge_id
expected_status
expected_reason
expected_playbook_id
mutation
```

All seven fields are always present. `mutation` is empty string when unused.

Allowed modes:

```text
RESOLVE
BUILD_ERROR
LOAD_ERROR
ACTION_CONTRACT
```

Allowed mutation values:

```text
""
APPROVED_CONFLICT
INELIGIBLE_REFERENCE
CATALOG_TAMPER
```

Write tests that reject wrong field set, duplicate case name, invalid mode, invalid mutation, blank case name, non-string knowledge ID, and any fixture count other than exactly 10.

- [ ] **Step 2: Run RED**

Expected: `playbook_smoke` module or fixture loader missing.

- [ ] **Step 3: Create synthetic playbook source with exactly these records**

1. `PB-SYN-ACCESS-SHARED-001`, APPROVED, links `KB-SYN-CIGAM-ACCESS-001` and `KB-SYN-SIAGRI-ACCESS-001`, contains only fictitious INSTRUCTION/CHECK text.
2. `PB-SYN-PRINT-001`, APPROVED, links `KB-SYN-PRINT-001`, contains CHECK plus ACTION_PROPOSAL capability `DEMO_PRINT_QUEUE_CLEAR`.
3. `PB-SYN-SOFTWARE-DRAFT-001`, DRAFT, links `KB-SYN-SOFTWARE-001`.
4. `PB-SYN-OUTLOOK-RETIRED-001`, RETIRED, links `KB-SYN-OUTLOOK-001`.

Leave `KB-SYN-VPN-001` unlinked.

DRAFT/RETIRED source rows may contain synthetic steps because the source is administrative content, but their step text must never appear in compiled operational catalog or report.

- [ ] **Step 4: Create the exact 10 smoke cases**

| # | case_name | mode | knowledge_id | expected status/reason | expected playbook | mutation |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `approved-single-link` | RESOLVE | `KB-SYN-PRINT-001` | `PLAYBOOK_FOUND/MATCH` | `PB-SYN-PRINT-001` | empty |
| 2 | `approved-shared-cigam` | RESOLVE | `KB-SYN-CIGAM-ACCESS-001` | `PLAYBOOK_FOUND/MATCH` | `PB-SYN-ACCESS-SHARED-001` | empty |
| 3 | `approved-shared-siagri` | RESOLVE | `KB-SYN-SIAGRI-ACCESS-001` | `PLAYBOOK_FOUND/MATCH` | `PB-SYN-ACCESS-SHARED-001` | empty |
| 4 | `knowledge-only` | RESOLVE | `KB-SYN-VPN-001` | `KNOWLEDGE_ONLY/NO_PLAYBOOK` | empty | empty |
| 5 | `draft-only` | RESOLVE | `KB-SYN-SOFTWARE-001` | `PLAYBOOK_UNAVAILABLE/PLAYBOOK_NOT_APPROVED` | empty | empty |
| 6 | `retired-only` | RESOLVE | `KB-SYN-OUTLOOK-001` | `PLAYBOOK_UNAVAILABLE/PLAYBOOK_RETIRED` | empty | empty |
| 7 | `approved-conflict` | BUILD_ERROR | `KB-SYN-PRINT-001` | `BUILD_ERROR/ValueError` | empty | `APPROVED_CONFLICT` |
| 8 | `ineligible-reference` | BUILD_ERROR | `KB-SYN-NOT-ELIGIBLE-001` | `BUILD_ERROR/ValueError` | empty | `INELIGIBLE_REFERENCE` |
| 9 | `catalog-integrity` | LOAD_ERROR | `KB-SYN-PRINT-001` | `LOAD_ERROR/ValueError` | empty | `CATALOG_TAMPER` |
| 10 | `action-proposal-contract` | ACTION_CONTRACT | `KB-SYN-PRINT-001` | `PLAYBOOK_FOUND/MATCH` | `PB-SYN-PRINT-001` | empty |

- [ ] **Step 5: Implement smoke signature and safe report**

Exact function:

```text
run_playbook_smoke(knowledge_index: str | Path, playbook_source: str | Path, cases_path: str | Path, work_directory: str | Path, report_path: str | Path) -> dict
```

It does not accept an Ollama URL.

Top-level report keys:

```text
schema_version
phase
domain
timestamp_utc
ok
cases
privacy
```

Privacy values:

```text
raw_text_included = false
approved_content_included = false
capability_included = false
corporate_data_included = false
```

Per-case report keys exactly:

```text
case_name
expected_status
actual_status
expected_reason
actual_reason
expected_playbook_id
actual_playbook_id
passed
```

For build/load error cases, report `actual_reason = type(exc).__name__`, not the full exception message.

Controlled mutations happen only under `work_directory`:

- `APPROVED_CONFLICT`: clone parsed source rows, append second approved playbook linked to print knowledge, write temp source, expect build ValueError.
- `INELIGIBLE_REFERENCE`: clone one approved source row, replace its knowledge IDs with `KB-SYN-NOT-ELIGIBLE-001`, expect build ValueError.
- `CATALOG_TAMPER`: build valid temp catalog, alter title in parsed catalog, rewrite catalog without updating sidecar, expect load ValueError.

ACTION_CONTRACT asserts machine result contains capability, formatter omits capability, and descriptor equals the six-field Phase 7 contract. Report stores none of those text/capability values.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook_smoke.py tests/engine/test_playbook.py tests/engine/test_playbook_resolution.py -v
git add playbooks/phase6_synthetic_playbooks.jsonl tests/fixtures/phase6_playbook_cases.jsonl src/ai_service_desk/engine/playbook_smoke.py tests/engine/test_playbook_smoke.py
git commit -m "test: add synthetic phase 6 playbook smoke"
```

---

# Gate 8 - CLI

### Task 8: Safe Phase 6 commands

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_playbook_cli.py`

- [ ] **Step 1: Write RED parser tests for exact commands**

Expected CLI:

```text
playbook-validate --file PATH
playbook-build --file PATH --knowledge-index PATH --output PATH
playbook-smoke --knowledge-index PATH --playbooks PATH --cases PATH --work-directory PATH --report PATH
```

Tests also assert these parsers have no `url`, `query`, `command`, `script`, `args`, or executor argument.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_playbook_cli.py -v
```

Expected: invalid command choice.

- [ ] **Step 3: Write safe-output tests**

`playbook-validate` expected lines:

```text
Total: 4
APPROVED: 2
DRAFT: 1
RETIRED: 1
Nenhum step ou capability foi exibido. Nenhuma chamada de IA foi feita.
```

`playbook-build` expected lines include:

```text
Playbook catalog: APPROVED_PLAYBOOK
Playbooks APPROVED: 2
Links ativos: 3
```

`playbook-smoke` expected lines include:

```text
PLAYBOOK SMOKE OK
Casos sinteticos: 10
Relatorio agregado local:
```

Every CLI test asserts output does not contain `DEMO_PRINT_QUEUE_CLEAR` and does not contain any fixture instruction sentence.

- [ ] **Step 4: Implement CLI before generic Ollama client creation**

Imports:

```python
from ai_service_desk.engine.playbook import build_playbook_catalog, load_playbooks
from ai_service_desk.engine.playbook_smoke import run_playbook_smoke
```

Place all three command handlers before the current generic `client = OllamaClient(args.url)` line. Phase 6 commands therefore cannot accidentally instantiate an Ollama client.

`playbook-validate` computes lifecycle counts from `load_playbooks`.

`playbook-build` calls `build_playbook_catalog` and prints only domain/counts.

`playbook-smoke` calls `run_playbook_smoke` and returns 0 only when report `ok` is true.

- [ ] **Step 5: Run GREEN and commit**

```bash
pytest tests/test_playbook_cli.py -v
python -m ai_service_desk playbook-validate --file playbooks/phase6_synthetic_playbooks.jsonl
git add src/ai_service_desk/cli.py tests/test_playbook_cli.py
git commit -m "feat: add phase 6 playbook cli"
```

---

# Gate 9 - Workflow and Docs

### Task 9: Manual Dell-compatible smoke workflow

**Files:**
- Create: `.github/workflows/phase6-playbook-smoke.yml`
- Modify: `tests/test_workflows.py`
- Create: `docs/playbooks/phase-6.md`
- Modify: `README.md`

- [ ] **Step 1: Write workflow RED test first**

Add `PHASE6_WORKFLOW` and a test requiring these strings:

```text
workflow_dispatch:
target_ref:
self-hosted
Windows
X64
ai-service-desk
ollama
python -m ai_service_desk knowledge-index
python -m ai_service_desk playbook-validate
python -m ai_service_desk playbook-build
python -m ai_service_desk playbook-smoke
knowledge/phase4_synthetic_faq.jsonl
playbooks/phase6_synthetic_playbooks.jsonl
tests/fixtures/phase6_playbook_cases.jsonl
http://127.0.0.1:11434
```

Forbidden workflow strings:

```text
upload-artifact
Get-Content
--show-history
DEMO_PRINT_QUEUE_CLEAR
```

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_workflows.py::test_phase6_playbook_workflow_is_manual_local_and_non_exporting -v
```

Expected: workflow file missing.

- [ ] **Step 3: Create workflow in this exact order**

1. checkout `target_ref`;
2. verify Python 3.14.x;
3. install `.[dev]`;
4. run `doctor --url http://127.0.0.1:11434` as upstream Phase 4 environment prerequisite;
5. `knowledge-validate` Phase 4 synthetic knowledge;
6. build fresh Phase 4 approved knowledge index in `$env:RUNNER_TEMP` using `knowledge-index`;
7. `playbook-validate` synthetic playbooks;
8. `playbook-build` into `$env:RUNNER_TEMP`;
9. `playbook-smoke` with temp work/report paths.

Runner labels:

```yaml
runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
```

Use `timeout-minutes: 20`, `permissions: contents: read`, no artifact upload, no report printing.

- [ ] **Step 4: Write operational docs**

`docs/playbooks/phase-6.md` must document:

- exact knowledge ID linkage;
- lifecycle and 0..1 active cardinality;
- INSTRUCTION/CHECK/ACTION_PROPOSAL;
- machine-only capability;
- no command/executor fields;
- fail-closed source/catalog/knowledge binding;
- sidecar-last write order;
- business statuses versus integrity exceptions;
- Phase 7 policy boundary and Phase 8 execution boundary;
- synthetic-only repository policy;
- CLI examples;
- Dell homologation commands.

README adds a concise Phase 6 section linking the spec and operational doc. It must not claim execution capability.

- [ ] **Step 5: Run GREEN and commit**

```bash
pytest tests/test_workflows.py -v
ruff check src tests
ruff format --check src tests
git add .github/workflows/phase6-playbook-smoke.yml tests/test_workflows.py docs/playbooks/phase-6.md README.md
git commit -m "docs: add phase 6 playbook operations"
```

---

# Gate 10 - Full Regression, Privacy, CI, Dell, Review

### Task 10: Exact-head completion gate

**Files:** review entire Phase 6 diff. Do not merge in this task.

- [ ] **Step 1: Verify scope against approved spec head**

```bash
git diff --name-only 849d4e6017ba54cf839971556366c4c8ead5f8dc...HEAD
```

Allowed implementation diff after the plan itself:

```text
.github/workflows/phase6-playbook-smoke.yml
README.md
docs/playbooks/phase-6.md
docs/superpowers/plans/2026-09-08-phase-6-playbooks.md
playbooks/phase6_synthetic_playbooks.jsonl
src/ai_service_desk/cli.py
src/ai_service_desk/engine/playbook.py
src/ai_service_desk/engine/playbook_resolution.py
src/ai_service_desk/engine/playbook_smoke.py
tests/engine/test_playbook.py
tests/engine/test_playbook_resolution.py
tests/engine/test_playbook_smoke.py
tests/fixtures/phase6_playbook_cases.jsonl
tests/test_playbook_cli.py
tests/test_workflows.py
```

If any protected file appears, stop and apply the protected-file escalation rule below.

- [ ] **Step 2: Run full regression**

```bash
ruff check .
ruff format --check .
pytest -q
```

Required: zero lint errors, zero formatting drift, all tests pass, including all Phase 1-5 tests.

- [ ] **Step 3: Run explicit zero-execution scans**

```bash
git grep -n -E "subprocess|Popen|os\.system|powershell|pwsh|requests|httpx|urllib\.request|shell=True" -- src/ai_service_desk/engine/playbook.py src/ai_service_desk/engine/playbook_resolution.py src/ai_service_desk/engine/playbook_smoke.py
```

Expected: no matches.

```bash
git grep -n -E '"(command|script|powershell|shell|executable|args|api_url|http_method|credential|token)"\s*:' -- playbooks/phase6_synthetic_playbooks.jsonl
```

Expected: no matches.

- [ ] **Step 4: Run privacy scans**

```bash
git grep -n -E "base_ti_preparada|C:\\\\ai-service-desk-data|juparana|PEDRO" -- playbooks/phase6_synthetic_playbooks.jsonl tests/fixtures/phase6_playbook_cases.jsonl
```

Expected: no matches.

```bash
git ls-files | grep -E "playbook-catalog\.json|playbook-provenance\.json|phase6.*report.*\.json"
```

Expected: no generated runtime catalog, sidecar, or report tracked.

- [ ] **Step 5: Run exact-candidate local functional smoke**

On Dell PowerShell or an equivalent Windows environment:

```powershell
$index = Join-Path $env:TEMP "phase6-knowledge-manual"
$catalog = Join-Path $env:TEMP "phase6-playbook-catalog-manual"
$work = Join-Path $env:TEMP "phase6-playbook-work-manual"
$report = Join-Path $env:TEMP "phase6-playbook-smoke-manual.json"

Remove-Item -Recurse -Force $index,$catalog,$work -ErrorAction SilentlyContinue
Remove-Item -Force $report -ErrorAction SilentlyContinue

python -m ai_service_desk knowledge-index `
  --file knowledge/phase4_synthetic_faq.jsonl `
  --index "$index" `
  --batch-size 10 `
  --url http://127.0.0.1:11434

python -m ai_service_desk playbook-validate `
  --file playbooks/phase6_synthetic_playbooks.jsonl

python -m ai_service_desk playbook-build `
  --file playbooks/phase6_synthetic_playbooks.jsonl `
  --knowledge-index "$index" `
  --output "$catalog"

python -m ai_service_desk playbook-smoke `
  --knowledge-index "$index" `
  --playbooks playbooks/phase6_synthetic_playbooks.jsonl `
  --cases tests/fixtures/phase6_playbook_cases.jsonl `
  --work-directory "$work" `
  --report "$report"

$LASTEXITCODE
```

Expected final output includes:

```text
PLAYBOOK SMOKE OK
Casos sinteticos: 10
0
```

The Phase 4 knowledge index setup uses the existing embedding prerequisite. Phase 6 validate/build/resolve/smoke code must not make LLM or embedding calls.

- [ ] **Step 6: Open or update draft PR with evidence**

Capture:

```bash
git rev-parse HEAD
git merge-base main HEAD
git status --short
```

PR body records:

- exact final head;
- approved spec and plan paths;
- Gate 1-8 RED/GREEN evidence;
- protected-file status;
- zero LLM/embedding/classifier/executor statement for Phase 6;
- privacy/synthetic-only statement;
- hosted CI status;
- Dell status initially pending.

Keep PR draft until same-head Dell homologation passes.

- [ ] **Step 7: Require hosted CI green on exact head**

Verify normal PR CI for that head includes Python 3.14, Ruff lint, Ruff format, complete pytest suite. On failure, invoke systematic debugging and preserve all safety tests.

- [ ] **Step 8: Run Dell homologation on the exact PR head**

First:

```powershell
git rev-parse HEAD
```

It must equal the PR head under review.

Then run Step 5 commands on the Dell environment with the known loopback Ollama prerequisite. Required Phase 6 evidence:

```text
playbook-validate success
playbook-build success
PLAYBOOK SMOKE OK
Casos sinteticos: 10
exit code 0
```

Do not print the aggregate report unless a failure requires safe metadata diagnosis.

- [ ] **Step 9: Final review before Ready for Review**

Verify all ten statements:

1. PR head equals Dell-tested head.
2. Hosted CI is green on that head.
3. Dell smoke is green on that head.
4. Protected files are absent from diff.
5. No unresolved review thread remains.
6. DRAFT/RETIRED operational catalog tests prove no step text/capability leakage.
7. Formatter tests prove capability is hidden.
8. No generated catalog/report artifact is tracked.
9. No corporate data exists in Phase 6 fixtures.
10. Every corruption path raises rather than returning a business status.

Then mark PR Ready for Review. Do not merge.

- [ ] **Step 10: Stop for explicit merge approval**

Report exact head, CI evidence, Dell evidence, and PR state. Merge only after explicit user approval, using expected-head SHA protection, then verify `main` contains the merge.

---

## Protected-File Escalation Rule

If a gate appears to require changing any protected file, stop before editing it and produce:

1. a focused reproducible failing test on the current head;
2. root cause;
3. smallest proposed change;
4. regression and security risk assessment.

No protected-file refactor for convenience is permitted.

---

## Gate Evidence Required in the PR

```text
Gate 1: schema RED -> GREEN
Gate 2: reference/cardinality RED -> GREEN
Gate 3: deterministic catalog/provenance RED -> GREEN
Gate 4: corruption/provenance fail-closed RED -> GREEN
Gate 5: exact knowledge_id resolution RED -> GREEN
Gate 6: machine/formatter/Phase7/zero-execution RED -> GREEN
Gate 7: exact 10-case synthetic smoke RED -> GREEN
Gate 8: CLI RED -> GREEN
Gate 9: workflow/docs test RED -> GREEN
Gate 10: full Ruff + full pytest + privacy + CI + same-head Dell + review
```

---

## Definition of Done

Phase 6 is complete only when all statements are evidenced:

- exact `knowledge_id` lookup only;
- no playbook selection via LLM, embedding, classification, scoring, or semantic retrieval;
- current knowledge trust comes from validated `APPROVED_KNOWLEDGE`, not caller assertion;
- only APPROVED playbooks contribute operational content;
- inactive metadata contains no title, description, step, instruction, or capability;
- 0..1 approved owner per knowledge is enforced at build and load;
- source, catalog, and current knowledge provenance are cryptographically bound;
- missing/copied/tampered/truncated/mismatched artifacts fail closed;
- integrity failure never degrades to `KNOWLEDGE_ONLY` or `PLAYBOOK_UNAVAILABLE`;
- machine result carries symbolic capability for Phase 7;
- user formatter hides capability and never claims policy or execution;
- no executor/action implementation exists;
- official smoke is 10/10 synthetic;
- all Phase 1-5 regression tests remain green;
- hosted CI is green on exact final head;
- Dell homologation is green on exact final head;
- final PR review is clean;
- user explicitly approves merge;
- merge is verified on `main`.
