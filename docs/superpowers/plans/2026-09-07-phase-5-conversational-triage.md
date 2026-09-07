# Phase 5 Conversational Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a short, deterministic, multi-turn triage state machine that gathers only missing context and then reuses Phase 4 APPROVED knowledge retrieval without changing existing Phase 1 to 4 behavior.

**Architecture:** Extend `KnowledgeEngine` additively with `search_classified()` and `available_systems()`, then add a pure `TriageState` plus `TriageEngine.step(state, message) -> (new_state, result)`. The triage layer classifies each user message at most once, performs deterministic state merge and clarification rules, and calls the existing Phase 4 retrieval only after context is sufficient. It never reads knowledge index internals directly, never uses historical retrieval as official guidance, and never persists transcript or approved answers in state.

**Tech Stack:** Python 3.14, dataclasses, existing `classify_ticket`, existing `KnowledgeEngine`, NumPy/Pandas only through existing knowledge retrieval, argparse CLI, pytest, Ruff, GitHub Actions on the existing Dell self-hosted Windows/Ollama runner.

**Spec:** `docs/superpowers/specs/2026-09-07-phase-5-conversational-triage-design.md`

## Global Constraints

- Base implementation from `main` commit `491e5dd5f79dec8ff9a192a4929b48209956be3a`; approved Phase 5 spec head is `a540c1707663d3d86693085046e4c2099d386e39`.
- `KnowledgeEngine.search(text)` remains public and behaviorally backward compatible.
- `KnowledgeEngine.search_classified(text, classification)` is strictly additive and must reuse the same Phase 4 gates and result contract.
- `KnowledgeEngine.available_systems(intent)` is the only availability interface the triage layer may use. `TriageEngine` must not read `KnowledgeEngine.df`, `documents.jsonl`, embeddings, manifest, provenance, or matrix internals.
- `MAX_USER_TURNS = 3` and `MAX_CLARIFICATIONS = 2` exactly.
- The third accepted user turn is processed fully and may return `KNOWLEDGE_FOUND`; a fourth turn is rejected before classification.
- Each user message is classified at most once. No second classification occurs when entering knowledge retrieval.
- Merge precedence and state-reset rules must follow the approved spec exactly.
- System correction parsing is conservative and only recognizes an unambiguous `nao e <known canonical alias>, e <known canonical alias>` structure.
- `confidence` is metadata only and never gates transitions.
- The knowledge query contains only current user-provided `problem_text` plus resolved user-provided system context when needed. Never add intent labels, knowledge tags, synonyms, titles, answers, historical text, or semantic booster phrases.
- Knowledge threshold remains exactly `0.65`; triage has no alternate threshold.
- `TriageState` never stores transcript, assistant messages, knowledge answer, article text, embeddings, scores, historical ticket content, historical `ticket_id`, or chain-of-thought.
- Only `APPROVED` knowledge may produce official guidance. DRAFT and RETIRED content never appears as a response.
- All new fixtures and conversations committed to Git are synthetic.
- No ticket creation, playbooks, policy engine, machine execution, frontend, database, global session cache, or persistence layer in Phase 5.
- Do not modify `src/ai_service_desk/engine/classification.py`, `src/ai_service_desk/engine/retrieval.py`, or `src/ai_service_desk/engine/index.py` unless a reproducible blocking test is first documented with technical cause, smallest possible change, and regression risk. The approved design expects no such changes.
- `src/ai_service_desk/engine/knowledge.py` should also remain unchanged unless a reproducible blocker proves otherwise.
- The 177 tests present at the Phase 5 base remain a mandatory regression gate, in addition to all new Phase 5 tests.

## File Map

**Modify** `src/ai_service_desk/engine/knowledge_retrieval.py`
- Keep `KnowledgeEngine.search(text)` behavior unchanged.
- Add `search_classified(text, classification)`.
- Add `available_systems(intent)`.

**Create** `src/ai_service_desk/engine/triage.py`
- Own `TriageState`, limits, conservative system correction parsing, deterministic message categorization, state merge, query construction, transition decisions, and `TriageEngine`.

**Create** `src/ai_service_desk/engine/triage_smoke.py`
- Execute the 10 approved synthetic multi-turn scenarios and write only safe aggregate metadata.

**Modify** `src/ai_service_desk/cli.py`
- Add only the Phase 5 smoke entrypoint needed for local homologation. Do not add a persistent chat/session store.

**Create** `tests/engine/test_triage.py`
- Unit-test state, merge precedence, correction parsing, limits, query construction, transitions, session isolation, and knowledge handoff using deterministic control doubles.

**Modify** `tests/engine/test_knowledge_retrieval.py`
- Prove `search()` compatibility and the new availability interface.

**Create** `tests/engine/test_triage_smoke.py`
- Prove smoke report privacy and 10-case execution using fakes.

**Create** `tests/test_triage_cli.py`
- Prove CLI wiring and safe output without requiring real Ollama.

**Create** `tests/fixtures/phase5_triage_conversations.jsonl`
- Store only the 10 approved synthetic conversations and expected statuses/reasons/knowledge IDs.

**Create** `.github/workflows/phase5-triage-smoke.yml`
- Manual Dell/Ollama homologation using only synthetic knowledge and synthetic conversations.

**Modify** `tests/test_workflows.py`
- Enforce manual/self-hosted/loopback/non-exporting workflow policy.

**Create** `docs/triage/phase-5.md`
- Operational description of state, limits, privacy, and local smoke.

**Modify** `README.md`
- Add Phase 5 summary and commands without changing prior phase semantics.

---

### Task 1: Add the backward-compatible KnowledgeEngine seam

**Files:**
- Modify: `src/ai_service_desk/engine/knowledge_retrieval.py`
- Test: `tests/engine/test_knowledge_retrieval.py`

**Interfaces:**
- Consumes: existing `KnowledgeEngine.search(text: str) -> dict`, `retrieve_knowledge(...)`, `classify_ticket(...)`, and validated APPROVED knowledge already loaded into `self.df`.
- Produces: `KnowledgeEngine.search_classified(text: str, classification: TicketClassification) -> dict` and `KnowledgeEngine.available_systems(intent: str) -> tuple[str, ...]`.

- [ ] **Step 1: Write failing equivalence and availability tests**

Add focused tests that use the existing `FakeClient`, `FakeEmbedder`, and synthetic knowledge source. The equivalence test must ensure the old entrypoint still classifies exactly once while the new entrypoint classifies zero times and produces the same result for the same `TicketClassification`.

```python
def test_search_and_search_classified_are_equivalent_for_same_classification(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    root = tmp_path / "index"
    build_knowledge_index(write_source(tmp_path / "knowledge.jsonl"), root, embedder, batch_size=1)
    embedder.calls.clear()

    client = FakeClient(system="CIGAM", intent="PROBLEMA_ACESSO")
    engine = KnowledgeEngine(root, client, embedder)
    expected_classification = TicketClassification("PROBLEMA_ACESSO", "CIGAM", {}, 0.9)

    via_search = engine.search("Nao consigo acessar o CIGAM")
    calls_after_search = client.chat_calls
    embedder.calls.clear()

    via_classified = engine.search_classified(
        "Nao consigo acessar o CIGAM",
        expected_classification,
    )

    assert via_classified == via_search
    assert calls_after_search == 1
    assert client.chat_calls == 1
    assert len(embedder.calls) == 1


def test_available_systems_returns_sorted_unique_metadata_only(tmp_path: Path) -> None:
    engine = build_engine_with_articles(
        tmp_path,
        [
            article(system="SIAGRI", intent="PROBLEMA_ACESSO", knowledge_id="KB-S1"),
            article(system="CIGAM", intent="PROBLEMA_ACESSO", knowledge_id="KB-C1"),
            article(system="CIGAM", intent="PROBLEMA_ACESSO", knowledge_id="KB-C2"),
            article(system="", intent="PROBLEMA_IMPRESSAO", knowledge_id="KB-P1"),
        ],
    )

    assert engine.available_systems("PROBLEMA_ACESSO") == ("CIGAM", "SIAGRI")
    assert engine.available_systems("PROBLEMA_IMPRESSAO") == ("",)
    assert engine.available_systems("ORIENTACAO") == ()
```

If convenient, add a tiny local test helper `build_engine_with_articles()` in this test module only. Do not move production data access into triage.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py -q
```

Expected: existing tests pass, new tests fail because `search_classified` and `available_systems` do not exist yet.

- [ ] **Step 3: Implement the smallest additive KnowledgeEngine change**

Refactor only the class methods. Preserve `retrieve_knowledge()` and all gates unchanged.

```python
class KnowledgeEngine:
    # existing __init__ unchanged

    def available_systems(self, intent: str) -> tuple[str, ...]:
        values = {
            str(value)
            for value in self.df.loc[self.df["intent"].astype(str).eq(intent), "system"].tolist()
        }
        return tuple(sorted(values))

    def search_classified(self, text: str, classification: TicketClassification) -> dict:
        pool, reason = _eligible_pool(self.df, classification, text)
        if reason != "MATCH":
            return _base_result(classification, self.threshold, reason)
        if not len(pool):
            return _base_result(classification, self.threshold, "NO_ELIGIBLE_KNOWLEDGE")
        query = self.embedder.embed([text])[0]
        return retrieve_knowledge(
            self.df,
            self.matrix,
            query,
            classification,
            text,
            threshold=self.threshold,
        )

    def search(self, text: str) -> dict:
        classification = classify_ticket(text, self.client.chat)
        return self.search_classified(text, classification)
```

Do not change `_eligible_pool`, `retrieve_knowledge`, `format_knowledge_result`, threshold defaults, result shape, or reasons.

- [ ] **Step 4: Run the Phase 4 knowledge retrieval tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py -q
```

Expected: all existing Phase 4 retrieval tests plus the new equivalence/availability tests pass.

- [ ] **Step 5: Run the broader Phase 4 knowledge regression gate**

Run:

```bash
pytest tests/engine/test_knowledge.py tests/engine/test_knowledge_retrieval.py tests/engine/test_knowledge_smoke.py tests/test_knowledge_cli.py -q
```

Expected: all Phase 4 knowledge tests pass unchanged.

- [ ] **Step 6: Commit the additive seam**

```bash
git add src/ai_service_desk/engine/knowledge_retrieval.py tests/engine/test_knowledge_retrieval.py
git commit -m "feat: add classified knowledge search seam"
```

---

### Task 2: Define TriageState and deterministic message evidence helpers

**Files:**
- Create: `src/ai_service_desk/engine/triage.py`
- Create: `tests/engine/test_triage.py`

**Interfaces:**
- Consumes: `TicketClassification`, `SYSTEM_ALIASES`, `explicit_systems`, and `normalize_text`.
- Produces: `TriageState`, `TurnEvidence`, `MAX_USER_TURNS`, `MAX_CLARIFICATIONS`, `new_triage_state(session_id)`, `_parse_system_correction(text)`, `_is_short_system_reply(...)`, and `_analyze_turn(...)`.

- [ ] **Step 1: Write failing state contract tests**

Start `tests/engine/test_triage.py` with tests proving the state is small, serializable, session-bound, and excludes forbidden data by schema rather than convention.

```python
from dataclasses import asdict

from ai_service_desk.engine.triage import (
    MAX_CLARIFICATIONS,
    MAX_USER_TURNS,
    TriageState,
    new_triage_state,
)


def test_new_state_has_exact_small_schema() -> None:
    state = new_triage_state("session-a")
    assert asdict(state) == {
        "version": 1,
        "session_id": "session-a",
        "status": "ACTIVE",
        "turn_count": 0,
        "clarification_count": 0,
        "problem_text": "",
        "intent": "",
        "system": "",
        "entities": {},
        "confidence": 0.0,
        "pending_field": "",
        "asked_fields": (),
    }
    serialized_keys = set(asdict(state))
    for forbidden in ("transcript", "messages", "answer", "ticket_id", "score", "embedding"):
        assert forbidden not in serialized_keys


def test_phase5_limits_are_exact() -> None:
    assert MAX_USER_TURNS == 3
    assert MAX_CLARIFICATIONS == 2
```

- [ ] **Step 2: Write failing conservative correction parser tests**

```python
def test_correction_parser_accepts_only_unique_known_alias_pair() -> None:
    assert _parse_system_correction("Nao e CIGAM, e SIAGRI") == ("CIGAM", "SIAGRI")


@pytest.mark.parametrize(
    "text",
    [
        "CIGAM e SIAGRI",
        "talvez SIAGRI em vez de CIGAM",
        "nao e CIGAM, e XYZ",
        "nao e XYZ, e SIAGRI",
        "nao e CIGAM, e SIAGRI e TEAMS",
        "prefiro SIAGRI",
    ],
)
def test_correction_parser_rejects_ambiguous_or_unknown_language(text: str) -> None:
    assert _parse_system_correction(text) is None
```

- [ ] **Step 3: Write failing short-system categorization tests**

The helper must treat a slot reply as slot-only only while `pending_field == "system"` and under the exact cases in the spec.

```python
def test_short_system_reply_is_slot_only_for_known_alias() -> None:
    classification = TicketClassification("OUTRO", "CIGAM", {}, 0.4)
    assert _is_short_system_reply("CIGAM", "system", classification)
    assert not _is_short_system_reply("CIGAM", "", classification)


def test_short_unknown_literal_reply_can_remain_slot_only() -> None:
    classification = TicketClassification("OUTRO", "XYZ", {}, 0.4)
    assert _is_short_system_reply("XYZ", "system", classification)
    assert _is_short_system_reply("sistema XYZ", "system", classification)
```

- [ ] **Step 4: Run focused tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: import or attribute failures because the triage module does not exist yet.

- [ ] **Step 5: Implement the state and transient evidence types**

Create `src/ai_service_desk/engine/triage.py` with the exact persisted state fields from the spec and a separate non-persisted `TurnEvidence` for current-turn ambiguity/correction facts.

```python
from dataclasses import dataclass, replace
from typing import Callable

from ai_service_desk.engine.classification import SYSTEM_ALIASES, explicit_systems
from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_text

MAX_USER_TURNS = 3
MAX_CLARIFICATIONS = 2


@dataclass(frozen=True)
class TriageState:
    version: int
    session_id: str
    status: str
    turn_count: int
    clarification_count: int
    problem_text: str
    intent: str
    system: str
    entities: dict[str, str]
    confidence: float
    pending_field: str
    asked_fields: tuple[str, ...]


@dataclass(frozen=True)
class TurnEvidence:
    kind: str
    explicit_systems: tuple[str, ...]
    correction: tuple[str, str] | None
    classification: TicketClassification


def new_triage_state(session_id: str) -> TriageState:
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 120:
        raise ValueError("session_id invalido.")
    return TriageState(1, session_id, "ACTIVE", 0, 0, "", "", "", {}, 0.0, "", ())
```

Keep `TurnEvidence` transient only. It must never be nested inside `TriageState` or serialized into smoke reports.

- [ ] **Step 6: Implement exact alias matching and correction parsing**

Build a canonical exact-alias map from existing `SYSTEM_ALIASES`. Match full normalized alias tokens only. Do not accept unknown systems in the correction parser.

```python
def _canonical_for_exact_alias(value: str) -> str | None:
    wanted = normalize_text(value).strip()
    matches = {
        canonical
        for canonical, aliases in SYSTEM_ALIASES.items()
        if wanted in {normalize_text(canonical), *(normalize_text(alias) for alias in aliases)}
    }
    return next(iter(matches)) if len(matches) == 1 else None
```

Use one conservative regex for normalized `nao e A, e B` structure, then require both captured values to resolve uniquely via `_canonical_for_exact_alias` and require the full message to contain no third explicit known system.

- [ ] **Step 7: Implement deterministic message categorization**

`_analyze_turn()` receives the single `TicketClassification` already produced for the message. It must not call an LLM.

```python
def _analyze_turn(
    state: TriageState,
    message: str,
    classification: TicketClassification,
) -> TurnEvidence:
    correction = _parse_system_correction(message)
    systems = tuple(explicit_systems(message))
    if correction is not None:
        kind = "SYSTEM_CORRECTION"
    elif _is_short_system_reply(message, state.pending_field, classification):
        kind = "SYSTEM_SLOT"
    else:
        kind = "SUBSTANTIVE"
    return TurnEvidence(kind, systems, correction, classification)
```

- [ ] **Step 8: Run focused state/parser tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: all state, limit, correction-parser, and message-categorization tests pass.

- [ ] **Step 9: Commit the state foundation**

```bash
git add src/ai_service_desk/engine/triage.py tests/engine/test_triage.py
git commit -m "feat: add phase 5 triage state foundation"
```

---

### Task 3: Implement formal state merge precedence

**Files:**
- Modify: `src/ai_service_desk/engine/triage.py`
- Modify: `tests/engine/test_triage.py`

**Interfaces:**
- Consumes: `TriageState`, `TurnEvidence`, and exactly one classification per accepted turn.
- Produces: `_merge_turn(state: TriageState, message: str, evidence: TurnEvidence) -> TriageState` with spec-defined precedence and reset behavior.

- [ ] **Step 1: Write failing tests for system correction and short slot replies**

```python
def test_system_correction_changes_only_system() -> None:
    state = seeded_state(
        pending_field="system",
        problem_text="Nao consigo acessar",
        intent="PROBLEMA_ACESSO",
        system="",
        entities={"filial": "003"},
        confidence=0.81,
    )
    classification = TicketClassification("OUTRO", "", {}, 0.2)
    evidence = _analyze_turn(state, "Nao e CIGAM, e SIAGRI", classification)

    merged = _merge_turn(state, "Nao e CIGAM, e SIAGRI", evidence)

    assert merged.system == "SIAGRI"
    assert merged.problem_text == state.problem_text
    assert merged.intent == state.intent
    assert merged.entities == state.entities
    assert merged.confidence == state.confidence


def test_short_system_reply_preserves_substantive_context() -> None:
    state = seeded_state(
        pending_field="system",
        problem_text="Nao consigo acessar",
        intent="PROBLEMA_ACESSO",
        entities={"filial": "003"},
        confidence=0.81,
    )
    evidence = _analyze_turn(
        state,
        "CIGAM",
        TicketClassification("OUTRO", "CIGAM", {}, 0.3),
    )
    merged = _merge_turn(state, "CIGAM", evidence)

    assert merged.system == "CIGAM"
    assert merged.intent == "PROBLEMA_ACESSO"
    assert merged.problem_text == "Nao consigo acessar"
    assert merged.entities == {"filial": "003"}
    assert merged.confidence == 0.81
```

- [ ] **Step 2: Write failing tests for substantive replacement and stale-entity removal**

```python
def test_substantive_replacement_discards_old_entities_and_changes_intent() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar o CIGAM",
        intent="PROBLEMA_ACESSO",
        system="CIGAM",
        entities={"filial": "003", "rotina": "1024"},
        confidence=0.91,
    )
    classification = TicketClassification("ERRO_SISTEMA", "", {"equipamento": "PC-1"}, 0.76)
    evidence = _analyze_turn(state, "na verdade o sistema trava ao salvar", classification)

    merged = _merge_turn(state, "na verdade o sistema trava ao salvar", evidence)

    assert merged.problem_text == "na verdade o sistema trava ao salvar"
    assert merged.intent == "ERRO_SISTEMA"
    assert merged.entities == {"equipamento": "PC-1"}
    assert merged.confidence == 0.76
    assert merged.system == "CIGAM"
    assert merged.asked_fields == ()
```

Also test that an explicit new SIAGRI replaces old CIGAM, while multiple explicit systems without a valid correction clear `system`.

- [ ] **Step 3: Write failing test for unresolved `pending_field=problem` anti-loop behavior**

```python
def test_vague_problem_reply_does_not_clear_problem_asked_marker() -> None:
    state = seeded_state(
        pending_field="problem",
        asked_fields=("problem",),
        problem_text="Preciso de ajuda",
        intent="OUTRO",
    )
    classification = TicketClassification("OUTRO", "", {}, 0.8)
    evidence = _analyze_turn(state, "Nao sei explicar", classification)
    merged = _merge_turn(state, "Nao sei explicar", evidence)

    assert merged.intent == "OUTRO"
    assert "problem" in merged.asked_fields
```

- [ ] **Step 4: Run merge tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: new merge tests fail because `_merge_turn` is not implemented.

- [ ] **Step 5: Implement merge precedence exactly as the spec**

Use `dataclasses.replace()` and keep turn counters outside merge so the function only merges semantic state.

```python
def _merge_turn(state: TriageState, message: str, evidence: TurnEvidence) -> TriageState:
    classification = evidence.classification

    if evidence.kind == "SYSTEM_CORRECTION":
        assert evidence.correction is not None
        return replace(
            state,
            system=evidence.correction[1],
            pending_field="" if state.pending_field == "system" else state.pending_field,
        )

    if evidence.kind == "SYSTEM_SLOT":
        return replace(
            state,
            system=_system_from_slot(message, classification, evidence),
            pending_field="",
        )

    explicit = evidence.explicit_systems
    if len(explicit) == 1:
        next_system = explicit[0]
    elif len(explicit) > 1:
        next_system = ""
    else:
        next_system = state.system

    if state.pending_field == "problem" and classification.intent == "OUTRO":
        return replace(
            state,
            problem_text=message.strip(),
            intent=classification.intent,
            system=next_system,
            entities=dict(classification.entities),
            confidence=classification.confidence,
            pending_field="",
        )

    return replace(
        state,
        problem_text=message.strip(),
        intent=classification.intent,
        system=next_system,
        entities=dict(classification.entities),
        confidence=classification.confidence,
        pending_field="",
        asked_fields=(),
    )
```

The implementation must preserve the existing `asked_fields` for an unresolved problem reply, and clear `asked_fields` only when a usable new substantive context is established. Adjust the branch above accordingly rather than relying on later code to repair it.

- [ ] **Step 6: Add explicit tests for merge precedence order**

Prove that correction wins over the fact that `explicit_systems()` sees two systems, and that a short system slot never changes intent/entities even if its classification says `OUTRO`.

- [ ] **Step 7: Run all triage merge tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: all current triage state/parser/merge tests pass.

- [ ] **Step 8: Commit the merge rules**

```bash
git add src/ai_service_desk/engine/triage.py tests/engine/test_triage.py
git commit -m "feat: add deterministic triage state merge"
```

---

### Task 4: Implement transitions, limits, query construction, and APPROVED knowledge handoff

**Files:**
- Modify: `src/ai_service_desk/engine/triage.py`
- Modify: `tests/engine/test_triage.py`

**Interfaces:**
- Consumes: `KnowledgeEngine.available_systems(intent)`, `KnowledgeEngine.search_classified(text, classification)`, `TriageState`, merge helpers, and one injected classifier callable.
- Produces: `build_knowledge_query(problem_text: str, system: str) -> str`, `TriageEngine(session_id, knowledge_engine, classifier)`, `TriageEngine.initial_state() -> TriageState`, and `TriageEngine.step(state, message) -> tuple[TriageState, dict]`.

- [ ] **Step 1: Add deterministic control doubles for triage tests**

In `tests/engine/test_triage.py`, define a fake knowledge engine that exposes only the public Phase 5 seam. This proves triage does not depend on `df` or index internals.

```python
class FakeKnowledgeEngine:
    def __init__(self, systems_by_intent: dict[str, tuple[str, ...]], result: dict | None = None):
        self.systems_by_intent = systems_by_intent
        self.result = result or {
            "status": "KNOWLEDGE_FOUND",
            "reason": "MATCH",
            "threshold": 0.65,
            "score": 0.9,
            "classification": {},
            "knowledge": {
                "knowledge_id": "KB-SYN-CIGAM-ACCESS-001",
                "title": "Acesso sintetico",
                "answer": "Resposta literal aprovada.",
                "system": "CIGAM",
                "intent": "PROBLEMA_ACESSO",
                "version": 1,
            },
        }
        self.search_calls: list[tuple[str, TicketClassification]] = []

    def available_systems(self, intent: str) -> tuple[str, ...]:
        return self.systems_by_intent.get(intent, ())

    def search_classified(self, text: str, classification: TicketClassification) -> dict:
        self.search_calls.append((text, classification))
        return self.result
```

Also use a classifier double with an explicit call counter and queued classifications so each accepted turn can assert exactly one call.

- [ ] **Step 2: Write failing tests for missing context and availability rules**

Cover all three availability contracts:

```python
def test_no_approved_knowledge_for_intent_abstains_without_system_question() -> None:
    engine = make_triage(
        classifications=[TicketClassification("ORIENTACAO", "", {}, 0.9)],
        systems_by_intent={},
    )
    state, result = engine.step(engine.initial_state(), "Como faco algo ficticio?")
    assert result["status"] == "TRIAGE_ABSTAINED"
    assert result["reason"] == "NO_APPROVED_KNOWLEDGE_FOR_INTENT"
    assert state.status == "ABSTAINED"


def test_generic_knowledge_does_not_require_system() -> None:
    engine = make_triage(
        classifications=[TicketClassification("PROBLEMA_IMPRESSAO", "", {}, 0.9)],
        systems_by_intent={"PROBLEMA_IMPRESSAO": ("",)},
    )
    state, result = engine.step(engine.initial_state(), "A impressora ficticia nao imprime")
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert state.clarification_count == 0


def test_specific_only_knowledge_requires_system_once() -> None:
    engine = make_triage(
        classifications=[TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9)],
        systems_by_intent={"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state, result = engine.step(engine.initial_state(), "Nao consigo acessar")
    assert result == {
        "status": "NEEDS_CLARIFICATION",
        "reason": "MISSING_SYSTEM",
        "question": "Qual sistema esta com o problema?",
        "knowledge": None,
    }
    assert state.pending_field == "system"
    assert state.asked_fields == ("system",)
```

- [ ] **Step 3: Write failing tests for ambiguity and unknown-system transitions**

Cover:
- initial `CIGAM e SIAGRI` -> `NEEDS_CLARIFICATION / AMBIGUOUS_SYSTEM`;
- unresolved ambiguity after opportunity -> terminal `TRIAGE_ABSTAINED / AMBIGUOUS_SYSTEM`;
- initial XYZ -> `NEEDS_CLARIFICATION / UNKNOWN_SYSTEM`;
- second XYZ -> terminal `TRIAGE_ABSTAINED / UNKNOWN_SYSTEM`;
- known system absent from availability is not replaced or re-asked and is passed to Phase 4, allowing `SYSTEM_MISMATCH` to surface.

- [ ] **Step 4: Write failing tests for turn and clarification limits**

```python
def test_third_turn_is_processed_and_can_find_knowledge() -> None:
    engine = make_three_turn_engine()
    state = engine.initial_state()

    state, first = engine.step(state, "Preciso de ajuda")
    assert first["status"] == "NEEDS_CLARIFICATION"

    state, second = engine.step(state, "Nao consigo acessar")
    assert second["status"] == "NEEDS_CLARIFICATION"

    state, third = engine.step(state, "CIGAM")
    assert third["status"] == "KNOWLEDGE_FOUND"
    assert state.turn_count == 3
    assert state.status == "ANSWERED"


def test_fourth_turn_is_rejected_before_classifier_call() -> None:
    engine, classifier = make_engine_with_active_three_turn_state()
    before = classifier.calls
    with pytest.raises(ValueError, match="turn"):
        engine.step(active_state(turn_count=3), "quarta mensagem")
    assert classifier.calls == before
```

Also test that if turn 3 still needs a question, the result is terminal `MAX_TURNS`, and if a third clarification would be required the result is terminal `MAX_CLARIFICATIONS`.

- [ ] **Step 5: Write failing tests proving `confidence` never changes transitions**

Run the same missing-system and knowledge-found paths with confidence `0.01` and `0.99`. Assert identical status/reason/query behavior.

- [ ] **Step 6: Write failing query-builder tests**

```python
def test_query_does_not_add_intent_label_or_semantic_boosters() -> None:
    query = build_knowledge_query("Nao consigo acessar", "CIGAM")
    assert query == "Nao consigo acessar\nCIGAM"
    assert "PROBLEMA_ACESSO" not in query


def test_query_does_not_duplicate_existing_system() -> None:
    assert build_knowledge_query("Nao consigo acessar o CIGAM", "CIGAM") == "Nao consigo acessar o CIGAM"


def test_query_reconciles_only_conflicting_known_aliases_after_correction() -> None:
    query = build_knowledge_query("CIGAM e SIAGRI estao sem acesso", "SIAGRI")
    assert "CIGAM" not in query
    assert query.count("SIAGRI") == 1
    assert "PROBLEMA_ACESSO" not in query
```

Do not add any stemming, synonym expansion, knowledge metadata, or classifier label to this helper.

- [ ] **Step 7: Write failing single-turn vs two-turn knowledge equivalence test**

Use one deterministic fake knowledge engine and assert both flows call `search_classified()` with `classification.system == "CIGAM"`, threshold remains owned by the fake result at `0.65`, and both return the same synthetic knowledge ID.

```python
assert direct_result["knowledge"]["knowledge_id"] == "KB-SYN-CIGAM-ACCESS-001"
assert two_turn_result["knowledge"]["knowledge_id"] == "KB-SYN-CIGAM-ACCESS-001"
assert fake_knowledge.search_calls[0][1].system == "CIGAM"
```

- [ ] **Step 8: Write failing session isolation and terminal-state tests**

Prove:
- a `TriageEngine("session-a", ...)` rejects state with `session_id="session-b"` before classification;
- two engines with interleaved states never affect each other;
- `ANSWERED` and `ABSTAINED` states reject later `step()` calls before classification;
- no global session dictionary exists in the triage module.

- [ ] **Step 9: Run transition tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: new transition and engine tests fail because query/decision/engine methods are not implemented.

- [ ] **Step 10: Implement query construction with lexical system reconciliation only**

Use existing `SYSTEM_ALIASES` and `normalize_text` only to detect exact conflicting known aliases. Preserve original problem text except exact alias-span removal and whitespace normalization required by that removal.

Do not use intent or knowledge metadata in this function.

```python
def build_knowledge_query(problem_text: str, system: str) -> str:
    text = problem_text.strip()
    if not system:
        return text
    # Keep final system if already explicitly present.
    # Remove only exact known alias spans that resolve to a different canonical system.
    reconciled = _remove_conflicting_known_system_aliases(text, system)
    if _text_contains_canonical_system(reconciled, system):
        return reconciled.strip()
    return reconciled.strip() + "\n" + system
```

The implementation of `_remove_conflicting_known_system_aliases()` must be lexical and deterministic. It must never remove unknown literals or rewrite surrounding problem semantics.

- [ ] **Step 11: Implement public-result helpers and clarification gate**

Keep exactly three public statuses. A helper may centralize the output contract:

```python
def _clarification(reason: str, question: str) -> dict:
    return {
        "status": "NEEDS_CLARIFICATION",
        "reason": reason,
        "question": question,
        "knowledge": None,
    }


def _abstained(reason: str) -> dict:
    return {
        "status": "TRIAGE_ABSTAINED",
        "reason": reason,
        "question": None,
        "knowledge": None,
    }
```

When mapping a Phase 4 `NO_APPROVED_KNOWLEDGE` result, preserve its `reason` and keep `knowledge=None`. When mapping `KNOWLEDGE_FOUND`, pass the public Phase 4 knowledge object unchanged so the approved `answer` remains literal in the result but not in state.

- [ ] **Step 12: Implement `TriageEngine.step()` in the exact decision order**

Constructor:

```python
class TriageEngine:
    def __init__(
        self,
        session_id: str,
        knowledge_engine,
        classifier: Callable[[str], TicketClassification],
    ):
        self.session_id = session_id
        self.knowledge_engine = knowledge_engine
        self.classifier = classifier

    def initial_state(self) -> TriageState:
        return new_triage_state(self.session_id)
```

`step()` must enforce this sequence:

```text
1. validate session match and ACTIVE state
2. reject fourth turn before classifier
3. call classifier exactly once
4. analyze current turn without another LLM call
5. increment accepted user turn
6. merge semantic state using formal precedence
7. if intent == OUTRO, clarify once or abstain
8. call available_systems(intent)
9. if (), abstain without system question
10. treat explicit ambiguity/unknown system before generic-knowledge shortcut
11. if specific-only knowledge and system missing, clarify once
12. if a new question would require turn 4 -> MAX_TURNS
13. if a new question would be clarification 3 -> MAX_CLARIFICATIONS
14. build literal user-grounded knowledge query
15. build TicketClassification from state
16. call search_classified() exactly once
17. map KNOWLEDGE_FOUND -> state ANSWERED
18. map NO_APPROVED_KNOWLEDGE -> state ABSTAINED preserving reason
```

Use `replace()` to produce new immutable state values. Never add `answer` or the public knowledge object to state.

- [ ] **Step 13: Run triage tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: all state, parser, merge, limits, query, transition, isolation, and knowledge-handoff tests pass.

- [ ] **Step 14: Run Phase 4 plus triage regression together**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py tests/engine/test_triage.py -q
```

Expected: Phase 4 compatibility tests and all triage tests pass in one process.

- [ ] **Step 15: Commit the triage engine**

```bash
git add src/ai_service_desk/engine/triage.py tests/engine/test_triage.py
git commit -m "feat: add deterministic conversational triage"
```

---

### Task 5: Add the 10 synthetic conversation fixtures and smoke runner

**Files:**
- Create: `tests/fixtures/phase5_triage_conversations.jsonl`
- Create: `src/ai_service_desk/engine/triage_smoke.py`
- Create: `tests/engine/test_triage_smoke.py`

**Interfaces:**
- Consumes: `TriageEngine`, `KnowledgeEngine`, `OllamaClient`, `LocalEmbedder`, and the existing Phase 4 synthetic knowledge index built outside this runner.
- Produces: `run_triage_smoke(index, cases_path, report_path, base_url=...) -> dict` with aggregate-safe report fields only.

- [ ] **Step 1: Create the synthetic JSONL fixture contract**

Use one JSON object per conversation. The file contains only synthetic user text and expected public outcomes.

```json
{"case_name":"missing-system","turns":["Nao consigo acessar.","CIGAM"],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-CIGAM-ACCESS-001","expected_turn_count":2,"expected_clarification_count":1}
{"case_name":"complete-first-turn","turns":["Nao consigo acessar o CIGAM."],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-CIGAM-ACCESS-001","expected_turn_count":1,"expected_clarification_count":0}
{"case_name":"ambiguous-resolved","turns":["CIGAM e SIAGRI estao sem acesso.","SIAGRI"],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-SIAGRI-ACCESS-001","expected_turn_count":2,"expected_clarification_count":1}
{"case_name":"explicit-correction","turns":["CIGAM e SIAGRI estao sem acesso.","Nao e CIGAM, e SIAGRI."],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-SIAGRI-ACCESS-001","expected_turn_count":2,"expected_clarification_count":1}
{"case_name":"unknown-corrected","turns":["O sistema XYZ esta sem acesso.","CIGAM"],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-CIGAM-ACCESS-001","expected_turn_count":2,"expected_clarification_count":1}
{"case_name":"unknown-remains","turns":["O sistema XYZ esta sem acesso.","XYZ"],"expected_status":"TRIAGE_ABSTAINED","expected_reason":"UNKNOWN_SYSTEM","expected_knowledge_id":null,"expected_turn_count":2,"expected_clarification_count":1}
{"case_name":"draft-only","turns":["O CIGAM fecha em uma rotina ficticia ainda em revisao."],"expected_status":"TRIAGE_ABSTAINED","expected_knowledge_id":null,"expected_turn_count":1,"expected_clarification_count":0}
{"case_name":"generic-printing","turns":["A impressora ficticia nao imprime."],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-PRINT-001","expected_turn_count":1,"expected_clarification_count":0}
{"case_name":"session-isolation","turns":["Nao consigo acessar.","CIGAM"],"expected_status":"KNOWLEDGE_FOUND","expected_reason":"MATCH","expected_knowledge_id":"KB-SYN-CIGAM-ACCESS-001","expected_turn_count":2,"expected_clarification_count":1,"requires_interleaved_control":true}
{"case_name":"anti-loop","turns":["Preciso de ajuda.","Nao sei explicar."],"expected_status":"TRIAGE_ABSTAINED","expected_reason":"UNRESOLVED_PROBLEM","expected_knowledge_id":null,"expected_turn_count":2,"expected_clarification_count":1}
```

For `draft-only`, let the smoke accept any terminal Phase 4 no-approved reason but assert no knowledge ID and no answer are returned. Keep this fixture entirely synthetic.

- [ ] **Step 2: Write failing fixture-validation and report-privacy tests**

In `tests/engine/test_triage_smoke.py`, verify exactly 10 unique cases, all required fields, and no forbidden report keys.

```python
def test_smoke_report_contains_only_safe_aggregate_case_metadata(tmp_path: Path, monkeypatch) -> None:
    report = run_fake_smoke(tmp_path, monkeypatch)
    assert report["ok"] is True
    assert len(report["cases"]) == 10
    for case in report["cases"]:
        assert set(case) <= {
            "case_name",
            "expected_status",
            "actual_status",
            "reason",
            "expected_knowledge_id",
            "actual_knowledge_id",
            "turn_count",
            "clarification_count",
            "passed",
        }
        for forbidden in ("message", "messages", "turns", "transcript", "answer", "ticket_id"):
            assert forbidden not in case
```

- [ ] **Step 3: Run smoke tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage_smoke.py -q
```

Expected: fail because fixture/runner do not exist yet.

- [ ] **Step 4: Implement fixture loading with strict synthetic schema**

In `triage_smoke.py`, reject malformed or duplicate `case_name` rows. The loader may retain messages in memory for execution but must never copy them into the report.

- [ ] **Step 5: Implement smoke execution and interleaved session case**

For normal cases:

```python
state = engine.initial_state()
result = None
for message in case["turns"]:
    state, result = engine.step(state, message)
    if result["status"] != "NEEDS_CLARIFICATION":
        break
```

For `requires_interleaved_control`, create session A and a separate session B engine/state. Between A's first and second turns, run the synthetic printing case in B and assert B does not alter A. Do not persist either transcript.

- [ ] **Step 6: Build only safe report records**

Each case record must contain only:

```python
{
    "case_name": case["case_name"],
    "expected_status": case["expected_status"],
    "actual_status": result.get("status"),
    "reason": result.get("reason"),
    "expected_knowledge_id": case.get("expected_knowledge_id"),
    "actual_knowledge_id": (result.get("knowledge") or {}).get("knowledge_id"),
    "turn_count": state.turn_count,
    "clarification_count": state.clarification_count,
    "passed": passed,
}
```

Top-level privacy metadata should mirror the Phase 4 safe-report style and explicitly state that raw text, approved answer content, and corporate data are not included.

- [ ] **Step 7: Run smoke unit tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage_smoke.py -q
```

Expected: all fixture validation, 10-case fake execution, session isolation, and privacy tests pass.

- [ ] **Step 8: Commit the synthetic smoke layer**

```bash
git add tests/fixtures/phase5_triage_conversations.jsonl src/ai_service_desk/engine/triage_smoke.py tests/engine/test_triage_smoke.py
git commit -m "test: add phase 5 synthetic triage smoke"
```

---

### Task 6: Wire the CLI smoke command without creating a session store

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_triage_cli.py`

**Interfaces:**
- Consumes: `run_triage_smoke(...)`.
- Produces: `triage-smoke --index PATH --cases PATH --report PATH --url URL`.

- [ ] **Step 1: Write failing parser/default tests**

```python
def test_triage_smoke_parser_requires_index_cases_and_report() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "triage-smoke",
            "--index",
            "index",
            "--cases",
            "tests/fixtures/phase5_triage_conversations.jsonl",
            "--report",
            "report.json",
        ]
    )
    assert args.command == "triage-smoke"
    assert str(args.index) == "index"
    assert str(args.cases).endswith("phase5_triage_conversations.jsonl")
    assert str(args.report) == "report.json"
    assert args.url == DEFAULT_URL
```

- [ ] **Step 2: Write failing CLI delegation and safe-output test**

Patch `run_triage_smoke` to return a synthetic aggregate report. Assert the CLI prints only aggregate status, case count, and report path. It must not print fixture turns or approved answer text.

```python
def test_triage_smoke_cli_prints_only_safe_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "run_triage_smoke",
        lambda *args, **kwargs: {"ok": True, "cases": [{"passed": True}] * 10},
    )
    code = cli.main(
        [
            "triage-smoke",
            "--index",
            str(tmp_path / "index"),
            "--cases",
            "tests/fixtures/phase5_triage_conversations.jsonl",
            "--report",
            str(tmp_path / "report.json"),
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "TRIAGE SMOKE OK" in output
    assert "Casos sinteticos: 10" in output
    assert "answer" not in output.lower()
```

- [ ] **Step 3: Run CLI tests and verify RED**

Run:

```bash
pytest tests/test_triage_cli.py -q
```

Expected: fail because `triage-smoke` is not registered.

- [ ] **Step 4: Add the parser and command delegation**

In `build_parser()`:

```python
triage_smoke = sub.add_parser("triage-smoke")
triage_smoke.add_argument("--index", type=Path, required=True)
triage_smoke.add_argument("--cases", type=Path, required=True)
triage_smoke.add_argument("--report", type=Path, required=True)
triage_smoke.add_argument("--url", default=DEFAULT_URL)
```

In `main()`, place this beside the existing smoke/evaluation commands so `run_triage_smoke()` owns its Ollama client lifecycle, as `run_knowledge_smoke()` already does:

```python
if args.command == "triage-smoke":
    report = run_triage_smoke(args.index, args.cases, args.report, args.url)
    print("TRIAGE SMOKE OK" if report["ok"] else "TRIAGE SMOKE REQUER REVISAO")
    print(f"Casos sinteticos: {len(report.get('cases', []))}")
    print("Relatorio agregado local: " + str(args.report))
    return 0 if report["ok"] else 1
```

Do not add `--state`, `--transcript`, chat history persistence, or an interactive session store in Phase 5.

- [ ] **Step 5: Run CLI tests and verify GREEN**

Run:

```bash
pytest tests/test_triage_cli.py -q
```

Expected: all triage CLI tests pass without real Ollama.

- [ ] **Step 6: Run all CLI regression tests**

Run:

```bash
pytest tests/test_cli.py tests/test_knowledge_cli.py tests/test_triage_cli.py -q
```

Expected: all previous CLI contracts remain green.

- [ ] **Step 7: Commit CLI wiring**

```bash
git add src/ai_service_desk/cli.py tests/test_triage_cli.py
git commit -m "feat: add phase 5 triage smoke CLI"
```

---

### Task 7: Add Dell workflow and Phase 5 documentation last

**Files:**
- Create: `.github/workflows/phase5-triage-smoke.yml`
- Modify: `tests/test_workflows.py`
- Create: `docs/triage/phase-5.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `triage-smoke` CLI, existing Phase 4 synthetic FAQ, Phase 5 synthetic conversations, local Ollama.
- Produces: manual Dell homologation gate and operator documentation.

- [ ] **Step 1: Write failing workflow policy test before creating the workflow**

Extend `tests/test_workflows.py`:

```python
PHASE5_WORKFLOW = ROOT / ".github" / "workflows" / "phase5-triage-smoke.yml"


def test_phase5_triage_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE5_WORKFLOW.exists()
    text = PHASE5_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk knowledge-index",
        "python -m ai_service_desk triage-smoke",
        "knowledge/phase4_synthetic_faq.jsonl",
        "tests/fixtures/phase5_triage_conversations.jsonl",
        "http://127.0.0.1:11434",
    ):
        assert required in text
    for forbidden in ("upload-artifact", "Get-Content", "--show-history", "documents.jsonl", "embeddings.npy"):
        assert forbidden not in text
```

- [ ] **Step 2: Run the workflow test and verify RED**

Run:

```bash
pytest tests/test_workflows.py::test_phase5_triage_workflow_is_manual_local_and_non_exporting -q
```

Expected: fail because `.github/workflows/phase5-triage-smoke.yml` does not exist.

- [ ] **Step 3: Create the manual Dell workflow**

Follow the Phase 4 pattern exactly where possible:

```yaml
name: Phase 5 triage smoke

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
  phase5-triage-smoke:
    name: Windows Phase 5 triage smoke
    runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
    timeout-minutes: 20
```

Required steps:
1. checkout `inputs.target_ref`;
2. verify Python 3.14;
3. install `.[dev]`;
4. run `doctor --url http://127.0.0.1:11434`;
5. run `knowledge-validate --file knowledge/phase4_synthetic_faq.jsonl`;
6. create a fresh index under `$env:RUNNER_TEMP` with `knowledge-index`;
7. run `triage-smoke --index ... --cases tests/fixtures/phase5_triage_conversations.jsonl --report ... --url http://127.0.0.1:11434`.

Never upload or print the report body. No `upload-artifact` or `Get-Content`.

- [ ] **Step 4: Run workflow policy tests and verify GREEN**

Run:

```bash
pytest tests/test_workflows.py -q
```

Expected: all existing workflow policy tests plus the Phase 5 policy test pass.

- [ ] **Step 5: Write Phase 5 operational documentation**

Create `docs/triage/phase-5.md` containing these concrete sections:
- purpose and non-goals;
- exact `TriageState` persisted fields;
- `MAX_USER_TURNS = 3` and `MAX_CLARIFICATIONS = 2` semantics;
- three public statuses and terminal behavior;
- `search_classified()`/`available_systems()` seam;
- query constraints and unchanged `0.65` threshold;
- session isolation and caller-owned persistence;
- synthetic smoke command;
- privacy statement that transcript and answer are not persisted in triage state/report.

Document the local smoke command exactly:

```powershell
python -m ai_service_desk triage-smoke `
  --index C:\ai-service-desk-data\phase-5\index `
  --cases tests/fixtures/phase5_triage_conversations.jsonl `
  --report C:\ai-service-desk-data\phase-5\reports\smoke.json `
  --url http://127.0.0.1:11434
```

- [ ] **Step 6: Update README without changing earlier phase claims**

Add a short Phase 5 section describing short controlled multi-turn triage, APPROVED-only handoff, no ticket/action execution, and the `triage-smoke` command. Keep Phase 1 to 4 documentation intact.

- [ ] **Step 7: Run documentation-adjacent workflow/CLI tests**

Run:

```bash
pytest tests/test_workflows.py tests/test_triage_cli.py -q
```

Expected: pass.

- [ ] **Step 8: Commit workflow and docs**

```bash
git add .github/workflows/phase5-triage-smoke.yml tests/test_workflows.py docs/triage/phase-5.md README.md
git commit -m "docs: add phase 5 triage homologation"
```

---

### Task 8: Final regression, privacy review, hosted CI, and Dell homologation gate

**Files:**
- Review only all Phase 5 changed files.
- Do not add implementation changes unless a failing verification demonstrates a defect and the fix follows TDD.

**Interfaces:**
- Consumes: completed Tasks 1 to 7.
- Produces: evidence that Phase 5 is ready for review/homologation without merging.

- [ ] **Step 1: Run focused Phase 5 tests**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py tests/engine/test_triage.py tests/engine/test_triage_smoke.py tests/test_triage_cli.py tests/test_workflows.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run Ruff lint and formatting checks**

Run:

```bash
ruff check .
ruff format --check .
```

Expected: no lint errors and all files already formatted.

- [ ] **Step 3: Run the complete pytest regression suite**

Run:

```bash
pytest -q
```

Expected: all 177 pre-Phase-5 tests still pass plus all new Phase 5 tests. If total test count is below 177, stop and investigate test loss before proceeding.

- [ ] **Step 4: Review protected-file integrity**

Compare the implementation branch against base `491e5dd5f79dec8ff9a192a4929b48209956be3a` and assert these paths are absent from the changed-file list:

```text
src/ai_service_desk/engine/classification.py
src/ai_service_desk/engine/retrieval.py
src/ai_service_desk/engine/index.py
src/ai_service_desk/engine/knowledge.py
```

If any protected file changed, stop and require the blocker evidence mandated by the spec before continuing.

- [ ] **Step 5: Perform explicit privacy and scope review**

Inspect changed files and assert:
- no real corporate ticket text or identifiers;
- no generated `documents.jsonl` or `embeddings.npy`;
- no real index/report artifacts;
- no transcript persistence;
- no `answer` field in `TriageState`;
- no historical `ticket_id` in triage public results or smoke report;
- no DRAFT/RETIRED answer path;
- no global session store;
- no ticket creation, playbook, policy, execution, or frontend code;
- no threshold other than existing `0.65` in the Phase 5 path.

- [ ] **Step 6: Verify no second classification path**

Use tests plus code review to confirm:
- each accepted `TriageEngine.step()` invokes its injected classifier once;
- `search_classified()` never invokes `classify_ticket`;
- `KnowledgeEngine.search()` still invokes `classify_ticket` once for existing callers.

- [ ] **Step 7: Push branch and use hosted CI as the authoritative full Python gate**

Hosted CI must run on the final head and confirm Python 3.14, Ruff lint, Ruff format, and complete pytest success. Do not treat local reconstructed environments as a substitute for hosted CI.

- [ ] **Step 8: Run the manual Dell Phase 5 smoke on the same final head**

Use `.github/workflows/phase5-triage-smoke.yml` or the equivalent manual PowerShell commands if workflow dispatch is unavailable before merge. Required evidence:

```text
Python 3.14.x
Ollama reachable on 127.0.0.1:11434
qwen3.5:4b available
qwen3-embedding:0.6b available
Phase 4 synthetic knowledge validates
APPROVED_KNOWLEDGE index builds
TRIAGE SMOKE OK
10 synthetic cases
exit code 0
```

Do not print or upload raw smoke report contents.

- [ ] **Step 9: Final review checkpoint before any merge**

Record:
- final head SHA;
- hosted CI result and total pytest count;
- Dell smoke result;
- changed-file list;
- protected files unchanged;
- no corporate data/helpers/generated index artifacts;
- PR open and unmerged.

Stop for explicit user merge approval. Phase 5 must not be marked 100% or merged without that approval.
