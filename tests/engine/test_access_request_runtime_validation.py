import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
    validate_access_request_context,
)


def test_invalid_runtime_requested_role_raises_domain_error() -> None:
    context = AccessRequestContext(
        requester=SessionIdentity(
            username="synthetic.user",
            name="Synthetic User",
            email="synthetic.user@example.invalid",
            area="Revenda Sintetica",
        ),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role=[],
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-001",
        playbook_id="PB-SYN-CDM-001",
        playbook_version=1,
        step_id="STEP-CDM-001",
        capability="CDM_ACCESS_REQUEST",
    )

    with pytest.raises(AccessRequestValidationError, match="requested_role"):
        validate_access_request_context(context)
