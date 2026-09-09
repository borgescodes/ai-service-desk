import ast
import subprocess
from pathlib import Path

import pytest

from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import ALLOWED_TRANSITIONS, REQUEST_STATES, RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.routing import (
    ApprovalQueue,
    InMemoryRoutingAssignmentStore,
    RouteNotFoundError,
    RoutedRequestService,
    RoutingRegistry,
    RoutingRule,
    RoutingRuleConfigurationError,
    RoutingService,
)
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)
from tests.engine.phase8_helpers import FixedClock, make_context

ROOT = Path(__file__).resolve().parents[2]
PROTECTED_BLOBS = {
    "src/ai_service_desk/engine/access_request.py": "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
    "src/ai_service_desk/engine/policy.py": "60a4f3ae785353009c30b37f71e1ce91865b899e",
    "src/ai_service_desk/engine/confidence.py": "ffc0c212b455978f79a3591578f323ca0e9612dc",
    "src/ai_service_desk/engine/request_lifecycle.py": "dfd194ff8a364a0eb0d803409dad252ced216279",
    "src/ai_service_desk/engine/request_repository.py": "5ccda3d30484729faa1a568cf64e20bfe55e595f",
    "src/ai_service_desk/engine/technician_authorization.py": "ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4",
    "src/ai_service_desk/engine/approval.py": "ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8",
    "src/ai_service_desk/engine/execution.py": "908ceade729daa3e18b7b604549f635b33d4688f",
    "src/ai_service_desk/engine/cdm_execution.py": "516e258f2349fee42dbd963a7371d2ca3937ca69",
    "src/ai_service_desk/engine/cdm_integration_smoke.py": "07a9416a1c4727b224176ab0840067c536ffc1b9",
    "src/ai_service_desk/integrations/cdm.py": "83cc0b23b27b1654912e4f9ba7162c0b0d5f7bfe",
    "src/ai_service_desk/integrations/cdm_fake_api.py": "275b1833d5b27b09c0ffeae9f4484636d10afe63",
}


@pytest.mark.parametrize(("path", "expected_sha"), PROTECTED_BLOBS.items())
def test_phase10_protected_git_blob_is_exact(path, expected_sha):
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == expected_sha


def test_phase8_lifecycle_contract_remains_exact():
    assert REQUEST_STATES == frozenset(
        {
            "TRIAGED",
            "PENDING_APPROVAL",
            "APPROVED",
            "REJECTED",
            "DENIED_POLICY",
            "EXECUTING",
            "COMPLETED",
            "FAILED",
        }
    )
    assert len(ALLOWED_TRANSITIONS) == 8


def test_routing_runtime_has_no_http_or_cdm_execution_imports():
    path = ROOT / "src/ai_service_desk/engine/routing.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    forbidden = (
        "requests",
        "urllib",
        "http.client",
        "socket",
        "ai_service_desk.integrations.cdm",
        "ai_service_desk.integrations.cdm_fake_api",
        "ai_service_desk.engine.cdm_execution",
    )
    for name in imports:
        assert not any(name == item or name.startswith(item + ".") for item in forbidden)


def _routing_services():
    repository = InMemoryRequestRepository()
    lifecycle = RequestLifecycleService(repository, policy_engine=PolicyEngine(), clock=FixedClock())
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
    return repository, lifecycle, authorization, assignments, routing


def test_denied_policy_never_receives_assignment_or_queue_item():
    repository, lifecycle, _, assignments, routing = _routing_services()
    routed = RoutedRequestService(lifecycle, routing)
    context = make_context(requested_role="ADMIN")
    denied = routed.create_request(context)
    assert denied.state == "DENIED_POLICY"
    assert assignments.get_optional(denied.request_id) is None
    assert ApprovalQueue(repository, assignments).pending() == ()


def test_routing_preserves_policy_confidence_and_context():
    _, lifecycle, _, assignments, routing = _routing_services()
    pending = lifecycle.create_request(make_context())
    before = (pending.context, pending.creation_policy, pending.latest_policy, pending.confidence)
    routing.route(pending)
    after = (pending.context, pending.creation_policy, pending.latest_policy, pending.confidence)
    assert after == before
    assert len(assignments.snapshot()) == 1


def test_unknown_route_fails_closed():
    repository = InMemoryRequestRepository()
    lifecycle = RequestLifecycleService(repository, policy_engine=PolicyEngine(), clock=FixedClock())
    authorization = TechnicianAuthorizationRegistry([])
    routing = RoutingService(RoutingRegistry([], authorization), InMemoryRoutingAssignmentStore())
    pending = lifecycle.create_request(make_context())
    with pytest.raises(RouteNotFoundError) as exc:
        routing.route(pending)
    assert exc.value.reason_code == "ROUTE_NOT_FOUND"


def test_conflicting_and_incompatible_route_configuration_fails_closed():
    first = TechnicianIdentity("TECH-A", "tech.a", "Tech A", "tech.a@example.invalid")
    second = TechnicianIdentity("TECH-B", "tech.b", "Tech B", "tech.b@example.invalid")
    authorization = TechnicianAuthorizationRegistry(
        [
            TechnicianRegistryEntry(first, frozenset({"CDM_ACCESS_REQUEST"})),
            TechnicianRegistryEntry(second, frozenset({"HARDWARE_SUPPORT_REQUEST"})),
        ]
    )
    with pytest.raises(RoutingRuleConfigurationError) as incompatible:
        RoutingRegistry([RoutingRule("CDM", "CDM_ACCESS_REQUEST", second)], authorization)
    assert incompatible.value.reason_code == "ROUTING_TECHNICIAN_NOT_AUTHORIZED"
    with pytest.raises(RoutingRuleConfigurationError) as conflict:
        RoutingRegistry(
            [
                RoutingRule("CDM", "CDM_ACCESS_REQUEST", first),
                RoutingRule("CDM", "CDM_ACCESS_REQUEST", first),
            ],
            authorization,
        )
    assert conflict.value.reason_code == "ROUTING_RULE_CONFLICT"
