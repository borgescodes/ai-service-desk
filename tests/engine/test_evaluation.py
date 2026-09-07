import json
from pathlib import Path

import pytest

from ai_service_desk.engine.evaluation import compute_metrics, load_evaluation_cases

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "phase3_eval_cases.jsonl"


def _write_cases(path: Path, cases: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )


def _case(case_id: str = "a") -> dict:
    return {
        "id": case_id,
        "query": "CIGAM falhou em um exemplo.",
        "expected_intent": "ERRO_SISTEMA",
        "expected_system": "CIGAM",
        "relevant_ticket_ids": ["SYN-CIG-01"],
        "must_abstain": False,
    }


def test_versioned_phase3_benchmark_has_expected_size_and_unique_ids() -> None:
    cases = load_evaluation_cases(FIXTURE)
    assert len(cases) == 28
    assert len({case["id"] for case in cases}) == 28
    assert all(case["query"].strip() for case in cases)


def test_load_evaluation_cases_validates_schema(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_cases(path, [_case()])
    cases = load_evaluation_cases(path)
    assert cases[0]["id"] == "a"
    assert cases[0]["expected_intent"] == "ERRO_SISTEMA"


def test_load_evaluation_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    _write_cases(path, [_case("same"), _case("same")])
    with pytest.raises(ValueError, match="id"):
        load_evaluation_cases(path)


def test_load_evaluation_cases_rejects_invalid_intent(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    case = _case()
    case["expected_intent"] = "INVENTADO"
    _write_cases(path, [case])
    with pytest.raises(ValueError, match="intent"):
        load_evaluation_cases(path)


def test_load_evaluation_cases_rejects_abstain_with_relevant_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    case = _case()
    case["must_abstain"] = True
    _write_cases(path, [case])
    with pytest.raises(ValueError, match="abstain"):
        load_evaluation_cases(path)


def test_load_evaluation_cases_rejects_invalid_expected_status(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    case = _case()
    case["expected_status"] = "QUALQUER"
    _write_cases(path, [case])
    with pytest.raises(ValueError, match="status"):
        load_evaluation_cases(path)


def test_compute_metrics_counts_hit_mrr_and_abstention() -> None:
    cases = [
        {
            "id": "a",
            "expected_intent": "ERRO_SISTEMA",
            "expected_system": "CIGAM",
            "relevant_ticket_ids": ["SYN-1"],
            "must_abstain": False,
        },
        {
            "id": "b",
            "expected_intent": "OUTRO",
            "expected_system": "XYZ",
            "relevant_ticket_ids": [],
            "must_abstain": True,
            "expected_status": "SEM_CONTEXTO",
        },
    ]
    results = [
        {
            "id": "a",
            "actual_intent": "ERRO_SISTEMA",
            "actual_system": "CIGAM",
            "status": "ENCONTRADOS",
            "candidate_ids": ["SYN-1", "SYN-2"],
            "system_leakage": False,
            "total_seconds": 1.0,
        },
        {
            "id": "b",
            "actual_intent": "OUTRO",
            "actual_system": "XYZ",
            "status": "SEM_CONTEXTO",
            "candidate_ids": [],
            "system_leakage": False,
            "total_seconds": 2.0,
        },
    ]
    metrics = compute_metrics(cases, results)
    assert metrics["intent_accuracy"] == 1.0
    assert metrics["system_accuracy"] == 1.0
    assert metrics["hit_at_1"] == 1.0
    assert metrics["hit_at_3"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["precision_at_3"] == pytest.approx(1 / 3)
    assert metrics["correct_abstention_rate"] == 1.0
    assert metrics["unsafe_accept_count"] == 0
    assert metrics["system_leakage_count"] == 0
    assert metrics["unknown_system_failures"] == 0
    assert metrics["execution_failures"] == 0
    assert metrics["p50_total_seconds"] == 1.5
    assert metrics["p95_total_seconds"] == pytest.approx(1.95)


def test_compute_metrics_detects_unsafe_accept_leakage_and_status_failure() -> None:
    cases = [
        {
            "id": "amb",
            "expected_intent": "ERRO_SISTEMA",
            "expected_system": "",
            "relevant_ticket_ids": [],
            "must_abstain": True,
            "expected_status": "CONTEXTO_AMBIGUO",
        },
        {
            "id": "rank",
            "expected_intent": "PROBLEMA_REDE",
            "expected_system": "",
            "relevant_ticket_ids": ["SYN-R"],
            "must_abstain": False,
        },
    ]
    results = [
        {
            "id": "amb",
            "actual_intent": "ERRO_SISTEMA",
            "actual_system": "",
            "status": "ENCONTRADOS",
            "candidate_ids": ["SYN-WRONG"],
            "system_leakage": True,
            "total_seconds": 0.5,
        },
        {
            "id": "rank",
            "actual_intent": "OUTRO",
            "actual_system": "",
            "status": "ENCONTRADOS",
            "candidate_ids": ["SYN-X", "SYN-R"],
            "system_leakage": False,
            "total_seconds": 0.7,
        },
    ]
    metrics = compute_metrics(cases, results)
    assert metrics["intent_accuracy"] == 0.5
    assert metrics["hit_at_1"] == 0.0
    assert metrics["hit_at_3"] == 1.0
    assert metrics["mrr"] == 0.5
    assert metrics["unsafe_accept_count"] == 1
    assert metrics["system_leakage_count"] == 1
    assert metrics["ambiguous_context_failures"] == 1


def test_compute_metrics_counts_execution_failure_without_crashing() -> None:
    cases = [
        {
            "id": "failed",
            "expected_intent": "OUTRO",
            "expected_system": "",
            "relevant_ticket_ids": [],
            "must_abstain": True,
        }
    ]
    results = [{"id": "failed", "error": "synthetic failure"}]
    metrics = compute_metrics(cases, results)
    assert metrics["execution_failures"] == 1
    assert metrics["correct_abstention_rate"] == 0.0
    assert metrics["p50_total_seconds"] is None


def test_compute_metrics_rejects_invalid_k() -> None:
    with pytest.raises(ValueError, match="k"):
        compute_metrics([], [], k=0)
