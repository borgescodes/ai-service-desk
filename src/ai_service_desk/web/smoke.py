from dataclasses import replace

from ai_service_desk.web.demo_runtime import DemoRuntime


def _case(name: str, passed: bool, actual: str) -> dict:
    return {"name": name, "passed": bool(passed), "actual": actual}


def run_web_demo_smoke() -> dict:
    runtime = DemoRuntime.create(mode="DETERMINISTIC")
    cases: list[dict] = []
    try:
        requester = runtime.identity_provider.requester_identity("pedro-miranda")
        requester_ok = requester.username == "fulano.tal"
        cases.append(
            _case(
                "REQUESTER_IDENTITY",
                requester_ok,
                "REQUESTER_RESOLVED" if requester_ok else "REQUESTER_INVALID",
            )
        )

        knowledge = runtime.send_message(
            "pedro-miranda",
            "Não consigo acessar o Microsoft 365 depois que esqueci minha senha.",
        )
        knowledge_ok = (
            knowledge.get("status") == "KNOWLEDGE_FOUND" and knowledge.get("request_id") is None
        )
        cases.append(
            _case(
                "KNOWLEDGE_NO_REQUEST",
                knowledge_ok,
                "KNOWLEDGE_FOUND:NO_REQUEST" if knowledge_ok else "KNOWLEDGE_FLOW_INVALID",
            )
        )

        created = runtime.send_message(
            "pedro-miranda",
            "Preciso de acesso ao CDM para solicitar materiais para uma revenda.",
        )
        request_id = created.get("request_id")
        created_ok = (
            created.get("status") == "REQUEST_CREATED"
            and created.get("state") == "PENDING_APPROVAL"
            and isinstance(request_id, str)
        )
        cases.append(
            _case(
                "CDM_REQUEST_CREATED",
                created_ok,
                "PENDING_APPROVAL" if created_ok else "REQUEST_NOT_PENDING",
            )
        )

        if not isinstance(request_id, str):
            request_id = ""
        record = runtime.request_repository.get(request_id)
        assignment = runtime.routing_store.get(request_id)
        routing_ok = assignment.technician.technician_id == "TECH-CDM"
        cases.append(
            _case(
                "ROUTING_TECH_CDM",
                routing_ok,
                "TECH-CDM" if routing_ok else "ROUTING_INVALID",
            )
        )

        pending = runtime.list_approvals("tecnico-cdm")
        pending_ok = [item["request_id"] for item in pending] == [request_id]
        cases.append(
            _case(
                "TECHNICIAN_PENDING_VISIBILITY",
                pending_ok,
                "ONE_PENDING" if pending_ok else "PENDING_VISIBILITY_INVALID",
            )
        )

        denied_context = replace(record.context, requested_role="ADMIN")
        denied = runtime.routed_requests.create_request(denied_context)
        denied_absent = (
            denied.state == "DENIED_POLICY"
            and runtime.routing_store.get_optional(denied.request_id) is None
            and all(
                item["request_id"] != denied.request_id
                for item in runtime.list_approvals("tecnico-cdm")
            )
        )

        approved = runtime.approve_request(
            "tecnico-cdm",
            request_id,
            expected_version=record.version,
        )
        approval_ok = any(
            event["event_type"] == "REQUEST_APPROVED" for event in approved["timeline"]
        )
        cases.append(
            _case(
                "APPROVAL",
                approval_ok,
                "REQUEST_APPROVED" if approval_ok else "APPROVAL_EVENT_MISSING",
            )
        )

        execution_ok = (
            approved["state"] == "COMPLETED"
            and approved["execution_result_code"] == "CDM_ACCESS_CREATED"
            and runtime.fake_cdm_store.access_count == 1
        )
        cases.append(
            _case(
                "CDM_EXECUTION_COMPLETE",
                execution_ok,
                "CDM_ACCESS_CREATED" if execution_ok else "EXECUTION_NOT_COMPLETED",
            )
        )

        requester_view = runtime.get_request("pedro-miranda", request_id)
        requester_complete = requester_view["state"] == "COMPLETED"
        cases.append(
            _case(
                "REQUESTER_COMPLETED_VISIBILITY",
                requester_complete,
                "COMPLETED" if requester_complete else "REQUESTER_STATE_INVALID",
            )
        )

        cases.append(
            _case(
                "POLICY_DENIED_ABSENT_FROM_QUEUE",
                denied_absent,
                "DENIED_POLICY:ZERO_ASSIGNMENT" if denied_absent else "DENIED_POLICY_QUEUE_INVALID",
            )
        )

        prevention = runtime.list_prevention("tecnico-cdm")
        prevention_ok = bool(prevention)
        cases.append(
            _case(
                "PREVENTION_AVAILABLE",
                prevention_ok,
                "OPPORTUNITY_AVAILABLE" if prevention_ok else "NO_OPPORTUNITY",
            )
        )

        return {
            "ok": len(cases) == 10 and all(case["passed"] for case in cases),
            "total": len(cases),
            "cases": cases,
        }
    finally:
        runtime.close()
