from pathlib import Path

from ai_service_desk.engine import knowledge_smoke


def test_knowledge_smoke_report_is_aggregate_and_content_free(tmp_path: Path, monkeypatch) -> None:
    results = {
        "cigam-access": {
            "status": "KNOWLEDGE_FOUND",
            "reason": "MATCH",
            "score": 0.9,
            "knowledge": {"knowledge_id": "KB-SYN-CIGAM-ACCESS-001", "answer": "SECRET-ANSWER"},
        },
        "siagri-access": {
            "status": "KNOWLEDGE_FOUND",
            "reason": "MATCH",
            "score": 0.88,
            "knowledge": {"knowledge_id": "KB-SYN-SIAGRI-ACCESS-001", "answer": "SECRET-ANSWER"},
        },
        "draft-only": {
            "status": "NO_APPROVED_KNOWLEDGE",
            "reason": "INTENT_MISMATCH",
            "score": None,
            "knowledge": None,
        },
        "unknown-system": {
            "status": "NO_APPROVED_KNOWLEDGE",
            "reason": "UNKNOWN_SYSTEM",
            "score": None,
            "knowledge": None,
        },
        "ambiguous": {
            "status": "NO_APPROVED_KNOWLEDGE",
            "reason": "CONTEXTO_AMBIGUO",
            "score": None,
            "knowledge": None,
        },
    }

    class FakeClient:
        def __init__(self, url: str) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeEmbedder:
        def __init__(self, client) -> None:
            pass

    class FakeEngine:
        def __init__(self, index, client, embedder) -> None:
            pass

        def search(self, text: str) -> dict:
            for case in knowledge_smoke.CASES:
                if case["query"] == text:
                    return results[case["name"]]
            raise AssertionError("unexpected query")

    monkeypatch.setattr(knowledge_smoke, "OllamaClient", FakeClient)
    monkeypatch.setattr(knowledge_smoke, "LocalEmbedder", FakeEmbedder)
    monkeypatch.setattr(knowledge_smoke, "KnowledgeEngine", FakeEngine)
    report_path = tmp_path / "report.json"
    report = knowledge_smoke.run_knowledge_smoke(tmp_path / "index", report_path)

    assert report["ok"] is True
    assert len(report["cases"]) == 5
    raw = report_path.read_text(encoding="utf-8")
    assert "SECRET-ANSWER" not in raw
    assert "query" not in raw
    assert "answer" not in raw
    assert "KB-SYN-CIGAM-ACCESS-001" in raw


def test_knowledge_smoke_marks_wrong_cross_system_result_failed(
    tmp_path: Path, monkeypatch
) -> None:
    class FakeClient:
        def __init__(self, url: str) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeEmbedder:
        def __init__(self, client) -> None:
            pass

    class FakeEngine:
        def __init__(self, index, client, embedder) -> None:
            pass

        def search(self, text: str) -> dict:
            return {
                "status": "KNOWLEDGE_FOUND",
                "reason": "MATCH",
                "score": 0.99,
                "knowledge": {"knowledge_id": "KB-SYN-CIGAM-ACCESS-001", "answer": "hidden"},
            }

    monkeypatch.setattr(knowledge_smoke, "OllamaClient", FakeClient)
    monkeypatch.setattr(knowledge_smoke, "LocalEmbedder", FakeEmbedder)
    monkeypatch.setattr(knowledge_smoke, "KnowledgeEngine", FakeEngine)
    report = knowledge_smoke.run_knowledge_smoke(tmp_path / "index", tmp_path / "report.json")
    assert report["ok"] is False
    siagri = next(case for case in report["cases"] if case["name"] == "siagri-access")
    assert siagri["passed"] is False
