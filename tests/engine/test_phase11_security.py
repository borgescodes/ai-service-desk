import ast
import json
import subprocess
from pathlib import Path

import pytest

from ai_service_desk.engine.learning_prevention import (
    LEARNING_RULES_VERSION,
    MIN_RECURRENCE,
    OPPORTUNITY_CATEGORIES,
    OUTCOMES,
    OpportunityEngine,
    OutcomeCollector,
    OutcomeRecord,
    PatternAggregator,
)
from ai_service_desk.engine.routing import RoutingAssignment
from ai_service_desk.engine.technician_authorization import TechnicianIdentity
from tests.engine.phase8_helpers import make_record

ROOT = Path(__file__).resolve().parents[2]
LEARNING_MODULE = ROOT / "src" / "ai_service_desk" / "engine" / "learning_prevention.py"
SMOKE_MODULE = ROOT / "src" / "ai_service_desk" / "engine" / "learning_prevention_smoke.py"
FIXTURE = ROOT / "tests" / "fixtures" / "phase11_learning_prevention_cases.jsonl"

PROTECTED_BLOBS = (
    ("src/ai_service_desk/engine/knowledge.py", "233d60bea6e0616d6b3968760f1bce09fc393d08"),
    (
        "src/ai_service_desk/engine/knowledge_retrieval.py",
        "cf559b66c9a9d150628eeb0d8db195f7a51a34e7",
    ),
    ("src/ai_service_desk/engine/triage.py", "c5ab48f7194fab561f9062c3ab5798c86ec0a8a0"),
    ("src/ai_service_desk/engine/playbook.py", "947fa1c888688a28a35826bc5a03286f46d0269a"),
    (
        "src/ai_service_desk/engine/access_request.py",
        "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
    ),
    ("src/ai_service_desk/engine/policy.py", "60a4f3ae785353009c30b37f71e1ce91865b899e"),
    (
        "src/ai_service_desk/engine/confidence.py",
        "ffc0c212b455978f79a3591578f323ca0e9612dc",
    ),
    (
        "src/ai_service_desk/engine/request_lifecycle.py",
        "dfd194ff8a364a0eb0d803409dad252ced216279",
    ),
    (
        "src/ai_service_desk/engine/request_repository.py",
        "5ccda3d30484729faa1a568cf64e20bfe55e595f",
    ),
    (
        "src/ai_service_desk/engine/technician_authorization.py",
        "ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4",
    ),
    ("src/ai_service_desk/engine/approval.py", "ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8"),
    ("src/ai_service_desk/engine/execution.py", "908ceade729daa3e18b7b604549f635b33d4688f"),
    (
        "src/ai_service_desk/engine/cdm_execution.py",
        "516e258f2349fee42dbd963a7371d2ca3937ca69",
    ),
    (
        "src/ai_service_desk/engine/cdm_integration_smoke.py",
        "07a9416a1c4727b224176ab0840067c536ffc1b9",
    ),
    ("src/ai_service_desk/integrations/cdm.py", "83cc0b23b27b1654912e4f9ba7162c0b0d5f7bfe"),
    (
        "src/ai_service_desk/integrations/cdm_fake_api.py",
        "275b1833d5b27b09c0ffeae9f4484636d10afe63",
    ),
    ("src/ai_service_desk/engine/routing.py", "5c29d443801c26fa54a305a6403949681bae076a"),
    (
        "src/ai_service_desk/engine/routing_escalation_smoke.py",
        "34cc749ac4abdc48a1d8200a2e32c2635773a42c",
    ),
)

FORBIDDEN_MODULES = {
    "requests",
    "urllib",
    "http.client",
    "socket",
    "ai_service_desk.integrations.cdm",
    "ai_service_desk.integrations.cdm_fake_api",
    "ai_service_desk.engine.cdm_execution",
}

FORBIDDEN_MUTATOR_NAMES = {
    "PolicyEngine",
    "ApprovalService",
    "ExecutionEngine",
    "TechnicianAuthorizationRegistry",
    "RoutingService",
    "RoutedRequestService",
}

FORBIDDEN_DATA_FIELDS = {
    "purpose",
    "name",
    "username",
    "email",
    "token",
    "transcript",
    "answer",
    "traceback",
}


def _imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
            names.update(alias.name for alias in node.names)
    return modules, names


@pytest.mark.parametrize(("path", "expected_sha"), PROTECTED_BLOBS)
def test_previous_phase_protected_blobs_are_exact(path: str, expected_sha: str) -> None:
    authorized_extensions = {
        "src/ai_service_desk/integrations/cdm_fake_api.py": (
            "275b1833d5b27b09c0ffeae9f4484636d10afe63",
            "790a3d3fb13bd3b617c0e8587811bf70e519e40c",
        ),
        "src/ai_service_desk/engine/knowledge_retrieval.py": (
            "cf559b66c9a9d150628eeb0d8db195f7a51a34e7",
            "9f887e1a3e1fdc62cdd1cd694c91e48c2ed4fa59",
        ),
        "src/ai_service_desk/engine/triage.py": (
            "c5ab48f7194fab561f9062c3ab5798c86ec0a8a0",
            "d373faa3abbc7d40f31ead59ca369bad3aaed59e",
        ),
        "src/ai_service_desk/engine/access_request.py": (
            "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
            "515a23a38791edd4e11f675804062aa9305a1d25",
        ),
        "src/ai_service_desk/engine/confidence.py": (
            "ffc0c212b455978f79a3591578f323ca0e9612dc",
            "9864ed510a0de3270d30e9088aec407bfd16392d",
        ),
        "src/ai_service_desk/engine/request_lifecycle.py": (
            "dfd194ff8a364a0eb0d803409dad252ced216279",
            "6ab28ad86d7d40e4873e9a76b6c3cd9f3b4c843b",
        ),
    }
    if path in authorized_extensions:
        historical, authorized = authorized_extensions[path]
        assert expected_sha == historical
        expected_sha = authorized
    actual = subprocess.run(
        ["git", "hash-object", path]
        if path == "src/ai_service_desk/integrations/cdm_fake_api.py"
        else ["git", "rev-parse", f"HEAD:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual == expected_sha


@pytest.mark.parametrize("path", [LEARNING_MODULE, SMOKE_MODULE])
def test_learning_runtime_has_no_external_integration_imports(path: Path) -> None:
    modules, _ = _imports(path)
    assert FORBIDDEN_MODULES.isdisjoint(modules)
    assert not any(module.startswith("urllib.") for module in modules)


def test_learning_domain_does_not_import_authorization_or_execution_mutators() -> None:
    _, names = _imports(LEARNING_MODULE)
    assert FORBIDDEN_MUTATOR_NAMES.isdisjoint(names)


def test_outcome_schema_excludes_sensitive_or_free_form_operational_fields() -> None:
    fields = set(OutcomeRecord.__dataclass_fields__)
    assert FORBIDDEN_DATA_FIELDS.isdisjoint(fields)


def test_fixture_is_closed_synthetic_and_contains_no_email_or_secret_fields() -> None:
    allowed = set(OutcomeRecord.__dataclass_fields__)
    raw = FIXTURE.read_text(encoding="utf-8")
    assert "@" not in raw
    for line in raw.splitlines():
        payload = json.loads(line)
        assert set(payload) == allowed
        assert FORBIDDEN_DATA_FIELDS.isdisjoint(payload)
        serialized = json.dumps(payload, sort_keys=True).lower()
        assert "password" not in serialized
        assert "secret" not in serialized
        assert "token" not in serialized


def test_learning_rules_and_vocabularies_are_explicit_and_closed() -> None:
    assert LEARNING_RULES_VERSION == 1
    assert MIN_RECURRENCE == 3
    assert OUTCOMES == frozenset(
        {
            "RESOLVED_BY_KNOWLEDGE",
            "GUIDED_BY_PLAYBOOK",
            "ROUTED_TO_HUMAN",
            "APPROVED",
            "REJECTED",
            "DENIED_POLICY",
            "EXECUTION_COMPLETED",
            "EXECUTION_FAILED",
        }
    )
    assert OPPORTUNITY_CATEGORIES == (
        "KNOWLEDGE_GAP",
        "PLAYBOOK_GAP",
        "HUMAN_DEPENDENCY",
        "AUTOMATION_CANDIDATE",
        "PREVENTION_CANDIDATE",
        "EXECUTION_RELIABILITY_ISSUE",
    )


def test_analytics_does_not_mutate_request_or_routing_assignment() -> None:
    request = make_record("PENDING_APPROVAL")
    technician = TechnicianIdentity(
        technician_id="TECH-SYN",
        username="tech.syn",
        name="Synthetic Technician",
        email="tech.syn@example.invalid",
    )
    assignment = RoutingAssignment(
        request_id=request.request_id,
        system=request.context.system,
        capability=request.context.capability,
        technician=technician,
    )
    request_before = request
    assignment_before = assignment

    outcome = OutcomeCollector.from_request("INT-SYN-SECURITY", request, assignment)
    patterns = PatternAggregator.aggregate((outcome, outcome, outcome))
    OpportunityEngine().generate(patterns)

    assert request == request_before
    assert assignment == assignment_before
    assert outcome.outcome == "ROUTED_TO_HUMAN"
