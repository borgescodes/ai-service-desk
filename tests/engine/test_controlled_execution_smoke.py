import json
from pathlib import Path

import pytest
import requests

from ai_service_desk.engine.controlled_execution_smoke import (
    load_controlled_execution_cases,
    run_controlled_execution_smoke,
)
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/phase8_controlled_execution_cases.jsonl"


def test_controlled_execution_smoke_passes_all_six_flows(tmp_path):
    report = run_controlled_execution_smoke(FIXTURE, tmp_path / "report.json")
    assert report["ok"] is True
    assert len(report["cases"]) == 6
    assert all(case["passed"] for case in report["cases"])
    assert [case["final_state"] for case in report["cases"]] == [
        "COMPLETED",
        "FAILED",
        "FAILED",
        "REJECTED",
        "DENIED_POLICY",
        "DENIED_POLICY",
    ]
    assert [case["executor_calls"] for case in report["cases"]] == [1, 1, 1, 0, 0, 0]


def test_smoke_loader_requires_exact_six_unique_flows():
    rows = load_controlled_execution_cases(FIXTURE)
    assert len(rows) == len({row["case_name"] for row in rows}) == 6


@pytest.mark.parametrize(
    "change",
    [
        {"extra": "secret"},
        {"expected_executor_calls": True},
        {"revalidation_deny": 1},
        {"executor_mode": "network"},
        {"case_name": "someone@example.invalid"},
        {"requested_role": []},
        {"expected_result_code": []},
    ],
)
def test_smoke_loader_rejects_invalid_closed_schema(tmp_path, change):
    rows = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
    rows[0].update(change)
    source = tmp_path / "cases.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        load_controlled_execution_cases(source)


@pytest.mark.parametrize(
    "mode", ["missing", "duplicate", "invalid_json", "invalid_utf8", "wrong_flow"]
)
def test_smoke_loader_rejects_malformed_or_incomplete_flows(tmp_path, mode):
    lines = FIXTURE.read_text().splitlines()
    if mode == "missing":
        lines.pop()
    elif mode == "duplicate":
        lines[-1] = lines[0]
    elif mode == "invalid_json":
        lines[0] = "not json"
    elif mode == "wrong_flow":
        row = json.loads(lines[0])
        row["executor_mode"] = "failure"
        lines[0] = json.dumps(row)
    source = tmp_path / "cases.jsonl"
    source.write_bytes(b"\xff" if mode == "invalid_utf8" else "\n".join(lines).encode())
    with pytest.raises(ValueError):
        load_controlled_execution_cases(source)


def test_smoke_report_is_deterministic_and_privacy_safe(tmp_path):
    target = tmp_path / "report.json"
    first = run_controlled_execution_smoke(FIXTURE, target)
    assert run_controlled_execution_smoke(FIXTURE, target) == first
    assert set(first) == {"schema_version", "phase", "ok", "cases"}
    for row in first["cases"]:
        assert set(row) == {
            "case_name",
            "final_state",
            "reason_code",
            "result_code",
            "error_code",
            "executor_calls",
            "passed",
        }
    text = target.read_text()
    for forbidden in (
        "example.invalid",
        "Synthetic",
        "solicitar materiais",
        "CDM_ACCESS_REQUEST",
        "KB-SYN",
        "PB-SYN",
        "STEP-SYN",
        "Traceback",
        "RuntimeError",
    ):
        assert forbidden not in text


def test_smoke_invalid_input_returns_safe_failure_report(tmp_path):
    source = tmp_path / "invalid.jsonl"
    source.write_text('{"secret":"SYNTHETIC_PRIVATE_PAYLOAD"}')
    target = tmp_path / "report.json"
    report = run_controlled_execution_smoke(source, target)
    assert report["ok"] is False
    assert report["error_code"] == "CONTROLLED_EXECUTION_CASES_INVALID"
    assert "SYNTHETIC_PRIVATE_PAYLOAD" not in target.read_text()


def test_smoke_expected_mismatch_reports_failure(tmp_path):
    rows = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
    rows[0]["expected_state"] = "FAILED"
    source = tmp_path / "cases.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in rows))
    report = run_controlled_execution_smoke(source, tmp_path / "report.json")
    assert report["ok"] is False
    assert report["cases"][0]["passed"] is False


def test_smoke_makes_zero_external_calls(monkeypatch, tmp_path):
    import subprocess
    import urllib.request

    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("attempted")
        raise AssertionError("External execution forbidden")

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(OllamaClient, "__init__", forbidden)
    monkeypatch.setattr(LocalEmbedder, "embed", forbidden)
    assert run_controlled_execution_smoke(FIXTURE, tmp_path / "report.json")["ok"] is True
    assert attempts == []


def test_smoke_unexpected_failure_does_not_claim_zero_executor_calls(monkeypatch, tmp_path):
    from ai_service_desk.engine import controlled_execution_smoke as smoke

    def fail_after_unobserved_work(case):
        raise RuntimeError("PRIVATE_EXCEPTION")

    monkeypatch.setattr(smoke, "_run_case", fail_after_unobserved_work)
    target = tmp_path / "report.json"
    report = smoke.run_controlled_execution_smoke(FIXTURE, target)
    assert report["ok"] is False
    assert all(row["executor_calls"] is None for row in report["cases"])
    assert "PRIVATE_EXCEPTION" not in target.read_text()
