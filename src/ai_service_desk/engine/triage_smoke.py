import json
from datetime import UTC, datetime
from pathlib import Path

from ai_service_desk.engine.classification import classify_ticket
from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.knowledge_retrieval import KnowledgeEngine
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.triage import MAX_USER_TURNS, TriageEngine

REQUIRED_CASE_FIELDS = {
    "case_name",
    "turns",
    "expected_status",
    "expected_knowledge_id",
    "expected_turn_count",
    "expected_clarification_count",
}
OPTIONAL_CASE_FIELDS = {"expected_reason", "requires_interleaved_control"}


def load_triage_cases(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ValueError("Arquivo de casos de triagem nao encontrado.")
    rows: list[dict] = []
    seen: set[str] = set()
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON invalido na linha {line_number}.") from exc
            if not isinstance(case, dict):
                raise ValueError("Caso de triagem deve ser objeto JSON.")
            keys = set(case)
            invalid_extra = keys - REQUIRED_CASE_FIELDS - OPTIONAL_CASE_FIELDS
            if not REQUIRED_CASE_FIELDS <= keys or invalid_extra:
                raise ValueError("Campos invalidos no caso de triagem.")
            name = case["case_name"]
            if not isinstance(name, str) or not name.strip() or name in seen:
                raise ValueError("case_name invalido ou duplicado.")
            turns = case["turns"]
            if not isinstance(turns, list) or not 1 <= len(turns) <= MAX_USER_TURNS:
                raise ValueError("turns deve conter de 1 a 3 mensagens.")
            if any(not isinstance(turn, str) or not turn.strip() for turn in turns):
                raise ValueError("turn de triagem invalido.")
            seen.add(name)
            rows.append(case)
    if len(rows) != 10:
        raise ValueError("Smoke da Fase 5 exige exatamente 10 casos sinteticos.")
    return rows


def _execute_turns(engine: TriageEngine, turns: list[str]):
    state = engine.initial_state()
    result = None
    for message in turns:
        state, result = engine.step(state, message)
        if result["status"] != "NEEDS_CLARIFICATION":
            break
    if result is None:
        raise ValueError("Caso de triagem sem resultado.")
    return state, result


def _summarize(case: dict, state, result: dict, isolation_ok: bool = True) -> dict:
    actual_id = (result.get("knowledge") or {}).get("knowledge_id")
    passed = result.get("status") == case["expected_status"]
    if "expected_reason" in case:
        passed = passed and result.get("reason") == case["expected_reason"]
    passed = passed and actual_id == case.get("expected_knowledge_id")
    passed = passed and state.turn_count == case["expected_turn_count"]
    passed = passed and state.clarification_count == case["expected_clarification_count"]
    passed = passed and isolation_ok
    return {
        "case_name": case["case_name"],
        "expected_status": case["expected_status"],
        "actual_status": result.get("status"),
        "reason": result.get("reason"),
        "expected_knowledge_id": case.get("expected_knowledge_id"),
        "actual_knowledge_id": actual_id,
        "turn_count": state.turn_count,
        "clarification_count": state.clarification_count,
        "passed": bool(passed),
    }


def run_triage_smoke(
    index: str | Path,
    cases_path: str | Path,
    report_path: str | Path,
    base_url: str = "http://127.0.0.1:11434",
) -> dict:
    report = {
        "schema_version": 1,
        "phase": 5,
        "domain": "CONVERSATIONAL_TRIAGE",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "ok": False,
        "cases": [],
        "privacy": {
            "raw_text_included": False,
            "approved_content_included": False,
            "corporate_data_included": False,
        },
    }
    client = None
    try:
        cases = load_triage_cases(cases_path)
        client = OllamaClient(base_url)
        embedder = LocalEmbedder(client)
        knowledge = KnowledgeEngine(index, client, embedder)

        def classifier(text: str):
            return classify_ticket(text, client.chat)

        for case in cases:
            try:
                isolation_ok = True
                if case.get("requires_interleaved_control"):
                    engine = TriageEngine("synthetic-session-a", knowledge, classifier)
                    state = engine.initial_state()
                    state, first = engine.step(state, case["turns"][0])
                    if first["status"] != "NEEDS_CLARIFICATION":
                        raise ValueError("Caso de isolamento nao solicitou esclarecimento.")
                    snapshot = state
                    control = TriageEngine("synthetic-session-b", knowledge, classifier)
                    _, control_result = _execute_turns(
                        control,
                        ["A impressora ficticia nao imprime."],
                    )
                    isolation_ok = (
                        state == snapshot and control_result["status"] == "KNOWLEDGE_FOUND"
                    )
                    state, result = engine.step(state, case["turns"][1])
                else:
                    engine = TriageEngine(
                        f"synthetic-{case['case_name']}",
                        knowledge,
                        classifier,
                    )
                    state, result = _execute_turns(engine, case["turns"])
                report["cases"].append(_summarize(case, state, result, isolation_ok))
            except (ValueError, RuntimeError, OSError, KeyError, AssertionError) as exc:
                report["cases"].append(
                    {
                        "case_name": case["case_name"],
                        "expected_status": case["expected_status"],
                        "actual_status": "EXECUTION_ERROR",
                        "reason": type(exc).__name__,
                        "expected_knowledge_id": case.get("expected_knowledge_id"),
                        "actual_knowledge_id": None,
                        "turn_count": 0,
                        "clarification_count": 0,
                        "passed": False,
                    }
                )
        report["ok"] = len(report["cases"]) == 10 and all(
            case["passed"] for case in report["cases"]
        )
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        report["error"] = type(exc).__name__
    finally:
        if client is not None:
            client.close()
        atomic_json(Path(report_path), report)
    return report
