_STATE_LABELS = {
    "TRIAGED": "Triada",
    "PENDING_APPROVAL": "Aguardando aprovação",
    "APPROVED": "Aprovada",
    "REJECTED": "Rejeitada",
    "DENIED_POLICY": "Bloqueada por política",
    "EXECUTING": "Em execução",
    "COMPLETED": "Concluída",
    "FAILED": "Falhou",
}

_EVENT_LABELS = {
    "REQUEST_CREATED": "Solicitação criada",
    "POLICY_REQUIRES_APPROVAL": "Aprovação necessária",
    "POLICY_DENIED_AT_CREATION": "Bloqueada por política",
    "REQUEST_APPROVED": "Solicitação aprovada",
    "REQUEST_REJECTED": "Solicitação rejeitada",
    "POLICY_DENIED_BEFORE_EXECUTION": "Execução bloqueada por política",
    "EXECUTION_STARTED": "Execução iniciada",
    "EXECUTION_COMPLETED": "Execução concluída",
    "EXECUTION_FAILED": "Execução falhou",
}

_CONFIDENCE_LABELS = {"HIGH": "Alta", "MEDIUM": "Média", "LOW": "Baixa"}
_CONFIDENCE_EXPLANATIONS = {
    "IDENTITY_CONFIRMED": (
        "positive",
        "Identidade confirmada pelo backend/session provider.",
    ),
    "AREA_MATCH_REVENDA": (
        "positive",
        "Área de atuação compatível com Revenda.",
    ),
    "AREA_OUTSIDE_REVENDA": (
        "conflict",
        "Área de atuação não corresponde ao contexto esperado de Revenda.",
    ),
    "AREA_SYSTEM_MISMATCH": (
        "conflict",
        "Acesso solicitado não possui coerência conhecida com a área de atuação.",
    ),
    "PURPOSE_MATCH_MATERIAL_REQUEST": (
        "positive",
        "Finalidade de solicitação de materiais confirmada.",
    ),
    "PURPOSE_NOT_CONFIRMED": (
        "missing",
        "Finalidade operacional ainda não foi confirmada.",
    ),
    "CONTEXT_INSUFFICIENT": (
        "missing",
        "Contexto insuficiente para elevar a confiança.",
    ),
    "CONTEXT_NOT_CDM_ACCESS_REQUEST": (
        "conflict",
        "O contexto não corresponde a uma solicitação controlada de acesso ao CDM.",
    ),
}

_PREVENTION_CATEGORY_LABELS = {
    "KNOWLEDGE_GAP": "Lacuna de conhecimento",
    "PLAYBOOK_GAP": "Lacuna de playbook",
    "HUMAN_DEPENDENCY": "Dependência humana",
    "AUTOMATION_CANDIDATE": "Candidato à automação",
    "PREVENTION_CANDIDATE": "Candidato à prevenção",
    "EXECUTION_RELIABILITY_ISSUE": "Confiabilidade de execução",
}


def _iso(value):
    return value.isoformat() if value is not None else None


def present_confidence(assessment) -> dict:
    explanations = []
    for code in assessment.reason_codes:
        kind, text = _CONFIDENCE_EXPLANATIONS.get(
            code,
            ("missing", "Evidência registrada pelo backend sem descrição pública."),
        )
        explanations.append({"code": code, "kind": kind, "text": text})
    return {
        "level": assessment.level,
        "label": _CONFIDENCE_LABELS[assessment.level],
        "percent": None,
        "tone": "confidence",
        "explanations": explanations,
    }


def _confidence(record, metadata: dict[str, object]) -> dict:
    # Percentuais de classificação do LLM não representam confiança de negócio.
    # A UI explica somente o assessment calculado pelo backend.
    _ = metadata
    return present_confidence(record.confidence)


def present_timeline(events) -> list[dict]:
    return [
        {
            "event_type": event.event_type,
            "label": _EVENT_LABELS.get(event.event_type, event.event_type),
            "from_state": event.from_state,
            "to_state": event.to_state,
            "record_version": event.record_version,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "occurred_at": _iso(event.occurred_at),
        }
        for event in events
    ]


def present_request(
    record,
    audit,
    metadata: dict[str, object],
    *,
    assignment=None,
    include_internal: bool = False,
) -> dict:
    policy = {
        "decision": record.latest_policy.decision,
        "requires_approval": record.latest_policy.decision == "REQUIRE_APPROVAL",
    }
    if include_internal:
        policy.update(
            {
                "policy_id": record.latest_policy.policy_id,
                "reason_code": record.latest_policy.reason_code,
                "reason": record.latest_policy.reason,
            }
        )

    routing = None
    if assignment is not None:
        routing = {
            "technician_id": assignment.technician.technician_id,
            "technician_name": assignment.technician.name,
            "system": assignment.system,
            "capability": assignment.capability,
        }

    return {
        "request_id": record.request_id,
        "version": record.version,
        "state": record.state,
        "state_label": _STATE_LABELS[record.state],
        "requester": {
            "name": record.context.requester.name,
            "username": record.context.requester.username,
            "email": record.context.requester.email,
            "area": record.context.requester.area,
            "identity_source": "BACKEND_SESSION_PROVIDER",
        },
        "system": record.context.system,
        "intent": record.context.intent,
        "requested_role": record.context.requested_role,
        "purpose": record.context.purpose,
        "capability": record.context.capability,
        "knowledge_id": record.context.knowledge_id,
        "playbook_id": record.context.playbook_id,
        "playbook_version": record.context.playbook_version,
        "confidence": _confidence(record, metadata),
        "policy": policy,
        "routing": routing,
        "timeline": present_timeline(audit),
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
        "decided_by": record.decided_by,
        "decided_at": _iso(record.decided_at),
        "execution_started_at": _iso(record.execution_started_at),
        "execution_finished_at": _iso(record.execution_finished_at),
        "execution_result_code": record.execution_result_code,
        "execution_error_code": record.execution_error_code,
    }


def present_prevention(opportunity) -> dict:
    key = opportunity.key
    category_label = _PREVENTION_CATEGORY_LABELS[opportunity.category]
    explanation = (
        f"O engine F11 identificou {opportunity.occurrence_count} ocorrências recorrentes "
        f"de {key.intent} em {key.system}"
    )
    if key.area:
        explanation += f" na área {key.area}"
    explanation += f" e classificou o padrão como {category_label.casefold()}."
    return {
        "opportunity_id": opportunity.opportunity_id,
        "category": opportunity.category,
        "category_label": category_label,
        "occurrence_count": opportunity.occurrence_count,
        "system": key.system,
        "intent": key.intent,
        "capability": key.capability,
        "area": key.area,
        "reason_codes": list(opportunity.reason_codes),
        "explanation": explanation,
        "explanation_code": f"F11_{opportunity.category}",
    }
