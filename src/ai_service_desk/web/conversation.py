import json
import re
from collections.abc import Callable

from ai_service_desk.engine.ollama import OllamaError
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

    payload = {
        "model": "qwen3.5:4b",
        "stream": False,
        "think": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é Jup. Responda apenas à saudação, em português, "
                    "de forma breve e natural. "
                    f"O nome do solicitante, confirmado pelo backend, é {name}. "
                    "Use seu primeiro nome e convide-o a contar o que precisa. "
                    "Não afirme ter criado solicitações, aprovado ou executado ações."
                ),
            },
            {"role": "user", "content": message},
        ],
        "format": {
            "type": "object",
            "properties": {"assistant_message": {"type": "string"}},
            "required": ["assistant_message"],
            "additionalProperties": False,
        },
        "options": {"temperature": 0, "num_predict": 256},
    }
    try:
        response = chat(payload)
        if response.get("done_reason") == "length":
            raise ValueError("Resposta social truncada.")
        data = json.loads(response["message"]["content"])
        text = data["assistant_message"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Resposta social vazia.")
        return text.strip()
    except (OllamaError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise WebDemoError(
            "SOCIAL_RESPONSE_UNAVAILABLE", "Não foi possível obter a resposta social do Ollama."
        ) from exc
