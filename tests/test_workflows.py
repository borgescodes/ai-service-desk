from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "real-corpus-smoke.yml"
DEMO_WORKFLOW = ROOT / ".github" / "workflows" / "demo-retrieval-smoke.yml"


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


def test_gitignore_blocks_real_corpus_and_generated_index_files() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for required in (
        "base_ti_preparada.csv",
        "**/documents.jsonl",
        "**/embeddings.npy",
        "phase-2-data/",
    ):
        assert required in text
