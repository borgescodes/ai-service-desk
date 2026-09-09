import inspect
from dataclasses import replace

import pytest

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
)
from ai_service_desk.engine.confidence import ConfidenceAssessment, assess_confidence
from ai_service_desk.engine.policy import PolicyEngine


def valid_identity() -> SessionIdentity:
    return SessionIdentity(
        username="synthetic.confidence",
        name="Synthetic Confidence User",
        email="synthetic.confidence@example.invalid",
        area="Revenda Sintetica",
    )


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=valid_identity(),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-CONFIDENCE",
        playbook_id="PB-SYN-CDM-CONFIDENCE",
        playbook_version=1,
        step_id="STEP-CDM-CONFIDENCE",
        capability="CDM_ACCESS_REQUEST",
    )


@pytest.mark.parametrize(
    ("area", "purpose", "level", "reason_codes"),
    [
        (
            "Revenda Sintetica",
            "preciso de acesso ao CDM para solicitar materiais",
            "HIGH",
            ("AREA_MATCH_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST"),
        ),
        (
            "Financeiro Sintetico",
            "preciso de acesso ao CDM para solicitar materiais",
            "LOW",
            ("AREA_OUTSIDE_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST"),
        ),
        (
            "Revenda Sintetica",
            "preciso de acesso ao CDM",
            "LOW",
            ("AREA_MATCH_REVENDA", "PURPOSE_NOT_CONFIRMED"),
        ),
        (
            "Financeiro Sintetico",
            "preciso de acesso ao CDM",
            "LOW",
            ("AREA_OUTSIDE_REVENDA", "PURPOSE_NOT_CONFIRMED"),
        ),
    ],
)
def test_confidence_exact_reason_composition_and_order(
    area: str,
    purpose: str,
    level: str,
    reason_codes: tuple[str, ...],
) -> None:
    requester = replace(valid_identity(), area=area)
    context = replace(valid_context(), requester=requester, purpose=purpose)
    assert assess_confidence(context) == ConfidenceAssessment(level, reason_codes)


def test_confidence_valid_context_outside_cdm_is_single_low_reason() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    assert assess_confidence(context) == ConfidenceAssessment(
        "LOW",
        ("CONTEXT_NOT_CDM_ACCESS_REQUEST",),
    )


def test_confidence_validates_context_independently() -> None:
    with pytest.raises(AccessRequestValidationError):
        assess_confidence(replace(valid_context(), purpose=""))


def test_policy_and_confidence_public_signatures_are_separate() -> None:
    assert list(inspect.signature(PolicyEngine.evaluate).parameters) == ["self", "context"]
    assert list(inspect.signature(assess_confidence).parameters) == ["context"]
