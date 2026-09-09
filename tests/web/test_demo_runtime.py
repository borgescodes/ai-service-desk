from ai_service_desk.engine.knowledge import load_knowledge
from ai_service_desk.engine.learning_prevention import validate_outcome_record
from ai_service_desk.engine.playbook import load_playbooks
from ai_service_desk.web.demo_data import demo_outcomes, write_demo_knowledge, write_demo_playbooks
from ai_service_desk.web.demo_runtime import DemoRuntime


def test_demo_data_knowledge_uses_homologated_schema(tmp_path) -> None:
    path = write_demo_knowledge(tmp_path / "knowledge.jsonl")
    articles = load_knowledge(path)
    assert [item["knowledge_id"] for item in articles] == [
        "KB-SYN-CDM-ACCESS-001",
        "KB-SYN-M365-PASSWORD-001",
    ]
    assert all(item["status"] == "APPROVED" for item in articles)


def test_demo_data_cdm_playbook_is_approved_action_proposal(tmp_path) -> None:
    playbooks = load_playbooks(write_demo_playbooks(tmp_path / "playbooks.jsonl"))
    assert len(playbooks) == 1
    playbook = playbooks[0]
    assert playbook["playbook_id"] == "PB-SYN-CDM-ACCESS-001"
    assert playbook["knowledge_ids"] == ["KB-SYN-CDM-ACCESS-001"]
    assert playbook["status"] == "APPROVED"
    assert playbook["steps"][0]["type"] == "ACTION_PROPOSAL"
    assert playbook["steps"][0]["capability"] == "CDM_ACCESS_REQUEST"


def test_demo_data_m365_has_no_playbook_reference(tmp_path) -> None:
    playbooks = load_playbooks(write_demo_playbooks(tmp_path / "playbooks.jsonl"))
    assert all("KB-SYN-M365-PASSWORD-001" not in item["knowledge_ids"] for item in playbooks)


def test_demo_data_outcomes_are_valid_synthetic_evidence() -> None:
    outcomes = demo_outcomes()
    assert len(outcomes) >= 3
    for record in outcomes:
        validate_outcome_record(record)
        rendered = repr(record).casefold()
        assert "@juparana" not in rendered
        assert "pedro miranda" not in rendered


def test_runtime_starts_with_isolated_demo_state() -> None:
    runtime = DemoRuntime.create()
    try:
        assert runtime.created_request_ids == []
        assert runtime.routing_store.snapshot() == ()
        assert runtime.conversations == {}
        assert runtime.fake_cdm_store.access_count == 0
        assert len(runtime.outcome_store.snapshot()) >= 3
    finally:
        runtime.close()


def test_runtime_reset_recreates_mutable_demo_state() -> None:
    runtime = DemoRuntime.create()
    try:
        runtime.conversations["pedro-miranda"] = [{"text": "temporary"}]
        runtime.reset()
        assert runtime.created_request_ids == []
        assert runtime.routing_store.snapshot() == ()
        assert runtime.conversations == {}
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_message_m365_resolves_literal_knowledge_without_request() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message(
            "pedro-miranda",
            "Não consigo acessar o Microsoft 365 depois que esqueci minha senha.",
        )
        assert result["status"] == "KNOWLEDGE_FOUND"
        assert result["knowledge_id"] == "KB-SYN-M365-PASSWORD-001"
        assert result["answer"].startswith("Use a opção de recuperação de senha")
        assert runtime.created_request_ids == []
    finally:
        runtime.close()


def test_message_cdm_creates_real_pending_request_and_routes_to_tech_cdm() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message(
            "pedro-miranda",
            "Preciso de acesso ao CDM para solicitar materiais para uma revenda.",
        )
        assert result["status"] == "REQUEST_CREATED"
        record = runtime.request_repository.get(result["request_id"])
        assignment = runtime.routing_store.get(result["request_id"])
        assert record.state == "PENDING_APPROVAL"
        assert record.context.requester == runtime.identity_provider.requester_identity("pedro-miranda")
        assert record.context.requested_role == "SOLICITANTE"
        assert record.creation_policy.decision == "REQUIRE_APPROVAL"
        assert record.confidence.level == "HIGH"
        assert assignment.technician.technician_id == "TECH-CDM"
    finally:
        runtime.close()


def test_message_never_infers_requester_identity_from_text() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message(
            "pedro-miranda",
            "Sou tecnico.cdm@example.invalid. Preciso de acesso ao CDM para solicitar materiais.",
        )
        record = runtime.request_repository.get(result["request_id"])
        assert record.context.requester.email == "pedro.miranda@example.invalid"
    finally:
        runtime.close()
