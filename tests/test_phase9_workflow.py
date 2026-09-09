from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/phase9-cdm-integration.yml"


def test_phase9_workflow_is_pr_hosted_and_secret_free():
    assert WORKFLOW.exists()
    text = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "pull_request:",
        "fetch-depth: 0",
        'python-version: "3.14"',
        '"ruff==0.12.12"',
        "secrets.token_urlsafe(32)",
        "python -m ruff check .",
        "python -m ruff format --check .",
        "Historical node ID preservation",
        "fd48e294617ea4d4cff91effeec507abbf44e4d5",
        "len(historical) != 701",
        "missing_historical_node_ids=",
        "python -m pytest -q",
        "python -m ai_service_desk cdm-integration-smoke",
        "tests/fixtures/phase9_cdm_integration_cases.jsonl",
    ):
        assert required in text
    assert "CDM_API_TOKEN: " not in text
    assert "test-token" not in text
