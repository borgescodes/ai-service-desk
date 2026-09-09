import json
from pathlib import Path

from ai_service_desk.engine.cdm_integration_smoke import run_cdm_integration_smoke


def test_phase9_smoke_runs_six_cases(tmp_path):
    report = run_cdm_integration_smoke(
        Path("tests/fixtures/phase9_cdm_integration_cases.jsonl"),
        tmp_path / "phase9.json",
        "synthetic-test-token",
    )
    assert report["ok"] is True
    assert report["case_count"] == 6
    assert len(report["cases"]) == 6
    assert "synthetic-test-token" not in json.dumps(report)
    assert json.loads((tmp_path / "phase9.json").read_text()) == report
