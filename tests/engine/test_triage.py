import dataclasses
from dataclasses import asdict

import pytest

from ai_service_desk.engine.triage import (
    MAX_CLARIFICATIONS,
    MAX_USER_TURNS,
    TriageEngine,
    _analyze_turn,
    _is_short_system_reply,
    _merge_turn,
    _parse_system_correction,
    build_knowledge_query,
    new_triage_state,
)
from ai_service_desk.engine.types import TicketClassification


def seeded_state(**changes):
    return dataclasses.replace(new_triage_state("session-a"), **changes)


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
            "threshold": 0.65,
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
    forbidden = {"transcript", "messages", "answer", "ticket_id", "score", "embedding"}
    assert not (forbidden & set(asdict(state)))


def test_invalid_session_id_is_rejected() -> None:
    for value in ("", "   ", "x" * 121):
        with pytest.raises(ValueError):
            new_triage_state(value)


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


def test_short_known_system_reply_is_slot_only_only_when_system_is_pending() -> None:
    classification = TicketClassification("OUTRO", "CIGAM", {}, 0.4)
    assert _is_short_system_reply("CIGAM", "system", classification)
    assert not _is_short_system_reply("CIGAM", "", classification)


def test_short_unknown_literal_reply_can_remain_slot_only() -> None:
    classification = TicketClassification("OUTRO", "XYZ", {}, 0.4)
    assert _is_short_system_reply("XYZ", "system", classification)
    assert _is_short_system_reply("sistema XYZ", "system", classification)


def test_correction_has_precedence_over_multiple_explicit_systems() -> None:
    state = dataclasses.replace(new_triage_state("session-a"), pending_field="system")
    classification = TicketClassification("OUTRO", "", {}, 0.3)
    evidence = _analyze_turn(state, "Nao e CIGAM, e SIAGRI", classification)
    assert evidence.kind == "SYSTEM_CORRECTION"
    assert evidence.explicit_systems == ("CIGAM", "SIAGRI")
    assert evidence.correction == ("CIGAM", "SIAGRI")


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


def test_substantive_replacement_discards_old_entities_and_changes_intent() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar o CIGAM",
        intent="PROBLEMA_ACESSO",
        system="CIGAM",
        entities={"filial": "003", "rotina": "1024"},
        confidence=0.91,
        asked_fields=("system",),
    )
    message = "na verdade o sistema trava ao salvar"
    evidence = _analyze_turn(
        state,
        message,
        TicketClassification("ERRO_SISTEMA", "", {"equipamento": "PC-1"}, 0.76),
    )
    merged = _merge_turn(state, message, evidence)
    assert merged.problem_text == message
    assert merged.intent == "ERRO_SISTEMA"
    assert merged.entities == {"equipamento": "PC-1"}
    assert merged.confidence == 0.76
    assert merged.system == "CIGAM"
    assert merged.asked_fields == ()


def test_new_explicit_system_replaces_old_system() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar",
        intent="PROBLEMA_ACESSO",
        system="CIGAM",
    )
    message = "na verdade o SIAGRI trava ao salvar"
    evidence = _analyze_turn(
        state,
        message,
        TicketClassification("ERRO_SISTEMA", "SIAGRI", {}, 0.8),
    )
    assert _merge_turn(state, message, evidence).system == "SIAGRI"


def test_multiple_explicit_systems_clear_old_system_without_correction() -> None:
    state = seeded_state(
        problem_text="Nao consigo acessar",
        intent="PROBLEMA_ACESSO",
        system="CIGAM",
    )
    message = "CIGAM e SIAGRI estao sem acesso"
    evidence = _analyze_turn(
        state,
        message,
        TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8),
    )
    assert _merge_turn(state, message, evidence).system == ""


def test_vague_problem_reply_preserves_problem_asked_marker() -> None:
    state = seeded_state(
        pending_field="problem",
        asked_fields=("problem",),
        problem_text="Preciso de ajuda",
        intent="OUTRO",
    )
    message = "Nao sei explicar"
    evidence = _analyze_turn(
        state,
        message,
        TicketClassification("OUTRO", "", {}, 0.8),
    )
    merged = _merge_turn(state, message, evidence)
    assert merged.intent == "OUTRO"
    assert merged.problem_text == message
    assert merged.asked_fields == ("problem",)


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
    assert (result["status"], result["reason"]) == (
        "NEEDS_CLARIFICATION",
        "MISSING_SYSTEM",
    )
    assert state.pending_field == "system"
    assert state.asked_fields == ("system",)
    assert knowledge.search_calls == []


def test_ambiguous_system_gets_one_clarification_then_terminal() -> None:
    engine, classifier, _ = make_engine(
        [
            TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
            TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
        ],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state, first = engine.step(
        engine.initial_state(),
        "CIGAM e SIAGRI estao sem acesso",
    )
    assert (first["status"], first["reason"]) == (
        "NEEDS_CLARIFICATION",
        "AMBIGUOUS_SYSTEM",
    )
    state, second = engine.step(state, "CIGAM e SIAGRI")
    assert (second["status"], second["reason"]) == (
        "TRIAGE_ABSTAINED",
        "AMBIGUOUS_SYSTEM",
    )
    assert state.status == "ABSTAINED"
    assert classifier.calls == 2


def test_unknown_system_gets_one_correction_opportunity_then_terminal() -> None:
    engine, _, _ = make_engine(
        [
            TicketClassification("PROBLEMA_ACESSO", "XYZ", {}, 0.9),
            TicketClassification("OUTRO", "XYZ", {}, 0.2),
        ],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    state, first = engine.step(engine.initial_state(), "O sistema XYZ esta sem acesso")
    assert (first["status"], first["reason"]) == (
        "NEEDS_CLARIFICATION",
        "UNKNOWN_SYSTEM",
    )
    state, second = engine.step(state, "XYZ")
    assert (second["status"], second["reason"]) == (
        "TRIAGE_ABSTAINED",
        "UNKNOWN_SYSTEM",
    )


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
    assert (result["status"], result["reason"]) == (
        "TRIAGE_ABSTAINED",
        "SYSTEM_MISMATCH",
    )
    assert len(knowledge.search_calls) == 1
    assert state.status == "ABSTAINED"


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


def test_turn_three_that_needs_question_abstains_with_max_turns() -> None:
    engine, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
    )
    state = dataclasses.replace(engine.initial_state(), turn_count=2)
    state, result = engine.step(state, "Nao consigo acessar")
    assert (result["status"], result["reason"]) == (
        "TRIAGE_ABSTAINED",
        "MAX_TURNS",
    )
    assert state.status == "ABSTAINED"


def test_third_clarification_is_never_emitted() -> None:
    engine, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, 0.8)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
    )
    state = dataclasses.replace(engine.initial_state(), clarification_count=2)
    _, result = engine.step(state, "Nao consigo acessar")
    assert (result["status"], result["reason"]) == (
        "TRIAGE_ABSTAINED",
        "MAX_CLARIFICATIONS",
    )
    assert result["question"] is None


@pytest.mark.parametrize("confidence", [0.01, 0.99])
def test_confidence_does_not_change_missing_system_transition(confidence: float) -> None:
    engine, _, _ = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "", {}, confidence)],
        {"PROBLEMA_ACESSO": ("CIGAM",)},
    )
    _, result = engine.step(engine.initial_state(), "Nao consigo acessar")
    assert (result["status"], result["reason"]) == (
        "NEEDS_CLARIFICATION",
        "MISSING_SYSTEM",
    )


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


def test_direct_and_two_turn_access_reach_same_approved_knowledge() -> None:
    direct, _, direct_knowledge = make_engine(
        [TicketClassification("PROBLEMA_ACESSO", "CIGAM", {}, 0.9)],
        {"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")},
    )
    _, direct_result = direct.step(
        direct.initial_state(),
        "Nao consigo acessar o CIGAM",
    )

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


def test_session_mismatch_is_rejected_before_classifier() -> None:
    engine, classifier, _ = make_engine([], {}, session_id="session-a")
    foreign = dataclasses.replace(engine.initial_state(), session_id="session-b")
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
    state_b, result_b = engine_b.step(
        engine_b.initial_state(),
        "A impressora nao imprime",
    )
    assert state_a.session_id == "session-a"
    assert state_a.pending_field == "system"
    assert state_b.session_id == "session-b"
    assert result_b["status"] == "KNOWLEDGE_FOUND"


def test_step_can_use_precomputed_classification_without_second_classifier_call():
    knowledge = FakeKnowledgeEngine({"PROBLEMA_ACESSO": ("CDM",)})
    calls = []

    def forbidden_classifier(text):
        calls.append(text)
        raise AssertionError("classifier must not be called")

    engine = TriageEngine(
        "session-precomputed",
        knowledge,
        forbidden_classifier,
    )
    state = engine.initial_state()
    classification = TicketClassification(
        "PROBLEMA_ACESSO",
        "CDM",
        {},
        0.9,
    )

    next_state, _ = engine.step(
        state,
        "Preciso acessar o CDM",
        classification=classification,
    )

    assert calls == []
    assert next_state.system == "CDM"
