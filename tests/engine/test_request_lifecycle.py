from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

from ai_service_desk.engine.confidence import ConfidenceAssessment
from ai_service_desk.engine.request_lifecycle import (
    ALLOWED_TRANSITIONS,
    REQUEST_STATES,
    AccessRequestRecord,
    AuditEvent,
    AuditEventValidationError,
    ConcurrencyConflictError,
    ExpectedVersionValidationError,
    InvalidStateTransitionError,
    Phase8DomainError,
    RecordInvariantError,
    RequestNotFoundError,
    validate_access_request_record,
    validate_audit_event,
    validate_expected_version,
)
from tests.engine.phase8_helpers import (
    DEFAULT_TIMESTAMP,
    make_context,
    make_policy_decision,
    make_record,
)


def make_audit_event(**changes: object) -> AuditEvent:
    event = AuditEvent(
        request_id="REQ-000001",
        event_type="REQUEST_CREATED",
        actor_type="SYSTEM",
        actor_id="SYSTEM",
        from_state=None,
        to_state="TRIAGED",
        record_version=1,
        reason_code="REQUEST_CREATED",
        policy_id=None,
        occurred_at=DEFAULT_TIMESTAMP,
    )
    return replace(event, **changes)


def test_request_states_are_exactly_the_eight_frozen_states() -> None:
    assert REQUEST_STATES == frozenset(
        {
            "TRIAGED",
            "PENDING_APPROVAL",
            "APPROVED",
            "REJECTED",
            "DENIED_POLICY",
            "EXECUTING",
            "COMPLETED",
            "FAILED",
        }
    )


def test_allowed_transitions_are_the_closed_eight_transition_matrix() -> None:
    assert ALLOWED_TRANSITIONS == frozenset(
        {
            ("TRIAGED", "PENDING_APPROVAL"),
            ("TRIAGED", "DENIED_POLICY"),
            ("PENDING_APPROVAL", "APPROVED"),
            ("PENDING_APPROVAL", "REJECTED"),
            ("APPROVED", "EXECUTING"),
            ("APPROVED", "DENIED_POLICY"),
            ("EXECUTING", "COMPLETED"),
            ("EXECUTING", "FAILED"),
        }
    )


def test_lifecycle_snapshots_are_frozen_dataclasses() -> None:
    record = make_record()
    event = make_audit_event()

    with pytest.raises(FrozenInstanceError):
        record.version = 2  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        event.record_version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "error_type",
    [
        RequestNotFoundError,
        InvalidStateTransitionError,
        ExpectedVersionValidationError,
        ConcurrencyConflictError,
        RecordInvariantError,
        AuditEventValidationError,
    ],
)
def test_phase8_domain_errors_preserve_stable_reason_code(
    error_type: type[Phase8DomainError],
) -> None:
    error = error_type("SYNTHETIC_REASON", "Synthetic failure.")

    assert isinstance(error, Phase8DomainError)
    assert error.reason_code == "SYNTHETIC_REASON"
    assert str(error) == "Synthetic failure."


@pytest.mark.parametrize("value", [True, False, 3.0, "3", None, 0, -1])
def test_validate_expected_version_rejects_non_exact_positive_integers(value: object) -> None:
    with pytest.raises(ExpectedVersionValidationError) as exc_info:
        validate_expected_version(value)

    assert exc_info.value.reason_code == "EXPECTED_VERSION_INVALID"


def test_validate_expected_version_returns_exact_positive_integer() -> None:
    assert validate_expected_version(3) == 3


@pytest.mark.parametrize(
    "record",
    [
        make_record("TRIAGED"),
        make_record("PENDING_APPROVAL"),
        make_record("APPROVED"),
        make_record("REJECTED"),
        make_record("DENIED_POLICY"),
        make_record("EXECUTING"),
        make_record("COMPLETED"),
        make_record("FAILED"),
    ],
)
def test_validate_access_request_record_accepts_structurally_coherent_states(
    record: AccessRequestRecord,
) -> None:
    assert validate_access_request_record(record) is None


def test_denied_policy_after_approval_preserves_the_complete_decision_pair() -> None:
    record = make_record(
        "DENIED_POLICY",
        creation_policy=make_policy_decision("REQUIRE_APPROVAL"),
        latest_policy=make_policy_decision("DENY"),
        decided_by="TECH-SYNTHETIC",
        decided_at=DEFAULT_TIMESTAMP,
    )

    assert validate_access_request_record(record) is None


@pytest.mark.parametrize(
    "record",
    [
        make_record(request_id=""),
        make_record(version=True),
        make_record(version=0),
        make_record(state="UNKNOWN"),
        make_record(context=object()),
        make_record(context=replace(make_context(), requester=object())),
        make_record(creation_policy=object()),
        make_record(creation_policy=make_policy_decision(decision="ALLOW")),
        make_record(latest_policy=object()),
        make_record(confidence=object()),
        make_record(confidence=ConfidenceAssessment("MEDIUM", ("SYNTHETIC_REASON",))),
        make_record(confidence=ConfidenceAssessment("HIGH", ["SYNTHETIC_REASON"])),
        make_record("PENDING_APPROVAL", decided_by="TECH-SYNTHETIC"),
        make_record(
            "PENDING_APPROVAL",
            decided_by="TECH-SYNTHETIC",
            decided_at=DEFAULT_TIMESTAMP,
        ),
        make_record("APPROVED", decided_by=None),
        make_record("REJECTED", decided_at=None),
        make_record(
            "DENIED_POLICY",
            decided_by="TECH-SYNTHETIC",
            decided_at=DEFAULT_TIMESTAMP,
        ),
        make_record(
            "DENIED_POLICY",
            creation_policy=make_policy_decision("REQUIRE_APPROVAL"),
            latest_policy=make_policy_decision("DENY"),
        ),
        make_record("EXECUTING", execution_started_at=None),
        make_record("EXECUTING", execution_finished_at=DEFAULT_TIMESTAMP),
        make_record("COMPLETED", execution_finished_at=None),
        make_record("COMPLETED", execution_result_code=None),
        make_record("COMPLETED", execution_error_code="EXECUTOR_EXCEPTION"),
        make_record("FAILED", execution_error_code=None),
        make_record("TRIAGED", execution_result_code="UNEXPECTED_RESULT"),
    ],
)
def test_validate_access_request_record_rejects_runtime_structural_invariants(
    record: object,
) -> None:
    with pytest.raises(RecordInvariantError) as exc_info:
        validate_access_request_record(record)  # type: ignore[arg-type]

    assert exc_info.value.reason_code == "RECORD_INVARIANT_INVALID"


@pytest.mark.parametrize(
    ("state", "field"),
    [
        ("TRIAGED", "created_at"),
        ("TRIAGED", "updated_at"),
        ("APPROVED", "decided_at"),
        ("EXECUTING", "execution_started_at"),
        ("COMPLETED", "execution_finished_at"),
    ],
)
def test_validate_access_request_record_rejects_naive_timestamps(
    state: str,
    field: str,
) -> None:
    record = make_record(state, **{field: datetime(2026, 9, 9, 12, 0)})  # type: ignore[arg-type]

    with pytest.raises(RecordInvariantError) as exc_info:
        validate_access_request_record(record)

    assert exc_info.value.reason_code == "RECORD_INVARIANT_INVALID"


@pytest.mark.parametrize(
    "event",
    [
        object(),
        make_audit_event(request_id=""),
        make_audit_event(event_type="UNKNOWN_EVENT"),
        make_audit_event(actor_type="ROBOT"),
        make_audit_event(actor_id=""),
        make_audit_event(from_state="UNKNOWN"),
        make_audit_event(to_state="UNKNOWN"),
        make_audit_event(record_version=True),
        make_audit_event(record_version=0),
        make_audit_event(reason_code="bad reason"),
        make_audit_event(policy_id="bad policy"),
        make_audit_event(occurred_at=datetime(2026, 9, 9, 12, 0)),
    ],
)
def test_validate_audit_event_rejects_runtime_structural_invariants(event: object) -> None:
    with pytest.raises(AuditEventValidationError) as exc_info:
        validate_audit_event(event)  # type: ignore[arg-type]

    assert exc_info.value.reason_code == "AUDIT_EVENT_INVALID"


def test_validate_audit_event_accepts_timezone_aware_canonical_event() -> None:
    event = make_audit_event(occurred_at=datetime(2026, 9, 9, 12, 0, tzinfo=UTC))

    assert validate_audit_event(event) is None


@pytest.mark.parametrize(
    "event",
    [
        make_audit_event(),
        make_audit_event(
            event_type="POLICY_REQUIRES_APPROVAL",
            from_state="TRIAGED",
            to_state="PENDING_APPROVAL",
            record_version=2,
            reason_code="SYNTHETIC_REQUIRES_APPROVAL",
            policy_id="SYNTHETIC_ACCESS_POLICY",
        ),
        make_audit_event(
            event_type="POLICY_DENIED_AT_CREATION",
            from_state="TRIAGED",
            to_state="DENIED_POLICY",
            record_version=2,
            reason_code="SYNTHETIC_ACCESS_DENIED",
            policy_id="SYNTHETIC_ACCESS_POLICY",
        ),
        make_audit_event(
            event_type="REQUEST_APPROVED",
            actor_type="TECHNICIAN",
            actor_id="TECH-SYNTHETIC",
            from_state="PENDING_APPROVAL",
            to_state="APPROVED",
            record_version=3,
            reason_code="APPROVED_BY_AUTHORIZED_TECHNICIAN",
        ),
        make_audit_event(
            event_type="REQUEST_REJECTED",
            actor_type="TECHNICIAN",
            actor_id="TECH-SYNTHETIC",
            from_state="PENDING_APPROVAL",
            to_state="REJECTED",
            record_version=3,
            reason_code="REJECTED_BY_AUTHORIZED_TECHNICIAN",
        ),
        make_audit_event(
            event_type="POLICY_DENIED_BEFORE_EXECUTION",
            from_state="APPROVED",
            to_state="DENIED_POLICY",
            record_version=4,
            reason_code="SYNTHETIC_ACCESS_DENIED",
            policy_id="SYNTHETIC_ACCESS_POLICY",
        ),
        make_audit_event(
            event_type="EXECUTION_STARTED",
            from_state="APPROVED",
            to_state="EXECUTING",
            record_version=4,
            reason_code="SYNTHETIC_REQUIRES_APPROVAL",
            policy_id="SYNTHETIC_ACCESS_POLICY",
        ),
        make_audit_event(
            event_type="EXECUTION_COMPLETED",
            from_state="EXECUTING",
            to_state="COMPLETED",
            record_version=5,
            reason_code="FAKE_EXECUTION_SUCCEEDED",
        ),
        make_audit_event(
            event_type="EXECUTION_FAILED",
            from_state="EXECUTING",
            to_state="FAILED",
            record_version=5,
            reason_code="EXECUTOR_EXCEPTION",
        ),
    ],
)
def test_validate_audit_event_accepts_the_canonical_event_matrix(event: AuditEvent) -> None:
    assert validate_audit_event(event) is None


@pytest.mark.parametrize(
    "event",
    [
        make_audit_event(reason_code="WRONG_CREATED_REASON"),
        make_audit_event(actor_id="OTHER_SYSTEM"),
        make_audit_event(
            event_type="REQUEST_APPROVED",
            from_state="PENDING_APPROVAL",
            to_state="APPROVED",
            record_version=3,
            reason_code="APPROVED_BY_AUTHORIZED_TECHNICIAN",
        ),
        make_audit_event(
            event_type="REQUEST_REJECTED",
            actor_type="TECHNICIAN",
            actor_id="TECH-SYNTHETIC",
            from_state="PENDING_APPROVAL",
            to_state="APPROVED",
            record_version=3,
            reason_code="REJECTED_BY_AUTHORIZED_TECHNICIAN",
        ),
        make_audit_event(
            event_type="EXECUTION_STARTED",
            from_state="APPROVED",
            to_state="EXECUTING",
            record_version=4,
            reason_code="SYNTHETIC_REQUIRES_APPROVAL",
            policy_id=None,
        ),
    ],
)
def test_validate_audit_event_rejects_noncanonical_event_semantics(event: AuditEvent) -> None:
    with pytest.raises(AuditEventValidationError) as exc_info:
        validate_audit_event(event)

    assert exc_info.value.reason_code == "AUDIT_EVENT_INVALID"
