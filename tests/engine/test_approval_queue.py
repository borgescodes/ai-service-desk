from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.routing import (
    ApprovalQueue,
    InMemoryRoutingAssignmentStore,
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


def _services():
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
    registry = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)], authorization
    )
    assignments = InMemoryRoutingAssignmentStore()
    routing = RoutingService(registry, assignments)
    queue = ApprovalQueue(repository, assignments)
    return repository, lifecycle, authorization, technician, routing, queue


def test_pending_assignment_appears_and_filter_is_operational_only():
    _, lifecycle, _, technician, routing, queue = _services()
    pending = lifecycle.create_request(make_context())
    routing.route(pending)
    items = queue.pending()
    assert len(items) == 1
    assert items[0].request.request_id == pending.request_id
    assert items[0].assignment.technician == technician
    assert queue.pending(technician_id="TECH-CDM") == items
    assert queue.pending(technician_id="TECH-OTHER") == ()


def test_approved_request_leaves_pending_queue_automatically():
    repository, lifecycle, authorization, technician, routing, queue = _services()
    pending = lifecycle.create_request(make_context())
    routing.route(pending)
    assert len(queue.pending()) == 1
    approval = ApprovalService(repository, lifecycle, authorization, clock=FixedClock())
    approval.approve(pending.request_id, technician, expected_version=pending.version)
    assert queue.pending() == ()


def test_rejected_request_leaves_pending_queue_automatically():
    repository, lifecycle, authorization, technician, routing, queue = _services()
    pending = lifecycle.create_request(make_context())
    routing.route(pending)
    approval = ApprovalService(repository, lifecycle, authorization, clock=FixedClock())
    approval.reject(pending.request_id, technician, expected_version=pending.version)
    assert queue.pending() == ()
