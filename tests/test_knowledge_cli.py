import contextlib
import io
import json
from pathlib import Path

from ai_service_desk import cli


def article() -> dict:
    return {
        "knowledge_id": "KB-SYN-001",
        "title": "Artigo sintetico",
        "question": "Pergunta sintetica?",
        "answer": "Resposta literal sintetica.",
        "system": "CIGAM",
        "intent": "PROBLEMA_ACESSO",
        "tags": ["acesso"],
        "source": "SYNTHETIC_DEMO",
        "status": "APPROVED",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-09-07T12:00:00-03:00",
        "version": 1,
    }


def write_source(path: Path) -> Path:
    draft = dict(article(), knowledge_id="KB-DRAFT", status="DRAFT", reviewed_by="", reviewed_at="")
    retired = dict(
        article(), knowledge_id="KB-RETIRED", status="RETIRED", reviewed_by="", reviewed_at=""
    )
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in [article(), draft, retired]),
        encoding="utf-8",
    )
    return path


def test_help_lists_knowledge_commands() -> None:
    parser = cli.build_parser()
    help_text = parser.format_help()
    assert "knowledge-validate" in help_text
    assert "knowledge-index" in help_text
    assert "knowledge-search" in help_text
    assert "knowledge-smoke" in help_text


def test_knowledge_search_threshold_defaults_to_065() -> None:
    args = cli.build_parser().parse_args(
        ["knowledge-search", "--index", "example", "--query", "CIGAM sem acesso"]
    )
    assert args.threshold == 0.65


def test_knowledge_validate_does_not_create_ollama_client(
    tmp_path: Path, monkeypatch
) -> None:
    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("knowledge-validate must not create Ollama client")

    monkeypatch.setattr(cli, "OllamaClient", ForbiddenClient)
    source = write_source(tmp_path / "knowledge.jsonl")
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(["knowledge-validate", "--file", str(source)])
    text = stdout.getvalue()
    assert code == 0
    assert "Total: 3" in text
    assert "APPROVED: 1" in text
    assert "DRAFT: 1" in text
    assert "RETIRED: 1" in text
    assert "Resposta literal sintetica" not in text


def test_knowledge_index_forwards_to_dedicated_builder(tmp_path: Path, monkeypatch) -> None:
    source = write_source(tmp_path / "knowledge.jsonl")
    captured: dict = {}

    class FakeClient:
        def __init__(self, url: str) -> None:
            captured["url"] = url

        def close(self) -> None:
            captured["closed"] = True

    class FakeEmbedder:
        def __init__(self, client) -> None:
            captured["embedder_client"] = client

    def fake_build(source_path, index, embedder, batch_size=10):
        captured.update(source=source_path, index=index, embedder=embedder, batch_size=batch_size)
        return {"domain": "APPROVED_KNOWLEDGE", "rows": 1}

    monkeypatch.setattr(cli, "OllamaClient", FakeClient)
    monkeypatch.setattr(cli, "LocalEmbedder", FakeEmbedder)
    monkeypatch.setattr(cli, "build_knowledge_index", fake_build)
    code = cli.main(
        [
            "knowledge-index",
            "--file",
            str(source),
            "--index",
            str(tmp_path / "index"),
            "--batch-size",
            "7",
        ]
    )
    assert code == 0
    assert captured["batch_size"] == 7
    assert captured["closed"] is True


def test_knowledge_search_surfaces_fail_closed_index_error(tmp_path: Path, monkeypatch) -> None:
    class FakeClient:
        def __init__(self, url: str) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeEmbedder:
        def __init__(self, client) -> None:
            pass

    class RejectingEngine:
        def __init__(self, *args, **kwargs):
            raise ValueError("Indice sem provenance APPROVED_KNOWLEDGE valida.")

    monkeypatch.setattr(cli, "OllamaClient", FakeClient)
    monkeypatch.setattr(cli, "LocalEmbedder", FakeEmbedder)
    monkeypatch.setattr(cli, "KnowledgeEngine", RejectingEngine)
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = cli.main(
            [
                "knowledge-search",
                "--index",
                str(tmp_path / "historical"),
                "--query",
                "CIGAM sem acesso",
            ]
        )
    assert code == 1
    assert "APPROVED_KNOWLEDGE" in stderr.getvalue()


def test_knowledge_search_prints_literal_answer(tmp_path: Path, monkeypatch) -> None:
    literal = "Passo 1: NAO reescreva isto. Confirme: OK?"

    class FakeClient:
        def __init__(self, url: str) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeEmbedder:
        def __init__(self, client) -> None:
            pass

    class FakeEngine:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, text: str) -> dict:
            return {
                "status": "KNOWLEDGE_FOUND",
                "reason": "MATCH",
                "threshold": 0.65,
                "score": 0.9,
                "classification": {},
                "knowledge": {
                    "knowledge_id": "KB-SYN-001",
                    "title": "Sintetico",
                    "answer": literal,
                    "system": "CIGAM",
                    "intent": "PROBLEMA_ACESSO",
                    "version": 1,
                },
            }

    monkeypatch.setattr(cli, "OllamaClient", FakeClient)
    monkeypatch.setattr(cli, "LocalEmbedder", FakeEmbedder)
    monkeypatch.setattr(cli, "KnowledgeEngine", FakeEngine)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(
            [
                "knowledge-search",
                "--index",
                str(tmp_path / "index"),
                "--query",
                "CIGAM sem acesso",
            ]
        )
    assert code == 0
    assert stdout.getvalue() == literal + "\n\n"


def test_knowledge_smoke_delegates_without_creating_extra_client(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict = {}

    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("CLI must delegate smoke client lifecycle")

    def fake_smoke(index, report, url):
        captured.update(index=index, report=report, url=url)
        return {"ok": True, "cases": [{"passed": True}] * 5}

    monkeypatch.setattr(cli, "OllamaClient", ForbiddenClient)
    monkeypatch.setattr(cli, "run_knowledge_smoke", fake_smoke)
    report = tmp_path / "smoke.json"
    code = cli.main(
        [
            "knowledge-smoke",
            "--index",
            str(tmp_path / "index"),
            "--report",
            str(report),
        ]
    )
    assert code == 0
    assert captured["report"] == report
    assert captured["url"] == "http://127.0.0.1:11434"
