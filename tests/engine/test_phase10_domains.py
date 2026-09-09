import pytest

from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.routing import RoutingRegistry, RoutingRule
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationError,
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)
from tests.engine.phase8_helpers import FixedClock, make_context


DOMAIN_ROUTES = (
    ("CDM", "CDM_ACCESS_REQUEST", "TECH-CDM"),
    ("HARDWARE", "HARDWARE_SUPPORT_REQUEST", "TECH-HARDWARE"),
    ("POWER_BI", "POWER_BI_SUPPORT_REQUEST", "TECH-BI"),
    ("MICROSOFT_365", "MICROSOFT_365_SUPPORT_REQUEST", "TECH-M365"),
    ("ERP", "ERP_SUPPORT_REQUEST", "TECH-ERP"),
)


def _identity(technician_id: str) -> TechnicianIdentity:
    slug = technician_id.lower()
    return TechnicianIdentity(technician_id, slug, technician_id, f"{slug}@example.invalid")


def test_five_demo_domains_resolve_to_distinct_authorized_owners():
    entries = []
    rules = []
    expected = {}
    for system, capability, technician_id in DOMAIN_ROUTES:
        technician = _identity(technician_id)
        entries.append(TechnicianRegistryEntry(technician, frozenset({capability})))
        rules.append(RoutingRule(system, capability, technician))
        expected[(system, capability)] = technician
    registry = RoutingRegistry(rules, TechnicianAuthorizationRegistry(entries))
    assert {
        key: registry.resolve(*key).technician_id for key in expected
    } == {key: value.technician_id for key, value in expected.items()}
    assert len({value.technician_id for value in expected.values()}) == 5


def test_routing_does_not_replace_approval_authorization_gate():
    repository = InMemoryRequestRepository()
    policy = PolicyEngine()
    lifecycle = RequestLifecycleService(repository, policy_engine=policy, clock=FixedClock())
    assigned = _identity("TECH-CDM")
    unauthorized = _identity("TECH-HARDWARE")
    registry = TechnicianAuthorizationRegistry(
        [
            TechnicianRegistryEntry(assigned, frozenset({"CDM_ACCESS_REQUEST"})),
            TechnicianRegistryEntry(unauthorized, frozenset({"HARDWARE_SUPPORT_REQUEST"})),
        ]
    )
    routing = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", assigned)], registry
    )
    assert routing.resolve("CDM", "CDM_ACCESS_REQUEST") == assigned
    pending = lifecycle.create_request(make_context())
    approval = ApprovalService(repository, lifecycle, registry, clock=FixedClock())
    with pytest.raises(TechnicianAuthorizationError) as exc:
        approval.approve(pending.request_id, unauthorized, expected_version=pending.version)
    assert exc.value.reason_code == "TECHNICIAN_CAPABILITY_REQUIRED"
    assert repository.get(pending.request_id).state == "PENDING_APPROVAL"
