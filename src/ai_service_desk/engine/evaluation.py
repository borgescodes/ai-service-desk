from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from ai_service_desk.engine.classification import ALLOWED_INTENTS

OFFICIAL_STATUSES = {
    "ENCONTRADOS",
    "SEM_EVIDENCIA",
    "SEM_CONTEXTO",
    "CONTEXTO_AMBIGUO",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "query",
    "expected_intent",
    "expected_system",
    "relevant_ticket_ids",
    "must_abstain",
}


def _validate_case(case: object, seen_ids: set[str]) -> dict:
    if not isinstance(case, dict):
        raise ValueError("Caso de avaliacao deve ser objeto JSON.")
    if not REQUIRED_CASE_FIELDS.issubset(case):
        raise ValueError("Caso de avaliacao sem campos obrigatorios.")

    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("Caso de avaliacao possui id invalida.")
    if case_id in seen_ids:
        raise ValueError("Caso de avaliacao possui id duplicada.")
    seen_ids.add(case_id)

    query = case.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 3000:
        raise ValueError("Caso de avaliacao possui query invalida.")

    intent = case.get("expected_intent")
    if not isinstance(intent, str) or intent not in ALLOWED_INTENTS:
        raise ValueError("Caso de avaliacao possui intent invalida.")

    system = case.get("expected_system")
    if not isinstance(system, str) or len(system) > 120:
        raise ValueError("Caso de avaliacao possui system invalido.")

    relevant = case.get("relevant_ticket_ids")
    if not isinstance(relevant, list) or any(
        not isinstance(value, str) or not value for value in relevant
    ):
        raise ValueError("Caso de avaliacao possui relevant_ticket_ids invalidos.")

    must_abstain = case.get("must_abstain")
    if not isinstance(must_abstain, bool):
        raise ValueError("Caso de avaliacao possui must_abstain invalido.")
    if must_abstain and relevant:
        raise ValueError("Caso com abstain nao pode declarar documento relevante.")

    expected_status = case.get("expected_status")
    if expected_status is not None and expected_status not in OFFICIAL_STATUSES:
        raise ValueError("Caso de avaliacao possui status invalido.")

    return dict(case)


def load_evaluation_cases(path: str | Path) -> list[dict]:
    source = Path(path)
    cases: list[dict] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON invalido no caso de avaliacao na linha {line_number}.") from exc
        cases.append(_validate_case(case, seen_ids))
    if not cases:
        raise ValueError("Benchmark de avaliacao vazio.")
    return cases


def _ratio(numerator: int | float, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _result_map(results: list[dict]) -> dict[str, dict]:
    mapped: dict[str, dict] = {}
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("Resultado de avaliacao deve ser objeto.")
        result_id = result.get("id")
        if not isinstance(result_id, str) or not result_id:
            raise ValueError("Resultado de avaliacao possui id invalida.")
        if result_id in mapped:
            raise ValueError("Resultado de avaliacao possui id duplicada.")
        mapped[result_id] = result
    return mapped


def compute_metrics(cases: list[dict], results: list[dict], k: int = 3) -> dict:
    if not isinstance(k, int) or not 1 <= k <= 20:
        raise ValueError("k deve estar entre 1 e 20.")

    mapped = _result_map(results)
    case_ids = [str(case.get("id", "")) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Casos de avaliacao possuem id duplicada.")
    if set(case_ids) != set(mapped):
        raise ValueError("Casos e resultados de avaliacao nao correspondem.")

    intent_correct = 0
    system_correct = 0
    relevant_cases = 0
    hit_at_1 = 0
    hit_at_k = 0
    reciprocal_rank = 0.0
    precision_at_k = 0.0
    abstention_cases = 0
    correct_abstentions = 0
    unsafe_accept_count = 0
    system_leakage_count = 0
    ambiguous_context_failures = 0
    unknown_system_failures = 0
    execution_failures = 0
    latencies: list[float] = []

    for case in cases:
        result = mapped[str(case["id"])]
        failed = bool(result.get("error"))
        if failed:
            execution_failures += 1

        if not failed and result.get("actual_intent") == case.get("expected_intent"):
            intent_correct += 1
        if not failed and result.get("actual_system") == case.get("expected_system"):
            system_correct += 1

        candidates = result.get("candidate_ids", []) if not failed else []
        if not isinstance(candidates, list):
            raise ValueError("candidate_ids deve ser lista.")
        relevant = set(case.get("relevant_ticket_ids", []))
        if relevant:
            relevant_cases += 1
            if candidates and candidates[0] in relevant:
                hit_at_1 += 1
            top_candidates = candidates[:k]
            if any(candidate in relevant for candidate in top_candidates):
                hit_at_k += 1
            first_relevant_rank = next(
                (
                    position
                    for position, candidate in enumerate(candidates, 1)
                    if candidate in relevant
                ),
                None,
            )
            if first_relevant_rank is not None:
                reciprocal_rank += 1.0 / first_relevant_rank
            precision_at_k += sum(candidate in relevant for candidate in top_candidates) / k

        must_abstain = bool(case.get("must_abstain"))
        if must_abstain:
            abstention_cases += 1
            status = result.get("status") if not failed else None
            expected_status = case.get("expected_status")
            accepted = bool(candidates) or status == "ENCONTRADOS"
            if accepted:
                unsafe_accept_count += 1
            status_ok = expected_status is None or status == expected_status
            if not failed and not accepted and status_ok:
                correct_abstentions += 1

        if bool(result.get("system_leakage")):
            system_leakage_count += 1

        expected_status = case.get("expected_status")
        actual_status = result.get("status") if not failed else None
        if expected_status == "CONTEXTO_AMBIGUO" and actual_status != expected_status:
            ambiguous_context_failures += 1
        if expected_status == "SEM_CONTEXTO" and actual_status != expected_status:
            unknown_system_failures += 1

        latency = result.get("total_seconds")
        if (
            not failed
            and isinstance(latency, (int, float))
            and not isinstance(latency, bool)
            and math.isfinite(latency)
            and latency >= 0
        ):
            latencies.append(float(latency))

    total_cases = len(cases)
    p50 = float(np.percentile(latencies, 50)) if latencies else None
    p95 = float(np.percentile(latencies, 95)) if latencies else None
    return {
        "cases": total_cases,
        "relevant_cases": relevant_cases,
        "abstention_cases": abstention_cases,
        "intent_accuracy": _ratio(intent_correct, total_cases),
        "system_accuracy": _ratio(system_correct, total_cases),
        "hit_at_1": _ratio(hit_at_1, relevant_cases),
        "hit_at_3": _ratio(hit_at_k, relevant_cases),
        "mrr": _ratio(reciprocal_rank, relevant_cases),
        "precision_at_3": _ratio(precision_at_k, relevant_cases),
        "correct_abstention_rate": _ratio(correct_abstentions, abstention_cases),
        "unsafe_accept_count": unsafe_accept_count,
        "system_leakage_count": system_leakage_count,
        "ambiguous_context_failures": ambiguous_context_failures,
        "unknown_system_failures": unknown_system_failures,
        "execution_failures": execution_failures,
        "p50_total_seconds": p50,
        "p95_total_seconds": p95,
    }
