from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "real-corpus-smoke.yml"
DEMO_WORKFLOW = ROOT / ".github" / "workflows" / "demo-retrieval-smoke.yml"
PHASE3_WORKFLOW = ROOT / ".github" / "workflows" / "phase3-evaluation.yml"
PHASE4_WORKFLOW = ROOT / ".github" / "workflows" / "phase4-knowledge-smoke.yml"
PHASE5_WORKFLOW = ROOT / ".github" / "workflows" / "phase5-triage-smoke.yml"
PHASE6_WORKFLOW = ROOT / ".github" / "workflows" / "phase6-playbook-smoke.yml"
PHASE7_WORKFLOW = ROOT / ".github" / "workflows" / "phase7-policy-smoke.yml"


def test_real_corpus_workflow_is_manual_local_and_non_exporting() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "corpus_path:",
        "index_path:",
        "report_path:",
        "self-hosted",
        "Windows",
        "ai-service-desk",
        "ollama",
        "timeout-minutes: 180",
        "python -m ai_service_desk real-smoke",
        "--manifest docs/data/phase-2-corpus-v1.json",
        "--checkout",
        "http://127.0.0.1:11434",
    ):
        assert required in text

    for forbidden in ("upload-artifact", "Get-Content", "--show-history"):
        assert forbidden not in text


def test_demo_retrieval_workflow_is_manual_local_and_non_exporting() -> None:
    text = DEMO_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "corpus_path:",
        "demo_root:",
        "rebuild:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk audit",
        "--manifest docs/data/phase-2-corpus-v1.json",
        "python -m ai_service_desk demo-subset",
        "python -m ai_service_desk demo-smoke",
        "C:\\ai-service-desk-data\\phase-2\\demo",
        "--per-group 40",
    ):
        assert required in text

    assert text.index("python -m ai_service_desk audit") < text.index(
        "python -m ai_service_desk demo-subset"
    )

    for forbidden in ("upload-artifact", "Get-Content", "--show-history"):
        assert forbidden not in text


def test_phase3_evaluation_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE3_WORKFLOW.exists()
    text = PHASE3_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "report_path:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk index",
        "python -m ai_service_desk evaluate",
        "tests/fixtures/phase3_eval_corpus.csv",
        "tests/fixtures/phase3_eval_cases.jsonl",
        "C:\\ai-service-desk-data\\phase-3\\reports",
        "http://127.0.0.1:11434",
    ):
        assert required in text

    for forbidden in ("upload-artifact", "Get-Content", "--show-history"):
        assert forbidden not in text


def test_phase4_knowledge_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE4_WORKFLOW.exists()
    text = PHASE4_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk knowledge-index",
        "python -m ai_service_desk knowledge-smoke",
        "knowledge/phase4_synthetic_faq.jsonl",
        "http://127.0.0.1:11434",
    ):
        assert required in text

    for forbidden in ("upload-artifact", "Get-Content", "--show-history"):
        assert forbidden not in text


def test_phase5_triage_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE5_WORKFLOW.exists()
    text = PHASE5_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk knowledge-index",
        "python -m ai_service_desk triage-smoke",
        "knowledge/phase4_synthetic_faq.jsonl",
        "tests/fixtures/phase5_triage_conversations.jsonl",
        "http://127.0.0.1:11434",
    ):
        assert required in text

    for forbidden in ("upload-artifact", "Get-Content", "--show-history"):
        assert forbidden not in text


def test_phase6_playbook_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE6_WORKFLOW.exists()
    text = PHASE6_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "python -m ai_service_desk knowledge-index",
        "python -m ai_service_desk playbook-validate",
        "python -m ai_service_desk playbook-build",
        "python -m ai_service_desk playbook-smoke",
        "knowledge/phase4_synthetic_faq.jsonl",
        "playbooks/phase6_synthetic_playbooks.jsonl",
        "tests/fixtures/phase6_playbook_cases.jsonl",
        "http://127.0.0.1:11434",
    ):
        assert required in text

    for forbidden in ("upload-artifact", "Get-Content", "--show-history", "DEMO_PRINT_QUEUE_CLEAR"):
        assert forbidden not in text


def test_phase7_policy_workflow_is_manual_local_and_non_exporting() -> None:
    assert PHASE7_WORKFLOW.exists()
    text = PHASE7_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "Exact candidate commit SHA to validate",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "TARGET_REF: ${{ inputs.target_ref }}",
        "git rev-parse HEAD",
        "^[0-9a-f]{40}$",
        "$actual -ne $expected",
        "python -m ruff check .",
        "python -m ruff format --check .",
        "python -m pytest -q",
        "python -m ai_service_desk policy-smoke",
        "tests/fixtures/phase7_policy_cases.jsonl",
    ):
        assert required in text
    for forbidden in (
        "upload-artifact",
        "Get-Content",
        "python -m ai_service_desk doctor",
        "knowledge-index",
        "playbook-build",
        "http://127.0.0.1:11434",
        "CDM_ACCESS_REQUEST",
        "PHASE7_CANDIDATE_SHA",
    ):
        assert forbidden not in text


def test_gitignore_blocks_real_corpus_and_generated_index_files() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for required in (
        "base_ti_preparada.csv",
        "**/documents.jsonl",
        "**/embeddings.npy",
        "phase-2-data/",
    ):
        assert required in text


PHASE8_WORKFLOW = ROOT / ".github/workflows/phase8-controlled-execution-smoke.yml"


def test_phase8_controlled_execution_workflow_is_exact_head_and_non_exporting():
    text = PHASE8_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "workflow_dispatch:",
        "target_ref:",
        "required: true",
        "type: string",
        "ref: ${{ inputs.target_ref }}",
        "^[0-9a-f]{40}$",
        "[self-hosted, Windows, X64, ai-service-desk]",
        'StartsWith("3.14.")',
        "git rev-parse HEAD",
        "$actual -ne $expected",
        "$LASTEXITCODE -ne 0",
        "python -m ruff check .",
        "python -m ruff format --check .",
        "python -m pytest -q",
        "python -m ai_service_desk controlled-execution-smoke",
        "tests/fixtures/phase8_controlled_execution_cases.jsonl",
        '"HEAD:tests/fixtures/phase2_corpus.csv"',
        "path.write_bytes(blob)",
        'manifest["expected"]["raw_sha256"]',
        "fixture_raw_sha_after=",
        "candidate_sha_after_fixture_restore=",
        "RUNNER_TEMP",
    ):
        assert required in text
    for forbidden in (
        "upload-artifact",
        "ollama",
        "http://",
        "https://",
        "CDMAdapter",
        "git commit",
    ):
        assert forbidden not in text
    assert text.count("write_bytes(") == 1
    assert "write_text(" not in text
    assert text.index("path.write_bytes(blob)") < text.index("candidate_sha_after_fixture_restore=")
    assert text.index("candidate_sha_after_fixture_restore=") < text.index("python -m pytest -q")


def test_conversational_core_smoke_is_windows_ollama_opt_in():
    source = (ROOT / ".github" / "workflows" / "conversational-core-smoke.yml").read_text(
        encoding="utf-8"
    )

    for required in (
        "workflow_dispatch",
        "self-hosted",
        "Windows",
        "X64",
        "ai-service-desk",
        "ollama",
        "JUP_BUSINESS_LOCAL_QA",
        "qwen3.5:4b",
        "qwen3-embedding:0.6b",
        "pytest",
    ):
        assert required in source

    assert "upload-artifact" not in source
