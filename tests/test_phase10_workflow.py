from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/phase10-routing-escalation.yml"


def test_phase10_workflow_contains_required_gates():
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "pull_request:",
        "fetch-depth: 0",
        'python-version: "3.14"',
        '"ruff==0.12.12"',
        "python -m ruff check .",
        "python -m ruff format --check .",
        "PHASE10_BASELINE_SHA: e5d0e3ccde56effff5c5f9558591b0d12c0740bb",
        "historical_node_ids=",
        "candidate_node_ids=",
        "missing_historical_node_ids=",
        "new_node_ids=",
        "len(historical) != 786",
        "python -m pytest -q",
        "tests/engine/test_phase8_security.py",
        "tests/engine/test_phase9_security.py",
        "tests/engine/test_phase10_security.py",
        "python -m ai_service_desk routing-escalation-smoke",
        "git status --porcelain",
    ):
        assert required in text


def test_phase10_workflow_has_no_external_routing_dependency():
    text = WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "ollama",
        "CDM_API_TOKEN",
        "upload-artifact",
        "workflow_dispatch:",
        "self-hosted",
    ):
        assert forbidden not in text
