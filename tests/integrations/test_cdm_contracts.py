from dataclasses import FrozenInstanceError

import pytest

from ai_service_desk.integrations.cdm import (
    AccessCreationResult,
    AccessLookup,
    CDMAdapterError,
    CDMIdempotencyConflictError,
    CDMProtocolError,
    CDMRemoteInternalError,
    CDMRequestValidationError,
    CDMServiceAuthenticationError,
    CDMUnavailableError,
    validate_service_token,
)


def test_access_lookup_is_frozen():
    value = AccessLookup(False, "user@example.invalid", None, None, None)
    with pytest.raises(FrozenInstanceError):
        value.exists = True


def test_access_creation_result_is_frozen():
    value = AccessCreationResult("CREATED", "100001", "ACTIVE")
    with pytest.raises(FrozenInstanceError):
        value.status = "OTHER"


@pytest.mark.parametrize("value", [None, "", "   ", 123, True])
def test_service_token_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_service_token(value)


def test_adapter_errors_expose_machine_reason_code():
    errors = [
        CDMRequestValidationError("bad"),
        CDMServiceAuthenticationError("bad"),
        CDMIdempotencyConflictError("bad"),
        CDMUnavailableError("bad"),
        CDMProtocolError("bad"),
        CDMRemoteInternalError("bad"),
    ]
    assert all(isinstance(error, CDMAdapterError) for error in errors)
    assert [error.reason_code for error in errors] == [
        "CDM_REQUEST_INVALID",
        "CDM_SERVICE_UNAUTHORIZED",
        "CDM_IDEMPOTENCY_CONFLICT",
        "CDM_UNAVAILABLE",
        "CDM_PROTOCOL_ERROR",
        "CDM_INTERNAL_ERROR",
    ]
