from datetime import UTC, datetime

from ai_service_desk.engine.access_request import AccessRequestContext, SessionIdentity
from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.routing import (
    ApprovalQueue,
    InMemoryRoutingAssignmentStore,
    RoutedRequestService,
    RouteNotFoundError,
    RoutingRegistry,
    RoutingRule,
    RoutingRuleConfigurationError,
    RoutingService,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationError,
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)

ROUTING_ESCALATION_CASE_IDS = (
    "CDM_ALLOWED_PENDING_AND_QUEUED",
    "IDEMPOTENT_ROUTING",
    "DENIED_POLICY_OUTSIDE_QUEUE",
    "UNKNOWN_ROUTE_FAILS_CLOSED",
    "INCOMPATIBLE_TECHNICIAN_CONFIG_REJECTED",
    "DISTINCT_DOMAIN_OWNERS",
    "QUEUE_ITEM_LEAVES_AFTER_DECISION",
    "AUTHORIZATION_REMAINS_FINAL_GATE",
)

DOMAIN_ROUTES = (
    ("CDM", "CDM_ACCESS_REQUEST", "TECH-CDM"),
    ("HARDWARE", "HARDWARE_SUPPORT_REQUEST", "TECH-HARDWARE"),
    ("POWER_BI", "POWER_BI_SUPPORT_REQUEST", "TECH-BI"),
    ("MICROSOFT_365", "MICROSOFT_365_SUPPORT_REQUEST", "TECH-M365"),
    ("ERP", "ERP_SUPPORT_REQUEST", "TECH-ERP"),
)

_TIMESTAMP = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def _clock():
    return _TIMESTAMP


def _identity(technician_id: str) -> TechnicianIdentity:
    slug = technician_id.lower()
    return TechnicianIdentity(
        technician_id=technician_id,
        username=slug,
        name=technician_id,
        email=f"{slug}@example.invalid",
    )


def _context(*, requested_role="SOLICITANTE") -> AccessRequestContext:
    return AccessRequestContext(
        requester=SessionIdentity(
            username="phase10.requester",
            name="Phase 10 Requester",
            email="phase10.requester@example.invalid",
            area="Revenda Sintetica",
        ),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role=requested_role,
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-PHASE10",
        playbook_id="PB-SYN-PHASE10",
        playbook_version=1,
        step_id="STEP-SYN-PHASE10",
        capability="CDM_ACCESS_REQUEST",
    )


def _domain_configuration():
    entries = []
    rules = []
    technicians = {}
    for system, capability, technician_id in DOMAIN_ROUTES:
        technician = _identity(technician_id)
        technicians[technician_id] = technician
        entries.append(TechnicianRegistryEntry(technician, frozenset({capability})))
        rules.append(RoutingRule(system, capability, technician))
    authorization = TechnicianAuthorizationRegistry(entries)
    return authorization, RoutingRegistry(rules, authorization), technicians


def _request_stack():
    repository = InMemoryRequestRepository()
    lifecycle = RequestLifecycleService(
        repository, policy_engine=PolicyEngine(), clock=_clock
    )
    authorization, registry, technicians = _domain_configuration()
    assignments = InMemoryRoutingAssignmentStore()
    routing = RoutingService(registry, assignments)
    queue = ApprovalQueue(repository, assignments)
    routed = RoutedRequestService(lifecycle, routing)
    return repository, lifecycle, authorization, assignments, routing, queue, routed, technicians


def _result(case_id: str, expected: str, actual: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "ok": actual == expected,
        "expected": expected,
        "actual": actual,
    }


def run_routing_escalation_smoke() -> dict[str, object]:
    results = []

    (
        repository,
        lifecycle,
        authorization,
        assignments,
        routing,
        queue,
        routed,
        technicians,
    ) = _request_stack()
    pending = routed.create_request(_context())
    assigned = assignments.get(pending.request_id)
    actual = (
        "PENDING_APPROVAL:TECH-CDM:QUEUED"
        if pending.state == "PENDING_APPROVAL"
        and assigned.technician == technicians["TECH-CDM"]
        and len(queue.pending()) == 1
        else "FAILED"
    )
    results.append(
        _result(
            "CDM_ALLOWED_PENDING_AND_QUEUED",
            "PENDING_APPROVAL:TECH-CDM:QUEUED",
            actual,
        )
    )

    replay = routing.route(pending)
    actual = (
        "ONE_ASSIGNMENT"
        if replay == assigned and len(assignments.snapshot()) == 1
        else "FAILED"
    )
    results.append(_result("IDEMPOTENT_ROUTING", "ONE_ASSIGNMENT", actual))

    denied = routed.create_request(_context(requested_role="ADMIN"))
    actual = (
        "DENIED_POLICY:ZERO_QUEUE"
        if denied.state == "DENIED_POLICY"
        and assignments.get_optional(denied.request_id) is None
        and all(item.request.request_id != denied.request_id for item in queue.pending())
        else "FAILED"
    )
    results.append(
        _result("DENIED_POLICY_OUTSIDE_QUEUE", "DENIED_POLICY:ZERO_QUEUE", actual)
    )

    empty_store = InMemoryRoutingAssignmentStore()
    empty_routing = RoutingService(RoutingRegistry([], authorization), empty_store)
    unknown_pending = lifecycle.create_request(_context())
    try:
        empty_routing.route(unknown_pending)
    except RouteNotFoundError as exc:
        actual = exc.reason_code if not empty_store.snapshot() else "FAILED"
    else:
        actual = "FAILED"
    results.append(_result("UNKNOWN_ROUTE_FAILS_CLOSED", "ROUTE_NOT_FOUND", actual))

    hardware = technicians["TECH-HARDWARE"]
    try:
        RoutingRegistry(
            [RoutingRule("CDM", "CDM_ACCESS_REQUEST", hardware)],
            authorization,
        )
    except RoutingRuleConfigurationError as exc:
        actual = exc.reason_code
    else:
        actual = "FAILED"
    results.append(
        _result(
            "INCOMPATIBLE_TECHNICIAN_CONFIG_REJECTED",
            "ROUTING_TECHNICIAN_NOT_AUTHORIZED",
            actual,
        )
    )

    resolved = tuple(
        routing.registry.resolve(system, capability).technician_id
        for system, capability, _ in DOMAIN_ROUTES
    )
    actual = "FIVE_DISTINCT_OWNERS" if len(set(resolved)) == 5 else "FAILED"
    results.append(_result("DISTINCT_DOMAIN_OWNERS", "FIVE_DISTINCT_OWNERS", actual))

    approval = ApprovalService(repository, lifecycle, authorization, clock=_clock)
    approval.approve(
        pending.request_id,
        technicians["TECH-CDM"],
        expected_version=pending.version,
    )
    actual = (
        "LEFT_QUEUE"
        if all(item.request.request_id != pending.request_id for item in queue.pending())
        else "FAILED"
    )
    results.append(_result("QUEUE_ITEM_LEAVES_AFTER_DECISION", "LEFT_QUEUE", actual))

    second_pending = routed.create_request(_context())
    try:
        approval.approve(
            second_pending.request_id,
            technicians["TECH-HARDWARE"],
            expected_version=second_pending.version,
        )
    except TechnicianAuthorizationError as exc:
        actual = exc.reason_code
    else:
        actual = "FAILED"
    results.append(
        _result(
            "AUTHORIZATION_REMAINS_FINAL_GATE",
            "TECHNICIAN_CAPABILITY_REQUIRED",
            actual,
        )
    )

    return {
        "ok": all(item["ok"] for item in results),
        "case_count": len(results),
        "cases": results,
    }
