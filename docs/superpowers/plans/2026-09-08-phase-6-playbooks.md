# Phase 6 Playbooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic, declarative, human-approved playbooks resolved only by exact `knowledge_id`, with fail-closed provenance, no execution, and a stable machine contract for Phase 7.

**Architecture:** Phase 6 adds a separate playbook domain after Phase 5. A source JSONL is structurally validated, compiled against an already validated `APPROVED_KNOWLEDGE` index into a deterministic catalog plus provenance sidecar, loaded fail-closed, and resolved by exact `knowledge_id`. Production trust must come from `load_knowledge_index(...)` or an already validated `KnowledgeEngine`, never from an arbitrary caller-supplied provenance mapping.

**Tech Stack:** Python 3.14, stdlib `json`, `hashlib`, `datetime`, `pathlib`, existing `pytest`, Ruff, existing `ai_service_desk.engine.knowledge.load_knowledge_index`, existing `atomic_json`, GitHub Actions on the Dell self-hosted Windows runner.

**Spec:** `docs/superpowers/specs/2026-09-08-phase-6-playbooks-design.md`

**Approved spec head:** `849d4e6017ba54cf839971556366c4c8ead5f8dc`

**Phase 5 base:** `96fc2fd8b7c867fa7340dc75fddcbc37cbcff5c7`

## Global Constraints

- Association is exclusively by exact `knowledge_id`.
- `knowledge APPROVED -> 0..1 playbook APPROVED`.
- `playbook APPROVED -> 1..N knowledge APPROVED`.
- Two `APPROVED` playbooks for the same `knowledge_id` are a build/load integrity error. There is no priority or tie-break.
- Phase 6 performs zero LLM calls, zero embeddings, zero second classification, and zero executor calls.
- Phase 6 must not execute shell, PowerShell, scripts, processes, HTTP/API actions, commands, filesystem mutations described by steps, registry changes, credentials, or capability implementations.
- Step types are exactly `INSTRUCTION`, `CHECK`, and `ACTION_PROPOSAL`.
- `ACTION_PROPOSAL` requires a symbolic `capability` matching `^[A-Z][A-Z0-9_]{2,119}$`.
- `INSTRUCTION` and `CHECK` require `capability == ""`.
- `DRAFT` and `RETIRED` never contribute title, description, instruction, capability, or step text to the operational catalog.
- `PLAYBOOK_UNAVAILABLE` is only a normal lifecycle result from a valid catalog. Integrity failures raise explicit errors before resolution.
- The playbook provenance sidecar is written only after the complete catalog has been atomically written, re-read, and validated.
- The runtime trust chain must obtain knowledge provenance by loading a fail-closed `APPROVED_KNOWLEDGE` index or by using an already validated `KnowledgeEngine`. Do not add a public constructor that accepts a plain provenance `dict` as trust evidence.
- Tests may monkeypatch or use controlled doubles around the validated loader boundary, but production CLI/runtime paths use the real validated knowledge path.
- The Phase 6 result owns only `status`, `reason`, `knowledge_id`, and `playbook`. It does not duplicate `answer`, `question`, `system`, `intent`, `score`, or `threshold`.
- Machine results include `capability`; user-facing formatting does not expose it automatically.
- No real corporate history, ticket text, IDs, hostnames, credentials, procedures, or private corpus data are committed. All Phase 6 fixtures are synthetic.
- Existing protected files are unchanged unless a reproducible blocking test proves a technical necessity first: `classification.py`, `retrieval.py`, `index.py`, `knowledge.py`, `knowledge_retrieval.py`, `triage.py`.
- Merge occurs only after full regression, hosted CI, Dell homologation on the exact final head, final review, and explicit user approval.
- Do not skip RED -> GREEN evidence for Gates 1 through 8. Run the focused failing test before production code for that gate.

---

## File Structure

### New domain files

- `src/ai_service_desk/engine/playbook.py`
  - strict source schema validation;
  - lifecycle validation;
  - deterministic JSON canonicalization and SHA-256 helpers;
  - compilation of approved content and inactive metadata;
  - referential/cardinality validation against `APPROVED_KNOWLEDGE`;
  - atomic catalog build;
  - fail-closed catalog/provenance load and integrity validation.

- `src/ai_service_desk/engine/playbook_resolution.py`
  - `PlaybookEngine` production constructor anchored to a validated knowledge index;
  - exact `knowledge_id` resolution;
  - machine result projection;
  - Phase 7 `ACTION_PROPOSAL` descriptor projection;
  - user-facing formatter that omits capability and internal lifecycle details.

- `src/ai_service_desk/engine/playbook_smoke.py`
  - strict 10-case synthetic smoke loader;
  - aggregate-only report;
  - no execution surface.

### New synthetic data

- `playbooks/phase6_synthetic_playbooks.jsonl`
- `tests/fixtures/phase6_playbook_cases.jsonl`

### New tests

- `tests/engine/test_playbook.py`
- `tests/engine/test_playbook_resolution.py`
- `tests/engine/test_playbook_smoke.py`
- `tests/test_playbook_cli.py`

### Existing files modified only when their gate arrives

- `src/ai_service_desk/cli.py`
- `tests/test_workflows.py`
- `.github/workflows/phase6-playbook-smoke.yml`
- `docs/playbooks/phase-6.md`
- `README.md`

### Protected files expected to remain byte-for-byte unchanged

- `src/ai_service_desk/engine/classification.py`
- `src/ai_service_desk/engine/retrieval.py`
- `src/ai_service_desk/engine/index.py`
- `src/ai_service_desk/engine/knowledge.py`
- `src/ai_service_desk/engine/knowledge_retrieval.py`
- `src/ai_service_desk/engine/triage.py`

---

## Public and Internal Interfaces Locked by This Plan

The following names are the intended implementation contract. Later gates must use these exact names unless a focused RED test proves a blocker and the plan is amended before continuing.

```python
# src/ai_service_desk/engine/playbook.py
PLAYBOOK_SCHEMA_VERSION = 1
PLAYBOOK_CATALOG_SCHEMA_VERSION = 1
PLAYBOOK_DOMAIN = "APPROVED_PLAYBOOK"
CATALOG_RECIPE = "playbook-catalog-v1"
PLAYBOOK_CATALOG_FILE = "playbook-catalog.json"
PLAYBOOK_PROVENANCE_FILE = "playbook-provenance.json"
ALLOWED_PLAYBOOK_STATUSES = {"DRAFT", "APPROVED", "RETIRED"}
ALLOWED_STEP_TYPES = {"INSTRUCTION", "CHECK", "ACTION_PROPOSAL"}


def load_playbooks(path: str | Path) -> list[dict]: ...
def canonical_json_bytes(payload: object) -> bytes: ...
def sha256_bytes(payload: bytes) -> str: ...
def build_playbook_catalog(
    source: str | Path,
    knowledge_index_directory: str | Path,
    output_directory: str | Path,
) -> dict: ...
def load_playbook_catalog(
    directory: str | Path,
    knowledge_index_directory: str | Path,
) -> tuple[dict, dict]: ...
```

`build_playbook_catalog(...)` and `load_playbook_catalog(...)` must call the existing fail-closed `load_knowledge_index(...)` themselves. They must not accept `knowledge_provenance: dict` from public callers.

```python
# src/ai_service_desk/engine/playbook_resolution.py
class PlaybookEngine:
    def __init__(
        self,
        catalog_directory: str | Path,
        knowledge_index_directory: str | Path,
    ): ...

    def resolve(self, knowledge: Mapping[str, object]) -> dict: ...
    def resolve_knowledge_id(self, knowledge_id: str) -> dict: ...


def action_proposal_descriptor(
    knowledge_id: str,
    playbook: Mapping[str, object],
    step: Mapping[str, object],
) -> dict: ...


def format_playbook_result(result: Mapping[str, object]) -> str: ...
```

The production constructor must call `load_playbook_catalog(catalog_directory, knowledge_index_directory)`. Unit tests may monkeypatch `load_playbook_catalog`, but no alternate public constructor accepts unvalidated provenance.

Machine result shapes:

```python
{
    "status": "KNOWLEDGE_ONLY",
    "reason": "NO_PLAYBOOK",
    "knowledge_id": "KB-SYN-VPN-001",
    "playbook": None,
}
```

```python
{
    "status": "PLAYBOOK_UNAVAILABLE",
    "reason": "PLAYBOOK_NOT_APPROVED",  # or PLAYBOOK_RETIRED
    "knowledge_id": "KB-SYN-SOFTWARE-001",
    "playbook": None,
}
```

```python
{
    "status": "PLAYBOOK_FOUND",
    "reason": "MATCH",
    "knowledge_id": "KB-SYN-PRINT-001",
    "playbook": {
        "playbook_id": "PB-SYN-PRINT-001",
        "title": "...",
        "description": "...",
        "playbook_version": 1,
        "steps": [
            {
                "step_id": "STEP-01",
                "type": "CHECK",
                "title": "...",
                "instruction": "...",
                "capability": "",
            }
        ],
    },
}
```

Phase 7 descriptor shape:

```python
{
    "knowledge_id": "KB-SYN-PRINT-001",
    "playbook_id": "PB-SYN-PRINT-001",
    "playbook_version": 1,
    "step_id": "STEP-02",
    "type": "ACTION_PROPOSAL",
    "capability": "DEMO_PRINT_QUEUE_CLEAR",
}
```

---

### Task 1: Gate 1 - Source Schema and Structural Validation

**Files:**
- Create: `src/ai_service_desk/engine/playbook.py`
- Create: `tests/engine/test_playbook.py`

**Interfaces:**
- Consumes: stdlib only.
- Produces: `load_playbooks`, constants, source validators, `canonical_json_bytes`, `sha256_bytes`.

- [ ] **Step 1: Write RED tests for a valid source and exact field set**

Add focused helpers and tests in `tests/engine/test_playbook.py`:

```python
import json
from pathlib import Path

import pytest

from ai_service_desk.engine.playbook import load_playbooks


def valid_step(step_id="STEP-01", step_type="INSTRUCTION", capability=""):
    return {
        "step_id": step_id,
        "type": step_type,
        "title": "Passo sintetico",
        "instruction": "Execute apenas a verificacao ficticia descrita.",
        "capability": capability,
    }


def valid_playbook(playbook_id="PB-SYN-001", status="APPROVED"):
    return {
        "playbook_id": playbook_id,
        "title": "Playbook sintetico",
        "description": "Procedimento totalmente sintetico para testes.",
        "knowledge_ids": ["KB-SYN-PRINT-001"],
        "steps": [valid_step()],
        "source": "SYNTHETIC_DEMO",
        "status": status,
        "reviewed_by": "synthetic-reviewer" if status == "APPROVED" else "",
        "reviewed_at": "2026-09-08T01:00:00-03:00" if status == "APPROVED" else "",
        "version": 1,
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_load_playbooks_accepts_strict_valid_source(tmp_path: Path) -> None:
    source = tmp_path / "playbooks.jsonl"
    write_jsonl(source, [valid_playbook()])
    assert load_playbooks(source)[0]["playbook_id"] == "PB-SYN-001"


def test_load_playbooks_rejects_missing_and_extra_fields(tmp_path: Path) -> None:
    for mutation in ("missing", "extra"):
        row = valid_playbook()
        if mutation == "missing":
            row.pop("description")
        else:
            row["unexpected"] = True
        source = tmp_path / f"{mutation}.jsonl"
        write_jsonl(source, [row])
        with pytest.raises(ValueError, match="campos de playbook invalidos"):
            load_playbooks(source)
```

- [ ] **Step 2: Run the focused tests and record RED**

Run:

```bash
pytest tests/engine/test_playbook.py::test_load_playbooks_accepts_strict_valid_source tests/engine/test_playbook.py::test_load_playbooks_rejects_missing_and_extra_fields -v
```

Expected RED: import failure or missing `load_playbooks`.

Do not create production code before this RED is observed.

- [ ] **Step 3: Add RED tests for lifecycle, bounds, duplicates, and review metadata**

Cover at minimum:

```python
@pytest.mark.parametrize("status", ["DRAFT", "APPROVED", "RETIRED"])
def test_load_playbooks_accepts_official_statuses(tmp_path: Path, status: str) -> None: ...


def test_load_playbooks_rejects_duplicate_playbook_id(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_empty_source(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_invalid_utf8(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_invalid_json(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_approved_without_review(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_reviewed_at_without_timezone(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_non_positive_or_boolean_version(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_duplicate_knowledge_id_inside_record(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_more_than_20_knowledge_ids(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_more_than_20_steps(tmp_path: Path) -> None: ...
def test_load_playbooks_rejects_duplicate_step_id(tmp_path: Path) -> None: ...
```

Use the exact limits from the spec: playbook ID 120, title 180, description 1000, source/reviewer 120, reviewed_at 80, step ID 120, step title 180, instruction 1500, capability 120, 1..20 knowledge IDs, 1..20 steps.

- [ ] **Step 4: Add RED tests for step type and capability contract**

```python
@pytest.mark.parametrize("step_type", ["INSTRUCTION", "CHECK", "ACTION_PROPOSAL"])
def test_official_step_types_are_accepted(tmp_path: Path, step_type: str) -> None: ...


def test_action_proposal_requires_symbolic_capability(tmp_path: Path) -> None: ...
def test_instruction_rejects_capability(tmp_path: Path) -> None: ...
def test_check_rejects_capability(tmp_path: Path) -> None: ...
@pytest.mark.parametrize("capability", ["pwsh.exe", "http://x", "A", "lower_case", "A B", "ABC-DEF"])
def test_action_proposal_rejects_non_symbolic_capability(tmp_path: Path, capability: str) -> None: ...
```

- [ ] **Step 5: Implement the minimal strict validator**

In `playbook.py`, implement constants and private validators with a closed field set:

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

`load_playbooks(path)` must reject non-file, invalid JSONL, invalid UTF-8, empty source, duplicate `playbook_id`, missing/extra fields, invalid limits, invalid status/review, invalid step schema, invalid capability, and duplicate IDs.

Add deterministic helpers now because later gates depend on one canonical implementation:

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

- [ ] **Step 6: Run Gate 1 GREEN**

Run:

```bash
pytest tests/engine/test_playbook.py -v
```

Expected: all Gate 1 tests PASS.

Then run:

```bash
ruff check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
ruff format --check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
```

Expected: both commands exit 0.

- [ ] **Step 7: Commit Gate 1**

```bash
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: validate declarative playbook schema"
```

---

### Task 2: Gate 2 - Build Against APPROVED_KNOWLEDGE, References, and Cardinality

**Files:**
- Modify: `src/ai_service_desk/engine/playbook.py`
- Modify: `tests/engine/test_playbook.py`

**Interfaces:**
- Consumes: `load_knowledge_index(index_directory)` from protected Phase 4 code, `load_playbooks` from Gate 1.
- Produces: `build_playbook_catalog(source, knowledge_index_directory, output_directory)` with exact referential and 0..1 active cardinality validation.

- [ ] **Step 1: Write RED test proving production build calls the validated knowledge loader**

Monkeypatch only the imported loader boundary inside `playbook.py`:

```python
def test_build_uses_fail_closed_knowledge_index_loader(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_load_knowledge_index(path):
        calls.append(Path(path))
        data = pd.DataFrame([{"knowledge_id": "KB-SYN-PRINT-001"}])
        provenance = {
            "version": 1,
            "domain": "APPROVED_KNOWLEDGE",
            "knowledge_schema_version": 1,
            "source_hash": "b" * 64,
        }
        return data, object(), provenance

    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", fake_load_knowledge_index)
    ...
    build_playbook_catalog(source, tmp_path / "knowledge", tmp_path / "catalog")
    assert calls == [tmp_path / "knowledge"]
```

Do not expose a public `knowledge_provenance` mapping parameter to make this test easier.

- [ ] **Step 2: Run RED for missing build function**

Run:

```bash
pytest tests/engine/test_playbook.py::test_build_uses_fail_closed_knowledge_index_loader -v
```

Expected RED: missing `build_playbook_catalog`.

- [ ] **Step 3: Add RED tests for approved-index references**

```python
def test_build_accepts_reference_present_in_approved_index(...) -> None: ...
def test_build_rejects_reference_not_present_in_approved_index(...) -> None: ...
def test_build_does_not_read_raw_knowledge_source_to_discover_lifecycle(...) -> None: ...
```

For the last test, patch `Path.open` only if needed around a sentinel raw knowledge path, or assert the build signature has no raw knowledge source argument. The operational rule is simple: if an ID is absent from validated index `df["knowledge_id"]`, it is non-eligible regardless of whether it was historically DRAFT, RETIRED, or nonexistent.

- [ ] **Step 4: Add RED cardinality tests**

```python
def test_one_approved_playbook_may_reference_multiple_knowledge_ids(...) -> None: ...
def test_two_approved_playbooks_for_same_knowledge_id_reject_build(...) -> None: ...
def test_inactive_playbooks_do_not_create_active_conflict(...) -> None: ...
```

Expected conflict error must be explicit, for example `ValueError("knowledge_id possui mais de um playbook APPROVED: ...")`.

- [ ] **Step 5: Implement minimal referential/cardinality compilation**

Add an internal compiler that receives already validated rows and eligible IDs:

```python
def _compile_catalog_rows(playbooks: list[dict], eligible_ids: set[str]) -> dict:
    active_by_knowledge_id: dict[str, str] = {}
    approved_playbooks: dict[str, dict] = {}
    inactive_by_knowledge_id: dict[str, list[dict]] = {}
    ...
```

Rules:

1. Every referenced ID, regardless of playbook lifecycle, must be in `eligible_ids`.
2. Only `APPROVED` may populate `approved_playbooks` and `active_by_knowledge_id`.
3. `DRAFT`/`RETIRED` populate only minimal inactive metadata: `playbook_id`, `status`, `version`.
4. A second active link for one ID raises before any output is published.
5. Do not copy inactive `title`, `description`, `steps`, `instruction`, or `capability`.

`build_playbook_catalog(...)` must begin with:

```python
data, _, knowledge_provenance = load_knowledge_index(knowledge_index_directory)
eligible_ids = set(data["knowledge_id"].astype(str).tolist())
playbooks = load_playbooks(source)
```

- [ ] **Step 6: Run Gate 2 GREEN**

Run:

```bash
pytest tests/engine/test_playbook.py -v
```

Expected: all Gate 1 and Gate 2 tests PASS.

- [ ] **Step 7: Commit Gate 2**

```bash
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: bind playbooks to approved knowledge ids"
```

---

### Task 3: Gate 3 - Deterministic Catalog and Provenance Build

**Files:**
- Modify: `src/ai_service_desk/engine/playbook.py`
- Modify: `tests/engine/test_playbook.py`

**Interfaces:**
- Consumes: Gate 1 canonical hashing, Gate 2 compiler, validated Phase 4 knowledge provenance.
- Produces: exact `playbook-catalog.json`, exact `playbook-provenance.json`, sidecar-after-catalog ordering, stable hashes.

- [ ] **Step 1: Write RED deterministic-build test**

```python
def test_build_is_deterministic_for_same_source_and_knowledge_index(...) -> None:
    first = build_playbook_catalog(source, knowledge_index, tmp_path / "a")
    second = build_playbook_catalog(source, knowledge_index, tmp_path / "b")
    assert first == second
    assert (tmp_path / "a" / "playbook-catalog.json").read_text() == (
        tmp_path / "b" / "playbook-catalog.json"
    ).read_text()
```

If atomic JSON formatting contains environmental newlines, compare parsed JSON and `catalog_hash`; the canonical hash must always match.

- [ ] **Step 2: Write RED provenance binding tests**

Verify exact fields and bindings:

```python
def test_provenance_binds_source_catalog_and_knowledge(...) -> None:
    provenance = build_playbook_catalog(...)
    catalog = json.loads((out / "playbook-catalog.json").read_text(encoding="utf-8"))
    assert provenance["domain"] == "APPROVED_PLAYBOOK"
    assert provenance["source_hash"] == catalog["source_hash"]
    assert provenance["knowledge_domain"] == "APPROVED_KNOWLEDGE"
    assert provenance["knowledge_source_hash"] == catalog["knowledge_binding"]["source_hash"]
    assert provenance["knowledge_provenance_hash"] == catalog["knowledge_binding"]["provenance_hash"]
```

Also verify `approved_playbooks`, `active_links`, and `inactive_links` counts.

- [ ] **Step 3: Write RED ordering test proving sidecar is last**

Patch the local write helper or `atomic_json` call in `playbook.py` and record paths:

```python
def test_sidecar_is_written_only_after_complete_catalog(monkeypatch, ...) -> None:
    writes = []
    real_atomic = playbook.atomic_json

    def recording_atomic(path, payload):
        writes.append(Path(path).name)
        return real_atomic(path, payload)

    monkeypatch.setattr(playbook, "atomic_json", recording_atomic)
    build_playbook_catalog(...)
    assert writes[-1] == "playbook-provenance.json"
    assert writes.index("playbook-catalog.json") < writes.index("playbook-provenance.json")
```

The build must re-read and validate catalog structure before writing provenance.

- [ ] **Step 4: Implement exact catalog and provenance shapes**

Catalog top-level keys are closed and must include:

```python
{
    "catalog_schema_version": 1,
    "domain": "APPROVED_PLAYBOOK",
    "source_hash": source_hash,
    "knowledge_binding": {
        "domain": knowledge_provenance["domain"],
        "schema_version": knowledge_provenance["knowledge_schema_version"],
        "source_hash": knowledge_provenance["source_hash"],
        "provenance_hash": sha256_bytes(canonical_json_bytes(knowledge_provenance)),
    },
    "eligible_knowledge_ids": sorted(eligible_ids),
    "playbooks": approved_playbooks,
    "active_by_knowledge_id": active_by_knowledge_id,
    "inactive_by_knowledge_id": inactive_by_knowledge_id,
}
```

Sort emitted dictionary inputs where necessary to ensure stable JSON content.

Provenance keys are exactly:

```python
{
    "version",
    "domain",
    "playbook_schema_version",
    "catalog_schema_version",
    "catalog_recipe",
    "source_hash",
    "catalog_hash",
    "approved_playbooks",
    "active_links",
    "inactive_links",
    "knowledge_domain",
    "knowledge_schema_version",
    "knowledge_source_hash",
    "knowledge_provenance_hash",
}
```

`source_hash` is SHA-256 over exact source bytes. `catalog_hash` is SHA-256 over `canonical_json_bytes(parsed_catalog)`. `knowledge_provenance_hash` is SHA-256 over canonical JSON of the already validated knowledge provenance.

- [ ] **Step 5: Enforce fail-safe partial-build behavior**

If catalog write succeeds but sidecar write fails, leave no apparently valid engine state. It is acceptable for the catalog file to remain without sidecar because Gate 4 load must reject sidecar absence fail-closed.

Do not create a fallback sidecar or status result.

- [ ] **Step 6: Run Gate 3 GREEN**

```bash
pytest tests/engine/test_playbook.py -v
ruff check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
ruff format --check src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
```

Expected: all pass.

- [ ] **Step 7: Commit Gate 3**

```bash
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: build deterministic playbook catalog"
```

---

### Task 4: Gate 4 - Fail-Closed Load and Corruption/Adulteration Tests

**Files:**
- Modify: `src/ai_service_desk/engine/playbook.py`
- Modify: `tests/engine/test_playbook.py`

**Interfaces:**
- Consumes: built catalog/provenance and `load_knowledge_index(...)` trust boundary.
- Produces: `load_playbook_catalog(directory, knowledge_index_directory) -> tuple[catalog, provenance]` that either returns fully validated data or raises.

- [ ] **Step 1: Write RED test for missing provenance sidecar**

```python
def test_load_rejects_missing_playbook_provenance(...) -> None:
    build_playbook_catalog(...)
    (out / "playbook-provenance.json").unlink()
    with pytest.raises(ValueError, match="provenance"):
        load_playbook_catalog(out, knowledge_index)
```

- [ ] **Step 2: Add separate RED corruption tests required by the spec**

Implement explicit tests, not a single broad parameterized smoke, for:

```python
def test_load_rejects_sidecar_copied_from_other_catalog(...) -> None: ...
def test_load_rejects_adulterated_catalog_hash(...) -> None: ...
def test_load_rejects_truncated_catalog(...) -> None: ...
def test_load_rejects_partial_catalog_schema(...) -> None: ...
def test_load_rejects_valid_json_catalog_tampering(...) -> None: ...
def test_load_rejects_wrong_domain(...) -> None: ...
def test_load_rejects_invalid_provenance_schema(...) -> None: ...
def test_load_rejects_wrong_knowledge_source_hash(...) -> None: ...
def test_load_rejects_wrong_knowledge_provenance_hash(...) -> None: ...
def test_load_rejects_catalog_sidecar_knowledge_binding_mismatch(...) -> None: ...
def test_load_rejects_active_link_to_missing_playbook(...) -> None: ...
def test_load_rejects_active_link_outside_eligible_knowledge_ids(...) -> None: ...
def test_load_rejects_inactive_metadata_with_instruction_or_capability(...) -> None: ...
```

- [ ] **Step 3: Add RED runtime trust-chain test**

Prove loader gets current knowledge trust from the real fail-closed boundary:

```python
def test_load_revalidates_current_knowledge_index(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_load_knowledge_index(path):
        calls.append(Path(path))
        ...

    monkeypatch.setattr("ai_service_desk.engine.playbook.load_knowledge_index", fake_load_knowledge_index)
    load_playbook_catalog(catalog_dir, tmp_path / "knowledge-index")
    assert calls == [tmp_path / "knowledge-index"]
```

The public function signature must remain `(directory, knowledge_index_directory)`, not `(directory, provenance_dict)`.

- [ ] **Step 4: Implement closed-schema load validation**

Implement private validators for catalog and provenance. Required ordering:

1. require sidecar file;
2. parse/validate provenance closed schema and domain;
3. parse/validate catalog closed schema and domain;
4. compare catalog `source_hash` to sidecar;
5. recompute canonical `catalog_hash` and compare;
6. verify counts;
7. validate every approved playbook structure inside catalog;
8. validate no inactive operational content;
9. validate active cardinality and link targets;
10. call `load_knowledge_index(knowledge_index_directory)` and obtain current validated provenance;
11. recompute knowledge provenance hash;
12. compare catalog knowledge binding, sidecar knowledge fields, and current validated provenance;
13. return only after every check passes.

Any failure raises `ValueError`. Never return `PLAYBOOK_UNAVAILABLE` or `KNOWLEDGE_ONLY` from this layer.

- [ ] **Step 5: Add an explicit load-time duplicate-active defense**

Although JSON object keys cannot hold duplicate keys after parsing, tampering can create logical conflict by making two approved playbooks claim the same ID while `active_by_knowledge_id` chooses one. Loader must reconstruct approved link ownership from each approved playbook's `knowledge_ids` and verify exactly 0..1 owner per ID plus equality with `active_by_knowledge_id`.

Add test:

```python
def test_load_rejects_catalog_with_two_approved_owners_even_if_active_map_has_one(...) -> None: ...
```

- [ ] **Step 6: Run Gate 4 GREEN**

```bash
pytest tests/engine/test_playbook.py -v
```

Expected: all schema/build/corruption tests pass.

- [ ] **Step 7: Commit Gate 4**

```bash
git add src/ai_service_desk/engine/playbook.py tests/engine/test_playbook.py
git commit -m "feat: fail closed on playbook catalog integrity"
```

---

### Task 5: Gate 5 - Exact Resolution by knowledge_id

**Files:**
- Create: `src/ai_service_desk/engine/playbook_resolution.py`
- Create: `tests/engine/test_playbook_resolution.py`

**Interfaces:**
- Consumes: `load_playbook_catalog(catalog_directory, knowledge_index_directory)` from Gate 4.
- Produces: `PlaybookEngine`, `resolve`, `resolve_knowledge_id` and the three normal business statuses.

- [ ] **Step 1: Write RED production-constructor test**

```python
def test_engine_loads_catalog_through_validated_loader(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_load(directory, knowledge_index_directory):
        calls.append((Path(directory), Path(knowledge_index_directory)))
        return valid_catalog(), valid_provenance()

    monkeypatch.setattr(
        "ai_service_desk.engine.playbook_resolution.load_playbook_catalog",
        fake_load,
    )
    PlaybookEngine(tmp_path / "catalog", tmp_path / "knowledge")
    assert calls == [(tmp_path / "catalog", tmp_path / "knowledge")]
```

No constructor parameter may accept caller-provided provenance.

- [ ] **Step 2: Write RED resolution status tests**

```python
def test_knowledge_without_any_link_returns_knowledge_only(...) -> None: ...
def test_one_approved_link_returns_playbook_found(...) -> None: ...
def test_draft_only_returns_playbook_not_approved_without_playbook_content(...) -> None: ...
def test_retired_only_returns_playbook_retired_without_playbook_content(...) -> None: ...
def test_draft_precedes_retired_when_both_are_inactive(...) -> None: ...
```

- [ ] **Step 3: Write RED input-validation tests**

```python
def test_resolve_extracts_only_knowledge_id_from_mapping(...) -> None: ...
def test_resolve_rejects_non_mapping(...) -> None: ...
def test_resolve_rejects_missing_or_empty_knowledge_id(...) -> None: ...
def test_resolve_rejects_knowledge_id_not_in_eligible_set(...) -> None: ...
```

Include extra fake knowledge fields in the first test and assert the result contains none of them.

- [ ] **Step 4: Implement exact resolver**

Use only dictionaries already validated at load:

```python
class PlaybookEngine:
    def __init__(self, catalog_directory, knowledge_index_directory):
        self.catalog, self.provenance = load_playbook_catalog(
            catalog_directory,
            knowledge_index_directory,
        )

    def resolve(self, knowledge):
        if not isinstance(knowledge, Mapping):
            raise ValueError("knowledge deve ser mapping com knowledge_id.")
        return self.resolve_knowledge_id(knowledge.get("knowledge_id"))
```

`resolve_knowledge_id` must:

1. validate non-empty string and max 120;
2. require membership in `eligible_knowledge_ids` or raise;
3. return `PLAYBOOK_FOUND` if active map has the ID;
4. otherwise inspect only inactive metadata;
5. return `PLAYBOOK_NOT_APPROVED` if any DRAFT exists;
6. else return `PLAYBOOK_RETIRED` if any RETIRED exists;
7. else return `KNOWLEDGE_ONLY / NO_PLAYBOOK`.

No classification, scoring, fuzzy matching, LLM, embedding, or query text is present in this module.

- [ ] **Step 5: Run Gate 5 GREEN**

```bash
pytest tests/engine/test_playbook_resolution.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit Gate 5**

```bash
git add src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
git commit -m "feat: resolve approved playbooks by knowledge id"
```

---

### Task 6: Gate 6 - Machine Result, User Formatter, and Phase 7 Projection

**Files:**
- Modify: `src/ai_service_desk/engine/playbook_resolution.py`
- Modify: `tests/engine/test_playbook_resolution.py`

**Interfaces:**
- Consumes: Gate 5 `PLAYBOOK_FOUND` machine result.
- Produces: stable `playbook_version` runtime field, `action_proposal_descriptor`, `format_playbook_result`.

- [ ] **Step 1: Write RED machine-contract test**

```python
def test_machine_result_contains_phase7_action_metadata(...) -> None:
    result = engine.resolve_knowledge_id("KB-SYN-PRINT-001")
    assert set(result) == {"status", "reason", "knowledge_id", "playbook"}
    assert result["playbook"]["playbook_version"] == 1
    action = next(step for step in result["playbook"]["steps"] if step["type"] == "ACTION_PROPOSAL")
    assert action["capability"] == "DEMO_PRINT_QUEUE_CLEAR"
```

Ensure runtime projects source `version` to `playbook_version` and does not expose source lifecycle/reviewer/source metadata.

- [ ] **Step 2: Write RED Phase 7 descriptor test**

```python
def test_action_proposal_descriptor_is_text_independent(...) -> None:
    descriptor = action_proposal_descriptor("KB-SYN-PRINT-001", playbook, action_step)
    assert descriptor == {
        "knowledge_id": "KB-SYN-PRINT-001",
        "playbook_id": "PB-SYN-PRINT-001",
        "playbook_version": 1,
        "step_id": "STEP-02",
        "type": "ACTION_PROPOSAL",
        "capability": "DEMO_PRINT_QUEUE_CLEAR",
    }
```

Add rejection test for non-`ACTION_PROPOSAL` input so Phase 7 projection cannot accidentally turn an instruction into an executable capability.

- [ ] **Step 3: Write RED user-facing formatter secrecy tests**

```python
def test_formatter_shows_approved_text_but_hides_capability(...) -> None:
    text = format_playbook_result(found_result)
    assert "Verificar a fila" in text
    assert "Confirme se existe" in text
    assert "Acao proposta:" in text
    assert "DEMO_PRINT_QUEUE_CLEAR" not in text


def test_formatter_does_not_expose_internal_lifecycle_reason(...) -> None:
    text = format_playbook_result(unavailable_result)
    assert "PLAYBOOK_RETIRED" not in text
```

Also assert formatter never contains `reviewed_by`, provenance hashes, `APPROVED_PLAYBOOK`, or knowledge `answer` because Phase 6 does not own it.

- [ ] **Step 4: Prove zero executor behavior with a fail-if-called sentinel**

No executor parameter should exist in production code. Still include a test with monkeypatch sentinels for likely forbidden execution surfaces in the Phase 6 module:

```python
def test_action_proposal_is_data_only(monkeypatch, ...) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("executor must not be called")

    monkeypatch.setattr("subprocess.run", forbidden)
    result = engine.resolve_knowledge_id("KB-SYN-PRINT-001")
    text = format_playbook_result(result)
    assert result["status"] == "PLAYBOOK_FOUND"
    assert text
```

In addition, a static test must read `playbook.py` and `playbook_resolution.py` and reject imports/usages of `subprocess`, `powershell`, `requests`, `httpx`, `os.system`, `Popen`, or shell execution helpers.

- [ ] **Step 5: Implement formatter and projection**

Formatter behavior:

```python
if status == "KNOWLEDGE_ONLY":
    return ""
if status == "PLAYBOOK_UNAVAILABLE":
    return "Existe um procedimento relacionado, mas ele nao esta disponivel para orientacao.\n"
if status == "PLAYBOOK_FOUND":
    # title + description + ordered approved steps
```

For `ACTION_PROPOSAL`, prefix user text with `"Acao proposta: "`. Never say an action was authorized or executed.

- [ ] **Step 6: Run Gate 6 GREEN**

```bash
pytest tests/engine/test_playbook_resolution.py -v
ruff check src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
ruff format --check src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
```

Expected: all pass.

- [ ] **Step 7: Commit Gate 6**

```bash
git add src/ai_service_desk/engine/playbook_resolution.py tests/engine/test_playbook_resolution.py
git commit -m "feat: expose playbook machine and display contracts"
```

---

### Task 7: Gate 7 - Synthetic Fixtures and Official 10-Case Smoke

**Files:**
- Create: `playbooks/phase6_synthetic_playbooks.jsonl`
- Create: `tests/fixtures/phase6_playbook_cases.jsonl`
- Create: `src/ai_service_desk/engine/playbook_smoke.py`
- Create: `tests/engine/test_playbook_smoke.py`

**Interfaces:**
- Consumes: Phase 4 synthetic knowledge index, Gate 3 build, Gate 5 resolver, Gate 6 formatter/descriptor.
- Produces: `load_playbook_cases`, `run_playbook_smoke`, aggregate safe report with exactly 10 cases.

- [ ] **Step 1: Create the synthetic playbook fixture design in tests first**

Before creating the fixture file, write tests that expect the exact synthetic IDs used by the smoke:

- `PB-SYN-ACCESS-SHARED-001` APPROVED, links `KB-SYN-CIGAM-ACCESS-001` and `KB-SYN-SIAGRI-ACCESS-001`.
- `PB-SYN-PRINT-001` APPROVED, links `KB-SYN-PRINT-001`, contains CHECK plus ACTION_PROPOSAL with `DEMO_PRINT_QUEUE_CLEAR`.
- `PB-SYN-SOFTWARE-DRAFT-001` DRAFT, links `KB-SYN-SOFTWARE-001`.
- `PB-SYN-OUTLOOK-RETIRED-001` RETIRED, links `KB-SYN-OUTLOOK-001`.
- Leave `KB-SYN-VPN-001` with no playbook link for `KNOWLEDGE_ONLY`.

All text is fictitious and must not describe a real corporate procedure.

- [ ] **Step 2: Write RED fixture-loader tests**

`tests/fixtures/phase6_playbook_cases.jsonl` must contain exactly 10 case objects with a closed schema. Suggested fields:

```python
REQUIRED_CASE_FIELDS = {
    "case_name",
    "mode",
    "knowledge_id",
    "expected_status",
    "expected_reason",
    "expected_playbook_id",
}
OPTIONAL_CASE_FIELDS = {"mutation"}
```

`mode` values are exactly `RESOLVE`, `BUILD_ERROR`, `LOAD_ERROR`, `ACTION_CONTRACT`.

Write tests for exactly 10 cases, unique case names, valid modes, non-empty synthetic IDs, no raw messages, and no capability in the case report schema.

- [ ] **Step 3: Materialize the exact 10 official smoke cases**

The fixture must encode these case names and expectations:

1. `approved-single-link`: `KB-SYN-PRINT-001` -> `PLAYBOOK_FOUND / MATCH / PB-SYN-PRINT-001`.
2. `approved-shared-cigam`: `KB-SYN-CIGAM-ACCESS-001` -> shared APPROVED playbook.
3. `approved-shared-siagri`: `KB-SYN-SIAGRI-ACCESS-001` -> same shared APPROVED playbook, proving 1:N.
4. `knowledge-only`: `KB-SYN-VPN-001` -> `KNOWLEDGE_ONLY / NO_PLAYBOOK`.
5. `draft-only`: `KB-SYN-SOFTWARE-001` -> `PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED`.
6. `retired-only`: `KB-SYN-OUTLOOK-001` -> `PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED`.
7. `approved-conflict`: controlled mutated source with two APPROVED owners -> build error.
8. `ineligible-knowledge-reference`: controlled mutated source points to `KB-SYN-NOT-ELIGIBLE-001` -> build error.
9. `catalog-integrity`: controlled valid-JSON catalog tampering -> load error.
10. `action-proposal-contract`: `KB-SYN-PRINT-001`, machine result contains capability, formatter hides it, executor sentinel remains uncalled.

The spec also requires dedicated unit tests for missing sidecar, copied sidecar, truncated catalog, and knowledge provenance mismatch. Those remain Gate 4 unit tests rather than consuming extra official smoke slots.

- [ ] **Step 4: Write RED `run_playbook_smoke` test**

`run_playbook_smoke` signature:

```python
def run_playbook_smoke(
    knowledge_index: str | Path,
    playbook_source: str | Path,
    cases_path: str | Path,
    work_directory: str | Path,
    report_path: str | Path,
) -> dict: ...
```

It must not take an Ollama URL because Phase 6 itself does not need LLM or embeddings once the approved knowledge index already exists.

Use a temp work directory to build clean and intentionally corrupted catalogs. Never write into repository fixture directories.

- [ ] **Step 5: Implement aggregate-only smoke report**

Top-level report:

```python
{
    "schema_version": 1,
    "phase": 6,
    "domain": "DECLARATIVE_PLAYBOOK",
    "timestamp_utc": "...",
    "ok": False,
    "cases": [],
    "privacy": {
        "raw_text_included": False,
        "approved_content_included": False,
        "capability_included": False,
        "corporate_data_included": False,
    },
}
```

Per-case safe fields only:

```python
{
    "case_name": ...,
    "expected_status": ...,
    "actual_status": ...,
    "expected_reason": ...,
    "actual_reason": ...,
    "expected_playbook_id": ...,
    "actual_playbook_id": ...,
    "passed": ...,
}
```

For build/load errors, use safe symbolic `actual_status` values such as `BUILD_ERROR` or `LOAD_ERROR` and `actual_reason = type(exc).__name__`. Do not print exception messages containing paths or content into the report.

- [ ] **Step 6: Run Gate 7 GREEN**

```bash
pytest tests/engine/test_playbook_smoke.py tests/engine/test_playbook.py tests/engine/test_playbook_resolution.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit Gate 7**

```bash
git add playbooks/phase6_synthetic_playbooks.jsonl tests/fixtures/phase6_playbook_cases.jsonl src/ai_service_desk/engine/playbook_smoke.py tests/engine/test_playbook_smoke.py
git commit -m "test: add synthetic phase 6 playbook smoke"
```

---

### Task 8: Gate 8 - CLI Commands

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_playbook_cli.py`

**Interfaces:**
- Consumes: Gate 1 loader, Gate 3 build, Gate 7 smoke.
- Produces: `playbook-validate`, `playbook-build`, `playbook-smoke` CLI surfaces with safe output.

- [ ] **Step 1: Write RED parser tests**

Expected command signatures:

```text
playbook-validate --file PATH
playbook-build --file PATH --knowledge-index PATH --output PATH
playbook-smoke --knowledge-index PATH --playbooks PATH --cases PATH --work-directory PATH --report PATH
```

No `--url`, `--query`, `--command`, `--script`, `--args`, or executor argument belongs to these commands.

- [ ] **Step 2: Run parser RED**

```bash
pytest tests/test_playbook_cli.py -v
```

Expected RED: invalid command choice.

- [ ] **Step 3: Write RED output/privacy tests**

`playbook-validate` output may show counts only:

```text
Total: N
APPROVED: N
DRAFT: N
RETIRED: N
Nenhum step ou capability foi exibido. Nenhuma chamada de IA foi feita.
```

`playbook-build` output may show:

```text
Playbook catalog: APPROVED_PLAYBOOK
Playbooks APPROVED: N
Links ativos: N
```

`playbook-smoke` output:

```text
PLAYBOOK SMOKE OK
Casos sinteticos: 10
Relatorio agregado local: <path>
```

Tests must assert CLI output does not contain synthetic `instruction` or `DEMO_PRINT_QUEUE_CLEAR`.

- [ ] **Step 4: Implement parser and handlers without Ollama construction**

Place the three Phase 6 branches before the generic `client = OllamaClient(args.url)` section. This is important because `playbook-validate`, `playbook-build`, and `playbook-smoke` must not accidentally construct/use Ollama.

Imports:

```python
from ai_service_desk.engine.playbook import build_playbook_catalog, load_playbooks
from ai_service_desk.engine.playbook_smoke import run_playbook_smoke
```

Do not import an executor.

- [ ] **Step 5: Run Gate 8 GREEN**

```bash
pytest tests/test_playbook_cli.py -v
```

Expected: all pass.

Then run:

```bash
python -m ai_service_desk playbook-validate --file playbooks/phase6_synthetic_playbooks.jsonl
```

Expected: structural validation succeeds and prints no step text or capability.

- [ ] **Step 6: Commit Gate 8**

```bash
git add src/ai_service_desk/cli.py tests/test_playbook_cli.py
git commit -m "feat: add phase 6 playbook cli"
```

---

### Task 9: Gate 9 - Workflow and Operational Documentation

**Files:**
- Create: `.github/workflows/phase6-playbook-smoke.yml`
- Modify: `tests/test_workflows.py`
- Create: `docs/playbooks/phase-6.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: existing Phase 4 knowledge index command and Phase 6 CLI.
- Produces: manual Dell-compatible smoke workflow, operational docs, no artifact upload.

- [ ] **Step 1: Write RED workflow contract test before creating YAML**

Add:

```python
PHASE6_WORKFLOW = ROOT / ".github" / "workflows" / "phase6-playbook-smoke.yml"


def test_phase6_playbook_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE6_WORKFLOW.exists()
    text = PHASE6_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk knowledge-index",
        "python -m ai_service_desk playbook-validate",
        "python -m ai_service_desk playbook-build",
        "python -m ai_service_desk playbook-smoke",
        "knowledge/phase4_synthetic_faq.jsonl",
        "playbooks/phase6_synthetic_playbooks.jsonl",
        "tests/fixtures/phase6_playbook_cases.jsonl",
        "http://127.0.0.1:11434",
    ):
        assert required in text
    for forbidden in ("upload-artifact", "Get-Content", "--show-history", "DEMO_PRINT_QUEUE_CLEAR"):
        assert forbidden not in text
```

- [ ] **Step 2: Run workflow RED**

```bash
pytest tests/test_workflows.py::test_phase6_playbook_workflow_is_manual_local_and_non_exporting -v
```

Expected RED: workflow file missing.

- [ ] **Step 3: Create manual Phase 6 workflow**

Follow the Phase 5 runner pattern:

```yaml
name: Phase 6 playbook smoke

on:
  workflow_dispatch:
    inputs:
      target_ref:
        description: Branch or SHA to validate
        required: true
        type: string

permissions:
  contents: read

jobs:
  phase6-playbook-smoke:
    runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
    timeout-minutes: 20
```

Steps:

1. checkout `target_ref`;
2. verify Python 3.14;
3. install `.[dev]`;
4. run `doctor` only as environment/model prerequisite for the Phase 4 knowledge index build;
5. `knowledge-validate` synthetic Phase 4 source;
6. build a fresh synthetic approved knowledge index in `$env:RUNNER_TEMP` using `knowledge-index`;
7. `playbook-validate` synthetic playbook source;
8. `playbook-build` against the validated temp knowledge index;
9. `playbook-smoke` against the temp knowledge index and temp playbook work directory/report.

Phase 6 commands themselves must have no Ollama URL argument and no execution action.

Do not upload artifacts and do not print report contents.

- [ ] **Step 4: Write operational docs**

`docs/playbooks/phase-6.md` must document:

- playbook is content, not executor;
- exact `knowledge_id` linkage;
- status semantics;
- step types;
- capability machine-only behavior;
- fail-closed provenance and sidecar ordering;
- build/load commands;
- three public business statuses;
- corruption is an exception/error, not `PLAYBOOK_UNAVAILABLE`;
- Phase 7 and Phase 8 boundaries;
- synthetic-only repository policy;
- Dell homologation command sequence.

README adds only a concise Phase 6 section and links to the operational doc/spec.

- [ ] **Step 5: Run Gate 9 GREEN**

```bash
pytest tests/test_workflows.py -v
ruff check src tests
ruff format --check src tests
```

Expected: all pass.

- [ ] **Step 6: Commit Gate 9**

```bash
git add .github/workflows/phase6-playbook-smoke.yml tests/test_workflows.py docs/playbooks/phase-6.md README.md
git commit -m "docs: add phase 6 playbook operations"
```

---

### Task 10: Gate 10 - Full Regression, CI, Privacy, Dell Homologation, and Review Gate

**Files:**
- Review all Phase 6 changed files.
- Modify only documentation or tests if verification reveals a concrete issue.
- Do not merge in this task.

**Interfaces:**
- Consumes: all prior gates.
- Produces: exact final candidate head with local tests, hosted CI, privacy review, Dell homologation, and PR ready for explicit merge approval.

- [ ] **Step 1: Verify changed-file scope against the approved spec head**

Run:

```bash
git diff --name-only 849d4e6017ba54cf839971556366c4c8ead5f8dc...HEAD
```

Expected implementation files only:

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

If a protected file appears, stop. Document the blocker and root cause before any protected-file change proceeds.

- [ ] **Step 2: Run the complete local regression suite**

```bash
ruff check .
ruff format --check .
pytest -q
```

Expected: 0 lint errors, 0 format drift, all tests pass including all Phase 1-5 tests.

Do not claim completion from focused Phase 6 tests alone.

- [ ] **Step 3: Run explicit static no-execution checks**

Search only Phase 6 runtime files:

```bash
git grep -n -E "subprocess|Popen|os\.system|powershell|pwsh|requests|httpx|urllib\.request|shell=True" -- src/ai_service_desk/engine/playbook.py src/ai_service_desk/engine/playbook_resolution.py src/ai_service_desk/engine/playbook_smoke.py
```

Expected: no matches.

Search forbidden schema names in the committed synthetic playbook source:

```bash
git grep -n -E '"(command|script|powershell|shell|executable|args|api_url|http_method|credential|token)"\s*:' -- playbooks/phase6_synthetic_playbooks.jsonl
```

Expected: no matches.

- [ ] **Step 4: Run privacy review**

Verify fixtures contain only expected synthetic prefixes and no report output is committed:

```bash
git grep -n -E "base_ti_preparada|ticket_id|C:\\\\ai-service-desk-data|PEDRO|juparana" -- playbooks tests/fixtures/phase6_playbook_cases.jsonl
```

Expected: no corporate corpus/user/path content. `ticket_id` should not exist in Phase 6 fixtures.

Also confirm no generated catalog/report was accidentally committed:

```bash
git ls-files | grep -E "playbook-catalog\.json|playbook-provenance\.json|phase6.*report.*\.json"
```

Expected: no generated runtime catalog/report files tracked.

- [ ] **Step 5: Build and run the Phase 6 smoke locally on the exact candidate head**

Prerequisite knowledge index may use the existing Ollama embedding model because that is Phase 4 infrastructure. Phase 6 selection/resolution itself makes no LLM/embed call.

PowerShell on Dell or equivalent Windows shell:

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

Expected:

```text
PLAYBOOK SMOKE OK
Casos sinteticos: 10
...
0
```

- [ ] **Step 6: Push branch and open/update a draft PR**

Before opening the PR, capture:

```bash
git rev-parse HEAD
git merge-base main HEAD
git status --short
```

Expected: clean tree, base ancestry includes `96fc2fd8b7c867fa7340dc75fddcbc37cbcff5c7` and approved spec history.

PR body must include:

- exact final head;
- spec and plan paths;
- TDD RED -> GREEN gate evidence;
- protected-file status;
- zero-LLM/embedding/executor architecture statement;
- synthetic-only/privacy statement;
- hosted CI status;
- Dell homologation status, initially pending.

Keep PR draft until exact-head Dell homologation passes.

- [ ] **Step 7: Require hosted CI green on the exact candidate head**

Verify the normal CI job on the PR head includes:

- Python 3.14;
- Ruff lint;
- Ruff format;
- complete pytest suite.

If CI fails, use systematic debugging. Do not weaken tests, provenance checks, fixtures, or protected-file contracts to make CI green.

- [ ] **Step 8: Run Dell homologation on the exact final head**

Required evidence:

```powershell
git rev-parse HEAD
```

must equal the PR head being reviewed.

Then run the Phase 6 workflow-equivalent commands from Step 5 on Dell with:

- Python 3.14.7;
- loopback Ollama;
- existing `qwen3.5:4b` and `qwen3-embedding:0.6b` prerequisites for upstream Phase 4 index build;
- `playbook-validate` green;
- `playbook-build` green;
- `PLAYBOOK SMOKE OK`;
- `Casos sinteticos: 10`;
- exit code `0`.

Do not print the aggregate report contents unless a failure requires safe metadata diagnosis.

- [ ] **Step 9: Final review before ready-for-review state**

Verify:

1. exact head unchanged since Dell run;
2. hosted CI green for same head;
3. Dell green for same head;
4. protected files absent from diff;
5. no unresolved PR review threads;
6. no DRAFT/RETIRED step content in operational catalog tests;
7. no capability in user formatter tests;
8. no generated runtime artifacts committed;
9. no real corporate data in fixtures;
10. corruption tests remain fail-closed errors.

Then mark PR Ready for Review. Do not merge.

- [ ] **Step 10: Stop for explicit user merge approval**

Report the exact head, CI evidence, Dell evidence, and PR state. Wait for explicit user approval before invoking merge.

Only after approval may the merge be executed with an expected-head SHA guard and then verified on `main`.

---

## Gate Evidence Checklist

Before declaring Phase 6 implementation review-ready, the PR evidence must contain all of the following:

- Gate 1 RED and GREEN: strict source schema and lifecycle.
- Gate 2 RED and GREEN: approved-index reference validation and active cardinality.
- Gate 3 RED and GREEN: deterministic catalog/provenance and sidecar ordering.
- Gate 4 RED and GREEN: missing/copied/adulterated/truncated provenance/catalog and knowledge binding failures.
- Gate 5 RED and GREEN: exact resolution and three business statuses.
- Gate 6 RED and GREEN: machine capability, Phase 7 descriptor, formatter hiding capability, zero executor.
- Gate 7 RED and GREEN: exact 10 synthetic smoke cases and safe aggregate report.
- Gate 8 RED and GREEN: CLI commands with no Ollama/executor path for Phase 6 commands.
- Gate 9 RED and GREEN: manual self-hosted workflow and docs.
- Gate 10: full Ruff, full pytest, privacy checks, hosted CI, same-head Dell homologation, final PR review.

## Protected-File Escalation Rule

If any gate appears to require changing one of:

```text
src/ai_service_desk/engine/classification.py
src/ai_service_desk/engine/retrieval.py
src/ai_service_desk/engine/index.py
src/ai_service_desk/engine/knowledge.py
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/engine/triage.py
```

stop implementation and produce all four items before touching it:

1. focused reproducer/test that fails on the current head;
2. technical root cause;
3. smallest proposed protected-file change;
4. regression/security risk assessment.

No protected-file refactor for convenience is allowed.

## Definition of Done

Phase 6 is complete only when:

- lookup is only by exact `knowledge_id`;
- no playbook selection uses LLM, embeddings, classifier, scoring, or retrieval;
- production trust comes from a fail-closed validated knowledge index/engine, not a caller assertion mapping;
- only APPROVED playbooks contribute operational content;
- inactive lifecycle metadata contains no operational step text or capability;
- active cardinality 0..1 is enforced both at build and load;
- source, catalog, and current knowledge provenance are cryptographically bound and revalidated;
- integrity corruption raises and never degrades to a business status;
- machine result contains symbolic capability for Phase 7;
- user formatter hides capability and does not claim policy or execution;
- no executor or action path exists;
- 10/10 synthetic smoke cases pass;
- all Phase 1-5 regressions remain green;
- hosted CI is green on exact final head;
- Dell homologation is green on exact final head;
- final PR review is clean;
- user explicitly approves merge;
- merge is verified on `main`.
