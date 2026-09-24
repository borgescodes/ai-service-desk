import json
import re
from collections.abc import Callable

from ai_service_desk.engine.groq import GroqError
from ai_service_desk.engine.ollama import OllamaError
from ai_service_desk.engine.validation import normalize_text

_GREETING = re.compile(
    r"(?:bom dia|boa tarde|boa noite|oi|olá|ola)"
    r"(?:[\s,!]+jup)?(?:[\s,!]+(?:consegue|pode) me ajudar)?[.!?]*"
)


_OUTSIDE_IT_SCOPE = (
    re.compile(r"\b(?:quanto foi|quem ganhou|qual foi o placar)\b.*\b(?:jogo|partida)\b"),
    re.compile(
        r"\b(?:receita|ingredientes? para (?:um |uma )?receita|"
        r"como (?:fazer|faco|cozinhar) (?:um |uma )?(?:bolo|pao|torta|comida))\b"
    ),
    re.compile(r"\bqual(?: e)? a capital (?:da|de|do)\b"),
    re.compile(r"\b(?:escrever|escreve|escreva|cria|crie|faca)\b.*\b(?:poesia|poema)\b"),
)


def is_social_greeting(message: str) -> bool:
    return _GREETING.fullmatch(" ".join(message.casefold().split())) is not None


def is_outside_it_support_scope(message: str) -> bool:
    normalized = normalize_text(message)
    return any(pattern.search(normalized) is not None for pattern in _OUTSIDE_IT_SCOPE)


def scope_redirect_fallback(topic: str) -> str:
    normalized = normalize_text(topic)
    if re.search(r"\b(?:bolo|receita)\b", normalized):
        return (
            "Entendi que você procura uma receita de bolo. Aqui eu cuido de suporte "
            "e serviços de TI; se precisar de ajuda nessa área, pode me contar."
        )
    if re.search(r"\b(?:poema|poesia)\b", normalized):
        return (
            "Você quer ajuda com um poema, mas meu foco aqui é suporte de TI. "
            "Tem alguma necessidade de tecnologia em que eu possa ajudar?"
        )
    if re.search(r"\b(?:jogo|partida|futebol|placar)\b", normalized):
        return (
            "Sobre o jogo, não consigo ajudar por aqui. Cuido dos atendimentos "
            "e solicitações de TI; se precisar, pode me contar."
        )
    return (
        "Esse assunto fica fora do meu papel aqui. Posso ajudar com suporte e solicitações de TI."
    )


def greeting_message(
    message: str,
    name: str,
    chat: Callable[[dict], dict] | None,
) -> str:
    normalized = " ".join(message.casefold().split())
    if normalized.startswith("bom dia"):
        return "Bom dia! Como posso ajudar?"
    if normalized.startswith("boa tarde"):
        return "Boa tarde! Como posso ajudar?"
    if normalized.startswith("boa noite"):
        return "Boa noite! Como posso ajudar?"
    return "Oi! Como posso ajudar?"


def operational_message(result: dict, message: str, chat: Callable[[dict], dict] | None) -> str:
    if result.get("general_triage"):
        return result["general_triage"]["response_options"][0]
    if result["status"] == "OUT_OF_SCOPE":
        return scope_redirect_fallback(message)

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
        acknowledgment = "Entendi."
        return f"{acknowledgment}\n\n{question}" if question else acknowledgment

    if result["status"] == "TRIAGE_ABSTAINED":
        return (
            "Não encontrei uma orientação aprovada suficiente para esse caso. "
            "Nenhuma solicitação foi criada."
        )

    return f"Nenhuma solicitação foi criada. Resultado do processo: {result['status']}."


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


_INTERNAL_ARCHITECTURE_CLAIM = re.compile(
    r"\b(?:backend|grounding|handler|policy(?: engine)?|capabilit(?:y|ies)|routing|"
    r"confidence|knowledge_id|MODEL_INFERRED|USER_EXPLICIT|TRUSTED_SESSION|"
    r"GENERAL_IT(?:_SUPPORT)?|TECH-[\w-]+|SUPPORT_HANDOFF_PENDING|"
    r"NEEDS_CLARIFICATION|PENDING_APPROVAL|DENIED_POLICY|REQUIRE_APPROVAL|"
    r"ConversationInterpreter|ResponseGrounding|SupportHandoff(?:Store)?|"
    r"verifica[cç][aã]o operacional|escopo operacional)\b",
    re.I,
)


def _is_scope_redirect(text):
    normalized = normalize_text(text)
    if "escopo operacional" in normalized or re.search(
        r"\d|\b(?:encaminh\w*|notific\w*|contat\w*|ligar|retorno|sla|prazo|"
        r"mistur\w*|adicione|asse|preaque\w*|ingredientes|gols?|ganhou|venceu|"
        r"reinici\w*|instal\w*|execut\w*|simul\w*|recebera|resolveremos)\b",
        normalized,
    ):
        return False
    sentences = [
        normalize_text(part).strip() for part in re.split(r"[.!?\n]+", text) if part.strip()
    ]
    if not 1 <= len(sentences) <= 3 or len(text) > 500:
        return False
    role = re.compile(
        r"\b(?:meu (?:papel|foco)|suporte (?:de |e servicos de |tecnico)|"
        r"(?:assuntos|solicitacoes|necessidade|necessidades|questoes|servicos) de ti|"
        r"(?:ajudar|ajudo|ajuda|cuidar)\b.*\b(?:ti|tecnologia)|"
        r"(?:problema tecnico|duvida sobre tecnologia)\b.*\bajudar|"
        r"(?:aqui|atuo|cuido)\b.*\bti)\b"
    )
    acknowledgment = re.compile(
        r"^(?:entendi|vejo|percebi|voce (?:quer|gostaria|esta (?:buscando|procurando)))\b"
    )
    return any(role.search(part) for part in sentences) and all(
        role.search(part) or (index == 0 and acknowledgment.search(part))
        for index, part in enumerate(sentences)
    )


_INVENTED_CAPABILITY_CLAIM = re.compile(
    r"\b(?:tenho|temos) acesso ao sistema\b"
    r"|"
    r"\bt.cnico\b.{0,48}\b(?:est.|ficou) pronto\b",
    re.I,
)


def general_handoff_options(history):
    """Resumo extrativo: texto atribuído ao solicitante, nunca diagnóstico gerado."""
    reports = [item.text for item in history if item.role == "USER"]
    safe_reports = [
        text
        for text in reports
        if len(text) <= 220
        and not _INTERNAL_ARCHITECTURE_CLAIM.search(text)
        and not re.search(
            r"\b(?:reinici\w*|reinstal\w*|atualiz\w*|driver|usb|cache|comando|"
            r"configur\w*|registro|reset\w*|trocar|instal\w*|suporte|tecnico|"
            r"fazer|nao sei|nao tenho certeza|nao consigo dizer)\b",
            normalize_text(text),
        )
    ]
    summary = ""
    if safe_reports:
        summary = f"Você relatou “{safe_reports[0]}”. "
        if len(safe_reports) > 1:
            summary += f"Acrescentou: “{safe_reports[-1]}”. "
    return (
        summary + "Encaminhei esse contexto para o suporte de TI analisar.",
        "Entendi. " + summary + "Encaminhei o que você relatou para o suporte de TI analisar.",
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

    if _INTERNAL_ARCHITECTURE_CLAIM.search(text):
        return True

    if _INVENTED_CAPABILITY_CLAIM.search(text):
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
        "Voce e Jup, agente conversacional de suporte de TI. "
        "Escreva de forma natural e contextual, sem usar respostas de catalogo. "
        "Use somente os fatos operacionais confirmados fornecidos nesta instrucao. "
        "Nunca preencha fatos operacionais ausentes usando conhecimento do modelo. "
        "Nunca exponha componentes internos, mecanismos de decisao ou "
        "detalhes de implementacao.\n\n"
        f"Objetivo da resposta: {grounding.response_goal}\n"
        f"Fatos confirmados: {list(grounding.facts)}\n"
        f"Afirmacoes proibidas: {list(grounding.forbidden_claims)}\n"
        f"Informacoes obrigatorias: {list(grounding.required_information)}\n"
        f"Turnos recentes: {recent_turns}"
    )
    if grounding.response_options:
        instruction += (
            f"\nEscolha a formulação mais adequada ao turno entre: {grounding.response_options}. "
            "Retorne a frase escolhida literalmente em assistant_message, sem acrescentar nada."
        )
    if grounding.allowed_wrappers is not None:
        instruction += (
            f"\nintro e outro devem ser escolhidos somente entre: {grounding.allowed_wrappers}. "
            "Prefira outro vazio. O conteúdo confirmado será inserido pelo sistema."
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

        if grounding.allowed_wrappers is not None and any(
            part.strip() not in grounding.allowed_wrappers for part in (intro, outro)
        ):
            return grounding.fallback_message

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

    if grounding.response_options and assistant_message.strip() not in grounding.response_options:
        return grounding.fallback_message

    if grounding.disposition == "OUT_OF_SCOPE" and not _is_scope_redirect(assistant_message):
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
    except (OllamaError, GroqError, ValueError, KeyError, TypeError, AttributeError):
        return grounding.fallback_message
