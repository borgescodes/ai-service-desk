from ai_service_desk.engine.learning_prevention import OpportunityEngine, PatternAggregator
from ai_service_desk.web.demo_runtime import DemoRuntime
from ai_service_desk.web.presentation import present_prevention, present_request, present_timeline


def _pending_request(runtime: DemoRuntime):
    result = runtime.send_message(
        "pedro-miranda",
        "Preciso de acesso ao CDM para solicitar materiais para uma revenda.",
    )
    request_id = result["request_id"]
    return (
        runtime.request_repository.get(request_id),
        runtime.request_repository.audit_for(request_id),
        runtime.routing_store.get(request_id),
    )


def test_present_request_uses_portuguese_state_label_and_explainable_confidence() -> None:
    runtime = DemoRuntime.create()
    try:
        record, audit, assignment = _pending_request(runtime)
        payload = present_request(
            record,
            audit,
            {"classification_confidence": 0.873},
            assignment=assignment,
        )

        assert payload["state"] == "PENDING_APPROVAL"
        assert payload["state_label"] == "Aguardando aprovação"
        assert payload["requester"] == {
            "name": "Fulano de Tal",
            "username": "fulano.tal",
            "email": "fulano.tal@juparana.com.br",
            "area": "Revenda - Matriz",
            "job_title": "Colaborador",
            "identity_source": "BACKEND_SESSION_PROVIDER",
        }
        assert payload["confidence"]["level"] == "HIGH"
        assert payload["confidence"]["label"] == "Alta"
        assert payload["confidence"]["percent"] is None
        assert payload["confidence"]["explanations"] == [
            {
                "code": "AREA_MATCH_REVENDA",
                "kind": "positive",
                "text": "Área de atuação compatível com Revenda.",
            },
            {
                "code": "PURPOSE_MATCH_MATERIAL_REQUEST",
                "kind": "positive",
                "text": "Finalidade de solicitação de materiais confirmada.",
            },
        ]
        assert "reason_code" not in payload["policy"]
    finally:
        runtime.close()


def test_present_request_never_invents_numeric_confidence() -> None:
    runtime = DemoRuntime.create()
    try:
        record, audit, assignment = _pending_request(runtime)
        payload = present_request(record, audit, {}, assignment=assignment)
        assert payload["confidence"]["level"] == "HIGH"
        assert payload["confidence"]["percent"] is None
    finally:
        runtime.close()


def test_present_timeline_contains_only_real_audit_events() -> None:
    runtime = DemoRuntime.create()
    try:
        record, audit, _ = _pending_request(runtime)
        timeline = present_timeline(audit)
        assert [item["event_type"] for item in timeline] == [event.event_type for event in audit]
        assert len(timeline) == len(audit)
        assert timeline[-1]["record_version"] == record.version
    finally:
        runtime.close()


def test_operational_presentation_exposes_routing_and_policy_evidence() -> None:
    runtime = DemoRuntime.create()
    try:
        record, audit, assignment = _pending_request(runtime)
        payload = present_request(
            record,
            audit,
            runtime.request_metadata[record.request_id],
            assignment=assignment,
            include_internal=True,
        )

        assert payload["routing"]["technician_id"] == "TECH-CDM"
        assert payload["routing"]["technician_name"] == "Técnico CDM"
        assert payload["policy"]["reason_code"] == record.latest_policy.reason_code
        assert payload["policy"]["policy_id"] == record.latest_policy.policy_id
    finally:
        runtime.close()


def test_present_prevention_is_allowlisted_and_explains_engine_output() -> None:
    runtime = DemoRuntime.create()
    try:
        opportunity = OpportunityEngine().generate(
            PatternAggregator.aggregate(runtime.outcome_store.snapshot())
        )[0]
        payload = present_prevention(opportunity)
        assert payload["opportunity_id"] == opportunity.opportunity_id
        assert payload["category"] == opportunity.category
        assert payload["occurrence_count"] == opportunity.occurrence_count
        assert payload["system"] == opportunity.key.system
        assert payload["intent"] == opportunity.key.intent
        assert payload["reason_codes"] == list(opportunity.reason_codes)
        assert str(opportunity.occurrence_count) in payload["explanation"]
        assert opportunity.category in payload["explanation_code"]
        assert "evidence_ids" not in payload
    finally:
        runtime.close()
