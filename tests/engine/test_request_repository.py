from dataclasses import replace

import pytest

from ai_service_desk.engine.request_lifecycle import Phase8DomainError
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from tests.engine.phase8_helpers import make_record
from tests.engine.test_request_lifecycle import make_audit_event


def repository_fixture():
    repository = InMemoryRequestRepository()
    current = make_record(request_id=repository.allocate_request_id())
    created = make_audit_event(request_id=current.request_id)
    repository.create(current, audit_events=(created,))
    pending = replace(current, version=2, state="PENDING_APPROVAL")
    event = make_audit_event(
        event_type="POLICY_REQUIRES_APPROVAL",
        from_state="TRIAGED",
        to_state="PENDING_APPROVAL",
        record_version=2,
        reason_code=current.creation_policy.reason_code,
        policy_id=current.creation_policy.policy_id,
    )
    return repository, current, pending, event


def test_first_request_id_is_req_000001():
    assert InMemoryRequestRepository().allocate_request_id() == "REQ-000001"


def test_request_ids_are_monotonic():
    repo = InMemoryRequestRepository()
    assert [repo.allocate_request_id() for _ in range(3)] == [
        "REQ-000001",
        "REQ-000002",
        "REQ-000003",
    ]


def test_new_repository_restarts_id_sequence():
    repo = InMemoryRequestRepository()
    repo.allocate_request_id()
    assert InMemoryRequestRepository().allocate_request_id() == "REQ-000001"


def test_audit_for_returns_tuple_snapshot():
    repo, current, _, _ = repository_fixture()
    assert isinstance(repo.audit_for(current.request_id), tuple)
    assert repo.get(current.request_id) == current


def test_existing_audit_remains_immutable_prefix_after_save():
    repo, current, pending, event = repository_fixture()
    before = repo.audit_for(current.request_id)
    assert repo.save(pending, expected_version=1, audit_events=(event,)) == pending
    assert repo.get(current.request_id) == pending
    assert repo.audit_for(current.request_id) == before + (event,)
    assert len(before) == 1


def test_repository_exposes_no_audit_update_or_delete_api():
    repo = InMemoryRequestRepository()
    assert {name for name in dir(repo) if not name.startswith("_")} == {
        "allocate_request_id",
        "create",
        "get",
        "save",
        "audit_for",
    }


def assert_invalid_version(value):
    repo, current, pending, event = repository_fixture()
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(pending, expected_version=value, audit_events=(event,))
    assert exc.value.reason_code == "EXPECTED_VERSION_INVALID"
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before


def test_expected_version_true_is_invalid():
    assert_invalid_version(True)


def test_expected_version_false_is_invalid():
    assert_invalid_version(False)


def test_expected_version_float_is_invalid():
    assert_invalid_version(3.0)


def test_expected_version_string_is_invalid():
    assert_invalid_version("3")


def test_expected_version_none_is_invalid():
    assert_invalid_version(None)


@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_expected_version_is_invalid(value):
    assert_invalid_version(value)


def test_stale_save_preserves_record_and_audit():
    repo, current, pending, event = repository_fixture()
    repo.save(pending, expected_version=1, audit_events=(event,))
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(pending, expected_version=1, audit_events=(event,))
    assert exc.value.reason_code == "VERSION_CONFLICT"
    assert repo.get(current.request_id) == pending
    assert repo.audit_for(current.request_id) == before


@pytest.mark.parametrize("method", ["get", "audit_for"])
def test_missing_request_has_domain_error(method):
    with pytest.raises(Phase8DomainError) as exc:
        getattr(InMemoryRequestRepository(), method)("REQ-999999")
    assert exc.value.reason_code == "REQUEST_NOT_FOUND"


@pytest.mark.parametrize(
    "change",
    [
        {"version": 3},
        {"created_at": None},
        {
            "context": make_record().context.__class__(
                **(vars(make_record().context) | {"purpose": "changed purpose"})
            )
        },
        {"state": "TRIAGED"},
    ],
)
def test_invalid_save_is_atomic(change):
    repo, current, pending, event = repository_fixture()
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError):
        repo.save(replace(pending, **change), expected_version=1, audit_events=(event,))
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before


@pytest.mark.parametrize(
    "change",
    [
        {"request_id": "REQ-999999"},
        {"reason_code": "WRONG_POLICY"},
        {"policy_id": "WRONG_POLICY"},
        {"record_version": 3},
    ],
)
def test_audit_mismatch_has_no_partial_write(change):
    repo, current, pending, event = repository_fixture()
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        repo.save(pending, expected_version=1, audit_events=(replace(event, **change),))
    assert exc.value.reason_code == "AUDIT_EVENT_INVALID"
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before


def test_create_rejects_invalid_record_and_duplicate_id_atomically():
    repo, current, _, _ = repository_fixture()
    before = repo.audit_for(current.request_id)
    with pytest.raises(Phase8DomainError):
        repo.create(current, audit_events=(make_audit_event(),))
    assert repo.get(current.request_id) == current
    assert repo.audit_for(current.request_id) == before
    invalid = replace(current, request_id="REQ-000002", version=2)
    with pytest.raises(Phase8DomainError):
        repo.create(invalid, audit_events=(make_audit_event(request_id="REQ-000002"),))
    with pytest.raises(Phase8DomainError) as exc:
        repo.get("REQ-000002")
    assert exc.value.reason_code == "REQUEST_NOT_FOUND"


@pytest.mark.parametrize("events", [(), [], (make_audit_event(), make_audit_event())])
def test_create_requires_one_canonical_event(events):
    repo = InMemoryRequestRepository()
    with pytest.raises(Phase8DomainError):
        repo.create(make_record(), audit_events=events)
    with pytest.raises(Phase8DomainError):
        repo.get("REQ-000001")
