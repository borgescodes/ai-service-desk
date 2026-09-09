# Phase 7 Policy Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Phase 7 deterministic CDM access policy layer that prepares a provenance-preserving access context, normalizes requested CDM role safely, evaluates fail-closed policy, assesses contextual confidence independently, and stops before persistence, approval, execution or any external call.

**Architecture:** Phase 7 adds three focused domain modules: `access_request.py`, `policy.py`, and `confidence.py`. `prepare_access_request(...)` is CDM-specific in this phase and consumes trusted `SessionIdentity`, resolved `TriageState`, and the real Phase 6 `ACTION_PROPOSAL` descriptor. `PolicyEngine.evaluate(...)` and `assess_confidence(...)` independently validate `AccessRequestContext`, so Phase 8 can reuse both contracts when revalidating a context reconstructed from persisted data.

**Tech Stack:** Python 3.14, stdlib `dataclasses`, `typing`, `collections.abc`, `re`, existing `normalize_text`, existing `CAPABILITY_RE`, existing `TriageState`, existing `action_proposal_descriptor`, `pytest`, Ruff, GitHub Actions, Dell self-hosted Windows runner.

**Spec:** `docs/superpowers/specs/2026-09-08-phase-7-policy-engine-design.md`

**Regression baseline:** `7e7142f757f66585f240e16781accd044f31eb6f`.

**Execution start:** the final `phase-7-policy-engine` head containing this plan revision after explicit user approval. Execution starts from that approved plan head, not from the regression baseline.

**Phase 6 quantitative baseline:** `319` collected tests.

## Execution Start vs Regression Baseline

These two references have different purposes and must never be conflated:

```text
execution start = final plan head explicitly approved by the user
regression baseline = 7e7142f757f66585f240e16781accd044f31eb6f
```

At implementation handoff, before Gate 1, record the current approved branch head and prove the fixed regression baseline is its ancestor:

```bash
REGRESSION_BASELINE=7e7142f757f66585f240e16781accd044f31eb6f
EXECUTION_START_HEAD="$(git rev-parse HEAD)"
test -z "$(git status --porcelain)"
git merge-base --is-ancestor "$REGRESSION_BASELINE" "$EXECUTION_START_HEAD"
printf 'execution_start=%s\nregression_baseline=%s\n' "$EXECUTION_START_HEAD" "$REGRESSION_BASELINE"
```

The printed `EXECUTION_START_HEAD` must equal the concrete plan head explicitly approved in the implementation handoff. If it does not, stop and resolve the branch state. Do not run `git checkout`, `git switch --detach`, `git reset` or another operation that moves implementation back to `7e7142f757f66585f240e16781accd044f31eb6f`.

The regression baseline is used only for historical comparisons, protected-file diffs and baseline test-node collection.

## Global Constraints

- Implementation begins from the final approved plan head already present on branch `phase-7-policy-engine`.
- `7e7142f757f66585f240e16781accd044f31eb6f` is the regression baseline only. It is not an execution checkout target.
- Every production behavior gate follows observed RED before production implementation, then focused GREEN, then a small commit.
- Phase 7 does not add a second access intent. Existing `PROBLEMA_ACESSO` remains the intent contract.
- The Phase 7 CDM operational discriminator is `capability = "CDM_ACCESS_REQUEST"`.
- `prepare_access_request(...)` is explicitly CDM-specific in Phase 7. It rejects unsupported `system`, `intent` or `capability` before calling the CDM role normalizer.
- `SessionIdentity` is the only trusted identity source. Chat text never overwrites `username`, `name`, `email` or `area`.
- Requested role is derived only from request text. Identity fields never elevate, reduce, default or infer requested role.
- Role normalization is lexical and deterministic. It does not use LLM, embeddings, fuzzy matching, knowledge answer or playbook instruction.
- `purpose` is exactly `TriageState.problem_text.strip()` after validation. It is not rewritten by a model.
- Role normalization precedence is closed and ordered: conflict, privileged intent, privileged nominal role, explicit `SOLICITANTE`, ambiguous privilege, generic access default, unresolved.
- `AccessRequestPreparation.reason_code` has exactly seven allowed values defined in this plan and the approved spec.
- `AccessRequestContext` preserves `knowledge_id`, `playbook_id`, `playbook_version`, `step_id` and `capability` from the Phase 6 descriptor.
- Descriptor `type` must equal `ACTION_PROPOSAL` during preparation. It is not duplicated in `AccessRequestContext`.
- `PolicyEngine.evaluate(...)` calls shared structural validation itself before every rule lookup.
- `assess_confidence(...)` calls shared structural validation itself before every confidence assessment.
- Every `PolicyRule` is runtime-validated before policy indexing. Type hints are not validation.
- Any invalid policy rule fails engine construction with `PolicyConfigurationError / POLICY_RULE_INVALID`.
- Duplicate valid policy keys fail engine construction with `PolicyConfigurationError / POLICY_RULE_CONFLICT`. No rule wins silently.
- Validation of the complete rule sequence happens before any duplicate-key indexing, so invalid configuration takes precedence over conflict detection.
- A structurally valid context without a policy returns `DENY / POLICY_NOT_FOUND`.
- A structurally invalid context raises an explicit domain validation error and never becomes `POLICY_NOT_FOUND`.
- Policy and confidence remain structurally separate. Policy accepts no confidence input. Confidence accepts no policy input.
- Confidence reason codes are deterministic. CDM access returns exactly two codes in area-then-purpose order. A valid non-CDM context returns exactly `LOW / ("CONTEXT_NOT_CDM_ACCESS_REQUEST",)`.
- `SOLICITANTE` always yields `REQUIRE_APPROVAL` for `CDM_ACCESS_REQUEST`, regardless of HIGH or LOW confidence.
- `APROVADOR`, `ADMIN` and `SUPERADMIN` always yield `DENY` for `CDM_ACCESS_REQUEST`, regardless of confidence.
- Phase 7 production code performs zero HTTP, zero Ollama calls, zero embeddings, zero subprocess execution, zero executor calls and zero CDM calls.
- Phase 7 adds no policy catalog, no CDM adapter, no executor, no request persistence, no human approval state, and no request identifier.
- Do not modify the homologated Phase 4 and Phase 6 fixtures to add CDM.
- Preserve these files exactly unless a focused reproducible blocker is first documented and explicitly reviewed:
  - `src/ai_service_desk/engine/triage.py`
  - `src/ai_service_desk/engine/knowledge.py`
  - `src/ai_service_desk/engine/knowledge_retrieval.py`
  - `src/ai_service_desk/engine/playbook.py`
  - `src/ai_service_desk/engine/playbook_resolution.py`
  - `knowledge/phase4_synthetic_faq.jsonl`
  - `playbooks/phase6_synthetic_playbooks.jsonl`
- `classification.py` may change only by adding `"CDM": ("cdm",)` to `SYSTEM_ALIASES`. Prompt, intents, recovery and heuristics remain byte-for-byte unchanged.
- No existing test may be deleted, disabled, converted to skip or weakened to satisfy the suite.
- This plan defines a minimum of 105 new collected pytest cases. With the Phase 6 baseline of 319, the initial hard floor is 424 collected tests. If implementation adds additional tests, raise the floor by the same number.
- Merge is outside this plan. Final evidence is prepared for review only.

---

## File Map

### Create

- `src/ai_service_desk/engine/access_request.py`: trusted session identity, access contracts, shared structural validation, CDM role normalization, CDM-specific request preparation.
- `src/ai_service_desk/engine/policy.py`: immutable in-code policy rules, runtime rule validation, duplicate-key detection, fail-closed `PolicyEngine`, `PolicyDecision`.
- `src/ai_service_desk/engine/confidence.py`: deterministic confidence assessment with exact ordered machine reason codes.
- `src/ai_service_desk/engine/policy_smoke.py`: strict 15-case synthetic Phase 7 smoke and privacy-safe report.
- `tests/engine/test_access_request.py`: identity, context validation, role normalization and request preparation.
- `tests/engine/test_policy.py`: CDM matrix, invalid rule configuration, unknown policy, independent validation and duplicate rule conflict.
- `tests/engine/test_confidence.py`: confidence composition, ordering and independent validation.
- `tests/engine/test_policy_security.py`: identity spoofing, policy-confidence invariants, fail-closed and zero-execution checks.
- `tests/engine/test_policy_smoke.py`: strict smoke fixture and safe report tests.
- `tests/fixtures/phase7_policy_cases.jsonl`: exactly 15 synthetic policy cases.
- `tests/test_policy_cli.py`: parser and safe CLI behavior.
- `.github/workflows/phase7-policy-smoke.yml`: manual exact-SHA Dell-compatible smoke without Ollama or external calls.
- `docs/policy/phase-7.md`: operator-facing Phase 7 behavior, commands, boundaries and Dell homologation steps.
- `tests/test_phase7_docs.py`: operational documentation and README link contract.

### Modify

- `src/ai_service_desk/engine/classification.py`: add only `"CDM": ("cdm",)` to `SYSTEM_ALIASES`.
- `tests/engine/test_classification.py`: append CDM RED/GREEN and alias regression tests only.
- `src/ai_service_desk/cli.py`: add `policy-smoke` parser/import/handler before generic Ollama construction.
- `tests/test_workflows.py`: append Phase 7 workflow contract only.
- `README.md`: add Phase 7 operational link and scope summary.

### Protected and expected unchanged

```text
src/ai_service_desk/engine/triage.py
src/ai_service_desk/engine/knowledge.py
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/engine/playbook.py
src/ai_service_desk/engine/playbook_resolution.py
knowledge/phase4_synthetic_faq.jsonl
playbooks/phase6_synthetic_playbooks.jsonl
```

---

## Locked Interfaces

### `src/ai_service_desk/engine/access_request.py`

```text
RequestedRole = Literal["SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN", "UNKNOWN"]
ConcreteRequestedRole = Literal["SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN"]
PreparationStatus = Literal["READY", "NEEDS_CLARIFICATION"]

SessionIdentity(
    username: str,
    name: str,
    email: str,
    area: str,
)

AccessRequestContext(
    requester: SessionIdentity,
    system: str,
    intent: str,
    requested_role: ConcreteRequestedRole,
    purpose: str,
    knowledge_id: str,
    playbook_id: str,
    playbook_version: int,
    step_id: str,
    capability: str,
)

AccessRequestPreparation(
    status: PreparationStatus,
    requested_role: RequestedRole,
    reason_code: str,
    context: AccessRequestContext | None,
)

validate_session_identity(identity: SessionIdentity) -> None
validate_access_request_context(context: AccessRequestContext) -> None
normalize_requested_role(problem_text: str) -> tuple[RequestedRole, str]
prepare_access_request(
    requester: SessionIdentity,
    triage: TriageState,
    descriptor: Mapping[str, object],
) -> AccessRequestPreparation
```

Exact `AccessRequestPreparation.reason_code` set:

```text
ROLE_CONFLICT
ROLE_PRIVILEGED_INTENT_MATCH
ROLE_PRIVILEGED_NOMINAL_MATCH
ROLE_SOLICITANTE_EXPLICIT
ROLE_PRIVILEGE_AMBIGUOUS
ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE
ROLE_UNRESOLVED
```

### `src/ai_service_desk/engine/policy.py`

```text
PolicyDecision(
    decision: Literal["REQUIRE_APPROVAL", "DENY"],
    policy_id: str,
    reason_code: str,
    reason: str,
)

PolicyRule(
    system: str,
    capability: str,
    requested_role: ConcreteRequestedRole,
    decision: Literal["REQUIRE_APPROVAL", "DENY"],
    policy_id: str,
    reason_code: str,
    reason: str,
)

PolicyConfigurationError(reason_code: str, message: str)
PolicyEngine(rules: Sequence[PolicyRule] | None = None)
PolicyEngine.evaluate(context: AccessRequestContext) -> PolicyDecision
```

Runtime configuration error codes are exactly:

```text
POLICY_RULE_INVALID
POLICY_RULE_CONFLICT
```

The policy lookup key is exactly:

```text
(system, capability, requested_role)
```

### `src/ai_service_desk/engine/confidence.py`

```text
ConfidenceAssessment(
    level: Literal["HIGH", "LOW"],
    reason_codes: tuple[str, ...],
)

assess_confidence(context: AccessRequestContext) -> ConfidenceAssessment
```

Exact reason code set:

```text
CONTEXT_NOT_CDM_ACCESS_REQUEST
AREA_MATCH_REVENDA
AREA_OUTSIDE_REVENDA
PURPOSE_MATCH_MATERIAL_REQUEST
PURPOSE_NOT_CONFIRMED
```

Exact composition for a valid CDM access context:

```text
(reason_code_for_area, reason_code_for_purpose)
```

Area always occupies index 0. Purpose always occupies index 1.

Valid context outside the exact CDM triple returns:

```python
ConfidenceAssessment(
    level="LOW",
    reason_codes=("CONTEXT_NOT_CDM_ACCESS_REQUEST",),
)
```

### `src/ai_service_desk/engine/policy_smoke.py`

```text
load_policy_cases(path: str | Path) -> list[dict]
run_policy_smoke(cases_path: str | Path, report_path: str | Path) -> dict
```

The smoke contains exactly 15 synthetic cases and does not require Ollama, a knowledge index, a playbook catalog, network access or a work directory.

---

## Quantitative Test Budget

Planned new collected cases:

| Gate | New collected cases |
| --- | ---: |
| Gate 1 classification | 9 |
| Gate 2 contracts and structural validation | 21 |
| Gate 3 role normalizer | 12 |
| Gate 4 CDM preparation and provenance | 14 |
| Gate 5 policy engine and configuration | 23 |
| Gate 6 confidence | 7 |
| Gate 7 security and isolation | 8 |
| Gate 8 smoke | 5 |
| Gate 9 CLI and workflow | 4 |
| Gate 10 docs | 2 |
| **Minimum new Phase 7 cases** | **105** |

Initial final floor:

```text
319 + 105 = 424 collected tests
```

If any extra case is added beyond this plan, the final required count increases one-for-one. Gate 11 also verifies that every pre-Phase-7 collected node ID remains present.

---

# Gate 1 - Strictly Additive CDM System Alias

### Task 1: Recognize CDM without touching classifier behavior

**Files:** modify `tests/engine/test_classification.py`, then modify only the `SYSTEM_ALIASES` mapping in `src/ai_service_desk/engine/classification.py`.

**Interfaces:**
- Consumes: existing `explicit_systems(text: str) -> list[str]`, `classify_ticket(...)`, current alias mapping.
- Produces: canonical literal system `CDM` for exact alias `cdm`. Existing intents, prompt, recovery and heuristics remain unchanged.

- [ ] **Step 1: Append the RED test before modifying production code**

```python
def test_explicit_systems_recognizes_cdm() -> None:
    assert explicit_systems("acesso ao CDM") == ["CDM"]
```

- [ ] **Step 2: Run RED and record the expected failure**

```bash
python -m pytest tests/engine/test_classification.py::test_explicit_systems_recognizes_cdm -v
```

Expected: assertion failure showing the current result is `[]` rather than `["CDM"]`.

- [ ] **Step 3: Add the multi-system and existing-alias regression tests while production is still RED**

```python
def test_cdm_and_cigam_are_multi_system_context() -> None:
    text = "acesso ao CDM e CIGAM"
    assert set(explicit_systems(text)) == {"CDM", "CIGAM"}
    result = classify_ticket(
        text,
        lambda payload: response(
            '{"intent":"PROBLEMA_ACESSO","system":"CDM","entities":{},"confidence":0.9}'
        ),
    )
    assert result.system == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("erro no CIGAM", ["CIGAM"]),
        ("erro no SIAGRI", ["SIAGRI"]),
        ("erro no Outlook", ["OUTLOOK"]),
        ("erro no Teams", ["TEAMS"]),
        ("erro no Microsoft 365", ["OFFICE 365"]),
        ("erro no WhatsApp", ["WHATSAPP"]),
        ("erro no Windows", ["WINDOWS"]),
    ],
)
def test_existing_system_aliases_remain_recognized(text: str, expected: list[str]) -> None:
    assert explicit_systems(text) == expected
```

This contributes 9 new collected cases in Gate 1: two standalone tests plus seven parametrized regressions.

- [ ] **Step 4: Make the single allowed production change**

In `SYSTEM_ALIASES`, append exactly:

```python
    "CDM": ("cdm",),
```

Do not edit `ALLOWED_INTENTS`, `build_payload`, the classifier system prompt, `_recover_literal_system`, `preserve_evidence` or any other logic.

- [ ] **Step 5: Run focused GREEN plus the complete classification file**

```bash
python -m pytest tests/engine/test_classification.py -v
python -m ruff check src/ai_service_desk/engine/classification.py tests/engine/test_classification.py
python -m ruff format --check src/ai_service_desk/engine/classification.py tests/engine/test_classification.py
```

Expected: all classification tests pass. The new literal is recognized, CDM plus CIGAM remains ambiguous, and prior aliases still resolve.

- [ ] **Step 6: Verify the production diff is strictly additive and commit**

```bash
git diff -- src/ai_service_desk/engine/classification.py
git add src/ai_service_desk/engine/classification.py tests/engine/test_classification.py
git commit -m "feat: recognize CDM system alias"
```

Expected production diff: one added mapping entry and no other classifier edits.

---

# Gate 2 - SessionIdentity, Contracts and Shared Structural Validation

### Task 2: Add immutable Phase 7 domain contracts

**Files:** create `src/ai_service_desk/engine/access_request.py`, create `tests/engine/test_access_request.py`.

**Interfaces:**
- Consumes: `ALLOWED_INTENTS`, Phase 6 `CAPABILITY_RE`.
- Produces: `SessionIdentity`, `AccessRequestContext`, `AccessRequestPreparation`, `AccessRequestValidationError`, `validate_session_identity(...)`, `validate_access_request_context(...)`.
- Does not yet add role normalization or request preparation behavior.

- [ ] **Step 1: Write the 21 contract and validation tests first**

```python
from dataclasses import replace

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
    validate_access_request_context,
    validate_session_identity,
)


def valid_identity() -> SessionIdentity:
    return SessionIdentity(
        username="synthetic.user",
        name="Synthetic User",
        email="synthetic.user@example.invalid",
        area="Revenda Sintetica",
    )


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=valid_identity(),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-001",
        playbook_id="PB-SYN-CDM-001",
        playbook_version=1,
        step_id="STEP-CDM-001",
        capability="CDM_ACCESS_REQUEST",
    )


def test_validate_session_identity_accepts_trusted_identity() -> None:
    validate_session_identity(valid_identity())


@pytest.mark.parametrize(
    "identity",
    [
        SessionIdentity("", "Synthetic User", "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", "", "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", "", "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", "u@example.invalid", ""),
        SessionIdentity(None, "Synthetic User", "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", None, "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", None, "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", "u@example.invalid", None),
    ],
)
def test_validate_session_identity_rejects_invalid_fields(identity: SessionIdentity) -> None:
    with pytest.raises(AccessRequestValidationError):
        validate_session_identity(identity)


def test_validate_access_request_context_accepts_structural_cdm() -> None:
    validate_access_request_context(valid_context())


def test_validate_access_request_context_accepts_valid_unknown_policy_domain() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    validate_access_request_context(context)


@pytest.mark.parametrize(
    "context",
    [
        replace(valid_context(), requester=SessionIdentity("", "U", "u@example.invalid", "A")),
        replace(valid_context(), system=""),
        replace(valid_context(), intent="INVENTED_INTENT"),
        replace(valid_context(), requested_role="UNKNOWN"),
        replace(valid_context(), purpose=""),
        replace(valid_context(), knowledge_id=""),
        replace(valid_context(), playbook_id=""),
        replace(valid_context(), playbook_version=0),
        replace(valid_context(), step_id=""),
        replace(valid_context(), capability="not valid"),
    ],
)
def test_validate_access_request_context_rejects_invalid_fields(
    context: AccessRequestContext,
) -> None:
    with pytest.raises(AccessRequestValidationError):
        validate_access_request_context(context)
```

The four constructor calls with `None` are deliberately invalid runtime inputs. If Ruff or a future type checker requires an annotation, add `# type: ignore[arg-type]` only to those four constructor lines. Do not change the test behavior.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/engine/test_access_request.py -v
```

Expected: module import failure because `access_request.py` does not exist.

- [ ] **Step 3: Create the immutable contracts and exact structural validation**

Create `src/ai_service_desk/engine/access_request.py` with this concrete base:

```python
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.classification import ALLOWED_INTENTS
from ai_service_desk.engine.playbook import CAPABILITY_RE
from ai_service_desk.engine.triage import TriageState

RequestedRole = Literal["SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN", "UNKNOWN"]
ConcreteRequestedRole = Literal["SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN"]
PreparationStatus = Literal["READY", "NEEDS_CLARIFICATION"]

CDM_SYSTEM = "CDM"
CDM_ACCESS_INTENT = "PROBLEMA_ACESSO"
CDM_ACCESS_CAPABILITY = "CDM_ACCESS_REQUEST"
CONCRETE_ROLES = frozenset({"SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN"})

ROLE_CONFLICT = "ROLE_CONFLICT"
ROLE_PRIVILEGED_INTENT_MATCH = "ROLE_PRIVILEGED_INTENT_MATCH"
ROLE_PRIVILEGED_NOMINAL_MATCH = "ROLE_PRIVILEGED_NOMINAL_MATCH"
ROLE_SOLICITANTE_EXPLICIT = "ROLE_SOLICITANTE_EXPLICIT"
ROLE_PRIVILEGE_AMBIGUOUS = "ROLE_PRIVILEGE_AMBIGUOUS"
ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE = "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE"
ROLE_UNRESOLVED = "ROLE_UNRESOLVED"
PREPARATION_REASON_CODES = frozenset(
    {
        ROLE_CONFLICT,
        ROLE_PRIVILEGED_INTENT_MATCH,
        ROLE_PRIVILEGED_NOMINAL_MATCH,
        ROLE_SOLICITANTE_EXPLICIT,
        ROLE_PRIVILEGE_AMBIGUOUS,
        ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE,
        ROLE_UNRESOLVED,
    }
)


class AccessRequestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SessionIdentity:
    username: str
    name: str
    email: str
    area: str


@dataclass(frozen=True)
class AccessRequestContext:
    requester: SessionIdentity
    system: str
    intent: str
    requested_role: ConcreteRequestedRole
    purpose: str
    knowledge_id: str
    playbook_id: str
    playbook_version: int
    step_id: str
    capability: str


@dataclass(frozen=True)
class AccessRequestPreparation:
    status: PreparationStatus
    requested_role: RequestedRole
    reason_code: str
    context: AccessRequestContext | None


def _required_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AccessRequestValidationError(
            f"{field} deve ser texto nao vazio com ate {limit} caracteres."
        )
    return value


def validate_session_identity(identity: SessionIdentity) -> None:
    if not isinstance(identity, SessionIdentity):
        raise AccessRequestValidationError("requester deve ser SessionIdentity.")
    _required_text(identity.username, "username", 120)
    _required_text(identity.name, "name", 180)
    _required_text(identity.email, "email", 320)
    _required_text(identity.area, "area", 180)


def validate_access_request_context(context: AccessRequestContext) -> None:
    if not isinstance(context, AccessRequestContext):
        raise AccessRequestValidationError("context deve ser AccessRequestContext.")
    validate_session_identity(context.requester)
    _required_text(context.system, "system", 120)
    intent = _required_text(context.intent, "intent", 120)
    if intent not in ALLOWED_INTENTS:
        raise AccessRequestValidationError("intent fora do contrato existente.")
    if context.requested_role not in CONCRETE_ROLES:
        raise AccessRequestValidationError("requested_role fora do contrato concreto.")
    _required_text(context.purpose, "purpose", 3000)
    _required_text(context.knowledge_id, "knowledge_id", 120)
    _required_text(context.playbook_id, "playbook_id", 120)
    if (
        isinstance(context.playbook_version, bool)
        or not isinstance(context.playbook_version, int)
        or context.playbook_version <= 0
    ):
        raise AccessRequestValidationError("playbook_version deve ser inteiro positivo.")
    _required_text(context.step_id, "step_id", 120)
    capability = _required_text(context.capability, "capability", 120)
    if not CAPABILITY_RE.fullmatch(capability):
        raise AccessRequestValidationError("capability deve ser simbolica valida.")
```

Keep `Mapping` and `TriageState` imported in this new file because Gate 4 extends the same module with the locked `prepare_access_request(...)` signature.

- [ ] **Step 4: Run GREEN and Ruff**

```bash
python -m pytest tests/engine/test_access_request.py -v
python -m ruff check src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
python -m ruff format --check src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
```

- [ ] **Step 5: Commit the contracts**

```bash
git add src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
git commit -m "feat: add phase 7 access request contracts"
```

---

# Gate 3 - RoleNormalizer with Closed Precedence

### Task 3: Implement deterministic requested role normalization

**Files:** modify `src/ai_service_desk/engine/access_request.py`, append tests to `tests/engine/test_access_request.py`.

**Interfaces:**
- Consumes only `problem_text: str` and `normalize_text(...)`.
- Produces `normalize_requested_role(problem_text: str) -> tuple[RequestedRole, str]`.
- Identity is absent from the normalizer signature.

- [ ] **Step 1: Append the RED matrix with all seven terminal reasons**

```python
import inspect

from ai_service_desk.engine.access_request import normalize_requested_role


@pytest.mark.parametrize(
    ("text", "expected_role", "expected_reason"),
    [
        (
            "acesso ao CDM",
            "SOLICITANTE",
            "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE",
        ),
        (
            "quero acesso aprovador",
            "APROVADOR",
            "ROLE_PRIVILEGED_NOMINAL_MATCH",
        ),
        (
            "quero poder aprovar solicitacoes",
            "APROVADOR",
            "ROLE_PRIVILEGED_INTENT_MATCH",
        ),
        ("admin e superadmin", "UNKNOWN", "ROLE_CONFLICT"),
        ("perfil privilegiado", "UNKNOWN", "ROLE_PRIVILEGE_AMBIGUOUS"),
        ("solicitante e admin", "UNKNOWN", "ROLE_CONFLICT"),
        ("preciso de ajuda", "UNKNOWN", "ROLE_UNRESOLVED"),
    ],
)
def test_role_normalizer_closed_precedence(
    text: str,
    expected_role: str,
    expected_reason: str,
) -> None:
    assert normalize_requested_role(text) == (expected_role, expected_reason)


def test_role_normalizer_api_has_no_identity_parameter() -> None:
    assert list(inspect.signature(normalize_requested_role).parameters) == ["problem_text"]


def test_privileged_semantic_and_nominal_conflict_is_unknown() -> None:
    assert normalize_requested_role("admin e quero aprovar solicitacoes") == (
        "UNKNOWN",
        "ROLE_CONFLICT",
    )
```

- [ ] **Step 2: Add nominal role regressions before GREEN**

```python
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("quero admin", ("ADMIN", "ROLE_PRIVILEGED_NOMINAL_MATCH")),
        ("quero superadmin", ("SUPERADMIN", "ROLE_PRIVILEGED_NOMINAL_MATCH")),
        ("quero perfil solicitante", ("SOLICITANTE", "ROLE_SOLICITANTE_EXPLICIT")),
    ],
)
def test_role_normalizer_nominal_positive_cases(text: str, expected: tuple[str, str]) -> None:
    assert normalize_requested_role(text) == expected
```

Gate 3 now contributes exactly 12 collected cases.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/engine/test_access_request.py -k "role_normalizer or privileged_semantic" -v
```

Expected: import failure because `normalize_requested_role` is not defined.

- [ ] **Step 4: Add deterministic lexical constants and the normalizer**

Add this import:

```python
from ai_service_desk.engine.validation import normalize_text
```

Add these closed lexical definitions:

```python
ROLE_NOMINAL_TERMS = {
    "SOLICITANTE": frozenset({"solicitante"}),
    "APROVADOR": frozenset({"aprovador", "aprovadora"}),
    "ADMIN": frozenset({"admin"}),
    "SUPERADMIN": frozenset({"superadmin"}),
}
PRIVILEGED_INTENT_PHRASES = {
    "APROVADOR": ("aprovar solicitacoes",),
}
AMBIGUOUS_PRIVILEGE_PHRASES = (
    "perfil privilegiado",
    "acesso privilegiado",
    "permissao privilegiada",
    "permissoes privilegiadas",
)
GENERIC_ACCESS_TERMS = frozenset({"acesso", "acessar"})
PRIVILEGED_ROLES = frozenset({"APROVADOR", "ADMIN", "SUPERADMIN"})
```

Add these helpers and public function:

```python
def _nominal_role_signals(normalized: str) -> set[str]:
    tokens = set(normalized.split())
    return {
        role for role, terms in ROLE_NOMINAL_TERMS.items() if any(term in tokens for term in terms)
    }


def _privileged_intent_signals(normalized: str) -> set[str]:
    padded = f" {normalized} "
    return {
        role
        for role, phrases in PRIVILEGED_INTENT_PHRASES.items()
        if any(f" {phrase} " in padded for phrase in phrases)
    }


def normalize_requested_role(problem_text: str) -> tuple[RequestedRole, str]:
    text = _required_text(problem_text, "problem_text", 3000)
    normalized = normalize_text(text)
    nominal = _nominal_role_signals(normalized)
    semantic_privileged = _privileged_intent_signals(normalized)
    known_signals = nominal | semantic_privileged

    if len(known_signals) > 1:
        return "UNKNOWN", ROLE_CONFLICT

    if semantic_privileged:
        role = next(iter(semantic_privileged))
        return role, ROLE_PRIVILEGED_INTENT_MATCH

    privileged_nominal = nominal & PRIVILEGED_ROLES
    if privileged_nominal:
        role = next(iter(privileged_nominal))
        return role, ROLE_PRIVILEGED_NOMINAL_MATCH

    if "SOLICITANTE" in nominal:
        return "SOLICITANTE", ROLE_SOLICITANTE_EXPLICIT

    padded = f" {normalized} "
    if any(f" {phrase} " in padded for phrase in AMBIGUOUS_PRIVILEGE_PHRASES):
        return "UNKNOWN", ROLE_PRIVILEGE_AMBIGUOUS

    tokens = set(normalized.split())
    if tokens & GENERIC_ACCESS_TERMS:
        return "SOLICITANTE", ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE

    return "UNKNOWN", ROLE_UNRESOLVED
```

The union in `known_signals` is mandatory. `admin e quero aprovar solicitacoes` contains an ADMIN signal plus an APROVADOR semantic signal, so conflict wins before either privileged rule.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest tests/engine/test_access_request.py -v
python -m ruff check src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
python -m ruff format --check src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
git add src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
git commit -m "feat: add fail-safe CDM role normalization"
```

---

# Gate 4 - CDM-Specific Request Preparation and Phase 6 Provenance

### Task 4: Build AccessRequestContext only for the supported CDM access triple

**Files:** modify `src/ai_service_desk/engine/access_request.py`, append tests to `tests/engine/test_access_request.py`.

**Interfaces:**
- Consumes: `SessionIdentity`, resolved `TriageState`, real Phase 6 descriptor mapping.
- Produces: `prepare_access_request(...) -> AccessRequestPreparation`.
- Rejects unsupported scope before role normalization.

- [ ] **Step 1: Add deterministic test helpers that call the real Phase 6 descriptor**

Append:

```python
from ai_service_desk.engine.playbook_resolution import action_proposal_descriptor
from ai_service_desk.engine.triage import TriageState


def answered_triage(
    problem_text: str = "preciso de acesso ao CDM para solicitar materiais",
    system: str = "CDM",
    intent: str = "PROBLEMA_ACESSO",
) -> TriageState:
    return TriageState(
        version=1,
        session_id="phase7-synthetic-session",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text=problem_text,
        intent=intent,
        system=system,
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def cdm_descriptor() -> dict:
    playbook = {
        "playbook_id": "PB-SYN-CDM-001",
        "playbook_version": 3,
    }
    step = {
        "step_id": "STEP-CDM-ACCESS-01",
        "type": "ACTION_PROPOSAL",
        "capability": "CDM_ACCESS_REQUEST",
    }
    return action_proposal_descriptor("KB-SYN-CDM-001", playbook, step)
```

- [ ] **Step 2: Add RED tests for provenance, ambiguity and exact scope**

```python
from ai_service_desk.engine.access_request import prepare_access_request


def test_prepare_access_request_preserves_real_phase6_descriptor_provenance() -> None:
    result = prepare_access_request(valid_identity(), answered_triage(), cdm_descriptor())
    assert result.status == "READY"
    assert result.requested_role == "SOLICITANTE"
    assert result.reason_code == "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE"
    assert result.context is not None
    assert result.context.purpose == "preciso de acesso ao CDM para solicitar materiais"
    assert result.context.knowledge_id == "KB-SYN-CDM-001"
    assert result.context.playbook_id == "PB-SYN-CDM-001"
    assert result.context.playbook_version == 3
    assert result.context.step_id == "STEP-CDM-ACCESS-01"
    assert result.context.capability == "CDM_ACCESS_REQUEST"


def test_prepare_access_request_keeps_privileged_role_ready_for_policy_denial() -> None:
    result = prepare_access_request(
        valid_identity(),
        answered_triage("quero acesso aprovador ao CDM"),
        cdm_descriptor(),
    )
    assert result.status == "READY"
    assert result.requested_role == "APROVADOR"
    assert result.reason_code == "ROLE_PRIVILEGED_NOMINAL_MATCH"
    assert result.context is not None
    assert result.context.requested_role == "APROVADOR"


def test_prepare_access_request_returns_clarification_for_unknown_role() -> None:
    result = prepare_access_request(
        valid_identity(),
        answered_triage("perfil privilegiado no CDM"),
        cdm_descriptor(),
    )
    assert result.status == "NEEDS_CLARIFICATION"
    assert result.requested_role == "UNKNOWN"
    assert result.reason_code == "ROLE_PRIVILEGE_AMBIGUOUS"
    assert result.context is None


def test_prepare_access_request_rejects_non_action_proposal() -> None:
    descriptor = cdm_descriptor()
    descriptor["type"] = "CHECK"
    with pytest.raises(AccessRequestValidationError):
        prepare_access_request(valid_identity(), answered_triage(), descriptor)


@pytest.mark.parametrize(
    ("triage", "descriptor"),
    [
        (answered_triage(system="CIGAM"), cdm_descriptor()),
        (answered_triage(intent="ERRO_SISTEMA"), cdm_descriptor()),
        (
            answered_triage(),
            {**cdm_descriptor(), "capability": "FUTURE_CAPABILITY"},
        ),
    ],
)
def test_prepare_access_request_rejects_unsupported_scope(
    triage: TriageState,
    descriptor: dict,
) -> None:
    with pytest.raises(AccessRequestValidationError, match="somente CDM"):
        prepare_access_request(valid_identity(), triage, descriptor)
```

- [ ] **Step 3: Prove unsupported scope is rejected before role normalization**

```python
@pytest.mark.parametrize(
    ("triage", "descriptor"),
    [
        (answered_triage(system="FUTURE_SYSTEM"), cdm_descriptor()),
        (answered_triage(), {**cdm_descriptor(), "capability": "FUTURE_CAPABILITY"}),
    ],
)
def test_prepare_access_request_does_not_apply_cdm_role_normalizer_to_future_scope(
    monkeypatch,
    triage: TriageState,
    descriptor: dict,
) -> None:
    import ai_service_desk.engine.access_request as module

    monkeypatch.setattr(
        module,
        "normalize_requested_role",
        lambda text: (_ for _ in ()).throw(AssertionError("normalizer must not run")),
    )
    with pytest.raises(AccessRequestValidationError, match="somente CDM"):
        module.prepare_access_request(valid_identity(), triage, descriptor)
```

- [ ] **Step 4: Add purpose and descriptor corruption tests**

```python
def test_prepare_access_request_preserves_purpose_with_strip_only() -> None:
    result = prepare_access_request(
        valid_identity(),
        answered_triage("  Preciso de acesso ao CDM para solicitar materiais.  "),
        cdm_descriptor(),
    )
    assert result.context is not None
    assert result.context.purpose == "Preciso de acesso ao CDM para solicitar materiais."


@pytest.mark.parametrize(
    "descriptor",
    [
        {key: value for key, value in cdm_descriptor().items() if key != "knowledge_id"},
        {**cdm_descriptor(), "playbook_version": 0},
        {**cdm_descriptor(), "capability": "not valid"},
        {**cdm_descriptor(), "step_id": ""},
    ],
)
def test_prepare_access_request_rejects_corrupt_descriptor(descriptor: dict) -> None:
    with pytest.raises(AccessRequestValidationError):
        prepare_access_request(valid_identity(), answered_triage(), descriptor)
```

Gate 4 contributes 14 collected cases.

- [ ] **Step 5: Run RED**

```bash
python -m pytest tests/engine/test_access_request.py -k "prepare_access_request" -v
```

Expected: import failure because `prepare_access_request` is not implemented.

- [ ] **Step 6: Implement strict descriptor validation and CDM-only preparation**

Add:

```python
ACTION_DESCRIPTOR_FIELDS = {
    "knowledge_id",
    "playbook_id",
    "playbook_version",
    "step_id",
    "type",
    "capability",
}


def _validate_action_descriptor(descriptor: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(descriptor, Mapping) or set(descriptor) != ACTION_DESCRIPTOR_FIELDS:
        raise AccessRequestValidationError("descriptor ACTION_PROPOSAL fora do contrato.")
    data = dict(descriptor)
    _required_text(data["knowledge_id"], "knowledge_id", 120)
    _required_text(data["playbook_id"], "playbook_id", 120)
    version = data["playbook_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise AccessRequestValidationError("playbook_version deve ser inteiro positivo.")
    _required_text(data["step_id"], "step_id", 120)
    if data["type"] != "ACTION_PROPOSAL":
        raise AccessRequestValidationError("descriptor deve ser ACTION_PROPOSAL.")
    capability = _required_text(data["capability"], "capability", 120)
    if not CAPABILITY_RE.fullmatch(capability):
        raise AccessRequestValidationError("capability deve ser simbolica valida.")
    return data


def prepare_access_request(
    requester: SessionIdentity,
    triage: TriageState,
    descriptor: Mapping[str, object],
) -> AccessRequestPreparation:
    validate_session_identity(requester)
    if not isinstance(triage, TriageState):
        raise AccessRequestValidationError("triage deve ser TriageState.")
    if triage.status != "ANSWERED":
        raise AccessRequestValidationError("triage deve estar resolvida como ANSWERED.")
    purpose = _required_text(triage.problem_text, "problem_text", 3000).strip()
    data = _validate_action_descriptor(descriptor)

    if (
        triage.system != CDM_SYSTEM
        or triage.intent != CDM_ACCESS_INTENT
        or data["capability"] != CDM_ACCESS_CAPABILITY
    ):
        raise AccessRequestValidationError(
            "Fase 7 prepara somente CDM / PROBLEMA_ACESSO / CDM_ACCESS_REQUEST."
        )

    requested_role, reason_code = normalize_requested_role(purpose)
    if reason_code not in PREPARATION_REASON_CODES:
        raise AccessRequestValidationError("reason_code de normalizacao fora do contrato.")
    if requested_role == "UNKNOWN":
        return AccessRequestPreparation(
            status="NEEDS_CLARIFICATION",
            requested_role="UNKNOWN",
            reason_code=reason_code,
            context=None,
        )

    context = AccessRequestContext(
        requester=requester,
        system=triage.system,
        intent=triage.intent,
        requested_role=requested_role,
        purpose=purpose,
        knowledge_id=str(data["knowledge_id"]),
        playbook_id=str(data["playbook_id"]),
        playbook_version=int(data["playbook_version"]),
        step_id=str(data["step_id"]),
        capability=str(data["capability"]),
    )
    validate_access_request_context(context)
    return AccessRequestPreparation(
        status="READY",
        requested_role=requested_role,
        reason_code=reason_code,
        context=context,
    )
```

The conversion calls happen only after exact type validation. No provenance field is reconstructed from current playbook state.

- [ ] **Step 7: Run GREEN, confirm protected Phase 6 files are untouched, commit**

```bash
python -m pytest tests/engine/test_access_request.py tests/engine/test_playbook_resolution.py -v
git diff --exit-code 7e7142f757f66585f240e16781accd044f31eb6f -- src/ai_service_desk/engine/playbook.py src/ai_service_desk/engine/playbook_resolution.py knowledge/phase4_synthetic_faq.jsonl playbooks/phase6_synthetic_playbooks.jsonl
python -m ruff check src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
python -m ruff format --check src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
git add src/ai_service_desk/engine/access_request.py tests/engine/test_access_request.py
git commit -m "feat: prepare CDM access request context"
```

---

# Gate 5 - PolicyEngine, Runtime Rule Validation, Fail-Closed Lookup and Conflict Detection

### Task 5: Implement pure deterministic policy evaluation with validated in-code configuration

**Files:** create `src/ai_service_desk/engine/policy.py`, create `tests/engine/test_policy.py`.

**Interfaces:**
- Consumes: `AccessRequestContext`.
- Produces: `PolicyDecision`.
- Independently invokes `validate_access_request_context(context)` on every `evaluate(...)` call.
- Validates every injected or default `PolicyRule` in runtime before any index entry is created.

- [ ] **Step 1: Create self-contained test helpers and RED policy matrix**

```python
from dataclasses import replace

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
)
from ai_service_desk.engine.policy import (
    PolicyConfigurationError,
    PolicyEngine,
    PolicyRule,
)


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=SessionIdentity(
            username="synthetic.policy",
            name="Synthetic Policy User",
            email="synthetic.policy@example.invalid",
            area="Revenda Sintetica",
        ),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-POLICY",
        playbook_id="PB-SYN-CDM-POLICY",
        playbook_version=1,
        step_id="STEP-CDM-POLICY",
        capability="CDM_ACCESS_REQUEST",
    )


def valid_policy_rule() -> PolicyRule:
    return PolicyRule(
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
        requested_role="SOLICITANTE",
        decision="DENY",
        policy_id="FUTURE_ACCESS_POLICY",
        reason_code="FUTURE_ACCESS_DENIED",
        reason="Synthetic valid policy rule.",
    )


@pytest.mark.parametrize(
    ("role", "decision", "policy_id", "reason_code"),
    [
        (
            "SOLICITANTE",
            "REQUIRE_APPROVAL",
            "CDM_SOLICITANTE_ACCESS",
            "CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL",
        ),
        (
            "APROVADOR",
            "DENY",
            "CDM_PRIVILEGED_ACCESS",
            "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        ),
        (
            "ADMIN",
            "DENY",
            "CDM_PRIVILEGED_ACCESS",
            "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        ),
        (
            "SUPERADMIN",
            "DENY",
            "CDM_PRIVILEGED_ACCESS",
            "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        ),
    ],
)
def test_policy_cdm_matrix(
    role: str,
    decision: str,
    policy_id: str,
    reason_code: str,
) -> None:
    result = PolicyEngine().evaluate(replace(valid_context(), requested_role=role))
    assert result.decision == decision
    assert result.policy_id == policy_id
    assert result.reason_code == reason_code


def test_policy_unknown_valid_context_is_fail_closed_deny() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    result = PolicyEngine().evaluate(context)
    assert result.decision == "DENY"
    assert result.policy_id == "FAIL_CLOSED_UNKNOWN_POLICY"
    assert result.reason_code == "POLICY_NOT_FOUND"


def test_policy_evaluate_validates_context_independently() -> None:
    with pytest.raises(AccessRequestValidationError):
        PolicyEngine().evaluate(replace(valid_context(), purpose=""))
```

- [ ] **Step 2: Add RED runtime configuration validation tests before conflict tests**

```python
@pytest.mark.parametrize(
    "rule",
    [
        object(),
        replace(valid_policy_rule(), system=""),
        replace(valid_policy_rule(), system=123),
        replace(valid_policy_rule(), capability="cdm_access_request"),
        replace(valid_policy_rule(), requested_role="UNKNOWN"),
        replace(valid_policy_rule(), requested_role=[]),
        replace(valid_policy_rule(), decision="ALLOW"),
        replace(valid_policy_rule(), decision=[]),
        replace(valid_policy_rule(), policy_id=""),
        replace(valid_policy_rule(), policy_id="bad id"),
        replace(valid_policy_rule(), reason_code=""),
        replace(valid_policy_rule(), reason_code="bad reason"),
        replace(valid_policy_rule(), reason=""),
    ],
)
def test_policy_invalid_rule_configuration_fails_closed(rule: object) -> None:
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((rule,))
    assert exc_info.value.reason_code == "POLICY_RULE_INVALID"
```

The invalid constructor arguments are intentional runtime violations. Add focused `# type: ignore[arg-type]` comments only if future static tooling requires them. Do not remove any case.

- [ ] **Step 3: Add RED conflict, validation-order and idempotency tests**

```python
def duplicate_rule(decision: str = "DENY") -> PolicyRule:
    return PolicyRule(
        system="CDM",
        capability="CDM_ACCESS_REQUEST",
        requested_role="SOLICITANTE",
        decision=decision,
        policy_id="SYN_DUPLICATE",
        reason_code="SYN_DUPLICATE_REASON",
        reason="Synthetic duplicate rule.",
    )


def test_policy_rule_duplicate_key_fails_closed() -> None:
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((duplicate_rule("DENY"), duplicate_rule("REQUIRE_APPROVAL")))
    assert exc_info.value.reason_code == "POLICY_RULE_CONFLICT"


def test_policy_identical_duplicate_key_is_still_conflict() -> None:
    rule = duplicate_rule("DENY")
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((rule, rule))
    assert exc_info.value.reason_code == "POLICY_RULE_CONFLICT"


def test_policy_rule_invalid_precedes_duplicate_key_detection() -> None:
    first = duplicate_rule("DENY")
    second = duplicate_rule("DENY")
    invalid = replace(duplicate_rule("DENY"), decision="ALLOW")
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((first, second, invalid))
    assert exc_info.value.reason_code == "POLICY_RULE_INVALID"


def test_policy_same_context_is_idempotent() -> None:
    engine = PolicyEngine()
    context = valid_context()
    assert engine.evaluate(context) == engine.evaluate(context)
```

Gate 5 contributes 23 collected cases: the original 9 behavior/configuration cases plus 13 parametrized invalid-rule nodes and one validation-order node.

- [ ] **Step 4: Run RED**

```bash
python -m pytest tests/engine/test_policy.py -v
```

Expected: module import failure because `policy.py` does not exist.

- [ ] **Step 5: Implement runtime rule validation, then duplicate-safe indexing**

Create `src/ai_service_desk/engine/policy.py`:

```python
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.access_request import (
    CDM_ACCESS_CAPABILITY,
    CDM_SYSTEM,
    CONCRETE_ROLES,
    AccessRequestContext,
    ConcreteRequestedRole,
    validate_access_request_context,
)
from ai_service_desk.engine.playbook import CAPABILITY_RE

PolicyDecisionValue = Literal["REQUIRE_APPROVAL", "DENY"]
POLICY_DECISIONS = frozenset({"REQUIRE_APPROVAL", "DENY"})
MACHINE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,119}$")


@dataclass(frozen=True)
class PolicyDecision:
    decision: PolicyDecisionValue
    policy_id: str
    reason_code: str
    reason: str


@dataclass(frozen=True)
class PolicyRule:
    system: str
    capability: str
    requested_role: ConcreteRequestedRole
    decision: PolicyDecisionValue
    policy_id: str
    reason_code: str
    reason: str


class PolicyConfigurationError(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


def _invalid_rule(message: str) -> None:
    raise PolicyConfigurationError("POLICY_RULE_INVALID", message)


def _required_rule_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        _invalid_rule(f"{field} invalido na PolicyRule.")
    return value


def _validate_policy_rule(rule: object) -> PolicyRule:
    if not isinstance(rule, PolicyRule):
        _invalid_rule("Entrada de policy deve ser PolicyRule.")
    _required_rule_text(rule.system, "system", 120)
    capability = _required_rule_text(rule.capability, "capability", 120)
    if not CAPABILITY_RE.fullmatch(capability):
        _invalid_rule("capability invalida na PolicyRule.")
    if rule.requested_role not in CONCRETE_ROLES:
        _invalid_rule("requested_role invalida na PolicyRule.")
    if rule.decision not in POLICY_DECISIONS:
        _invalid_rule("decision invalida na PolicyRule.")
    policy_id = _required_rule_text(rule.policy_id, "policy_id", 120)
    if not MACHINE_CODE_RE.fullmatch(policy_id):
        _invalid_rule("policy_id invalido na PolicyRule.")
    reason_code = _required_rule_text(rule.reason_code, "reason_code", 120)
    if not MACHINE_CODE_RE.fullmatch(reason_code):
        _invalid_rule("reason_code invalido na PolicyRule.")
    _required_rule_text(rule.reason, "reason", 500)
    return rule


CDM_POLICY_RULES = (
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="SOLICITANTE",
        decision="REQUIRE_APPROVAL",
        policy_id="CDM_SOLICITANTE_ACCESS",
        reason_code="CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL",
        reason="Acesso de solicitante ao CDM exige aprovacao humana antes da execucao.",
    ),
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="APROVADOR",
        decision="DENY",
        policy_id="CDM_PRIVILEGED_ACCESS",
        reason_code="CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        reason="Roles privilegiados do CDM nao podem ser concedidos por este canal.",
    ),
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="ADMIN",
        decision="DENY",
        policy_id="CDM_PRIVILEGED_ACCESS",
        reason_code="CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        reason="Roles privilegiados do CDM nao podem ser concedidos por este canal.",
    ),
    PolicyRule(
        system=CDM_SYSTEM,
        capability=CDM_ACCESS_CAPABILITY,
        requested_role="SUPERADMIN",
        decision="DENY",
        policy_id="CDM_PRIVILEGED_ACCESS",
        reason_code="CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        reason="Roles privilegiados do CDM nao podem ser concedidos por este canal.",
    ),
)


class PolicyEngine:
    def __init__(self, rules: Sequence[PolicyRule] | None = None):
        source = tuple(CDM_POLICY_RULES if rules is None else rules)
        validated = tuple(_validate_policy_rule(rule) for rule in source)

        index: dict[tuple[str, str, str], PolicyRule] = {}
        for rule in validated:
            key = (rule.system, rule.capability, rule.requested_role)
            if key in index:
                raise PolicyConfigurationError(
                    "POLICY_RULE_CONFLICT",
                    "Duas regras de policy possuem a mesma chave.",
                )
            index[key] = rule
        self._rules = index

    def evaluate(self, context: AccessRequestContext) -> PolicyDecision:
        validate_access_request_context(context)
        rule = self._rules.get((context.system, context.capability, context.requested_role))
        if rule is None:
            return PolicyDecision(
                decision="DENY",
                policy_id="FAIL_CLOSED_UNKNOWN_POLICY",
                reason_code="POLICY_NOT_FOUND",
                reason="Nenhuma policy conhecida autoriza este contexto.",
            )
        return PolicyDecision(
            decision=rule.decision,
            policy_id=rule.policy_id,
            reason_code=rule.reason_code,
            reason=rule.reason,
        )
```

The two-pass construction is mandatory. Do not index while validating. A dict comprehension, `dict.setdefault`, or any other write-before-complete-validation pattern is forbidden because it can obscure configuration errors or conflicts.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m pytest tests/engine/test_policy.py tests/engine/test_access_request.py -v
python -m ruff check src/ai_service_desk/engine/policy.py tests/engine/test_policy.py
python -m ruff format --check src/ai_service_desk/engine/policy.py tests/engine/test_policy.py
git add src/ai_service_desk/engine/policy.py tests/engine/test_policy.py
git commit -m "feat: add validated fail-closed CDM policy engine"
```

---

# Gate 6 - ConfidenceAssessment with Exact Composition and Ordering

### Task 6: Add deterministic confidence independent of policy

**Files:** create `src/ai_service_desk/engine/confidence.py`, create `tests/engine/test_confidence.py`.

**Interfaces:**
- Consumes: `AccessRequestContext` only.
- Produces: `ConfidenceAssessment(level, reason_codes)`.
- Calls shared context validation independently before any confidence rule.

- [ ] **Step 1: Create self-contained helpers and RED tests for all four CDM combinations**

```python
from dataclasses import replace
import inspect

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
)
from ai_service_desk.engine.confidence import ConfidenceAssessment, assess_confidence
from ai_service_desk.engine.policy import PolicyEngine


def valid_identity() -> SessionIdentity:
    return SessionIdentity(
        username="synthetic.confidence",
        name="Synthetic Confidence User",
        email="synthetic.confidence@example.invalid",
        area="Revenda Sintetica",
    )


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=valid_identity(),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-CONFIDENCE",
        playbook_id="PB-SYN-CDM-CONFIDENCE",
        playbook_version=1,
        step_id="STEP-CDM-CONFIDENCE",
        capability="CDM_ACCESS_REQUEST",
    )


@pytest.mark.parametrize(
    ("area", "purpose", "level", "reason_codes"),
    [
        (
            "Revenda Sintetica",
            "preciso de acesso ao CDM para solicitar materiais",
            "HIGH",
            ("AREA_MATCH_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST"),
        ),
        (
            "Financeiro Sintetico",
            "preciso de acesso ao CDM para solicitar materiais",
            "LOW",
            ("AREA_OUTSIDE_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST"),
        ),
        (
            "Revenda Sintetica",
            "preciso de acesso ao CDM",
            "LOW",
            ("AREA_MATCH_REVENDA", "PURPOSE_NOT_CONFIRMED"),
        ),
        (
            "Financeiro Sintetico",
            "preciso de acesso ao CDM",
            "LOW",
            ("AREA_OUTSIDE_REVENDA", "PURPOSE_NOT_CONFIRMED"),
        ),
    ],
)
def test_confidence_exact_reason_composition_and_order(
    area: str,
    purpose: str,
    level: str,
    reason_codes: tuple[str, ...],
) -> None:
    requester = replace(valid_identity(), area=area)
    context = replace(valid_context(), requester=requester, purpose=purpose)
    assert assess_confidence(context) == ConfidenceAssessment(level, reason_codes)
```

- [ ] **Step 2: Add RED independent validation, out-of-domain and signature tests**

```python
def test_confidence_valid_context_outside_cdm_is_single_low_reason() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    assert assess_confidence(context) == ConfidenceAssessment(
        "LOW",
        ("CONTEXT_NOT_CDM_ACCESS_REQUEST",),
    )


def test_confidence_validates_context_independently() -> None:
    with pytest.raises(AccessRequestValidationError):
        assess_confidence(replace(valid_context(), purpose=""))


def test_policy_and_confidence_public_signatures_are_separate() -> None:
    assert list(inspect.signature(PolicyEngine.evaluate).parameters) == ["self", "context"]
    assert list(inspect.signature(assess_confidence).parameters) == ["context"]
```

Gate 6 contributes 7 collected cases.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/engine/test_confidence.py -v
```

Expected: module import failure because `confidence.py` does not exist.

- [ ] **Step 4: Implement exact ordered confidence logic**

Create `src/ai_service_desk/engine/confidence.py`:

```python
from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.access_request import (
    CDM_ACCESS_CAPABILITY,
    CDM_ACCESS_INTENT,
    CDM_SYSTEM,
    AccessRequestContext,
    validate_access_request_context,
)
from ai_service_desk.engine.validation import normalize_text

CONTEXT_NOT_CDM_ACCESS_REQUEST = "CONTEXT_NOT_CDM_ACCESS_REQUEST"
AREA_MATCH_REVENDA = "AREA_MATCH_REVENDA"
AREA_OUTSIDE_REVENDA = "AREA_OUTSIDE_REVENDA"
PURPOSE_MATCH_MATERIAL_REQUEST = "PURPOSE_MATCH_MATERIAL_REQUEST"
PURPOSE_NOT_CONFIRMED = "PURPOSE_NOT_CONFIRMED"

MATERIAL_PURPOSE_PHRASES = (
    "solicitar material",
    "solicitar materiais",
    "solicitacao de material",
    "solicitacao de materiais",
)


@dataclass(frozen=True)
class ConfidenceAssessment:
    level: Literal["HIGH", "LOW"]
    reason_codes: tuple[str, ...]


def _is_cdm_access_context(context: AccessRequestContext) -> bool:
    return (
        context.system == CDM_SYSTEM
        and context.intent == CDM_ACCESS_INTENT
        and context.capability == CDM_ACCESS_CAPABILITY
    )


def _area_matches_revenda(area: str) -> bool:
    return "revenda" in normalize_text(area).split()


def _purpose_matches_material_request(purpose: str) -> bool:
    normalized = f" {normalize_text(purpose)} "
    return any(f" {phrase} " in normalized for phrase in MATERIAL_PURPOSE_PHRASES)


def assess_confidence(context: AccessRequestContext) -> ConfidenceAssessment:
    validate_access_request_context(context)
    if not _is_cdm_access_context(context):
        return ConfidenceAssessment("LOW", (CONTEXT_NOT_CDM_ACCESS_REQUEST,))

    area_match = _area_matches_revenda(context.requester.area)
    purpose_match = _purpose_matches_material_request(context.purpose)
    area_reason = AREA_MATCH_REVENDA if area_match else AREA_OUTSIDE_REVENDA
    purpose_reason = PURPOSE_MATCH_MATERIAL_REQUEST if purpose_match else PURPOSE_NOT_CONFIRMED
    level: Literal["HIGH", "LOW"] = "HIGH" if area_match and purpose_match else "LOW"
    return ConfidenceAssessment(level, (area_reason, purpose_reason))
```

The tuple construction is fixed. Do not sort reason codes, build them from a set or omit negative reasons.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest tests/engine/test_confidence.py tests/engine/test_policy.py -v
python -m ruff check src/ai_service_desk/engine/confidence.py tests/engine/test_confidence.py
python -m ruff format --check src/ai_service_desk/engine/confidence.py tests/engine/test_confidence.py
git add src/ai_service_desk/engine/confidence.py tests/engine/test_confidence.py
git commit -m "feat: add deterministic access confidence"
```

---

# Gate 7 - Identity Spoofing, Fail-Closed Invariants and Zero External Execution

### Task 7: Prove cross-module security boundaries

**Files:** create `tests/engine/test_policy_security.py`. Production changes are allowed only if a new RED test reveals a defect in the Phase 7 modules created by Gates 2 through 6.

**Interfaces:**
- Consumes: real `prepare_access_request`, `PolicyEngine`, `assess_confidence`, and real Phase 6 `action_proposal_descriptor`.
- Produces: evidence that identity cannot be overwritten, confidence cannot authorize, unknown policy denies, and no Phase 7 path calls external execution.

- [ ] **Step 1: Create self-contained end-to-end helpers**

```python
from dataclasses import replace
from pathlib import Path
import subprocess

import pytest
import requests

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    SessionIdentity,
    prepare_access_request,
)
from ai_service_desk.engine.confidence import assess_confidence
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.playbook_resolution import action_proposal_descriptor
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.triage import TriageState


def valid_identity() -> SessionIdentity:
    return SessionIdentity(
        username="synthetic.security",
        name="Synthetic Security User",
        email="synthetic.security@example.invalid",
        area="Revenda Sintetica",
    )


def answered_triage(problem_text: str) -> TriageState:
    return TriageState(
        version=1,
        session_id="phase7-security",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text=problem_text,
        intent="PROBLEMA_ACESSO",
        system="CDM",
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def cdm_descriptor() -> dict:
    return action_proposal_descriptor(
        "KB-SYN-CDM-SECURITY",
        {"playbook_id": "PB-SYN-CDM-SECURITY", "playbook_version": 1},
        {
            "step_id": "STEP-CDM-SECURITY",
            "type": "ACTION_PROPOSAL",
            "capability": "CDM_ACCESS_REQUEST",
        },
    )


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=valid_identity(),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-SECURITY",
        playbook_id="PB-SYN-CDM-SECURITY",
        playbook_version=1,
        step_id="STEP-CDM-SECURITY",
        capability="CDM_ACCESS_REQUEST",
    )


def phase7_result(problem_text: str, area: str):
    identity = replace(valid_identity(), area=area)
    preparation = prepare_access_request(identity, answered_triage(problem_text), cdm_descriptor())
    assert preparation.context is not None
    context = preparation.context
    return preparation, PolicyEngine().evaluate(context), assess_confidence(context)
```

- [ ] **Step 2: Add identity spoofing tests**

```python
def test_chat_cannot_spoof_financeiro_area_into_revenda() -> None:
    preparation, policy, confidence = phase7_result(
        "sou da Revenda e preciso de acesso ao CDM para solicitar materiais",
        "Financeiro Sintetico",
    )
    assert preparation.context is not None
    assert preparation.context.requester.area == "Financeiro Sintetico"
    assert preparation.requested_role == "SOLICITANTE"
    assert policy.decision == "REQUIRE_APPROVAL"
    assert confidence.reason_codes == (
        "AREA_OUTSIDE_REVENDA",
        "PURPOSE_MATCH_MATERIAL_REQUEST",
    )


def test_chat_name_and_email_do_not_replace_session_identity() -> None:
    identity = valid_identity()
    preparation = prepare_access_request(
        identity,
        answered_triage(
            "meu nome e Fake Admin e meu email e fake@example.com, preciso de acesso ao CDM"
        ),
        cdm_descriptor(),
    )
    assert preparation.context is not None
    assert preparation.context.requester.name == identity.name
    assert preparation.context.requester.email == identity.email
```

- [ ] **Step 3: Add policy-confidence invariants**

```python
def test_superadmin_revenda_with_perfect_purpose_is_still_denied() -> None:
    preparation, policy, confidence = phase7_result(
        "preciso de superadmin no CDM para solicitar materiais",
        "Revenda Sintetica",
    )
    assert preparation.requested_role == "SUPERADMIN"
    assert policy.decision == "DENY"
    assert policy.reason_code == "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED"
    assert confidence.level == "HIGH"


@pytest.mark.parametrize(
    ("area", "expected_confidence"),
    [
        ("Revenda Sintetica", "HIGH"),
        ("Financeiro Sintetico", "LOW"),
    ],
)
def test_solicitante_policy_is_require_approval_for_high_and_low(
    area: str,
    expected_confidence: str,
) -> None:
    preparation, policy, confidence = phase7_result(
        "preciso de acesso ao CDM para solicitar materiais",
        area,
    )
    assert preparation.requested_role == "SOLICITANTE"
    assert policy.decision == "REQUIRE_APPROVAL"
    assert confidence.level == expected_confidence
```

- [ ] **Step 4: Add unknown-policy and runtime external-call guards**

```python
def test_valid_unknown_policy_stays_denied_and_confidence_stays_low() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    policy = PolicyEngine().evaluate(context)
    confidence = assess_confidence(context)
    assert policy.decision == "DENY"
    assert policy.reason_code == "POLICY_NOT_FOUND"
    assert confidence.level == "LOW"
    assert confidence.reason_codes == ("CONTEXT_NOT_CDM_ACCESS_REQUEST",)


def test_phase7_domain_paths_make_zero_external_calls(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("external execution forbidden in Phase 7")

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(OllamaClient, "chat", forbidden)
    monkeypatch.setattr(LocalEmbedder, "embed", forbidden)

    preparation, policy, confidence = phase7_result(
        "preciso de acesso ao CDM para solicitar materiais",
        "Revenda Sintetica",
    )
    assert preparation.status == "READY"
    assert policy.decision == "REQUIRE_APPROVAL"
    assert confidence.level == "HIGH"
```

- [ ] **Step 5: Add a static boundary scan for the three production modules**

```python
def test_phase7_domain_modules_do_not_import_execution_or_persistence_boundaries() -> None:
    root = Path(__file__).resolve().parents[2]
    files = [
        root / "src/ai_service_desk/engine/access_request.py",
        root / "src/ai_service_desk/engine/policy.py",
        root / "src/ai_service_desk/engine/confidence.py",
    ]
    forbidden = (
        "import requests",
        "from requests",
        "import subprocess",
        "from subprocess",
        "OllamaClient",
        "LocalEmbedder",
        "CDMAdapter",
        "ExecutionEngine",
        "REQUEST_ACCESS",
        "request_id",
        "sqlite3",
        "sqlalchemy",
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{marker} found in {path.name}"
```

Gate 7 contributes 8 collected cases.

- [ ] **Step 6: Run RED if an invariant exposes a defect, then focused GREEN**

```bash
python -m pytest tests/engine/test_policy_security.py -v
python -m pytest tests/engine/test_access_request.py tests/engine/test_policy.py tests/engine/test_confidence.py tests/engine/test_policy_security.py -v
python -m ruff check src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py tests/engine/test_policy_security.py
python -m ruff format --check src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py tests/engine/test_policy_security.py
```

If RED exposes a defect, change only the owning Phase 7 module and rerun the exact failing test before the full Gate 7 GREEN command.

- [ ] **Step 7: Commit the security proof**

```bash
git add tests/engine/test_policy_security.py src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
git commit -m "test: lock phase 7 policy security boundaries"
```

If no production file changed after RED, the commit contains only `tests/engine/test_policy_security.py`.

---

# Gate 8 - Exact 15-Case Synthetic Phase 7 Smoke

### Task 8: Add deterministic smoke without Ollama or Phase 4/6 fixture mutation

**Files:** create `tests/fixtures/phase7_policy_cases.jsonl`, create `src/ai_service_desk/engine/policy_smoke.py`, create `tests/engine/test_policy_smoke.py`.

**Interfaces:**
- Consumes: real `action_proposal_descriptor(...)`, Phase 7 preparation, policy and confidence.
- Produces: `load_policy_cases(...)`, `run_policy_smoke(...)`, and a local privacy-safe report.

- [ ] **Step 1: Create the exact 15 synthetic fixture rows**

Use these fields on every line:

```text
case_name
username
name
email
area
problem_text
expected_preparation_status
expected_role
expected_preparation_reason_code
expected_policy_decision
expected_policy_reason_code
expected_confidence
expected_confidence_reason_codes
```

Create `tests/fixtures/phase7_policy_cases.jsonl` with exactly these rows:

```jsonl
{"case_name":"generic_revenda_materials","username":"synthetic.01","name":"Synthetic User 01","email":"synthetic.01@example.invalid","area":"Revenda Sintetica","problem_text":"preciso de acesso ao CDM para solicitar materiais","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"HIGH","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_MATCH_MATERIAL_REQUEST"]}
{"case_name":"generic_financeiro_materials","username":"synthetic.02","name":"Synthetic User 02","email":"synthetic.02@example.invalid","area":"Financeiro Sintetico","problem_text":"preciso de acesso ao CDM para solicitar materiais","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_OUTSIDE_REVENDA","PURPOSE_MATCH_MATERIAL_REQUEST"]}
{"case_name":"aprovador_nominal","username":"synthetic.03","name":"Synthetic User 03","email":"synthetic.03@example.invalid","area":"Revenda Sintetica","problem_text":"quero acesso aprovador ao CDM","expected_preparation_status":"READY","expected_role":"APROVADOR","expected_preparation_reason_code":"ROLE_PRIVILEGED_NOMINAL_MATCH","expected_policy_decision":"DENY","expected_policy_reason_code":"CDM_PRIVILEGED_ACCESS_NOT_ALLOWED","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_NOT_CONFIRMED"]}
{"case_name":"aprovador_semantic","username":"synthetic.04","name":"Synthetic User 04","email":"synthetic.04@example.invalid","area":"Revenda Sintetica","problem_text":"quero poder aprovar solicitacoes no CDM","expected_preparation_status":"READY","expected_role":"APROVADOR","expected_preparation_reason_code":"ROLE_PRIVILEGED_INTENT_MATCH","expected_policy_decision":"DENY","expected_policy_reason_code":"CDM_PRIVILEGED_ACCESS_NOT_ALLOWED","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_NOT_CONFIRMED"]}
{"case_name":"admin_nominal","username":"synthetic.05","name":"Synthetic User 05","email":"synthetic.05@example.invalid","area":"Revenda Sintetica","problem_text":"preciso de acesso admin ao CDM","expected_preparation_status":"READY","expected_role":"ADMIN","expected_preparation_reason_code":"ROLE_PRIVILEGED_NOMINAL_MATCH","expected_policy_decision":"DENY","expected_policy_reason_code":"CDM_PRIVILEGED_ACCESS_NOT_ALLOWED","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_NOT_CONFIRMED"]}
{"case_name":"superadmin_nominal","username":"synthetic.06","name":"Synthetic User 06","email":"synthetic.06@example.invalid","area":"Financeiro Sintetico","problem_text":"preciso de superadmin no CDM","expected_preparation_status":"READY","expected_role":"SUPERADMIN","expected_preparation_reason_code":"ROLE_PRIVILEGED_NOMINAL_MATCH","expected_policy_decision":"DENY","expected_policy_reason_code":"CDM_PRIVILEGED_ACCESS_NOT_ALLOWED","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_OUTSIDE_REVENDA","PURPOSE_NOT_CONFIRMED"]}
{"case_name":"admin_superadmin_conflict","username":"synthetic.07","name":"Synthetic User 07","email":"synthetic.07@example.invalid","area":"Revenda Sintetica","problem_text":"admin e superadmin","expected_preparation_status":"NEEDS_CLARIFICATION","expected_role":"UNKNOWN","expected_preparation_reason_code":"ROLE_CONFLICT","expected_policy_decision":"","expected_policy_reason_code":"","expected_confidence":"","expected_confidence_reason_codes":[]}
{"case_name":"ambiguous_privileged","username":"synthetic.08","name":"Synthetic User 08","email":"synthetic.08@example.invalid","area":"Revenda Sintetica","problem_text":"perfil privilegiado","expected_preparation_status":"NEEDS_CLARIFICATION","expected_role":"UNKNOWN","expected_preparation_reason_code":"ROLE_PRIVILEGE_AMBIGUOUS","expected_policy_decision":"","expected_policy_reason_code":"","expected_confidence":"","expected_confidence_reason_codes":[]}
{"case_name":"solicitante_admin_conflict","username":"synthetic.09","name":"Synthetic User 09","email":"synthetic.09@example.invalid","area":"Revenda Sintetica","problem_text":"solicitante e admin","expected_preparation_status":"NEEDS_CLARIFICATION","expected_role":"UNKNOWN","expected_preparation_reason_code":"ROLE_CONFLICT","expected_policy_decision":"","expected_policy_reason_code":"","expected_confidence":"","expected_confidence_reason_codes":[]}
{"case_name":"solicitante_explicit_high","username":"synthetic.10","name":"Synthetic User 10","email":"synthetic.10@example.invalid","area":"Revenda Sintetica","problem_text":"quero acesso solicitante ao CDM para solicitar materiais","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_SOLICITANTE_EXPLICIT","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"HIGH","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_MATCH_MATERIAL_REQUEST"]}
{"case_name":"solicitante_explicit_low","username":"synthetic.11","name":"Synthetic User 11","email":"synthetic.11@example.invalid","area":"Financeiro Sintetico","problem_text":"quero acesso solicitante ao CDM para solicitar materiais","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_SOLICITANTE_EXPLICIT","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_OUTSIDE_REVENDA","PURPOSE_MATCH_MATERIAL_REQUEST"]}
{"case_name":"chat_spoof_revenda","username":"synthetic.12","name":"Synthetic User 12","email":"synthetic.12@example.invalid","area":"Financeiro Sintetico","problem_text":"sou da Revenda e preciso de acesso ao CDM para solicitar materiais","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_OUTSIDE_REVENDA","PURPOSE_MATCH_MATERIAL_REQUEST"]}
{"case_name":"revenda_without_material_purpose","username":"synthetic.13","name":"Synthetic User 13","email":"synthetic.13@example.invalid","area":"Revenda Sintetica","problem_text":"preciso de acesso ao CDM","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_NOT_CONFIRMED"]}
{"case_name":"financeiro_without_material_purpose","username":"synthetic.14","name":"Synthetic User 14","email":"synthetic.14@example.invalid","area":"Financeiro Sintetico","problem_text":"preciso de acesso ao CDM","expected_preparation_status":"READY","expected_role":"SOLICITANTE","expected_preparation_reason_code":"ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE","expected_policy_decision":"REQUIRE_APPROVAL","expected_policy_reason_code":"CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL","expected_confidence":"LOW","expected_confidence_reason_codes":["AREA_OUTSIDE_REVENDA","PURPOSE_NOT_CONFIRMED"]}
{"case_name":"superadmin_revenda_perfect_context","username":"synthetic.15","name":"Synthetic User 15","email":"synthetic.15@example.invalid","area":"Revenda Sintetica","problem_text":"preciso de superadmin no CDM para solicitar materiais","expected_preparation_status":"READY","expected_role":"SUPERADMIN","expected_preparation_reason_code":"ROLE_PRIVILEGED_NOMINAL_MATCH","expected_policy_decision":"DENY","expected_policy_reason_code":"CDM_PRIVILEGED_ACCESS_NOT_ALLOWED","expected_confidence":"HIGH","expected_confidence_reason_codes":["AREA_MATCH_REVENDA","PURPOSE_MATCH_MATERIAL_REQUEST"]}
```

- [ ] **Step 2: Write RED smoke tests with complete imports**

```python
from pathlib import Path
import subprocess

import pytest
import requests

from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.policy_smoke import load_policy_cases, run_policy_smoke

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "phase7_policy_cases.jsonl"


def test_load_policy_cases_requires_exactly_15_cases() -> None:
    cases = load_policy_cases(FIXTURE)
    assert len(cases) == 15
    assert len({row["case_name"] for row in cases}) == 15


def test_load_policy_cases_rejects_invalid_schema(tmp_path: Path) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text('{"case_name":"only"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy_cases(path)


def test_run_policy_smoke_passes_all_15_cases(tmp_path: Path) -> None:
    report = run_policy_smoke(FIXTURE, tmp_path / "report.json")
    assert report["ok"] is True
    assert len(report["cases"]) == 15
    assert all(row["passed"] for row in report["cases"])


def test_policy_smoke_report_is_privacy_safe(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    run_policy_smoke(FIXTURE, report_path)
    text = report_path.read_text(encoding="utf-8")
    for forbidden in (
        "Synthetic User",
        "example.invalid",
        "Financeiro Sintetico",
        "Revenda Sintetica",
        "preciso de acesso",
        "quero acesso",
        "CDM_ACCESS_REQUEST",
        "KB-SYN-CDM",
        "PB-SYN-CDM",
    ):
        assert forbidden not in text


def test_policy_smoke_makes_zero_external_calls(monkeypatch, tmp_path: Path) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("external execution forbidden")

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(OllamaClient, "chat", forbidden)
    monkeypatch.setattr(LocalEmbedder, "embed", forbidden)
    report = run_policy_smoke(FIXTURE, tmp_path / "report.json")
    assert report["ok"] is True
```

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/engine/test_policy_smoke.py -v
```

Expected: module import failure because `policy_smoke.py` does not exist.

- [ ] **Step 4: Implement the complete strict smoke loader and runner**

Create `src/ai_service_desk/engine/policy_smoke.py`:

```python
import json
from datetime import UTC, datetime
from pathlib import Path

from ai_service_desk.engine.access_request import SessionIdentity, prepare_access_request
from ai_service_desk.engine.confidence import assess_confidence
from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.playbook_resolution import action_proposal_descriptor
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.triage import TriageState

CASE_FIELDS = {
    "case_name",
    "username",
    "name",
    "email",
    "area",
    "problem_text",
    "expected_preparation_status",
    "expected_role",
    "expected_preparation_reason_code",
    "expected_policy_decision",
    "expected_policy_reason_code",
    "expected_confidence",
    "expected_confidence_reason_codes",
}


def load_policy_cases(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ValueError("Arquivo de casos da Fase 7 nao encontrado.")
    rows: list[dict] = []
    seen: set[str] = set()
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON invalido na linha {line_number}.") from exc
                if not isinstance(raw, dict) or set(raw) != CASE_FIELDS:
                    raise ValueError("Campos invalidos no caso da Fase 7.")
                name = raw["case_name"]
                if not isinstance(name, str) or not name.strip() or name in seen:
                    raise ValueError("case_name invalido ou duplicado.")
                for field in (
                    "username",
                    "name",
                    "email",
                    "area",
                    "problem_text",
                    "expected_preparation_status",
                    "expected_role",
                    "expected_preparation_reason_code",
                    "expected_policy_decision",
                    "expected_policy_reason_code",
                    "expected_confidence",
                ):
                    if not isinstance(raw[field], str):
                        raise ValueError(f"{field} deve ser texto.")
                codes = raw["expected_confidence_reason_codes"]
                if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
                    raise ValueError("expected_confidence_reason_codes deve ser lista de textos.")
                seen.add(name)
                rows.append(dict(raw))
    except UnicodeDecodeError as exc:
        raise ValueError("Casos da Fase 7 devem ser JSONL UTF-8 valido.") from exc
    if len(rows) != 15:
        raise ValueError("Smoke da Fase 7 exige exatamente 15 casos sinteticos.")
    return rows


def _cdm_descriptor() -> dict:
    return action_proposal_descriptor(
        "KB-SYN-CDM-ACCESS-001",
        {
            "playbook_id": "PB-SYN-CDM-ACCESS-001",
            "playbook_version": 1,
        },
        {
            "step_id": "STEP-CDM-ACCESS-01",
            "type": "ACTION_PROPOSAL",
            "capability": "CDM_ACCESS_REQUEST",
        },
    )


def _triage(case: dict) -> TriageState:
    return TriageState(
        version=1,
        session_id=f"phase7-{case['case_name']}",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text=case["problem_text"],
        intent="PROBLEMA_ACESSO",
        system="CDM",
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def _safe_case_result(
    case: dict,
    actual_preparation_status: str,
    actual_role: str,
    actual_preparation_reason_code: str,
    actual_policy_decision: str,
    actual_policy_reason_code: str,
    actual_confidence: str,
    actual_confidence_reason_codes: tuple[str, ...],
) -> dict:
    expected_codes = tuple(case["expected_confidence_reason_codes"])
    passed = (
        actual_preparation_status == case["expected_preparation_status"]
        and actual_role == case["expected_role"]
        and actual_preparation_reason_code == case["expected_preparation_reason_code"]
        and actual_policy_decision == case["expected_policy_decision"]
        and actual_policy_reason_code == case["expected_policy_reason_code"]
        and actual_confidence == case["expected_confidence"]
        and actual_confidence_reason_codes == expected_codes
    )
    return {
        "case_name": case["case_name"],
        "actual_preparation_status": actual_preparation_status,
        "actual_role": actual_role,
        "actual_preparation_reason_code": actual_preparation_reason_code,
        "actual_policy_decision": actual_policy_decision,
        "actual_policy_reason_code": actual_policy_reason_code,
        "actual_confidence": actual_confidence,
        "actual_confidence_reason_codes": list(actual_confidence_reason_codes),
        "passed": bool(passed),
    }


def run_policy_smoke(cases_path: str | Path, report_path: str | Path) -> dict:
    report = {
        "schema_version": 1,
        "phase": 7,
        "domain": "POLICY_ENGINE",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "ok": False,
        "cases": [],
        "privacy": {
            "identity_included": False,
            "raw_problem_text_included": False,
            "purpose_included": False,
            "capability_included": False,
            "corporate_data_included": False,
        },
    }
    try:
        cases = load_policy_cases(cases_path)
        engine = PolicyEngine()
        descriptor = _cdm_descriptor()
        for case in cases:
            try:
                requester = SessionIdentity(
                    username=case["username"],
                    name=case["name"],
                    email=case["email"],
                    area=case["area"],
                )
                preparation = prepare_access_request(requester, _triage(case), descriptor)
                actual_policy_decision = ""
                actual_policy_reason_code = ""
                actual_confidence = ""
                actual_confidence_reason_codes: tuple[str, ...] = ()
                if preparation.status == "READY":
                    if preparation.context is None:
                        raise ValueError("READY sem AccessRequestContext.")
                    decision = engine.evaluate(preparation.context)
                    confidence = assess_confidence(preparation.context)
                    actual_policy_decision = decision.decision
                    actual_policy_reason_code = decision.reason_code
                    actual_confidence = confidence.level
                    actual_confidence_reason_codes = confidence.reason_codes
                elif preparation.context is not None:
                    raise ValueError("NEEDS_CLARIFICATION com contexto preenchido.")
                report["cases"].append(
                    _safe_case_result(
                        case,
                        preparation.status,
                        preparation.requested_role,
                        preparation.reason_code,
                        actual_policy_decision,
                        actual_policy_reason_code,
                        actual_confidence,
                        actual_confidence_reason_codes,
                    )
                )
            except (ValueError, RuntimeError, OSError, KeyError, AssertionError) as exc:
                report["cases"].append(
                    {
                        "case_name": case["case_name"],
                        "actual_preparation_status": "EXECUTION_ERROR",
                        "actual_role": "",
                        "actual_preparation_reason_code": type(exc).__name__,
                        "actual_policy_decision": "",
                        "actual_policy_reason_code": "",
                        "actual_confidence": "",
                        "actual_confidence_reason_codes": [],
                        "passed": False,
                    }
                )
        report["ok"] = len(report["cases"]) == 15 and all(row["passed"] for row in report["cases"])
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        report["error"] = type(exc).__name__
    finally:
        atomic_json(Path(report_path), report)
    return report
```

The runner never stores exception messages, identity values, raw problem text, purpose, capability, knowledge ID or playbook ID in its persisted report.

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest tests/engine/test_policy_smoke.py tests/engine/test_policy_security.py -v
python -m ruff check src/ai_service_desk/engine/policy_smoke.py tests/engine/test_policy_smoke.py
python -m ruff format --check src/ai_service_desk/engine/policy_smoke.py tests/engine/test_policy_smoke.py
git add src/ai_service_desk/engine/policy_smoke.py tests/engine/test_policy_smoke.py tests/fixtures/phase7_policy_cases.jsonl
git commit -m "test: add synthetic phase 7 policy smoke"
```

---

# Gate 9 - CLI and Manual Workflow

### Task 9: Expose safe `policy-smoke` and exact-head Dell-compatible workflow

**Files:** modify `src/ai_service_desk/cli.py`, create `tests/test_policy_cli.py`, create `.github/workflows/phase7-policy-smoke.yml`, append `tests/test_workflows.py`.

**Interfaces:**
- Produces CLI: `policy-smoke --cases PATH --report PATH`.
- No `--url`, knowledge index, playbook catalog or work directory is accepted.
- Workflow `target_ref` is required to be the exact 40-character candidate commit SHA, not a branch name.

- [ ] **Step 1: Write CLI RED tests**

```python
from pathlib import Path

from ai_service_desk import cli


def test_phase7_parser_accepts_exact_policy_smoke_command() -> None:
    args = cli.build_parser().parse_args(
        ["policy-smoke", "--cases", "cases.jsonl", "--report", "report.json"]
    )
    assert args.command == "policy-smoke"
    assert args.cases == Path("cases.jsonl")
    assert args.report == Path("report.json")
    assert not hasattr(args, "url")
    assert not hasattr(args, "knowledge_index")
    assert not hasattr(args, "playbooks")
    assert not hasattr(args, "work_directory")


def test_policy_smoke_cli_output_is_safe_and_does_not_construct_ollama(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli,
        "run_policy_smoke",
        lambda *args, **kwargs: {"ok": True, "cases": [{}] * 15},
    )
    monkeypatch.setattr(
        cli,
        "OllamaClient",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Ollama forbidden")),
    )
    assert cli.main(["policy-smoke", "--cases", "c", "--report", "r"]) == 0
    out = capsys.readouterr().out
    assert "POLICY SMOKE OK" in out
    assert "Casos sinteticos: 15" in out
    assert "CDM_ACCESS_REQUEST" not in out
    assert "Synthetic User" not in out


def test_policy_smoke_cli_returns_nonzero_when_report_is_not_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "run_policy_smoke",
        lambda *args, **kwargs: {"ok": False, "cases": [{}] * 15},
    )
    assert cli.main(["policy-smoke", "--cases", "c", "--report", "r"]) == 1
```

- [ ] **Step 2: Write workflow RED test including exact-head proof**

Append to `tests/test_workflows.py`:

```python
PHASE7_WORKFLOW = ROOT / ".github" / "workflows" / "phase7-policy-smoke.yml"


def test_phase7_policy_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE7_WORKFLOW.exists()
    text = PHASE7_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "Exact candidate commit SHA to validate",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "TARGET_REF: ${{ inputs.target_ref }}",
        "git rev-parse HEAD",
        "^[0-9a-f]{40}$",
        "$actual -ne $expected",
        "python -m ruff check .",
        "python -m ruff format --check .",
        "python -m pytest -q",
        "python -m ai_service_desk policy-smoke",
        "tests/fixtures/phase7_policy_cases.jsonl",
    ):
        assert required in text
    for forbidden in (
        "upload-artifact",
        "Get-Content",
        "python -m ai_service_desk doctor",
        "knowledge-index",
        "playbook-build",
        "http://127.0.0.1:11434",
        "CDM_ACCESS_REQUEST",
        "PHASE7_CANDIDATE_SHA",
    ):
        assert forbidden not in text
```

Gate 9 contributes 4 collected cases.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests/test_policy_cli.py tests/test_workflows.py::test_phase7_policy_workflow_is_manual_local_and_non_exporting -v
```

Expected: parser rejects `policy-smoke`, workflow file is missing.

- [ ] **Step 4: Add CLI import, parser and handler before generic Ollama construction**

Add import:

```python
from ai_service_desk.engine.policy_smoke import run_policy_smoke
```

Add parser:

```python
    policy_smoke = sub.add_parser("policy-smoke")
    policy_smoke.add_argument("--cases", type=Path, required=True)
    policy_smoke.add_argument("--report", type=Path, required=True)
```

Add handler before the existing line `client = OllamaClient(args.url)`:

```python
        if args.command == "policy-smoke":
            report = run_policy_smoke(args.cases, args.report)
            print("POLICY SMOKE OK" if report["ok"] else "POLICY SMOKE REQUER REVISAO")
            print(f"Casos sinteticos: {len(report.get('cases', []))}")
            print("Relatorio agregado local: " + str(args.report))
            return 0 if report["ok"] else 1
```

- [ ] **Step 5: Create the manual Phase 7 workflow with exact-head verification inside the workflow**

Create `.github/workflows/phase7-policy-smoke.yml`:

```yaml
name: Phase 7 policy smoke

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
  phase7-policy-smoke:
    name: Windows Phase 7 policy smoke
    runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
    timeout-minutes: 20

    steps:
      - name: Checkout target ref
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.target_ref }}

      - name: Verify exact target SHA
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        env:
          TARGET_REF: ${{ inputs.target_ref }}
        run: |
          $ErrorActionPreference = "Stop"
          $expected = $env:TARGET_REF.Trim().ToLowerInvariant()
          if ($expected -notmatch '^[0-9a-f]{40}$') {
            throw "target_ref must be an exact 40-character commit SHA"
          }
          $actual = (git rev-parse HEAD).Trim().ToLowerInvariant()
          if ($actual -ne $expected) {
            throw "Checked out SHA $actual differs from target_ref $expected"
          }
          Write-Host "Exact head verified: $actual"

      - name: Verify Python 3.14
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $version = python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
          Write-Host "Python: $version"
          if (-not $version.StartsWith("3.14.")) {
            throw "Phase 7 policy smoke requires Python 3.14.x. Found $version"
          }

      - name: Install project
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Run Ruff lint
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m ruff check .

      - name: Run Ruff format check
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m ruff format --check .

      - name: Run complete test suite
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m pytest -q

      - name: Run Phase 7 policy smoke
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $report = Join-Path $env:RUNNER_TEMP "phase7-policy-$env:GITHUB_RUN_ID.json"
          Remove-Item -Force $report -ErrorAction SilentlyContinue
          python -m ai_service_desk policy-smoke `
            --cases tests/fixtures/phase7_policy_cases.jsonl `
            --report "$report"
```

The exact-head comparison is self-contained in the workflow. It maps the `workflow_dispatch` input explicitly into `TARGET_REF`, requires that input to be a 40-character commit SHA, and compares `git rev-parse HEAD` directly with that received value before Python installation or any test execution. It does not depend on `PHASE7_CANDIDATE_SHA` or any externally defined environment variable.

The existing `ollama` runner label only selects the already homologated Dell runner. This workflow contains no Ollama command, URL or model call.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m pytest tests/test_policy_cli.py tests/test_workflows.py -v
python -m ai_service_desk policy-smoke --cases tests/fixtures/phase7_policy_cases.jsonl --report .phase7-policy-smoke-local.json
rm -f .phase7-policy-smoke-local.json
python -m ruff check src/ai_service_desk/cli.py tests/test_policy_cli.py tests/test_workflows.py
python -m ruff format --check src/ai_service_desk/cli.py tests/test_policy_cli.py tests/test_workflows.py
git add src/ai_service_desk/cli.py tests/test_policy_cli.py tests/test_workflows.py .github/workflows/phase7-policy-smoke.yml
git commit -m "feat: add phase 7 policy smoke cli"
```

---

# Gate 10 - Operational Documentation and Focused Regressions

### Task 10: Document the exact Phase 7 operating boundary

**Files:** create `docs/policy/phase-7.md`, create `tests/test_phase7_docs.py`, modify `README.md`.

**Interfaces:**
- Produces operator instructions for local smoke and Dell homologation.
- Documentation must not claim request creation, approval or execution capability.

- [ ] **Step 1: Write RED documentation tests**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "policy" / "phase-7.md"
README = ROOT / "README.md"


def test_phase7_operational_doc_locks_policy_boundary() -> None:
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "PROBLEMA_ACESSO",
        "CDM_ACCESS_REQUEST",
        "ROLE_CONFLICT",
        "ROLE_PRIVILEGED_INTENT_MATCH",
        "ROLE_PRIVILEGED_NOMINAL_MATCH",
        "ROLE_SOLICITANTE_EXPLICIT",
        "ROLE_PRIVILEGE_AMBIGUOUS",
        "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE",
        "ROLE_UNRESOLVED",
        "POLICY_NOT_FOUND",
        "POLICY_RULE_INVALID",
        "POLICY_RULE_CONFLICT",
        "CONTEXT_NOT_CDM_ACCESS_REQUEST",
        "AREA_MATCH_REVENDA",
        "PURPOSE_MATCH_MATERIAL_REQUEST",
        "python -m ai_service_desk policy-smoke",
        "319",
    ):
        assert required in text


def test_readme_links_phase7_operational_doc() -> None:
    text = README.read_text(encoding="utf-8")
    assert "docs/policy/phase-7.md" in text
```

Gate 10 contributes 2 collected cases.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_phase7_docs.py -v
```

Expected: operational doc missing.

- [ ] **Step 3: Create `docs/policy/phase-7.md` with these exact sections**

```text
# Fase 7: Policy Engine

## Escopo
## Contratos
## Normalizacao de role
## Preparacao CDM-specific
## Policy fail-closed
## Confidence separado
## Provenance da Fase 6
## CLI
## Privacidade
## Fronteira com a Fase 8
## Homologacao Dell
## Baseline de regressao
```

The CLI section must show exactly:

```powershell
$report = Join-Path $env:TEMP "phase7-policy-smoke-manual.json"
Remove-Item -Force $report -ErrorAction SilentlyContinue

python -m ai_service_desk policy-smoke `
  --cases tests/fixtures/phase7_policy_cases.jsonl `
  --report "$report"

$LASTEXITCODE
```

Expected console evidence:

```text
POLICY SMOKE OK
Casos sinteticos: 15
0
```

The document must state this flow explicitly:

```text
SessionIdentity -> TriageState ANSWERED -> ACTION_PROPOSAL descriptor -> AccessRequestPreparation
READY -> AccessRequestContext -> PolicyEngine + ConfidenceAssessment
NEEDS_CLARIFICATION -> no PolicyDecision and no ConfidenceAssessment
```

It must list all seven preparation reason codes, the four CDM policy rows, `DENY / POLICY_NOT_FOUND` for a valid unknown policy, runtime `PolicyRule` validation with `PolicyConfigurationError / POLICY_RULE_INVALID`, `PolicyConfigurationError / POLICY_RULE_CONFLICT` for duplicate valid rule keys, exact confidence reason-code order, provenance fields, zero external calls and the Phase 8 boundary.

The Dell section must instruct the operator to dispatch `.github/workflows/phase7-policy-smoke.yml` with `target_ref` equal to the exact 40-character candidate SHA and explain that the workflow itself compares that input with `git rev-parse HEAD` immediately after checkout. It does not use an external `PHASE7_CANDIDATE_SHA` variable, run `doctor`, build a knowledge index or start Ollama.

- [ ] **Step 4: Update README minimally**

Add a Phase 7 line linking `docs/policy/phase-7.md` and stating that Phase 7 decides policy and confidence only. It must not claim that access is created, approved or executed.

- [ ] **Step 5: Run focused regressions and protected-file checks**

```bash
python -m pytest tests/test_phase7_docs.py tests/test_workflows.py tests/test_policy_cli.py -v
python -m pytest tests/engine/test_classification.py tests/engine/test_triage.py tests/engine/test_playbook_resolution.py -v
git diff --exit-code 7e7142f757f66585f240e16781accd044f31eb6f -- src/ai_service_desk/engine/triage.py src/ai_service_desk/engine/knowledge.py src/ai_service_desk/engine/knowledge_retrieval.py src/ai_service_desk/engine/playbook.py src/ai_service_desk/engine/playbook_resolution.py knowledge/phase4_synthetic_faq.jsonl playbooks/phase6_synthetic_playbooks.jsonl
python -m ruff check .
python -m ruff format --check .
```

Expected protected-file diff: empty.

- [ ] **Step 6: Commit docs and operational regression contract**

```bash
git add docs/policy/phase-7.md tests/test_phase7_docs.py README.md
git commit -m "docs: add phase 7 policy operations"
```

---

# Gate 11 - Full Ruff, Quantitative Suite, Privacy and Dell Homologation

### Task 11: Exact-head verification gate

**Do not merge in this task. Do not change production behavior to make verification pass. A failure returns to the owning RED/GREEN gate.**

- [ ] **Step 1: Verify recorded execution lineage and final scope against the regression baseline**

Use the `EXECUTION_START_HEAD` captured at implementation handoff. Do not derive or recompute it from commit order.

```bash
REGRESSION_BASELINE=7e7142f757f66585f240e16781accd044f31eb6f
test -n "$EXECUTION_START_HEAD"
git merge-base --is-ancestor "$REGRESSION_BASELINE" "$EXECUTION_START_HEAD"
git merge-base --is-ancestor "$EXECUTION_START_HEAD" HEAD
git diff --name-status "$REGRESSION_BASELINE"...HEAD
printf 'execution_start=%s\nregression_baseline=%s\nfinal_head=%s\n' \
  "$EXECUTION_START_HEAD" \
  "$REGRESSION_BASELINE" \
  "$(git rev-parse HEAD)"
```

`EXECUTION_START_HEAD` is the exact final plan head explicitly approved by the user and recorded before Gate 1. It is never the first commit after the regression baseline unless those commits happen to be identical by history, and it is never recomputed from `git log`. The regression baseline is only the reference for historical comparison and test preservation.

Allowed implementation files are exactly the Phase 7 file map in this plan plus the plan/spec documentary refinements already present at execution start. Any other changed production or protected file stops the gate for review.

- [ ] **Step 2: Prove existing tests were not removed or skipped**

Existing test files intentionally modified by this plan are only:

```text
tests/engine/test_classification.py
tests/test_workflows.py
```

Both edits must be additive-only:

```bash
git diff --numstat 7e7142f757f66585f240e16781accd044f31eb6f -- tests/engine/test_classification.py tests/test_workflows.py
```

Expected: deletion column is `0` for both files.

No test file may be deleted:

```bash
git diff --diff-filter=D --name-only 7e7142f757f66585f240e16781accd044f31eb6f -- tests
```

Expected: no output.

Scan added lines for skip markers:

```bash
git diff --unified=0 7e7142f757f66585f240e16781accd044f31eb6f -- tests | grep -E '^\+.*(pytest\.mark\.skip|pytest\.skip|unittest\.skip)' || true
```

Expected: no matches.

- [ ] **Step 3: Run full Ruff gates**

```bash
python -m ruff check .
python -m ruff format --check .
```

Require zero lint errors and zero format drift.

- [ ] **Step 4: Collect and run the complete suite**

```bash
python -m pytest --collect-only -q
python -m pytest -q
```

Requirements:

```text
baseline = 319
planned Phase 7 minimum = 105 new collected cases
initial hard floor = 424
```

If more than 105 new cases were added, increase the floor one-for-one. A smaller green suite is not acceptable.

- [ ] **Step 5: Compare baseline and final collected node IDs, not only counts**

From repository root on a Unix-like executor:

```bash
BASELINE_DIR="../ai-service-desk-phase7-baseline"
rm -rf "$BASELINE_DIR"
git worktree add --detach "$BASELINE_DIR" 7e7142f757f66585f240e16781accd044f31eb6f
(
  cd "$BASELINE_DIR"
  PYTHONPATH=src python -m pytest --collect-only -q > /tmp/phase7-baseline-nodeids.txt
)
PYTHONPATH=src python -m pytest --collect-only -q > /tmp/phase7-final-nodeids.txt
python - <<'PY'
from pathlib import Path


def nodeids(path: str) -> set[str]:
    return {
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if "::" in line
    }

baseline = nodeids("/tmp/phase7-baseline-nodeids.txt")
final = nodeids("/tmp/phase7-final-nodeids.txt")
missing = sorted(baseline - final)
new = sorted(final - baseline)
print(f"baseline_nodeids={len(baseline)}")
print(f"final_nodeids={len(final)}")
print(f"new_nodeids={len(new)}")
if len(baseline) != 319:
    raise SystemExit(f"expected baseline 319, got {len(baseline)}")
if missing:
    raise SystemExit("missing baseline nodeids:\n" + "\n".join(missing))
if len(new) < 105:
    raise SystemExit(f"expected at least 105 new Phase 7 nodeids, got {len(new)}")
if len(final) < 424:
    raise SystemExit(f"expected at least 424 final nodeids, got {len(final)}")
PY
git worktree remove "$BASELINE_DIR"
```

This detached worktree exists only to inspect the regression baseline. It must never replace, reset or move the implementation worktree. This check proves the old 319-node set is a subset of the final suite and records the actual number of newly collected tests.

- [ ] **Step 6: Run zero-execution scans on Phase 7 production modules**

```bash
git grep -n -E "requests|httpx|urllib\.request|subprocess|Popen|os\.system|shell=True|OllamaClient|LocalEmbedder|CDMAdapter|ExecutionEngine" -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py
```

Expected: no matches.

The smoke module may use only local file/report utilities and existing pure domain functions. It must not match network or executor markers:

```bash
git grep -n -E "requests|httpx|urllib\.request|subprocess|Popen|os\.system|shell=True|OllamaClient|LocalEmbedder|CDMAdapter|ExecutionEngine" -- src/ai_service_desk/engine/policy_smoke.py
```

Expected: no matches.

- [ ] **Step 7: Scan for forbidden Phase 7 domain expansion**

```bash
git grep -n -E "REQUEST_ACCESS|AUTO_APPROVE|request_id|PENDING_APPROVAL|CDMAdapter|ExecutionEngine" -- src/ai_service_desk/engine/access_request.py src/ai_service_desk/engine/policy.py src/ai_service_desk/engine/confidence.py src/ai_service_desk/engine/policy_smoke.py
```

Expected: no matches. `CDM_ACCESS_REQUEST` remains allowed because it is the Phase 6 capability, not a new intent.

- [ ] **Step 8: Privacy scan synthetic fixture and generated-file tracking**

```bash
git grep -n -E "juparana|@juparana|base_ti_preparada|ticket_id|hostname|credential|password|secret" -- tests/fixtures/phase7_policy_cases.jsonl
```

Expected: no matches.

Every fixture email must end in `@example.invalid`:

```bash
python - <<'PY'
import json
from pathlib import Path

rows = [
    json.loads(line)
    for line in Path("tests/fixtures/phase7_policy_cases.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
assert len(rows) == 15
assert all(row["email"].endswith("@example.invalid") for row in rows)
assert all(row["username"].startswith("synthetic.") for row in rows)
print("phase7 synthetic fixture privacy: OK")
PY
```

No generated smoke report may be tracked:

```bash
git ls-files | grep -E "phase7.*report.*\.json|phase7-policy-smoke.*\.json" || true
```

Expected: no generated report file.

- [ ] **Step 9: Verify protected Phase 4, 5 and 6 files are unchanged**

```bash
git diff --exit-code 7e7142f757f66585f240e16781accd044f31eb6f -- src/ai_service_desk/engine/triage.py src/ai_service_desk/engine/knowledge.py src/ai_service_desk/engine/knowledge_retrieval.py src/ai_service_desk/engine/playbook.py src/ai_service_desk/engine/playbook_resolution.py knowledge/phase4_synthetic_faq.jsonl playbooks/phase6_synthetic_playbooks.jsonl
```

Expected: empty diff.

For `classification.py`, inspect the only allowed production delta:

```bash
git diff 7e7142f757f66585f240e16781accd044f31eb6f -- src/ai_service_desk/engine/classification.py
```

Expected: only the `"CDM": ("cdm",),` mapping entry.

- [ ] **Step 10: Run exact-head functional smoke locally**

```powershell
$head = (git rev-parse HEAD).Trim()
Write-Host "Phase 7 candidate: $head"
$report = Join-Path $env:TEMP "phase7-policy-smoke-manual.json"
Remove-Item -Force $report -ErrorAction SilentlyContinue

python -m ai_service_desk policy-smoke `
  --cases tests/fixtures/phase7_policy_cases.jsonl `
  --report "$report"

$LASTEXITCODE
```

Required console evidence:

```text
POLICY SMOKE OK
Casos sinteticos: 15
0
```

Do not print the report body.

- [ ] **Step 11: Dell homologation through the exact-head workflow**

Capture the immutable final candidate SHA before dispatch:

```powershell
$candidate = (git rev-parse HEAD).Trim().ToLowerInvariant()
if ($candidate -notmatch '^[0-9a-f]{40}$') {
    throw "Candidate must be an exact 40-character commit SHA"
}
Write-Host "Dispatch phase7-policy-smoke.yml with target_ref=$candidate"
```

Dispatch `.github/workflows/phase7-policy-smoke.yml` using exactly the printed `$candidate` as the `workflow_dispatch` input `target_ref`.

The workflow itself, immediately after `actions/checkout`, must:

```text
receive target_ref
require a 40-character commit SHA
read git rev-parse HEAD
compare actual HEAD directly with target_ref
fail before Python setup if they differ
```

No `PHASE7_CANDIDATE_SHA` environment variable is set or expected outside the workflow. The only SHA source for the workflow comparison is the explicitly propagated `workflow_dispatch` input.

Required Dell workflow evidence on that same run:

```text
Exact head verified: <candidate SHA>
Python 3.14.x
Ruff check exit code 0
Ruff format check exit code 0
pytest all tests pass with collected count at or above 319 plus every new Phase 7 test
POLICY SMOKE OK
Casos sinteticos: 15
0
```

The Dell run must not start Ollama, run `doctor`, build a knowledge index or call any URL.

- [ ] **Step 12: Final self-review against the approved spec and plan refinements**

Review each item and record pass/fail in the review evidence:

```text
1. Implementation started from the final plan head approved by the user, not by checkout/reset to the regression baseline.
2. Regression baseline remains exactly 7e7142f757f66585f240e16781accd044f31eb6f for comparisons and node-ID preservation.
3. prepare_access_request is CDM-specific and rejects future system/capability before role normalization.
4. SessionIdentity is the only identity source and chat spoofing tests pass.
5. RoleNormalizer uses closed lexical precedence and all seven reason codes exactly.
6. Purpose is problem_text.strip() with no LLM rewrite.
7. Full Phase 6 provenance survives in AccessRequestContext.
8. ACTION_PROPOSAL type is validated and not duplicated in context.
9. PolicyEngine validates context independently on every evaluate call.
10. assess_confidence validates context independently on every call.
11. Every PolicyRule is runtime-validated before any index entry exists.
12. Invalid PolicyRule raises POLICY_RULE_INVALID and prevents engine construction.
13. A sequence containing an invalid rule and duplicate valid key fails as POLICY_RULE_INVALID before conflict indexing.
14. Duplicate valid policy key raises POLICY_RULE_CONFLICT before any decision.
15. Unknown valid policy context returns DENY / POLICY_NOT_FOUND.
16. Invalid context raises domain validation error rather than POLICY_NOT_FOUND.
17. Confidence CDM codes are always ordered area then purpose.
18. Valid non-CDM confidence is exactly LOW / CONTEXT_NOT_CDM_ACCESS_REQUEST.
19. HIGH never grants approval and LOW never denies SOLICITANTE.
20. Privileged roles remain DENY under perfect confidence.
21. No LLM, HTTP, executor, CDM adapter, persistence, approval state or request identifier exists.
22. Homologated Phase 4, 5 and 6 protected files and fixtures are unchanged.
23. Baseline 319 node IDs are all still present.
24. Final collected count is at least 319 plus every newly added Phase 7 test, with planned minimum 424.
25. Synthetic smoke is 15/15 and report privacy checks pass.
26. Dell workflow verifies git rev-parse HEAD against the received target_ref inside the workflow before test execution.
27. Dell workflow does not depend on PHASE7_CANDIDATE_SHA or another unpropagated external variable.
```

- [ ] **Step 13: Prepare review evidence without merging**

```bash
git status --short
git rev-parse HEAD
git log --oneline 7e7142f757f66585f240e16781accd044f31eb6f..HEAD
git diff --stat 7e7142f757f66585f240e16781accd044f31eb6f...HEAD
```

Report the execution-start head recorded at handoff, regression baseline, exact final SHA, commit list, collected test count, new node ID count, Ruff results, smoke 15/15, privacy scan, protected-file equality and Dell exact-head result. Do not merge until explicit user approval in a later step.

---

## Gate Evidence Required for Review

```text
Gate 1: CDM alias observed RED -> strictly additive GREEN; existing aliases preserved
Gate 2: SessionIdentity and structural context validation RED -> GREEN
Gate 3: closed RoleNormalizer precedence and seven reason codes RED -> GREEN
Gate 4: CDM-specific preparation, full Phase 6 provenance and real descriptor RED -> GREEN
Gate 5: runtime PolicyRule validation, POLICY_RULE_INVALID, CDM matrix, POLICY_NOT_FOUND and POLICY_RULE_CONFLICT RED -> GREEN
Gate 6: exact confidence composition/order and independent validation RED -> GREEN
Gate 7: spoofing, fail-closed invariants and zero-external-execution RED -> GREEN
Gate 8: exact 15-case synthetic smoke RED -> GREEN
Gate 9: policy-smoke CLI and workflow-owned exact-head Dell verification RED -> GREEN
Gate 10: operational docs, focused regressions and protected-file checks RED -> GREEN
Gate 11: full Ruff, complete suite, baseline-node subset, privacy, zero-execution scan and exact-head Dell homologation
```

---

## Definition of Done for Implementation Review

Phase 7 implementation is ready for review only when all of the following are evidenced on the same final SHA:

- implementation began from the final plan head explicitly approved by the user;
- the implementation worktree was never reset or checked out to the regression baseline to begin work;
- `7e7142f757f66585f240e16781accd044f31eb6f` remains the fixed regression baseline for historical comparison only;
- `CDM` alias support is the only behavior change in `classification.py`;
- `triage.py` is unchanged;
- Phase 4 knowledge code and fixture are unchanged;
- Phase 6 playbook code and fixture are unchanged;
- `SessionIdentity` is immutable and validated;
- `AccessRequestContext` is immutable, structurally validated and preserves all required provenance;
- role normalization depends only on request text and uses the exact closed precedence;
- all seven preparation reason codes are present and no eighth preparation reason code exists;
- unsupported system, intent or capability is rejected before the CDM role normalizer runs;
- `prepare_access_request(...)` creates contexts only for CDM `PROBLEMA_ACESSO` with `CDM_ACCESS_REQUEST`;
- the real Phase 6 `action_proposal_descriptor(...)` is used in integration tests and smoke construction;
- `PolicyEngine` has only in-code rules, no policy catalog;
- every `PolicyRule` is runtime-validated before indexing;
- invalid rule configuration fails with `PolicyConfigurationError / POLICY_RULE_INVALID`;
- duplicate valid policy keys fail with `PolicyConfigurationError / POLICY_RULE_CONFLICT`;
- invalid configuration is detected before duplicate-key indexing;
- `PolicyEngine.evaluate(...)` validates context independently;
- unknown valid policy keys return deterministic `DENY / POLICY_NOT_FOUND`;
- structural corruption raises an explicit validation error;
- `assess_confidence(...)` validates context independently;
- CDM confidence reason codes always contain exactly two items, area first and purpose second;
- valid non-CDM confidence returns the single context reason;
- policy never consumes confidence and confidence never consumes policy;
- `SOLICITANTE + HIGH` and `SOLICITANTE + LOW` both produce `REQUIRE_APPROVAL`;
- privileged roles produce `DENY`, including `SUPERADMIN` with Revenda area and matching material purpose;
- chat text cannot overwrite trusted identity;
- Phase 7 production modules have zero HTTP, Ollama, embedding, subprocess, executor or CDM calls;
- no request persistence, human approval state or request identifier is implemented;
- official synthetic smoke is exactly 15/15;
- smoke report contains no identity, raw problem text, purpose, capability, corporate data or generated external artifacts;
- all 319 baseline test node IDs remain present;
- final collected suite is at least the baseline plus every newly added Phase 7 test, with initial planned floor of 424 before optional extra tests;
- complete pytest passes;
- Ruff lint and format checks pass;
- Dell workflow accepts only exact candidate SHA input for `target_ref` and verifies it against `git rev-parse HEAD` inside the workflow immediately after checkout;
- Dell homologation passes on the exact final candidate SHA without `PHASE7_CANDIDATE_SHA` or another external comparison variable;
- final review evidence is prepared without merging.