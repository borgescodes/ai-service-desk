import threading

import pytest

from ai_service_desk.engine.routing import (
    InMemoryRoutingAssignmentStore,
    RoutingAssignment,
    RoutingAssignmentConflictError,
    RoutingAssignmentNotFoundError,
)
from ai_service_desk.engine.technician_authorization import TechnicianIdentity


def _assignment(request_id="REQ-000001", technician_id="TECH-CDM"):
    technician = TechnicianIdentity(
        technician_id=technician_id,
        username=technician_id.lower(),
        name=technician_id,
        email=f"{technician_id.lower()}@example.invalid",
    )
    return RoutingAssignment(request_id, "CDM", "CDM_ACCESS_REQUEST", technician)


def test_assignment_is_idempotent_and_snapshot_is_immutable():
    store = InMemoryRoutingAssignmentStore()
    assignment = _assignment()
    assert store.assign(assignment) == assignment
    assert store.assign(assignment) == assignment
    assert store.snapshot() == (assignment,)
    assert type(store.snapshot()) is tuple


def test_conflicting_assignment_fails_closed_without_overwrite():
    store = InMemoryRoutingAssignmentStore()
    first = _assignment()
    second = _assignment(technician_id="TECH-OTHER")
    store.assign(first)
    with pytest.raises(RoutingAssignmentConflictError) as exc:
        store.assign(second)
    assert exc.value.reason_code == "ROUTING_ASSIGNMENT_CONFLICT"
    assert store.get(first.request_id) == first


def test_missing_assignment_is_explicit():
    store = InMemoryRoutingAssignmentStore()
    assert store.get_optional("REQ-999999") is None
    with pytest.raises(RoutingAssignmentNotFoundError) as exc:
        store.get("REQ-999999")
    assert exc.value.reason_code == "ROUTING_ASSIGNMENT_NOT_FOUND"


def test_same_assignment_is_safe_under_concurrency():
    store = InMemoryRoutingAssignmentStore()
    assignment = _assignment()
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait(timeout=5)
        results.append(store.assign(assignment))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert results == [assignment, assignment]
    assert store.snapshot() == (assignment,)


def test_conflicting_assignments_are_atomic_under_concurrency():
    store = InMemoryRoutingAssignmentStore()
    barrier = threading.Barrier(2)
    outcomes = []

    def worker(assignment):
        barrier.wait(timeout=5)
        try:
            store.assign(assignment)
        except RoutingAssignmentConflictError as exc:
            assert exc.reason_code == "ROUTING_ASSIGNMENT_CONFLICT"
            outcomes.append("conflict")
        else:
            outcomes.append("saved")

    threads = [
        threading.Thread(target=worker, args=(_assignment(technician_id="TECH-A"),)),
        threading.Thread(target=worker, args=(_assignment(technician_id="TECH-B"),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == ["conflict", "saved"]
    assert len(store.snapshot()) == 1
