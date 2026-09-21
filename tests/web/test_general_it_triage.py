import json

import pytest

from ai_service_desk.web.conversation import generate_natural_response
from ai_service_desk.web.conversation_grounding import ground_response
from ai_service_desk.web.conversation_state import new_conversation_context
from ai_service_desk.web.demo_runtime import DemoRuntime


@pytest.fixture
def runtime():
    instance = DemoRuntime.create()
    yield instance
    instance.close()


def send(runtime, text, identity="pedro-miranda"):
    return runtime.send_message(identity, text)


def assert_general(result, count):
    assert result["status"] == "SUPPORT_HANDOFF_PENDING"
    assert result["general_triage"]["questions_asked"] == count
    assert result["support_handoff"]["capability"] == "GENERAL_IT_SUPPORT"
    assert result["support_handoff"]["technician"]["technician_id"] == "TECH-GENERAL"


def test_notebook_collects_context_and_preserves_question_answer_and_identity(runtime):
    first = send(runtime, "meu notebook tá muito lento")
    assert first["status"] == "NEEDS_CLARIFICATION"
    assert "programa" in first["question"].casefold()
    assert not runtime.support_handoff_store.snapshot()
    result = send(runtime, "principalmente no Excel")
    assert_general(result, 1)
    handoff = result["support_handoff"]
    history = handoff["source_conversation"]
    assert history[0]["text"] == "meu notebook tá muito lento"
    assert history[1] == {"role": "ASSISTANT", "text": first["assistant_message"]}
    assert history[2] == {"role": "USER", "text": "principalmente no Excel"}
    summary = handoff["technical_summary"]
    assert first["assistant_message"] in summary
    assert "Excel" in summary
    assert "Cargo:" in summary
    assert handoff["requester"]["username"] == "fulano.tal"
    assert "Encaminhei" in result["assistant_message"]
    assert "Excel" in result["assistant_message"]
    assert "notebook" in result["assistant_message"]


@pytest.mark.parametrize(
    "reply",
    ["ele acende, mas não lê nenhum código", "não sei", "não tenho certeza", "não consigo dizer"],
)
def test_barcode_reader_and_uncertainty_end_triage(runtime, reply):
    first = send(runtime, "meu leitor de código de barras parou")
    assert first["status"] == "NEEDS_CLARIFICATION"
    assert_general(send(runtime, reply), 1)


def test_never_asks_a_third_question(runtime):
    send(runtime, "meu leitor de código de barras parou")
    second = send(runtime, "sim")
    assert second["status"] == "NEEDS_CLARIFICATION"
    assert second["general_triage"]["questions_asked"] == 2
    assert_general(send(runtime, "sim"), 2)
    assert_general(send(runtime, "e agora?"), 2)
    assert len(runtime.support_handoff_store.snapshot()) == 1


def test_rich_initial_message_needs_no_question(runtime):
    assert_general(
        send(
            runtime, "meu monitor fica piscando desde ontem principalmente quando abro o sistema X"
        ),
        0,
    )


def test_topic_switch_cancels_triage_and_processes_cdm(runtime):
    send(runtime, "meu notebook está muito lento")
    result = send(runtime, "deixa isso, preciso de acesso ao CDM")
    assert result["state"] == "PENDING_APPROVAL"
    assert not runtime.support_handoff_store.snapshot()
    assert "pedro-miranda" not in runtime._general_triage


def test_explicit_correction_after_general_handoff_starts_cdm_instead_of_repeating_handoff(runtime):
    send(runtime, "meu note ta lento")
    handoff = send(runtime, "pc todo")
    assert handoff["status"] == "SUPPORT_HANDOFF_PENDING"

    result = send(runtime, "na verdade eu preciso de acesso ao cdm")

    assert result["state"] == "PENDING_APPROVAL"
    assert result["system"] == "CDM"
    assert "general_triage" not in result
    assert "pedro-miranda" not in runtime._general_triage


def test_application_answer_is_context_not_a_specialized_topic_switch(runtime):
    first = send(runtime, "meu notebook está muito lento")
    result = send(runtime, "principalmente no Teams")
    assert_general(result, 1)
    assert first["assistant_message"] in result["support_handoff"]["technical_summary"]
    assert "notebook" in result["support_handoff"]["technical_summary"]


@pytest.mark.parametrize(
    "answer",
    [
        "Misture farinha, ovos e leite. Meu foco é TI.",
        "O jogo terminou 2 a 1. Posso ajudar com TI?",
        "O mar canta ao luar, nas ondas vou sonhar. Meu foco é TI.",
        "Meu escopo operacional rejeita esse pedido.",
        "Meu foco é TI e encaminhei esse assunto para um técnico.",
        "Meu papel é suporte de TI; alguém vai ligar para você.",
        "Entendi: misture os ingredientes para o bolo. Posso ajudar com TI?",
        "Meu papel é ajudar com TI. Se precisar de suporte de TI, "
        "posso simular uma necessidade para você.",
    ],
)
def test_outside_writer_rejects_answers_and_implementation_language(answer):
    context = new_conversation_context("x", "Fulano", "x@example.com", "TI", "REQUESTER")
    grounding = ground_response(
        {"status": "OUT_OF_SCOPE", "understood_topic": "poema"}, context, None
    )
    rendered = generate_natural_response(
        "escreva um poema",
        context,
        grounding,
        lambda _: {"message": {"content": json.dumps({"assistant_message": answer})}},
    )
    assert rendered == grounding.fallback_message


def test_language_guard_does_not_replace_substrings_in_natural_words():
    context = new_conversation_context("x", "Fulano", "x@example.com", "TI", "REQUESTER")
    grounding = ground_response({"status": "SOCIAL"}, context, None)
    answer = "Olá! Posso ajudar com sua política de acesso?"
    assert (
        generate_natural_response(
            "oi",
            context,
            grounding,
            lambda _: {"message": {"content": json.dumps({"assistant_message": answer})}},
        )
        == answer
    )


def test_contextual_scope_redirect_accepts_help_after_technology():
    context = new_conversation_context("x", "Fulano", "x@example.com", "TI", "REQUESTER")
    grounding = ground_response({"status": "OUT_OF_SCOPE"}, context, None)
    answer = (
        "Adoro a beleza do mar, mas meu papel aqui é focar em resolver necessidades de TI. "
        "Poderia me contar se há algum problema técnico ou dúvida sobre tecnologia "
        "que eu possa ajudar?"
    )
    assert (
        generate_natural_response(
            "poema",
            context,
            grounding,
            lambda _: {"message": {"content": json.dumps({"assistant_message": answer})}},
        )
        == answer
    )


def test_m365_and_approved_knowledge_keep_priority(runtime):
    send(runtime, "meu notebook está muito lento")
    first = send(runtime, "deixa isso, meu Office não entra")
    assert first["status"] == "NEEDS_CLARIFICATION"
    assert "general_triage" not in first
    guidance = send(runtime, "a senha está errada")
    assert guidance["status"] == "KNOWLEDGE_FOUND"
    assert not runtime.support_handoff_store.snapshot()


def test_requester_triage_is_isolated_and_trusted_profile_reaches_technician(runtime):
    other = runtime.identity_provider.configure_requester(
        name="Pessoa Teste",
        email="pessoa.teste@juparana.com.br",
        job_title="Analista",
        area="Financeiro",
    )
    send(runtime, "meu notebook está muito lento")
    first = send(runtime, "meu leitor de código de barras parou", other.identity_id)
    assert first["general_triage"]["questions_asked"] == 1
    runtime.reset_conversation("pedro-miranda")
    result = send(runtime, "não sei", other.identity_id)
    assert_general(result, 1)
    handoff = result["support_handoff"]
    assert handoff["requester"]["name"] == "Pessoa Teste"
    assert "Analista" in handoff["technical_summary"]
    assert "Financeiro" in handoff["technical_summary"]
    assert "notebook" not in handoff["technical_summary"]


def test_new_general_occurrence_does_not_reuse_old_handoff(runtime):
    send(runtime, "meu notebook está muito lento")
    old = send(runtime, "não sei")
    new = send(runtime, "outro problema: meu leitor de código de barras parou")
    assert new["status"] == "NEEDS_CLARIFICATION"
    final = send(runtime, "ele acende mas não lê")
    assert final["support_handoff"]["handoff_id"] != old["support_handoff"]["handoff_id"]
    assert "notebook" not in final["support_handoff"]["technical_summary"]


def test_approved_general_knowledge_wins_before_triage(runtime, monkeypatch):
    # Simulate an approved retrieval and its knowledge-only playbook boundary.
    monkeypatch.setattr(runtime.knowledge_engine, "available_systems", lambda _: ("SAP",))
    monkeypatch.setattr(runtime.playbook_engine, "resolve", lambda _: {"status": "KNOWLEDGE_ONLY"})
    monkeypatch.setattr(
        runtime.knowledge_engine,
        "search_classified",
        lambda *args, **kwargs: {
            "status": "KNOWLEDGE_FOUND",
            "knowledge": {
                "knowledge_id": "KB-TEST",
                "system": "GENERAL_IT",
                "intent": "OUTRO",
                "answer": "Orientação aprovada de teste.",
                "playbook_id": None,
                "related_playbook_id": None,
            },
        },
    )
    result = send(runtime, "o sistema SAP está muito lento")
    assert result["status"] == "KNOWLEDGE_FOUND"
    assert not runtime._general_triage


def test_it_how_to_is_not_misclassified_as_cooking(runtime):
    result = send(runtime, "como faço para acessar o CDM?")
    assert result["status"] == "KNOWLEDGE_FOUND"


def test_m365_how_to_is_not_misclassified_as_cooking(runtime):
    result = send(runtime, "como faço para trocar minha senha do Microsoft 365?")
    assert result["status"] == "KNOWLEDGE_FOUND"


def test_reset_clears_pending_but_keeps_materialized_handoff(runtime):
    send(runtime, "meu notebook está muito lento")
    runtime.reset_conversation("pedro-miranda")
    assert "pedro-miranda" not in runtime._general_triage
    send(runtime, "meu notebook está muito lento")
    result = send(runtime, "não sei")
    runtime.reset_conversation("pedro-miranda")
    assert runtime.support_handoff_store.get(result["support_handoff"]["handoff_id"])
    assert send(runtime, "meu notebook está muito lento")["status"] == "NEEDS_CLARIFICATION"


@pytest.mark.parametrize(
    "text", ["como faço um bolo?", "quanto foi o jogo?", "me ajuda a escrever um poema?"]
)
def test_outside_it_does_not_answer_or_handoff(runtime, text):
    result = send(runtime, text)
    assert result["status"] == "OUT_OF_SCOPE"
    assert not runtime.support_handoff_store.snapshot()
    assert "TI" in result["assistant_message"]
    topic = "bolo" if "bolo" in text else "jogo" if "jogo" in text else "poema"
    assert topic in result["assistant_message"].casefold()


@pytest.mark.parametrize(
    "unsafe",
    [
        "Reinicie o notebook.",
        "Experimente outra porta USB.",
        "Isso é defeito de memória.",
        "O técnico foi notificado e vai ligar amanhã.",
        "Você receberá retorno em uma hora.",
        "Limpe o cache.",
        "Execute sfc /scannow.",
        "Atualize o driver.",
        "Qual erro aparece? Quando começou? Qual aplicativo?",
        *[
            f"O {token} decidiu."
            for token in [
                "backend",
                "policy",
                "handler",
                "grounding",
                "capability",
                "routing",
                "confidence",
                "knowledge_id",
                "MODEL_INFERRED",
                "TRUSTED_SESSION",
                "GENERAL_IT_SUPPORT",
                "TECH-GENERAL",
                "verificação operacional",
                "escopo operacional",
            ]
        ],
    ],
)
def test_writer_cannot_add_procedures_facts_questions_or_internal_tokens(runtime, unsafe):
    result = send(runtime, "meu notebook está muito lento")
    context = runtime._conversation_contexts["pedro-miranda"]
    grounding = ground_response(result, context, None)

    def chat(payload):
        return {"message": {"content": json.dumps({"assistant_message": unsafe})}}

    rendered = generate_natural_response("meu notebook está muito lento", context, grounding, chat)
    assert rendered == grounding.fallback_message
    assert "reinicie" not in rendered.casefold()


@pytest.mark.parametrize(
    "token",
    [
        "policy",
        "capability",
        "routing",
        "confidence",
        "knowledge_id",
        "TECH-GENERAL",
        "GENERAL_IT_SUPPORT",
        "TRUSTED_SESSION",
        "MODEL_INFERRED",
        "verificação operacional",
        "escopo operacional",
    ],
)
def test_internal_tokens_rejected_in_all_requester_generation(token):
    context = new_conversation_context("x", "Fulano", "x@example.com", "TI", "REQUESTER")
    grounding = ground_response({"status": "SOCIAL"}, context, None)
    rendered = generate_natural_response(
        "oi",
        context,
        grounding,
        lambda _: {"message": {"content": json.dumps({"assistant_message": f"Olá, {token}."})}},
    )
    assert rendered == grounding.fallback_message
