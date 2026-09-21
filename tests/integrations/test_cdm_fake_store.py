from concurrent.futures import ThreadPoolExecutor

import pytest

from ai_service_desk.integrations.cdm_fake_api import CDMFakeStore, CDMStoreConflict

PAYLOAD = {
    "request_id": "REQ-000001",
    "username": "synthetic.requester",
    "email": "synthetic.requester@example.invalid",
    "role": "SOLICITANTE",
}


def create(store, **changes):
    return store.create_access(**(PAYLOAD | changes))


def test_first_create_allocates_single_access_id():
    store = CDMFakeStore()
    result = create(store)
    assert result.outcome == "CREATED"
    assert result.access.access_id == "100001"
    assert store.get_access(PAYLOAD["email"]) == result.access
    assert store.access_count == 1


def test_same_request_and_payload_replays_same_access():
    store = CDMFakeStore()
    first = create(store)
    second = create(store)
    assert first.outcome == "CREATED"
    assert second.outcome == "REPLAYED"
    assert second.access.access_id == first.access.access_id
    assert store.access_count == 1


def test_same_request_with_different_payload_conflicts():
    store = CDMFakeStore()
    first = create(store)
    with pytest.raises(CDMStoreConflict):
        create(store, username="different.user")
    assert store.get_access(PAYLOAD["email"]) == first.access
    assert store.access_count == 1


def test_different_request_same_email_reports_existing_access():
    store = CDMFakeStore()
    first = create(store)
    second = create(store, request_id="REQ-000002")
    assert second.outcome == "ALREADY_EXISTS"
    assert second.access.access_id == first.access.access_id
    assert store.access_count == 1


def test_two_threads_same_request_create_once():
    store = CDMFakeStore()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(store), range(2)))
    assert sorted(result.outcome for result in results) == ["CREATED", "REPLAYED"]
    assert {result.access.access_id for result in results} == {"100001"}
    assert store.access_count == 1


def test_two_threads_same_email_create_at_most_once():
    store = CDMFakeStore()
    payloads = [
        {"request_id": "REQ-000001"},
        {"request_id": "REQ-000002"},
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda change: create(store, **change), payloads))
    assert sorted(result.outcome for result in results) == ["ALREADY_EXISTS", "CREATED"]
    assert {result.access.access_id for result in results} == {"100001"}
    assert store.access_count == 1


def test_scope_is_part_of_fake_store_idempotency():
    store = CDMFakeStore()
    first = create(store, business_scopes=("ubs",))
    assert first.access.business_scopes == ("ubs",)
    assert create(store, business_scopes=("ubs",)).outcome == "REPLAYED"
    with pytest.raises(CDMStoreConflict):
        create(store, business_scopes=("revenda",))
