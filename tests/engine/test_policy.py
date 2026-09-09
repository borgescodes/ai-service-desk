from dataclasses import replace

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
)
from ai_service_desk.engine.policy import (
    PolicyConfigurationError,
    PolicyEngine,
    PolicyRule,
)


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=SessionIdentity(
            username="synthetic.policy",
            name="Synthetic Policy User",
            email="synthetic.policy@example.invalid",
            area="Revenda Sintetica",
        ),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-POLICY",
        playbook_id="PB-SYN-CDM-POLICY",
        playbook_version=1,
        step_id="STEP-CDM-POLICY",
        capability="CDM_ACCESS_REQUEST",
    )


def valid_policy_rule() -> PolicyRule:
    return PolicyRule(
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
        requested_role="SOLICITANTE",
        decision="DENY",
        policy_id="FUTURE_ACCESS_POLICY",
        reason_code="FUTURE_ACCESS_DENIED",
        reason="Synthetic valid policy rule.",
    )


@pytest.mark.parametrize(
    ("role", "decision", "policy_id", "reason_code"),
    [
        (
            "SOLICITANTE",
            "REQUIRE_APPROVAL",
            "CDM_SOLICITANTE_ACCESS",
            "CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL",
        ),
        (
            "APROVADOR",
            "DENY",
            "CDM_PRIVILEGED_ACCESS",
            "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        ),
        (
            "ADMIN",
            "DENY",
            "CDM_PRIVILEGED_ACCESS",
            "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        ),
        (
            "SUPERADMIN",
            "DENY",
            "CDM_PRIVILEGED_ACCESS",
            "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
        ),
    ],
)
def test_policy_cdm_matrix(
    role: str,
    decision: str,
    policy_id: str,
    reason_code: str,
) -> None:
    result = PolicyEngine().evaluate(replace(valid_context(), requested_role=role))
    assert result.decision == decision
    assert result.policy_id == policy_id
    assert result.reason_code == reason_code


def test_policy_unknown_valid_context_is_fail_closed_deny() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    result = PolicyEngine().evaluate(context)
    assert result.decision == "DENY"
    assert result.policy_id == "FAIL_CLOSED_UNKNOWN_POLICY"
    assert result.reason_code == "POLICY_NOT_FOUND"


def test_policy_evaluate_validates_context_independently() -> None:
    with pytest.raises(AccessRequestValidationError):
        PolicyEngine().evaluate(replace(valid_context(), purpose=""))


@pytest.mark.parametrize(
    "rule",
    [
        object(),
        replace(valid_policy_rule(), system=""),
        replace(valid_policy_rule(), system=123),  # type: ignore[arg-type]
        replace(valid_policy_rule(), capability="cdm_access_request"),
        replace(valid_policy_rule(), requested_role="UNKNOWN"),  # type: ignore[arg-type]
        replace(valid_policy_rule(), requested_role=[]),  # type: ignore[arg-type]
        replace(valid_policy_rule(), decision="ALLOW"),  # type: ignore[arg-type]
        replace(valid_policy_rule(), decision=[]),  # type: ignore[arg-type]
        replace(valid_policy_rule(), policy_id=""),
        replace(valid_policy_rule(), policy_id="bad id"),
        replace(valid_policy_rule(), reason_code=""),
        replace(valid_policy_rule(), reason_code="bad reason"),
        replace(valid_policy_rule(), reason=""),
    ],
)
def test_policy_invalid_rule_configuration_fails_closed(rule: object) -> None:
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((rule,))  # type: ignore[arg-type]
    assert exc_info.value.reason_code == "POLICY_RULE_INVALID"


def duplicate_rule(decision: str = "DENY") -> PolicyRule:
    return PolicyRule(
        system="CDM",
        capability="CDM_ACCESS_REQUEST",
        requested_role="SOLICITANTE",
        decision=decision,  # type: ignore[arg-type]
        policy_id="SYN_DUPLICATE",
        reason_code="SYN_DUPLICATE_REASON",
        reason="Synthetic duplicate rule.",
    )


def test_policy_rule_duplicate_key_fails_closed() -> None:
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((duplicate_rule("DENY"), duplicate_rule("REQUIRE_APPROVAL")))
    assert exc_info.value.reason_code == "POLICY_RULE_CONFLICT"


def test_policy_identical_duplicate_key_is_still_conflict() -> None:
    rule = duplicate_rule("DENY")
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((rule, rule))
    assert exc_info.value.reason_code == "POLICY_RULE_CONFLICT"


def test_policy_rule_invalid_precedes_duplicate_key_detection() -> None:
    first = duplicate_rule("DENY")
    second = duplicate_rule("DENY")
    invalid = replace(duplicate_rule("DENY"), decision="ALLOW")  # type: ignore[arg-type]
    with pytest.raises(PolicyConfigurationError) as exc_info:
        PolicyEngine((first, second, invalid))
    assert exc_info.value.reason_code == "POLICY_RULE_INVALID"


def test_policy_same_context_is_idempotent() -> None:
    engine = PolicyEngine()
    context = valid_context()
    assert engine.evaluate(context) == engine.evaluate(context)
