from pathlib import Path

from ai_service_desk import cli


def test_phase7_parser_accepts_exact_policy_smoke_command() -> None:
    args = cli.build_parser().parse_args(
        ["policy-smoke", "--cases", "cases.jsonl", "--report", "report.json"]
    )
    assert args.command == "policy-smoke"
    assert args.cases == Path("cases.jsonl")
    assert args.report == Path("report.json")
    assert not hasattr(args, "url")
    assert not hasattr(args, "knowledge_index")
    assert not hasattr(args, "playbooks")
    assert not hasattr(args, "work_directory")


def test_policy_smoke_cli_output_is_safe_and_does_not_construct_ollama(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        cli,
        "run_policy_smoke",
        lambda *args, **kwargs: {"ok": True, "cases": [{}] * 15},
    )
    monkeypatch.setattr(
        cli,
        "OllamaClient",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Ollama forbidden")),
    )
    assert cli.main(["policy-smoke", "--cases", "c", "--report", "r"]) == 0
    out = capsys.readouterr().out
    assert "POLICY SMOKE OK" in out
    assert "Casos sinteticos: 15" in out
    assert "CDM_ACCESS_REQUEST" not in out
    assert "Synthetic User" not in out


def test_policy_smoke_cli_returns_nonzero_when_report_is_not_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "run_policy_smoke",
        lambda *args, **kwargs: {"ok": False, "cases": [{}] * 15},
    )
    assert cli.main(["policy-smoke", "--cases", "c", "--report", "r"]) == 1
