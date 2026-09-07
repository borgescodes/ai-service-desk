import json
from pathlib import Path

import pytest
from ai_service_desk.engine.evaluation import load_evaluation_cases

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
