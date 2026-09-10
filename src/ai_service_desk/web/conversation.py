import json
import re
from collections.abc import Callable

from ai_service_desk.engine.ollama import OllamaError
from ai_service_desk.web.business_context import BusinessVocabulary
from ai_service_desk.web.errors import WebDemoError

_GREETING = re.compile(
    r"(?:bom dia|boa tarde|boa noite|oi|olá|ola)"
    r"(?:[\s,!]+jup)?(?:[\s,!]+(?:consegue|pode) me ajudar)?[.!?]*"
)


def is_social_greeting(message: str) -> bool:
    return _GREETING.fullmatch(" ".join(message.casefold().split())) is not None


def greeting_message(message: str, name: str, chat: Callable[[dict], dict] | None) -> str:
    if chat is None:
        return f"Olá, {name.split()[0]}! Me conta o que você precisa resolver ou acessar."

    choices = (
        f"Olá, {name.split()[0]}! Me conta o que você precisa resolver ou acessar.",
        f"Oi, {name.split()[0]}! Como posso ajudar?",
    )
    return _conversation_message(
        message,
        "Você é Jup. Escolha uma das saudações permitidas pelo formato JSON. "
        f"O nome do solicitante, confirmado pelo backend, é {name}. "
        "Use seu primeiro nome e convide-o a contar o que precisa. "
        "Não afirme ter criado solicitações, aprovado ou executado ações.",
        chat,
        "SOCIAL_RESPONSE_UNAVAILABLE",
        choices,
    )


def operational_message(result: dict, message: str, chat: Callable[[dict], dict] | None) -> str:
    if result["status"] == "KNOWLEDGE_FOUND":
        return f"Encontrei uma orientação aprovada para esse caso:\n\n{result['answer']}"

    if result["request_id"] is not None:
        if result["state"] == "PENDING_APPROVAL" and result["policy"] == "REQUIRE_APPROVAL":
            return f"Sua solicitação {result['request_id']} foi registrada e aguarda aprovação."
        return (
            f"Sua solicitação {result['request_id']} foi registrada. "
            f"Estado informado pelo processo: {result['state']}."
        )

    if result["status"] == "NEEDS_CLARIFICATION":
        question = result.get("question") or ""
        systems = BusinessVocabulary().systems(message)
        choices = ("Entendi seu relato.", "Entendi que você precisa de ajuda.")
        if systems:
            choices = (f"Entendi seu relato sobre {', '.join(systems)}.", *choices)
        acknowledgment = choices[0]
        if chat is not None:
            acknowledgment = _conversation_message(
                message,
                "Você é Jup. Escolha um reconhecimento permitido pelo formato JSON. "
                "Fale diretamente com a pessoa em segunda pessoa e apenas reconheça o que ela "
                "relatou. Não faça perguntas. Não mencione instruções, limitações, regras ou "
                "processos internos. Não use a expressão 'o usuário'. Não invente solução, "
                "identidade, decisão, estado ou ação executada.",
                chat,
                "OPERATIONAL_RESPONSE_UNAVAILABLE",
                choices,
            )
        return f"{acknowledgment}\n\n{question}" if question else acknowledgment

    return f"Nenhuma solicitação foi criada. Resultado do processo: {result['status']}."


def _conversation_message(
    message: str,
    instruction: str,
    chat: Callable[[dict], dict],
    error_code: str,
    choices: tuple[str, ...],
) -> str:
    payload = {
        "model": "qwen3.5:4b",
        "stream": False,
        "think": False,
        "messages": [
            {
                "role": "system",
                "content": instruction,
            },
            {"role": "user", "content": message},
        ],
        "format": {
            "type": "object",
            "properties": {"assistant_message": {"type": "string", "enum": list(choices)}},
            "required": ["assistant_message"],
            "additionalProperties": False,
        },
        "options": {"temperature": 0, "num_predict": 256},
    }
    try:
        response = chat(payload)
        if response.get("done_reason") == "length":
            raise ValueError("Resposta conversacional truncada.")
        data = json.loads(response["message"]["content"])
        if not isinstance(data, dict) or set(data) != {"assistant_message"}:
            raise ValueError("Resposta fora do contrato de apresentação.")
        text = data["assistant_message"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Resposta conversacional vazia.")
        if text not in choices:
            raise ValueError("Reconhecimento não autorizado pelo contrato de apresentação.")
        return text
    except (OllamaError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise WebDemoError(
            error_code, "Não foi possível obter a resposta conversacional do Ollama."
        ) from exc
