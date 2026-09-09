from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from ai_service_desk.engine.request_lifecycle import ConcurrencyConflictError
from tests.engine.phase8_helpers import DEFAULT_TIMESTAMP
from tests.engine.test_approval import make_system
from tests.engine.test_execution import make_engine
from tests.engine.test_request_repository import repository_fixture
from tests.engine.test_technician_authorization import TECH


def interleave_first_two(repository, monkeypatch):
    barrier = Barrier(2)
    lock = Lock()
    count = 0

    def before():
        nonlocal count
        with lock:
            count += 1
            wait = count <= 2
        if wait:
            barrier.wait(timeout=5)

    monkeypatch.setattr(repository, "_before_final_cas", before)


def race(functions):
    def run(function):
        try:
            function()
            return "saved"
        except ConcurrencyConflictError as exc:
            assert exc.reason_code == "VERSION_CONFLICT"
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, functions))
    assert sorted(results) == ["conflict", "saved"]


def test_repository_final_cas_is_atomic_under_forced_interleaving(monkeypatch):
    repo, current, pending, event = repository_fixture()
    interleave_first_two(repo, monkeypatch)
    race([lambda: repo.save(pending, expected_version=1, audit_events=(event,))] * 2)
    assert repo.get(current.request_id) == pending
    assert len(repo.audit_for(current.request_id)) == 2


def test_double_human_decision_persists_exactly_one_transition(monkeypatch):
    repo, _, service, pending = make_system()
    service.clock = lambda: DEFAULT_TIMESTAMP
    interleave_first_two(repo, monkeypatch)
    race(
        [
            lambda: service.approve(pending.request_id, TECH, expected_version=2),
            lambda: service.reject(pending.request_id, TECH, expected_version=2),
        ]
    )
    assert repo.get(pending.request_id).state in {"APPROVED", "REJECTED"}
    assert repo.get(pending.request_id).version == 3
    assert len(repo.audit_for(pending.request_id)) == 3


def test_double_execution_calls_executor_exactly_once(monkeypatch):
    engine, approved = make_engine()
    engine.clock = lambda: DEFAULT_TIMESTAMP
    interleave_first_two(engine.repository, monkeypatch)
    race([lambda: engine.execute(approved.request_id, expected_version=3)] * 2)
    assert len(engine.executor.calls) == 1
    assert engine.repository.get(approved.request_id).state == "COMPLETED"
    assert len(engine.repository.audit_for(approved.request_id)) == 5


def test_concurrent_ids_are_unique_and_monotonic():
    from ai_service_desk.engine.request_repository import InMemoryRequestRepository

    repo = InMemoryRequestRepository()
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: repo.allocate_request_id(), range(64)))
    assert sorted(ids) == [f"REQ-{i:06d}" for i in range(1, 65)]
