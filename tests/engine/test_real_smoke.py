from pathlib import Path

import numpy as np
import pytest

from ai_service_desk.engine import real_smoke
from ai_service_desk.engine.data import load_corpus
from ai_service_desk.engine.index import build_index

FIXTURE = Path("tests/fixtures/phase2_corpus.csv")


class FakeEmbedder:
    model = "synthetic-embedder"
    digest = "digest-v1"
    dimensions = 4

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            [[len(text) + 1, 1, 2, 3] for text in texts],
            dtype=np.float32,
        )


def test_validate_real_index_reports_shape_and_integrity_without_documents(tmp_path: Path) -> None:
    data = load_corpus(FIXTURE)
    state = build_index(data, tmp_path / "index", FakeEmbedder(), batch_size=2)

    report = real_smoke.validate_real_index(
        tmp_path / "index",
        {
            "rows": 3,
            "dimensions": 4,
            "model": "synthetic-embedder",
            "model_digest": "digest-v1",
            "recipe": "texto_busca-plain-v1",
            "source_hash": state["source_hash"],
        },
    )

    assert report["rows"] == 3
    assert report["shape"] == [3, 4]
    assert report["finite"] is True
    assert report["normalized"] is True
    assert report["complete"] is True
    assert report["self_similarity"] > 0.999
    assert "documents" not in report
    assert "ticket_id" not in str(report)


def test_validate_real_index_rejects_expected_mismatch(tmp_path: Path) -> None:
    data = load_corpus(FIXTURE)
    build_index(data, tmp_path / "index", FakeEmbedder(), batch_size=2)

    with pytest.raises(ValueError, match="Indice real divergente"):
        real_smoke.validate_real_index(
            tmp_path / "index",
            {
                "rows": 4,
                "dimensions": 4,
                "model": "synthetic-embedder",
                "model_digest": "digest-v1",
                "recipe": "texto_busca-plain-v1",
            },
        )


class FakeEngine:
    def search(self, query: str) -> dict:
        if query.startswith("No CIGAM"):
            return {
                "classification": {"system": "CIGAM", "intent": "ERRO_SISTEMA"},
                "status": "ENCONTRADOS",
                "candidates": [
                    {
                        "ticket_number": "9999",
                        "title": "conteudo proibido",
                        "catalogo": "Sistemas",
                        "area": "CIGAM",
                        "item": "ERP",
                        "texto_busca": "conteudo proibido",
                        "historico_atendimento": "conteudo proibido",
                    }
                ],
                "best_score": 0.81,
                "pool_size": 12,
            }
        if query.startswith("No SIAGRI"):
            return {
                "classification": {"system": "SIAGRI", "intent": "ERRO_SISTEMA"},
                "status": "SEM_EVIDENCIA",
                "candidates": [],
                "best_score": 0.61,
                "pool_size": 8,
            }
        if query.startswith("No sistema XYZ"):
            return {
                "classification": {"system": "XYZ", "intent": "ERRO_SISTEMA"},
                "status": "SEM_CONTEXTO",
                "candidates": [],
                "best_score": None,
                "pool_size": 0,
            }
        if query.startswith("CIGAM e SIAGRI"):
            return {
                "classification": {"system": "", "intent": "ERRO_SISTEMA"},
                "status": "CONTEXTO_AMBIGUO",
                "candidates": [],
                "best_score": None,
                "pool_size": 0,
            }
        return {
            "classification": {"system": "", "intent": "PROBLEMA_IMPRESSAO"},
            "status": "SEM_EVIDENCIA",
            "candidates": [],
            "best_score": 0.42,
            "pool_size": 4,
        }


def _cases() -> list[dict]:
    return [
        {
            "name": "cigam",
            "query": "No CIGAM aparece erro ao abrir uma rotina de exemplo.",
            "expected_system": "CIGAM",
            "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
        },
        {
            "name": "siagri",
            "query": "No SIAGRI aparece erro ao abrir uma rotina de exemplo.",
            "expected_system": "SIAGRI",
            "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
        },
        {
            "name": "unknown",
            "query": "No sistema XYZ aparece um erro de exemplo.",
            "expected_system": "XYZ",
            "allowed_statuses": ["SEM_CONTEXTO"],
            "expected_candidates": 0,
        },
        {
            "name": "ambiguous",
            "query": "CIGAM e SIAGRI apresentam um erro de exemplo.",
            "allowed_statuses": ["CONTEXTO_AMBIGUO"],
            "expected_candidates": 0,
        },
        {
            "name": "printing",
            "query": "A impressora de exemplo nao imprime.",
            "expected_intent": "PROBLEMA_IMPRESSAO",
            "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
        },
    ]


def test_run_safe_queries_projects_only_aggregate_invariants() -> None:
    report = real_smoke.run_safe_queries(FakeEngine(), _cases())

    assert len(report) == 5
    assert all(item["ok"] for item in report)
    serialized = str(report)
    for forbidden in ("ticket_number", "title", "texto_busca", "historico_atendimento"):
        assert forbidden not in serialized
    assert "conteudo proibido" not in serialized


def test_run_safe_queries_marks_wrong_system_candidate_as_failure() -> None:
    class WrongSystemEngine(FakeEngine):
        def search(self, query: str) -> dict:
            result = super().search(query)
            if query.startswith("No CIGAM"):
                result["candidates"][0]["area"] = "SIAGRI"
                result["candidates"][0]["texto_busca"] = "Falha apenas no SIAGRI"
            return result

    report = real_smoke.run_safe_queries(WrongSystemEngine(), _cases()[:1])

    assert report[0]["ok"] is False
    assert report[0]["candidate_systems_ok"] is False


def test_build_real_smoke_report_is_aggregate_and_uses_fixed_threshold() -> None:
    report = real_smoke.build_real_smoke_report(
        {"rows": 3, "manifest_match": True},
        {"rows": 3, "shape": [3, 4], "complete": True},
        [{"name": "cigam", "ok": True}],
    )

    assert report["ok"] is True
    assert report["threshold"] == 0.65
    assert report["privacy"] == {
        "contains_ticket_content": False,
        "contains_ticket_identifiers": False,
        "history_displayed": False,
    }


def test_run_real_smoke_orchestrates_aggregate_pipeline(tmp_path: Path, monkeypatch) -> None:
    external = tmp_path / "external"
    checkout = tmp_path / "repo"
    corpus = external / "corpus.csv"
    index = external / "index"
    report_path = external / "report.json"
    external.mkdir()
    checkout.mkdir()

    calls: list[tuple] = []
    written: dict = {}

    def fake_external_path(path, checkout_path):
        calls.append(("external", Path(path), Path(checkout_path)))
        return Path(path).resolve()

    def fake_audit(corpus_path, manifest_path):
        calls.append(("audit", Path(corpus_path), Path(manifest_path)))
        return {
            "rows": 3,
            "manifest_match": True,
            "canonical_sha256": "canonical-v1",
        }

    def fake_manifest(_path):
        return {
            "expected": {
                "rows": 3,
                "canonical_sha256": "canonical-v1",
            }
        }

    class FakeClient:
        def __init__(self, base_url):
            calls.append(("client", base_url))
            self.closed = False

        def model_info(self, model):
            calls.append(("model_info", model))
            return {"digest": "digest-v1"}

        def close(self):
            self.closed = True
            calls.append(("close",))

    class FakeLocalEmbedder:
        model = "qwen3-embedding:0.6b"
        digest = "digest-v1"
        dimensions = 1024

        def __init__(self, client):
            calls.append(("embedder", client))

    def fake_load_corpus(path):
        calls.append(("load_corpus", Path(path)))
        return "prepared-data"

    def fake_build_index(data, directory, embedder):
        calls.append(("build_index", data, Path(directory), embedder))
        return {"complete": True}

    class FakeRetrievalEngine(FakeEngine):
        def __init__(self, directory, client, embedder, threshold):
            calls.append(("engine", Path(directory), client, embedder, threshold))

    def fake_validate_index(directory, expected):
        calls.append(("validate_index", Path(directory), expected))
        return {
            "rows": 3,
            "shape": [3, 1024],
            "complete": True,
        }

    def fake_safe_queries(engine, cases):
        calls.append(("queries", engine, cases))
        return [{"name": case["name"], "ok": True} for case in cases]

    def fake_write_report(path, report):
        written["path"] = Path(path)
        written["report"] = report
        calls.append(("write", Path(path)))

    monkeypatch.setattr(real_smoke, "ensure_external_path", fake_external_path, raising=False)
    monkeypatch.setattr(real_smoke, "audit_corpus", fake_audit, raising=False)
    monkeypatch.setattr(real_smoke, "load_corpus_manifest", fake_manifest, raising=False)
    monkeypatch.setattr(real_smoke, "OllamaClient", FakeClient, raising=False)
    monkeypatch.setattr(real_smoke, "LocalEmbedder", FakeLocalEmbedder, raising=False)
    monkeypatch.setattr(real_smoke, "load_corpus", fake_load_corpus, raising=False)
    monkeypatch.setattr(real_smoke, "build_index", fake_build_index, raising=False)
    monkeypatch.setattr(real_smoke, "RetrievalEngine", FakeRetrievalEngine, raising=False)
    monkeypatch.setattr(real_smoke, "validate_real_index", fake_validate_index)
    monkeypatch.setattr(real_smoke, "run_safe_queries", fake_safe_queries)
    monkeypatch.setattr(real_smoke, "write_safe_report", fake_write_report, raising=False)

    result = real_smoke.run_real_smoke(
        corpus,
        Path("manifest.json"),
        index,
        report_path,
        "http://127.0.0.1:11434",
        checkout,
    )

    assert result["ok"] is True
    assert result["threshold"] == 0.65
    assert written["path"] == report_path
    assert written["report"] == result
    assert [call[0] for call in calls[:3]] == ["external", "external", "external"]
    query_call = next(call for call in calls if call[0] == "queries")
    cases = query_call[2]
    assert [case["query"] for case in cases] == [
        "No CIGAM aparece erro ao abrir uma rotina de exemplo.",
        "No SIAGRI aparece erro ao abrir uma rotina de exemplo.",
        "No sistema XYZ aparece um erro de exemplo.",
        "CIGAM e SIAGRI apresentam um erro de exemplo.",
        "A impressora de exemplo nao imprime.",
    ]
    engine_call = next(call for call in calls if call[0] == "engine")
    assert engine_call[4] == 0.65
    assert calls[-1] == ("close",)
