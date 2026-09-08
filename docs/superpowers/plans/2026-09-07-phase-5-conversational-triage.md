# Phase 5 Conversational Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a short, deterministic, multi-turn triage state machine that gathers only missing context and then reuses Phase 4 APPROVED knowledge retrieval without changing existing Phase 1 to 4 behavior.

**Architecture:** Extend `KnowledgeEngine` additively with `search_classified()` and `available_systems()`, then add a pure `TriageState` plus `TriageEngine.step(state, message) -> (new_state, result)`. The triage layer classifies each accepted user message at most once, applies deterministic merge and stop rules, and calls Phase 4 retrieval only after context is sufficient. It never reads knowledge index internals directly, never uses historical retrieval as official guidance, and never persists transcript or approved answers in state.

**Tech Stack:** Python 3.14, dataclasses, existing `classify_ticket`, existing `KnowledgeEngine`, argparse, pytest, Ruff, GitHub Actions, Dell self-hosted Windows/Ollama runner.

**Spec:** `docs/superpowers/specs/2026-09-07-phase-5-conversational-triage-design.md`

## Global Constraints

- Base implementation is `main` at `491e5dd5f79dec8ff9a192a4929b48209956be3a`; approved spec head is `a540c1707663d3d86693085046e4c2099d386e39`.
- `KnowledgeEngine.search(text)` remains public and behaviorally backward compatible.
- `KnowledgeEngine.search_classified(text, classification)` is strictly additive and reuses the same Phase 4 gates, embedding path, threshold, and result contract.
- `KnowledgeEngine.available_systems(intent)` is the only knowledge-availability interface the triage layer may use. `TriageEngine` must not read `KnowledgeEngine.df`, `documents.jsonl`, embeddings, manifest, provenance, or matrix internals.
- `MAX_USER_TURNS = 3` and `MAX_CLARIFICATIONS = 2` exactly.
- Turn 3 is processed fully and may return `KNOWLEDGE_FOUND`; turn 4 is rejected before classification.
- Each accepted user message is classified at most once. Entering knowledge must not classify again.
- Merge precedence and state-reset rules follow the approved spec exactly.
- System correction parsing is conservative and only accepts an unambiguous `nao e <known alias>, e <known alias>` structure with exactly two distinct known canonical systems and no third system.
- `confidence` is metadata only and never affects a transition.
- Knowledge query text contains only current user-provided `problem_text` plus resolved user-provided system context when needed. No intent labels, knowledge tags, synonyms, titles, answers, historical text, or semantic booster phrases may be added.
- Threshold remains exactly `0.65`; triage has no threshold parameter or override.
- `TriageState` never stores transcript, assistant messages, knowledge answer, article text, embeddings, scores, historical ticket content, historical `ticket_id`, or chain-of-thought.
- Only `APPROVED` knowledge may produce official guidance. DRAFT and RETIRED content never appears as a response.
- All new committed fixtures and conversations are synthetic.
- No ticket creation, playbooks, policy engine, machine execution, frontend, database, global session cache, or persistence layer in Phase 5.
- Do not modify `src/ai_service_desk/engine/classification.py`, `src/ai_service_desk/engine/retrieval.py`, or `src/ai_service_desk/engine/index.py` unless a reproducible blocking test is first documented with technical cause, smallest possible change, and regression risk. The approved design expects no such changes.
- `src/ai_service_desk/engine/knowledge.py` also remains unchanged unless a reproducible blocker proves otherwise.
- All 177 pre-Phase-5 tests remain a mandatory regression gate, in addition to all new Phase 5 tests.

## File Map

**Modify** `src/ai_service_desk/engine/knowledge_retrieval.py`
- Keep `KnowledgeEngine.search(text)` behavior unchanged.
- Add `search_classified(text, classification)`.
- Add `available_systems(intent)`.

**Create** `src/ai_service_desk/engine/triage.py`
- Own `TriageState`, limits, current-turn evidence, conservative system correction parsing, deterministic message categorization, state merge, query construction, transition decisions, and `TriageEngine`.

**Create** `src/ai_service_desk/engine/triage_smoke.py`
- Load and execute the 10 approved synthetic multi-turn cases and write only safe aggregate metadata.

**Modify** `src/ai_service_desk/cli.py`
- Add only the `triage-smoke` homologation entrypoint. No persistent chat/session store.

**Create** `tests/engine/test_triage.py`
- Unit-test state, parser, merge precedence, availability decisions, limits, query construction, session isolation, terminal behavior, and knowledge handoff with deterministic control doubles.

**Modify** `tests/engine/test_knowledge_retrieval.py`
- Prove `search()` compatibility and `available_systems()` behavior.

**Create** `tests/engine/test_triage_smoke.py`
- Prove fixture validation, 10-case execution, isolation, and report privacy using fakes.

**Create** `tests/test_triage_cli.py`
- Prove CLI parser/delegation/safe output without real Ollama.

**Create** `tests/fixtures/phase5_triage_conversations.jsonl`
- Store only the 10 approved synthetic conversations and expected outcomes.

**Create** `.github/workflows/phase5-triage-smoke.yml`
- Manual Dell/Ollama homologation using only synthetic knowledge and conversations.

**Modify** `tests/test_workflows.py`
- Enforce manual, self-hosted, loopback, non-exporting workflow policy.

**Create** `docs/triage/phase-5.md`
- Operational Phase 5 contract and smoke instructions.

**Modify** `README.md`
- Add Phase 5 summary and command without changing prior phase semantics.

---

### Task 1: Add the backward-compatible KnowledgeEngine seam

**Files:**
- Modify: `src/ai_service_desk/engine/knowledge_retrieval.py`
- Test: `tests/engine/test_knowledge_retrieval.py`

**Interfaces:**
- Consumes: existing `KnowledgeEngine.search(text: str) -> dict`, `retrieve_knowledge(...)`, `classify_ticket(...)`, validated APPROVED data loaded by `KnowledgeEngine`.
- Produces: `KnowledgeEngine.search_classified(text: str, classification: TicketClassification) -> dict` and `KnowledgeEngine.available_systems(intent: str) -> tuple[str, ...]`.

- [ ] **Step 1: Write failing equivalence tests**

Add a Phase 4 regression test using the existing fakes:

```python
def test_search_and_search_classified_are_equivalent_for_same_classification(
    tmp_path: Path,
) -> None:
    embedder = FakeEmbedder()
    root = tmp_path / "index"
    build_knowledge_index(write_source(tmp_path / "knowledge.jsonl"), root, embedder, batch_size=1)
    embedder.calls.clear()

    client = FakeClient(system="CIGAM", intent="PROBLEMA_ACESSO")
    engine = KnowledgeEngine(root, client, embedder)
    expected = TicketClassification("PROBLEMA_ACESSO", "CIGAM", {}, 0.9)

    via_search = engine.search("Nao consigo acessar o CIGAM")
    assert client.chat_calls == 1

    embedder.calls.clear()
    via_classified = engine.search_classified("Nao consigo acessar o CIGAM", expected)

    assert via_classified == via_search
    assert client.chat_calls == 1
    assert len(embedder.calls) == 1
```

- [ ] **Step 2: Write failing availability tests**

Add a local test helper that builds a valid APPROVED index with multiple synthetic articles, then assert deterministic unique system metadata only:

```python
def test_available_systems_is_sorted_unique_and_intent_scoped(tmp_path: Path) -> None:
    engine = build_engine_with_articles(
        tmp_path,
        [
            article(knowledge_id="KB-S1", system="SIAGRI", intent="PROBLEMA_ACESSO"),
            article(knowledge_id="KB-C1", system="CIGAM", intent="PROBLEMA_ACESSO"),
            article(knowledge_id="KB-C2", system="CIGAM", intent="PROBLEMA_ACESSO"),
            article(knowledge_id="KB-P1", system="", intent="PROBLEMA_IMPRESSAO"),
        ],
    )

    assert engine.available_systems("PROBLEMA_ACESSO") == ("CIGAM", "SIAGRI")
    assert engine.available_systems("PROBLEMA_IMPRESSAO") == ("",)
    assert engine.available_systems("ORIENTACAO") == ()
```

The helper stays in the test module. No production triage code receives `df` or document rows.

- [ ] **Step 3: Run focused tests and verify RED**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py -q
```

Expected: old tests pass and the new tests fail because the two new methods do not exist.

- [ ] **Step 4: Implement the smallest additive seam**

Keep `retrieve_knowledge()`, `_eligible_pool()`, `_base_result()`, threshold defaults, result shape, and reasons unchanged. Change only the `KnowledgeEngine` class:

```python
class KnowledgeEngine:
    # __init__ stays unchanged

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

- [ ] **Step 5: Run Phase 4 retrieval tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py -q
```

Expected: all Phase 4 retrieval tests plus new seam tests pass.

- [ ] **Step 6: Run the broader Phase 4 knowledge regression gate**

Run:

```bash
pytest tests/engine/test_knowledge.py tests/engine/test_knowledge_retrieval.py tests/engine/test_knowledge_smoke.py tests/test_knowledge_cli.py -q
```

Expected: all prior knowledge tests pass without changed expectations.

- [ ] **Step 7: Commit the additive seam**

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
- Consumes: `TicketClassification`, `SYSTEM_ALIASES`, `explicit_systems`, `normalize_text`.
- Produces: `TriageState`, `TurnEvidence`, `MAX_USER_TURNS`, `MAX_CLARIFICATIONS`, `new_triage_state(session_id)`, `_parse_system_correction(text)`, `_is_short_system_reply(...)`, `_analyze_turn(...)`.

- [ ] **Step 1: Write failing state-schema and limit tests**

```python
from dataclasses import asdict

import pytest

from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.triage import (
    MAX_CLARIFICATIONS,
    MAX_USER_TURNS,
    _analyze_turn,
    _is_short_system_reply,
    _parse_system_correction,
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
    assert MAX_USER_TURNS == 3
    assert MAX_CLARIFICATIONS == 2
    assert not (
        {"transcript", "messages", "answer", "ticket_id", "score", "embedding"} & set(asdict(state))
    )
```

- [ ] **Step 2: Write failing conservative correction tests**

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
def test_correction_parser_rejects_ambiguous_unknown_or_vague_language(text: str) -> None:
    assert _parse_system_correction(text) is None
```

- [ ] **Step 3: Write failing slot-only categorization tests**

```python
def test_short_known_system_reply_is_slot_only_only_when_system_is_pending() -> None:
    classification = TicketClassification("OUTRO", "CIGAM", {}, 0.4)
    assert _is_short_system_reply("CIGAM", "system", classification)
    assert not _is_short_system_reply("CIGAM", "", classification)


def test_short_unknown_literal_reply_can_remain_slot_only() -> None:
    classification = TicketClassification("OUTRO", "XYZ", {}, 0.4)
    assert _is_short_system_reply("XYZ", "system", classification)
    assert _is_short_system_reply("sistema XYZ", "system", classification)


def test_correction_has_precedence_over_multiple_explicit_systems() -> None:
    state = new_triage_state("session-a")
    state = dataclasses.replace(state, pending_field="system")
    classification = TicketClassification("OUTRO", "", {}, 0.3)
    evidence = _analyze_turn(state, "Nao e CIGAM, e SIAGRI", classification)
    assert evidence.kind == "SYSTEM_CORRECTION"
    assert evidence.explicit_systems == ("CIGAM", "SIAGRI")
    assert evidence.correction == ("CIGAM", "SIAGRI")
```

Add `import dataclasses` in the test file for the last test.

- [ ] **Step 4: Run focused tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: import/attribute failures because the triage module does not exist.

- [ ] **Step 5: Implement the state and transient evidence types**

Create only imports used in this gate:

```python
import re
from dataclasses import dataclass

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

- [ ] **Step 6: Implement exact alias and correction helpers**

Use full normalized alias equality, never fuzzy matching:

```python
def _canonical_for_exact_alias(value: str) -> str | None:
    wanted = normalize_text(value).strip().strip(".!?")
    matches = {
        canonical
        for canonical, aliases in SYSTEM_ALIASES.items()
        if wanted in {normalize_text(canonical), *(normalize_text(alias) for alias in aliases)}
    }
    return next(iter(matches)) if len(matches) == 1 else None


_CORRECTION_RE = re.compile(r"^nao\s+e\s+(.+?)\s*,?\s+e\s+(.+?)\s*[.!?]?$", re.IGNORECASE)


def _parse_system_correction(text: str) -> tuple[str, str] | None:
    normalized = normalize_text(text).strip()
    match = _CORRECTION_RE.fullmatch(normalized)
    if not match:
        return None
    old = _canonical_for_exact_alias(match.group(1))
    new = _canonical_for_exact_alias(match.group(2))
    systems = tuple(explicit_systems(text))
    if old is None or new is None or old == new:
        return None
    if len(systems) != 2 or set(systems) != {old, new}:
        return None
    return old, new
```

- [ ] **Step 7: Implement slot-only and turn categorization**

```python
def _is_short_system_reply(
    message: str,
    pending_field: str,
    classification: TicketClassification,
) -> bool:
    if pending_field != "system":
        return False
    if _parse_system_correction(message) is not None:
        return True
    normalized = normalize_text(message).strip().strip(".!?")
    if _canonical_for_exact_alias(normalized) is not None:
        return True
    literal = normalize_text(classification.system).strip()
    if not literal:
        return False
    return normalized == literal or normalized == f"sistema {literal}"


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

Expected: state, limit, correction-parser, slot-only, and categorization tests pass.

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
- Consumes: `TriageState`, `TurnEvidence`, one classification already produced for the accepted turn.
- Produces: `_system_from_slot(...)` and `_merge_turn(state, message, evidence) -> TriageState`.

- [ ] **Step 1: Add a deterministic state factory to tests**

```python
def seeded_state(**changes) -> TriageState:
    return dataclasses.replace(new_triage_state("session-a"), **changes)
```

Import `TriageState`, `_merge_turn`, and `_system_from_slot` for the new tests.

- [ ] **Step 2: Write failing tests for correction and slot preservation**

```python
def test_system_correction_changes_only_system() -> None:
    state = seeded_state(
        pending_field="system",
        problem_text="Nao consigo acessar",
        intent="PROBLEMA_ACESSO",
        entities={"filial": "003"},
        confidence=0.81,
    )
    evidence = _analyze_turn(
        state,
        "Nao e CIGAM, e SIAGRI",
        TicketClassification("OUTRO", "", {}, 0.2),
    )
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
    evidence = _analyze_turn(state, "CIGAM", TicketClassification("OUTRO", "CIGAM", {}, 0.3))
    merged = _merge_turn(state, "CIGAM", evidence)
    assert merged.system == "CIGAM"
    assert merged.intent == "PROBLEMA_ACESSO"
    assert merged.problem_text == "Nao consigo acessar"
    assert merged.entities == {"filial": "003"}
    assert merged.confidence == 0.81
```

- [ ] **Step 3: Write failing tests for substantive replacement**

```python
def test_substantive_replacement_discards_old_entities_and_changes_intent() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar o CIGAM",
        intent="PROBLEMA_ACESSO",
        system="CIGAM",
        entities={"filial": "003", "rotina": "1024"},
        confidence=0.91,
        asked_fields=("system",),
    )
    evidence = _analyze_turn(
        state,
        "na verdade o sistema trava ao salvar",
        TicketClassification("ERRO_SISTEMA", "", {"equipamento": "PC-1"}, 0.76),
    )
    merged = _merge_turn(state, "na verdade o sistema trava ao salvar", evidence)
    assert merged.problem_text == "na verdade o sistema trava ao salvar"
    assert merged.intent == "ERRO_SISTEMA"
    assert merged.entities == {"equipamento": "PC-1"}
    assert merged.confidence == 0.76
    assert merged.system == "CIGAM"
    assert merged.asked_fields == ()


def test_new_explicit_system_replaces_old_system() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar", intent="PROBLEMA_ACESSO", system="CIGAM"
    )
    message = "na verdade o SIAGRI trava ao salvar"
    evidence = _analyze_turn(
        state, message, TicketClassification("ERRO_SISTEMA", "SIAGRI", {}, 0.8)
    )
    assert _merge_turn(state, message, evidence).system == "SIAGRI"


def test_multiple_explicit_systems_clear_old_system_without_correction() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar", intent="PROBLEMA_ACESSO", system="CIGAM"
    )
    message = "CIGAM e SIAGRI estao sem acesso"
    evidence = _analyze_turn(state, message, TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8))
    assert _merge_turn(state, message, evidence).system == ""
```

- [ ] **Step 4: Write failing anti-loop merge test for `pending_field=problem`**

```python
def test_vague_problem_reply_preserves_problem_asked_marker() -> None:
    state = seeded_state(
        pending_field="problem",
        asked_fields=("problem",),
        problem_text="Preciso de ajuda",
        intent="OUTRO",
    )
    message = "Nao sei explicar"
    evidence = _analyze_turn(state, message, TicketClassification("OUTRO", "", {}, 0.8))
    merged = _merge_turn(state, message, evidence)
    assert merged.intent == "OUTRO"
    assert merged.problem_text == message
    assert merged.asked_fields == ("problem",)
```

- [ ] **Step 5: Run merge tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: new tests fail because merge helpers do not exist.

- [ ] **Step 6: Implement slot resolution and merge precedence**

Add `replace` to the production dataclass import in this task.

```python
def _system_from_slot(
    message: str,
    classification: TicketClassification,
    evidence: TurnEvidence,
) -> str:
    if evidence.correction is not None:
        return evidence.correction[1]
    canonical = _canonical_for_exact_alias(message)
    if canonical is not None:
        return canonical
    normalized = normalize_text(message).strip().strip(".!?")
    if normalized.startswith("sistema "):
        normalized = normalized.removeprefix("sistema ").strip()
    literal = classification.system.strip()
    if literal and normalize_text(literal) == normalized:
        return literal
    return ""


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

The unresolved `pending_field="problem"` branch intentionally omits `asked_fields`, so `dataclasses.replace()` preserves the existing `("problem",)` marker. A usable substantive replacement takes the final branch and starts a new context by clearing `asked_fields`.

- [ ] **Step 7: Run all merge tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: state/parser/merge tests pass.

- [ ] **Step 8: Commit merge rules**

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
- Consumes: `KnowledgeEngine.available_systems(intent)`, `KnowledgeEngine.search_classified(text, classification)`, merged `TriageState`, one injected classifier callable.
- Produces: `build_knowledge_query(problem_text, system) -> str`, `TriageEngine(session_id, knowledge_engine, classifier)`, `initial_state()`, `step(state, message) -> tuple[TriageState, dict]`.

- [ ] **Step 1: Add exact control doubles to tests**

```python
class QueueClassifier:
    def __init__(self, values: list[TicketClassification]):
        self.values = list(values)
        self.calls = 0

    def __call__(self, text: str) -> TicketClassification:
        self.calls += 1
        if not self.values:
            raise AssertionError("unexpected classifier call")
        return self.values.pop(0)


class FakeKnowledgeEngine:
    def __init__(
        self,
        systems_by_intent: dict[str, tuple[str, ...]],
        result: dict | None = None,
    ):
        self.systems_by_intent = systems_by_intent
        self.result = result or {
            "status": "KNOWLEDGE_FOUND",
            "reason": "MATCH",
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
        self.availability_calls: list[str] = []

    def available_systems(self, intent: str) -> tuple[str, ...]:
        self.availability_calls.append(intent)
        return self.systems_by_intent.get(intent, ())

    def search_classified(self, text: str, classification: TicketClassification) -> dict:
        self.search_calls.append((text, classification))
        return self.result


def make_engine(
    classifications: list[TicketClassification],
    systems_by_intent: dict[str, tuple[str, ...]],
    result: dict | None = None,
    session_id: str = "session-a",
):
    classifier = QueueClassifier(classifications)
    knowledge = FakeKnowledgeEngine(systems_by_intent, result)
    return TriageEngine(session_id, knowledge, classifier), classifier, knowledge
```

- [ ] **Step 2: Write failing availability and missing-context tests**

```python
def test_no_approved_knowledge_for_intent_abstains_without_system_question() -> None:
    engine, _, knowledge = make_engine(
        [TicketClassification("ORIENTACAO", "", {}, 0.9)],
        {},
    )
    state, result = engine.step(engine.initial_state(), "Como faco algo ficticio?")
    assert result["status"] == "TRIAGE_ABSTAINED"
    assert result["reason"] == "NO_APPROVED_KNOWLEDGE_FOR_INTENT"
    assert state.status == "ABSTAINED"
    assert knowledge.search_calls == []


def test_generic_knowledge_does_not_require_missing_system() -> None:
    engine, _, knowledge = make_engine(
        [TicketClassification("PROBLEMA_IMPRESSAO", "", {}, 0.9)],
        {"PROBLEMA_IMPRESSAO": ("",)},
    )
    state, result = engine.step(engine.initial_state(), "A impressora ficticia nao imprime")
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert state.clarification_count == 0
    assert len(knowledge.search_calls) == 1


def test_specific_only_knowledge_requires_system_once() -> None:
    engine, _, knowledge = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9)],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
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
    assert knowledge.search_calls == []
```

- [ ] **Step 3: Write failing ambiguity, unknown, and mismatch tests**

```python
def test_ambiguous_system_gets_one_clarification_then_terminal_if_still_ambiguous() -> None:
    engine, _, _ = make_engine(
        [
            TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
            TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
        ],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state, first = engine.step(engine.initial_state(), "CIGAM e SIAGRI estao sem acesso")
    assert (first["status"], first["reason"]) == ("NEEDS_CLARIFICATION", "AMBIGUOUS_SYSTEM")
    state, second = engine.step(state, "CIGAM e SIAGRI")
    assert (second["status"], second["reason"]) == ("TRIAGE_ABSTAINED", "AMBIGUOUS_SYSTEM")
    assert state.status == "ABSTAINED"


def test_unknown_system_gets_one_correction_opportunity_then_terminal() -> None:
    engine, _, _ = make_engine(
        [
            TicketClassification("PROBLEMA_ACESSO", "XYZ", {}, 0.9),
            TicketClassification("OUTRO", "XYZ", {}, 0.2),
        ],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state, first = engine.step(engine.initial_state(), "O sistema XYZ esta sem acesso")
    assert (first["status"], first["reason"]) == ("NEEDS_CLARIFICATION", "UNKNOWN_SYSTEM")
    state, second = engine.step(state, "XYZ")
    assert (second["status"], second["reason"]) == ("TRIAGE_ABSTAINED", "UNKNOWN_SYSTEM")


def test_known_system_without_intent_coverage_is_delegated_to_phase4() -> None:
    phase4 = {
        "status": "NO_APPROVED_KNOWLEDGE",
        "reason": "SYSTEM_MISMATCH",
        "knowledge": None,
    }
    engine, _, knowledge = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "TEAMS", {}, 0.9)],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
        phase4,
    )
    state, result = engine.step(engine.initial_state(), "Nao consigo acessar o TEAMS")
    assert result["status"] == "TRIAGE_ABSTAINED"
    assert result["reason"] == "SYSTEM_MISMATCH"
    assert len(knowledge.search_calls) == 1
    assert state.status == "ABSTAINED"
```

- [ ] **Step 4: Write failing turn and clarification limit tests**

```python
def test_third_turn_is_fully_processed_and_can_find_knowledge() -> None:
    engine, classifier, _ = make_engine(
        [
            TicketClassification("OUTRO", "", {}, 0.8),
            TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8),
            TicketClassification("OUTRO", "CIGAM", {}, 0.2),
        ],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state = engine.initial_state()
    state, first = engine.step(state, "Preciso de ajuda")
    state, second = engine.step(state, "Nao consigo acessar")
    state, third = engine.step(state, "CIGAM")
    assert first["status"] == second["status"] == "NEEDS_CLARIFICATION"
    assert third["status"] == "KNOWLEDGE_FOUND"
    assert state.turn_count == 3
    assert state.status == "ANSWERED"
    assert classifier.calls == 3


def test_fourth_turn_is_rejected_before_classification() -> None:
    engine, classifier, _ = make_engine([], {})
    state = dataclasses.replace(engine.initial_state(), turn_count=3)
    with pytest.raises(ValueError, match="turn"):
        engine.step(state, "quarta mensagem")
    assert classifier.calls == 0


def test_turn_three_that_would_need_another_question_abstains_with_max_turns() -> None:
    engine, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
    )
    state = dataclasses.replace(engine.initial_state(), turn_count=2)
    state, result = engine.step(state, "Nao consigo acessar")
    assert result == {
        "status": "TRIAGE_ABSTAINED",
        "reason": "MAX_TURNS",
        "question": None,
        "knowledge": None,
    }
    assert state.status == "ABSTAINED"


def test_third_clarification_is_never_emitted() -> None:
    engine, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
    )
    state = dataclasses.replace(engine.initial_state(), clarification_count=2)
    state, result = engine.step(state, "Nao consigo acessar")
    assert result["status"] == "TRIAGE_ABSTAINED"
    assert result["reason"] == "MAX_CLARIFICATIONS"
    assert result["question"] is None
```

- [ ] **Step 5: Write failing confidence-invariance tests**

```python
@pytest.mark.parametrize("confidence", [0.01, 0.99])
def test_confidence_does_not_change_missing_system_transition(confidence: float) -> None:
    engine, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, confidence)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
    )
    _, result = engine.step(engine.initial_state(), "Nao consigo acessar")
    assert (result["status"], result["reason"]) == ("NEEDS_CLARIFICATION", "MISSING_SYSTEM")
```

- [ ] **Step 6: Write failing query-builder tests**

```python
def test_query_contains_only_problem_and_later_system_context() -> None:
    query = build_knowledge_query("Nao consigo acessar", "CIGAM")
    assert query == "Nao consigo acessar\nCIGAM"
    assert "PROBLEMA_ACESSO" not in query


def test_query_does_not_duplicate_existing_system() -> None:
    assert (
        build_knowledge_query("Nao consigo acessar o CIGAM", "CIGAM")
        == "Nao consigo acessar o CIGAM"
    )


def test_query_removes_only_conflicting_known_alias_after_correction() -> None:
    query = build_knowledge_query("CIGAM e SIAGRI estao sem acesso", "SIAGRI")
    assert "CIGAM" not in query
    assert query.count("SIAGRI") == 1
    assert "estao sem acesso" in query
    assert "PROBLEMA_ACESSO" not in query


def test_query_does_not_remove_unknown_old_literal_or_add_boosters() -> None:
    query = build_knowledge_query("O sistema XYZ esta sem acesso", "CIGAM")
    assert "XYZ" in query
    assert query.endswith("CIGAM")
    assert "PROBLEMA_ACESSO" not in query
```

- [ ] **Step 7: Write failing direct-vs-two-turn equivalence test**

```python
def test_direct_and_two_turn_access_reach_same_approved_knowledge() -> None:
    direct, _, direct_knowledge = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "CIGAM", {}, 0.9)],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    _, direct_result = direct.step(direct.initial_state(), "Nao consigo acessar o CIGAM")

    two_turn, _, two_knowledge = make_engine(
        [
            TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
            TicketClassification("OUTRO", "CIGAM", {}, 0.2),
        ],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state, first = two_turn.step(two_turn.initial_state(), "Nao consigo acessar")
    assert first["status"] == "NEEDS_CLARIFICATION"
    _, two_result = two_turn.step(state, "CIGAM")

    assert direct_result["knowledge"]["knowledge_id"] == "KB-SYN-CIGAM-ACCESS-001"
    assert two_result["knowledge"]["knowledge_id"] == "KB-SYN-CIGAM-ACCESS-001"
    assert direct_knowledge.search_calls[0][1].system == "CIGAM"
    assert two_knowledge.search_calls[0][1].system == "CIGAM"
```

- [ ] **Step 8: Write failing session and terminal-state tests**

```python
def test_session_mismatch_is_rejected_before_classifier() -> None:
    engine, classifier, _ = make_engine([], {}, session_id="session-a")
    foreign = new_triage_state("session-b")
    with pytest.raises(ValueError, match="session"):
        engine.step(foreign, "mensagem")
    assert classifier.calls == 0


@pytest.mark.parametrize("terminal", ["ANSWERED", "ABSTAINED"])
def test_terminal_state_cannot_be_reopened(terminal: str) -> None:
    engine, classifier, _ = make_engine([], {})
    state = dataclasses.replace(engine.initial_state(), status=terminal)
    with pytest.raises(ValueError, match="terminal"):
        engine.step(state, "outra mensagem")
    assert classifier.calls == 0


def test_two_sessions_do_not_share_state() -> None:
    engine_a, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
        session_id="session-a",
    )
    engine_b, _, _ = make_engine(
        [TicketClassification("PROBLEMA_IMPRESSAO", "", {}, 0.9)],
        {"PROBLEMA_IMPRESSAO": ("",)},
        session_id="session-b",
    )
    state_a, _ = engine_a.step(engine_a.initial_state(), "Nao consigo acessar")
    state_b, result_b = engine_b.step(engine_b.initial_state(), "A impressora nao imprime")
    assert state_a.session_id == "session-a"
    assert state_a.pending_field == "system"
    assert state_b.session_id == "session-b"
    assert result_b["status"] == "KNOWLEDGE_FOUND"
```

- [ ] **Step 9: Run transition tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: new engine/query/transition tests fail because those functions do not exist yet.

- [ ] **Step 10: Implement lexical query construction exactly**

Add `Callable` and `replace` only now if not already present. Use regular expressions only for exact known alias spans:

```python
def _alias_values(canonical: str) -> tuple[str, ...]:
    return (canonical, *SYSTEM_ALIASES.get(canonical, ()))


def _contains_system_text(text: str, system: str) -> bool:
    canonical = _canonical_for_exact_alias(system)
    values = _alias_values(canonical) if canonical else (system,)
    return any(
        re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE)
        for value in values
        if value
    )


def _remove_conflicting_known_system_aliases(text: str, final_system: str) -> str:
    final_canonical = _canonical_for_exact_alias(final_system)
    result = text
    if final_canonical is None:
        return result.strip()
    for canonical, aliases in SYSTEM_ALIASES.items():
        if canonical == final_canonical:
            continue
        for value in sorted((canonical, *aliases), key=len, reverse=True):
            result = re.sub(
                rf"(?<!\w){re.escape(value)}(?!\w)",
                "",
                result,
                flags=re.IGNORECASE,
            )
    return re.sub(r"\s+", " ", result).strip()


def build_knowledge_query(problem_text: str, system: str) -> str:
    text = problem_text.strip()
    if not system:
        return text
    reconciled = _remove_conflicting_known_system_aliases(text, system)
    if _contains_system_text(reconciled, system):
        return reconciled
    return reconciled + "\n" + system
```

Do not normalize/rewrite the rest of the problem beyond whitespace created by exact alias removal.

- [ ] **Step 11: Implement exact public result and clarification helpers**

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


def _found(knowledge: dict) -> dict:
    return {
        "status": "KNOWLEDGE_FOUND",
        "reason": "MATCH",
        "question": None,
        "knowledge": knowledge,
    }


def _mark_terminal(state: TriageState, status: str) -> TriageState:
    return replace(state, status=status, pending_field="")


def _ask_or_abstain(
    state: TriageState,
    field: str,
    reason: str,
    question: str,
) -> tuple[TriageState, dict]:
    if field in state.asked_fields:
        repeated_reason = {
            "MISSING_PROBLEM": "UNRESOLVED_PROBLEM",
            "AMBIGUOUS_SYSTEM": "AMBIGUOUS_SYSTEM",
            "UNKNOWN_SYSTEM": "UNKNOWN_SYSTEM",
        }.get(reason, "MAX_CLARIFICATIONS")
        terminal = _mark_terminal(state, "ABSTAINED")
        return terminal, _abstained(repeated_reason)
    if state.turn_count >= MAX_USER_TURNS:
        terminal = _mark_terminal(state, "ABSTAINED")
        return terminal, _abstained("MAX_TURNS")
    if state.clarification_count >= MAX_CLARIFICATIONS:
        terminal = _mark_terminal(state, "ABSTAINED")
        return terminal, _abstained("MAX_CLARIFICATIONS")
    asked = state.asked_fields + (field,)
    next_state = replace(
        state,
        clarification_count=state.clarification_count + 1,
        pending_field=field,
        asked_fields=asked,
    )
    return next_state, _clarification(reason, question)
```

- [ ] **Step 12: Implement exact system-availability predicates**

```python
def _known_alias_system(system: str) -> bool:
    return bool(system and _canonical_for_exact_alias(system))


def _unknown_system(system: str, available: tuple[str, ...]) -> bool:
    return bool(system) and not _known_alias_system(system) and system not in available
```

A known canonical system absent from `available` is not called unknown; it proceeds to Phase 4 so `SYSTEM_MISMATCH` can remain authoritative.

- [ ] **Step 13: Implement `TriageEngine.step()` in the approved order**

```python
class TriageEngine:
    def __init__(
        self,
        session_id: str,
        knowledge_engine,
        classifier: Callable[[str], TicketClassification],
    ):
        self.session_id = new_triage_state(session_id).session_id
        self.knowledge_engine = knowledge_engine
        self.classifier = classifier

    def initial_state(self) -> TriageState:
        return new_triage_state(self.session_id)

    def step(self, state: TriageState, message: str) -> tuple[TriageState, dict]:
        if state.session_id != self.session_id:
            raise ValueError("session_id nao corresponde a esta triagem.")
        if state.status != "ACTIVE":
            raise ValueError("Estado terminal nao pode ser reaberto.")
        if state.turn_count >= MAX_USER_TURNS:
            raise ValueError("Limite de turnos atingido.")
        if not isinstance(message, str) or not message.strip() or len(message) > 3000:
            raise ValueError("Mensagem de triagem invalida.")

        classification = self.classifier(message)
        evidence = _analyze_turn(state, message, classification)
        counted = replace(state, turn_count=state.turn_count + 1)
        merged = _merge_turn(counted, message.strip(), evidence)

        if not merged.problem_text or not merged.intent or merged.intent == "OUTRO":
            return _ask_or_abstain(
                merged,
                "problem",
                "MISSING_PROBLEM",
                "O que esta acontecendo?",
            )

        available = self.knowledge_engine.available_systems(merged.intent)
        if not available:
            terminal = _mark_terminal(merged, "ABSTAINED")
            return terminal, _abstained("NO_APPROVED_KNOWLEDGE_FOR_INTENT")

        if len(evidence.explicit_systems) > 1 and evidence.correction is None:
            return _ask_or_abstain(
                merged,
                "system",
                "AMBIGUOUS_SYSTEM",
                "Qual sistema esta com o problema?",
            )

        if _unknown_system(merged.system, available):
            return _ask_or_abstain(
                merged,
                "system",
                "UNKNOWN_SYSTEM",
                "Qual e o sistema correto?",
            )

        if not merged.system and "" not in available:
            return _ask_or_abstain(
                merged,
                "system",
                "MISSING_SYSTEM",
                "Qual sistema esta com o problema?",
            )

        query = build_knowledge_query(merged.problem_text, merged.system)
        resolved = TicketClassification(
            merged.intent,
            merged.system,
            dict(merged.entities),
            merged.confidence,
        )
        result = self.knowledge_engine.search_classified(query, resolved)

        if result["status"] == "KNOWLEDGE_FOUND":
            terminal = _mark_terminal(merged, "ANSWERED")
            return terminal, _found(dict(result["knowledge"]))

        terminal = _mark_terminal(merged, "ABSTAINED")
        return terminal, _abstained(str(result["reason"]))
```

This method must never call `classify_ticket` directly in addition to the injected classifier. Production creates the injected callable from existing `classify_ticket`; tests inject `QueueClassifier`.

- [ ] **Step 14: Run all triage tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage.py -q
```

Expected: all state, parser, merge, availability, limit, query, isolation, terminal, and handoff tests pass.

- [ ] **Step 15: Run Phase 4 and triage together**

Run:

```bash
pytest tests/engine/test_knowledge_retrieval.py tests/engine/test_triage.py -q
```

Expected: both Phase 4 seam tests and Phase 5 triage tests pass in one process.

- [ ] **Step 16: Commit the triage engine**

```bash
git add src/ai_service_desk/engine/triage.py tests/engine/test_triage.py
git commit -m "feat: add deterministic conversational triage"
```

---

### Task 5: Add the 10 synthetic conversations and smoke runner

**Files:**
- Create: `tests/fixtures/phase5_triage_conversations.jsonl`
- Create: `src/ai_service_desk/engine/triage_smoke.py`
- Create: `tests/engine/test_triage_smoke.py`

**Interfaces:**
- Consumes: `TriageEngine`, `KnowledgeEngine`, `classify_ticket`, `OllamaClient`, `LocalEmbedder`, existing Phase 4 synthetic APPROVED index.
- Produces: `load_triage_cases(path) -> list[dict]` and `run_triage_smoke(index, cases_path, report_path, base_url=...) -> dict`.

- [ ] **Step 1: Create the exact synthetic JSONL fixture**

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

The `draft-only` case intentionally does not constrain `expected_reason`; Phase 5 may abstain before retrieval when there is no APPROVED article for the classified intent. It must assert only terminal abstention and no knowledge ID.

- [ ] **Step 2: Write failing fixture-schema tests**

```python
def test_phase5_fixture_has_exact_ten_unique_synthetic_cases() -> None:
    cases = load_triage_cases(FIXTURE)
    assert len(cases) == 10
    assert len({case["case_name"] for case in cases}) == 10
    assert all(1 <= len(case["turns"]) <= 3 for case in cases)
    assert all(case["expected_status"] in {"KNOWLEDGE_FOUND", "TRIAGE_ABSTAINED"} for case in cases)
```

- [ ] **Step 3: Write failing report-privacy test**

```python
def test_smoke_report_contains_only_safe_case_metadata(tmp_path: Path, monkeypatch) -> None:
    report = run_fake_smoke(tmp_path, monkeypatch)
    assert report["ok"] is True
    assert len(report["cases"]) == 10
    allowed = {
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
    for case in report["cases"]:
        assert set(case) == allowed
        for forbidden in ("message", "messages", "turns", "transcript", "answer", "ticket_id"):
            assert forbidden not in case
    assert report["privacy"] == {
        "raw_text_included": False,
        "approved_content_included": False,
        "corporate_data_included": False,
    }
```

- [ ] **Step 4: Run smoke tests and verify RED**

Run:

```bash
pytest tests/engine/test_triage_smoke.py -q
```

Expected: fail because fixture and smoke module do not exist.

- [ ] **Step 5: Implement strict fixture loading**

```python
REQUIRED_CASE_FIELDS = {
    "case_name",
    "turns",
    "expected_status",
    "expected_knowledge_id",
    "expected_turn_count",
    "expected_clarification_count",
}
OPTIONAL_CASE_FIELDS = {"expected_reason", "requires_interleaved_control"}


def load_triage_cases(path: str | Path) -> list[dict]:
    source = Path(path)
    rows: list[dict] = []
    seen: set[str] = set()
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON invalido na linha {line_number}.") from exc
            if not isinstance(case, dict):
                raise ValueError("Caso de triagem deve ser objeto JSON.")
            keys = set(case)
            if (
                not REQUIRED_CASE_FIELDS <= keys
                or keys - REQUIRED_CASE_FIELDS - OPTIONAL_CASE_FIELDS
            ):
                raise ValueError("Campos invalidos no caso de triagem.")
            name = case["case_name"]
            if not isinstance(name, str) or not name.strip() or name in seen:
                raise ValueError("case_name invalido ou duplicado.")
            turns = case["turns"]
            if not isinstance(turns, list) or not 1 <= len(turns) <= MAX_USER_TURNS:
                raise ValueError("turns deve conter de 1 a 3 mensagens.")
            if any(not isinstance(turn, str) or not turn.strip() for turn in turns):
                raise ValueError("turn de triagem invalido.")
            seen.add(name)
            rows.append(case)
    if len(rows) != 10:
        raise ValueError("Smoke da Fase 5 exige exatamente 10 casos sinteticos.")
    return rows
```

- [ ] **Step 6: Implement smoke execution and safe summarization**

`run_triage_smoke()` owns the real client lifecycle, creates one validated `KnowledgeEngine`, and creates a fresh `TriageEngine`/state per case:

```python
client = OllamaClient(base_url)
embedder = LocalEmbedder(client)
knowledge = KnowledgeEngine(index, client, embedder)
classifier = lambda text: classify_ticket(text, client.chat)
```

For a normal case:

```python
engine = TriageEngine(f"synthetic-{case['case_name']}", knowledge, classifier)
state = engine.initial_state()
result = None
for message in case["turns"]:
    state, result = engine.step(state, message)
    if result["status"] != "NEEDS_CLARIFICATION":
        break
```

For `requires_interleaved_control`, execute session A turn 1, then a separate session B generic-printing triage, then session A turn 2. Assert A's state fields are unchanged by B except for A's own second turn.

Summarize only:

```python
summary = {
    "case_name": case["case_name"],
    "expected_status": case["expected_status"],
    "actual_status": result.get("status"),
    "reason": result.get("reason"),
    "expected_knowledge_id": case.get("expected_knowledge_id"),
    "actual_knowledge_id": (result.get("knowledge") or {}).get("knowledge_id"),
    "turn_count": state.turn_count,
    "clarification_count": state.clarification_count,
    "passed": bool(passed),
}
```

`passed` compares status, optional expected reason, optional expected knowledge ID, expected turn count, and expected clarification count. Never place `turns`, queries, answer text, transcript, or article text in the report.

Top-level report:

```python
report = {
    "schema_version": 1,
    "phase": 5,
    "domain": "CONVERSATIONAL_TRIAGE",
    "timestamp_utc": datetime.now(UTC).isoformat(),
    "ok": False,
    "cases": [],
    "privacy": {
        "raw_text_included": False,
        "approved_content_included": False,
        "corporate_data_included": False,
    },
}
```

Write with existing `atomic_json()` in `finally`, close the client, and set `ok` only when all 10 summaries pass.

- [ ] **Step 7: Run smoke unit tests and verify GREEN**

Run:

```bash
pytest tests/engine/test_triage_smoke.py -q
```

Expected: fixture validation, fake 10-case execution, interleaved isolation, and report privacy tests pass.

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

- [ ] **Step 1: Write failing parser/default test**

```python
def test_triage_smoke_parser_requires_index_cases_and_report() -> None:
    args = build_parser().parse_args(
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

- [ ] **Step 2: Write failing delegation/safe-output test**

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
    assert "Nao consigo acessar" not in output
```

- [ ] **Step 3: Run CLI tests and verify RED**

Run:

```bash
pytest tests/test_triage_cli.py -q
```

Expected: fail because `triage-smoke` is not registered.

- [ ] **Step 4: Add parser and delegation**

Add import:

```python
from ai_service_desk.engine.triage_smoke import run_triage_smoke
```

In `build_parser()`:

```python
triage_smoke = sub.add_parser("triage-smoke")
triage_smoke.add_argument("--index", type=Path, required=True)
triage_smoke.add_argument("--cases", type=Path, required=True)
triage_smoke.add_argument("--report", type=Path, required=True)
triage_smoke.add_argument("--url", default=DEFAULT_URL)
```

Before generic `OllamaClient(args.url)` construction in `main()`:

```python
if args.command == "triage-smoke":
    report = run_triage_smoke(args.index, args.cases, args.report, args.url)
    print("TRIAGE SMOKE OK" if report["ok"] else "TRIAGE SMOKE REQUER REVISAO")
    print(f"Casos sinteticos: {len(report.get('cases', []))}")
    print("Relatorio agregado local: " + str(args.report))
    return 0 if report["ok"] else 1
```

Do not add `--state`, `--transcript`, interactive history, or persistent sessions.

- [ ] **Step 5: Run triage CLI tests and verify GREEN**

Run:

```bash
pytest tests/test_triage_cli.py -q
```

Expected: pass without real Ollama.

- [ ] **Step 6: Run all CLI regression tests**

Run:

```bash
pytest tests/test_cli.py tests/test_knowledge_cli.py tests/test_triage_cli.py -q
```

Expected: all old and new CLI tests pass.

- [ ] **Step 7: Commit CLI wiring**

```bash
git add src/ai_service_desk/cli.py tests/test_triage_cli.py
git commit -m "feat: add phase 5 triage smoke CLI"
```

---

### Task 7: Add Dell workflow and documentation last

**Files:**
- Create: `.github/workflows/phase5-triage-smoke.yml`
- Modify: `tests/test_workflows.py`
- Create: `docs/triage/phase-5.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `triage-smoke`, existing Phase 4 synthetic FAQ, Phase 5 synthetic conversations, local Ollama.
- Produces: manual Dell homologation gate and operator documentation.

- [ ] **Step 1: Write failing workflow policy test**

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
    for forbidden in ("upload-artifact", "Get-Content", "--show-history"):
        assert forbidden not in text
```

- [ ] **Step 2: Run workflow test and verify RED**

Run:

```bash
pytest tests/test_workflows.py::test_phase5_triage_workflow_is_manual_local_and_non_exporting -q
```

Expected: fail because the workflow does not exist.

- [ ] **Step 3: Create the complete manual workflow**

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

    steps:
      - name: Checkout target ref
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.target_ref }}

      - name: Verify Python 3.14
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $version = python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
          Write-Host "Python: $version"
          if (-not $version.StartsWith("3.14.")) {
            throw "Phase 5 triage smoke requires Python 3.14.x. Found $version"
          }

      - name: Install project
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Verify local models
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m ai_service_desk doctor --url http://127.0.0.1:11434

      - name: Validate synthetic knowledge
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m ai_service_desk knowledge-validate `
            --file knowledge/phase4_synthetic_faq.jsonl

      - name: Build synthetic approved knowledge index
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $index = Join-Path $env:RUNNER_TEMP "phase5-knowledge-$env:GITHUB_RUN_ID"
          if (Test-Path $index) { Remove-Item -Recurse -Force $index }
          python -m ai_service_desk knowledge-index `
            --file knowledge/phase4_synthetic_faq.jsonl `
            --index "$index" `
            --batch-size 10 `
            --url http://127.0.0.1:11434

      - name: Run Phase 5 triage smoke
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $index = Join-Path $env:RUNNER_TEMP "phase5-knowledge-$env:GITHUB_RUN_ID"
          $report = Join-Path $env:RUNNER_TEMP "phase5-triage-$env:GITHUB_RUN_ID.json"
          python -m ai_service_desk triage-smoke `
            --index "$index" `
            --cases tests/fixtures/phase5_triage_conversations.jsonl `
            --report "$report" `
            --url http://127.0.0.1:11434
```

No artifact upload and no report-content printing.

- [ ] **Step 4: Run all workflow policy tests and verify GREEN**

Run:

```bash
pytest tests/test_workflows.py -q
```

Expected: all old workflow tests plus Phase 5 pass.

- [ ] **Step 5: Create Phase 5 operational documentation**

`docs/triage/phase-5.md` must contain these exact topics:
- purpose and non-goals;
- exact persisted `TriageState` fields;
- merge precedence summary;
- `MAX_USER_TURNS = 3`, `MAX_CLARIFICATIONS = 2`, turn-3 semantics;
- `NEEDS_CLARIFICATION`, `KNOWLEDGE_FOUND`, `TRIAGE_ABSTAINED` semantics;
- `search_classified()` and `available_systems()` boundaries;
- query restrictions and unchanged `0.65` threshold;
- session isolation and caller-owned persistence;
- no transcript/answer persistence;
- synthetic smoke instructions.

Document this command exactly:

```powershell
python -m ai_service_desk triage-smoke `
  --index C:\ai-service-desk-data\phase-5\index `
  --cases tests/fixtures/phase5_triage_conversations.jsonl `
  --report C:\ai-service-desk-data\phase-5\reports\smoke.json `
  --url http://127.0.0.1:11434
```

- [ ] **Step 6: Update README without changing prior phase claims**

Add a concise Phase 5 section describing short controlled multi-turn triage, APPROVED-only handoff, no ticket/action execution, limits, and `triage-smoke`. Do not rewrite Phase 1 to 4 claims.

- [ ] **Step 7: Run documentation-adjacent tests**

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

### Task 8: Final regression, privacy review, CI, and Dell homologation gate

**Files:**
- Review only all Phase 5 changed files.
- Any defect discovered here is fixed only by adding/reproducing a failing test first.

**Interfaces:**
- Consumes: Tasks 1 to 7 complete.
- Produces: evidence that Phase 5 is ready for user review without merge.

- [ ] **Step 1: Run focused Phase 5 tests**

```bash
pytest tests/engine/test_knowledge_retrieval.py tests/engine/test_triage.py tests/engine/test_triage_smoke.py tests/test_triage_cli.py tests/test_workflows.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run Ruff lint and formatting**

```bash
ruff check .
ruff format --check .
```

Expected: all checks pass.

- [ ] **Step 3: Run the complete regression suite**

```bash
pytest -q
```

Expected: all 177 pre-Phase-5 tests still pass plus every new Phase 5 test. If total collection is below 177, stop and investigate test loss.

- [ ] **Step 4: Verify protected files are untouched**

Compare branch against `491e5dd5f79dec8ff9a192a4929b48209956be3a`. These files must not appear in the diff:

```text
src/ai_service_desk/engine/classification.py
src/ai_service_desk/engine/retrieval.py
src/ai_service_desk/engine/index.py
src/ai_service_desk/engine/knowledge.py
```

If one changed, stop and document the required reproducible blocker, technical cause, minimal change, and regression risk before proceeding.

- [ ] **Step 5: Perform explicit privacy and scope review**

Verify changed files contain:
- no real corporate ticket text or identifiers;
- no generated `documents.jsonl`, `embeddings.npy`, real index, or real report artifacts;
- no transcript persistence;
- no `answer` field in `TriageState`;
- no historical `ticket_id` in triage result/report;
- no DRAFT/RETIRED answer path;
- no global session store;
- no ticket creation, playbook, policy, machine execution, or frontend code;
- no triage threshold override and no threshold other than the existing knowledge `0.65` path.

- [ ] **Step 6: Verify no second-classification path**

Use tests and code review to confirm:
- each accepted `TriageEngine.step()` invokes the injected classifier exactly once;
- turn 4, session mismatch, and terminal-state calls invoke it zero times;
- `search_classified()` invokes no classifier;
- existing `KnowledgeEngine.search()` still invokes `classify_ticket` once.

- [ ] **Step 7: Open/update the Phase 5 PR and require hosted CI on the final head**

Hosted CI is authoritative for Python 3.14, Ruff lint, Ruff format, and full pytest. Record final head SHA and total test count. Do not treat an isolated reconstructed environment as a substitute.

- [ ] **Step 8: Run Dell homologation on the same final head**

Use `.github/workflows/phase5-triage-smoke.yml` or equivalent manual PowerShell commands if first-time workflow dispatch is unavailable before merge. Required evidence:

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

Do not print or upload raw report contents.

- [ ] **Step 9: Final review checkpoint before merge approval**

Record:
- final head SHA;
- hosted CI result and full pytest count;
- Dell smoke result;
- changed-file list;
- protected files unchanged;
- no corporate data, temporary helpers, generated index, or report artifacts;
- PR open and unmerged.

Stop for explicit user approval. Do not merge and do not mark Phase 5 as 100% without that approval.
