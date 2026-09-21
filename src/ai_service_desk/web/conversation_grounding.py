from dataclasses import dataclass, replace
from enum import StrEnum

from ai_service_desk.web.conversation import scope_redirect_fallback


class ConversationDisposition(StrEnum):
    SOCIAL = "SOCIAL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    ANSWER_WITH_APPROVED_KNOWLEDGE = "ANSWER_WITH_APPROVED_KNOWLEDGE"
    CREATE_ACCESS_REQUEST = "CREATE_ACCESS_REQUEST"
    DENY_BY_POLICY = "DENY_BY_POLICY"
    WAIT_FOR_APPROVAL = "WAIT_FOR_APPROVAL"
    HANDOFF = "HANDOFF"
    ACKNOWLEDGE_RESOLUTION = "ACKNOWLEDGE_RESOLUTION"
    REQUEST_STATUS = "REQUEST_STATUS"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class ProtectedContent:
    kind: str
    content: str


@dataclass(frozen=True)
class ResponseGrounding:
    disposition: ConversationDisposition
    response_goal: str
    verbosity: str
    facts: tuple[str, ...]
    protected_content: tuple[ProtectedContent, ...]
    forbidden_claims: tuple[str, ...]
    required_information: tuple[str, ...]
    fallback_message: str
    allowed_operational_values: frozenset[str]
    allowed_wrappers: tuple[str, ...] | None = None
    response_options: tuple[str, ...] = ()


def _consolidated_facts(context) -> tuple[str, ...]:
    rendered = []
    for fact in getattr(context, "facts", ()):
        key = getattr(fact, "key", "")
        value = getattr(fact, "value", "")
        if key and value:
            rendered.append(f"{key}: {value}")
    return tuple(rendered)


def ground_response(result, context, delta) -> ResponseGrounding:
    grounding = _ground_response(result, context, delta)
    if result.get("general_triage"):
        options = tuple(result["general_triage"]["response_options"])
        return replace(
            grounding,
            facts=(),
            response_goal="Use somente a pergunta ou o encaminhamento confirmado, com o relato.",
            fallback_message=options[0],
            response_options=options,
            forbidden_claims=(
                *grounding.forbidden_claims,
                "Não acrescente procedimentos, causas, diagnóstico, fatos técnicos ou perguntas.",
                "Não prometa contato, notificação, prazo, resolução ou acompanhamento.",
            ),
        )
    article = result.get("article") or {}
    article_is_approved = article.get("provenance", {}).get("status") == "APPROVED"
    if result.get("system") != "CDM" and not article_is_approved:
        return grounding
    # The writer may connect confirmed content, never author operational facts.
    content = grounding.protected_content or (
        ProtectedContent("BACKEND_RESULT", grounding.fallback_message),
    )
    if result.get("offer_action") == "CDM_ACCESS_REQUEST":
        content = (
            *content,
            ProtectedContent(
                "ACTION_OFFER",
                "Você pode solicitar por aqui: eu registro a solicitação para análise da governança do CDM.",
            ),
        )
    return replace(
        grounding,
        protected_content=content,
        fallback_message="\n\n".join(item.content for item in content),
        response_goal=(
            "Conecte brevemente o conteúdo confirmado usando somente as expressões permitidas. "
            "Não repita nem complemente o conteúdo protegido."
        ),
        allowed_wrappers=("",),
        forbidden_claims=(
            *grounding.forbidden_claims,
            "Não acrescente notificações, acompanhamento, contato futuro, técnico ou SLA.",
            "Não invente status, aprovação, criação, execução ou procedimentos.",
        ),
    )


def _ground_response(result, context, delta) -> ResponseGrounding:
    status = result.get("status")
    facts = list(_consolidated_facts(context))
    protected_content = ()

    allowed_values = frozenset(
        str(value)
        for value in (
            result.get("request_id"),
            result.get("state"),
            result.get("policy"),
        )
        if value is not None and str(value).strip()
    )

    forbidden_claims = (
        "Nao invente request_id.",
        "Nao afirme aprovacao sem confirmacao operacional.",
        "Nao afirme execucao sem confirmacao operacional.",
        "Nao afirme que acesso foi liberado sem confirmacao operacional.",
    )

    if status == "REQUESTS_LISTED":
        summary = result.get("request_summary") or {}
        items = summary.get("items") if isinstance(summary, dict) else None
        if not isinstance(items, list):
            raise ValueError("REQUESTS_LISTED requer resumo autoritativo.")
        facts.extend(
            f"solicitação confirmada: {item.get('request_id')} · {item.get('system')} · "
            f"{item.get('state_label')}"
            for item in items
            if isinstance(item, dict)
        )
        fallback = result.get("assistant_message")
        if not isinstance(fallback, str) or not fallback.strip():
            raise ValueError("REQUESTS_LISTED requer mensagem factual.")
        return ResponseGrounding(
            disposition=ConversationDisposition.REQUEST_STATUS,
            response_goal="Apresente somente o resumo autoritativo já fornecido.",
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(ProtectedContent("REQUEST_SUMMARY", fallback.strip()),),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message=fallback.strip(),
            allowed_operational_values=frozenset(
                str(value)
                for item in items
                if isinstance(item, dict)
                for value in (item.get("request_id"), item.get("system"), item.get("state_label"))
                if value is not None and str(value).strip()
            ),
            allowed_wrappers=("",),
        )

    if status == "SOCIAL":
        return ResponseGrounding(
            disposition=ConversationDisposition.SOCIAL,
            response_goal=(
                "Responda socialmente de forma breve e natural e convide a pessoa "
                "a contar o que precisa resolver em TI."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message="Oi! Como posso ajudar com TI?",
            allowed_operational_values=allowed_values,
        )

    if status == "NEEDS_CLARIFICATION":
        question = result.get("question")
        required_information = (question,) if isinstance(question, str) and question.strip() else ()
        return ResponseGrounding(
            disposition=ConversationDisposition.ASK_CLARIFICATION,
            response_goal=(
                "Reconheça naturalmente o contexto já entendido e peça somente "
                "a informação que ainda falta."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=required_information,
            fallback_message=(
                question
                if isinstance(question, str) and question.strip()
                else "Preciso de mais uma informação para continuar."
            ),
            allowed_operational_values=allowed_values,
        )

    state = result.get("state")
    policy = result.get("policy")
    request_id = result.get("request_id")

    if status == "DENIED_POLICY" or state == "DENIED_POLICY":
        if request_id:
            facts.append(f"request_id confirmado: {request_id}")
        if state:
            facts.append(f"estado confirmado: {state}")
        if policy:
            facts.append(f"política confirmada: {policy}")

        return ResponseGrounding(
            disposition=ConversationDisposition.DENY_BY_POLICY,
            response_goal=(
                "Explique de forma natural que a solicitação foi negada pela "
                "política confirmada pelo processo. Não sugira que o acesso foi liberado."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message=("Esse tipo de acesso não pode ser liberado por este atendimento."),
            allowed_operational_values=allowed_values,
        )

    if status == "REQUEST_CREATED" and state == "PENDING_APPROVAL":
        if request_id:
            facts.append(f"request_id confirmado: {request_id}")
        facts.append(f"estado confirmado: {state}")
        if policy:
            facts.append(f"política confirmada: {policy}")

        fallback = "A solicitação foi registrada e aguarda aprovação."
        if request_id:
            fallback = f"Sua solicitação {request_id} foi registrada e aguarda aprovação."

        return ResponseGrounding(
            disposition=ConversationDisposition.WAIT_FOR_APPROVAL,
            response_goal=(
                "Informe naturalmente que a solicitação foi registrada e que "
                "continua aguardando aprovação. Não afirme que foi aprovada."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message=fallback,
            allowed_operational_values=allowed_values,
        )

    if status == "REQUEST_CREATED":
        if request_id:
            facts.append(f"request_id confirmado: {request_id}")
        if state:
            facts.append(f"estado confirmado: {state}")
        if policy:
            facts.append(f"política confirmada: {policy}")

        fallback = "A solicitação foi registrada."
        if request_id:
            fallback = f"Sua solicitação {request_id} foi registrada."

        return ResponseGrounding(
            disposition=ConversationDisposition.CREATE_ACCESS_REQUEST,
            response_goal=(
                "Confirme somente que a solicitação foi criada e descreva apenas "
                "o estado confirmado pelo processo."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message=fallback,
            allowed_operational_values=allowed_values,
        )

    if status == "SUPPORT_HANDOFF_PENDING":
        handoff = result.get("support_handoff") or {}
        system = handoff.get("system")
        technician = handoff.get("technician") or {}
        technician_name = technician.get("name")

        if system:
            facts.append(f"sistema do handoff confirmado: {system}")
        if technician_name:
            facts.append(f"técnico confirmado: {technician_name}")

        return ResponseGrounding(
            disposition=ConversationDisposition.HANDOFF,
            response_goal=(
                "Explique naturalmente que o atendimento foi encaminhado ao suporte "
                "confirmado pelo processo e preserve o contexto já entendido."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message=("Encaminhei o atendimento para o suporte técnico responsável."),
            allowed_operational_values=allowed_values,
        )

    if status == "SUPPORT_RESOLVED":
        return ResponseGrounding(
            disposition=ConversationDisposition.ACKNOWLEDGE_RESOLUTION,
            response_goal=(
                "Reconheça brevemente que o problema foi resolvido conforme "
                "o estado confirmado pelo processo."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message="Ótimo, vou considerar este atendimento resolvido.",
            allowed_operational_values=allowed_values,
        )

    if status == "KNOWLEDGE_FOUND":
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("KNOWLEDGE_FOUND requer answer aprovado.")

        protected_items = [
            ProtectedContent(
                kind="APPROVED_PROCEDURE",
                content=answer,
            ),
        ]

        procedure_url = result.get("procedure_url")
        if isinstance(procedure_url, str) and procedure_url.strip():
            protected_items.append(
                ProtectedContent(
                    kind="OFFICIAL_URL",
                    content=procedure_url.strip(),
                )
            )

        protected_content = tuple(protected_items)
        knowledge_id = result.get("knowledge_id")
        if knowledge_id:
            facts.append(f"knowledge_id confirmado: {knowledge_id}")

        return ResponseGrounding(
            disposition=ConversationDisposition.ANSWER_WITH_APPROVED_KNOWLEDGE,
            response_goal=(
                "Introduza brevemente a orientacao aprovada e finalize de forma natural. "
                "O procedimento oficial e eventual link oficial serao apresentados "
                "literalmente entre a introducao e o encerramento."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=protected_content,
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message="\n\n".join(item.content for item in protected_content),
            allowed_operational_values=allowed_values,
        )

    if status == "OUT_OF_SCOPE":
        topic = result.get("understood_topic") or getattr(delta, "understood_topic", "")
        if topic:
            facts.append(f"Assunto entendido fora do escopo de TI: {topic}")

        return ResponseGrounding(
            disposition=ConversationDisposition.OUT_OF_SCOPE,
            response_goal=(
                "Reconheça naturalmente o assunto entendido, explique que ele está "
                "fora do papel de suporte de TI do Jup e redirecione a conversa para "
                "assuntos de TI. Não invente encaminhamento para técnico."
                " Não responda o conteúdo solicitado: nenhuma receita, placar, poema ou conselho."
                " Use no máximo duas frases curtas e acolhedoras: reconheça o tema e convide "
                "a trazer uma necessidade de TI. Evite explicações formais sobre restrições, "
                "infraestrutura, escopo operacional ou regras."
            ),
            verbosity="concise",
            facts=tuple(facts),
            protected_content=(),
            forbidden_claims=forbidden_claims,
            required_information=(),
            fallback_message=scope_redirect_fallback(topic),
            allowed_operational_values=allowed_values,
        )

    raise ValueError(f"Status ainda não mapeado pelo grounding: {status!r}")
