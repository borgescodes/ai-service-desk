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


_OUTSIDE_IT_SCOPE = (
    re.compile(r"\b(?:quanto foi|quem ganhou|qual foi o placar)\b.*\b(?:jogo|partida)\b"),
    re.compile(r"\b(?:receita|ingredientes? para (?:um |uma )?receita|como (?:fazer|cozinhar))\b"),
    re.compile(r"\bqual(?: e)? a capital (?:da|de|do)\b"),
    re.compile(r"\b(?:escreve|escreva|cria|crie|faca)\b.*\b(?:poesia|poema)\b"),
)


def is_social_greeting(message: str) -> bool:
    return _GREETING.fullmatch(" ".join(message.casefold().split())) is not None


def is_outside_it_support_scope(message: str) -> bool:
    normalized = " ".join(message.casefold().split())
    return any(pattern.search(normalized) is not None for pattern in _OUTSIDE_IT_SCOPE)


def greeting_message(message: str, name: str, chat: Callable[[dict], dict] | None) -> str:
    if chat is None:
        normalized = " ".join(message.casefold().split())
        if normalized.startswith("bom dia"):
            return "Bom dia! Como posso ajudar?"
        if normalized.startswith("boa tarde"):
            return "Boa tarde! Como posso ajudar?"
        if normalized.startswith("boa noite"):
            return "Boa noite! Como posso ajudar?"
        return "Oi! Como posso ajudar?"

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
    if result["status"] == "OUT_OF_SCOPE":
        return (
            "Meu foco aqui é suporte de TI, como acesso a sistemas, Microsoft 365 "
            "e solicitações no CDM. Para esse outro assunto, não vou responder por aqui."
        )

    if result["status"] == "KNOWLEDGE_FOUND":
        return f"Encontrei uma orientação aprovada para esse caso:\n\n{result['answer']}"

    if result["status"] == "SUPPORT_RESOLVED":
        return "Ótimo, seu acesso voltou a funcionar. Vou considerar este atendimento resolvido."

    if result["status"] == "SUPPORT_HANDOFF_PENDING":
        handoff = result.get("support_handoff") or {}
        technician = handoff.get("technician") or {}
        technician_name = technician.get("name") or "o suporte técnico"
        if (
            handoff.get("capability") == "GENERAL_IT_SUPPORT"
            or handoff.get("confidence") is not None
        ):
            system = handoff.get("system") or "TI"
            if system == "MICROSOFT_365":
                system = "Microsoft 365"
            return (
                f"Entendi o contexto do seu atendimento sobre {system}. "
                "Ainda não tenho um procedimento aprovado suficiente para orientar esse caso "
                "com segurança, então "
                f"encaminhei o atendimento para {technician_name}."
            )
        return (
            "Entendi. Como o procedimento não resolveu o acesso, "
            f"encaminhei o atendimento para {technician_name}."
        )

    if result["status"] == "GUIDANCE_AWAITING_RESULT":
        return (
            "Se o acesso continuar indisponível depois do procedimento, me avise aqui "
            "para eu continuar o atendimento."
        )

    if result["request_id"] is not None:
        if result["state"] == "DENIED_POLICY" and result["policy"] == "DENY":
            return (
                "Esse tipo de acesso administrativo não pode ser liberado por este atendimento. "
                "Se o que você precisa é acessar o CDM para solicitar materiais, posso te ajudar "
                "com o perfil de solicitante."
            )
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
        acknowledgment = "Entendi."
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

    if result["status"] == "TRIAGE_ABSTAINED":
        return (
            "Não encontrei uma orientação aprovada suficiente para esse caso. "
            "Nenhuma solicitação foi criada."
        )

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


_REQUEST_ID = re.compile(r"\bREQ-\d{6}\b")
_APPROVAL_CLAIM = re.compile(
    r"\b(?:solicita[cç][aã]o|pedido|requisi[cç][aã]o|acesso|request|access request)\b"
    r".{0,32}\b(?:aprovad[oa]|approved)\b"
    r"|"
    r"\b(?:aprovad[oa]|approved)\b"
    r".{0,16}\b(?:solicita[cç][aã]o|pedido|requisi[cç][aã]o|acesso|request|access request)\b",
    re.I,
)
_EXECUTION_CLAIM = re.compile(
    r"\b(?:executad[oa]|completed|conclu[ií]d[oa])\b",
    re.I,
)
_ACCESS_GRANTED_CLAIM = re.compile(
    r"\b(?:acesso (?:foi )?liberad[oa]|já liberei|pode entrar)\b",
    re.I,
)


def _has_invalid_operational_claim(text, grounding):
    allowed = {value.casefold() for value in grounding.allowed_operational_values}

    request_ids = _REQUEST_ID.findall(text)
    if any(request_id.casefold() not in allowed for request_id in request_ids):
        return True

    if _APPROVAL_CLAIM.search(text) and "approved" not in allowed:
        return True

    if _EXECUTION_CLAIM.search(text) and not {
        "executed",
        "completed",
    }.intersection(allowed):
        return True

    if _ACCESS_GRANTED_CLAIM.search(text) and not {
        "access_granted",
        "granted",
    }.intersection(allowed):
        return True

    return False


def _generate_natural_response(message, context, grounding, chat):
    protected = bool(grounding.protected_content)

    if protected:
        response_format = {
            "type": "object",
            "properties": {
                "intro": {"type": "string"},
                "outro": {"type": "string"},
            },
            "required": ["intro", "outro"],
            "additionalProperties": False,
        }
    else:
        response_format = {
            "type": "object",
            "properties": {
                "assistant_message": {"type": "string"},
            },
            "required": ["assistant_message"],
            "additionalProperties": False,
        }

    recent_turns = [
        {
            "role": turn.role,
            "text": turn.text,
        }
        for turn in getattr(context, "recent_turns", ())
    ]

    instruction = (
        "Você é Jup, agente conversacional de suporte de TI. "
        "Escreva de forma natural e contextual, sem usar respostas de catálogo. "
        "O backend é a única autoridade operacional. "
        "Nunca preencha fatos operacionais ausentes usando conhecimento do modelo.\n\n"
        f"Objetivo da resposta: {grounding.response_goal}\n"
        f"Fatos confirmados: {list(grounding.facts)}\n"
        f"Afirmações proibidas: {list(grounding.forbidden_claims)}\n"
        f"Informações obrigatórias: {list(grounding.required_information)}\n"
        f"Turnos recentes: {recent_turns}"
    )

    payload = {
        "model": "qwen3.5:4b",
        "think": False,
        "stream": False,
        "keep_alive": "30m",
        "messages": [
            {
                "role": "system",
                "content": instruction,
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        "format": response_format,
        "options": {
            "temperature": 0.4,
            "num_ctx": 3072,
            "num_predict": 256,
        },
    }

    response = chat(payload)
    if response.get("done_reason") == "length":
        raise ValueError("Resposta conversacional truncada.")

    data = json.loads(response["message"]["content"])
    if not isinstance(data, dict):
        raise ValueError("Resposta conversacional fora do contrato.")

    if protected:
        if set(data) != {"intro", "outro"}:
            raise ValueError("Resposta protegida fora do contrato.")

        intro = data["intro"]
        outro = data["outro"]
        if not isinstance(intro, str) or not isinstance(outro, str):
            raise ValueError("Resposta protegida deve conter apenas texto.")

        if _has_invalid_operational_claim(intro, grounding):
            return grounding.fallback_message
        if _has_invalid_operational_claim(outro, grounding):
            return grounding.fallback_message

        parts = [
            intro.strip(),
            *(item.content for item in grounding.protected_content),
            outro.strip(),
        ]
        return "\n\n".join(part for part in parts if part)

    if set(data) != {"assistant_message"}:
        raise ValueError("Resposta conversacional fora do contrato.")

    assistant_message = data["assistant_message"]
    if not isinstance(assistant_message, str) or not assistant_message.strip():
        raise ValueError("Resposta conversacional vazia.")

    if _has_invalid_operational_claim(assistant_message, grounding):
        return grounding.fallback_message

    return assistant_message.strip()


def generate_natural_response(message, context, grounding, chat):
    try:
        return _generate_natural_response(
            message,
            context,
            grounding,
            chat,
        )
    except (OllamaError, ValueError, KeyError, TypeError, AttributeError):
        return grounding.fallback_message
