from ai_service_desk.engine.knowledge import load_knowledge
from ai_service_desk.engine.learning_prevention import validate_outcome_record
from ai_service_desk.engine.playbook import load_playbooks
from ai_service_desk.web.demo_data import demo_outcomes, write_demo_knowledge, write_demo_playbooks


def test_demo_data_knowledge_uses_homologated_schema(tmp_path) -> None:
    path = write_demo_knowledge(tmp_path / "knowledge.jsonl")
    articles = load_knowledge(path)

    assert [item["knowledge_id"] for item in articles] == [
        "KB-SYN-CDM-ACCESS-001",
        "KB-SYN-M365-PASSWORD-001",
    ]
    assert all(item["status"] == "APPROVED" for item in articles)


def test_demo_data_cdm_playbook_is_approved_action_proposal(tmp_path) -> None:
    path = write_demo_playbooks(tmp_path / "playbooks.jsonl")
    playbooks = load_playbooks(path)

    assert len(playbooks) == 1
    playbook = playbooks[0]
    assert playbook["playbook_id"] == "PB-SYN-CDM-ACCESS-001"
    assert playbook["knowledge_ids"] == ["KB-SYN-CDM-ACCESS-001"]
    assert playbook["status"] == "APPROVED"
    assert playbook["steps"][0]["type"] == "ACTION_PROPOSAL"
    assert playbook["steps"][0]["capability"] == "CDM_ACCESS_REQUEST"


def test_demo_data_m365_has_no_playbook_reference(tmp_path) -> None:
    path = write_demo_playbooks(tmp_path / "playbooks.jsonl")
    playbooks = load_playbooks(path)
    assert all("KB-SYN-M365-PASSWORD-001" not in item["knowledge_ids"] for item in playbooks)


def test_demo_data_outcomes_are_valid_synthetic_evidence() -> None:
    outcomes = demo_outcomes()
    assert len(outcomes) >= 3
    for record in outcomes:
        validate_outcome_record(record)
        rendered = repr(record).casefold()
        assert "@juparana" not in rendered
        assert "pedro miranda" not in rendered
