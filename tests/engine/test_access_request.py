from dataclasses import replace

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
    validate_access_request_context,
    validate_session_identity,
)


def valid_identity() -> SessionIdentity:
    return SessionIdentity(
        username="synthetic.user",
        name="Synthetic User",
        email="synthetic.user@example.invalid",
        area="Revenda Sintetica",
    )


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=valid_identity(),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-001",
        playbook_id="PB-SYN-CDM-001",
        playbook_version=1,
        step_id="STEP-CDM-001",
        capability="CDM_ACCESS_REQUEST",
    )


def test_validate_session_identity_accepts_trusted_identity() -> None:
    validate_session_identity(valid_identity())


@pytest.mark.parametrize(
    "identity",
    [
        SessionIdentity("", "Synthetic User", "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", "", "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", "", "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", "u@example.invalid", ""),
        SessionIdentity(None, "Synthetic User", "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", None, "u@example.invalid", "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", None, "Revenda"),
        SessionIdentity("synthetic.user", "Synthetic User", "u@example.invalid", None),
    ],
)
def test_validate_session_identity_rejects_invalid_fields(identity: SessionIdentity) -> None:
    with pytest.raises(AccessRequestValidationError):
        validate_session_identity(identity)


def test_validate_access_request_context_accepts_structural_cdm() -> None:
    validate_access_request_context(valid_context())


def test_validate_access_request_context_accepts_valid_unknown_policy_domain() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    validate_access_request_context(context)


@pytest.mark.parametrize(
    "context",
    [
        replace(valid_context(), requester=SessionIdentity("", "U", "u@example.invalid", "A")),
        replace(valid_context(), system=""),
        replace(valid_context(), intent="INVENTED_INTENT"),
        replace(valid_context(), requested_role="UNKNOWN"),
        replace(valid_context(), purpose=""),
        replace(valid_context(), knowledge_id=""),
        replace(valid_context(), playbook_id=""),
        replace(valid_context(), playbook_version=0),
        replace(valid_context(), step_id=""),
        replace(valid_context(), capability="not valid"),
    ],
)
def test_validate_access_request_context_rejects_invalid_fields(
    context: AccessRequestContext,
) -> None:
    with pytest.raises(AccessRequestValidationError):
        validate_access_request_context(context)
