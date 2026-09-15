import os

import pytest

from ai_service_desk.web.demo_runtime import DemoRuntime

pytestmark = pytest.mark.skipif(
    os.environ.get("JUP_BUSINESS_LOCAL_QA") != "1",
    reason="QA explícita com Qwen e embedding locais; CI hospedado permanece determinístico",
)


@pytest.fixture(scope="module")
def runtime():
    instance = DemoRuntime.create(mode="LOCAL_AI")
    yield instance
    instance.close()


@pytest.fixture(autouse=True)
def clean_conversation(runtime):
    runtime.reset_conversation("pedro-miranda")
    yield


def test_office_password_paraphrase_retrieves_approved_m365_guidance(runtime):
    result = runtime.send_message("pedro-miranda", "Esqueci minha senha do Office")

    assert result["status"] == "KNOWLEDGE_FOUND"
    assert result["knowledge_id"] == "KB-SYN-M365-PASSWORD-001"
    assert result["request_id"] is None


def test_m365_natural_diagnostic_follow_up_retrieves_same_guidance(runtime):
    first = runtime.send_message("pedro-miranda", "meu office nao entra")
    assert first["status"] == "NEEDS_CLARIFICATION"

    second = runtime.send_message("pedro-miranda", "diz q a senha esta errada")
    assert second["status"] == "KNOWLEDGE_FOUND"
    assert second["knowledge_id"] == "KB-SYN-M365-PASSWORD-001"


@pytest.mark.parametrize("failure_text", ["deu errado", "não rolou", "continua sem entrar"])
def test_m365_failure_paraphrases_handoff_after_approved_guidance(runtime, failure_text):
    guidance = runtime.send_message("pedro-miranda", "Esqueci minha senha do Office")
    assert guidance["status"] == "KNOWLEDGE_FOUND"

    result = runtime.send_message("pedro-miranda", failure_text)

    assert result["status"] == "SUPPORT_HANDOFF_PENDING"
    assert result["support_handoff"]["technician"]["technician_id"] == "TECH-M365"
    assert result["request_id"] is None


@pytest.mark.parametrize(
    "message",
    [
        "preciso de acesso adm no cdm",
        "preciso de acesso administrativo ao cdm",
        "preciso de acesso administrador ao cdm",
        "quero superadmin no cdm",
    ],
)
def test_privileged_cdm_paraphrases_are_denied_with_real_qwen(runtime, message):
    result = runtime.send_message("pedro-miranda", message)

    assert result["state"] == "DENIED_POLICY"
    assert result["policy"] == "DENY"
    assert result["request_id"] is not None
    assert runtime.fake_cdm_store.access_count == 0


def test_ubs_access_goes_to_general_technician_with_low_explainable_confidence(runtime):
    result = runtime.send_message("pedro-miranda", "Preciso de acesso ao UBS")

    assert result["status"] == "SUPPORT_HANDOFF_PENDING"
    handoff = result["support_handoff"]
    assert handoff["technician"]["technician_id"] == "TECH-GENERAL"
    assert handoff["system"] == "UBS"
    assert handoff["confidence"]["level"] == "LOW"
    assert {item["code"] for item in handoff["confidence"]["explanations"]} >= {
        "AREA_SYSTEM_MISMATCH",
        "CONTEXT_INSUFFICIENT",
    }
    assert runtime.fake_cdm_store.access_count == 0


def test_general_it_without_approved_knowledge_handoffs_instead_of_dying(runtime):
    result = runtime.send_message("pedro-miranda", "meu pc ta travando muito")

    assert result["status"] == "SUPPORT_HANDOFF_PENDING"
    assert result["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"
    assert result["request_id"] is None
    assert runtime.fake_cdm_store.access_count == 0


def test_material_registration_never_becomes_access_and_has_human_continuity(runtime):
    first = runtime.send_message("pedro-miranda", "Preciso cadastrar um material para revenda")

    assert first.get("state") != "PENDING_APPROVAL"
    assert first.get("policy") != "REQUIRE_APPROVAL"
    assert runtime.fake_cdm_store.access_count == 0

    if first["status"] == "NEEDS_CLARIFICATION":
        second = runtime.send_message(
            "pedro-miranda",
            "eu ja consigo acessar, preciso de ajuda com o cadastro do material",
        )
        assert second["status"] == "SUPPORT_HANDOFF_PENDING"
        assert second["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"
        assert second["request_id"] is None
    else:
        assert first["status"] == "SUPPORT_HANDOFF_PENDING"
        assert first["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"
        assert first["request_id"] is None
