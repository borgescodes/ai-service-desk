from dataclasses import replace
from datetime import UTC, datetime

from ai_service_desk.engine.access_request import AccessRequestContext, SessionIdentity
from ai_service_desk.engine.confidence import ConfidenceAssessment
from ai_service_desk.engine.policy import PolicyDecision, PolicyDecisionValue
from ai_service_desk.engine.request_lifecycle import AccessRequestRecord, RequestState

DEFAULT_TIMESTAMP = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def make_context(**changes: object) -> AccessRequestContext:
    context = AccessRequestContext(
        requester=SessionIdentity(
            username="synthetic.requester",
            name="Synthetic Requester",
            email="synthetic.requester@example.invalid",
            area="Revenda Sintetica",
        ),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-PHASE8",
        playbook_id="PB-SYN-PHASE8",
        playbook_version=1,
        step_id="STEP-SYN-PHASE8",
        capability="CDM_ACCESS_REQUEST",
    )
    return replace(context, **changes)


def make_policy_decision(
    decision: PolicyDecisionValue = "REQUIRE_APPROVAL",
    **changes: object,
) -> PolicyDecision:
    policy = PolicyDecision(
        decision=decision,
        policy_id="SYNTHETIC_ACCESS_POLICY",
        reason_code=(
            "SYNTHETIC_REQUIRES_APPROVAL"
            if decision == "REQUIRE_APPROVAL"
            else "SYNTHETIC_ACCESS_DENIED"
        ),
        reason="Synthetic Phase 8 policy decision.",
    )
    return replace(policy, **changes)


def make_record(
    state: RequestState = "TRIAGED",
    **changes: object,
) -> AccessRequestRecord:
    decision_fields = {
        "decided_by": "TECH-SYNTHETIC",
        "decided_at": DEFAULT_TIMESTAMP,
    }
    execution_fields = {
        **decision_fields,
        "execution_started_at": DEFAULT_TIMESTAMP,
    }
    terminal_execution_fields = {
        **execution_fields,
        "execution_finished_at": DEFAULT_TIMESTAMP,
    }
    fields_by_state: dict[RequestState, dict[str, object]] = {
        "TRIAGED": {},
        "PENDING_APPROVAL": {},
        "APPROVED": decision_fields,
        "REJECTED": decision_fields,
        "DENIED_POLICY": {},
        "EXECUTING": execution_fields,
        "COMPLETED": {
            **terminal_execution_fields,
            "execution_result_code": "EXECUTION_SUCCEEDED",
        },
        "FAILED": {
            **terminal_execution_fields,
            "execution_error_code": "EXECUTOR_EXCEPTION",
        },
    }
    policy = make_policy_decision("DENY" if state == "DENIED_POLICY" else "REQUIRE_APPROVAL")
    record = AccessRequestRecord(
        request_id="REQ-000001",
        version=1,
        state=state,
        context=make_context(),
        creation_policy=policy,
        latest_policy=policy,
        confidence=ConfidenceAssessment(
            level="HIGH",
            reason_codes=("AREA_MATCH_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST"),
        ),
        created_at=DEFAULT_TIMESTAMP,
        updated_at=DEFAULT_TIMESTAMP,
        decided_by=None,
        decided_at=None,
        execution_started_at=None,
        execution_finished_at=None,
        execution_result_code=None,
        execution_error_code=None,
    )
    return replace(record, **(fields_by_state.get(state, {}) | changes))


class FixedClock:
    def __init__(self, *timestamps: datetime):
        self._timestamps = timestamps or (DEFAULT_TIMESTAMP,)
        self.calls = 0

    def __call__(self) -> datetime:
        if self.calls >= len(self._timestamps):
            raise AssertionError("FixedClock recebeu mais chamadas que timestamps configurados.")
        timestamp = self._timestamps[self.calls]
        self.calls += 1
        return timestamp
