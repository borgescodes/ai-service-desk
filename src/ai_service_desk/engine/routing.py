from dataclasses import dataclass
from threading import RLock

from ai_service_desk.engine.policy import MACHINE_CODE_RE
from ai_service_desk.engine.request_lifecycle import (
    AccessRequestRecord,
    RequestNotFoundError,
    validate_access_request_record,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationError,
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
)


class Phase10RoutingError(ValueError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class RoutingRuleConfigurationError(Phase10RoutingError):
    pass


class RouteNotFoundError(Phase10RoutingError):
    pass


class RoutingAssignmentValidationError(Phase10RoutingError):
    pass


class RoutingAssignmentNotFoundError(Phase10RoutingError):
    pass


class RoutingAssignmentConflictError(Phase10RoutingError):
    pass


class RoutingStateError(Phase10RoutingError):
    pass


class RoutingQueueConsistencyError(Phase10RoutingError):
    pass


@dataclass(frozen=True)
class RoutingRule:
    system: str
    capability: str
    technician: TechnicianIdentity


@dataclass(frozen=True)
class RoutingAssignment:
    request_id: str
    system: str
    capability: str
    technician: TechnicianIdentity


@dataclass(frozen=True)
class ApprovalQueueItem:
    request: AccessRequestRecord
    assignment: RoutingAssignment


def _machine_code(value: object) -> bool:
    return isinstance(value, str) and MACHINE_CODE_RE.fullmatch(value) is not None


def _identity_valid(identity: object) -> bool:
    if type(identity) is not TechnicianIdentity:
        return False
    return all(
        isinstance(value, str) and bool(value.strip()) and len(value) <= limit
        for value, limit in (
            (identity.technician_id, 120),
            (identity.username, 120),
            (identity.name, 180),
            (identity.email, 320),
        )
    )


def _validate_rule(rule: object) -> RoutingRule:
    if (
        type(rule) is not RoutingRule
        or not _machine_code(rule.system)
        or not _machine_code(rule.capability)
        or not _identity_valid(rule.technician)
    ):
        raise RoutingRuleConfigurationError("ROUTING_RULE_INVALID", "Regra de routing invalida.")
    return rule


def _validate_assignment(assignment: object) -> RoutingAssignment:
    if (
        type(assignment) is not RoutingAssignment
        or not isinstance(assignment.request_id, str)
        or not assignment.request_id.strip()
        or len(assignment.request_id) > 120
        or not _machine_code(assignment.system)
        or not _machine_code(assignment.capability)
        or not _identity_valid(assignment.technician)
    ):
        raise RoutingAssignmentValidationError(
            "ROUTING_ASSIGNMENT_INVALID", "Assignment de routing invalido."
        )
    return assignment


class RoutingRegistry:
    def __init__(
        self,
        rules: list[RoutingRule] | tuple[RoutingRule, ...],
        authorization_registry: TechnicianAuthorizationRegistry,
    ):
        if not isinstance(rules, list | tuple) or not isinstance(
            authorization_registry, TechnicianAuthorizationRegistry
        ):
            raise RoutingRuleConfigurationError(
                "ROUTING_RULE_INVALID", "Configuracao de routing invalida."
            )

        validated: list[RoutingRule] = []
        for candidate in rules:
            rule = _validate_rule(candidate)
            try:
                authorization_registry.require_capability(rule.technician, rule.capability)
            except TechnicianAuthorizationError as exc:
                raise RoutingRuleConfigurationError(
                    "ROUTING_TECHNICIAN_NOT_AUTHORIZED",
                    "Tecnico da rota nao possui a capability exigida.",
                ) from exc
            validated.append(rule)

        index: dict[tuple[str, str], RoutingRule] = {}
        for rule in validated:
            key = (rule.system, rule.capability)
            if key in index:
                raise RoutingRuleConfigurationError(
                    "ROUTING_RULE_CONFLICT", "Duas regras possuem a mesma chave de routing."
                )
            index[key] = rule
        self._rules = index

    def resolve(self, system: str, capability: str) -> TechnicianIdentity:
        rule = self._rules.get((system, capability))
        if rule is None:
            raise RouteNotFoundError("ROUTE_NOT_FOUND", "Nenhuma rota exata configurada.")
        return rule.technician


class InMemoryRoutingAssignmentStore:
    def __init__(self):
        self._lock = RLock()
        self._assignments: dict[str, RoutingAssignment] = {}

    def assign(self, assignment: RoutingAssignment) -> RoutingAssignment:
        value = _validate_assignment(assignment)
        with self._lock:
            current = self._assignments.get(value.request_id)
            if current is None:
                self._assignments[value.request_id] = value
                return value
            if current == value:
                return current
            raise RoutingAssignmentConflictError(
                "ROUTING_ASSIGNMENT_CONFLICT",
                "Request ja possui assignment de routing incompatível.",
            )

    def get(self, request_id: str) -> RoutingAssignment:
        with self._lock:
            assignment = self._assignments.get(request_id)
            if assignment is None:
                raise RoutingAssignmentNotFoundError(
                    "ROUTING_ASSIGNMENT_NOT_FOUND", "Assignment de routing inexistente."
                )
            return assignment

    def get_optional(self, request_id: str) -> RoutingAssignment | None:
        with self._lock:
            return self._assignments.get(request_id)

    def snapshot(self) -> tuple[RoutingAssignment, ...]:
        with self._lock:
            return tuple(self._assignments[key] for key in sorted(self._assignments))


class RoutingService:
    def __init__(self, registry: RoutingRegistry, store: InMemoryRoutingAssignmentStore):
        self.registry = registry
        self.store = store

    def route(self, request: AccessRequestRecord) -> RoutingAssignment:
        validate_access_request_record(request)
        if request.state != "PENDING_APPROVAL":
            raise RoutingStateError(
                "ROUTING_STATE_NOT_PENDING", "Somente request PENDING_APPROVAL pode ser roteado."
            )
        technician = self.registry.resolve(request.context.system, request.context.capability)
        return self.store.assign(
            RoutingAssignment(
                request_id=request.request_id,
                system=request.context.system,
                capability=request.context.capability,
                technician=technician,
            )
        )


class ApprovalQueue:
    def __init__(self, request_repository, assignment_store: InMemoryRoutingAssignmentStore):
        self.request_repository = request_repository
        self.assignment_store = assignment_store

    def pending(self, *, technician_id: str | None = None) -> tuple[ApprovalQueueItem, ...]:
        items: list[ApprovalQueueItem] = []
        normalized_technician = (
            technician_id.strip().casefold()
            if isinstance(technician_id, str) and technician_id.strip()
            else None
        )
        for assignment in self.assignment_store.snapshot():
            try:
                request = self.request_repository.get(assignment.request_id)
            except RequestNotFoundError as exc:
                raise RoutingQueueConsistencyError(
                    "ROUTING_QUEUE_INCONSISTENT",
                    "Assignment aponta para request inexistente.",
                ) from exc
            if (
                assignment.system != request.context.system
                or assignment.capability != request.context.capability
            ):
                raise RoutingQueueConsistencyError(
                    "ROUTING_QUEUE_INCONSISTENT",
                    "Assignment diverge do contexto imutavel do request.",
                )
            if request.state != "PENDING_APPROVAL":
                continue
            if normalized_technician is not None and (
                assignment.technician.technician_id.strip().casefold() != normalized_technician
            ):
                continue
            items.append(ApprovalQueueItem(request=request, assignment=assignment))
        return tuple(items)


class RoutedRequestService:
    def __init__(self, lifecycle, routing: RoutingService):
        self.lifecycle = lifecycle
        self.routing = routing

    def create_request(self, context) -> AccessRequestRecord:
        record = self.lifecycle.create_request(context)
        if record.state == "PENDING_APPROVAL":
            self.routing.route(record)
        return record
