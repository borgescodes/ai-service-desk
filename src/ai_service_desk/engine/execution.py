from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from ai_service_desk.engine.policy import MACHINE_CODE_RE
from ai_service_desk.engine.request_lifecycle import (
    AccessRequestRecord,
    ConcurrencyConflictError,
    InvalidStateTransitionError,
    validate_expected_version,
)


@dataclass(frozen=True)
class ActionExecutionResult:
    success: bool
    result_code: str


class ActionExecutor(Protocol):
    def execute(self, request: AccessRequestRecord) -> ActionExecutionResult: ...


class FakeActionExecutor:
    def __init__(self, mode="success"):
        if mode not in {"success", "failure", "exception", "invalid_result"}:
            raise ValueError("Modo sintetico invalido.")
        self.mode = mode
        self.calls: list[AccessRequestRecord] = []

    def execute(self, request: AccessRequestRecord) -> ActionExecutionResult:
        if request.state != "EXECUTING":
            raise ValueError("Executor exige request EXECUTING.")
        self.calls.append(request)
        if self.mode == "exception":
            raise RuntimeError("Falha sintetica do executor.")
        if self.mode == "invalid_result":
            return None
        if self.mode == "failure":
            return ActionExecutionResult(False, "FAKE_EXECUTION_FAILED")
        return ActionExecutionResult(True, "FAKE_EXECUTION_SUCCEEDED")


class ExecutionEngine:
    def __init__(self, repository, lifecycle, policy_engine, executor: ActionExecutor, clock=None):
        self.repository = repository
        self.lifecycle = lifecycle
        self.policy_engine = policy_engine
        self.executor = executor
        self.clock = clock if clock is not None else lambda: datetime.now(UTC)

    def execute(self, request_id: str, *, expected_version: int) -> AccessRequestRecord:
        record = self.repository.get(request_id)
        validate_expected_version(expected_version)
        if expected_version != record.version:
            raise ConcurrencyConflictError("VERSION_CONFLICT", "Versao stale.")
        if record.state != "APPROVED":
            raise InvalidStateTransitionError(
                "INVALID_STATE_TRANSITION", "Request nao esta APPROVED."
            )
        policy = self.policy_engine.evaluate(record.context)
        operation_timestamp = self.clock()
        if policy.decision == "DENY":
            return self.lifecycle.transition_to_denied_policy(
                record, policy, expected_version=expected_version, occurred_at=operation_timestamp
            )
        executing = self.lifecycle.transition_to_executing(
            record, policy, expected_version=expected_version, occurred_at=operation_timestamp
        )
        try:
            result = self.executor.execute(executing)
        except Exception:
            return self.lifecycle.transition_to_failed(
                executing,
                "EXECUTOR_EXCEPTION",
                expected_version=executing.version,
                occurred_at=operation_timestamp,
            )
        if (
            type(result) is not ActionExecutionResult
            or type(result.success) is not bool
            or not isinstance(result.result_code, str)
            or MACHINE_CODE_RE.fullmatch(result.result_code) is None
        ):
            return self.lifecycle.transition_to_failed(
                executing,
                "EXECUTOR_INVALID_RESULT",
                expected_version=executing.version,
                occurred_at=operation_timestamp,
            )
        if result.success:
            return self.lifecycle.transition_to_completed(
                executing,
                result.result_code,
                expected_version=executing.version,
                occurred_at=operation_timestamp,
            )
        return self.lifecycle.transition_to_failed(
            executing,
            result.result_code,
            result_code=result.result_code,
            expected_version=executing.version,
            occurred_at=operation_timestamp,
        )
