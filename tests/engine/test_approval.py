import inspect
from dataclasses import replace

import pytest

from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.request_lifecycle import Phase8DomainError, RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianRegistryEntry,
)
from tests.engine.phase8_helpers import DEFAULT_TIMESTAMP, FixedClock, make_context
from tests.engine.test_technician_authorization import TECH


def make_system(
    role="SOLICITANTE",
    technician=TECH,
    capabilities=frozenset({"CDM_ACCESS_REQUEST"}),
    context=None,
):
    repository = InMemoryRequestRepository()
    lifecycle = RequestLifecycleService(repository, clock=FixedClock())
    pending = lifecycle.create_request(context or make_context(requested_role=role))
    registry = TechnicianAuthorizationRegistry([TechnicianRegistryEntry(technician, capabilities)])
    service = ApprovalService(repository, lifecycle, registry, clock=FixedClock())
    return repository, lifecycle, service, pending


def denied_decision(
    method,
    *,
    role="SOLICITANTE",
    technician=TECH,
    registered=TECH,
    capabilities=frozenset({"CDM_ACCESS_REQUEST"}),
    code,
    expected_version=2,
):
    repo, _, service, pending = make_system(role, registered, capabilities)
    before = repo.audit_for(pending.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        getattr(service, method)(pending.request_id, technician, expected_version=expected_version)
    assert exc.value.reason_code == code
    assert repo.get(pending.request_id) == pending
    assert repo.audit_for(pending.request_id) == before
    assert service.clock.calls == 0


def test_denied_policy_cannot_be_approved():
    denied_decision("approve", role="ADMIN", code="INVALID_STATE_TRANSITION")


def test_denied_policy_cannot_be_rejected():
    denied_decision("reject", role="ADMIN", code="INVALID_STATE_TRANSITION")


def test_technician_without_capability_cannot_approve():
    denied_decision("approve", capabilities=frozenset(), code="TECHNICIAN_CAPABILITY_REQUIRED")


def test_technician_without_capability_cannot_reject():
    denied_decision("reject", capabilities=frozenset(), code="TECHNICIAN_CAPABILITY_REQUIRED")


@pytest.mark.parametrize("method", ["approve", "reject"])
def test_unregistered_technician_cannot_decide(method):
    denied_decision(
        method,
        technician=replace(TECH, technician_id="UNREGISTERED"),
        code="TECHNICIAN_CAPABILITY_REQUIRED",
    )


@pytest.mark.parametrize("method", ["approve", "reject"])
def test_registry_identity_mismatch_cannot_decide(method):
    denied_decision(
        method,
        technician=replace(TECH, email="other@example.invalid"),
        code="TECHNICIAN_CAPABILITY_REQUIRED",
    )


def test_requester_username_cannot_approve_own_request():
    tech = replace(TECH, username=make_context().requester.username)
    denied_decision("approve", technician=tech, registered=tech, code="SELF_DECISION_NOT_ALLOWED")


def test_requester_email_cannot_reject_own_request():
    tech = replace(TECH, email=make_context().requester.email)
    denied_decision("reject", technician=tech, registered=tech, code="SELF_DECISION_NOT_ALLOWED")


@pytest.mark.parametrize("method", ["approve", "reject"])
@pytest.mark.parametrize("field", ["username", "email"])
def test_self_decision_normalizes_case_and_outer_whitespace(method, field):
    tech = replace(TECH, **{field: " " + getattr(make_context().requester, field).upper() + " "})
    denied_decision(method, technician=tech, registered=tech, code="SELF_DECISION_NOT_ALLOWED")


def authorized_decision(method, state):
    repo, _, service, pending = make_system()
    result = getattr(service, method)(pending.request_id, TECH, expected_version=2)
    assert result.state == state
    assert result.version == 3
    assert result.decided_by == TECH.technician_id
    assert result.decided_at == DEFAULT_TIMESTAMP
    assert result.execution_started_at is None
    assert result.execution_finished_at is None
    assert len(repo.audit_for(result.request_id)) == 3
    assert repo.audit_for(result.request_id)[-1].actor_id == TECH.technician_id
    return repo, service, pending


def test_authorized_technician_approves_pending_request():
    authorized_decision("approve", "APPROVED")


def test_authorized_technician_rejects_pending_request():
    authorized_decision("reject", "REJECTED")


def test_approve_makes_zero_executor_calls():
    repo, _, pending = authorized_decision("approve", "APPROVED")
    assert not any(
        e.event_type.startswith("EXECUTION_") for e in repo.audit_for(pending.request_id)
    )
    assert set(inspect.signature(ApprovalService).parameters) == {
        "repository",
        "lifecycle",
        "registry",
        "clock",
    }


def test_reject_makes_zero_executor_calls():
    repo, _, pending = authorized_decision("reject", "REJECTED")
    assert not any(
        e.event_type.startswith("EXECUTION_") for e in repo.audit_for(pending.request_id)
    )


def stale_decision(method):
    repo, _, service, pending = make_system()
    approved = service.approve(pending.request_id, TECH, expected_version=2)
    before = repo.audit_for(pending.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        getattr(service, method)(pending.request_id, None, expected_version=2)
    assert exc.value.reason_code == "VERSION_CONFLICT"
    assert repo.get(pending.request_id) == approved
    assert repo.audit_for(pending.request_id) == before
    assert service.clock.calls == 1


def test_stale_approval_conflicts_before_state_or_authorization():
    stale_decision("approve")


def test_stale_rejection_conflicts_before_state_or_authorization():
    stale_decision("reject")


@pytest.mark.parametrize("value", [True, False, 3.0, "3", None, 0, -1])
@pytest.mark.parametrize("method", ["approve", "reject"])
def test_approval_expected_version_is_exact_positive_integer(method, value):
    denied_decision(
        method, technician=None, expected_version=value, code="EXPECTED_VERSION_INVALID"
    )
