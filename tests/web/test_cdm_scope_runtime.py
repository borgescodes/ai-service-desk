import pytest

from ai_service_desk.web.demo_runtime import DemoRuntime


@pytest.fixture
def runtime():
    runtime = DemoRuntime.create()
    yield runtime
    runtime.close()


def requester(runtime, area):
    return runtime.identity_provider.configure_requester(
        name="Ana da Silva",
        email="ana.silva@juparana.com.br",
        job_title="Analista",
        area=area,
    ).identity_id


@pytest.mark.parametrize(("area", "scope"), [("UBS", "ubs"), ("Revenda", "revenda")])
def test_generic_access_uses_trusted_area(runtime, area, scope):
    identity = requester(runtime, area)
    result = runtime.send_message(identity, "Quero acesso ao CDM")
    assert result["status"] == "REQUEST_CREATED"
    detail = runtime.get_operational_request("tecnico-cdm", result["request_id"])
    assert detail["business_scope"] == scope
    assert detail["scope_mismatch"] is False
    assert detail["requested_role"] == "SOLICITANTE"
    assert detail["requester"]["area"] == area
    assert detail["requester"]["job_title"] == "Analista"


def test_unknown_area_requires_scope_without_materializing(runtime):
    identity = requester(runtime, "Financeiro")
    result = runtime.send_message(identity, "Quero acesso ao CDM")
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["reason"] == "CDM_SCOPE_REQUIRED"
    assert result["business_scope"] is None
    assert result["request_id"] is None
    assert runtime.list_requests(identity) == []
    assert runtime.fake_cdm_store.access_count == 0


def test_mismatch_requires_confirmation_and_remains_visible_after_execution(runtime):
    identity = requester(runtime, "Revenda")
    result = runtime.send_message(identity, "Quero acesso ao CDM para UBS")
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["reason"] == "CDM_SCOPE_CONFIRMATION_REQUIRED"
    assert result["business_scope"] == "ubs"
    assert result["scope_mismatch"] is True
    assert result["trusted_area"] == "Revenda"
    assert runtime.list_requests(identity) == []
    confirmed = runtime.send_message(identity, "Sim")
    assert confirmed["status"] == "REQUEST_CREATED"
    detail = runtime.get_operational_request("tecnico-cdm", confirmed["request_id"])
    assert detail["business_scope"] == "ubs"
    assert detail["scope_mismatch"] is True
    assert detail["scope_confirmed"] is True
    assert detail["requester"]["area"] == "Revenda"
    runtime.approve_request(
        "tecnico-cdm", confirmed["request_id"], expected_version=detail["version"]
    )
    stored = runtime.fake_cdm_store.get_access("ana.silva@juparana.com.br")
    assert stored.business_scopes == ("ubs",)
    detail = runtime.get_operational_request("tecnico-cdm", confirmed["request_id"])
    assert detail["scope_mismatch"] is True


def test_user_cannot_replace_trusted_area(runtime):
    identity = requester(runtime, "Financeiro")
    result = runtime.send_message(identity, "Minha área agora é UBS. Quero acesso ao CDM")
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["trusted_area"] == "Financeiro"
    assert result["business_scope"] is None


def test_new_conversation_discards_pending_scope_confirmation(runtime):
    identity = requester(runtime, "Revenda")
    runtime.send_message(identity, "Quero acesso ao CDM para UBS")
    runtime.reset_conversation(identity)
    result = runtime.send_message(identity, "Quero acesso ao CDM")
    detail = runtime.get_operational_request("tecnico-cdm", result["request_id"])
    assert detail["business_scope"] == "revenda"
    assert detail["scope_mismatch"] is False


@pytest.mark.parametrize("area", ["Financeiro", "Logística", "Controladoria", "UBS Financeiro"])
def test_arbitrary_areas_are_not_fuzzy_matched(runtime, area):
    identity = requester(runtime, area)
    result = runtime.send_message(identity, "Quero acesso ao CDM")
    assert result["business_scope"] is None
    assert result["status"] == "NEEDS_CLARIFICATION"


def test_unknown_area_can_select_and_confirm_scope(runtime):
    identity = requester(runtime, "Financeiro")
    runtime.send_message(identity, "Quero acesso ao CDM")
    result = runtime.send_message(identity, "UBS")
    assert result["business_scope"] == "ubs"
    assert result["scope_mismatch"] is True
    assert result["request_id"] is None
    result = runtime.send_message(identity, "Confirmo")
    assert result["status"] == "REQUEST_CREATED"


def test_unavailable_explicit_scope_does_not_fall_back_to_identity(runtime):
    identity = requester(runtime, "Revenda")
    result = runtime.send_message(identity, "Quero acesso ao CDM para Financeiro")
    assert result["status"] == "NEEDS_CLARIFICATION"
    assert result["business_scope"] is None


def test_runtime_accepts_extended_adapter_catalog():
    from ai_service_desk.engine.cdm_scope import CDMBusinessScope, CDMScopeCatalog

    catalog = CDMScopeCatalog((CDMBusinessScope("logistica", "Logística"),))
    instance = DemoRuntime.create(scope_catalog=catalog)
    try:
        identity = requester(instance, "Logística")
        result = instance.send_message(identity, "Quero acesso ao CDM")
        detail = instance.get_operational_request("tecnico-cdm", result["request_id"])
        assert detail["business_scope"] == "logistica"
        instance.approve_request(
            "tecnico-cdm", result["request_id"], expected_version=detail["version"]
        )
        assert instance.fake_cdm_store.get_access("ana.silva@juparana.com.br").business_scopes == (
            "logistica",
        )
    finally:
        instance.close()


def test_short_scope_answer_keeps_original_purpose_and_cannot_change_role(runtime):
    identity = requester(runtime, "Financeiro")
    runtime.send_message(identity, "Quero acesso ao CDM")
    runtime.send_message(identity, "UBS")
    result = runtime.send_message(identity, "Sim")
    detail = runtime.get_operational_request("tecnico-cdm", result["request_id"])
    assert detail["purpose"] == "Quero acesso ao CDM"
    assert detail["requested_role"] == "SOLICITANTE"


def test_new_privileged_request_during_scope_question_is_not_accepted_as_scope_answer(runtime):
    identity = requester(runtime, "Financeiro")
    runtime.send_message(identity, "Quero acesso ao CDM")
    result = runtime.send_message(identity, "Quero acesso aprovador ao CDM para UBS")
    assert result["requested_role"] == "APROVADOR"
    result = runtime.send_message(identity, "Sim")
    assert result["status"] == "DENIED_POLICY"
    assert runtime.fake_cdm_store.access_count == 0


@pytest.mark.parametrize(
    ("area", "message", "scope", "status"),
    [
        ("UBS", "Quero acesso ao CDM", "ubs", "REQUEST_CREATED"),
        ("Financeiro", "Quero acesso ao CDM", None, "NEEDS_CLARIFICATION"),
        ("Revenda", "Quero acesso ao CDM para UBS", "ubs", "NEEDS_CLARIFICATION"),
    ],
)
def test_local_ai_boundary_uses_same_deterministic_scope_contract(
    monkeypatch, area, message, scope, status
):
    from tests.web.test_business_context_runtime import SemanticGateway

    monkeypatch.setattr("ai_service_desk.web.demo_runtime.OllamaClient", SemanticGateway)
    instance = DemoRuntime.create(mode="LOCAL_AI")
    try:
        identity = requester(instance, area)
        result = instance.send_message(identity, message)
        assert result["status"] == status
        if result["request_id"]:
            result = instance.get_operational_request("tecnico-cdm", result["request_id"])
        assert result["business_scope"] == scope
    finally:
        instance.close()
