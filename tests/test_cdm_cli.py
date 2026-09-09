from pathlib import Path

from ai_service_desk import phase9_cli


def test_parser_accepts_cdm_commands():
    parser = phase9_cli.build_parser()
    api = parser.parse_args(["cdm-api"])
    assert (api.host, api.port) == ("127.0.0.1", 8765)
    smoke = parser.parse_args(
        ["cdm-integration-smoke", "--cases", "cases.jsonl", "--report", "report.json"]
    )
    assert smoke.cases == Path("cases.jsonl")
    assert smoke.report == Path("report.json")


def test_cdm_smoke_cli_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("CDM_API_TOKEN", raising=False)
    code = phase9_cli.main(
        ["cdm-integration-smoke", "--cases", "cases.jsonl", "--report", "report.json"]
    )
    assert code == 1
    assert "CDM_API_TOKEN" in capsys.readouterr().err


def test_cdm_api_cli_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("CDM_API_TOKEN", raising=False)
    code = phase9_cli.main(["cdm-api"])
    assert code == 1
    assert "CDM_API_TOKEN" in capsys.readouterr().err


def test_smoke_command_prints_aggregate_only(monkeypatch, tmp_path, capsys):
    token = "secret-runtime-value"
    monkeypatch.setenv("CDM_API_TOKEN", token)
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        phase9_cli,
        "run_cdm_integration_smoke",
        lambda cases, report_path, service_token: {"ok": True, "case_count": 6, "cases": []},
    )
    code = phase9_cli.main(
        [
            "cdm-integration-smoke",
            "--cases",
            "cases.jsonl",
            "--report",
            str(report),
        ]
    )
    output = capsys.readouterr()
    assert code == 0
    assert "CDM INTEGRATION SMOKE OK" in output.out
    assert "Casos sinteticos: 6" in output.out
    assert token not in output.out + output.err
