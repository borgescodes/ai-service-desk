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
- Production build/load/runtime obtains current knowledge trust from `load_knowledge_index(...)` or an already validated `KnowledgeEngine`. This plan chooses the public runtime contract that receives `knowledge_index_directory` and calls `load_knowledge_index(...)` internally.
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

- `src/ai_service_desk/engine/playbook.py`: source validation, lifecycle, canonical hashes, reference/cardinality validation, catalog build, provenance, fail-closed load.
- `src/ai_service_desk/engine/playbook_resolution.py`: `PlaybookEngine`, exact resolution, machine result, Phase 7 descriptor, user formatter.
- `src/ai_service_desk/engine/playbook_smoke.py`: strict 10-case smoke and aggregate-only report.
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

`build_playbook_catalog(...)` and `load_playbook_catalog(...)` call the existing fail-closed `load_knowledge_index(...)` internally. Neither accepts a provenance mapping from a public caller.

### `src/ai_service_desk/engine/playbook_resolution.py`

```text
PlaybookEngine(catalog_directory: str | Path, knowledge_index_directory: str | Path)
PlaybookEngine.resolve(knowledge: Mapping[str, object]) -> dict
PlaybookEngine.resolve_knowledge_id(knowledge_id: str) -> dict
action_proposal_descriptor(knowledge_id: str, playbook: Mapping[str, object], step: Mapping[str, object]) -> dict
format_playbook_result(result: Mapping[str, object]) -> str
```

Machine result keys are always exactly `status`, `reason`, `knowledge_id`, `playbook`.

Normal statuses/reasons:

```text
KNOWLEDGE_ONLY / NO_PLAYBOOK
PLAYBOOK_FOUND / MATCH
PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED
PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED
```

Integrity errors are exceptions, never business statuses.

For `ACTION_PROPOSAL`, the Phase 7 projection keys are exactly:

```text
knowledge_id
playbook_id
playbook_version
step_id
type
capability
```

---

## Shared Test Helpers for Gates 1-6

Use these concrete helpers in `tests/engine/test_playbook.py`. Resolution tests may use equivalent local dictionaries rather than importing test code across modules.

```python
import json
from pathlib import Path

import pandas as pd
import pytest

from ai_service_desk.engine.index import RECIPE


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
        "knowledge_ids": (
            knowledge_ids if knowledge_ids is not None else ["KB-SYN-PRINT-001"]
        ),
        "steps": steps if steps is not None else [valid_step()],
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


def trusted_knowledge_provenance(rows: int, source_hash: str = "b" * 64) -> dict:
    return {
        "version": 1,
        "domain": "APPROVED_KNOWLEDGE",
        "knowledge_schema_version": 1,
        "projection_recipe": "knowledge-search-v1",
        "approved_only": True,
        "source_hash": source_hash,
        "matrix_hash": "c" * 64,
        "rows": rows,
        "dimensions": 1024,
        "model": "qwen3-embedding:0.6b",
        "model_digest": "d" * 64,
        "index_recipe": RECIPE,
    }


def trusted_index_double(ids: list[str], source_hash: str = "b" * 64):
    data = pd.DataFrame({"knowledge_id": ids})
    return data, object(), trusted_knowledge_provenance(len(ids), source_hash)
```

The real protected `RECIPE` currently resolves to `texto_busca-plain-v1`; import it rather than duplicating the constant.

---

# Gate 1 - Schema and Structural Validation

### Task 1: Strict source loader

**Files:** create `src/ai_service_desk/engine/playbook.py`, create `tests/engine/test_playbook.py`.

**Produces:** `load_playbooks`, constants, canonical hash helpers.

- [ ] **Step 1: Write the first failing tests**

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

Expected: import or missing-function failure. Do not create production implementation before observing RED.

- [ ] **Step 3: Add the exact schema test matrix**

Each row is one explicit test that mutates `valid_playbook()`, writes JSONL, and asserts `ValueError`.

| Test name | Mutation | Expected failure theme |
| --- | --- | --- |
| `test_rejects_duplicate_playbook_id` | same `playbook_id` twice | duplicate ID |
| `test_rejects_empty_source` | zero nonblank lines | empty base |
| `test_rejects_invalid_utf8` | invalid bytes | UTF-8 |
| `test_rejects_invalid_json` | `{not-json}` | invalid JSON |
| `test_rejects_invalid_status` | `status="ACTIVE"` | lifecycle |
| `test_rejects_approved_without_reviewer` | blank `reviewed_by` | review |
| `test_rejects_approved_without_reviewed_at` | blank `reviewed_at` | review |
| `test_rejects_reviewed_at_without_timezone` | `2026-09-08T01:00:00` | timezone |
| `test_rejects_boolean_version` | `True` | integer |
| `test_rejects_zero_version` | `0` | positive integer |
| `test_rejects_duplicate_knowledge_id_inside_playbook` | same ID twice | duplicate link |
| `test_rejects_empty_knowledge_ids` | `[]` | 1..20 |
| `test_rejects_more_than_20_knowledge_ids` | 21 IDs | 1..20 |
| `test_rejects_empty_steps` | `[]` | 1..20 |
| `test_rejects_more_than_20_steps` | 21 unique steps | 1..20 |
| `test_rejects_duplicate_step_id` | two `STEP-01` | duplicate step |
| `test_rejects_invalid_step_type` | `EXECUTE` | official type |
| `test_action_proposal_requires_capability` | empty capability | symbolic capability |
| `test_instruction_rejects_capability` | `DEMO_X` | empty capability |
| `test_check_rejects_capability` | `DEMO_X` | empty capability |
| `test_rejects_invalid_capability` | `pwsh.exe` | regex |
| `test_rejects_overlong_playbook_id` | 121 chars | limit 120 |
| `test_rejects_overlong_title` | 181 chars | limit 180 |
| `test_rejects_overlong_description` | 1001 chars | limit 1000 |
| `test_rejects_overlong_step_instruction` | 1501 chars | limit 1500 |

Positive tests must cover all three lifecycles and all three step types, with `DEMO_PRINT_QUEUE_CLEAR` for the valid action proposal.

- [ ] **Step 4: Implement the strict validator**

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

Exact limits:

```text
playbook_id 1..120
title 1..180
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

Canonical helpers:

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

- [ ] **Step 5: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook.py -v
ruff check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
ruff format --check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: validate declarative playbook schema"
```

---

# Gate 2 - Build Against APPROVED_KNOWLEDGE, References, and Cardinality

### Task 2: Reference validation and active ownership

**Files:** modify `playbook.py`, modify `test_playbook.py`.

**Produces:** `build_playbook_catalog(...)`.

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

Expected: missing build function.

- [ ] **Step 3: Add reference and public-signature tests**

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

Use `inspect.signature(build_playbook_catalog)` to assert parameters are exactly `source`, `knowledge_index_directory`, `output_directory`. No raw knowledge source or provenance mapping parameter is allowed.

- [ ] **Step 4: Add cardinality tests**

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
    write_jsonl(source, [valid_playbook("PB-SYN-A"), valid_playbook("PB-SYN-B")])
    with pytest.raises(ValueError, match="mais de um playbook APPROVED"):
        build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
```

Add a test with one DRAFT plus one RETIRED for the same approved knowledge and assert build succeeds with `active_links == 0` and two inactive metadata records.

- [ ] **Step 5: Implement compilation**

Private contract:

```text
_compile_catalog_rows(playbooks: list[dict], eligible_ids: set[str]) -> dict
```

Rules:

1. every referenced ID from every lifecycle must exist in `eligible_ids`;
2. APPROVED populates full `playbooks` and `active_by_knowledge_id`;
3. DRAFT/RETIRED populate only `playbook_id`, `status`, `version` in `inactive_by_knowledge_id`;
4. second APPROVED owner for one knowledge ID raises before any output write;
5. inactive content never copies title, description, steps, instruction, capability.

Build starts with:

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

**Files:** modify `playbook.py`, modify `test_playbook.py`.

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
    first_catalog = json.loads(
        (tmp_path / "first" / "playbook-catalog.json").read_text(encoding="utf-8")
    )
    second_catalog = json.loads(
        (tmp_path / "second" / "playbook-catalog.json").read_text(encoding="utf-8")
    )
    assert first_catalog == second_catalog
```

- [ ] **Step 2: Run RED**

Expected: Gate 2 lacks final provenance/hash behavior.

- [ ] **Step 3: Add exact provenance binding tests**

Sidecar keys are exactly:

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

Assertions:

```python
assert provenance["domain"] == "APPROVED_PLAYBOOK"
assert provenance["source_hash"] == catalog["source_hash"]
assert provenance["knowledge_domain"] == catalog["knowledge_binding"]["domain"]
assert provenance["knowledge_schema_version"] == catalog["knowledge_binding"]["schema_version"]
assert provenance["knowledge_source_hash"] == catalog["knowledge_binding"]["source_hash"]
assert provenance["knowledge_provenance_hash"] == catalog["knowledge_binding"]["provenance_hash"]
assert provenance["catalog_hash"] == sha256_bytes(canonical_json_bytes(catalog))
```

- [ ] **Step 4: Write sidecar-last test**

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

- [ ] **Step 5: Implement catalog/provenance**

Catalog keys exactly:

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

`knowledge_binding` keys exactly `domain`, `schema_version`, `source_hash`, `provenance_hash`.

Hash rules:

- source hash is SHA-256 over exact JSONL bytes;
- catalog hash is SHA-256 over canonical parsed catalog JSON;
- knowledge provenance hash is SHA-256 over canonical validated knowledge provenance JSON.

Build order:

1. validated knowledge load;
2. source validation;
3. reference/cardinality compilation;
4. construct catalog;
5. atomic catalog write;
6. re-read and structurally validate catalog;
7. calculate catalog hash;
8. construct sidecar;
9. atomic sidecar write;
10. re-read and validate pair before returning provenance.

A catalog left without sidecar after write failure is intentionally unusable and must fail Gate 4 load.

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

### Task 4: Reject integrity ambiguity before resolution

**Files:** modify `playbook.py`, modify `test_playbook.py`.

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

Expected: missing load function or missing fail-closed behavior.

- [ ] **Step 3: Add exact corruption matrix**

Each row is a separate test that starts from a valid build and asserts `ValueError` on load.

| Test | Mutation |
| --- | --- |
| `test_load_rejects_sidecar_from_other_catalog` | replace sidecar with one built from another playbook source |
| `test_load_rejects_catalog_hash_mismatch` | edit catalog after sidecar creation |
| `test_load_rejects_truncated_catalog` | replace catalog with first half of bytes |
| `test_load_rejects_partial_catalog_schema` | remove `active_by_knowledge_id` |
| `test_load_rejects_wrong_catalog_domain` | set catalog domain to `HISTORICO_NAO_VALIDADO` |
| `test_load_rejects_wrong_sidecar_domain` | set sidecar domain to another string |
| `test_load_rejects_extra_provenance_field` | add unknown sidecar key |
| `test_load_rejects_wrong_knowledge_source_hash` | alter sidecar knowledge source hash |
| `test_load_rejects_wrong_knowledge_provenance_hash` | alter sidecar provenance hash |
| `test_load_rejects_catalog_sidecar_binding_mismatch` | alter catalog binding only |
| `test_load_rejects_active_link_to_missing_playbook` | map active ID to nonexistent playbook |
| `test_load_rejects_active_link_outside_eligible_ids` | add active non-eligible ID |
| `test_load_rejects_inactive_instruction` | add `instruction` to inactive metadata |
| `test_load_rejects_inactive_capability` | add `capability` to inactive metadata |
| `test_load_rejects_two_approved_owners_even_if_active_map_has_one` | add second approved playbook claiming the same knowledge ID |

For deeper invariant tests, recalculate sidecar `catalog_hash` after the intentional catalog mutation so hash mismatch does not mask the structural failure being tested.

- [ ] **Step 4: Add runtime trust-chain test**

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

Use `inspect.signature(load_playbook_catalog)` to assert the only public parameters are `directory` and `knowledge_index_directory`.

- [ ] **Step 5: Implement load validation in exact order**

1. require sidecar;
2. validate sidecar closed schema/domain;
3. validate catalog closed schema/domain;
4. compare source hash;
5. recompute/compare catalog hash;
6. verify counters;
7. validate approved playbook structures;
8. reconstruct approved ownership and enforce 0..1;
9. verify reconstructed owners equal active map;
10. verify active IDs are eligible;
11. verify inactive records have exactly `playbook_id`, `status`, `version` and only DRAFT/RETIRED;
12. call `load_knowledge_index(knowledge_index_directory)`;
13. hash returned validated knowledge provenance;
14. compare current knowledge domain/schema/source/provenance hash with catalog binding and sidecar;
15. return only after every check passes.

No failure returns `KNOWLEDGE_ONLY` or `PLAYBOOK_UNAVAILABLE`.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook.py -v
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: fail closed on playbook catalog integrity"
```

---

# Gate 5 - Resolution by knowledge_id

### Task 5: Deterministic business resolution

**Files:** create `playbook_resolution.py`, create `test_playbook_resolution.py`.

- [ ] **Step 1: Write constructor RED test**

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

- [ ] **Step 3: Add exact resolution matrix**

Use a loaded catalog with eligible IDs for print, VPN, software, Outlook; one approved print playbook; DRAFT metadata for software; RETIRED metadata for Outlook.

Expected:

```text
KB-SYN-PRINT-001 -> PLAYBOOK_FOUND / MATCH / PB-SYN-PRINT-001
KB-SYN-VPN-001 -> KNOWLEDGE_ONLY / NO_PLAYBOOK / null
KB-SYN-SOFTWARE-001 -> PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED / null
KB-SYN-OUTLOOK-001 -> PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED / null
```

Add one case with both DRAFT and RETIRED metadata and assert DRAFT reason wins deterministically.

- [ ] **Step 4: Add domain-isolation tests**

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

Assert `ValueError` for non-mapping input, missing ID, blank ID, over-120 ID, and ID outside `eligible_knowledge_ids`.

- [ ] **Step 5: Implement exact resolution**

`PlaybookEngine.__init__` calls `load_playbook_catalog(catalog_directory, knowledge_index_directory)`.

`resolve(knowledge)` extracts only `knowledge_id` and delegates to `resolve_knowledge_id`.

`resolve_knowledge_id` uses only exact dictionary membership. No normalization, aliases, fuzzy matching, score, classifier, LLM, or embedding.

`PLAYBOOK_FOUND` runtime playbook keys are exactly:

```text
playbook_id
title
description
playbook_version
steps
```

Source `version` becomes runtime `playbook_version`.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook_resolution.py -v
git add src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
git commit -m "feat: resolve approved playbooks by knowledge id"
```

---

# Gate 6 - Machine Result, Formatter, and Phase 7 Projection

### Task 6: Separate machine and user-facing contracts

**Files:** modify `playbook_resolution.py`, modify its tests.

- [ ] **Step 1: Add concrete ACTION_PROPOSAL and write RED machine test**

Approved test playbook gets:

```python
{
    "step_id": "STEP-02",
    "type": "ACTION_PROPOSAL",
    "title": "Considerar limpeza ficticia",
    "instruction": "A limpeza ficticia pode ser considerada como proxima acao.",
    "capability": "DEMO_PRINT_QUEUE_CLEAR",
}
```

Assert machine result keeps `playbook_version=1` and `capability="DEMO_PRINT_QUEUE_CLEAR"`.

- [ ] **Step 2: Run RED for descriptor/formatter**

Tests import and call `action_proposal_descriptor` and `format_playbook_result` before implementation. Expected: missing functions.

- [ ] **Step 3: Add exact Phase 7 descriptor assertion**

```python
assert action_proposal_descriptor(
    "KB-SYN-PRINT-001",
    result["playbook"],
    action,
) == {
    "knowledge_id": "KB-SYN-PRINT-001",
    "playbook_id": "PB-SYN-PRINT-001",
    "playbook_version": 1,
    "step_id": "STEP-02",
    "type": "ACTION_PROPOSAL",
    "capability": "DEMO_PRINT_QUEUE_CLEAR",
}
```

CHECK passed to descriptor must raise `ValueError("step nao e ACTION_PROPOSAL")`.

- [ ] **Step 4: Add formatter secrecy tests**

For found playbook, formatted text contains title, description, ordered step titles/instructions and `Acao proposta:`. It must not contain `DEMO_PRINT_QUEUE_CLEAR`, `APPROVED_PLAYBOOK`, reviewer fields, or hashes.

For unavailable playbook, formatter returns generic unavailable text and does not reveal `PLAYBOOK_RETIRED` or `PLAYBOOK_NOT_APPROVED` literally.

For `KNOWLEDGE_ONLY`, formatter returns empty string.

- [ ] **Step 5: Add zero-execution proof**

Static test reads `playbook.py` and `playbook_resolution.py` and rejects these tokens:

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

Dynamic test monkeypatches `subprocess.run` to raise, then resolves, projects, and formats an ACTION_PROPOSAL. No sentinel call may occur.

- [ ] **Step 6: Implement descriptor and formatter**

Descriptor reads structured IDs/capability directly and never parses `instruction`.

Formatter shows only approved presentation text, preserves step order, prefixes action text with `Acao proposta:`, never claims permission/execution, and never emits capability/provenance.

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

**Files:** create synthetic playbook source, smoke case fixture, smoke module, smoke tests.

- [ ] **Step 1: Write RED fixture-loader tests before fixture creation**

Case fields are exactly:

```text
case_name
mode
knowledge_id
expected_status
expected_reason
expected_playbook_id
mutation
```

Allowed modes: `RESOLVE`, `BUILD_ERROR`, `LOAD_ERROR`, `ACTION_CONTRACT`.

Allowed mutation values: empty string, `APPROVED_CONFLICT`, `INELIGIBLE_REFERENCE`, `CATALOG_TAMPER`.

Reject wrong field set, duplicate names, invalid mode, invalid mutation, blank name, non-string knowledge ID, and any count other than exactly 10.

- [ ] **Step 2: Run RED**

Expected: smoke module/loader missing.

- [ ] **Step 3: Create exactly four synthetic playbook records**

1. `PB-SYN-ACCESS-SHARED-001`, APPROVED, links CIGAM and SIAGRI synthetic access knowledge.
2. `PB-SYN-PRINT-001`, APPROVED, links print synthetic knowledge, contains CHECK plus `ACTION_PROPOSAL / DEMO_PRINT_QUEUE_CLEAR`.
3. `PB-SYN-SOFTWARE-DRAFT-001`, DRAFT, links software synthetic knowledge.
4. `PB-SYN-OUTLOOK-RETIRED-001`, RETIRED, links Outlook synthetic knowledge.

Leave VPN synthetic knowledge unlinked.

All wording is fictitious. Inactive source records may contain synthetic administrative steps, but compiled operational catalog and reports must never contain those steps.

- [ ] **Step 4: Create exact 10 smoke cases**

| # | case | mode | knowledge | expected | playbook | mutation |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | approved-single-link | RESOLVE | KB-SYN-PRINT-001 | PLAYBOOK_FOUND/MATCH | PB-SYN-PRINT-001 | empty |
| 2 | approved-shared-cigam | RESOLVE | KB-SYN-CIGAM-ACCESS-001 | PLAYBOOK_FOUND/MATCH | PB-SYN-ACCESS-SHARED-001 | empty |
| 3 | approved-shared-siagri | RESOLVE | KB-SYN-SIAGRI-ACCESS-001 | PLAYBOOK_FOUND/MATCH | PB-SYN-ACCESS-SHARED-001 | empty |
| 4 | knowledge-only | RESOLVE | KB-SYN-VPN-001 | KNOWLEDGE_ONLY/NO_PLAYBOOK | empty | empty |
| 5 | draft-only | RESOLVE | KB-SYN-SOFTWARE-001 | PLAYBOOK_UNAVAILABLE/PLAYBOOK_NOT_APPROVED | empty | empty |
| 6 | retired-only | RESOLVE | KB-SYN-OUTLOOK-001 | PLAYBOOK_UNAVAILABLE/PLAYBOOK_RETIRED | empty | empty |
| 7 | approved-conflict | BUILD_ERROR | KB-SYN-PRINT-001 | BUILD_ERROR/ValueError | empty | APPROVED_CONFLICT |
| 8 | ineligible-reference | BUILD_ERROR | KB-SYN-NOT-ELIGIBLE-001 | BUILD_ERROR/ValueError | empty | INELIGIBLE_REFERENCE |
| 9 | catalog-integrity | LOAD_ERROR | KB-SYN-PRINT-001 | LOAD_ERROR/ValueError | empty | CATALOG_TAMPER |
| 10 | action-proposal-contract | ACTION_CONTRACT | KB-SYN-PRINT-001 | PLAYBOOK_FOUND/MATCH | PB-SYN-PRINT-001 | empty |

- [ ] **Step 5: Implement smoke contract**

```text
run_playbook_smoke(knowledge_index: str | Path, playbook_source: str | Path, cases_path: str | Path, work_directory: str | Path, report_path: str | Path) -> dict
```

No Ollama URL parameter.

Report top-level keys: `schema_version`, `phase`, `domain`, `timestamp_utc`, `ok`, `cases`, `privacy`.

Privacy values are all false for `raw_text_included`, `approved_content_included`, `capability_included`, `corporate_data_included`.

Per-case keys exactly: `case_name`, `expected_status`, `actual_status`, `expected_reason`, `actual_reason`, `expected_playbook_id`, `actual_playbook_id`, `passed`.

For build/load errors, store only `type(exc).__name__`, never full exception message.

Controlled mutations happen only in `work_directory`:

- conflict appends a second approved print playbook;
- ineligible replaces knowledge ID with `KB-SYN-NOT-ELIGIBLE-001`;
- catalog tamper changes valid catalog content without updating sidecar.

ACTION_CONTRACT verifies machine capability present, formatter capability absent, six-field descriptor exact, and no execution call.

- [ ] **Step 6: Run GREEN and commit**

```bash
pytest tests/engine/test_playbook_smoke.py tests/engine/test_playbook.py tests/engine/test_playbook_resolution.py -v
git add playbooks/phase6_synthetic_playbooks.jsonl tests/fixtures/phase6_playbook_cases.jsonl src/ai_service_desk/engine/playbook_smoke.py tests/engine/test_playbook_smoke.py
git commit -m "test: add synthetic phase 6 playbook smoke"
```

---

# Gate 8 - CLI

### Task 8: Safe Phase 6 commands

**Files:** modify `src/ai_service_desk/cli.py`, create `tests/test_playbook_cli.py`.

- [ ] **Step 1: Write RED parser tests**

Exact commands:

```text
playbook-validate --file PATH
playbook-build --file PATH --knowledge-index PATH --output PATH
playbook-smoke --knowledge-index PATH --playbooks PATH --cases PATH --work-directory PATH --report PATH
```

Assert no Phase 6 parser argument named `url`, `query`, `command`, `script`, `args`, or executor.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_playbook_cli.py -v
```

Expected: invalid command choice.

- [ ] **Step 3: Add safe-output tests**

Expected validate counts for the official four-row fixture:

```text
Total: 4
APPROVED: 2
DRAFT: 1
RETIRED: 1
Nenhum step ou capability foi exibido. Nenhuma chamada de IA foi feita.
```

Expected build summary includes `APPROVED_PLAYBOOK`, two approved playbooks, three active links.

Expected smoke summary includes `PLAYBOOK SMOKE OK`, `Casos sinteticos: 10`, local report path.

All outputs must exclude `DEMO_PRINT_QUEUE_CLEAR` and fixture instruction text.

- [ ] **Step 4: Implement CLI before generic Ollama creation**

Imports:

```python
from ai_service_desk.engine.playbook import build_playbook_catalog, load_playbooks
from ai_service_desk.engine.playbook_smoke import run_playbook_smoke
```

Place all three handlers before current `client = OllamaClient(args.url)`. Phase 6 commands therefore do not instantiate Ollama.

- [ ] **Step 5: Run GREEN and commit**

```bash
pytest tests/test_playbook_cli.py -v
python -m ai_service_desk playbook-validate --file playbooks/phase6_synthetic_playbooks.jsonl
git add src/ai_service_desk/cli.py tests/test_playbook_cli.py
git commit -m "feat: add phase 6 playbook cli"
```

---

# Gate 9 - Workflow and Docs

### Task 9: Manual Dell-compatible validation

**Files:** create Phase 6 workflow, modify workflow tests, create operational doc, modify README.

- [ ] **Step 1: Write workflow RED test**

Require strings:

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

Forbid `upload-artifact`, `Get-Content`, `--show-history`, `DEMO_PRINT_QUEUE_CLEAR`.

- [ ] **Step 2: Run RED**

```bash
pytest tests/test_workflows.py::test_phase6_playbook_workflow_is_manual_local_and_non_exporting -v
```

Expected: workflow missing.

- [ ] **Step 3: Create workflow in exact order**

1. checkout target ref;
2. verify Python 3.14.x;
3. install `.[dev]`;
4. doctor loopback as upstream Phase 4 prerequisite;
5. validate Phase 4 synthetic knowledge;
6. build fresh approved knowledge index in `RUNNER_TEMP`;
7. playbook validate;
8. playbook build in `RUNNER_TEMP`;
9. playbook smoke with temp work/report paths.

Use `runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]`, timeout 20, contents read only, no artifact upload/report printing.

- [ ] **Step 4: Write docs**

Operational doc covers linkage, lifecycle, cardinality, step types, capability machine-only behavior, forbidden execution fields, fail-closed binding, sidecar order, business statuses versus integrity exceptions, Phase 7/8 boundary, synthetic policy, CLI, Dell commands.

README links spec and operational doc and does not claim execution capability.

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

**Do not merge in this task.**

- [ ] **Step 1: Verify scope**

```bash
git diff --name-only 849d4e6017ba54cf839971556366c4c8ead5f8dc...HEAD
```

Allowed files after the approved spec are only the plan plus Phase 6 files listed in this document. Any protected file triggers escalation.

- [ ] **Step 2: Full regression**

```bash
ruff check .
ruff format --check .
pytest -q
```

Require zero lint errors, zero format drift, all tests passing including all Phase 1-5 tests.

- [ ] **Step 3: Zero-execution scans**

```bash
git grep -n -E "subprocess|Popen|os\.system|powershell|pwsh|requests|httpx|urllib\.request|shell=True" -- src/ai_service_desk/engine/playbook.py src/ai_service_desk/engine/playbook_resolution.py src/ai_service_desk/engine/playbook_smoke.py
```

Expected no matches.

```bash
git grep -n -E '"(command|script|powershell|shell|executable|args|api_url|http_method|credential|token)"\s*:' -- playbooks/phase6_synthetic_playbooks.jsonl
```

Expected no matches.

- [ ] **Step 4: Privacy scans**

```bash
git grep -n -E "base_ti_preparada|C:\\\\ai-service-desk-data|juparana|PEDRO" -- playbooks/phase6_synthetic_playbooks.jsonl tests/fixtures/phase6_playbook_cases.jsonl
```

Expected no matches.

```bash
git ls-files | grep -E "playbook-catalog\.json|playbook-provenance\.json|phase6.*report.*\.json"
```

Expected no generated catalog, provenance, or report tracked.

- [ ] **Step 5: Exact-candidate functional smoke on Windows**

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

Expected final evidence:

```text
PLAYBOOK SMOKE OK
Casos sinteticos: 10
0
```

The upstream Phase 4 index setup uses its existing embedding prerequisite. Phase 6 validate/build/load/resolve/smoke code itself makes no LLM or embedding call.

- [ ] **Step 6: Draft PR evidence**

Capture exact head, merge-base, clean status. PR body records spec/plan, TDD gates, protected status, zero-LLM/embedding/classifier/executor claim scoped to Phase 6, privacy, CI, Dell pending. Keep draft until same-head Dell passes.

- [ ] **Step 7: Hosted CI**

Require exact-head Python 3.14, Ruff lint, Ruff format, complete pytest suite. On failure use systematic debugging and never weaken fail-closed tests.

- [ ] **Step 8: Dell homologation on exact PR head**

First `git rev-parse HEAD` must equal PR head. Then run Step 5 commands. Require validate/build success, `PLAYBOOK SMOKE OK`, 10 cases, exit 0. Do not print report unless safe diagnosis is needed.

- [ ] **Step 9: Final review**

Verify exact-head equality, hosted CI green, Dell green, protected files absent, no unresolved threads, inactive content isolation, capability hidden in formatter, no generated artifacts, no corporate fixture data, all corruption paths raise.

Mark Ready for Review only after these checks. Do not merge.

- [ ] **Step 10: Explicit merge gate**

Report evidence and wait for user approval. Merge only with expected-head SHA protection and verify `main` afterward.

---

## Protected-File Escalation Rule

Before touching a protected file, produce all four:

1. focused reproducible failing test;
2. root cause;
3. smallest proposed protected-file change;
4. regression/security risk assessment.

No protected refactor for convenience.

---

## Gate Evidence Required in PR

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

Phase 6 is complete only when:

- lookup is exact `knowledge_id` only;
- no playbook selection uses LLM, embeddings, classifier, score, or semantic retrieval;
- current knowledge trust comes from validated `APPROVED_KNOWLEDGE`, not caller assertion;
- only APPROVED contributes operational content;
- inactive metadata has no title, description, step, instruction, capability;
- 0..1 approved owner is enforced at build and load;
- source, catalog, and current knowledge provenance are cryptographically bound;
- missing/copied/tampered/truncated/mismatched artifacts fail closed;
- integrity failure never degrades to `KNOWLEDGE_ONLY` or `PLAYBOOK_UNAVAILABLE`;
- machine result carries symbolic capability for Phase 7;
- formatter hides capability and never claims policy/execution;
- no executor/action implementation exists;
- official smoke is 10/10 synthetic;
- all Phase 1-5 regressions remain green;
- hosted CI is green on exact final head;
- Dell homologation is green on exact final head;
- final PR review is clean;
- user explicitly approves merge;
- merge is verified on `main`.
