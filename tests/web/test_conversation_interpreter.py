import json

import pytest

from ai_service_desk.web.business_context import BusinessVocabulary
from ai_service_desk.web.conversation_interpreter import (
    build_interpretation_payload,
    classification_from_context,
    parse_interpretation_response,
)
from ai_service_desk.web.conversation_state import (
    ConversationDelta,
    FactAuthority,
    TurnRelation,
    new_conversation_context,
    reduce_conversation_context,
)


def m365_context():
    context = new_conversation_context(
        identity_id="pedro-miranda",
        name="Fulano de Tal",
        email="fulano.tal@juparana.com.br",
        area="Revenda - Matriz",
        role="REQUESTER",
    )
    return reduce_conversation_context(
        context,
        ConversationDelta(
            relation=TurnRelation.NEW_GOAL,
            domain="IT_SUPPORT",
            goal="RECOVER_ACCESS",
            intent="PROBLEMA_ACESSO",
            entities={
                "system": "OFFICE 365",
                "product": "OUTLOOK",
            },
            facts_added=(),
            facts_corrected=(),
            answered_pending_question=False,
            semantic_signal="LOGIN_PROBLEM",
            understood_topic="Problema de acesso no Outlook",
        ),
        user_message="Meu Outlook não entra",
    )


def valid_interpretation_data():
    return {
        "relation": "CONTINUATION",
        "domain": "IT_SUPPORT",
        "goal": "RECOVER_ACCESS",
        "intent": "PROBLEMA_ACESSO",
        "entities": {
            "system": "OFFICE 365",
            "product": "OUTLOOK",
        },
        "facts_added": [
            {
                "key": "product",
                "value": "OUTLOOK",
                "source": "USER_EXPLICIT",
            }
        ],
        "facts_corrected": [],
        "answered_pending_question": True,
        "semantic_signal": "PASSWORD_EVIDENCE",
        "understood_topic": "A senha está sendo rejeitada",
    }


def response_for(data, *, done_reason="stop"):
    return {
        "message": {
            "content": json.dumps(
                data,
                ensure_ascii=False,
            )
        },
        "done_reason": done_reason,
    }


def test_payload_contains_context_and_no_operational_authority():
    payload = build_interpretation_payload(
        m365_context(),
        "fala que a senha está errada",
        BusinessVocabulary(),
    )

    assert payload["model"] == "qwen3.5:4b"
    assert payload["think"] is False
    assert payload["stream"] is False
    assert payload["keep_alive"] == "30m"
    assert payload["options"] == {
        "temperature": 0,
        "num_ctx": 3072,
        "num_predict": 192,
    }

    schema = payload["format"]
    properties = schema["properties"]

    assert schema["additionalProperties"] is False
    assert {"relation", "domain", "semantic_signal"} <= set(properties)

    for forbidden in (
        "policy",
        "request_id",
        "request_state",
        "approved",
        "technician",
        "execution",
    ):
        assert forbidden not in properties

    for fact_field in ("facts_added", "facts_corrected"):
        fact_schema = properties[fact_field]["items"]
        assert fact_schema["additionalProperties"] is False
        assert fact_schema["properties"]["source"]["enum"] == [
            "USER_EXPLICIT",
            "MODEL_INFERRED",
        ]

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "OFFICE 365" in serialized
    assert "OUTLOOK" in serialized


def test_parser_returns_conversation_delta_for_valid_response():
    delta = parse_interpretation_response(response_for(valid_interpretation_data()))

    assert delta.relation == TurnRelation.CONTINUATION
    assert delta.domain == "IT_SUPPORT"
    assert delta.goal == "RECOVER_ACCESS"
    assert delta.intent == "PROBLEMA_ACESSO"
    assert delta.entities == {
        "system": "OFFICE 365",
        "product": "OUTLOOK",
    }
    assert delta.answered_pending_question is True
    assert delta.semantic_signal == "PASSWORD_EVIDENCE"
    assert delta.facts_added[0].key == "product"
    assert delta.facts_added[0].value == "OUTLOOK"
    assert delta.facts_added[0].source == FactAuthority.USER_EXPLICIT


@pytest.mark.parametrize(
    "response",
    [
        {
            "message": {
                "content": "{not-json",
            },
            "done_reason": "stop",
        },
        {
            "message": {
                "content": json.dumps(
                    {
                        "relation": "CONTINUATION",
                        "extra": True,
                    }
                )
            },
            "done_reason": "stop",
        },
        response_for(
            valid_interpretation_data(),
            done_reason="length",
        ),
    ],
)
def test_parser_rejects_malformed_extra_or_truncated_response(response):
    with pytest.raises(ValueError):
        parse_interpretation_response(response)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("relation", "MAYBE"),
        ("domain", "FINANCE"),
        ("intent", "INVENTED_INTENT"),
        ("semantic_signal", "MODEL_DECIDES"),
    ],
)
def test_parser_rejects_invalid_enums(field, value):
    data = valid_interpretation_data()
    data[field] = value

    with pytest.raises(ValueError):
        parse_interpretation_response(response_for(data))


def test_parser_rejects_missing_field():
    data = valid_interpretation_data()
    data.pop("goal")

    with pytest.raises(ValueError):
        parse_interpretation_response(response_for(data))


def test_parser_rejects_non_string_entity():
    data = valid_interpretation_data()
    data["entities"] = {
        "system": "OFFICE 365",
        "product": 123,
    }

    with pytest.raises(ValueError):
        parse_interpretation_response(response_for(data))


def test_parser_rejects_operational_fact_source():
    data = valid_interpretation_data()
    data["facts_added"] = [
        {
            "key": "request_state",
            "value": "APPROVED",
            "source": "BACKEND",
        }
    ]

    with pytest.raises(ValueError):
        parse_interpretation_response(response_for(data))


def test_short_follow_up_classification_preserves_m365_context():
    context = m365_context()
    delta = ConversationDelta(
        relation=TurnRelation.ANSWER_TO_PENDING,
        domain="IT_SUPPORT",
        goal="RECOVER_ACCESS",
        intent="PROBLEMA_ACESSO",
        entities={},
        facts_added=(),
        facts_corrected=(),
        answered_pending_question=True,
        semantic_signal="PASSWORD_EVIDENCE",
        understood_topic="A senha está sendo rejeitada",
    )

    classification = classification_from_context(
        context,
        delta,
        BusinessVocabulary(),
    )

    assert classification.system == "OFFICE 365"
    assert classification.entities["product"] == "OUTLOOK"
    assert classification.intent == "PROBLEMA_ACESSO"
