from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASE7_WORKFLOW = ROOT / ".github" / "workflows" / "phase7-policy-smoke.yml"


def test_phase7_policy_workflow_restores_phase2_fixture_from_exact_head_blob() -> None:
    text = PHASE7_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "Restore line-ending-sensitive Phase 2 fixture from exact Git blob bytes",
        '["git", "show", "HEAD:tests/fixtures/phase2_corpus.csv"]',
        "tests/fixtures/phase2_corpus_manifest.json",
        'manifest["expected"]["raw_sha256"]',
        "path.write_bytes(blob)",
        "fixture_raw_sha_after",
        "candidate_sha_after_fixture_restore",
        "$actual -ne $expected",
    ):
        assert required in text

    assert (
        text.index("Verify Python 3.14")
        < text.index("Restore line-ending-sensitive Phase 2 fixture from exact Git blob bytes")
        < text.index("Install project")
    )
