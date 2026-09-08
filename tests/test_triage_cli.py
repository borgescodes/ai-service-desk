from pathlib import Path

import ai_service_desk.cli as cli
from ai_service_desk.cli import DEFAULT_URL, build_parser


def test_triage_smoke_parser_requires_index_cases_and_report() -> None:
    args = build_parser().parse_args(
        [
            "triage-smoke",
            "--index",
            "index",
            "--cases",
            "tests/fixtures/phase5_triage_conversations.jsonl",
            "--report",
            "report.json",
        ]
    )
    assert args.command == "triage-smoke"
    assert str(args.index) == "index"
    assert str(args.cases).endswith("phase5_triage_conversations.jsonl")
    assert str(args.report) == "report.json"
    assert args.url == DEFAULT_URL


def test_triage_smoke_cli_prints_only_safe_summary(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        cli,
        "run_triage_smoke",
        lambda *args, **kwargs: {"ok": True, "cases": [{"passed": True}] * 10},
        raising=False,
    )
    code = cli.main(
        [
            "triage-smoke",
            "--index",
            str(tmp_path / "index"),
            "--cases",
            "tests/fixtures/phase5_triage_conversations.jsonl",
            "--report",
            str(tmp_path / "report.json"),
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "TRIAGE SMOKE OK" in output
    assert "Casos sinteticos: 10" in output
    assert "answer" not in output.lower()
    assert "Nao consigo acessar" not in output
