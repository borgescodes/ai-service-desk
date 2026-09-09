import json
from datetime import UTC, datetime
from pathlib import Path

from ai_service_desk.engine.access_request import AccessRequestContext, SessionIdentity
from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.execution import ExecutionEngine, FakeActionExecutor
from ai_service_desk.engine.index import atomic_json
from ai_service_desk.engine.policy import MACHINE_CODE_RE, PolicyEngine
from ai_service_desk.engine.request_lifecycle import REQUEST_STATES, RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)

CASE_FIELDS = frozenset(
    {
        "case_name",
        "requested_role",
        "human_decision",
        "executor_mode",
        "revalidation_deny",
        "expected_state",
        "expected_result_code",
        "expected_error_code",
        "expected_executor_calls",
    }
)
FLOWS = {
    "approved_completed": ("SOLICITANTE", "approve", "success", False),
    "approved_failed": ("SOLICITANTE", "approve", "failure", False),
    "approved_exception": ("SOLICITANTE", "approve", "exception", False),
    "rejected": ("SOLICITANTE", "reject", "success", False),
    "denied_creation": ("ADMIN", "none", "success", False),
    "denied_revalidation": ("SOLICITANTE", "approve", "success", True),
}


def load_controlled_execution_cases(path: str | Path) -> list[dict]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError("Casos devem ser arquivo JSONL UTF-8 valido.") from exc
    rows = []
    seen = set()
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError("JSON invalido nos casos sinteticos.") from exc
        if not isinstance(row, dict) or set(row) != CASE_FIELDS:
            raise ValueError("Campos invalidos no caso da Fase 8.")
        name = row["case_name"]
        if not isinstance(name, str) or name not in FLOWS or name in seen:
            raise ValueError("Fluxo desconhecido ou duplicado.")
        flow = tuple(
            row[field]
            for field in ("requested_role", "human_decision", "executor_mode", "revalidation_deny")
        )
        if type(row["revalidation_deny"]) is not bool or flow != FLOWS[name]:
            raise ValueError("Configuracao fora dos seis fluxos sinteticos.")
        if (
            not isinstance(row["expected_state"], str)
            or row["expected_state"] not in REQUEST_STATES
        ):
            raise ValueError("Estado esperado invalido.")
        for field in ("expected_result_code", "expected_error_code"):
            value = row[field]
            if value is not None and (
                not isinstance(value, str) or MACHINE_CODE_RE.fullmatch(value) is None
            ):
                raise ValueError("Codigo esperado invalido.")
        if type(row["expected_executor_calls"]) is not int or row[
            "expected_executor_calls"
        ] not in {0, 1}:
            raise ValueError("Contagem de execucoes esperada invalida.")
        seen.add(name)
        rows.append(row)
    if len(rows) != 6:
        raise ValueError("Smoke da Fase 8 exige exatamente seis fluxos sinteticos.")
    return rows


def _run_case(case):
    stamp = datetime(2026, 9, 9, 12, tzinfo=UTC)
    repository = InMemoryRequestRepository()
    policy = PolicyEngine()
    lifecycle = RequestLifecycleService(repository, policy, clock=lambda: stamp)
    context = AccessRequestContext(
        requester=SessionIdentity(
            "synthetic.requester",
            "Synthetic Requester",
            "requester@example.invalid",
            "Revenda Sintetica",
        ),
        system="CDM",
        intent="PROBLEMA_ACESSO",
        requested_role=case["requested_role"],
        purpose="solicitar materiais sinteticos",
        knowledge_id="KB-SYN-PHASE8",
        playbook_id="PB-SYN-PHASE8",
        playbook_version=1,
        step_id="STEP-SYN-PHASE8",
        capability="CDM_ACCESS_REQUEST",
    )
    technician = TechnicianIdentity(
        "TECH-SYN-001", "synthetic.tech", "Synthetic Technician", "technician@example.invalid"
    )
    registry = TechnicianAuthorizationRegistry(
        [TechnicianRegistryEntry(technician, frozenset({"CDM_ACCESS_REQUEST"}))]
    )
    approval = ApprovalService(repository, lifecycle, registry, clock=lambda: stamp)
    executor = FakeActionExecutor(case["executor_mode"])
    record = lifecycle.create_request(context)
    if case["human_decision"] == "approve":
        record = approval.approve(record.request_id, technician, expected_version=record.version)
        revalidation = PolicyEngine([]) if case["revalidation_deny"] else policy
        engine = ExecutionEngine(repository, lifecycle, revalidation, executor, clock=lambda: stamp)
        record = engine.execute(record.request_id, expected_version=record.version)
    elif case["human_decision"] == "reject":
        record = approval.reject(record.request_id, technician, expected_version=record.version)
    return {
        "case_name": case["case_name"],
        "final_state": record.state,
        "reason_code": repository.audit_for(record.request_id)[-1].reason_code,
        "result_code": record.execution_result_code,
        "error_code": record.execution_error_code,
        "executor_calls": len(executor.calls),
        "passed": (
            record.state == case["expected_state"]
            and record.execution_result_code == case["expected_result_code"]
            and record.execution_error_code == case["expected_error_code"]
            and len(executor.calls) == case["expected_executor_calls"]
        ),
    }


def run_controlled_execution_smoke(cases_path: str | Path, report_path: str | Path) -> dict:
    report = {"schema_version": 1, "phase": 8, "ok": False, "cases": []}
    try:
        cases = load_controlled_execution_cases(cases_path)
    except ValueError:
        report["error_code"] = "CONTROLLED_EXECUTION_CASES_INVALID"
    else:
        for case in cases:
            try:
                report["cases"].append(_run_case(case))
            except Exception:
                report["cases"].append(
                    {
                        "case_name": case["case_name"],
                        "final_state": None,
                        "reason_code": "CONTROLLED_EXECUTION_SMOKE_ERROR",
                        "result_code": None,
                        "error_code": "CONTROLLED_EXECUTION_SMOKE_ERROR",
                        "executor_calls": 0,
                        "passed": False,
                    }
                )
        report["ok"] = len(report["cases"]) == 6 and all(row["passed"] for row in report["cases"])
    atomic_json(Path(report_path), report)
    return report
