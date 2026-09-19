import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from ai_service_desk.engine.classification import (
    SYSTEM_ALIASES,
    VocabularyResolver,
    explicit_systems,
)
from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_text

MAX_USER_TURNS = 3
MAX_CLARIFICATIONS = 2

_GENERIC_HELP_TEXTS = {"preciso de ajuda"}
_PROBLEM_NON_ANSWER_TEXTS = {"nao sei explicar"}


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


def _canonical_for_exact_alias(
    value: str, resolver: VocabularyResolver | None = None
) -> str | None:
    wanted = normalize_text(value).strip().strip(".!?")
    if resolver is not None:
        return resolver.canonical(wanted)
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


def _parse_system_correction(
    text: str, resolver: VocabularyResolver | None = None
) -> tuple[str, str] | None:
    normalized = normalize_text(text).strip()
    match = _CORRECTION_RE.fullmatch(normalized)
    if not match:
        return None
    old = _canonical_for_exact_alias(match.group(1), resolver)
    new = _canonical_for_exact_alias(match.group(2), resolver)
    systems = tuple(explicit_systems(text, resolver))
    if old is None or new is None or old == new:
        return None
    if len(systems) != 2 or set(systems) != {old, new}:
        return None
    return old, new


def _normalized_short_text(message: str) -> str:
    return normalize_text(message).strip().strip(".!?")


def _is_known_insufficient_problem(state: TriageState, message: str) -> bool:
    normalized = _normalized_short_text(message)
    if state.pending_field == "problem":
        return normalized in _PROBLEM_NON_ANSWER_TEXTS
    if not state.pending_field:
        return normalized in _GENERIC_HELP_TEXTS
    return False


def _is_short_system_reply(
    message: str,
    pending_field: str,
    classification: TicketClassification,
    prior_system: str = "",
    resolver: VocabularyResolver | None = None,
) -> bool:
    if pending_field != "system":
        return False
    if _parse_system_correction(message, resolver) is not None:
        return True
    normalized = _normalized_short_text(message)
    if _canonical_for_exact_alias(normalized, resolver) is not None:
        return True
    literal = normalize_text(classification.system).strip()
    if literal and (normalized == literal or normalized == f"sistema {literal}"):
        return True
    prior_literal = normalize_text(prior_system).strip()
    return bool(
        prior_literal and (normalized == prior_literal or normalized == f"sistema {prior_literal}")
    )


def _analyze_turn(
    state: TriageState,
    message: str,
    classification: TicketClassification,
    resolver: VocabularyResolver | None = None,
) -> TurnEvidence:
    correction = _parse_system_correction(message, resolver)
    systems = tuple(explicit_systems(message, resolver))
    if correction is not None:
        kind = "SYSTEM_CORRECTION"
    elif _is_short_system_reply(
        message,
        state.pending_field,
        classification,
        state.system,
        resolver,
    ):
        kind = "SYSTEM_SLOT"
    elif _is_known_insufficient_problem(state, message):
        kind = "INSUFFICIENT_PROBLEM"
    else:
        kind = "SUBSTANTIVE"
    return TurnEvidence(kind, systems, correction, classification)


def _system_from_slot(
    message: str,
    classification: TicketClassification,
    evidence: TurnEvidence,
    prior_system: str = "",
    resolver: VocabularyResolver | None = None,
) -> str:
    if evidence.correction is not None:
        return evidence.correction[1]
    canonical = _canonical_for_exact_alias(message, resolver)
    if canonical is not None:
        return canonical
    normalized = _normalized_short_text(message)
    if normalized.startswith("sistema "):
        normalized = normalized.removeprefix("sistema ").strip()
    literal = classification.system.strip()
    if literal and normalize_text(literal) == normalized:
        return literal
    if prior_system and normalize_text(prior_system).strip() == normalized:
        return prior_system
    return ""


def _merge_turn(
    state: TriageState,
    message: str,
    evidence: TurnEvidence,
    resolver: VocabularyResolver | None = None,
) -> TriageState:
    classification = evidence.classification

    if evidence.kind == "SYSTEM_CORRECTION":
        assert evidence.correction is not None
        entities = state.entities
        if resolver is not None:
            correction = _CORRECTION_RE.fullmatch(normalize_text(message).strip())
            assert correction is not None
            entities = {**entities, **resolver.entities(correction.group(2))}
        return replace(
            state,
            system=evidence.correction[1],
            entities=entities,
            pending_field="" if state.pending_field == "system" else state.pending_field,
        )

    if evidence.kind == "SYSTEM_SLOT":
        return replace(
            state,
            system=_system_from_slot(
                message,
                classification,
                evidence,
                state.system,
                resolver,
            ),
            pending_field="",
            entities=(
                {**state.entities, **resolver.entities(message)}
                if resolver is not None
                else state.entities
            ),
        )

    if evidence.kind == "INSUFFICIENT_PROBLEM":
        return replace(
            state,
            problem_text=message.strip(),
            intent="OUTRO",
            entities={},
            confidence=classification.confidence,
            pending_field="",
        )

    explicit = evidence.explicit_systems
    if state.pending_field == "system" and len(explicit) > 1:
        return replace(state, system="", pending_field="")

    if len(explicit) == 1:
        next_system = explicit[0]
    elif len(explicit) > 1:
        next_system = ""
    elif classification.system.strip():
        next_system = classification.system.strip()
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


def _alias_values(canonical: str, resolver: VocabularyResolver | None = None) -> tuple[str, ...]:
    if resolver is not None:
        return (canonical, *resolver.aliases(canonical))
    return (canonical, *SYSTEM_ALIASES.get(canonical, ()))


def _contains_system_text(
    text: str, system: str, resolver: VocabularyResolver | None = None
) -> bool:
    canonical = _canonical_for_exact_alias(system, resolver)
    values = _alias_values(canonical, resolver) if canonical else (system,)
    return any(
        re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE)
        for value in values
        if value
    )


def _remove_conflicting_known_system_aliases(
    text: str, final_system: str, resolver: VocabularyResolver | None = None
) -> str:
    final_canonical = _canonical_for_exact_alias(final_system, resolver)
    result = text
    if final_canonical is None:
        return result.strip()
    candidates = (
        ((name, resolver.aliases(name)) for name in resolver.systems(text))
        if resolver is not None
        else SYSTEM_ALIASES.items()
    )
    for canonical, aliases in candidates:
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


def build_knowledge_query(
    problem_text: str, system: str, resolver: VocabularyResolver | None = None
) -> str:
    text = problem_text.strip()
    if not system:
        return text
    reconciled = _remove_conflicting_known_system_aliases(text, system, resolver)
    if _contains_system_text(reconciled, system, resolver):
        return reconciled
    return reconciled + "\n" + system


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


def _known_alias_system(system: str, resolver: VocabularyResolver | None = None) -> bool:
    return bool(system and _canonical_for_exact_alias(system, resolver))


def _unknown_system(
    system: str, available: tuple[str, ...], resolver: VocabularyResolver | None = None
) -> bool:
    return bool(system) and not _known_alias_system(system, resolver) and system not in available


class TriageEngine:
    def __init__(
        self,
        session_id: str,
        knowledge_engine,
        classifier: Callable[[str], TicketClassification],
        *,
        resolver: VocabularyResolver | None = None,
    ):
        self.session_id = new_triage_state(session_id).session_id
        self.knowledge_engine = knowledge_engine
        self.classifier = classifier
        self.resolver = resolver

    def initial_state(self) -> TriageState:
        return new_triage_state(self.session_id)

    def step(
        self,
        state: TriageState,
        message: str,
        *,
        classification: TicketClassification | None = None,
    ) -> tuple[TriageState, dict]:
        if state.session_id != self.session_id:
            raise ValueError("session_id nao corresponde a esta triagem.")
        if state.status != "ACTIVE":
            raise ValueError("Estado terminal nao pode ser reaberto.")
        if state.turn_count >= MAX_USER_TURNS:
            raise ValueError("Limite de turnos atingido.")
        if not isinstance(message, str) or not message.strip() or len(message) > 3000:
            raise ValueError("Mensagem de triagem invalida.")

        resolved_classification = (
            classification if classification is not None else self.classifier(message)
        )
        evidence = _analyze_turn(
            state,
            message,
            resolved_classification,
            self.resolver,
        )
        counted = replace(state, turn_count=state.turn_count + 1)
        merged = _merge_turn(counted, message.strip(), evidence, self.resolver)

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

        if _unknown_system(merged.system, available, self.resolver):
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

        query = build_knowledge_query(merged.problem_text, merged.system, self.resolver)
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
