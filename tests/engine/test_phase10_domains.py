import pytest

from ai_service_desk.engine import (
    approval,
    policy,
    request_lifecycle,
    request_repository,
    routing,
    technician_authorization,
)
from tests.engine import phase8_helpers


DOMAIN_ROUTES = (
    ("CDM", "CDM_ACCESS_REQUEST", "TECH-CDM"),
    ("HARDWARE", "HARDWARE_SUPPORT_REQUEST", "TECH-HARDWARE"),
    ("POWER_BI", "POWER_BI_SUPPORT_REQUEST", "TECH-BI"),
    ("MICROSOFT_365", "MICROSOFT_365_SUPPORT_REQUEST", "TECH-M365"),
    ("ERP", "ERP_SUPPORT_REQUEST", "TECH-ERP"),
)


def _identity(technician_id: str) -> technician_authorization.TechnicianIdentity:
    slug = technician_id.lower()
    return technician_authorization.TechnicianIdentity(
        technician_id,
        slug,
        technician_id,
        f"{slug}@example.invalid",
    )


def test_five_demo_domains_resolve_to_distinct_authorized_owners():
    entries = []
    rules = []
    expected = {}
    for system, capability, technician_id in DOMAIN_ROUTES:
        technician = _identity(technician_id)
        entries.append(
            technician_authorization.TechnicianRegistryEntry(
                technician,
                frozenset({capability}),
            )
        )
        rules.append(routing.RoutingRule(system, capability, technician))
        expected[(system, capability)] = technician
    registry = routing.RoutingRegistry(
        rules,
        technician_authorization.TechnicianAuthorizationRegistry(entries),
    )
    assert {key: registry.resolve(*key).technician_id for key in expected} == {
        key: value.technician_id for key, value in expected.items()
    }
    assert len({value.technician_id for value in expected.values()}) == 5


def test_routing_does_not_replace_approval_authorization_gate():
    repository = request_repository.InMemoryRequestRepository()
    lifecycle = request_lifecycle.RequestLifecycleService(
        repository,
        policy_engine=policy.PolicyEngine(),
        clock=phase8_helpers.FixedClock(),
    )
    assigned = _identity("TECH-CDM")
    unauthorized = _identity("TECH-HARDWARE")
    registry = technician_authorization.TechnicianAuthorizationRegistry(
        [
            technician_authorization.TechnicianRegistryEntry(
                assigned,
                frozenset({"CDM_ACCESS_REQUEST"}),
            ),
            technician_authorization.TechnicianRegistryEntry(
                unauthorized,
                frozenset({"HARDWARE_SUPPORT_REQUEST"}),
            ),
        ]
    )
    resolver = routing.RoutingRegistry(
        [routing.RoutingRule("CDM", "CDM_ACCESS_REQUEST", assigned)],
        registry,
    )
    assert resolver.resolve("CDM", "CDM_ACCESS_REQUEST") == assigned
    pending = lifecycle.create_request(phase8_helpers.make_context())
    approval_service = approval.ApprovalService(
        repository,
        lifecycle,
        registry,
        clock=phase8_helpers.FixedClock(),
    )
    with pytest.raises(technician_authorization.TechnicianAuthorizationError) as exc:
        approval_service.approve(
            pending.request_id,
            unauthorized,
            expected_version=pending.version,
        )
    assert exc.value.reason_code == "TECHNICIAN_CAPABILITY_REQUIRED"
    assert repository.get(pending.request_id).state == "PENDING_APPROVAL"
