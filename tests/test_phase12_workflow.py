from pathlib import Path


WORKFLOW = Path(".github/workflows/phase12-web-demo.yml")
BASELINE = "a4c4dc25afd07f449036dd837dbcfa4a219806c2"


def test_phase12_workflow_contains_required_runtime_and_verification_gates() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    required = [
        'python-version: "3.14"',
        '"ruff==0.12.12"',
        BASELINE,
        "925",
        "Historical node ID preservation",
        "Full pytest",
        "actions/setup-node",
        "Frontend lint",
        "Frontend tests",
        "Frontend build",
        "Protected F1-F11 blobs",
        "test_phase8_security.py",
        "test_phase9_security.py",
        "test_phase10_security.py",
        "test_phase11_security.py",
        "test_phase12_security.py",
        "routing-escalation-smoke",
        "learning-prevention-smoke",
        "web-demo-smoke",
        "Working tree clean",
    ]
    for marker in required:
        assert marker in text


def test_phase12_workflow_protects_all_specified_domain_modules() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    protected = [
        "engine/classification.py",
        "engine/knowledge.py",
        "engine/knowledge_retrieval.py",
        "engine/triage.py",
        "engine/playbook.py",
        "engine/playbook_resolution.py",
        "engine/access_request.py",
        "engine/policy.py",
        "engine/confidence.py",
        "engine/request_lifecycle.py",
        "engine/request_repository.py",
        "engine/technician_authorization.py",
        "engine/approval.py",
        "engine/execution.py",
        "engine/cdm_execution.py",
        "engine/routing.py",
        "engine/learning_prevention.py",
        "integrations/cdm.py",
        "integrations/cdm_fake_api.py",
    ]
    for suffix in protected:
        assert f"src/ai_service_desk/{suffix}" in text
