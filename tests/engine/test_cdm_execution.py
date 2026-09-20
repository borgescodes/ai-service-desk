from types import SimpleNamespace

import pytest

from ai_service_desk.engine.cdm_execution import CDMActionExecutor
from ai_service_desk.integrations.cdm import (
    AccessCreationResult,
    AccessLookup,
    CDMIdempotencyConflictError,
    CDMProtocolError,
    CDMRemoteInternalError,
    CDMRequestValidationError,
    CDMServiceAuthenticationError,
    CDMUnavailableError,
)


def make_request(**context_changes):
    requester = SimpleNamespace(username="user", email="user@example.invalid")
    context = SimpleNamespace(
        requester=requester,
        system="CDM",
        intent="PROBLEMA_ACESSO",
        capability="CDM_ACCESS_REQUEST",
        requested_role="SOLICITANTE",
        business_scope=None,
        scope_mismatch=False,
        scope_confirmed=False,
    )
    for key, value in context_changes.items():
        setattr(context, key, value)
    return SimpleNamespace(state="EXECUTING", request_id="REQ-000001", context=context)


class AdapterSpy:
    def __init__(self, lookup=None, creation=None, error=None):
        self.lookup = (
            lookup
            if lookup is not None
            else AccessLookup(False, "user@example.invalid", None, None, None)
        )
        self.creation = (
            creation
            if creation is not None
            else AccessCreationResult("CREATED", "100001", "ACTIVE")
        )
        self.error = error
        self.get_calls = 0
        self.post_calls = 0

    def get_access(self, email):
        self.get_calls += 1
        if self.error is not None:
            raise self.error
        return self.lookup

    def create_access(self, request_id, username, email, role, *, business_scopes=()):
        self.post_calls += 1
        if self.error is not None:
            raise self.error
        return self.creation


def test_requires_executing_state():
    adapter = AdapterSpy()
    request = make_request()
    request.state = "APPROVED"
    with pytest.raises(ValueError):
        CDMActionExecutor(adapter).execute(request)
    assert adapter.get_calls == adapter.post_calls == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"system": "ERP"},
        {"intent": "OUTRO"},
        {"capability": "OTHER"},
        {"requested_role": "ADMIN"},
    ],
)
def test_invalid_context_returns_failure_without_adapter_call(changes):
    adapter = AdapterSpy()
    result = CDMActionExecutor(adapter).execute(make_request(**changes))
    assert result.success is False
    assert result.result_code == "CDM_EXECUTION_CONTEXT_INVALID"
    assert adapter.get_calls == adapter.post_calls == 0


def test_existing_active_solicitante_returns_success():
    adapter = AdapterSpy(
        lookup=AccessLookup(True, "user@example.invalid", "SOLICITANTE", "ACTIVE", "100001")
    )
    result = CDMActionExecutor(adapter).execute(make_request())
    assert (result.success, result.result_code) == (True, "CDM_ACCESS_ALREADY_EXISTS")
    assert adapter.get_calls == 1 and adapter.post_calls == 0


def test_missing_access_creates_and_returns_created():
    adapter = AdapterSpy()
    result = CDMActionExecutor(adapter).execute(make_request())
    assert (result.success, result.result_code) == (True, "CDM_ACCESS_CREATED")
    assert adapter.get_calls == adapter.post_calls == 1


@pytest.mark.parametrize(
    ("outcome", "code"),
    [("REPLAYED", "CDM_REQUEST_REPLAYED"), ("ALREADY_EXISTS", "CDM_ACCESS_ALREADY_EXISTS")],
)
def test_create_reconciled_outcomes_return_success(outcome, code):
    adapter = AdapterSpy(creation=AccessCreationResult(outcome, "100001", "ACTIVE"))
    result = CDMActionExecutor(adapter).execute(make_request())
    assert (result.success, result.result_code) == (True, code)


def test_existing_incompatible_access_returns_failure_without_post():
    adapter = AdapterSpy(
        lookup=AccessLookup(True, "user@example.invalid", "ADMIN", "ACTIVE", "100001")
    )
    result = CDMActionExecutor(adapter).execute(make_request())
    assert (result.success, result.result_code) == (False, "CDM_EXISTING_ACCESS_CONFLICT")
    assert adapter.get_calls == 1 and adapter.post_calls == 0


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (CDMRequestValidationError("x"), "CDM_REQUEST_INVALID"),
        (CDMServiceAuthenticationError("x"), "CDM_SERVICE_UNAUTHORIZED"),
        (CDMIdempotencyConflictError("x"), "CDM_IDEMPOTENCY_CONFLICT"),
        (CDMUnavailableError("x"), "CDM_UNAVAILABLE"),
        (CDMProtocolError("x"), "CDM_PROTOCOL_ERROR"),
        (CDMRemoteInternalError("x"), "CDM_INTERNAL_ERROR"),
    ],
)
def test_known_adapter_error_returns_failure(error, code):
    result = CDMActionExecutor(AdapterSpy(error=error)).execute(make_request())
    assert (result.success, result.result_code) == (False, code)


def test_unexpected_runtime_error_propagates():
    with pytest.raises(RuntimeError):
        CDMActionExecutor(AdapterSpy(error=RuntimeError("boom"))).execute(make_request())


def test_scoped_request_does_not_accept_existing_access_in_another_scope():
    adapter = AdapterSpy(
        lookup=AccessLookup(
            True, "user@example.invalid", "SOLICITANTE", "ACTIVE", "100001", ("revenda",)
        )
    )
    result = CDMActionExecutor(adapter).execute(make_request(business_scope="ubs"))
    assert result.success is False
    assert result.result_code == "CDM_EXISTING_ACCESS_CONFLICT"


def test_scoped_create_race_does_not_claim_success_without_matching_access():
    adapter = AdapterSpy(creation=AccessCreationResult("ALREADY_EXISTS", "100001", "ACTIVE"))
    result = CDMActionExecutor(adapter).execute(make_request(business_scope="ubs"))
    assert result.success is False
    assert result.result_code == "CDM_EXISTING_ACCESS_CONFLICT"
