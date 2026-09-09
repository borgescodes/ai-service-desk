from datetime import UTC, datetime

from ai_service_desk.engine.request_lifecycle import (
    AccessRequestRecord,
    ConcurrencyConflictError,
    InvalidStateTransitionError,
    Phase8DomainError,
    validate_expected_version,
)
from ai_service_desk.engine.technician_authorization import TechnicianIdentity


class SelfDecisionError(Phase8DomainError):
    pass


class ApprovalService:
    def __init__(self, repository, lifecycle, registry, clock=None):
        self.repository = repository
        self.lifecycle = lifecycle
        self.registry = registry
        self.clock = clock if clock is not None else lambda: datetime.now(UTC)

    def _decide(self, request_id, technician, expected_version, *, approved):
        record = self.repository.get(request_id)
        validate_expected_version(expected_version)
        if expected_version != record.version:
            raise ConcurrencyConflictError("VERSION_CONFLICT", "Versao stale.")
        if record.state != "PENDING_APPROVAL":
            raise InvalidStateTransitionError(
                "INVALID_STATE_TRANSITION", "Request nao esta pendente."
            )
        self.registry.require_capability(technician, record.context.capability)
        requester = record.context.requester
        if any(
            getattr(technician, field).strip().casefold()
            == getattr(requester, field).strip().casefold()
            for field in ("username", "email")
        ):
            raise SelfDecisionError(
                "SELF_DECISION_NOT_ALLOWED", "Requester nao pode decidir o proprio request."
            )
        occurred_at = self.clock()
        transition = (
            self.lifecycle.transition_to_approved
            if approved
            else self.lifecycle.transition_to_rejected
        )
        return transition(
            record,
            technician.technician_id,
            expected_version=expected_version,
            occurred_at=occurred_at,
        )

    def approve(
        self, request_id: str, technician: TechnicianIdentity, *, expected_version: int
    ) -> AccessRequestRecord:
        return self._decide(request_id, technician, expected_version, approved=True)

    def reject(
        self, request_id: str, technician: TechnicianIdentity, *, expected_version: int
    ) -> AccessRequestRecord:
        return self._decide(request_id, technician, expected_version, approved=False)
