import json

import pytest

from ai_service_desk.engine.ollama import OllamaError
from ai_service_desk.web.conversation import generate_natural_response
from ai_service_desk.web.conversation_grounding import ground_response
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


def base_delta():
    return ConversationDelta(
        relation=TurnRelation.NEW_GOAL,
        domain="IT_SUPPORT",
        goal="REQUEST_ACCESS",
        intent="PROBLEMA_ACESSO",
        entities={"system": "CDM"},
        facts_added=(),
        facts_corrected=(),
        answered_pending_question=False,
        semantic_signal="ACCESS_REQUEST",
        understood_topic="acesso ao CDM",
    )


def pending_approval_grounding():
    return ground_response(
        {
            "status": "REQUEST_CREATED",
            "request_id": "REQ-123456",
            "state": "PENDING_APPROVAL",
            "policy": "REQUIRE_APPROVAL",
        },
        base_context(),
        base_delta(),
    )


@pytest.mark.parametrize(
    "claim",
    [
        "Sua solicitação REQ-999999 foi registrada.",
        "Sua solicitação foi aprovada.",
        "Já liberei seu acesso.",
        "Tudo foi executado e concluído.",
    ],
)
def test_untrusted_writer_claims_fall_back_to_backend_grounding(claim):
    grounding = pending_approval_grounding()

    def chat(payload):
        return {
            "message": {
                "content": json.dumps(
                    {
                        "assistant_message": claim,
                    }
                )
            },
            "done_reason": "stop",
        }

    rendered = generate_natural_response(
        "Preciso de acesso ao CDM",
        base_context(),
        grounding,
        chat,
    )

    assert rendered == grounding.fallback_message
    assert "REQ-999999" not in rendered
    assert "aprovada" not in rendered.casefold()
    assert "liberei" not in rendered.casefold()
    assert "executado" not in rendered.casefold()


@pytest.mark.parametrize(
    "failure_mode",
    [
        "invalid_json",
        "truncated",
        "ollama_error",
    ],
)
def test_writer_failures_preserve_backend_fallback(failure_mode):
    grounding = pending_approval_grounding()

    def chat(payload):
        if failure_mode == "invalid_json":
            return {
                "message": {"content": "{not-json"},
                "done_reason": "stop",
            }

        if failure_mode == "truncated":
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "assistant_message": "Resposta incompleta",
                        }
                    )
                },
                "done_reason": "length",
            }

        raise OllamaError("Falha simulada do Ollama.")

    rendered = generate_natural_response(
        "Preciso de acesso ao CDM",
        base_context(),
        grounding,
        chat,
    )

    assert rendered == grounding.fallback_message
    assert "REQ-123456" in rendered
    assert "aguarda aprovação" in rendered
