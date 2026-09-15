import json

from ai_service_desk.web.conversation import generate_natural_response
from ai_service_desk.web.conversation_grounding import (
    ConversationDisposition,
    ground_response,
)
from ai_service_desk.web.conversation_state import (
    ConversationDelta,
    TurnRelation,
    new_conversation_context,
)


def base_context():
    return new_conversation_context(
        identity_id="pedro-miranda",
        name="Fulano de Tal",
        email="fulano.tal@juparana.com.br",
        area="Revenda - Matriz",
        role="REQUESTER",
    )


def delta_for(domain="IT_SUPPORT", topic=""):
    return ConversationDelta(
        relation=TurnRelation.NEW_GOAL,
        domain=domain,
        goal="DIAGNOSE_ISSUE" if domain == "IT_SUPPORT" else "",
        intent="PROBLEMA_ACESSO" if domain == "IT_SUPPORT" else "OUTRO",
        entities={},
        facts_added=(),
        facts_corrected=(),
        answered_pending_question=False,
        semantic_signal="NONE",
        understood_topic=topic,
    )


def test_approved_knowledge_is_protected():
    answer = "PASSO OFICIAL 1\nPASSO OFICIAL 2"

    grounding = ground_response(
        {
            "status": "KNOWLEDGE_FOUND",
            "request_id": None,
            "answer": answer,
            "knowledge_id": "KB-1",
        },
        base_context(),
        delta_for(),
    )

    assert grounding.disposition == ConversationDisposition.ANSWER_WITH_APPROVED_KNOWLEDGE
    assert [item.content for item in grounding.protected_content] == [answer]


def test_out_of_scope_grounding_has_topic_and_no_handoff():
    grounding = ground_response(
        {
            "status": "OUT_OF_SCOPE",
            "request_id": None,
            "understood_topic": "xadrez",
        },
        base_context(),
        delta_for(
            domain="OTHER",
            topic="xadrez",
        ),
    )

    assert grounding.disposition == ConversationDisposition.OUT_OF_SCOPE
    assert "xadrez" in " ".join(grounding.facts).casefold()
    assert "técnico" not in " ".join(grounding.facts).casefold()


def test_normal_writer_schema_has_free_string_not_enum():
    captured = []

    def chat(payload):
        captured.append(payload)
        return {
            "message": {
                "content": json.dumps(
                    {
                        "assistant_message": (
                            "Xadrez foge do meu papel aqui; posso cuidar da parte de TI."
                        )
                    }
                )
            },
            "done_reason": "stop",
        }

    grounding = ground_response(
        {
            "status": "OUT_OF_SCOPE",
            "request_id": None,
            "understood_topic": "xadrez",
        },
        base_context(),
        delta_for(
            domain="OTHER",
            topic="xadrez",
        ),
    )

    rendered = generate_natural_response(
        "Como melhorar no xadrez?",
        base_context(),
        grounding,
        chat,
    )

    assert captured[0]["format"]["properties"]["assistant_message"] == {"type": "string"}
    assert "enum" not in json.dumps(captured[0]["format"])
    assert rendered.startswith("Xadrez")


def test_backend_inserts_approved_content_exactly_once():
    answer = "PASSO OFICIAL 1\nPASSO OFICIAL 2"

    grounding = ground_response(
        {
            "status": "KNOWLEDGE_FOUND",
            "request_id": None,
            "answer": answer,
            "knowledge_id": "KB-1",
        },
        base_context(),
        delta_for(),
    )

    def chat(payload):
        return {
            "message": {
                "content": json.dumps(
                    {
                        "intro": "Temos uma orientação aprovada.",
                        "outro": "Me diga se resolveu.",
                    }
                )
            },
            "done_reason": "stop",
        }

    rendered = generate_natural_response(
        "Minha senha falhou",
        base_context(),
        grounding,
        chat,
    )

    assert rendered.count(answer) == 1
    assert rendered == (f"Temos uma orientação aprovada.\n\n{answer}\n\nMe diga se resolveu.")


def test_backend_statuses_map_to_authoritative_dispositions():
    cases = (
        (
            {"status": "SOCIAL", "request_id": None},
            ConversationDisposition.SOCIAL,
        ),
        (
            {
                "status": "NEEDS_CLARIFICATION",
                "request_id": None,
                "question": "Qual sistema está com o problema?",
            },
            ConversationDisposition.ASK_CLARIFICATION,
        ),
        (
            {
                "status": "DENIED_POLICY",
                "request_id": "REQ-000001",
                "state": "DENIED_POLICY",
                "policy": "DENY",
            },
            ConversationDisposition.DENY_BY_POLICY,
        ),
        (
            {
                "status": "REQUEST_CREATED",
                "request_id": "REQ-000002",
                "state": "DENIED_POLICY",
                "policy": "DENY",
            },
            ConversationDisposition.DENY_BY_POLICY,
        ),
        (
            {
                "status": "REQUEST_CREATED",
                "request_id": "REQ-000003",
                "state": "PENDING_APPROVAL",
                "policy": "REQUIRE_APPROVAL",
            },
            ConversationDisposition.WAIT_FOR_APPROVAL,
        ),
        (
            {
                "status": "REQUEST_CREATED",
                "request_id": "REQ-000004",
                "state": "CREATED",
                "policy": "ALLOW",
            },
            ConversationDisposition.CREATE_ACCESS_REQUEST,
        ),
        (
            {
                "status": "SUPPORT_HANDOFF_PENDING",
                "request_id": None,
                "support_handoff": {
                    "system": "UBS",
                    "technician": {"name": "TECH-GENERAL"},
                },
            },
            ConversationDisposition.HANDOFF,
        ),
        (
            {
                "status": "SUPPORT_RESOLVED",
                "request_id": None,
            },
            ConversationDisposition.ACKNOWLEDGE_RESOLUTION,
        ),
    )

    for result, expected in cases:
        grounding = ground_response(
            result,
            base_context(),
            delta_for(),
        )
        assert grounding.disposition == expected


def test_pending_request_exposes_backend_operational_values_only():
    grounding = ground_response(
        {
            "status": "REQUEST_CREATED",
            "request_id": "REQ-123456",
            "state": "PENDING_APPROVAL",
            "policy": "REQUIRE_APPROVAL",
        },
        base_context(),
        delta_for(),
    )

    assert grounding.allowed_operational_values == frozenset(
        {
            "REQ-123456",
            "PENDING_APPROVAL",
            "REQUIRE_APPROVAL",
        }
    )
