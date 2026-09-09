from dataclasses import FrozenInstanceError

import pytest

from ai_service_desk.engine.routing import (
    RouteNotFoundError,
    RoutingRegistry,
    RoutingRule,
    RoutingRuleConfigurationError,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)


def _technician(
    technician_id: str, capability: str
) -> tuple[TechnicianIdentity, TechnicianRegistryEntry]:
    identity = TechnicianIdentity(
        technician_id=technician_id,
        username=technician_id.lower(),
        name=technician_id,
        email=f"{technician_id.lower()}@example.invalid",
    )
    return identity, TechnicianRegistryEntry(identity, frozenset({capability}))


def test_routing_rule_is_frozen():
    technician, entry = _technician("TECH-CDM", "CDM_ACCESS_REQUEST")
    TechnicianAuthorizationRegistry([entry])
    rule = RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)
    with pytest.raises(FrozenInstanceError):
        rule.system = "ERP"


def test_registry_resolves_exact_route():
    technician, entry = _technician("TECH-CDM", "CDM_ACCESS_REQUEST")
    authorization = TechnicianAuthorizationRegistry([entry])
    registry = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)],
        authorization,
    )
    assert registry.resolve("CDM", "CDM_ACCESS_REQUEST") == technician


@pytest.mark.parametrize(
    "rule",
    [
        None,
        RoutingRule("", "CDM_ACCESS_REQUEST", TechnicianIdentity("T", "u", "n", "e")),
        RoutingRule("cdm", "CDM_ACCESS_REQUEST", TechnicianIdentity("T", "u", "n", "e")),
        RoutingRule("CDM", "bad capability", TechnicianIdentity("T", "u", "n", "e")),
    ],
)
def test_invalid_rule_fails_closed(rule):
    technician, entry = _technician("TECH-CDM", "CDM_ACCESS_REQUEST")
    authorization = TechnicianAuthorizationRegistry([entry])
    with pytest.raises(RoutingRuleConfigurationError) as exc:
        RoutingRegistry([rule], authorization)
    assert exc.value.reason_code == "ROUTING_RULE_INVALID"


def test_duplicate_route_fails_closed():
    first, first_entry = _technician("TECH-CDM-A", "CDM_ACCESS_REQUEST")
    second, second_entry = _technician("TECH-CDM-B", "CDM_ACCESS_REQUEST")
    authorization = TechnicianAuthorizationRegistry([first_entry, second_entry])
    with pytest.raises(RoutingRuleConfigurationError) as exc:
        RoutingRegistry(
            [
                RoutingRule("CDM", "CDM_ACCESS_REQUEST", first),
                RoutingRule("CDM", "CDM_ACCESS_REQUEST", second),
            ],
            authorization,
        )
    assert exc.value.reason_code == "ROUTING_RULE_CONFLICT"


def test_incompatible_technician_configuration_is_rejected():
    technician, entry = _technician("TECH-HARDWARE", "HARDWARE_SUPPORT_REQUEST")
    authorization = TechnicianAuthorizationRegistry([entry])
    with pytest.raises(RoutingRuleConfigurationError) as exc:
        RoutingRegistry(
            [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)],
            authorization,
        )
    assert exc.value.reason_code == "ROUTING_TECHNICIAN_NOT_AUTHORIZED"


def test_unknown_route_fails_closed_without_fallback():
    technician, entry = _technician("TECH-CDM", "CDM_ACCESS_REQUEST")
    authorization = TechnicianAuthorizationRegistry([entry])
    registry = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)],
        authorization,
    )
    with pytest.raises(RouteNotFoundError) as exc:
        registry.resolve("ERP", "ERP_SUPPORT_REQUEST")
    assert exc.value.reason_code == "ROUTE_NOT_FOUND"


@pytest.mark.parametrize(
    ("system", "capability"),
    [
        ("CD", "CDM_ACCESS_REQUEST"),
        ("CDM", "CDM_*"),
        ("CDM", "CDM_ACCESS"),
        ("CDM", "cdm_access_request"),
    ],
)
def test_resolver_does_not_use_wildcard_prefix_or_fuzzy_matching(system, capability):
    technician, entry = _technician("TECH-CDM", "CDM_ACCESS_REQUEST")
    authorization = TechnicianAuthorizationRegistry([entry])
    registry = RoutingRegistry(
        [RoutingRule("CDM", "CDM_ACCESS_REQUEST", technician)],
        authorization,
    )
    with pytest.raises(RouteNotFoundError):
        registry.resolve(system, capability)
