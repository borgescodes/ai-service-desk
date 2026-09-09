from pathlib import Path

from ai_service_desk.engine.learning_prevention import OutcomeRecord
from ai_service_desk.engine.learning_prevention_smoke import (
    LEARNING_PREVENTION_CASE_IDS,
    load_learning_prevention_cases,
    run_learning_prevention_smoke,
)

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "phase11_learning_prevention_cases.jsonl"
)

EXPECTED_CASE_IDS = (
    "KNOWLEDGE_RECURRING_RESOLVES",
    "KNOWLEDGE_GAP",
    "HUMAN_DEPENDENCY",
    "AUTOMATION_CANDIDATE",
    "PREVENTION_CANDIDATE",
    "EXECUTION_RELIABILITY_ISSUE",
    "IDEMPOTENT_INGESTION",
    "CONFLICT_FAILS_CLOSED",
    "ANALYTICS_DOES_NOT_MUTATE_OPERATIONAL_STATE",
    "DETERMINISTIC_SNAPSHOT",
)


def test_learning_prevention_case_contract_is_exact() -> None:
    assert LEARNING_PREVENTION_CASE_IDS == EXPECTED_CASE_IDS


def test_fixture_loads_as_closed_synthetic_outcome_records() -> None:
    rows = load_learning_prevention_cases(FIXTURE)
    assert len(rows) == 15
    assert all(type(row) is OutcomeRecord for row in rows)
    assert len({row.interaction_id for row in rows}) == 15
    assert tuple(row.interaction_id for row in rows) == tuple(
        sorted(row.interaction_id for row in rows)
    )


def test_official_smoke_passes_all_ten_cases() -> None:
    report = run_learning_prevention_smoke(FIXTURE)
    assert report["ok"] is True
    assert report["case_count"] == 10
    assert tuple(item["case_id"] for item in report["cases"]) == EXPECTED_CASE_IDS
    assert all(item["ok"] is True for item in report["cases"])


def test_official_smoke_is_deterministic() -> None:
    first = run_learning_prevention_smoke(FIXTURE)
    second = run_learning_prevention_smoke(FIXTURE)
    assert first == second
