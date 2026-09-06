import json
from pathlib import Path

from ai_service_desk.engine import smoke


class FailingClient:
    def __init__(self, base_url: str):
        raise RuntimeError("synthetic connection failure")


def test_validation_writes_report_when_ollama_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(smoke, "OllamaClient", FailingClient)
    report_path = tmp_path / "report.json"
    report = smoke.run_validation(
        Path("tests/fixtures/engine_smoke_corpus.csv"),
        tmp_path / "index",
        report_path,
    )
    assert report["ok"] is False
    assert "synthetic connection failure" in report["error"]
    assert report_path.is_file()
    assert json.loads(report_path.read_text(encoding="utf-8"))["ok"] is False


def test_fixture_has_only_synthetic_ids() -> None:
    text = Path("tests/fixtures/engine_smoke_corpus.csv").read_text(encoding="utf-8")
    for index in range(1, 9):
        assert f"SYN-{index:03d}" in text
