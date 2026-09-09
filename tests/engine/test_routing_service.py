import pytest

from ai_service_desk.engine.routing import (
    InMemoryRoutingAssignmentStore,
    RouteNotFoundError,
    RoutingRegistry,
    RoutingRule,
    RoutingService,
    RoutingStateError,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)
from tests.engine.phase8_helpers import make_record


def _service():
    technician = TechnicianIdentity(
        technician_id="TECH-CDM",
        username="tech.cdm",
        name="Tech CDM",
        email="tech.cdm@example.invalid",
    )
    authorization = TechnicianAuthorizationRegistry(
        [TechnicianRegistryEntry(technician, frozenset({"CDM_ACCESS_REQUEST"}))]
    )
    registry = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)],
        authorization,
    )
    store = InMemoryRoutingAssignmentStore()
    return RoutingService(registry, store), store, technician


def test_pending_request_routes_to_configured_technician():
    service, store, technician = _service()
    record = make_record("PENDING_APPROVAL")
    assignment = service.route(record)
    assert assignment.request_id == record.request_id
    assert assignment.technician == technician
    assert store.snapshot() == (assignment,)


def test_repeated_routing_is_idempotent():
    service, store, _ = _service()
    record = make_record("PENDING_APPROVAL")
    first = service.route(record)
    second = service.route(record)
    assert first == second
    assert store.snapshot() == (first,)


@pytest.mark.parametrize(
    "state",
    ["TRIAGED", "APPROVED", "REJECTED", "DENIED_POLICY", "EXECUTING", "COMPLETED", "FAILED"],
)
def test_non_pending_state_never_routes(state):
    service, store, _ = _service()
    with pytest.raises(RoutingStateError) as exc:
        service.route(make_record(state))
    assert exc.value.reason_code == "ROUTING_STATE_NOT_PENDING"
    assert store.snapshot() == ()


def test_unknown_route_does_not_assign_arbitrary_technician():
    service, store, _ = _service()
    record = make_record("PENDING_APPROVAL")
    record = record.__class__(
        **{
            **record.__dict__,
            "context": record.context.__class__(
                **{**record.context.__dict__, "system": "ERP", "capability": "ERP_SUPPORT_REQUEST"}
            ),
        }
    )
    with pytest.raises(RouteNotFoundError) as exc:
        service.route(record)
    assert exc.value.reason_code == "ROUTE_NOT_FOUND"
    assert store.snapshot() == ()
