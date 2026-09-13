import pytest

from ai_service_desk.engine.knowledge import load_knowledge
from ai_service_desk.engine.learning_prevention import (
    OpportunityEngine,
    PatternAggregator,
    validate_outcome_record,
)
from ai_service_desk.engine.playbook import load_playbooks
from ai_service_desk.engine.policy import PolicyEngine, PolicyRule
from ai_service_desk.engine.routing import InMemoryRoutingAssignmentStore, RoutingAssignment
from ai_service_desk.web.demo_data import demo_outcomes, write_demo_knowledge, write_demo_playbooks
from ai_service_desk.web.demo_runtime import DemoRuntime
from ai_service_desk.web.errors import WebDemoError


def _create_cdm_request(runtime: DemoRuntime) -> str:
    result = runtime.send_message(
        "pedro-miranda",
        "Preciso de acesso ao CDM para solicitar materiais para uma revenda.",
    )
    assert result["status"] == "REQUEST_CREATED"
    return result["request_id"]


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
        answer = result["answer"]
        assert answer.startswith("Vamos redefinir sua senha do Microsoft 365.")
        assert all(f"{number}. " in answer for number in range(1, 8))
        assert "Microsoft Authenticator" in answer
        assert answer.endswith("Faça esse procedimento e me diga se conseguiu acessar.")
        assert runtime.created_request_ids == []
    finally:
        runtime.close()


def test_message_cdm_creates_real_pending_request_and_routes_to_tech_cdm() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        record = runtime.request_repository.get(request_id)
        assignment = runtime.routing_store.get(request_id)
        assert record.state == "PENDING_APPROVAL"
        assert record.context.requester == runtime.identity_provider.requester_identity(
            "pedro-miranda"
        )
        assert record.context.requested_role == "SOLICITANTE"
        assert record.creation_policy.decision == "REQUIRE_APPROVAL"
        assert record.confidence.level == "HIGH"
        assert assignment.technician.technician_id == "TECH-CDM"
        assert runtime.fake_cdm_store.access_count == 0
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


def test_requester_lists_and_opens_own_request() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        listing = runtime.list_requests("pedro-miranda")
        detail = runtime.get_request("pedro-miranda", request_id)
        assert [item["request_id"] for item in listing] == [request_id]
        assert detail["request_id"] == request_id
        assert detail["state"] == "PENDING_APPROVAL"
        assert "reason_code" not in detail["policy"]
    finally:
        runtime.close()


def test_technician_cannot_use_requester_requests_view() -> None:
    runtime = DemoRuntime.create()
    try:
        _create_cdm_request(runtime)
        with pytest.raises(WebDemoError) as exc_info:
            runtime.list_requests("tecnico-cdm")
        assert exc_info.value.code == "NOT_AUTHORIZED"
    finally:
        runtime.close()


def test_approval_queue_is_routed_and_requester_cannot_open_it() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        with pytest.raises(WebDemoError) as exc_info:
            runtime.list_approvals("pedro-miranda")
        assert exc_info.value.code == "NOT_AUTHORIZED"

        items = runtime.list_approvals("tecnico-cdm")
        assert [item["request_id"] for item in items] == [request_id]
        assert items[0]["routing"]["technician_id"] == "TECH-CDM"
        assert runtime.list_approvals("tecnico-geral") == []
    finally:
        runtime.close()


def test_operational_detail_requires_assigned_technician() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        detail = runtime.get_operational_request("tecnico-cdm", request_id)
        assert detail["request_id"] == request_id
        assert detail["policy"]["reason_code"] == "CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL"
        with pytest.raises(WebDemoError) as exc_info:
            runtime.get_operational_request("tecnico-geral", request_id)
        assert exc_info.value.code == "NOT_AUTHORIZED"
    finally:
        runtime.close()


def test_approve_executes_only_after_valid_approval_and_returns_completed_to_pedro() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        assert runtime.fake_cdm_store.access_count == 0

        result = runtime.approve_request("tecnico-cdm", request_id, expected_version=2)
        assert result["state"] == "COMPLETED"
        assert result["execution_result_code"] == "CDM_ACCESS_CREATED"
        assert [item["event_type"] for item in result["timeline"]][-3:] == [
            "REQUEST_APPROVED",
            "EXECUTION_STARTED",
            "EXECUTION_COMPLETED",
        ]
        assert runtime.fake_cdm_store.access_count == 1
        assert runtime.list_approvals("tecnico-cdm") == []

        requester_detail = runtime.get_request("pedro-miranda", request_id)
        assert requester_detail["state"] == "COMPLETED"
        assert requester_detail["state_label"] == "Concluída"
        assert requester_detail["execution_result_code"] == "CDM_ACCESS_CREATED"
    finally:
        runtime.close()


def test_requester_cannot_approve_and_no_external_execution_happens() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        with pytest.raises(WebDemoError) as exc_info:
            runtime.approve_request("pedro-miranda", request_id, expected_version=2)
        assert exc_info.value.code == "NOT_AUTHORIZED"
        assert runtime.request_repository.get(request_id).state == "PENDING_APPROVAL"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_unassigned_technician_cannot_approve_and_no_external_execution_happens() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        with pytest.raises(WebDemoError) as exc_info:
            runtime.approve_request("tecnico-geral", request_id, expected_version=2)
        assert exc_info.value.code == "NOT_AUTHORIZED"
        assert runtime.request_repository.get(request_id).state == "PENDING_APPROVAL"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_missing_routing_fails_closed_before_approval() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        runtime.routing_store = InMemoryRoutingAssignmentStore()
        with pytest.raises(WebDemoError) as exc_info:
            runtime.approve_request("tecnico-cdm", request_id, expected_version=2)
        assert exc_info.value.code == "ROUTING_INCONSISTENT"
        assert runtime.request_repository.get(request_id).state == "PENDING_APPROVAL"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_inconsistent_routing_fails_closed_before_approval() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        technician = runtime.identity_provider.technician_identity("tecnico-cdm")
        store = InMemoryRoutingAssignmentStore()
        store.assign(RoutingAssignment(request_id, "OTHER", "CDM_ACCESS_REQUEST", technician))
        runtime.routing_store = store
        with pytest.raises(WebDemoError) as exc_info:
            runtime.approve_request("tecnico-cdm", request_id, expected_version=2)
        assert exc_info.value.code == "ROUTING_INCONSISTENT"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_reject_stops_at_rejected_and_never_executes() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        result = runtime.reject_request("tecnico-cdm", request_id, expected_version=2)
        assert result["state"] == "REJECTED"
        assert result["timeline"][-1]["event_type"] == "REQUEST_REJECTED"
        assert runtime.fake_cdm_store.access_count == 0
        assert runtime.list_approvals("tecnico-cdm") == []
    finally:
        runtime.close()


def test_request_outside_pending_approval_cannot_be_decided_again() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        runtime.reject_request("tecnico-cdm", request_id, expected_version=2)
        with pytest.raises(Exception):
            runtime.reject_request("tecnico-cdm", request_id, expected_version=3)
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_execution_failure_from_fake_cdm_returns_failed() -> None:
    runtime = DemoRuntime.create(fail_cdm_request_ids={"REQ-000001"})
    try:
        request_id = _create_cdm_request(runtime)
        result = runtime.approve_request("tecnico-cdm", request_id, expected_version=2)
        assert result["state"] == "FAILED"
        assert result["execution_error_code"] == "CDM_INTERNAL_ERROR"
        assert result["timeline"][-1]["event_type"] == "EXECUTION_FAILED"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_policy_revalidation_can_block_after_valid_approval_without_cdm_call() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        runtime.execution_engine.policy_engine = PolicyEngine(
            [
                PolicyRule(
                    system="CDM",
                    capability="CDM_ACCESS_REQUEST",
                    requested_role="SOLICITANTE",
                    decision="DENY",
                    policy_id="DEMO_EXECUTION_BLOCK",
                    reason_code="DEMO_EXECUTION_BLOCKED",
                    reason="Bloqueio sintético para provar revalidação antes da execução.",
                )
            ]
        )
        result = runtime.approve_request("tecnico-cdm", request_id, expected_version=2)
        assert result["state"] == "DENIED_POLICY"
        assert result["timeline"][-1]["event_type"] == "POLICY_DENIED_BEFORE_EXECUTION"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_prevention_is_generated_by_phase11_engine_and_requester_is_unauthorized() -> None:
    runtime = DemoRuntime.create()
    try:
        expected = OpportunityEngine().generate(
            PatternAggregator.aggregate(runtime.outcome_store.snapshot())
        )
        assert expected

        with pytest.raises(WebDemoError) as exc_info:
            runtime.list_prevention("pedro-miranda")
        assert exc_info.value.code == "NOT_AUTHORIZED"

        items = runtime.list_prevention("tecnico-cdm")
        assert [item["opportunity_id"] for item in items] == [
            item.opportunity_id for item in expected
        ]
        assert [item["occurrence_count"] for item in items] == [
            item.occurrence_count for item in expected
        ]
    finally:
        runtime.close()


def test_prevention_detail_uses_real_opportunity_id_and_unknown_fails_closed() -> None:
    runtime = DemoRuntime.create()
    try:
        item = runtime.list_prevention("tecnico-cdm")[0]
        detail = runtime.get_prevention("tecnico-cdm", item["opportunity_id"])
        assert detail == item
        with pytest.raises(WebDemoError) as exc_info:
            runtime.get_prevention("tecnico-cdm", "OPP-DOES-NOT-EXIST")
        assert exc_info.value.code == "PREVENTION_NOT_FOUND"
    finally:
        runtime.close()
