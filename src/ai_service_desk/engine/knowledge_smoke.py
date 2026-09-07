"""Synthetic competition smoke for approved knowledge retrieval."""

from datetime import UTC, datetime
from pathlib import Path

from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.knowledge_retrieval import KnowledgeEngine
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient

CASES = [
    {
        "name": "cigam-access",
        "query": "Nao consigo acessar o CIGAM no ambiente ficticio.",
        "expected_status": "KNOWLEDGE_FOUND",
        "expected_knowledge_id": "KB-SYN-CIGAM-ACCESS-001",
    },
    {
        "name": "siagri-access",
        "query": "Nao consigo acessar o SIAGRI no ambiente ficticio.",
        "expected_status": "KNOWLEDGE_FOUND",
        "expected_knowledge_id": "KB-SYN-SIAGRI-ACCESS-001",
    },
    {
        "name": "draft-only",
        "query": "O CIGAM fecha em uma rotina ficticia ainda em revisao.",
        "expected_status": "NO_APPROVED_KNOWLEDGE",
    },
    {
        "name": "unknown-system",
        "query": "O sistema XYZ esta sem acesso no exemplo ficticio.",
        "expected_status": "NO_APPROVED_KNOWLEDGE",
        "expected_reason": "UNKNOWN_SYSTEM",
    },
    {
        "name": "ambiguous",
        "query": "CIGAM e SIAGRI estao sem acesso no ambiente ficticio.",
        "expected_status": "NO_APPROVED_KNOWLEDGE",
        "expected_reason": "CONTEXTO_AMBIGUO",
    },
]


def _summarize_case(case: dict, result: dict) -> dict:
    knowledge = result.get("knowledge") or {}
    actual_id = knowledge.get("knowledge_id")
    passed = result.get("status") == case["expected_status"]
    if "expected_knowledge_id" in case:
        passed = passed and actual_id == case["expected_knowledge_id"]
    if "expected_reason" in case:
        passed = passed and result.get("reason") == case["expected_reason"]
    return {
        "name": case["name"],
        "expected_status": case["expected_status"],
        "actual_status": result.get("status"),
        "reason": result.get("reason"),
        "expected_knowledge_id": case.get("expected_knowledge_id"),
        "actual_knowledge_id": actual_id,
        "score": result.get("score"),
        "passed": bool(passed),
    }


def run_knowledge_smoke(
    index: str | Path,
    report_path: str | Path,
    base_url: str = "http://127.0.0.1:11434",
) -> dict:
    report = {
        "schema_version": 1,
        "phase": 4,
        "domain": "APPROVED_KNOWLEDGE",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "ok": False,
        "cases": [],
        "privacy": {
            "query_text_included": False,
            "answer_text_included": False,
            "corporate_data_included": False,
        },
    }
    client = None
    try:
        client = OllamaClient(base_url)
        embedder = LocalEmbedder(client)
        engine = KnowledgeEngine(index, client, embedder)
        for case in CASES:
            try:
                result = engine.search(case["query"])
                report["cases"].append(_summarize_case(case, result))
            except (ValueError, RuntimeError, OSError, KeyError) as exc:
                report["cases"].append(
                    {
                        "name": case["name"],
                        "expected_status": case["expected_status"],
                        "actual_status": "EXECUTION_ERROR",
                        "reason": type(exc).__name__,
                        "expected_knowledge_id": case.get("expected_knowledge_id"),
                        "actual_knowledge_id": None,
                        "score": None,
                        "passed": False,
                    }
                )
        report["ok"] = len(report["cases"]) == len(CASES) and all(
            case["passed"] for case in report["cases"]
        )
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        report["error"] = type(exc).__name__
    finally:
        if client:
            client.close()
        atomic_json(Path(report_path), report)
    return report
