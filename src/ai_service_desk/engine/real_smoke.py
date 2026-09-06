from __future__ import annotations

import math
import re

import numpy as np

from ai_service_desk.engine.classification import SYSTEM_ALIASES
from ai_service_desk.engine.index import load_index
from ai_service_desk.engine.validation import normalize_text

THRESHOLD = 0.65


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
