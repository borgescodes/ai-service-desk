import dataclasses
from dataclasses import asdict

import pytest

from ai_service_desk.engine.triage import (
    MAX_CLARIFICATIONS,
    MAX_USER_TURNS,
    _analyze_turn,
    _is_short_system_reply,
    _merge_turn,
    _parse_system_correction,
    new_triage_state,
)
from ai_service_desk.engine.types import TicketClassification


def seeded_state(**changes):
    return dataclasses.replace(new_triage_state("session-a"), **changes)


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
