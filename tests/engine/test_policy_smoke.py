from pathlib import Path
import subprocess

import pytest
import requests

from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.policy_smoke import load_policy_cases, run_policy_smoke

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "phase7_policy_cases.jsonl"


def test_load_policy_cases_requires_exactly_15_cases() -> None:
    cases = load_policy_cases(FIXTURE)
    assert len(cases) == 15
    assert len({row["case_name"] for row in cases}) == 15


def test_load_policy_cases_rejects_invalid_schema(tmp_path: Path) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text('{"case_name":"only"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy_cases(path)


def test_run_policy_smoke_passes_all_15_cases(tmp_path: Path) -> None:
    report = run_policy_smoke(FIXTURE, tmp_path / "report.json")
    assert report["ok"] is True
    assert len(report["cases"]) == 15
    assert all(row["passed"] for row in report["cases"])


def test_policy_smoke_report_is_privacy_safe(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    run_policy_smoke(FIXTURE, report_path)
    text = report_path.read_text(encoding="utf-8")
    for forbidden in (
        "Synthetic User",
        "example.invalid",
        "Financeiro Sintetico",
        "Revenda Sintetica",
        "preciso de acesso",
        "quero acesso",
        "CDM_ACCESS_REQUEST",
        "KB-SYN-CDM",
        "PB-SYN-CDM",
    ):
        assert forbidden not in text


def test_policy_smoke_makes_zero_external_calls(monkeypatch, tmp_path: Path) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("external execution forbidden")

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(OllamaClient, "chat", forbidden)
    monkeypatch.setattr(LocalEmbedder, "embed", forbidden)
    report = run_policy_smoke(FIXTURE, tmp_path / "report.json")
    assert report["ok"] is True
