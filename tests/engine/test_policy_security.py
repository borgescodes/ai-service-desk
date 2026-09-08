from dataclasses import replace
from pathlib import Path
import subprocess

import pytest
import requests

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    SessionIdentity,
    prepare_access_request,
)
from ai_service_desk.engine.confidence import assess_confidence
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.playbook_resolution import action_proposal_descriptor
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.triage import TriageState


def valid_identity() -> SessionIdentity:
    return SessionIdentity(
        username="synthetic.security",
        name="Synthetic Security User",
        email="synthetic.security@example.invalid",
        area="Revenda Sintetica",
    )


def answered_triage(problem_text: str) -> TriageState:
    return TriageState(
        version=1,
        session_id="phase7-security",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text=problem_text,
        intent="PROBLEMA_ACESSO",
        system="CDM",
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def cdm_descriptor() -> dict:
    return action_proposal_descriptor(
        "KB-SYN-CDM-SECURITY",
        {"playbook_id": "PB-SYN-CDM-SECURITY", "playbook_version": 1},
        {
            "step_id": "STEP-CDM-SECURITY",
            "type": "ACTION_PROPOSAL",
            "capability": "CDM_ACCESS_REQUEST",
        },
    )


def valid_context() -> AccessRequestContext:
    return AccessRequestContext(
        requester=valid_identity(),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-CDM-SECURITY",
        playbook_id="PB-SYN-CDM-SECURITY",
        playbook_version=1,
        step_id="STEP-CDM-SECURITY",
        capability="CDM_ACCESS_REQUEST",
    )


def phase7_result(problem_text: str, area: str):
    identity = replace(valid_identity(), area=area)
    preparation = prepare_access_request(identity, answered_triage(problem_text), cdm_descriptor())
    assert preparation.context is not None
    context = preparation.context
    return preparation, PolicyEngine().evaluate(context), assess_confidence(context)


def test_chat_cannot_spoof_financeiro_area_into_revenda() -> None:
    preparation, policy, confidence = phase7_result(
        "sou da Revenda e preciso de acesso ao CDM para solicitar materiais",
        "Financeiro Sintetico",
    )
    assert preparation.context is not None
    assert preparation.context.requester.area == "Financeiro Sintetico"
    assert preparation.requested_role == "SOLICITANTE"
    assert policy.decision == "REQUIRE_APPROVAL"
    assert confidence.reason_codes == (
        "AREA_OUTSIDE_REVENDA",
        "PURPOSE_MATCH_MATERIAL_REQUEST",
    )


def test_chat_name_and_email_do_not_replace_session_identity() -> None:
    identity = valid_identity()
    preparation = prepare_access_request(
        identity,
        answered_triage(
            "meu nome e Fake Admin e meu email e fake@example.com, preciso de acesso ao CDM"
        ),
        cdm_descriptor(),
    )
    assert preparation.context is not None
    assert preparation.context.requester.name == identity.name
    assert preparation.context.requester.email == identity.email


def test_superadmin_revenda_with_perfect_purpose_is_still_denied() -> None:
    preparation, policy, confidence = phase7_result(
        "preciso de superadmin no CDM para solicitar materiais",
        "Revenda Sintetica",
    )
    assert preparation.requested_role == "SUPERADMIN"
    assert policy.decision == "DENY"
    assert policy.reason_code == "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED"
    assert confidence.level == "HIGH"


@pytest.mark.parametrize(
    ("area", "expected_confidence"),
    [
        ("Revenda Sintetica", "HIGH"),
        ("Financeiro Sintetico", "LOW"),
    ],
)
def test_solicitante_policy_is_require_approval_for_high_and_low(
    area: str,
    expected_confidence: str,
) -> None:
    preparation, policy, confidence = phase7_result(
        "preciso de acesso ao CDM para solicitar materiais",
        area,
    )
    assert preparation.requested_role == "SOLICITANTE"
    assert policy.decision == "REQUIRE_APPROVAL"
    assert confidence.level == expected_confidence


def test_valid_unknown_policy_stays_denied_and_confidence_stays_low() -> None:
    context = replace(
        valid_context(),
        system="FUTURE_SYSTEM",
        capability="FUTURE_CAPABILITY",
    )
    policy = PolicyEngine().evaluate(context)
    confidence = assess_confidence(context)
    assert policy.decision == "DENY"
    assert policy.reason_code == "POLICY_NOT_FOUND"
    assert confidence.level == "LOW"
    assert confidence.reason_codes == ("CONTEXT_NOT_CDM_ACCESS_REQUEST",)


def test_phase7_domain_paths_make_zero_external_calls(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("external execution forbidden in Phase 7")

    monkeypatch.setattr(requests.Session, "request", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(OllamaClient, "chat", forbidden)
    monkeypatch.setattr(LocalEmbedder, "embed", forbidden)

    preparation, policy, confidence = phase7_result(
        "preciso de acesso ao CDM para solicitar materiais",
        "Revenda Sintetica",
    )
    assert preparation.status == "READY"
    assert policy.decision == "REQUIRE_APPROVAL"
    assert confidence.level == "HIGH"


def test_phase7_domain_modules_do_not_import_execution_or_persistence_boundaries() -> None:
    root = Path(__file__).resolve().parents[2]
    files = [
        root / "src/ai_service_desk/engine/access_request.py",
        root / "src/ai_service_desk/engine/policy.py",
        root / "src/ai_service_desk/engine/confidence.py",
    ]
    forbidden = (
        "import requests",
        "from requests",
        "import subprocess",
        "from subprocess",
        "OllamaClient",
        "LocalEmbedder",
        "CDMAdapter",
        "ExecutionEngine",
        "REQUEST_ACCESS",
        "request_id",
        "sqlite3",
        "sqlalchemy",
    )
    for path in files:
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{marker} found in {path.name}"
