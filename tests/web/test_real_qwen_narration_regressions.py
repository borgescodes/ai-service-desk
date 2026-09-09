import json

import pytest

from ai_service_desk.web.conversation import operational_message
from ai_service_desk.web.errors import WebDemoError


def _clarification_result() -> dict:
    return {
        "status": "NEEDS_CLARIFICATION",
        "request_id": None,
        "question": "Qual sistema esta com o problema?",
        "reason": "MISSING_SYSTEM",
    }


def _chat_response(text: str) -> dict:
    return {
        "message": {
            "content": json.dumps({"assistant_message": text}, ensure_ascii=False),
        }
    }


def test_clarification_prompt_keeps_backend_question_out_of_llm_input() -> None:
    message = (
        "Jup, preciso pedir material para uma revenda mas acho que nunca me deram acesso "
        "ao sistema que faz isso. Você consegue verificar?"
    )
    captured = {}

    def chat(payload: dict) -> dict:
        captured.update(payload)
        return _chat_response(
            "Entendi que você precisa solicitar materiais para uma revenda e aparentemente "
            "falta acesso."
        )

    rendered = operational_message(_clarification_result(), message, chat)

    assert captured["messages"][-1]["content"] == message
    instruction = captured["messages"][0]["content"].casefold()
    assert "backend" not in instruction
    assert "pergunta exigida" not in instruction
    assert "não responda" not in instruction
    assert rendered.endswith("Qual sistema esta com o problema?")


def test_clarification_rejects_meta_instruction_leak_from_llm() -> None:
    def chat(_payload: dict) -> dict:
        return _chat_response(
            "Como solicitado, não posso responder à pergunta exigida porque o backend ainda "
            "não informou."
        )

    with pytest.raises(WebDemoError) as exc_info:
        operational_message(
            _clarification_result(),
            "Preciso pedir material para uma revenda e acho que não tenho acesso ao sistema.",
            chat,
        )

    assert exc_info.value.code == "OPERATIONAL_RESPONSE_UNAVAILABLE"


def test_office_clarification_uses_contextual_system_question() -> None:
    result = _clarification_result()

    def chat(_payload: dict) -> dict:
        return _chat_response(
            "Entendi que você esqueceu sua senha do Office e não consegue entrar."
        )

    rendered = operational_message(
        result,
        "Cara, esqueci minha senha do Office e não consigo entrar. O que eu faço?",
        chat,
    )

    assert result["question"] == "Qual sistema esta com o problema?"
    assert "microsoft 365/office 365" in rendered.casefold()
    assert "outro sistema" in rendered.casefold()
    assert "Qual sistema esta com o problema?" not in rendered
