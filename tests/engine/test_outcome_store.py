from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace

import pytest

from ai_service_desk.engine.learning_prevention import (
    InMemoryOutcomeStore,
    OutcomeConflictError,
    OutcomeNotFoundError,
    OutcomeRecord,
    OutcomeValidationError,
    validate_outcome_record,
)


def outcome(interaction_id: str = "INT-001", **changes: object) -> OutcomeRecord:
    record = OutcomeRecord(
        interaction_id=interaction_id,
        system="POWER_BI",
        intent="PROBLEMA_ACESSO",
        capability="POWER_BI_SUPPORT_REQUEST",
        area="COMERCIAL",
        knowledge_id="KB-SYN-POWER-BI-001",
        playbook_id="PB-SYN-POWER-BI-001",
        playbook_version=1,
        step_id="STEP-SYN-POWER-BI-001",
        outcome="ROUTED_TO_HUMAN",
        reason_code="ROUTED_TO_HUMAN",
    )
    return replace(record, **changes)


def test_outcome_record_is_frozen() -> None:
    record = outcome()
    with pytest.raises(FrozenInstanceError):
        record.outcome = "REJECTED"


def test_validate_outcome_record_accepts_valid_record() -> None:
    assert validate_outcome_record(outcome()) is None


def test_validate_outcome_record_rejects_unknown_outcome() -> None:
    with pytest.raises(OutcomeValidationError) as captured:
        validate_outcome_record(outcome(outcome="UNKNOWN"))
    assert captured.value.reason_code == "OUTCOME_INVALID"


@pytest.mark.parametrize(
    "changes",
    [
        {"playbook_id": "", "playbook_version": 1, "step_id": ""},
        {"playbook_id": "PB-SYN", "playbook_version": None, "step_id": "STEP-SYN"},
        {"playbook_id": "PB-SYN", "playbook_version": 0, "step_id": "STEP-SYN"},
    ],
)
def test_validate_outcome_record_rejects_incoherent_playbook_fields(changes: dict) -> None:
    with pytest.raises(OutcomeValidationError) as captured:
        validate_outcome_record(outcome(**changes))
    assert captured.value.reason_code == "OUTCOME_INVALID"


def test_store_ingests_and_returns_record() -> None:
    store = InMemoryOutcomeStore()
    record = outcome()
    assert store.ingest(record) == record
    assert store.get(record.interaction_id) == record


def test_identical_replay_is_idempotent() -> None:
    store = InMemoryOutcomeStore()
    record = outcome()
    first = store.ingest(record)
    second = store.ingest(record)
    assert first == second == record
    assert store.snapshot() == (record,)


def test_same_interaction_with_different_payload_fails_closed() -> None:
    store = InMemoryOutcomeStore()
    store.ingest(outcome())
    with pytest.raises(OutcomeConflictError) as captured:
        store.ingest(outcome(outcome="REJECTED", reason_code="REJECTED_BY_HUMAN"))
    assert captured.value.reason_code == "OUTCOME_CONFLICT"
    assert store.snapshot() == (outcome(),)


def test_get_missing_interaction_is_explicit() -> None:
    store = InMemoryOutcomeStore()
    with pytest.raises(OutcomeNotFoundError) as captured:
        store.get("INT-MISSING")
    assert captured.value.reason_code == "OUTCOME_NOT_FOUND"


def test_snapshot_is_tuple_sorted_by_interaction_id() -> None:
    store = InMemoryOutcomeStore()
    second = outcome("INT-002")
    first = outcome("INT-001")
    store.ingest(second)
    store.ingest(first)
    assert store.snapshot() == (first, second)


def test_concurrent_identical_ingestion_keeps_one_record() -> None:
    store = InMemoryOutcomeStore()
    record = outcome()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(store.ingest, (record, record)))
    assert results == (record, record)
    assert store.snapshot() == (record,)


def test_concurrent_conflicting_ingestion_has_one_winner() -> None:
    store = InMemoryOutcomeStore()
    first = outcome()
    second = outcome(outcome="REJECTED", reason_code="REJECTED_BY_HUMAN")

    def ingest(record: OutcomeRecord):
        try:
            return store.ingest(record)
        except OutcomeConflictError as exc:
            return exc.reason_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(ingest, (first, second)))

    assert results.count("OUTCOME_CONFLICT") == 1
    assert len(store.snapshot()) == 1
