from dataclasses import replace
from datetime import timedelta

import pytest

from ai_service_desk.engine.request_lifecycle import (
    Phase8DomainError,
    validate_access_request_record,
)
from tests.engine.phase8_helpers import DEFAULT_TIMESTAMP, make_record
from tests.engine.test_execution import make_engine
from tests.engine.test_request_repository import repository_fixture


@pytest.mark.parametrize(
    "state", ["PENDING_APPROVAL", "APPROVED", "EXECUTING", "COMPLETED", "FAILED"]
)
def test_all_persisted_timestamps_are_timezone_aware(state):
    engine, record = make_engine(state)
    for name in (
        "created_at",
        "updated_at",
        "decided_at",
        "execution_started_at",
        "execution_finished_at",
    ):
        value = getattr(record, name)
        if value is not None:
            assert value.tzinfo is not None and value.utcoffset() is not None
    assert all(
        e.occurred_at.utcoffset() is not None
        for e in engine.repository.audit_for(record.request_id)
    )


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_naive_datetime_is_rejected(field):
    repo, current, pending, event = repository_fixture()
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(
            replace(pending, **{field: DEFAULT_TIMESTAMP.replace(tzinfo=None)}),
            expected_version=1,
            audit_events=(event,),
        )
    assert exc.value.reason_code == "RECORD_INVARIANT_INVALID"
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before


def test_created_at_after_updated_at_is_record_invariant_invalid():
    invalid = make_record(updated_at=DEFAULT_TIMESTAMP - timedelta(seconds=1))
    with pytest.raises(Phase8DomainError) as exc:
        validate_access_request_record(invalid)
    assert exc.value.reason_code == "RECORD_INVARIANT_INVALID"


def temporal_transition(source, target):
    from tests.engine.test_request_lifecycle import make_audit_event

    engine, current = make_engine(source)
    repo = engine.repository
    before = repo.audit_for(current.request_id)
    earlier = DEFAULT_TIMESTAMP - timedelta(seconds=1)
    later = DEFAULT_TIMESTAMP + timedelta(seconds=1)
    changes = {
        "APPROVED": {"decided_by": "TECH-001", "decided_at": earlier},
        "EXECUTING": {"execution_started_at": earlier},
        "COMPLETED": {
            "execution_finished_at": earlier,
            "execution_result_code": "FAKE_EXECUTION_SUCCEEDED",
        },
    }[target]
    next_record = replace(
        current, state=target, version=current.version + 1, updated_at=later, **changes
    )
    event_type, reason, policy_id = {
        "APPROVED": ("REQUEST_APPROVED", "APPROVED_BY_AUTHORIZED_TECHNICIAN", None),
        "EXECUTING": (
            "EXECUTION_STARTED",
            current.latest_policy.reason_code,
            current.latest_policy.policy_id,
        ),
        "COMPLETED": ("EXECUTION_COMPLETED", "FAKE_EXECUTION_SUCCEEDED", None),
    }[target]
    event = make_audit_event(
        event_type=event_type,
        from_state=source,
        to_state=target,
        record_version=next_record.version,
        occurred_at=later,
        reason_code=reason,
        policy_id=policy_id,
        actor_type="TECHNICIAN" if target == "APPROVED" else "SYSTEM",
        actor_id="TECH-001" if target == "APPROVED" else "SYSTEM",
    )
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(next_record, expected_version=current.version, audit_events=(event,))
    assert exc.value.reason_code == "RECORD_INVARIANT_INVALID"
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before


def test_created_at_after_decided_at_is_record_invariant_invalid():
    temporal_transition("PENDING_APPROVAL", "APPROVED")


def test_decided_at_after_execution_started_at_is_record_invariant_invalid():
    temporal_transition("APPROVED", "EXECUTING")


def test_execution_started_at_after_finished_at_is_record_invariant_invalid():
    temporal_transition("EXECUTING", "COMPLETED")


def test_audit_timestamp_regression_is_audit_event_invalid():
    repo, current, pending, event = repository_fixture()
    before = repo.audit_for(current.request_id)
    event = replace(event, occurred_at=DEFAULT_TIMESTAMP - timedelta(seconds=1))
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(pending, expected_version=1, audit_events=(event,))
    assert exc.value.reason_code == "AUDIT_EVENT_INVALID"
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before


def test_equal_timestamps_are_allowed_and_ordered_by_version_and_append():
    engine, approved = make_engine()
    result = engine.execute(approved.request_id, expected_version=3)
    events = engine.repository.audit_for(result.request_id)
    assert [event.record_version for event in events] == [1, 2, 3, 4, 5]
    assert [event.occurred_at for event in events] == sorted(event.occurred_at for event in events)
    assert events[-1].occurred_at == events[-2].occurred_at


def test_save_rejects_updated_at_regression_without_write_or_audit():
    repo, current, pending, event = repository_fixture()
    future = DEFAULT_TIMESTAMP + timedelta(hours=1)
    pending = replace(pending, updated_at=future)
    repo.save(pending, expected_version=1, audit_events=(replace(event, occurred_at=future),))
    from tests.engine.test_request_lifecycle import make_audit_event

    approved = replace(
        pending,
        state="APPROVED",
        version=3,
        updated_at=DEFAULT_TIMESTAMP,
        decided_by="TECH-001",
        decided_at=DEFAULT_TIMESTAMP,
    )
    decision = make_audit_event(
        event_type="REQUEST_APPROVED",
        actor_type="TECHNICIAN",
        actor_id="TECH-001",
        from_state="PENDING_APPROVAL",
        to_state="APPROVED",
        record_version=3,
        reason_code="APPROVED_BY_AUTHORIZED_TECHNICIAN",
    )
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(approved, expected_version=2, audit_events=(decision,))
    assert exc.value.reason_code == "RECORD_INVARIANT_INVALID"
    assert repo.get(current.request_id) == pending
    assert repo.audit_for(current.request_id) == before


def test_save_accepts_equal_updated_at_when_other_invariants_hold():
    repo, current, pending, event = repository_fixture()
    assert (
        repo.save(pending, expected_version=1, audit_events=(event,)).updated_at
        == current.updated_at
    )
