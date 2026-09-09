from ai_service_desk.engine.access_request import (
    CDM_ACCESS_CAPABILITY,
    CDM_ACCESS_INTENT,
    CDM_SYSTEM,
)
from ai_service_desk.engine.execution import ActionExecutionResult
from ai_service_desk.engine.request_lifecycle import AccessRequestRecord
from ai_service_desk.integrations.cdm import CDMAdapterError


class CDMActionExecutor:
    def __init__(self, adapter):
        self.adapter = adapter

    def execute(self, request: AccessRequestRecord) -> ActionExecutionResult:
        if request.state != "EXECUTING":
            raise ValueError("Executor CDM exige request EXECUTING.")
        context = request.context
        if (
            context.system != CDM_SYSTEM
            or context.intent != CDM_ACCESS_INTENT
            or context.capability != CDM_ACCESS_CAPABILITY
            or context.requested_role != "SOLICITANTE"
        ):
            return ActionExecutionResult(False, "CDM_EXECUTION_CONTEXT_INVALID")

        try:
            lookup = self.adapter.get_access(context.requester.email)
            if lookup.exists:
                if lookup.role == "SOLICITANTE" and lookup.status == "ACTIVE":
                    return ActionExecutionResult(True, "CDM_ACCESS_ALREADY_EXISTS")
                return ActionExecutionResult(False, "CDM_EXISTING_ACCESS_CONFLICT")

            created = self.adapter.create_access(
                request.request_id,
                context.requester.username,
                context.requester.email,
                context.requested_role,
            )
        except CDMAdapterError as exc:
            return ActionExecutionResult(False, exc.reason_code)

        result_codes = {
            "CREATED": "CDM_ACCESS_CREATED",
            "REPLAYED": "CDM_REQUEST_REPLAYED",
            "ALREADY_EXISTS": "CDM_ACCESS_ALREADY_EXISTS",
        }
        code = result_codes.get(created.outcome)
        if code is None:
            return ActionExecutionResult(False, "CDM_PROTOCOL_ERROR")
        return ActionExecutionResult(True, code)
