import threading

import pytest
import requests

from ai_service_desk.integrations.cdm_fake_api import build_cdm_server

TOKEN = "test-token"
URL = "/api/v1/access"


@pytest.fixture
def cdm_server():
    server = build_cdm_server("127.0.0.1", 0, TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def payload(request_id="REQ-000001", **changes):
    base = {
        "request_id": request_id,
        "username": "synthetic.requester",
        "email": "synthetic.requester@example.invalid",
        "role": "SOLICITANTE",
    }
    return base | changes


def auth(token=TOKEN):
    return {"Authorization": f"Bearer {token}"}


def test_get_missing_access_returns_exists_false(cdm_server):
    _, base = cdm_server
    response = requests.get(base + URL, params={"email": "User@Example.Invalid"}, timeout=2)
    assert response.status_code == 200
    assert response.json() == {"exists": False, "email": "user@example.invalid"}


def test_get_existing_access_returns_contract(cdm_server):
    _, base = cdm_server
    created = requests.post(base + URL, json=payload(), headers=auth(), timeout=2)
    assert created.status_code == 201
    response = requests.get(base + URL, params={"email": payload()["email"]}, timeout=2)
    assert response.status_code == 200
    assert response.json() == {
        "exists": True,
        "email": payload()["email"],
        "role": "SOLICITANTE",
        "status": "ACTIVE",
        "access_id": "100001",
    }


@pytest.mark.parametrize(
    "params",
    [None, {}, {"email": ""}, [("email", "a@example.invalid"), ("email", "b@example.invalid")]],
)
def test_get_requires_single_nonempty_email(cdm_server, params):
    _, base = cdm_server
    response = requests.get(base + URL, params=params, timeout=2)
    assert response.status_code == 400
    assert response.json()["error_code"] == "CDM_REQUEST_INVALID"


def test_unknown_route_returns_closed_404(cdm_server):
    _, base = cdm_server
    response = requests.get(base + "/unknown", timeout=2)
    assert response.status_code == 404
    assert response.json()["error_code"] == "CDM_ROUTE_NOT_FOUND"


def test_post_requires_bearer(cdm_server):
    _, base = cdm_server
    response = requests.post(base + URL, json=payload(), timeout=2)
    assert response.status_code == 401
    assert response.json()["error_code"] == "CDM_SERVICE_UNAUTHORIZED"


def test_post_rejects_wrong_bearer(cdm_server):
    _, base = cdm_server
    response = requests.post(base + URL, json=payload(), headers=auth("wrong"), timeout=2)
    assert response.status_code == 401
    assert response.json()["error_code"] == "CDM_SERVICE_UNAUTHORIZED"
    assert "wrong" not in response.text


def test_post_creates_solicitante(cdm_server):
    _, base = cdm_server
    response = requests.post(base + URL, json=payload(), headers=auth(), timeout=2)
    assert response.status_code == 201
    assert response.json() == {
        "success": True,
        "outcome": "CREATED",
        "access_id": "100001",
        "status": "ACTIVE",
    }


@pytest.mark.parametrize("role", ["APROVADOR", "ADMIN", "SUPERADMIN", "UNKNOWN"])
def test_post_rejects_privileged_or_unknown_role(cdm_server, role):
    server, base = cdm_server
    response = requests.post(base + URL, json=payload(role=role), headers=auth(), timeout=2)
    assert response.status_code == 400
    assert response.json()["error_code"] == "CDM_REQUEST_INVALID"
    assert server.store.access_count == 0


def test_post_rejects_extra_fields(cdm_server):
    server, base = cdm_server
    response = requests.post(base + URL, json=payload(extra="x"), headers=auth(), timeout=2)
    assert response.status_code == 400
    assert response.json()["error_code"] == "CDM_REQUEST_INVALID"
    assert server.store.access_count == 0


def test_post_replay_returns_200_same_access_id(cdm_server):
    _, base = cdm_server
    first = requests.post(base + URL, json=payload(), headers=auth(), timeout=2)
    second = requests.post(base + URL, json=payload(), headers=auth(), timeout=2)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == {
        "success": True,
        "outcome": "REPLAYED",
        "access_id": first.json()["access_id"],
        "status": "ACTIVE",
    }


def test_post_idempotency_conflict_returns_409(cdm_server):
    _, base = cdm_server
    requests.post(base + URL, json=payload(), headers=auth(), timeout=2)
    response = requests.post(
        base + URL,
        json=payload(username="different.user"),
        headers=auth(),
        timeout=2,
    )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CDM_IDEMPOTENCY_CONFLICT"


def test_post_existing_access_returns_409_with_access_id(cdm_server):
    _, base = cdm_server
    requests.post(base + URL, json=payload(), headers=auth(), timeout=2)
    response = requests.post(
        base + URL,
        json=payload(request_id="REQ-000002"),
        headers=auth(),
        timeout=2,
    )
    assert response.status_code == 409
    assert response.json() == {
        "success": False,
        "error_code": "CDM_ACCESS_ALREADY_EXISTS",
        "access_id": "100001",
        "status": "ACTIVE",
    }


def test_controlled_internal_error_hides_traceback_and_token():
    server = build_cdm_server("127.0.0.1", 0, TOKEN, fail_request_ids={"REQ-000099"})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        base = f"http://{host}:{port}"
        response = requests.post(
            base + URL,
            json=payload(request_id="REQ-000099"),
            headers=auth(),
            timeout=2,
        )
        assert response.status_code == 500
        assert response.json()["error_code"] == "CDM_INTERNAL_ERROR"
        assert TOKEN not in response.text
        assert "Traceback" not in response.text
        assert server.store.access_count == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
