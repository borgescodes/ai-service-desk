import re
from dataclasses import dataclass, replace

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


def _canonical_for_exact_alias(value: str) -> str | None:
    wanted = normalize_text(value).strip().strip(".!?")
    matches = {
        canonical
        for canonical, aliases in SYSTEM_ALIASES.items()
        if wanted in {normalize_text(canonical), *(normalize_text(alias) for alias in aliases)}
    }
    return next(iter(matches)) if len(matches) == 1 else None


_CORRECTION_RE = re.compile(
    r"^nao\s+e\s+(.+?)\s*,?\s+e\s+(.+?)\s*[.!?]?$",
    re.IGNORECASE,
)


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


def _merge_turn(
    state: TriageState,
    message: str,
    evidence: TurnEvidence,
) -> TriageState:
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
