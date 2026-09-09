import pytest

from ai_service_desk.engine.access_request import AccessRequestContext
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
    RoutingService,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)
from tests.engine.phase8_helpers import FixedClock, make_context


def _build(rules=True):
    repository = InMemoryRequestRepository()
    policy = PolicyEngine()
    lifecycle = RequestLifecycleService(
        repository, policy_engine=policy, clock=FixedClock()
    )
    technician = TechnicianIdentity(
        "TECH-CDM", "tech.cdm", "Tech CDM", "tech.cdm@example.invalid"
    )
    authorization = TechnicianAuthorizationRegistry(
        [TechnicianRegistryEntry(technician, frozenset({"CDM_ACCESS_REQUEST"}))]
    )
    routing_registry = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)] if rules else [],
        authorization,
    )
    assignments = InMemoryRoutingAssignmentStore()
    routing = RoutingService(routing_registry, assignments)
    routed = RoutedRequestService(lifecycle, routing)
    queue = ApprovalQueue(repository, assignments)
    return repository, assignments, routed, queue, technician


def test_allowed_cdm_request_is_automatically_routed_and_queued():
    _, assignments, routed, queue, technician = _build()
    record = routed.create_request(make_context())
    assert record.state == "PENDING_APPROVAL"
    assert assignments.get(record.request_id).technician == technician
    assert tuple(item.request.request_id for item in queue.pending()) == (
        record.request_id,
    )


def test_policy_denied_request_has_no_assignment_and_no_queue_item():
    _, assignments, routed, queue, _ = _build()
    denied_context = AccessRequestContext(
        **{**make_context().__dict__, "requested_role": "ADMIN"}
    )
    record = routed.create_request(denied_context)
    assert record.state == "DENIED_POLICY"
    assert assignments.get_optional(record.request_id) is None
    assert queue.pending() == ()


def test_missing_route_fails_closed_but_preserves_auditable_pending_request():
    repository, assignments, routed, queue, _ = _build(rules=False)
    with pytest.raises(RouteNotFoundError):
        routed.create_request(make_context())
    pending = repository.get("REQ-000001")
    assert pending.state == "PENDING_APPROVAL"
    assert assignments.get_optional(pending.request_id) is None
    assert queue.pending() == ()
