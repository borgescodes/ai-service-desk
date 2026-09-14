import pytest

from ai_service_desk.web.demo_runtime import DemoRuntime
from ai_service_desk.web.demo_support import DemoSupportState, LinguisticSignal


def test_m365_strong_password_evidence_overrides_broader_semantic_signal() -> None:
    support = DemoSupportState()
    first = support.handle(
        "requester",
        "meu office nao entra",
        interpreted_signal=LinguisticSignal.M365_LOGIN_PROBLEM,
    )
    assert first is not None
    assert first.status == "NEEDS_CLARIFICATION"

    second = support.handle(
        "requester",
        "diz q a senha esta errada",
        interpreted_signal=LinguisticSignal.M365_LOGIN_PROBLEM,
    )
    assert second is not None
    assert second.status == "PASSWORD_EVIDENCE_COLLECTED"


@pytest.mark.parametrize("failure_text", ["deu errado", "não rolou", "continua sem entrar"])
def test_m365_guidance_failure_paraphrases_handoff_to_specialist(failure_text: str) -> None:
    runtime = DemoRuntime.create()
    try:
        first = runtime.send_message("pedro-miranda", "Esqueci minha senha do Microsoft 365")
        assert first["status"] == "KNOWLEDGE_FOUND"

        result = runtime.send_message("pedro-miranda", failure_text)

        assert result["status"] == "SUPPORT_HANDOFF_PENDING"
        assert result["support_handoff"]["technician"]["technician_id"] == "TECH-M365"
    finally:
        runtime.close()


@pytest.mark.parametrize(
    "message",
    [
        "preciso de acesso adm no cdm",
        "preciso de acesso administrativo ao cdm",
        "preciso de acesso administrador ao cdm",
        "quero superadmin no cdm",
    ],
)
def test_privileged_cdm_paraphrases_are_denied_by_policy(message: str) -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message("pedro-miranda", message)

        assert result["state"] == "DENIED_POLICY"
        assert result["policy"] == "DENY"
        assert result["request_id"] is not None
    finally:
        runtime.close()


def test_unresolved_general_it_is_handed_to_general_technician() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message("pedro-miranda", "meu pc ta travando muito")

        assert result["status"] == "SUPPORT_HANDOFF_PENDING"
        assert result["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"
        assert result["support_handoff"]["capability"] == "GENERAL_IT_SUPPORT"
        assert result["request_id"] is None
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_ubs_access_is_low_confidence_general_handoff_without_external_execution() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message("pedro-miranda", "Preciso de acesso ao UBS")

        assert result["status"] == "SUPPORT_HANDOFF_PENDING"
        handoff = result["support_handoff"]
        assert handoff["system"] == "UBS"
        assert handoff["technician"]["technician_id"] == "TECH-GENERAL"
        assert handoff["confidence"]["level"] == "LOW"
        assert {
            item["code"] for item in handoff["confidence"]["explanations"]
        } >= {"AREA_SYSTEM_MISMATCH", "CONTEXT_INSUFFICIENT"}
        assert runtime.created_request_ids == []
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_material_registration_never_becomes_cdm_access_request() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message("pedro-miranda", "Preciso cadastrar um material para revenda")

        assert result.get("state") != "PENDING_APPROVAL"
        assert result.get("policy") != "REQUIRE_APPROVAL"
        assert runtime.created_request_ids == []
        assert runtime.fake_cdm_store.access_count == 0

        if result["status"] == "NEEDS_CLARIFICATION":
            result = runtime.send_message(
                "pedro-miranda",
                "eu ja consigo acessar, preciso de ajuda com o cadastro do material",
            )

        assert result["status"] == "SUPPORT_HANDOFF_PENDING"
        assert result["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"
        assert result["request_id"] is None
        assert runtime.created_request_ids == []
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()
