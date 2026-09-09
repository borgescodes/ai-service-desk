from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, NoReturn

from ai_service_desk.engine.access_request import (
    AccessRequestContext,
    AccessRequestValidationError,
    SessionIdentity,
    validate_access_request_context,
)
from ai_service_desk.engine.confidence import ConfidenceAssessment, assess_confidence
from ai_service_desk.engine.policy import (
    MACHINE_CODE_RE,
    POLICY_DECISIONS,
    PolicyDecision,
    PolicyEngine,
)

RequestState = Literal[
    "TRIAGED",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "DENIED_POLICY",
    "EXECUTING",
    "COMPLETED",
    "FAILED",
]
ActorType = Literal["SYSTEM", "TECHNICIAN"]

REQUEST_STATES: frozenset[str] = frozenset(
    {
        "TRIAGED",
        "PENDING_APPROVAL",
        "APPROVED",
        "REJECTED",
        "DENIED_POLICY",
        "EXECUTING",
        "COMPLETED",
        "FAILED",
    }
)
ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("TRIAGED", "PENDING_APPROVAL"),
        ("TRIAGED", "DENIED_POLICY"),
        ("PENDING_APPROVAL", "APPROVED"),
        ("PENDING_APPROVAL", "REJECTED"),
        ("APPROVED", "EXECUTING"),
        ("APPROVED", "DENIED_POLICY"),
        ("EXECUTING", "COMPLETED"),
        ("EXECUTING", "FAILED"),
    }
)

AUDIT_EVENT_TYPES = frozenset(
    {
        "REQUEST_CREATED",
        "POLICY_REQUIRES_APPROVAL",
        "POLICY_DENIED_AT_CREATION",
        "REQUEST_APPROVED",
        "REQUEST_REJECTED",
        "POLICY_DENIED_BEFORE_EXECUTION",
        "EXECUTION_STARTED",
        "EXECUTION_COMPLETED",
        "EXECUTION_FAILED",
    }
)


class Phase8DomainError(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class RequestNotFoundError(Phase8DomainError):
    pass


class InvalidStateTransitionError(Phase8DomainError):
    pass


class ExpectedVersionValidationError(Phase8DomainError):
    pass


class ConcurrencyConflictError(Phase8DomainError):
    pass


class RecordInvariantError(Phase8DomainError):
    pass


class AuditEventValidationError(Phase8DomainError):
    pass


@dataclass(frozen=True)
class AccessRequestRecord:
    request_id: str
    version: int
    state: RequestState
    context: AccessRequestContext
    creation_policy: PolicyDecision
    latest_policy: PolicyDecision
    confidence: ConfidenceAssessment
    created_at: datetime
    updated_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    execution_started_at: datetime | None
    execution_finished_at: datetime | None
    execution_result_code: str | None
    execution_error_code: str | None


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    event_type: str
    actor_type: ActorType
    actor_id: str
    from_state: RequestState | None
    to_state: RequestState
    record_version: int
    reason_code: str
    policy_id: str | None
    occurred_at: datetime


def validate_expected_version(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ExpectedVersionValidationError(
            "EXPECTED_VERSION_INVALID",
            "expected_version deve ser inteiro positivo exato.",
        )
    return value


def _invalid_record(message: str) -> NoReturn:
    raise RecordInvariantError("RECORD_INVARIANT_INVALID", message)


def _invalid_audit(message: str) -> NoReturn:
    raise AuditEventValidationError("AUDIT_EVENT_INVALID", message)


def _is_required_text(value: object, limit: int = 500) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def _is_machine_code(value: object) -> bool:
    return isinstance(value, str) and MACHINE_CODE_RE.fullmatch(value) is not None


def _is_aware_datetime(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _validate_policy_decision(policy: object) -> None:
    if type(policy) is not PolicyDecision:
        _invalid_record("policy deve ser PolicyDecision imutavel exata.")
    if type(policy.decision) is not str or policy.decision not in POLICY_DECISIONS:
        _invalid_record("decision da policy fora do contrato fechado.")
    if not _is_machine_code(policy.policy_id):
        _invalid_record("policy_id deve ser codigo simbolico valido.")
    if not _is_machine_code(policy.reason_code):
        _invalid_record("reason_code da policy deve ser codigo simbolico valido.")
    if not _is_required_text(policy.reason):
        _invalid_record("reason da policy deve ser texto valido.")


def _validate_confidence(confidence: object) -> None:
    if type(confidence) is not ConfidenceAssessment:
        _invalid_record("confidence deve ser ConfidenceAssessment imutavel exata.")
    if type(confidence.level) is not str or confidence.level not in {"HIGH", "LOW"}:
        _invalid_record("confidence.level fora do contrato fechado.")
    if type(confidence.reason_codes) is not tuple or not confidence.reason_codes:
        _invalid_record("confidence.reason_codes deve ser tuple nao vazio.")
    if not all(_is_machine_code(code) for code in confidence.reason_codes):
        _invalid_record("confidence.reason_codes contem codigo invalido.")


def _validate_record_timestamps(record: AccessRequestRecord) -> None:
    if not _is_aware_datetime(record.created_at):
        _invalid_record("created_at deve ser datetime timezone-aware.")
    if not _is_aware_datetime(record.updated_at):
        _invalid_record("updated_at deve ser datetime timezone-aware.")
    for field_name in (
        "decided_at",
        "execution_started_at",
        "execution_finished_at",
    ):
        value = getattr(record, field_name)
        if value is not None and not _is_aware_datetime(value):
            _invalid_record(f"{field_name} deve ser datetime timezone-aware.")
    for earlier, later in (
        (record.created_at, record.updated_at),
        (record.created_at, record.decided_at),
        (record.decided_at, record.execution_started_at),
        (record.execution_started_at, record.execution_finished_at),
    ):
        if earlier is not None and later is not None and earlier > later:
            _invalid_record("Cronologia do record deve ser nao decrescente.")


def _validate_record_state_fields(record: AccessRequestRecord) -> None:
    has_decider = record.decided_by is not None
    has_decided_at = record.decided_at is not None
    if has_decider != has_decided_at:
        _invalid_record("decided_by e decided_at devem formar um par completo.")

    has_started = record.execution_started_at is not None
    has_finished = record.execution_finished_at is not None
    has_result = record.execution_result_code is not None
    has_error = record.execution_error_code is not None
    decision_pair = has_decider and has_decided_at

    if record.state in {"TRIAGED", "PENDING_APPROVAL"}:
        if decision_pair or has_started or has_finished or has_result or has_error:
            _invalid_record("state anterior a decisao contem campos posteriores preenchidos.")
        if record.latest_policy != record.creation_policy:
            _invalid_record("latest_policy mudou antes da revalidacao de execucao.")
        if (
            record.state == "PENDING_APPROVAL"
            and record.creation_policy.decision != "REQUIRE_APPROVAL"
        ):
            _invalid_record("PENDING_APPROVAL exige creation_policy REQUIRE_APPROVAL.")
        return

    if record.state in {"APPROVED", "REJECTED"}:
        if not decision_pair or has_started or has_finished or has_result or has_error:
            _invalid_record("state de decisao humana possui campos incoerentes.")
        if record.creation_policy.decision != "REQUIRE_APPROVAL":
            _invalid_record("decisao humana exige creation_policy REQUIRE_APPROVAL.")
        if record.latest_policy != record.creation_policy:
            _invalid_record("latest_policy mudou antes da revalidacao de execucao.")
        return

    if record.state == "DENIED_POLICY":
        if has_started or has_finished or has_result or has_error:
            _invalid_record("DENIED_POLICY nao aceita campos de execucao.")
        if record.latest_policy.decision != "DENY":
            _invalid_record("DENIED_POLICY exige latest_policy DENY.")
        denied_at_creation = record.creation_policy.decision == "DENY"
        if denied_at_creation:
            if decision_pair or record.latest_policy != record.creation_policy:
                _invalid_record("negacao na criacao nao aceita decisao humana ou policy alterada.")
        elif record.creation_policy.decision == "REQUIRE_APPROVAL":
            if not decision_pair:
                _invalid_record("negacao na revalidacao deve preservar a decisao humana.")
        else:
            _invalid_record("creation_policy fora do contrato fechado.")
        return

    if not decision_pair or not has_started:
        _invalid_record("state de execucao exige decisao humana e execution_started_at.")
    if record.creation_policy.decision != "REQUIRE_APPROVAL":
        _invalid_record("execucao exige creation_policy REQUIRE_APPROVAL.")
    if record.latest_policy.decision != "REQUIRE_APPROVAL":
        _invalid_record("execucao exige latest_policy REQUIRE_APPROVAL.")

    if record.state == "EXECUTING":
        if has_finished or has_result or has_error:
            _invalid_record("EXECUTING nao aceita campos de conclusao.")
    elif record.state == "COMPLETED":
        if not has_finished or not has_result or has_error:
            _invalid_record("COMPLETED exige finalizacao sem execution_error_code.")
    elif record.state == "FAILED":
        if not has_finished or not has_error:
            _invalid_record("FAILED exige finalizacao e execution_error_code.")


def validate_access_request_record(record: AccessRequestRecord) -> None:
    if type(record) is not AccessRequestRecord:
        _invalid_record("record deve ser AccessRequestRecord imutavel exato.")
    if not _is_required_text(record.request_id, 120):
        _invalid_record("request_id deve ser texto nao vazio.")
    if type(record.version) is not int or record.version <= 0:
        _invalid_record("version deve ser inteiro positivo exato.")
    if type(record.state) is not str or record.state not in REQUEST_STATES:
        _invalid_record("state fora do contrato fechado.")
    if type(record.context) is not AccessRequestContext:
        _invalid_record("context deve ser AccessRequestContext imutavel exato.")
    if type(record.context.requester) is not SessionIdentity:
        _invalid_record("context.requester deve ser SessionIdentity imutavel exata.")
    try:
        validate_access_request_context(record.context)
    except AccessRequestValidationError as exc:
        _invalid_record(str(exc))
    _validate_policy_decision(record.creation_policy)
    _validate_policy_decision(record.latest_policy)
    _validate_confidence(record.confidence)
    _validate_record_timestamps(record)
    if record.decided_by is not None and not _is_required_text(record.decided_by, 120):
        _invalid_record("decided_by deve ser texto nao vazio quando preenchido.")
    if record.execution_result_code is not None and not _is_machine_code(
        record.execution_result_code
    ):
        _invalid_record("execution_result_code deve ser codigo simbolico valido.")
    if record.execution_error_code is not None and not _is_machine_code(
        record.execution_error_code
    ):
        _invalid_record("execution_error_code deve ser codigo simbolico valido.")
    _validate_record_state_fields(record)


_AUDIT_SHAPES: dict[str, tuple[str | None, str, int]] = {
    "REQUEST_CREATED": (None, "TRIAGED", 1),
    "POLICY_REQUIRES_APPROVAL": ("TRIAGED", "PENDING_APPROVAL", 2),
    "POLICY_DENIED_AT_CREATION": ("TRIAGED", "DENIED_POLICY", 2),
    "REQUEST_APPROVED": ("PENDING_APPROVAL", "APPROVED", 3),
    "REQUEST_REJECTED": ("PENDING_APPROVAL", "REJECTED", 3),
    "POLICY_DENIED_BEFORE_EXECUTION": ("APPROVED", "DENIED_POLICY", 4),
    "EXECUTION_STARTED": ("APPROVED", "EXECUTING", 4),
    "EXECUTION_COMPLETED": ("EXECUTING", "COMPLETED", 5),
    "EXECUTION_FAILED": ("EXECUTING", "FAILED", 5),
}
_TECHNICIAN_EVENTS = {"REQUEST_APPROVED", "REQUEST_REJECTED"}
_POLICY_EVENTS = {
    "POLICY_REQUIRES_APPROVAL",
    "POLICY_DENIED_AT_CREATION",
    "POLICY_DENIED_BEFORE_EXECUTION",
    "EXECUTION_STARTED",
}
_FIXED_EVENT_REASONS = {
    "REQUEST_CREATED": "REQUEST_CREATED",
    "REQUEST_APPROVED": "APPROVED_BY_AUTHORIZED_TECHNICIAN",
    "REQUEST_REJECTED": "REJECTED_BY_AUTHORIZED_TECHNICIAN",
}


def validate_audit_event(event: AuditEvent) -> None:
    if type(event) is not AuditEvent:
        _invalid_audit("event deve ser AuditEvent imutavel exato.")
    if not _is_required_text(event.request_id, 120):
        _invalid_audit("request_id deve ser texto nao vazio.")
    if type(event.event_type) is not str or event.event_type not in AUDIT_EVENT_TYPES:
        _invalid_audit("event_type fora do contrato fechado.")
    if type(event.actor_type) is not str or event.actor_type not in {"SYSTEM", "TECHNICIAN"}:
        _invalid_audit("actor_type fora do contrato fechado.")
    if not _is_required_text(event.actor_id, 120):
        _invalid_audit("actor_id deve ser texto nao vazio.")
    if event.from_state is not None and (
        type(event.from_state) is not str or event.from_state not in REQUEST_STATES
    ):
        _invalid_audit("from_state fora do contrato fechado.")
    if type(event.to_state) is not str or event.to_state not in REQUEST_STATES:
        _invalid_audit("to_state fora do contrato fechado.")
    if type(event.record_version) is not int or event.record_version <= 0:
        _invalid_audit("record_version deve ser inteiro positivo exato.")
    if not _is_machine_code(event.reason_code):
        _invalid_audit("reason_code deve ser codigo simbolico valido.")
    if event.policy_id is not None and not _is_machine_code(event.policy_id):
        _invalid_audit("policy_id deve ser codigo simbolico valido quando preenchido.")
    if not _is_aware_datetime(event.occurred_at):
        _invalid_audit("occurred_at deve ser datetime timezone-aware.")

    expected_from, expected_to, expected_version = _AUDIT_SHAPES[event.event_type]
    if (event.from_state, event.to_state, event.record_version) != (
        expected_from,
        expected_to,
        expected_version,
    ):
        _invalid_audit("evento nao corresponde ao state ou record_version canonico.")

    is_technician_event = event.event_type in _TECHNICIAN_EVENTS
    if is_technician_event:
        if event.actor_type != "TECHNICIAN" or event.actor_id == "SYSTEM":
            _invalid_audit("evento de decisao exige actor TECHNICIAN confiavel.")
    elif event.actor_type != "SYSTEM" or event.actor_id != "SYSTEM":
        _invalid_audit("evento automatico exige actor SYSTEM.")

    if event.event_type in _POLICY_EVENTS:
        if event.policy_id is None:
            _invalid_audit("evento de policy exige policy_id.")
    elif event.policy_id is not None:
        _invalid_audit("evento sem policy nao aceita policy_id.")

    fixed_reason = _FIXED_EVENT_REASONS.get(event.event_type)
    if fixed_reason is not None and event.reason_code != fixed_reason:
        _invalid_audit("reason_code nao corresponde ao evento canonico.")


class RequestLifecycleService:
    def __init__(self, repository, policy_engine=None, clock=None):
        self.repository = repository
        self.policy_engine = policy_engine if policy_engine is not None else PolicyEngine()
        self.clock = clock if clock is not None else lambda: datetime.now(UTC)

    def create_request(self, context: AccessRequestContext) -> AccessRequestRecord:
        validate_access_request_context(context)
        policy = self.policy_engine.evaluate(context)
        _validate_policy_decision(policy)
        confidence = assess_confidence(context)
        initial_timestamp = self.clock()
        if not _is_aware_datetime(initial_timestamp):
            _invalid_record("Clock deve retornar datetime timezone-aware.")
        record = AccessRequestRecord(
            request_id=self.repository.allocate_request_id(),
            version=1,
            state="TRIAGED",
            context=context,
            creation_policy=policy,
            latest_policy=policy,
            confidence=confidence,
            created_at=initial_timestamp,
            updated_at=initial_timestamp,
            decided_by=None,
            decided_at=None,
            execution_started_at=None,
            execution_finished_at=None,
            execution_result_code=None,
            execution_error_code=None,
        )
        event = AuditEvent(
            record.request_id,
            "REQUEST_CREATED",
            "SYSTEM",
            "SYSTEM",
            None,
            "TRIAGED",
            1,
            "REQUEST_CREATED",
            None,
            initial_timestamp,
        )
        record = self.repository.create(record, audit_events=(event,))
        if policy.decision == "DENY":
            return self.transition_to_denied_policy(
                record, policy, expected_version=1, occurred_at=initial_timestamp
            )
        return self.transition_to_pending_approval(
            record, expected_version=1, occurred_at=initial_timestamp
        )

    def _transition(
        self,
        record,
        target,
        event_type,
        reason_code,
        *,
        expected_version,
        occurred_at,
        policy_id=None,
        actor_id="SYSTEM",
        **changes,
    ):
        validate_expected_version(expected_version)
        if expected_version != record.version:
            raise ConcurrencyConflictError("VERSION_CONFLICT", "Versao stale.")
        if (record.state, target) not in ALLOWED_TRANSITIONS:
            raise InvalidStateTransitionError(
                "INVALID_STATE_TRANSITION", "Transicao fora da matriz."
            )
        updated = replace(
            record, state=target, version=record.version + 1, updated_at=occurred_at, **changes
        )
        validate_access_request_record(updated)
        actor_type = "TECHNICIAN" if event_type in _TECHNICIAN_EVENTS else "SYSTEM"
        event = AuditEvent(
            record.request_id,
            event_type,
            actor_type,
            actor_id,
            record.state,
            target,
            updated.version,
            reason_code,
            policy_id,
            occurred_at,
        )
        return self.repository.save(
            updated, expected_version=expected_version, audit_events=(event,)
        )

    def transition_to_pending_approval(
        self, record: AccessRequestRecord, *, expected_version: int, occurred_at: datetime
    ) -> AccessRequestRecord:
        return self._transition(
            record,
            "PENDING_APPROVAL",
            "POLICY_REQUIRES_APPROVAL",
            record.creation_policy.reason_code,
            expected_version=expected_version,
            occurred_at=occurred_at,
            policy_id=record.creation_policy.policy_id,
        )

    def transition_to_denied_policy(
        self,
        record: AccessRequestRecord,
        policy: PolicyDecision,
        *,
        expected_version: int,
        occurred_at: datetime,
    ) -> AccessRequestRecord:
        _validate_policy_decision(policy)
        event_type = (
            "POLICY_DENIED_AT_CREATION"
            if record.state == "TRIAGED"
            else "POLICY_DENIED_BEFORE_EXECUTION"
        )
        return self._transition(
            record,
            "DENIED_POLICY",
            event_type,
            policy.reason_code,
            expected_version=expected_version,
            occurred_at=occurred_at,
            policy_id=policy.policy_id,
            latest_policy=policy,
        )

    def transition_to_approved(
        self,
        record: AccessRequestRecord,
        technician_id: str,
        *,
        expected_version: int,
        occurred_at: datetime,
    ) -> AccessRequestRecord:
        return self._transition(
            record,
            "APPROVED",
            "REQUEST_APPROVED",
            "APPROVED_BY_AUTHORIZED_TECHNICIAN",
            expected_version=expected_version,
            occurred_at=occurred_at,
            actor_id=technician_id,
            decided_by=technician_id,
            decided_at=occurred_at,
        )

    def transition_to_rejected(
        self,
        record: AccessRequestRecord,
        technician_id: str,
        *,
        expected_version: int,
        occurred_at: datetime,
    ) -> AccessRequestRecord:
        return self._transition(
            record,
            "REJECTED",
            "REQUEST_REJECTED",
            "REJECTED_BY_AUTHORIZED_TECHNICIAN",
            expected_version=expected_version,
            occurred_at=occurred_at,
            actor_id=technician_id,
            decided_by=technician_id,
            decided_at=occurred_at,
        )

    def transition_to_executing(
        self,
        record: AccessRequestRecord,
        policy: PolicyDecision,
        *,
        expected_version: int,
        occurred_at: datetime,
    ) -> AccessRequestRecord:
        _validate_policy_decision(policy)
        return self._transition(
            record,
            "EXECUTING",
            "EXECUTION_STARTED",
            policy.reason_code,
            expected_version=expected_version,
            occurred_at=occurred_at,
            policy_id=policy.policy_id,
            latest_policy=policy,
            execution_started_at=occurred_at,
        )

    def transition_to_completed(
        self,
        record: AccessRequestRecord,
        result_code: str,
        *,
        expected_version: int,
        occurred_at: datetime,
    ) -> AccessRequestRecord:
        return self._transition(
            record,
            "COMPLETED",
            "EXECUTION_COMPLETED",
            result_code,
            expected_version=expected_version,
            occurred_at=occurred_at,
            execution_result_code=result_code,
            execution_finished_at=occurred_at,
        )

    def transition_to_failed(
        self,
        record: AccessRequestRecord,
        error_code: str,
        *,
        expected_version: int,
        occurred_at: datetime,
        result_code: str | None = None,
    ) -> AccessRequestRecord:
        return self._transition(
            record,
            "FAILED",
            "EXECUTION_FAILED",
            error_code,
            expected_version=expected_version,
            occurred_at=occurred_at,
            execution_error_code=error_code,
            execution_result_code=result_code,
            execution_finished_at=occurred_at,
        )
