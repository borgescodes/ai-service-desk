import json
from pathlib import Path

import numpy as np
import pandas as pd

from ai_service_desk.engine.knowledge import build_knowledge_index
from ai_service_desk.engine.knowledge_retrieval import KnowledgeEngine, retrieve_knowledge
from ai_service_desk.engine.types import TicketClassification


def classification(intent: str = "PROBLEMA_ACESSO", system: str = "CIGAM") -> TicketClassification:
    return TicketClassification(intent, system, {}, 0.9)


def knowledge_data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "knowledge_id": "KB-CIGAM",
                "title": "Acesso CIGAM",
                "answer": "Passo 1: use APENAS o ambiente ficticio. Depois, confirme: OK?",
                "system": "CIGAM",
                "intent": "PROBLEMA_ACESSO",
                "version": 1,
            },
            {
                "knowledge_id": "KB-SIAGRI",
                "title": "Acesso SIAGRI",
                "answer": "Resposta SIAGRI sintetica.",
                "system": "SIAGRI",
                "intent": "PROBLEMA_ACESSO",
                "version": 1,
            },
            {
                "knowledge_id": "KB-PRINT",
                "title": "Fila de impressao",
                "answer": "Resposta de impressao sintetica.",
                "system": "",
                "intent": "PROBLEMA_IMPRESSAO",
                "version": 1,
            },
        ]
    )


def matrix() -> np.ndarray:
    return np.asarray([[1.0, 0.0], [0.99, 0.1], [0.8, 0.6]], dtype=np.float32)


def test_retrieval_returns_literal_answer_and_public_identifier_only() -> None:
    data = knowledge_data()
    result = retrieve_knowledge(
        data,
        matrix(),
        np.asarray([1.0, 0.0], dtype=np.float32),
        classification(),
        "Nao consigo acessar o CIGAM",
    )
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert result["reason"] == "MATCH"
    assert result["knowledge"]["knowledge_id"] == "KB-CIGAM"
    assert result["knowledge"]["answer"] == data.iloc[0].answer
    assert "ticket_id" not in result["knowledge"]
    assert result["threshold"] == 0.65


def test_other_system_is_never_used_even_with_higher_similarity() -> None:
    data = knowledge_data()
    query = np.asarray([0.99, 0.1], dtype=np.float32)
    result = retrieve_knowledge(data, matrix(), query, classification(), "Acesso no CIGAM")
    assert result["knowledge"]["knowledge_id"] == "KB-CIGAM"


def test_ambiguous_context_abstains_before_matching() -> None:
    result = retrieve_knowledge(
        knowledge_data(),
        matrix(),
        np.asarray([1.0, 0.0], dtype=np.float32),
        classification(system=""),
        "CIGAM e SIAGRI estao sem acesso",
    )
    assert result["status"] == "NO_APPROVED_KNOWLEDGE"
    assert result["reason"] == "CONTEXTO_AMBIGUO"
    assert result["knowledge"] is None


def test_unknown_system_abstains_without_cross_system_fallback() -> None:
    result = retrieve_knowledge(
        knowledge_data(),
        matrix(),
        np.asarray([1.0, 0.0], dtype=np.float32),
        classification(system="XYZ"),
        "O sistema XYZ esta sem acesso",
    )
    assert result["status"] == "NO_APPROVED_KNOWLEDGE"
    assert result["reason"] == "UNKNOWN_SYSTEM"


def test_known_system_without_matching_article_reports_system_mismatch() -> None:
    data = knowledge_data().query("system != 'CIGAM'").reset_index(drop=True)
    result = retrieve_knowledge(
        data,
        matrix()[[1, 2]],
        np.asarray([1.0, 0.0], dtype=np.float32),
        classification(system="CIGAM"),
        "Acesso no CIGAM",
    )
    assert result["status"] == "NO_APPROVED_KNOWLEDGE"
    assert result["reason"] == "SYSTEM_MISMATCH"


def test_intent_mismatch_never_falls_back_to_another_intent() -> None:
    result = retrieve_knowledge(
        knowledge_data(),
        matrix(),
        np.asarray([1.0, 0.0], dtype=np.float32),
        classification(intent="ERRO_SISTEMA"),
        "CIGAM apresenta erro",
    )
    assert result["status"] == "NO_APPROVED_KNOWLEDGE"
    assert result["reason"] == "INTENT_MISMATCH"


def test_below_threshold_abstains() -> None:
    result = retrieve_knowledge(
        knowledge_data(),
        matrix(),
        np.asarray([0.0, 1.0], dtype=np.float32),
        classification(),
        "Acesso CIGAM",
    )
    assert result["status"] == "NO_APPROVED_KNOWLEDGE"
    assert result["reason"] == "BELOW_THRESHOLD"
    assert result["knowledge"] is None


def test_query_without_system_only_uses_generic_articles() -> None:
    result = retrieve_knowledge(
        knowledge_data(),
        matrix(),
        np.asarray([0.8, 0.6], dtype=np.float32),
        classification(intent="PROBLEMA_IMPRESSAO", system=""),
        "A impressora nao imprime",
    )
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert result["knowledge"]["knowledge_id"] == "KB-PRINT"


class FakeEmbedder:
    model = "qwen3-embedding:0.6b"
    digest = "phase4-engine-digest"
    dimensions = 2

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        return np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))


class FakeClient:
    def __init__(self, system: str = "CIGAM", intent: str = "PROBLEMA_ACESSO") -> None:
        self.system = system
        self.intent = intent
        self.chat_calls = 0

    def chat(self, payload: dict) -> dict:
        self.chat_calls += 1
        return {
            "message": {
                "content": json.dumps(
                    {
                        "intent": self.intent,
                        "system": self.system,
                        "entities": {},
                        "confidence": 0.9,
                    }
                )
            }
        }


def article(
    knowledge_id: str = "KB-CIGAM",
    system: str = "CIGAM",
    intent: str = "PROBLEMA_ACESSO",
) -> dict:
    return {
        "knowledge_id": knowledge_id,
        "title": f"Artigo sintetico {knowledge_id}",
        "question": f"Pergunta sintetica {knowledge_id}.",
        "answer": f"Resposta literal aprovada {knowledge_id}.",
        "system": system,
        "intent": intent,
        "tags": ["sintetico"],
        "source": "SYNTHETIC_DEMO",
        "status": "APPROVED",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-09-07T12:00:00-03:00",
        "version": 1,
    }


def write_source(path: Path) -> Path:
    path.write_text(json.dumps(article()) + "\n", encoding="utf-8")
    return path


def write_articles(path: Path, articles: list[dict]) -> Path:
    path.write_text("".join(json.dumps(item) + "\n" for item in articles), encoding="utf-8")
    return path


def build_engine_with_articles(tmp_path: Path, articles: list[dict]) -> KnowledgeEngine:
    embedder = FakeEmbedder()
    root = tmp_path / "index"
    source = write_articles(tmp_path / "knowledge.jsonl", articles)
    build_knowledge_index(source, root, embedder, batch_size=10)
    embedder.calls.clear()
    return KnowledgeEngine(root, FakeClient(), embedder)


def test_engine_loads_only_valid_knowledge_index_and_searches_once(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    root = tmp_path / "index"
    build_knowledge_index(write_source(tmp_path / "knowledge.jsonl"), root, embedder, batch_size=1)
    embedder.calls.clear()
    client = FakeClient()
    engine = KnowledgeEngine(root, client, embedder)
    result = engine.search("Nao consigo acessar o CIGAM")
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert client.chat_calls == 1
    assert len(embedder.calls) == 1


def test_engine_ambiguous_context_does_not_embed(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    root = tmp_path / "index"
    build_knowledge_index(write_source(tmp_path / "knowledge.jsonl"), root, embedder, batch_size=1)
    embedder.calls.clear()
    client = FakeClient(system="")
    engine = KnowledgeEngine(root, client, embedder)
    result = engine.search("CIGAM e SIAGRI estao sem acesso")
    assert result["reason"] == "CONTEXTO_AMBIGUO"
    assert embedder.calls == []


def test_search_and_search_classified_are_equivalent_for_same_classification(tmp_path: Path) -> None:
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
