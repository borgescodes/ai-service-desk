from threading import RLock
from typing import Protocol

from ai_service_desk.engine.request_lifecycle import (
    ALLOWED_TRANSITIONS,
    AccessRequestRecord,
    AuditEvent,
    AuditEventValidationError,
    ConcurrencyConflictError,
    InvalidStateTransitionError,
    RecordInvariantError,
    RequestNotFoundError,
    validate_access_request_record,
    validate_audit_event,
    validate_expected_version,
)


class RequestRepository(Protocol):
    def allocate_request_id(self) -> str: ...
    def create(
        self, record: AccessRequestRecord, *, audit_events: tuple[AuditEvent, ...]
    ) -> AccessRequestRecord: ...
    def get(self, request_id: str) -> AccessRequestRecord: ...
    def save(
        self,
        record: AccessRequestRecord,
        *,
        expected_version: int,
        audit_events: tuple[AuditEvent, ...],
    ) -> AccessRequestRecord: ...
    def audit_for(self, request_id: str) -> tuple[AuditEvent, ...]: ...


def _record_invalid():
    raise RecordInvariantError(
        "RECORD_INVARIANT_INVALID", "Snapshot ou alteracao de campos invalida."
    )


def _audit_invalid():
    raise AuditEventValidationError("AUDIT_EVENT_INVALID", "Auditoria nao corresponde a transicao.")


def _validate_delta(current: AccessRequestRecord, record: AccessRequestRecord):
    if (current.state, record.state) not in ALLOWED_TRANSITIONS:
        raise InvalidStateTransitionError("INVALID_STATE_TRANSITION", "Transicao fora da matriz.")
    if record.version != current.version + 1:
        _record_invalid()
    if record.updated_at < current.updated_at:
        _record_invalid()
    for field in ("request_id", "context", "creation_policy", "confidence", "created_at"):
        if getattr(record, field) != getattr(current, field):
            _record_invalid()
    changing = {"version", "state", "updated_at"}
    if current.state == "PENDING_APPROVAL":
        changing |= {"decided_by", "decided_at"}
    if current.state == "APPROVED":
        changing.add("latest_policy")
        if record.state == "EXECUTING":
            changing.add("execution_started_at")
    if current.state == "EXECUTING":
        changing |= {"execution_finished_at", "execution_result_code", "execution_error_code"}
    for field in AccessRequestRecord.__dataclass_fields__:
        if field not in changing and getattr(current, field) != getattr(record, field):
            _record_invalid()


def _validate_events(record, events, current=None):
    if type(events) is not tuple or len(events) != 1:
        _audit_invalid()
    for event in events:
        validate_audit_event(event)
        if (
            event.request_id != record.request_id
            or event.record_version != record.version
            or event.to_state != record.state
            or event.from_state != (current.state if current else None)
            or event.occurred_at != record.updated_at
        ):
            _audit_invalid()
        if event.event_type in {
            "POLICY_REQUIRES_APPROVAL",
            "POLICY_DENIED_AT_CREATION",
            "POLICY_DENIED_BEFORE_EXECUTION",
            "EXECUTION_STARTED",
        }:
            if (event.policy_id, event.reason_code) != (
                record.latest_policy.policy_id,
                record.latest_policy.reason_code,
            ):
                _audit_invalid()
        if event.actor_type == "TECHNICIAN" and event.actor_id != record.decided_by:
            _audit_invalid()
        if (
            event.event_type == "EXECUTION_COMPLETED"
            and event.reason_code != record.execution_result_code
        ):
            _audit_invalid()
        if (
            event.event_type == "EXECUTION_FAILED"
            and event.reason_code != record.execution_error_code
        ):
            _audit_invalid()


class InMemoryRequestRepository:
    def __init__(self):
        self._lock = RLock()
        self._records: dict[str, AccessRequestRecord] = {}
        self._audit: dict[str, list[AuditEvent]] = {}
        self._next_id = 1

    def allocate_request_id(self) -> str:
        with self._lock:
            request_id = f"REQ-{self._next_id:06d}"
            self._next_id += 1
            return request_id

    def create(
        self, record: AccessRequestRecord, *, audit_events: tuple[AuditEvent, ...]
    ) -> AccessRequestRecord:
        with self._lock:
            validate_access_request_record(record)
            if (
                record.request_id in self._records
                or record.version != 1
                or record.state != "TRIAGED"
            ):
                _record_invalid()
            _validate_events(record, audit_events)
            self._records[record.request_id] = record
            self._audit[record.request_id] = list(audit_events)
            return record

    def get(self, request_id: str) -> AccessRequestRecord:
        with self._lock:
            if request_id not in self._records:
                raise RequestNotFoundError("REQUEST_NOT_FOUND", "Request inexistente.")
            return self._records[request_id]

    def save(
        self,
        record: AccessRequestRecord,
        *,
        expected_version: int,
        audit_events: tuple[AuditEvent, ...],
    ) -> AccessRequestRecord:
        validate_expected_version(expected_version)
        current = self.get(record.request_id)
        if current.version != expected_version:
            raise ConcurrencyConflictError("VERSION_CONFLICT", "Versao stale.")
        validate_access_request_record(record)
        _validate_delta(current, record)
        _validate_events(record, audit_events, current)
        self._before_final_cas()
        with self._lock:
            current = self.get(record.request_id)
            if current.version != expected_version:
                raise ConcurrencyConflictError("VERSION_CONFLICT", "Versao stale no CAS final.")
            previous = self._audit[record.request_id][-1].occurred_at
            for event in audit_events:
                if event.occurred_at < previous:
                    _audit_invalid()
                previous = event.occurred_at
            self._records[record.request_id] = record
            self._audit[record.request_id].extend(audit_events)
            return record

    def _before_final_cas(self) -> None:
        pass

    def audit_for(self, request_id: str) -> tuple[AuditEvent, ...]:
        with self._lock:
            self.get(request_id)
            return tuple(self._audit[request_id])
