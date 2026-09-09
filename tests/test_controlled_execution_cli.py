from pathlib import Path

import pytest

from ai_service_desk import cli


def test_phase8_parser_accepts_exact_controlled_execution_smoke_command():
    args = cli.build_parser().parse_args(
        ["controlled-execution-smoke", "--cases", "cases.jsonl", "--report", "report.json"]
    )
    assert args.command == "controlled-execution-smoke"
    assert args.cases == Path("cases.jsonl")
    assert args.report == Path("report.json")
    assert not hasattr(args, "url")


@pytest.mark.parametrize("ok", [True, False])
def test_controlled_execution_smoke_cli_output_is_safe_and_does_not_construct_ollama(
    monkeypatch, capsys, ok
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Ollama forbidden")

    monkeypatch.setattr(cli, "OllamaClient", forbidden)
    monkeypatch.setattr(
        cli,
        "run_controlled_execution_smoke",
        lambda *args: {"ok": ok, "cases": [{"identity": "PRIVATE", "purpose": "PRIVATE"}] * 6},
    )
    assert cli.main(["controlled-execution-smoke", "--cases", "c", "--report", "r"]) == (
        0 if ok else 1
    )
    status = "OK" if ok else "REQUER REVISAO"
    assert capsys.readouterr().out == (
        f"CONTROLLED EXECUTION SMOKE {status}\nCasos sinteticos: 6\nRelatorio agregado local: r\n"
    )


def test_controlled_execution_smoke_cli_runs_real_six_cases(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Ollama forbidden")

    monkeypatch.setattr(cli, "OllamaClient", forbidden)
    report = tmp_path / "report.json"
    assert (
        cli.main(
            [
                "controlled-execution-smoke",
                "--cases",
                "tests/fixtures/phase8_controlled_execution_cases.jsonl",
                "--report",
                str(report),
            ]
        )
        == 0
    )
    assert report.exists()
    assert "Casos sinteticos: 6" in capsys.readouterr().out
