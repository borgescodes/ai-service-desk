from dataclasses import asdict

import pytest

from ai_service_desk.engine.learning_prevention import (
    OutcomeCollector,
    OutcomeValidationError,
)
from ai_service_desk.engine.request_lifecycle import AccessRequestRecord
from ai_service_desk.engine.routing import RoutingAssignment
from ai_service_desk.engine.technician_authorization import TechnicianIdentity
from ai_service_desk.engine.triage import TriageState
from tests.engine.phase8_helpers import make_record


def answered_triage() -> TriageState:
    return TriageState(
        version=2,
        session_id="SESSION-SYN-001",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text="problema sintetico",
        intent="PROBLEMA_ACESSO",
        system="POWER_BI",
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def knowledge_result() -> dict:
    return {
        "status": "KNOWLEDGE_FOUND",
        "reason": "MATCH",
        "question": None,
        "knowledge": {"knowledge_id": "KB-SYN-POWER-BI-001"},
    }


def playbook_result() -> dict:
    return {
        "status": "PLAYBOOK_FOUND",
        "reason": "MATCH",
        "knowledge_id": "KB-SYN-POWER-BI-001",
        "playbook": {
            "playbook_id": "PB-SYN-POWER-BI-001",
            "playbook_version": 1,
            "steps": [],
        },
    }


def assignment_for(record: AccessRequestRecord) -> RoutingAssignment:
    return RoutingAssignment(
        request_id=record.request_id,
        system=record.context.system,
        capability=record.context.capability,
        technician=TechnicianIdentity(
            technician_id="TECH-SYN",
            username="tech.syn",
            name="Synthetic Technician",
            email="tech.syn@example.invalid",
        ),
    )


def test_from_knowledge_projects_structured_evidence_only() -> None:
    triage = answered_triage()
    result = knowledge_result()
    record = OutcomeCollector.from_knowledge("INT-KB-001", triage, result, area="COMERCIAL")
    assert record.interaction_id == "INT-KB-001"
    assert record.system == "POWER_BI"
    assert record.intent == "PROBLEMA_ACESSO"
    assert record.area == "COMERCIAL"
    assert record.knowledge_id == "KB-SYN-POWER-BI-001"
    assert record.outcome == "RESOLVED_BY_KNOWLEDGE"
    assert record.playbook_id == ""
    assert record.reason_code == "KNOWLEDGE_FOUND"


def test_from_knowledge_rejects_non_answered_triage() -> None:
    triage = answered_triage()
    triage = TriageState(**(asdict(triage) | {"status": "ABSTAINED"}))
    with pytest.raises(OutcomeValidationError) as captured:
        OutcomeCollector.from_knowledge("INT-KB-002", triage, knowledge_result())
    assert captured.value.reason_code == "OUTCOME_EVIDENCE_INVALID"


def test_from_playbook_preserves_approved_ids_without_step_selection() -> None:
    record = OutcomeCollector.from_playbook(
        "INT-PB-001",
        answered_triage(),
        playbook_result(),
        area="COMERCIAL",
    )
    assert record.knowledge_id == "KB-SYN-POWER-BI-001"
    assert record.playbook_id == "PB-SYN-POWER-BI-001"
    assert record.playbook_version == 1
    assert record.step_id == ""
    assert record.outcome == "GUIDED_BY_PLAYBOOK"
    assert record.reason_code == "PLAYBOOK_FOUND"


def test_pending_request_requires_routing_assignment() -> None:
    with pytest.raises(OutcomeValidationError) as captured:
        OutcomeCollector.from_request("INT-REQ-001", make_record("PENDING_APPROVAL"))
    assert captured.value.reason_code == "OUTCOME_EVIDENCE_INVALID"


def test_pending_request_with_assignment_projects_human_route() -> None:
    request = make_record("PENDING_APPROVAL")
    record = OutcomeCollector.from_request("INT-REQ-002", request, assignment_for(request))
    assert record.outcome == "ROUTED_TO_HUMAN"
    assert record.reason_code == "ROUTED_TO_HUMAN"
    assert record.system == request.context.system
    assert record.capability == request.context.capability
    assert record.area == request.context.requester.area


def test_mismatched_assignment_fails_closed() -> None:
    request = make_record("PENDING_APPROVAL")
    wrong = RoutingAssignment(
        request_id="REQ-999999",
        system=request.context.system,
        capability=request.context.capability,
        technician=assignment_for(request).technician,
    )
    with pytest.raises(OutcomeValidationError) as captured:
        OutcomeCollector.from_request("INT-REQ-003", request, wrong)
    assert captured.value.reason_code == "OUTCOME_EVIDENCE_INVALID"


@pytest.mark.parametrize(
    ("state", "expected_outcome", "expected_reason"),
    [
        ("APPROVED", "APPROVED", "APPROVED"),
        ("REJECTED", "REJECTED", "REJECTED"),
        ("DENIED_POLICY", "DENIED_POLICY", "SYNTHETIC_ACCESS_DENIED"),
        ("COMPLETED", "EXECUTION_COMPLETED", "EXECUTION_SUCCEEDED"),
        ("FAILED", "EXECUTION_FAILED", "EXECUTOR_EXCEPTION"),
    ],
)
def test_request_states_project_safe_outcomes(
    state: str,
    expected_outcome: str,
    expected_reason: str,
) -> None:
    record = OutcomeCollector.from_request("INT-REQ-STATE", make_record(state))
    assert record.outcome == expected_outcome
    assert record.reason_code == expected_reason


@pytest.mark.parametrize("state", ["TRIAGED", "EXECUTING"])
def test_transient_request_states_are_not_analytic_outcomes(state: str) -> None:
    with pytest.raises(OutcomeValidationError) as captured:
        OutcomeCollector.from_request("INT-TRANSIENT", make_record(state))
    assert captured.value.reason_code == "OUTCOME_EVIDENCE_INVALID"


def test_collectors_do_not_mutate_inputs_or_copy_sensitive_fields() -> None:
    triage = answered_triage()
    knowledge = knowledge_result()
    triage_before = asdict(triage)
    knowledge_before = knowledge.copy()
    request = make_record("PENDING_APPROVAL")
    assignment = assignment_for(request)
    request_before = request
    assignment_before = assignment

    OutcomeCollector.from_knowledge("INT-SAFE-KB", triage, knowledge, area="COMERCIAL")
    outcome = OutcomeCollector.from_request("INT-SAFE-REQ", request, assignment)

    assert asdict(triage) == triage_before
    assert knowledge == knowledge_before
    assert request == request_before
    assert assignment == assignment_before
    serialized = asdict(outcome)
    forbidden = {"purpose", "username", "email", "name", "technician_id", "answer"}
    assert forbidden.isdisjoint(serialized)
