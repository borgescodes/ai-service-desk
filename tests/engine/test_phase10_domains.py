import pytest


DOMAIN_ROUTES = (
    ("CDM", "CDM_ACCESS_REQUEST", "TECH-CDM"),
    ("HARDWARE", "HARDWARE_SUPPORT_REQUEST", "TECH-HARDWARE"),
    ("POWER_BI", "POWER_BI_SUPPORT_REQUEST", "TECH-BI"),
    ("MICROSOFT_365", "MICROSOFT_365_SUPPORT_REQUEST", "TECH-M365"),
    ("ERP", "ERP_SUPPORT_REQUEST", "TECH-ERP"),
)


def _identity(technician_id: str):
    from ai_service_desk.engine.technician_authorization import TechnicianIdentity

    slug = technician_id.lower()
    return TechnicianIdentity(
        technician_id,
        slug,
        technician_id,
        f"{slug}@example.invalid",
    )


def test_five_demo_domains_resolve_to_distinct_authorized_owners():
    from ai_service_desk.engine.routing import RoutingRegistry, RoutingRule
    from ai_service_desk.engine.technician_authorization import (
        TechnicianAuthorizationRegistry,
        TechnicianRegistryEntry,
    )

    entries = []
    rules = []
    expected = {}
    for system, capability, technician_id in DOMAIN_ROUTES:
        technician = _identity(technician_id)
        entries.append(TechnicianRegistryEntry(technician, frozenset({capability})))
        rules.append(RoutingRule(system, capability, technician))
        expected[(system, capability)] = technician
    registry = RoutingRegistry(rules, TechnicianAuthorizationRegistry(entries))
    assert {key: registry.resolve(*key).technician_id for key in expected} == {
        key: value.technician_id for key, value in expected.items()
    }
    assert len({value.technician_id for value in expected.values()}) == 5


def test_routing_does_not_replace_approval_authorization_gate():
    from ai_service_desk.engine.approval import ApprovalService
    from ai_service_desk.engine.policy import PolicyEngine
    from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
    from ai_service_desk.engine.request_repository import InMemoryRequestRepository
    from ai_service_desk.engine.routing import RoutingRegistry, RoutingRule
    from ai_service_desk.engine.technician_authorization import (
        TechnicianAuthorizationError,
        TechnicianAuthorizationRegistry,
        TechnicianRegistryEntry,
    )
    from tests.engine.phase8_helpers import FixedClock, make_context

    repository = InMemoryRequestRepository()
    lifecycle = RequestLifecycleService(
        repository,
        policy_engine=PolicyEngine(),
        clock=FixedClock(),
    )
    assigned = _identity("TECH-CDM")
    unauthorized = _identity("TECH-HARDWARE")
    registry = TechnicianAuthorizationRegistry(
        [
            TechnicianRegistryEntry(assigned, frozenset({"CDM_ACCESS_REQUEST"})),
            TechnicianRegistryEntry(unauthorized, frozenset({"HARDWARE_SUPPORT_REQUEST"})),
        ]
    )
    resolver = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", assigned)],
        registry,
    )
    assert resolver.resolve("CDM", "CDM_ACCESS_REQUEST") == assigned
    pending = lifecycle.create_request(make_context())
    approval_service = ApprovalService(
        repository,
        lifecycle,
        registry,
        clock=FixedClock(),
    )
    with pytest.raises(TechnicianAuthorizationError) as exc:
        approval_service.approve(
            pending.request_id,
            unauthorized,
            expected_version=pending.version,
        )
    assert exc.value.reason_code == "TECHNICIAN_CAPABILITY_REQUIRED"
    assert repository.get(pending.request_id).state == "PENDING_APPROVAL"
