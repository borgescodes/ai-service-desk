import threading

import pytest

from ai_service_desk.integrations.cdm import (
    CDMAdapter,
    CDMIdempotencyConflictError,
    CDMProtocolError,
    CDMRemoteInternalError,
    CDMRequestValidationError,
    CDMServiceAuthenticationError,
    CDMUnavailableError,
)
from ai_service_desk.integrations.cdm_fake_api import build_cdm_server

TOKEN = "test-token"


@pytest.fixture
def live_server():
    server = build_cdm_server("127.0.0.1", 0, TOKEN, fail_request_ids={"REQ-000099"})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_get_access_returns_typed_lookup(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    lookup = adapter.get_access("USER@EXAMPLE.INVALID")
    assert lookup.exists is False
    assert lookup.email == "user@example.invalid"


def test_create_access_returns_created(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    result = adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    assert (result.outcome, result.access_id, result.status) == ("CREATED", "100001", "ACTIVE")


def test_create_access_returns_replayed(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    first = adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    second = adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    assert second.outcome == "REPLAYED"
    assert second.access_id == first.access_id


def test_create_access_maps_existing_access_to_result(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    first = adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    second = adapter.create_access("REQ-000002", "other", "user@example.invalid", "SOLICITANTE")
    assert second.outcome == "ALREADY_EXISTS"
    assert second.access_id == first.access_id


def test_create_maps_400_to_validation_error(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    with pytest.raises(CDMRequestValidationError):
        adapter.create_access("bad", "user", "user@example.invalid", "SOLICITANTE")


def test_create_maps_401_to_auth_error(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, "wrong-token")
    with pytest.raises(CDMServiceAuthenticationError):
        adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")


def test_create_maps_idempotency_409_to_conflict_error(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    with pytest.raises(CDMIdempotencyConflictError):
        adapter.create_access("REQ-000001", "different", "user@example.invalid", "SOLICITANTE")


def test_500_maps_remote_internal_error(live_server):
    _, base = live_server
    adapter = CDMAdapter(base, TOKEN)
    with pytest.raises(CDMRemoteInternalError):
        adapter.create_access("REQ-000099", "user", "user@example.invalid", "SOLICITANTE")


def test_connection_failure_maps_unavailable():
    adapter = CDMAdapter("http://127.0.0.1:1", TOKEN, timeout_seconds=0.05)
    with pytest.raises(CDMUnavailableError):
        adapter.get_access("user@example.invalid")


class FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append(("GET", args, kwargs))
        return self.response

    def post(self, *args, **kwargs):
        self.calls.append(("POST", args, kwargs))
        return self.response


def test_invalid_json_maps_protocol_error():
    session = FakeSession(FakeResponse(200, json_error=ValueError("bad json")))
    adapter = CDMAdapter("http://example.invalid", TOKEN, session=session)
    with pytest.raises(CDMProtocolError):
        adapter.get_access("user@example.invalid")
    assert len(session.calls) == 1


def test_invalid_schema_maps_protocol_error():
    session = FakeSession(FakeResponse(200, {"exists": "false", "email": "x"}))
    adapter = CDMAdapter("http://example.invalid", TOKEN, session=session)
    with pytest.raises(CDMProtocolError):
        adapter.get_access("user@example.invalid")


def test_unexpected_status_maps_protocol_error():
    session = FakeSession(FakeResponse(418, {}))
    adapter = CDMAdapter("http://example.invalid", TOKEN, session=session)
    with pytest.raises(CDMProtocolError):
        adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    assert len(session.calls) == 1


def test_get_sends_no_authorization_and_calls_once():
    session = FakeSession(FakeResponse(200, {"exists": False, "email": "user@example.invalid"}))
    adapter = CDMAdapter("http://example.invalid", TOKEN, session=session)
    adapter.get_access("user@example.invalid")
    assert len(session.calls) == 1
    _, _, kwargs = session.calls[0]
    assert "headers" not in kwargs


def test_post_sends_bearer_and_calls_once():
    session = FakeSession(
        FakeResponse(
            201,
            {"success": True, "outcome": "CREATED", "access_id": "1", "status": "ACTIVE"},
        )
    )
    adapter = CDMAdapter("http://example.invalid", TOKEN, session=session)
    adapter.create_access("REQ-000001", "user", "user@example.invalid", "SOLICITANTE")
    assert len(session.calls) == 1
    _, _, kwargs = session.calls[0]
    assert kwargs["headers"] == {"Authorization": f"Bearer {TOKEN}"}
