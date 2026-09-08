import json
from datetime import UTC, datetime
from pathlib import Path

from ai_service_desk.engine.access_request import SessionIdentity, prepare_access_request
from ai_service_desk.engine.confidence import assess_confidence
from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.playbook_resolution import action_proposal_descriptor
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.triage import TriageState

CASE_FIELDS = {
    "case_name",
    "username",
    "name",
    "email",
    "area",
    "problem_text",
    "expected_preparation_status",
    "expected_role",
    "expected_preparation_reason_code",
    "expected_policy_decision",
    "expected_policy_reason_code",
    "expected_confidence",
    "expected_confidence_reason_codes",
}


def load_policy_cases(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ValueError("Arquivo de casos da Fase 7 nao encontrado.")
    rows: list[dict] = []
    seen: set[str] = set()
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON invalido na linha {line_number}.") from exc
                if not isinstance(raw, dict) or set(raw) != CASE_FIELDS:
                    raise ValueError("Campos invalidos no caso da Fase 7.")
                name = raw["case_name"]
                if not isinstance(name, str) or not name.strip() or name in seen:
                    raise ValueError("case_name invalido ou duplicado.")
                for field in (
                    "username",
                    "name",
                    "email",
                    "area",
                    "problem_text",
                    "expected_preparation_status",
                    "expected_role",
                    "expected_preparation_reason_code",
                    "expected_policy_decision",
                    "expected_policy_reason_code",
                    "expected_confidence",
                ):
                    if not isinstance(raw[field], str):
                        raise ValueError(f"{field} deve ser texto.")
                codes = raw["expected_confidence_reason_codes"]
                if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
                    raise ValueError("expected_confidence_reason_codes deve ser lista de textos.")
                seen.add(name)
                rows.append(dict(raw))
    except UnicodeDecodeError as exc:
        raise ValueError("Casos da Fase 7 devem ser JSONL UTF-8 valido.") from exc
    if len(rows) != 15:
        raise ValueError("Smoke da Fase 7 exige exatamente 15 casos sinteticos.")
    return rows


def _cdm_descriptor() -> dict:
    return action_proposal_descriptor(
        "KB-SYN-CDM-ACCESS-001",
        {
            "playbook_id": "PB-SYN-CDM-ACCESS-001",
            "playbook_version": 1,
        },
        {
            "step_id": "STEP-CDM-ACCESS-01",
            "type": "ACTION_PROPOSAL",
            "capability": "CDM_ACCESS_REQUEST",
        },
    )


def _triage(case: dict) -> TriageState:
    return TriageState(
        version=1,
        session_id=f"phase7-{case['case_name']}",
        status="ANSWERED",
        turn_count=1,
        clarification_count=0,
        problem_text=case["problem_text"],
        intent="PROBLEMA_ACESSO",
        system="CDM",
        entities={},
        confidence=0.9,
        pending_field="",
        asked_fields=(),
    )


def _safe_case_result(
    case: dict,
    actual_preparation_status: str,
    actual_role: str,
    actual_preparation_reason_code: str,
    actual_policy_decision: str,
    actual_policy_reason_code: str,
    actual_confidence: str,
    actual_confidence_reason_codes: tuple[str, ...],
) -> dict:
    expected_codes = tuple(case["expected_confidence_reason_codes"])
    passed = (
        actual_preparation_status == case["expected_preparation_status"]
        and actual_role == case["expected_role"]
        and actual_preparation_reason_code == case["expected_preparation_reason_code"]
        and actual_policy_decision == case["expected_policy_decision"]
        and actual_policy_reason_code == case["expected_policy_reason_code"]
        and actual_confidence == case["expected_confidence"]
        and actual_confidence_reason_codes == expected_codes
    )
    return {
        "case_name": case["case_name"],
        "actual_preparation_status": actual_preparation_status,
        "actual_role": actual_role,
        "actual_preparation_reason_code": actual_preparation_reason_code,
        "actual_policy_decision": actual_policy_decision,
        "actual_policy_reason_code": actual_policy_reason_code,
        "actual_confidence": actual_confidence,
        "actual_confidence_reason_codes": list(actual_confidence_reason_codes),
        "passed": bool(passed),
    }


def run_policy_smoke(cases_path: str | Path, report_path: str | Path) -> dict:
    report = {
        "schema_version": 1,
        "phase": 7,
        "domain": "POLICY_ENGINE",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "ok": False,
        "cases": [],
        "privacy": {
            "identity_included": False,
            "raw_problem_text_included": False,
            "purpose_included": False,
            "capability_included": False,
            "corporate_data_included": False,
        },
    }
    try:
        cases = load_policy_cases(cases_path)
        engine = PolicyEngine()
        descriptor = _cdm_descriptor()
        for case in cases:
            try:
                requester = SessionIdentity(
                    username=case["username"],
                    name=case["name"],
                    email=case["email"],
                    area=case["area"],
                )
                preparation = prepare_access_request(requester, _triage(case), descriptor)
                actual_policy_decision = ""
                actual_policy_reason_code = ""
                actual_confidence = ""
                actual_confidence_reason_codes: tuple[str, ...] = ()
                if preparation.status == "READY":
                    if preparation.context is None:
                        raise ValueError("READY sem AccessRequestContext.")
                    decision = engine.evaluate(preparation.context)
                    confidence = assess_confidence(preparation.context)
                    actual_policy_decision = decision.decision
                    actual_policy_reason_code = decision.reason_code
                    actual_confidence = confidence.level
                    actual_confidence_reason_codes = confidence.reason_codes
                elif preparation.context is not None:
                    raise ValueError("NEEDS_CLARIFICATION com contexto preenchido.")
                report["cases"].append(
                    _safe_case_result(
                        case,
                        preparation.status,
                        preparation.requested_role,
                        preparation.reason_code,
                        actual_policy_decision,
                        actual_policy_reason_code,
                        actual_confidence,
                        actual_confidence_reason_codes,
                    )
                )
            except (ValueError, RuntimeError, OSError, KeyError, AssertionError) as exc:
                report["cases"].append(
                    {
                        "case_name": case["case_name"],
                        "actual_preparation_status": "EXECUTION_ERROR",
                        "actual_role": "",
                        "actual_preparation_reason_code": type(exc).__name__,
                        "actual_policy_decision": "",
                        "actual_policy_reason_code": "",
                        "actual_confidence": "",
                        "actual_confidence_reason_codes": [],
                        "passed": False,
                    }
                )
        report["ok"] = len(report["cases"]) == 15 and all(
            row["passed"] for row in report["cases"]
        )
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        report["error"] = type(exc).__name__
    finally:
        atomic_json(Path(report_path), report)
    return report
