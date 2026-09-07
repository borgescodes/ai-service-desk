from ai_service_desk.engine.triage import TriageEngine
from ai_service_desk.engine.types import TicketClassification


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
    def __init__(self, systems_by_intent: dict[str, tuple[str, ...]]):
        self.systems_by_intent = systems_by_intent
        self.search_calls: list[tuple[str, TicketClassification]] = []

    def available_systems(self, intent: str) -> tuple[str, ...]:
        return self.systems_by_intent.get(intent, ())

    def search_classified(self, text: str, classification: TicketClassification) -> dict:
        self.search_calls.append((text, classification))
        raise AssertionError("knowledge search must not run in these regressions")


def test_unknown_system_repeat_stays_in_system_slot_when_llm_drops_literal() -> None:
    classifier = QueueClassifier(
        [
            TicketClassification("PROBLEMA_ACESSO", "XYZ", {}, 0.95),
            TicketClassification("OUTRO", "", {}, 0.5),
        ]
    )
    knowledge = FakeKnowledgeEngine({"PROBLEMA_ACESSO": ("CIGAM", "SIAGRI")})
    engine = TriageEngine("session-unknown", knowledge, classifier)

    state, first = engine.step(engine.initial_state(), "O sistema XYZ esta sem acesso.")
    assert (first["status"], first["reason"]) == (
        "NEEDS_CLARIFICATION",
        "UNKNOWN_SYSTEM",
    )

    state, second = engine.step(state, "XYZ")

    assert (second["status"], second["reason"]) == (
        "TRIAGE_ABSTAINED",
        "UNKNOWN_SYSTEM",
    )
    assert state.status == "ABSTAINED"
    assert state.system == "XYZ"
    assert state.intent == "PROBLEMA_ACESSO"
    assert state.problem_text == "O sistema XYZ esta sem acesso."
    assert state.clarification_count == 1
    assert classifier.calls == 2
    assert knowledge.search_calls == []


def test_approved_anti_loop_phrases_ignore_orientation_false_positive() -> None:
    classifier = QueueClassifier(
        [
            TicketClassification("ORIENTACAO", "", {}, 0.95),
            TicketClassification("ORIENTACAO", "", {}, 0.95),
        ]
    )
    knowledge = FakeKnowledgeEngine({"ORIENTACAO": ("OUTLOOK",)})
    engine = TriageEngine("session-vague", knowledge, classifier)

    state, first = engine.step(engine.initial_state(), "Preciso de ajuda.")
    assert (first["status"], first["reason"]) == (
        "NEEDS_CLARIFICATION",
        "MISSING_PROBLEM",
    )

    state, second = engine.step(state, "Nao sei explicar.")

    assert (second["status"], second["reason"]) == (
        "TRIAGE_ABSTAINED",
        "UNRESOLVED_PROBLEM",
    )
    assert state.status == "ABSTAINED"
    assert state.turn_count == 2
    assert state.clarification_count == 1
    assert classifier.calls == 2
    assert knowledge.search_calls == []
