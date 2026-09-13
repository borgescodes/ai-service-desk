import json

import pytest

from ai_service_desk.web import demo_runtime
from ai_service_desk.web.business_context import BusinessVocabulary
from ai_service_desk.web.conversation import operational_message

ONEDRIVE_SYNC = "O One Drive não está sincronizando minhas pastas."
PASSWORD_PREFIX = "Cara, esqueci minha senha do Office e não consigo entrar. "
PASSWORD_SUFFIX = "O que eu faço?"


class AccessGateway:
    def model_info(self, name):
        return {"name": name}

    def close(self):
        pass

    def chat(self, payload):
        properties = payload["format"]["properties"]
        if "scenario" in properties:
            text = payload["messages"][-1]["content"].casefold()
            if any(
                term in text
                for term in ("microsoft 365", "office", "outlook", "onedrive", "one drive")
            ):
                signal = "PASSWORD_EVIDENCE" if "senha" in text else "LOGIN_PROBLEM"
                result = {"scenario": "M365_SUPPORT", "signal": signal}
            elif "cdm" in text:
                result = {"scenario": "CDM_ACCESS", "signal": "ACCESS_REQUEST"}
            elif any(term in text for term in ("acesso", "acessar", "entrar")):
                result = {"scenario": "OTHER_IT", "signal": "LOGIN_PROBLEM"}
            else:
                result = {"scenario": "OTHER_IT", "signal": "UNKNOWN"}
            return {
                "message": {"content": json.dumps(result, ensure_ascii=False)},
                "done": True,
                "done_reason": "stop",
            }
        schema = properties["assistant_message"]
        choices = schema.get("enum") or ["Entendi seu relato."]
        result = {"assistant_message": choices[0]}
        return {"message": {"content": json.dumps(result, ensure_ascii=False)}}


@pytest.fixture
def access_runtime(monkeypatch):
    monkeypatch.setattr(demo_runtime, "OllamaClient", AccessGateway)
    instance = demo_runtime.DemoRuntime.create(mode="LOCAL_AI")
    yield instance
    instance.close()


@pytest.mark.parametrize(
    "message,system,product",
    [
        ("Não consigo acessar o Microsoft 365 desde cedo.", "OFFICE 365", ""),
        ("Outlook não abre e eu preciso ver meus e-mails.", "OFFICE 365", "OUTLOOK"),
        (ONEDRIVE_SYNC, "OFFICE 365", "ONEDRIVE"),
    ],
)
def test_password_article_requires_evidence(access_runtime, message, system, product):
    result = access_runtime.send_message("pedro-miranda", message)

    assert result["business_context"] == {"system": system, "product": product}
    if message.startswith("Não consigo acessar o Microsoft 365"):
        assert result["status"] == "NEEDS_CLARIFICATION"
        assert result["question"]
    else:
        assert result["status"] == "TRIAGE_ABSTAINED"
        assert result["reason"] == "KNOWLEDGE_EVIDENCE_MISMATCH"
    assert "recuperação de senha" not in result["assistant_message"].casefold()


def test_password_article_answers_with_password_evidence(access_runtime):
    message = PASSWORD_PREFIX + PASSWORD_SUFFIX
    result = access_runtime.send_message("pedro-miranda", message)

    assert result["status"] == "KNOWLEDGE_FOUND"
    assert result["business_context"]["system"] == "OFFICE 365"
    assert result["knowledge_id"] == "KB-SYN-M365-PASSWORD-001"
    assert result["answer"] in result["assistant_message"]
    assert result["answer"].startswith("Vamos redefinir sua senha do Microsoft 365.")


def test_product_follow_up_rejects_password_article(access_runtime):
    first_input = "Não consigo acessar o sistema."
    first = access_runtime.send_message("pedro-miranda", first_input)
    second = access_runtime.send_message("pedro-miranda", "Teams")

    assert first["status"] == "NEEDS_CLARIFICATION"
    assert second["business_context"] == {"system": "OFFICE 365", "product": "TEAMS"}
    assert second["status"] == "TRIAGE_ABSTAINED"
    assert second["reason"] == "KNOWLEDGE_EVIDENCE_MISMATCH"
    assert "recuperação de senha" not in second["assistant_message"].casefold()


def test_business_vocabulary_accepts_informal_pra_revenda():
    vocabulary = BusinessVocabulary()
    message = "Jup, preciso criar um material novo pra revenda, como faço?"

    assert vocabulary.systems(message) == ("CDM",)


def test_natural_cdm_slot_preserves_prior_access_context(access_runtime):
    original = "Preciso de acesso."
    first = access_runtime.send_message("pedro-miranda", original)
    second = access_runtime.send_message("pedro-miranda", "É no CDM")

    assert first["status"] == "NEEDS_CLARIFICATION"
    assert first["reason"] == "MISSING_SYSTEM"
    assert second["status"] == "REQUEST_CREATED"
    assert second["state"] == "PENDING_APPROVAL"
    assert second["policy"] == "REQUIRE_APPROVAL"
    assert second["business_context"]["system"] == "CDM"
    assert access_runtime._triage["pedro-miranda"][1].problem_text == original
    assert access_runtime.fake_cdm_store.access_count == 0


@pytest.mark.parametrize(
    "reason",
    ["NO_APPROVED_KNOWLEDGE_FOR_INTENT", "SYSTEM_MISMATCH", "BELOW_THRESHOLD"],
)
def test_abstention_message_hides_internal_status(reason):
    result = {
        "status": "TRIAGE_ABSTAINED",
        "reason": reason,
        "request_id": None,
        "business_context": {"system": "PORTAL RH", "product": ""},
    }
    rendered = operational_message(result, "Portal RH não abre pra mim.", None)

    assert "TRIAGE_ABSTAINED" not in rendered
    assert reason not in rendered
    assert "orientação aprovada" in rendered.casefold()
    assert "nenhuma solicitação foi criada" in rendered.casefold()
