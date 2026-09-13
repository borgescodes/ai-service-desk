import inspect
import json

import numpy as np
import pandas as pd
import pytest

from ai_service_desk.engine.classification import classify_ticket
from ai_service_desk.engine.knowledge_retrieval import retrieve_knowledge
from ai_service_desk.engine.triage import TriageEngine
from ai_service_desk.engine.types import TicketClassification


class NeutralVocabulary:
    """Synthetic names prove the extension has no dependency on demo terminology."""

    def canonical(self, value):
        return {"alpha": "SUITE", "suite": "SUITE", "beta": "OTHER", "other": "OTHER"}.get(
            value.casefold()
        )

    def systems(self, text):
        words = text.casefold().replace(",", " ").split()
        return tuple(dict.fromkeys(self.canonical(w) for w in words if self.canonical(w)))

    def aliases(self, system):
        return {"SUITE": ("alpha", "suite"), "OTHER": ("beta",)}.get(system, (system,))

    def entities(self, text):
        return {"product": "ALPHA"} if "alpha" in text.casefold().split() else {}


def chat(payload):
    return {
        "message": {
            "content": json.dumps(
                {
                    "intent": "PROBLEMA_ACESSO",
                    "system": "SUITE",
                    "entities": {"product": "FORGED"},
                    "confidence": 0.9,
                }
            )
        }
    }


def require_extension(callable_):
    assert "resolver" in inspect.signature(callable_).parameters, "neutral injection missing"


def test_classifier_consumes_injected_evidence_without_rewriting_user_input():
    require_extension(classify_ticket)
    captured = []

    def capture(payload):
        captured.append(payload["messages"][-1]["content"])
        return chat(payload)

    result = classify_ticket("alpha sem acesso", capture, resolver=NeutralVocabulary())
    assert result.system == "SUITE"
    assert result.entities["product"] == "ALPHA"
    assert captured == ["alpha sem acesso"]


def test_classifier_without_injection_preserves_literal_legacy_behavior():
    assert classify_ticket("alpha sem acesso", chat).system == ""


class NoKnowledge:
    def available_systems(self, intent):
        return ("EXISTING_ARTICLE",)

    def search_classified(self, text, classification):
        return {"status": "NO_APPROVED_KNOWLEDGE", "reason": "SYSTEM_MISMATCH"}


@pytest.mark.parametrize("injected", [False, True])
def test_known_vocabulary_is_distinct_from_article_availability(injected):
    kwargs = {}
    if injected:
        require_extension(TriageEngine)
        kwargs["resolver"] = NeutralVocabulary()
    engine = TriageEngine(
        "test",
        NoKnowledge(),
        lambda _: TicketClassification("PROBLEMA_ACESSO", "SUITE", {}, 0.9),
        **kwargs,
    )
    state, result = engine.step(engine.initial_state(), "alpha sem acesso")
    assert state.system == "SUITE"
    assert result["reason"] == ("SYSTEM_MISMATCH" if injected else "UNKNOWN_SYSTEM")
    assert result["status"] == ("TRIAGE_ABSTAINED" if injected else "NEEDS_CLARIFICATION")


@pytest.mark.parametrize("injected", [False, True])
def test_retrieval_alias_matching_is_opt_in_and_answer_stays_literal(injected):
    kwargs = {}
    if injected:
        require_extension(retrieve_knowledge)
        kwargs["resolver"] = NeutralVocabulary()
    data = pd.DataFrame(
        [
            {
                "knowledge_id": "KB",
                "title": "Synthetic",
                "answer": "Literal. Não completar!",
                "system": "alpha",
                "intent": "PROBLEMA_ACESSO",
                "version": 1,
            }
        ]
    )
    result = retrieve_knowledge(
        data,
        np.array([[1.0]]),
        np.array([1.0]),
        TicketClassification("PROBLEMA_ACESSO", "SUITE", {}, 0.9),
        "alpha sem acesso",
        **kwargs,
    )
    if injected:
        assert result["knowledge"]["answer"] == "Literal. Não completar!"
    else:
        assert result["reason"] == "UNKNOWN_SYSTEM"


def test_injected_triage_corrects_system_without_replacing_original_problem():
    require_extension(TriageEngine)
    engine = TriageEngine(
        "test",
        NoKnowledge(),
        lambda _: TicketClassification("PROBLEMA_ACESSO", "", {}, 0.9),
        resolver=NeutralVocabulary(),
    )
    state, result = engine.step(engine.initial_state(), "alpha e beta sem acesso")
    assert result["reason"] == "AMBIGUOUS_SYSTEM"
    corrected, result = engine.step(state, "Não é alpha, é beta")
    assert corrected.system == "OTHER"
    assert corrected.problem_text == "alpha e beta sem acesso"
    assert result["reason"] == "SYSTEM_MISMATCH"
