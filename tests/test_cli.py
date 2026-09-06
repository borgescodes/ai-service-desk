import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from ai_service_desk import cli

ROOT = Path(__file__).resolve().parent.parent


def test_help_runs_without_ollama() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "ai_service_desk", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "validate" in result.stdout
    assert "search" in result.stdout
    assert "audit" in result.stdout
    assert "real-smoke" in result.stdout


def test_inspect_uses_synthetic_fixture_without_history() -> None:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = cli.main(["inspect", "--file", "tests/fixtures/engine_smoke_corpus.csv"])
    output = stream.getvalue()
    assert code == 0
    assert "Registros: 8" in output
    assert "senha: exemplo-nao-real" not in output


def test_missing_index_returns_error_without_traceback(tmp_path: Path) -> None:
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        code = cli.main(["show-index", "--index", str(tmp_path / "missing")])
    assert code == 1
    assert "ERRO:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_prepare_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "existing.csv"
    output.write_text("x", encoding="utf-8")
    code = cli.main(
        [
            "prepare",
            "--tickets",
            str(tmp_path / "tickets.tsv"),
            "--appointments",
            str(tmp_path / "appointments.tsv"),
            "--output",
            str(output),
        ]
    )
    assert code == 1


def test_validate_forwards_arguments_and_exit_code(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    def fake_validation(corpus, index, report_path, base_url, legacy, threshold):
        captured.update(
            corpus=corpus,
            index=index,
            report_path=report_path,
            base_url=base_url,
            legacy=legacy,
            threshold=threshold,
        )
        Path(report_path).write_text(json.dumps({"ok": True}), encoding="utf-8")
        return {"ok": True}

    monkeypatch.setattr(cli, "run_validation", fake_validation)
    report = tmp_path / "report.json"
    code = cli.main(
        [
            "validate",
            "--file",
            "tests/fixtures/engine_smoke_corpus.csv",
            "--index",
            str(tmp_path / "index"),
            "--report",
            str(report),
            "--url",
            "http://127.0.0.1:11434",
            "--threshold",
            "0.7",
        ]
    )
    assert code == 0
    assert captured["threshold"] == 0.7
    assert str(captured["corpus"]).endswith("engine_smoke_corpus.csv")


def test_context_json_without_query_fails_before_client_creation(
    tmp_path: Path, monkeypatch
) -> None:
    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("client should not be created")

    monkeypatch.setattr(cli, "OllamaClient", ForbiddenClient)
    code = cli.main(
        [
            "search",
            "--index",
            str(tmp_path / "index"),
            "--context-json",
            str(tmp_path / "context.json"),
        ]
    )
    assert code == 1
    assert not (tmp_path / "context.json").exists()


def test_audit_writes_aggregate_report_without_ollama(tmp_path: Path, monkeypatch) -> None:
    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("audit must not create Ollama client")

    monkeypatch.setattr(cli, "OllamaClient", ForbiddenClient)
    report = tmp_path / "audit.json"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(
            [
                "audit",
                "--file",
                "tests/fixtures/phase2_corpus.csv",
                "--manifest",
                "tests/fixtures/phase2_corpus_manifest.json",
                "--report",
                str(report),
            ]
        )

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["manifest_match"] is True
    report_text = report.read_text(encoding="utf-8")
    assert "Falha CIGAM" not in report_text
    assert "1001" not in report_text
    assert "Falha CIGAM" not in stdout.getvalue()
    assert "1001" not in stdout.getvalue()


def test_real_smoke_forwards_external_paths(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    external = tmp_path / "external"
    checkout = tmp_path / "repo"
    external.mkdir()
    checkout.mkdir()

    def fake_run(corpus, manifest, index, report, base_url, checkout_path):
        captured.update(
            corpus=corpus,
            manifest=manifest,
            index=index,
            report=report,
            base_url=base_url,
            checkout=checkout_path,
        )
        Path(report).write_text('{"ok": true}', encoding="utf-8")
        return {"ok": True, "index": {"rows": 3, "shape": [3, 4]}, "queries": []}

    monkeypatch.setattr(cli, "run_real_smoke", fake_run, raising=False)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(
            [
                "real-smoke",
                "--file",
                str(external / "corpus.csv"),
                "--manifest",
                "tests/fixtures/phase2_corpus_manifest.json",
                "--index",
                str(external / "index"),
                "--report",
                str(external / "report.json"),
                "--checkout",
                str(checkout),
            ]
        )

    assert code == 0
    assert captured["base_url"] == "http://127.0.0.1:11434"
    assert Path(captured["corpus"]) == external / "corpus.csv"
    assert Path(captured["index"]) == external / "index"
    assert Path(captured["report"]) == external / "report.json"
    assert Path(captured["checkout"]) == checkout
    output = stdout.getvalue()
    assert "REAL CORPUS SMOKE OK" in output
    assert "Falha CIGAM" not in output
    assert "ticket" not in output.lower()
