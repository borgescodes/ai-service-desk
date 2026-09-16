"""Evidence gates for the synthetic Phase 12 knowledge set."""

from time import perf_counter

from ai_service_desk.engine.knowledge_retrieval import KnowledgeEngine
from ai_service_desk.engine.validation import normalize_text

_REQUIRED_EVIDENCE = {
    "KB-SYN-M365-PASSWORD-001": frozenset({"senha"}),
}


class DemoKnowledgeEngine(KnowledgeEngine):
    """Keep synthetic similarity matches behind explicit user evidence."""

    def search_classified(self, text, classification) -> dict:
        started = perf_counter()
        try:
            return self._search_classified_impl(text, classification)
        finally:
            self.last_search_ms = max(
                0.0,
                (perf_counter() - started) * 1000,
            )

    def _search_classified_impl(self, text, classification) -> dict:
        retrieval_text = text
        if classification.system == "CDM" and classification.intent == "PROBLEMA_ACESSO":
            retrieval_text = f"{text} acesso CDM solicitar materiais revenda"

        result = super().search_classified(retrieval_text, classification)
        if result["status"] != "KNOWLEDGE_FOUND":
            return result

        knowledge = result["knowledge"]
        required = _REQUIRED_EVIDENCE.get(knowledge["knowledge_id"], frozenset())
        if not required:
            return result

        tokens = frozenset(normalize_text(text).split())
        if tokens & required:
            return result

        blocked = dict(result)
        blocked["status"] = "NO_APPROVED_KNOWLEDGE"
        blocked["reason"] = "KNOWLEDGE_EVIDENCE_MISMATCH"
        blocked["knowledge"] = None
        return blocked
