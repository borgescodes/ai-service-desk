import inspect
from dataclasses import replace

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
    normalize_requested_role,
    prepare_access_request,
    validate_access_request_context,
    validate_session_identity,
)
from ai_service_desk.engine.playbook_resolution import action_proposal_descriptor
from ai_service_desk.engine.triage import TriageState


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


def answered_triage(
    problem_text: str = "preciso de acesso ao CDM para solicitar materiais",
    system: str = "CDM",
    intent: str = "PROBLEMA_ACESSO",
) -> TriageState:
    return TriageState(
        version=1,
        session_id="phase7-synthetic-session",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text=problem_text,
        intent=intent,
        system=system,
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def cdm_descriptor() -> dict:
    playbook = {
        "playbook_id": "PB-SYN-CDM-001",
        "playbook_version": 3,
    }
    step = {
        "step_id": "STEP-CDM-ACCESS-01",
        "type": "ACTION_PROPOSAL",
        "capability": "CDM_ACCESS_REQUEST",
    }
    return action_proposal_descriptor("KB-SYN-CDM-001", playbook, step)


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


@pytest.mark.parametrize(
    ("text", "expected_role", "expected_reason"),
    [
        (
            "acesso ao CDM",
            "SOLICITANTE",
            "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE",
        ),
        (
            "quero acesso aprovador",
            "APROVADOR",
            "ROLE_PRIVILEGED_NOMINAL_MATCH",
        ),
        (
            "quero poder aprovar solicitacoes",
            "APROVADOR",
            "ROLE_PRIVILEGED_INTENT_MATCH",
        ),
        ("admin e superadmin", "UNKNOWN", "ROLE_CONFLICT"),
        ("perfil privilegiado", "UNKNOWN", "ROLE_PRIVILEGE_AMBIGUOUS"),
        ("solicitante e admin", "UNKNOWN", "ROLE_CONFLICT"),
        ("preciso de ajuda", "UNKNOWN", "ROLE_UNRESOLVED"),
    ],
)
def test_role_normalizer_closed_precedence(
    text: str,
    expected_role: str,
    expected_reason: str,
) -> None:
    assert normalize_requested_role(text) == (expected_role, expected_reason)


def test_role_normalizer_api_has_no_identity_parameter() -> None:
    assert list(inspect.signature(normalize_requested_role).parameters) == ["problem_text"]


def test_privileged_semantic_and_nominal_conflict_is_unknown() -> None:
    assert normalize_requested_role("admin e quero aprovar solicitacoes") == (
        "UNKNOWN",
        "ROLE_CONFLICT",
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("quero admin", ("ADMIN", "ROLE_PRIVILEGED_NOMINAL_MATCH")),
        ("quero superadmin", ("SUPERADMIN", "ROLE_PRIVILEGED_NOMINAL_MATCH")),
        ("quero perfil solicitante", ("SOLICITANTE", "ROLE_SOLICITANTE_EXPLICIT")),
    ],
)
def test_role_normalizer_nominal_positive_cases(text: str, expected: tuple[str, str]) -> None:
    assert normalize_requested_role(text) == expected


def test_prepare_access_request_preserves_real_phase6_descriptor_provenance() -> None:
    result = prepare_access_request(valid_identity(), answered_triage(), cdm_descriptor())
    assert result.status == "READY"
    assert result.requested_role == "SOLICITANTE"
    assert result.reason_code == "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE"
    assert result.context is not None
    assert result.context.purpose == "preciso de acesso ao CDM para solicitar materiais"
    assert result.context.knowledge_id == "KB-SYN-CDM-001"
    assert result.context.playbook_id == "PB-SYN-CDM-001"
    assert result.context.playbook_version == 3
    assert result.context.step_id == "STEP-CDM-ACCESS-01"
    assert result.context.capability == "CDM_ACCESS_REQUEST"


def test_prepare_access_request_keeps_privileged_role_ready_for_policy_denial() -> None:
    result = prepare_access_request(
        valid_identity(),
        answered_triage("quero acesso aprovador ao CDM"),
        cdm_descriptor(),
    )
    assert result.status == "READY"
    assert result.requested_role == "APROVADOR"
    assert result.reason_code == "ROLE_PRIVILEGED_NOMINAL_MATCH"
    assert result.context is not None
    assert result.context.requested_role == "APROVADOR"


def test_prepare_access_request_returns_clarification_for_unknown_role() -> None:
    result = prepare_access_request(
        valid_identity(),
        answered_triage("perfil privilegiado no CDM"),
        cdm_descriptor(),
    )
    assert result.status == "NEEDS_CLARIFICATION"
    assert result.requested_role == "UNKNOWN"
    assert result.reason_code == "ROLE_PRIVILEGE_AMBIGUOUS"
    assert result.context is None


def test_prepare_access_request_rejects_non_action_proposal() -> None:
    descriptor = cdm_descriptor()
    descriptor["type"] = "CHECK"
    with pytest.raises(AccessRequestValidationError):
        prepare_access_request(valid_identity(), answered_triage(), descriptor)


@pytest.mark.parametrize(
    ("triage", "descriptor"),
    [
        (answered_triage(system="CIGAM"), cdm_descriptor()),
        (answered_triage(intent="ERRO_SISTEMA"), cdm_descriptor()),
        (
            answered_triage(),
            {**cdm_descriptor(), "capability": "FUTURE_CAPABILITY"},
        ),
    ],
)
def test_prepare_access_request_rejects_unsupported_scope(
    triage: TriageState,
    descriptor: dict,
) -> None:
    with pytest.raises(AccessRequestValidationError, match="somente CDM"):
        prepare_access_request(valid_identity(), triage, descriptor)


@pytest.mark.parametrize(
    ("triage", "descriptor"),
    [
        (answered_triage(system="FUTURE_SYSTEM"), cdm_descriptor()),
        (answered_triage(), {**cdm_descriptor(), "capability": "FUTURE_CAPABILITY"}),
    ],
)
def test_prepare_access_request_does_not_apply_cdm_role_normalizer_to_future_scope(
    monkeypatch,
    triage: TriageState,
    descriptor: dict,
) -> None:
    import ai_service_desk.engine.access_request as module

    monkeypatch.setattr(
        module,
        "normalize_requested_role",
        lambda text: (_ for _ in ()).throw(AssertionError("normalizer must not run")),
    )
    with pytest.raises(AccessRequestValidationError, match="somente CDM"):
        module.prepare_access_request(valid_identity(), triage, descriptor)


def test_prepare_access_request_preserves_purpose_with_strip_only() -> None:
    result = prepare_access_request(
        valid_identity(),
        answered_triage("  Preciso de acesso ao CDM para solicitar materiais.  "),
        cdm_descriptor(),
    )
    assert result.context is not None
    assert result.context.purpose == "Preciso de acesso ao CDM para solicitar materiais."


@pytest.mark.parametrize(
    "descriptor",
    [
        {key: value for key, value in cdm_descriptor().items() if key != "knowledge_id"},
        {**cdm_descriptor(), "playbook_version": 0},
        {**cdm_descriptor(), "capability": "not valid"},
        {**cdm_descriptor(), "step_id": ""},
    ],
)
def test_prepare_access_request_rejects_corrupt_descriptor(descriptor: dict) -> None:
    with pytest.raises(AccessRequestValidationError):
        prepare_access_request(valid_identity(), answered_triage(), descriptor)
