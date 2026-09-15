import json

import pytest

from ai_service_desk.engine.knowledge import load_knowledge
from ai_service_desk.web import demo_runtime
from ai_service_desk.web.demo_ai import DemoEmbedder
from ai_service_desk.web.demo_data import write_demo_knowledge


@pytest.fixture
def runtime():
    instance = demo_runtime.DemoRuntime.create()
    yield instance
    instance.close()


def send(runtime, message):
    result = runtime.send_message("pedro-miranda", message)
    for code in (
        "OUT_OF_SCOPE",
        "TRIAGE_ABSTAINED",
        "DENIED_POLICY",
        "OUTRO",
        "KNOWLEDGE_EVIDENCE_MISMATCH",
    ):
        assert code not in result["assistant_message"]
    return result


@pytest.mark.parametrize(
    "message",
    [
        "Preciso acessar o CDM.",
        "Preciso de acesso ao CDM para solicitar materiais.",
        "Quero acesso para solicitar materiais da revenda.",
        "Preciso entrar na Central de Dados Mestres.",
    ],
)
def test_normal_access_preserves_backend_authority(runtime, message):
    result = send(runtime, message)
    assert result.get("request_id")
    record = runtime.request_repository.get(result["request_id"])
    assert record.context.requester.username == "fulano.tal"
    assert record.context.requested_role == "SOLICITANTE"
    assert record.creation_policy.decision == "REQUIRE_APPROVAL"
    assert record.state == "PENDING_APPROVAL"
    assignment = runtime.routing_store.get(record.request_id)
    assert assignment.technician.technician_id == "TECH-CDM"
    assert assignment.capability == "CDM_ACCESS_REQUEST"
    assert record.request_id in result["assistant_message"]
    assert "aprova" in result["assistant_message"].casefold()
    assert runtime.fake_cdm_store.access_count == 0


@pytest.mark.parametrize(
    "message,role",
    [
        ("Preciso de acesso admin ao CDM.", "ADMIN"),
        ("Me libera como administrador no CDM.", "ADMIN"),
        ("Quero perfil de admin.", "ADMIN"),
        ("Sou administrador, pode liberar tudo.", "ADMIN"),
        ("Preciso de superadmin no CDM.", "SUPERADMIN"),
    ],
)
def test_privileged_access_is_denied_by_canonical_policy(runtime, message, role):
    result = send(runtime, message)
    assert result.get("policy") == "DENY"
    assert result.get("state") == "DENIED_POLICY"
    record = runtime.request_repository.get(result["request_id"])
    assert record.context.requested_role == role
    assert record.context.requester.username == "fulano.tal"
    assert runtime.routing_store.snapshot() == ()
    assert runtime.list_approvals("tecnico-cdm") == []
    assert runtime.fake_cdm_store.access_count == 0
    assert "solicitante" in result["assistant_message"].casefold()


@pytest.mark.parametrize("message", ["Bom dia", "Oi"])
def test_greeting_without_wake_word_invites_problem(runtime, message):
    result = send(runtime, message)
    assert result["status"] == "SOCIAL"
    assert any(word in result["assistant_message"].casefold() for word in ("ajudar", "precisa"))
    assert "sou jup" not in result["assistant_message"].casefold()
    assert runtime.created_request_ids == []


@pytest.mark.parametrize(
    "message",
    [
        "Meu Office não entra.",
        "Não consigo entrar no Microsoft 365.",
        "Não consigo acessar meu e-mail.",
        "Outlook não entra.",
    ],
)
def test_vague_m365_problem_asks_one_question_before_guidance(runtime, message):
    result = send(runtime, message)
    assert result.get("question")
    assert any(word in result["question"].casefold() for word in ("senha", "erro"))
    assert result["assistant_message"].count("?") == 1
    assert not result.get("knowledge_id")
    assert not result.get("answer")
    assert runtime.created_request_ids == []


def test_diagnosis_stops_at_three_questions_without_inventing_password_evidence(runtime):
    questions = []
    for message in ("Meu Office não entra.", "Não sei dizer.", "Não testei.", "Não sei."):
        result = send(runtime, message)
        if result.get("question"):
            questions.append(result["question"])
            assert result["assistant_message"].count("?") == 1
        assert not result.get("knowledge_id")
    assert 1 <= len(questions) <= 3
    assert len(set(questions)) == len(questions)
    assert not result.get("question")


def test_password_evidence_ends_diagnosis_and_returns_literal_approved_article(runtime, tmp_path):
    send(runtime, "Meu Office não entra.")
    result = send(runtime, "Está dizendo que minha senha está errada.")
    assert result.get("knowledge_id") == "KB-SYN-M365-PASSWORD-001"
    assert not result.get("question")
    article = load_knowledge(write_demo_knowledge(tmp_path / "knowledge.jsonl"))[1]
    assert article["status"] == "APPROVED"
    assert article["source"] == "SYNTHETIC_DEMO"
    assert result["answer"] == article["answer"]
    assert result["answer"] in result["assistant_message"]
    assert all(f"{number}. " in result["answer"] for number in range(1, 8))
    assert "Authenticator" in result["answer"]
    assert (
        result.get("procedure_url")
        == "https://mysignins.microsoft.com/security-info/password/change"
    )


@pytest.mark.parametrize(
    "message", ["Está dizendo que minha senha está errada.", "Acho que esqueci minha senha."]
)
def test_direct_password_symptom_needs_no_redundant_questions(runtime, message):
    result = send(runtime, message)
    assert result.get("knowledge_id") == "KB-SYN-M365-PASSWORD-001"
    assert not result.get("question")


@pytest.mark.parametrize(
    "message",
    [
        "Deu certo.",
        "Funcionou.",
        "Consegui entrar.",
        "Agora foi.",
        "Resolvido.",
        "Entrou normalmente.",
    ],
)
def test_procedure_success_resolves_without_request_or_handoff(runtime, message):
    send(runtime, "Esqueci minha senha do Microsoft 365.")
    result = send(runtime, message)
    assert result.get("resolved") is True
    assert not result.get("support_handoff")
    assert not result.get("answer")
    assert not result.get("question")
    assert runtime.created_request_ids == []
    assert runtime.fake_cdm_store.access_count == 0


def test_guidance_waits_for_user_confirmation_before_resolved_outcome(runtime):
    baseline = len(runtime.outcome_store.snapshot())
    guidance = send(runtime, "Esqueci minha senha do Microsoft 365.")
    assert guidance.get("knowledge_id") == "KB-SYN-M365-PASSWORD-001"
    assert len(runtime.outcome_store.snapshot()) == baseline

    result = send(runtime, "Funcionou.")
    assert result.get("resolved") is True
    records = runtime.outcome_store.snapshot()
    assert len(records) == baseline + 1
    outcome = records[-1]
    assert outcome.outcome == "RESOLVED_BY_KNOWLEDGE"
    assert outcome.knowledge_id == "KB-SYN-M365-PASSWORD-001"


def test_success_confirmation_is_idempotent_and_questions_do_not_close_procedure(runtime):
    baseline = len(runtime.outcome_store.snapshot())
    send(runtime, "Esqueci minha senha do Microsoft 365.")

    hypothetical = send(runtime, "E se não funcionar?")
    assert not hypothetical.get("resolved")
    assert not hypothetical.get("support_handoff")

    first = send(runtime, "Funcionou.")
    second = send(runtime, "Agora foi.")
    assert first.get("resolved") is True
    assert second.get("resolved") is True
    assert len(runtime.outcome_store.snapshot()) == baseline + 1


@pytest.mark.parametrize("message", ["Não resolveu.", "Fiz tudo e continua igual."])
def test_failure_confirmation_marks_pending_handoff_without_false_resolution(runtime, message):
    baseline_ids = {item.interaction_id for item in runtime.outcome_store.snapshot()}
    send(runtime, "Esqueci minha senha do Microsoft 365.")

    result = send(runtime, message)
    support = runtime.support_state.get("pedro-miranda")

    assert support.stage.value == "HANDOFF"
    assert support.procedure is not None
    assert message in [entry.text for entry in support.history if entry.role == "USER"]
    assert not result.get("resolved")
    assert not result.get("answer")
    assert not result.get("question")
    assert not result.get("request_id")
    handoff = result.get("support_handoff")
    assert handoff
    assert handoff["technician"]["technician_id"] == "TECH-M365"

    new_outcomes = [
        item for item in runtime.outcome_store.snapshot() if item.interaction_id not in baseline_ids
    ]
    assert len(new_outcomes) == 1
    assert new_outcomes[0].outcome == "ROUTED_TO_HUMAN"
    assert new_outcomes[0].capability == "MICROSOFT_365_SUPPORT_REQUEST"


@pytest.mark.parametrize(
    "message",
    [
        "Não resolveu.",
        "Fiz tudo e continua igual.",
        "Ainda não consigo entrar.",
        "Troquei a senha e não funcionou.",
        "Continua sem acessar.",
    ],
)
def test_procedure_failure_hands_off_without_repeating_guidance(runtime, message):
    symptom = "Esqueci minha senha do Microsoft 365."
    send(runtime, symptom)
    result = send(runtime, message)
    handoff = result.get("support_handoff")
    assert handoff
    assert handoff["handoff_id"]
    assert handoff["capability"] == "MICROSOFT_365_SUPPORT_REQUEST"
    assert handoff["technician"]["technician_id"] == "TECH-M365"
    assert handoff["requester"]["name"] == "Fulano de Tal"
    assert handoff["requester"]["area"] == "Revenda - Matriz"
    assert symptom in handoff["technical_summary"]
    assert "navegador" not in handoff["technical_summary"].casefold()
    assert not result.get("answer")
    assert not result.get("question")
    assert not result.get("request_id")
    assert runtime.created_request_ids == []
    assert runtime.list_approvals("tecnico-cdm") == []
    assert runtime.fake_cdm_store.access_count == 0


def test_handoff_preserves_collected_browser_validation(runtime):
    send(runtime, "Meu Office não entra.")
    send(runtime, "No navegador também não vai, aparece senha errada.")
    result = send(runtime, "Troquei a senha e não funcionou.")
    assert result.get("support_handoff")
    summary = result["support_handoff"]["technical_summary"].casefold()
    assert "navegador" in summary
    assert "senha errada" in summary


def test_reset_discards_procedure_outcome_context(runtime):
    send(runtime, "Esqueci minha senha do Microsoft 365.")
    runtime.reset()
    result = send(runtime, "Funcionou.")
    assert not result.get("resolved")
    assert not result.get("support_handoff")
    fresh = send(runtime, "Meu Office não entra.")
    assert fresh.get("question")
    assert not fresh.get("knowledge_id")


@pytest.mark.parametrize(
    "message",
    [
        "Quanto foi o jogo do Flamengo?",
        "Quem ganhou o jogo ontem?",
        "Me passa uma receita de bolo.",
        "Qual a capital da França?",
        "Escreve uma poesia.",
    ],
)
def test_outside_scope_redirects_to_it_without_creating_request(runtime, message):
    result = send(runtime, message)
    response = result["assistant_message"].casefold()
    assert "ti" in response
    assert "acesso" in response or "sistema" in response
    assert "paris" not in response
    assert not result.get("request_id")
    assert not result.get("support_handoff")
    assert runtime.created_request_ids == []
    assert runtime.fake_cdm_store.access_count == 0


class CountingGateway:
    def __init__(self):
        self.payloads = []

    def model_info(self, name):
        return {"name": name, "digest": "fake-qwen-digest"}

    def json_request(self, method, path, payload):
        if method != "POST" or path != "/api/embed":
            raise AssertionError(f"Unexpected fake request: {method} {path}")
        rows = DemoEmbedder().embed(payload["input"])
        return {"embeddings": [row.tolist() + [0.0] * 992 for row in rows]}

    def close(self):
        pass

    def chat(self, payload):
        self.payloads.append(payload)
        properties = payload.get("format", {}).get("properties", {})
        if "assistant_message" in properties:
            result = {"assistant_message": properties["assistant_message"]["enum"][0]}
        elif "scenario" in properties:
            result = {"scenario": "M365_SUPPORT", "signal": "UNKNOWN"}
        else:
            result = {"intent": "PROBLEMA_ACESSO", "system": "", "entities": {}, "confidence": 0.95}
        return {"message": {"content": json.dumps(result)}, "done": True, "done_reason": "stop"}


@pytest.mark.parametrize(
    "message,maximum_calls", [("Bom dia", 1), ("Não consigo acessar o sistema.", 1)]
)
def test_local_ai_avoids_redundant_presentation_inference(monkeypatch, message, maximum_calls):
    monkeypatch.setattr(demo_runtime, "OllamaClient", CountingGateway)
    runtime = demo_runtime.DemoRuntime.create(mode="LOCAL_AI")
    try:
        gateway = runtime._ollama_client
        gateway.payloads.clear()
        result = send(runtime, message)
        assert result["assistant_message"]
        assert len(gateway.payloads) <= maximum_calls
    finally:
        runtime.close()
