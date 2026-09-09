from collections.abc import Mapping


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

_CONFIDENCE_LABELS = {"HIGH": "Alta", "LOW": "Baixa"}


def _iso(value):
    return value.isoformat() if value is not None else None


def _confidence(record, metadata: Mapping[str, object]) -> dict:
    raw = metadata.get("classification_confidence")
    percent = None
    if type(raw) in {int, float} and not isinstance(raw, bool) and 0 <= raw <= 1:
        percent = round(float(raw) * 100)
    return {
        "level": record.confidence.level,
        "label": _CONFIDENCE_LABELS[record.confidence.level],
        "percent": percent,
        "tone": "confidence",
    }


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
    metadata: Mapping[str, object],
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
            "area": record.context.requester.area,
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
