from pathlib import Path

import pytest

from ai_service_desk.engine.playbook_resolution import PlaybookEngine


def catalog_double():
    return {
        "eligible_knowledge_ids": [
            "KB-SYN-PRINT-001",
            "KB-SYN-VPN-001",
            "KB-SYN-SOFTWARE-001",
            "KB-SYN-OUTLOOK-001",
        ],
        "playbooks": {
            "PB-SYN-PRINT-001": {
                "playbook_id": "PB-SYN-PRINT-001",
                "title": "Impressao sintetica",
                "description": "Procedimento aprovado ficticio.",
                "knowledge_ids": ["KB-SYN-PRINT-001"],
                "version": 1,
                "steps": [
                    {
                        "step_id": "STEP-01",
                        "type": "CHECK",
                        "title": "Verificar fila ficticia",
                        "instruction": "Confirme o estado da fila ficticia.",
                        "capability": "",
                    }
                ],
            }
        },
        "active_by_knowledge_id": {"KB-SYN-PRINT-001": "PB-SYN-PRINT-001"},
        "inactive_by_knowledge_id": {
            "KB-SYN-SOFTWARE-001": [
                {"playbook_id": "PB-SYN-SOFTWARE-DRAFT-001", "status": "DRAFT", "version": 1}
            ],
            "KB-SYN-OUTLOOK-001": [
                {"playbook_id": "PB-SYN-OUTLOOK-RETIRED-001", "status": "RETIRED", "version": 1}
            ],
        },
    }


def engine(monkeypatch, tmp_path: Path, catalog=None):
    value = catalog or catalog_double()
    monkeypatch.setattr(
        "ai_service_desk.engine.playbook_resolution.load_playbook_catalog",
        lambda directory, knowledge_index_directory: (value, {"domain": "APPROVED_PLAYBOOK"}),
    )
    return PlaybookEngine(tmp_path / "catalog", tmp_path / "knowledge")


def test_engine_loads_through_validated_catalog_loader(monkeypatch, tmp_path: Path) -> None:
    calls = []
    value = catalog_double()

    def fake_loader(directory, knowledge_index_directory):
        calls.append((Path(directory), Path(knowledge_index_directory)))
        return value, {"domain": "APPROVED_PLAYBOOK"}

    monkeypatch.setattr(
        "ai_service_desk.engine.playbook_resolution.load_playbook_catalog", fake_loader
    )
    PlaybookEngine(tmp_path / "catalog", tmp_path / "knowledge")
    assert calls == [(tmp_path / "catalog", tmp_path / "knowledge")]


def test_exact_approved_link_returns_playbook_found(monkeypatch, tmp_path: Path) -> None:
    result = engine(monkeypatch, tmp_path).resolve_knowledge_id("KB-SYN-PRINT-001")
    assert result["status"] == "PLAYBOOK_FOUND"
    assert result["reason"] == "MATCH"
    assert result["knowledge_id"] == "KB-SYN-PRINT-001"
    assert result["playbook"]["playbook_id"] == "PB-SYN-PRINT-001"
    assert result["playbook"]["playbook_version"] == 1
    assert set(result["playbook"]) == {
        "playbook_id", "title", "description", "playbook_version", "steps"
    }


def test_knowledge_without_link_returns_knowledge_only(monkeypatch, tmp_path: Path) -> None:
    result = engine(monkeypatch, tmp_path).resolve_knowledge_id("KB-SYN-VPN-001")
    assert result == {
        "status": "KNOWLEDGE_ONLY",
        "reason": "NO_PLAYBOOK",
        "knowledge_id": "KB-SYN-VPN-001",
        "playbook": None,
    }


def test_draft_only_returns_not_approved(monkeypatch, tmp_path: Path) -> None:
    result = engine(monkeypatch, tmp_path).resolve_knowledge_id("KB-SYN-SOFTWARE-001")
    assert result == {
        "status": "PLAYBOOK_UNAVAILABLE",
        "reason": "PLAYBOOK_NOT_APPROVED",
        "knowledge_id": "KB-SYN-SOFTWARE-001",
        "playbook": None,
    }


def test_retired_only_returns_retired(monkeypatch, tmp_path: Path) -> None:
    result = engine(monkeypatch, tmp_path).resolve_knowledge_id("KB-SYN-OUTLOOK-001")
    assert result == {
        "status": "PLAYBOOK_UNAVAILABLE",
        "reason": "PLAYBOOK_RETIRED",
        "knowledge_id": "KB-SYN-OUTLOOK-001",
        "playbook": None,
    }


def test_draft_precedes_retired_when_both_inactive(monkeypatch, tmp_path: Path) -> None:
    value = catalog_double()
    value["inactive_by_knowledge_id"]["KB-SYN-SOFTWARE-001"].append(
        {"playbook_id": "PB-SYN-OLD", "status": "RETIRED", "version": 1}
    )
    result = engine(monkeypatch, tmp_path, value).resolve_knowledge_id("KB-SYN-SOFTWARE-001")
    assert result["reason"] == "PLAYBOOK_NOT_APPROVED"


def test_resolve_uses_only_knowledge_id(monkeypatch, tmp_path: Path) -> None:
    result = engine(monkeypatch, tmp_path).resolve({
        "knowledge_id": "KB-SYN-VPN-001",
        "title": "must not copy",
        "answer": "must not copy",
        "system": "must not copy",
        "intent": "must not copy",
    })
    assert set(result) == {"status", "reason", "knowledge_id", "playbook"}
    assert "title" not in result
    assert "answer" not in result


@pytest.mark.parametrize(
    "value",
    [None, [], "KB-SYN-VPN-001", 1],
)
def test_resolve_rejects_non_mapping(monkeypatch, tmp_path: Path, value) -> None:
    with pytest.raises(ValueError):
        engine(monkeypatch, tmp_path).resolve(value)


@pytest.mark.parametrize(
    "knowledge",
    [{}, {"knowledge_id": ""}, {"knowledge_id": " "}, {"knowledge_id": "X" * 121}],
)
def test_resolve_rejects_invalid_knowledge_id(monkeypatch, tmp_path: Path, knowledge) -> None:
    with pytest.raises(ValueError):
        engine(monkeypatch, tmp_path).resolve(knowledge)


def test_resolve_rejects_id_outside_eligible_set(monkeypatch, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="elegivel"):
        engine(monkeypatch, tmp_path).resolve_knowledge_id("KB-SYN-NOT-ELIGIBLE-001")
