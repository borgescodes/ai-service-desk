import json
import threading
from pathlib import Path

from ai_service_desk.engine.access_request import (
    CDM_ACCESS_CAPABILITY,
    CDM_ACCESS_INTENT,
    CDM_SYSTEM,
    AccessRequestContext,
    SessionIdentity,
)
from ai_service_desk.engine.approval import ApprovalService
from ai_service_desk.engine.cdm_execution import CDMActionExecutor
from ai_service_desk.engine.execution import ExecutionEngine
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import RequestLifecycleService
from ai_service_desk.engine.request_repository import InMemoryRequestRepository
from ai_service_desk.engine.technician_authorization import (
    TechnicianAuthorizationRegistry,
    TechnicianIdentity,
    TechnicianRegistryEntry,
)
from ai_service_desk.integrations.cdm import CDMAdapter, CDMIdempotencyConflictError
from ai_service_desk.integrations.cdm_fake_api import build_cdm_server

CASE_IDS = (
    "CREATE_NEW_ACCESS",
    "ACCESS_ALREADY_EXISTS",
    "IDEMPOTENT_REPLAY",
    "IDEMPOTENCY_CONFLICT",
    "SERVICE_UNAUTHORIZED",
    "REMOTE_INTERNAL_ERROR",
)


def _load_cases(path: Path) -> list[dict[str, str]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if type(value) is not dict or set(value) != {"case_id", "expected"}:
                    raise ValueError("Fixture da Fase 9 possui schema invalido.")
                if not all(isinstance(value[key], str) and value[key] for key in value):
                    raise ValueError("Fixture da Fase 9 possui valores invalidos.")
                rows.append(value)
    if tuple(row["case_id"] for row in rows) != CASE_IDS:
        raise ValueError("Fixture da Fase 9 deve conter exatamente os seis casos canonicos.")
    return rows


def _context(case_id: str) -> AccessRequestContext:
    slug = case_id.lower().replace("_", ".")
    return AccessRequestContext(
        requester=SessionIdentity(
            username=f"phase9.{slug}",
            name=f"Phase 9 {case_id}",
            email=f"phase9.{slug}@example.invalid",
            area="Revenda Sintetica",
        ),
        system=CDM_SYSTEM,
        intent=CDM_ACCESS_INTENT,
        requested_role="SOLICITANTE",
        purpose="preciso de acesso ao CDM para solicitar materiais",
        knowledge_id="KB-SYN-PHASE9",
        playbook_id="PB-SYN-PHASE9",
        playbook_version=1,
        step_id="STEP-SYN-PHASE9",
        capability=CDM_ACCESS_CAPABILITY,
    )


def _build_phase8_services():
    repository = InMemoryRequestRepository()
    policy_engine = PolicyEngine()
    lifecycle = RequestLifecycleService(repository, policy_engine=policy_engine)
    technician = TechnicianIdentity(
        technician_id="TECH-CDM-PHASE9",
        username="tech.cdm.phase9",
        name="Tecnico CDM Phase 9",
        email="tech.cdm.phase9@example.invalid",
    )
    registry = TechnicianAuthorizationRegistry(
        [TechnicianRegistryEntry(technician, frozenset({CDM_ACCESS_CAPABILITY}))]
    )
    approval = ApprovalService(repository, lifecycle, registry)
    return repository, policy_engine, lifecycle, approval, technician


def _execute_case(context, adapter, repository, policy_engine, lifecycle, approval, technician):
    pending = lifecycle.create_request(context)
    approved = approval.approve(pending.request_id, technician, expected_version=pending.version)
    engine = ExecutionEngine(
        repository,
        lifecycle,
        policy_engine,
        CDMActionExecutor(adapter),
    )
    return engine.execute(approved.request_id, expected_version=approved.version)


def run_cdm_integration_smoke(
    cases_path: Path,
    report_path: Path,
    service_token: str,
) -> dict[str, object]:
    cases = _load_cases(Path(cases_path))
    repository, policy_engine, lifecycle, approval, technician = _build_phase8_services()
    server = build_cdm_server(
        "127.0.0.1",
        0,
        service_token,
        fail_request_ids={"REQ-000004"},
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results: list[dict[str, object]] = []
    try:
        host, port = server.server_address
        base_url = f"http://{host}:{port}"
        adapter = CDMAdapter(base_url, service_token)

        for case in cases:
            case_id = case["case_id"]
            expected = case["expected"]
            actual = "UNSET"

            if case_id == "CREATE_NEW_ACCESS":
                record = _execute_case(
                    _context(case_id),
                    adapter,
                    repository,
                    policy_engine,
                    lifecycle,
                    approval,
                    technician,
                )
                actual = record.execution_result_code or record.execution_error_code or record.state
            elif case_id == "ACCESS_ALREADY_EXISTS":
                context = _context(case_id)
                adapter.create_access(
                    "REQ-800001",
                    context.requester.username,
                    context.requester.email,
                    "SOLICITANTE",
                )
                record = _execute_case(
                    context, adapter, repository, policy_engine, lifecycle, approval, technician
                )
                actual = record.execution_result_code or record.execution_error_code or record.state
            elif case_id == "IDEMPOTENT_REPLAY":
                context = _context(case_id)
                first = adapter.create_access(
                    "REQ-900001",
                    context.requester.username,
                    context.requester.email,
                    "SOLICITANTE",
                )
                second = adapter.create_access(
                    "REQ-900001",
                    context.requester.username,
                    context.requester.email,
                    "SOLICITANTE",
                )
                actual = (
                    second.outcome if first.access_id == second.access_id else "ACCESS_ID_MISMATCH"
                )
            elif case_id == "IDEMPOTENCY_CONFLICT":
                context = _context(case_id)
                adapter.create_access(
                    "REQ-900002",
                    context.requester.username,
                    context.requester.email,
                    "SOLICITANTE",
                )
                try:
                    adapter.create_access(
                        "REQ-900002",
                        "different.user",
                        context.requester.email,
                        "SOLICITANTE",
                    )
                except CDMIdempotencyConflictError as exc:
                    actual = exc.reason_code
            elif case_id == "SERVICE_UNAUTHORIZED":
                record = _execute_case(
                    _context(case_id),
                    CDMAdapter(base_url, "wrong-runtime-token"),
                    repository,
                    policy_engine,
                    lifecycle,
                    approval,
                    technician,
                )
                actual = record.execution_error_code or record.execution_result_code or record.state
            elif case_id == "REMOTE_INTERNAL_ERROR":
                record = _execute_case(
                    _context(case_id),
                    adapter,
                    repository,
                    policy_engine,
                    lifecycle,
                    approval,
                    technician,
                )
                actual = record.execution_error_code or record.execution_result_code or record.state

            results.append(
                {
                    "case_id": case_id,
                    "ok": actual == expected,
                    "expected": expected,
                    "actual": actual,
                }
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    report: dict[str, object] = {
        "ok": all(item["ok"] for item in results),
        "case_count": len(results),
        "cases": results,
    }
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
