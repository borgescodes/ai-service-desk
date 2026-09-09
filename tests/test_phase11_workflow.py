from pathlib import Path

from tests.engine.test_phase11_security import PROTECTED_BLOBS

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "phase11-learning-prevention.yml"


def test_phase11_workflow_contains_required_homologation_gates() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "pull_request:",
        "fetch-depth: 0",
        'python-version: "3.14"',
        '"ruff==0.12.12"',
        "python -m ruff check .",
        "python -m ruff format --check .",
        "81a748921ba01393285da2e2d2ebc9371c890e2c",
        "historical_node_ids=",
        "candidate_node_ids=",
        "missing_historical_node_ids=",
        "new_node_ids=",
        "len(historical) != 847",
        "python -m pytest -q",
        "tests/engine/test_phase8_security.py",
        "tests/engine/test_phase9_security.py",
        "tests/engine/test_phase10_security.py",
        "tests/engine/test_phase11_security.py",
        "python -m ai_service_desk routing-escalation-smoke",
        "python -m ai_service_desk learning-prevention-smoke",
        "git status --porcelain",
    )
    for expected in required:
        assert expected in source


def test_phase11_workflow_verifies_every_protected_blob() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    for path, expected_sha in PROTECTED_BLOBS:
        assert path in source
        assert expected_sha in source
