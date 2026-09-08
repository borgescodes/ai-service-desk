import json
from pathlib import Path

import pytest

from ai_service_desk.engine.playbook_smoke import load_playbook_cases

VALID = {
    "case_name": "approved-single-link",
    "mode": "RESOLVE",
    "knowledge_id": "KB-SYN-PRINT-001",
    "expected_status": "PLAYBOOK_FOUND",
    "expected_reason": "MATCH",
    "expected_playbook_id": "PB-SYN-PRINT-001",
    "mutation": "",
}


def write_cases(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def ten_rows() -> list[dict]:
    rows = []
    for i in range(10):
        row = dict(VALID)
        row["case_name"] = f"case-{i}"
        rows.append(row)
    return rows


def test_loader_requires_exactly_ten_cases(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    write_cases(path, ten_rows())
    assert len(load_playbook_cases(path)) == 10
    write_cases(path, ten_rows()[:9])
    with pytest.raises(ValueError, match="10 casos"):
        load_playbook_cases(path)


def test_loader_rejects_wrong_fields_and_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    rows = ten_rows()
    rows[0]["extra"] = True
    write_cases(path, rows)
    with pytest.raises(ValueError, match="Campos"):
        load_playbook_cases(path)
    rows = ten_rows()
    rows[1]["case_name"] = rows[0]["case_name"]
    write_cases(path, rows)
    with pytest.raises(ValueError, match="duplicado"):
        load_playbook_cases(path)


@pytest.mark.parametrize(
    "field,value",
    [("mode", "OTHER"), ("mutation", "BOOM"), ("case_name", ""), ("knowledge_id", 1)],
)
def test_loader_rejects_invalid_values(tmp_path: Path, field: str, value) -> None:
    path = tmp_path / "cases.jsonl"
    rows = ten_rows()
    rows[0][field] = value
    write_cases(path, rows)
    with pytest.raises(ValueError):
        load_playbook_cases(path)
