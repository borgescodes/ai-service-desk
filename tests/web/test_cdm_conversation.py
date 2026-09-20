import json

import pytest

from ai_service_desk.web.conversation import generate_natural_response
from ai_service_desk.web.conversation_grounding import ground_response
from ai_service_desk.web.demo_runtime import DemoRuntime
from tests.web.test_cdm_scope_runtime import requester
from tests.web.test_conversation_grounding import base_context, delta_for


@pytest.fixture
def runtime():
    instance = DemoRuntime.create()
    yield instance
    instance.close()


@pytest.mark.parametrize("mode", ["DETERMINISTIC", "LOCAL_AI"])
def test_local_boundary_preserves_offer_and_grounding(monkeypatch, mode):
    from ai_service_desk.web.demo_runtime import DemoRuntime
    from tests.web.test_business_context_runtime import SemanticGateway

    monkeypatch.setattr("ai_service_desk.web.demo_runtime.OllamaClient", SemanticGateway)
    instance = DemoRuntime.create(mode=mode)
    try:
        identity = requester(instance, "UBS")
        guidance = instance.send_message(identity, "Como consigo acesso ao CDM?")
        assert guidance["status"] == "KNOWLEDGE_FOUND"
        assert "posso registrar" in guidance["assistant_message"]
        created = instance.send_message(identity, "Pode solicitar para mim.")
        assert created["state"] == "PENDING_APPROVAL"
        assert created["business_scope"] == "ubs"
        assert "aguarda aprovação" in created["assistant_message"]
    finally:
        instance.close()


def test_semantic_acceptance_preserves_purpose_but_ignores_model_role_and_scope(monkeypatch):
    from tests.web.test_business_context_runtime import SemanticGateway

    class Gateway(SemanticGateway):
        def chat(self, payload):
            response = super().chat(payload)
            if (
                "r" in payload.get("format", {}).get("properties", {})
                and payload["messages"][-1]["content"] == "Sim, prossiga por favor."
            ):
                data = json.loads(response["message"]["content"])
                data.update(
                    r="Y",
                    s="AR",
                    i="PA",
                    e={"system": "CDM", "requested_role": "ADMIN", "business_scope": "fazenda"},
                )
                response["message"]["content"] = json.dumps(data)
            return response

    monkeypatch.setattr("ai_service_desk.web.demo_runtime.OllamaClient", Gateway)
    instance = DemoRuntime.create(mode="LOCAL_AI")
    try:
        identity = requester(instance, "UBS")
        instance.send_message(identity, "Como consigo acesso ao CDM para solicitar materiais?")
        result = instance.send_message(identity, "Sim, prossiga por favor.")
        assert result["status"] == "REQUEST_CREATED"
        assert result["business_scope"] == "ubs"
        assert result["requested_role"] == "SOLICITANTE"
        detail = instance.get_operational_request("tecnico-cdm", result["request_id"])
        assert "solicitar materiais" in detail["purpose"]
    finally:
        instance.close()


@pytest.mark.parametrize("message", ["Quero acesso privilegiado ao CDM", "cancelar"])
def test_cdm_other_pending_results_also_protect_operational_text(monkeypatch, message):
    from tests.web.test_business_context_runtime import SemanticGateway

    class Gateway(SemanticGateway):
        def chat(self, payload):
            if "r" in payload.get("format", {}).get("properties", {}):
                return super().chat(payload)
            fields = payload["format"]["properties"]
            data = (
                {"intro": "", "outro": "Você será avisado."}
                if "intro" in fields
                else {"assistant_message": "Você será avisado."}
            )
            return {"message": {"content": json.dumps(data)}}

    monkeypatch.setattr("ai_service_desk.web.demo_runtime.OllamaClient", Gateway)
    instance = DemoRuntime.create(mode="LOCAL_AI")
    try:
        identity = requester(instance, "Financeiro")
        if message == "cancelar":
            instance.send_message(identity, "Quero acesso ao CDM")
        result = instance.send_message(identity, message)
        assert result["request_id"] is None
        assert "avisado" not in result["assistant_message"]
    finally:
        instance.close()


@pytest.mark.parametrize("interruption", ["reset", "Bom dia", "Não quero"])
def test_offer_cannot_be_accepted_after_reset_or_unrelated_turn(runtime, interruption):
    identity = requester(runtime, "UBS")
    runtime.send_message(identity, "Como consigo acesso ao CDM?")
    if interruption == "reset":
        runtime.reset_conversation(identity)
    else:
        runtime.send_message(identity, interruption)
    runtime.send_message(identity, "Pode solicitar")
    assert runtime.list_requests(identity) == []


def test_information_during_pending_mismatch_does_not_leave_old_execution_authority(runtime):
    identity = requester(runtime, "Revenda")
    runtime.send_message(identity, "Quero acesso ao CDM para UBS")
    runtime.send_message(identity, "Como consigo acesso ao CDM?")
    created = runtime.send_message(identity, "Pode solicitar")
    assert created["business_scope"] == "revenda"
    assert created["scope_mismatch"] is False
    runtime.send_message(identity, "Sim")
    assert len(runtime.list_requests(identity)) == 1


@pytest.mark.parametrize("missing", ["KB-SYN-FAQ-CDM-REQUEST-001", "KB-SYN-CDM-ACCESS-001"])
@pytest.mark.parametrize("status", ["DRAFT", "RETIRED", "MISSING"])
def test_unapproved_or_missing_article_never_offers_execution(runtime, missing, status, tmp_path):
    from ai_service_desk.web.demo_faq import DemoFaqCatalog

    articles = []
    for entry in runtime.faq_catalog._entries:
        article = dict(entry.article)
        if article["knowledge_id"] == missing:
            if status == "MISSING":
                continue
            article["status"] = status
        articles.append(article)
    source = tmp_path / "articles.jsonl"
    source.write_text("\n".join(json.dumps(article) for article in articles), encoding="utf-8")
    runtime.faq_catalog = DemoFaqCatalog.from_sources([source])
    identity = requester(runtime, "UBS")
    result = runtime.send_message(identity, "Como consigo acesso ao CDM?")
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert not result.get("offer_action")
    assert runtime.list_requests(identity) == []


def test_untrusted_retrieval_fails_closed_with_grounded_response(runtime, monkeypatch):
    monkeypatch.setattr(
        runtime.knowledge_engine,
        "search_classified",
        lambda *args: {
            "status": "NO_APPROVED_KNOWLEDGE",
            "reason": "PROVENANCE_MISMATCH",
            "knowledge": None,
        },
    )
    identity = requester(runtime, "UBS")
    result = runtime.send_message(identity, "Como consigo acesso ao CDM?")
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert not result.get("article")
    assert not result.get("offer_action")
    assert runtime.list_requests(identity) == []


@pytest.mark.parametrize(
    "question",
    [
        "Como consigo acesso ao CDM?",
        "Como faço para pedir acesso ao CDM?",
        "Preciso acessar o CDM, como funciona?",
    ],
)
def test_information_is_approved_short_guidance_with_article_and_offer(runtime, question):
    identity = requester(runtime, "UBS")
    result = runtime.send_message(identity, question)
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert result["request_id"] is None
    assert runtime.list_requests(identity) == []
    assert result["answer"] == runtime.get_faq("KB-SYN-CDM-ACCESS-001")["answer"]
    assert result["article"]["knowledge_id"] == "KB-SYN-FAQ-CDM-REQUEST-001"
    assert result["article"]["provenance"]["status"] == "APPROVED"
    assert result["answer"] in result["assistant_message"]
    assert "posso registrar" in result["assistant_message"]


@pytest.mark.parametrize(
    "acceptance",
    [
        "Pode solicitar para mim.",
        "Pode solicitar.",
        "Pode fazer pra mim.",
        "Sim, solicita.",
        "Quero sim.",
        "Pode abrir.",
    ],
)
def test_offer_acceptance_reuses_identity_and_backend_scope(runtime, acceptance):
    identity = requester(runtime, "UBS")
    runtime.send_message(identity, "Como consigo acesso ao CDM?")
    result = runtime.send_message(identity, acceptance)
    assert result["status"] == "REQUEST_CREATED"
    assert result["business_scope"] == "ubs"
    assert result["requested_role"] == "SOLICITANTE"
    detail = runtime.get_operational_request("tecnico-cdm", result["request_id"])
    assert detail["requester"]["email"] == "ana.silva@juparana.com.br"
    assert detail["requester"]["area"] == "UBS"
    assert result["state"] == "PENDING_APPROVAL"
    assert runtime.fake_cdm_store.access_count == 0


def test_financeiro_offer_does_not_invent_scope_and_short_answer_continues(runtime):
    identity = requester(runtime, "Financeiro")
    runtime.send_message(identity, "Como consigo acesso ao CDM?")
    pending = runtime.send_message(identity, "Pode solicitar.")
    assert pending["reason"] == "CDM_SCOPE_REQUIRED"
    assert pending["business_scope"] is None
    assert "Financeiro" in pending["assistant_message"]
    assert all(label in pending["assistant_message"] for label in ("Revenda", "UBS", "Fazenda"))
    selected = runtime.send_message(identity, "UBS")
    assert selected["business_scope"] == "ubs"
    assert selected["request_id"] is None
    confirmed = runtime.send_message(identity, "Sim, é para UBS.")
    assert confirmed["state"] == "PENDING_APPROVAL"
    detail = runtime.get_operational_request("tecnico-cdm", confirmed["request_id"])
    assert detail["requester"]["area"] == "Financeiro"


def test_short_mismatch_confirmation_preserves_trusted_area(runtime):
    identity = requester(runtime, "Revenda")
    pending = runtime.send_message(identity, "Quero acesso ao CDM para UBS.")
    assert pending["scope_mismatch"] is True
    assert pending["request_id"] is None
    result = runtime.send_message(identity, "Sim, é para UBS.")
    assert result["status"] == "REQUEST_CREATED"
    assert result["scope_confirmed"] is True
    detail = runtime.get_operational_request("tecnico-cdm", result["request_id"])
    assert detail["requester"]["area"] == "Revenda"
    assert detail["business_scope"] == "ubs"


@pytest.mark.parametrize(
    "fabrication",
    [
        "A equipe foi notificada.",
        "O técnico entrará em contato.",
        "Vamos acompanhar para você.",
        "Você será avisado.",
        "O acesso será liberado.",
        "Já está aprovado.",
        "Registrei a solicitação 12345, status concluído.",
        "Seu chamado ABC-42 foi criado.",
        "Maria cuida do seu pedido em 2 horas.",
        "Clique aqui e envie sua senha para liberar o acesso.",
    ],
)
@pytest.mark.parametrize("status", ["NEEDS_CLARIFICATION", "REQUEST_CREATED"])
def test_cdm_writer_cannot_add_facts_or_procedures(fabrication, status):
    result = {"status": status, "system": "CDM", "question": "Qual área do CDM você precisa?"}
    if status == "REQUEST_CREATED":
        result.update(request_id="REQ-000001", state="PENDING_APPROVAL", policy="REQUIRE_APPROVAL")
    grounding = ground_response(result, base_context(), delta_for())

    def chat(payload):
        fields = payload["format"]["properties"]
        content = (
            {"intro": "Entendi.", "outro": fabrication}
            if "intro" in fields
            else {"assistant_message": fabrication}
        )
        return {"message": {"content": json.dumps(content)}}

    answer = generate_natural_response("Pode solicitar", base_context(), grounding, chat)
    assert fabrication not in answer
    assert answer == grounding.fallback_message
