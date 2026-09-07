from __future__ import annotations

import json
from pathlib import Path

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
