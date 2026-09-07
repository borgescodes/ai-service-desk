import dataclasses
from dataclasses import asdict

import pytest

from ai_service_desk.engine.triage import (
    MAX_CLARIFICATIONS,
    MAX_USER_TURNS,
    _analyze_turn,
    _is_short_system_reply,
    _parse_system_correction,
    new_triage_state,
)
from ai_service_desk.engine.types import TicketClassification


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
