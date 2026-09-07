from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from ai_service_desk.engine.classification import SYSTEM_ALIASES
from ai_service_desk.engine.corpus import (
    audit_corpus,
    ensure_external_path,
    load_corpus_manifest,
    write_safe_report,
)
from ai_service_desk.engine.data import load_corpus
from ai_service_desk.engine.index import build_index, load_index
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.retrieval import RetrievalEngine
from ai_service_desk.engine.validation import normalize_text

THRESHOLD = 0.65
REAL_SMOKE_CASES = [
    {
        "name": "cigam",
        "query": "No CIGAM aparece erro ao abrir uma rotina de exemplo.",
        "expected_system": "CIGAM",
        "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
    },
    {
        "name": "siagri",
        "query": "No SIAGRI aparece erro ao abrir uma rotina de exemplo.",
        "expected_system": "SIAGRI",
        "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
    },
    {
        "name": "unknown",
        "query": "No sistema XYZ aparece um erro de exemplo.",
        "expected_system": "XYZ",
        "allowed_statuses": ["SEM_CONTEXTO"],
        "expected_candidates": 0,
    },
    {
        "name": "ambiguous",
        "query": "CIGAM e SIAGRI apresentam um erro de exemplo.",
        "allowed_statuses": ["CONTEXTO_AMBIGUO"],
        "expected_candidates": 0,
    },
    {
        "name": "printing",
        "query": "A impressora de exemplo nao imprime.",
        "expected_intent": "PROBLEMA_IMPRESSAO",
        "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
    },
]


def validate_real_index(index_directory, expected: dict) -> dict:
    _, matrix, manifest = load_index(index_directory)
    checks = {
        "rows": manifest["rows"],
        "dimensions": manifest["dimensions"],
        "model": manifest["model"],
        "model_digest": manifest["model_digest"],
        "recipe": manifest["recipe"],
        "source_hash": manifest["source_hash"],
    }
    for key, expected_value in expected.items():
        if key in checks and checks[key] != expected_value:
            raise ValueError(f"Indice real divergente no campo agregado: {key}.")

    values = np.asarray(matrix, dtype=np.float32)
    finite = bool(np.isfinite(values).all())
    norms = np.linalg.norm(values, axis=1)
    normalized = bool(np.allclose(norms, 1, atol=1e-4))
    if not finite or not normalized:
        raise ValueError("Indice real contem vetores invalidos.")
    self_similarity = float(values[0] @ values[0]) if len(values) else math.nan
    return {
        "rows": int(manifest["rows"]),
        "shape": [int(values.shape[0]), int(values.shape[1])],
        "dimensions": int(manifest["dimensions"]),
        "model": str(manifest["model"]),
        "model_digest": str(manifest["model_digest"]),
        "recipe": str(manifest["recipe"]),
        "source_hash": str(manifest["source_hash"]),
        "complete": bool(manifest["complete"]),
        "finite": finite,
        "normalized": normalized,
        "self_similarity": self_similarity,
    }


def _contains_alias(text: str, alias: str) -> bool:
    normalized_alias = normalize_text(alias)
    return bool(
        normalized_alias
        and re.search(
            rf"(?<!\w){re.escape(normalized_alias)}(?!\w)",
            normalize_text(text),
        )
    )


def _candidate_matches_system(candidate: dict, system: str) -> bool:
    aliases = SYSTEM_ALIASES.get(system, (system,))
    combined = " ".join(
        str(candidate.get(key, "")) for key in ("catalogo", "area", "item", "title", "texto_busca")
    )
    return any(_contains_alias(combined, alias) for alias in aliases)


def run_safe_queries(engine, cases: list[dict]) -> list[dict]:
    summaries: list[dict] = []
    for case in cases:
        result = engine.search(case["query"])
        classification = result.get("classification", {})
        candidates = result.get("candidates", [])
        expected_system = case.get("expected_system", "")
        expected_intent = case.get("expected_intent", "")
        actual_system = str(classification.get("system", ""))
        actual_intent = str(classification.get("intent", ""))
        status = str(result.get("status", ""))
        status_ok = status in case.get("allowed_statuses", [])
        system_ok = not expected_system or actual_system == expected_system
        intent_ok = not expected_intent or actual_intent == expected_intent
        expected_candidates = case.get("expected_candidates")
        candidate_count_ok = expected_candidates is None or len(candidates) == expected_candidates
        candidate_systems_ok = True
        if expected_system and candidates:
            candidate_systems_ok = all(
                _candidate_matches_system(candidate, expected_system) for candidate in candidates
            )
        summary = {
            "name": str(case["name"]),
            "expected_system": str(expected_system),
            "expected_intent": str(expected_intent),
            "actual_system": actual_system,
            "actual_intent": actual_intent,
            "status": status,
            "candidate_count": int(len(candidates)),
            "best_score": (
                float(result["best_score"]) if result.get("best_score") is not None else None
            ),
            "pool_size": int(result.get("pool_size", 0)),
            "status_ok": bool(status_ok),
            "system_ok": bool(system_ok),
            "intent_ok": bool(intent_ok),
            "candidate_count_ok": bool(candidate_count_ok),
            "candidate_systems_ok": bool(candidate_systems_ok),
        }
        summary["ok"] = all(
            summary[key]
            for key in (
                "status_ok",
                "system_ok",
                "intent_ok",
                "candidate_count_ok",
                "candidate_systems_ok",
            )
        )
        summaries.append(summary)
    return summaries


def build_real_smoke_report(corpus: dict, index: dict, queries: list[dict]) -> dict:
    return {
        "version": 1,
        "ok": bool(corpus.get("manifest_match"))
        and bool(index.get("complete"))
        and all(bool(query.get("ok")) for query in queries),
        "corpus": corpus,
        "index": index,
        "queries": queries,
        "threshold": THRESHOLD,
        "privacy": {
            "contains_ticket_content": False,
            "contains_ticket_identifiers": False,
            "history_displayed": False,
        },
    }


def _run_smoke(
    corpus_path,
    index_directory,
    report_path,
    base_url,
    checkout,
    expected: dict,
    corpus_report: dict,
) -> dict:
    client = OllamaClient(base_url)
    try:
        embedder = LocalEmbedder(client)
        client.model_info("qwen3.5:4b")
        data = load_corpus(corpus_path)
        build_index(data, index_directory, embedder)
        engine = RetrievalEngine(index_directory, client, embedder, THRESHOLD)
        index_expected = {
            "rows": expected["rows"],
            "dimensions": embedder.dimensions,
            "model": embedder.model,
            "model_digest": embedder.digest,
            "recipe": "texto_busca-plain-v1",
            "source_hash": expected["canonical_sha256"],
        }
        index_report = validate_real_index(index_directory, index_expected)
        query_report = run_safe_queries(engine, REAL_SMOKE_CASES)
        report = build_real_smoke_report(corpus_report, index_report, query_report)
        write_safe_report(report_path, report)
        return report
    finally:
        client.close()


def run_real_smoke(
    corpus_path,
    manifest_path,
    index_directory,
    report_path,
    base_url,
    checkout,
) -> dict:
    corpus_path = ensure_external_path(corpus_path, checkout)
    index_directory = ensure_external_path(index_directory, checkout)
    report_path = ensure_external_path(report_path, checkout)
    corpus_report = audit_corpus(corpus_path, manifest_path)
    manifest = load_corpus_manifest(manifest_path)
    return _run_smoke(
        corpus_path,
        index_directory,
        report_path,
        base_url,
        checkout,
        {
            "rows": manifest["expected"]["rows"],
            "canonical_sha256": manifest["expected"]["canonical_sha256"],
        },
        corpus_report,
    )


def run_demo_smoke(
    corpus_path,
    subset_report_path,
    index_directory,
    report_path,
    base_url,
    checkout,
) -> dict:
    corpus_path = ensure_external_path(corpus_path, checkout)
    subset_report_path = ensure_external_path(subset_report_path, checkout)
    index_directory = ensure_external_path(index_directory, checkout)
    report_path = ensure_external_path(report_path, checkout)
    subset_report = json.loads(Path(subset_report_path).read_text(encoding="utf-8"))
    rows = subset_report.get("selected_rows")
    canonical_hash = subset_report.get("subset_canonical_sha256")
    if not isinstance(rows, int) or rows <= 0 or not isinstance(canonical_hash, str) or not canonical_hash:
        raise ValueError("Relatorio agregado do subset de demo invalido.")
    return _run_smoke(
        corpus_path,
        index_directory,
        report_path,
        base_url,
        checkout,
        {"rows": rows, "canonical_sha256": canonical_hash},
        {"rows": rows, "manifest_match": True},
    )
