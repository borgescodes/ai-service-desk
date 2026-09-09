from dataclasses import replace
from datetime import timedelta

import pytest

from ai_service_desk.engine.execution import (
    ActionExecutionResult,
    ExecutionEngine,
    FakeActionExecutor,
)
from ai_service_desk.engine.policy import PolicyEngine
from ai_service_desk.engine.request_lifecycle import Phase8DomainError
from tests.engine.phase8_helpers import DEFAULT_TIMESTAMP, FixedClock, make_context
from tests.engine.test_approval import make_system
from tests.engine.test_technician_authorization import TECH


class PolicySpy(PolicyEngine):
    def __init__(self, rules=None):
        super().__init__(rules)
        self.calls = []

    def evaluate(self, context):
        self.calls.append(context)
        return super().evaluate(context)


class OneShotClock(FixedClock):
    def __call__(self):
        if self.calls:
            raise AssertionError("execution clock called more than once")
        return super().__call__()


def make_engine(state="APPROVED", mode="success", policy=None, executor=None, context=None):
    repo, lifecycle, approval, record = make_system(
        role="ADMIN" if state == "DENIED_POLICY" else "SOLICITANTE", context=context
    )
    if state == "REJECTED":
        record = approval.reject(record.request_id, TECH, expected_version=2)
    elif state not in {"PENDING_APPROVAL", "DENIED_POLICY"}:
        record = approval.approve(record.request_id, TECH, expected_version=2)
    if state in {"EXECUTING", "COMPLETED", "FAILED"}:
        record = lifecycle.transition_to_executing(
            record, record.latest_policy, expected_version=3, occurred_at=DEFAULT_TIMESTAMP
        )
        if state == "COMPLETED":
            record = lifecycle.transition_to_completed(
                record,
                "FAKE_EXECUTION_SUCCEEDED",
                expected_version=4,
                occurred_at=DEFAULT_TIMESTAMP,
            )
        elif state == "FAILED":
            record = lifecycle.transition_to_failed(
                record, "EXECUTOR_EXCEPTION", expected_version=4, occurred_at=DEFAULT_TIMESTAMP
            )
    clock = OneShotClock(DEFAULT_TIMESTAMP + timedelta(hours=1))
    engine = ExecutionEngine(
        repo,
        lifecycle,
        policy if policy is not None else PolicySpy(),
        executor if executor is not None else FakeActionExecutor(mode),
        clock=clock,
    )
    return engine, record


def assert_state_blocked(state):
    engine, record = make_engine(state)
    before = engine.repository.audit_for(record.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        engine.execute(record.request_id, expected_version=record.version)
    assert exc.value.reason_code == "INVALID_STATE_TRANSITION"
    assert engine.policy_engine.calls == []
    assert engine.executor.calls == []
    assert engine.clock.calls == 0
    assert engine.repository.get(record.request_id) == record
    assert engine.repository.audit_for(record.request_id) == before


def test_execute_rejects_pending_approval():
    assert_state_blocked("PENDING_APPROVAL")


def test_execute_rejects_denied_policy():
    assert_state_blocked("DENIED_POLICY")


def test_execute_rejects_rejected_request():
    assert_state_blocked("REJECTED")


def test_execute_rejects_completed_request():
    assert_state_blocked("COMPLETED")


def test_execute_rejects_failed_request_without_retry():
    assert_state_blocked("FAILED")


def test_execute_rejects_already_executing_request():
    assert_state_blocked("EXECUTING")


def test_stale_execute_conflicts_before_policy_clock_and_executor():
    engine, record = make_engine("COMPLETED")
    with pytest.raises(Phase8DomainError) as exc:
        engine.execute(record.request_id, expected_version=3)
    assert exc.value.reason_code == "VERSION_CONFLICT"
    assert engine.policy_engine.calls == engine.executor.calls == []
    assert engine.clock.calls == 0


@pytest.mark.parametrize("value", [True, False, 3.0, "3", None, 0, -1])
def test_execution_expected_version_is_exact_positive_integer(value):
    engine, record = make_engine()
    before = engine.repository.audit_for(record.request_id)
    with pytest.raises(Phase8DomainError) as exc:
        engine.execute(record.request_id, expected_version=value)
    assert exc.value.reason_code == "EXPECTED_VERSION_INVALID"
    assert engine.policy_engine.calls == engine.executor.calls == []
    assert engine.clock.calls == 0
    assert engine.repository.get(record.request_id) == record
    assert engine.repository.audit_for(record.request_id) == before


def check_order():
    engine, approved = make_engine()

    class ObservingExecutor:
        def execute(self, record):
            assert engine.policy_engine.calls == [approved.context]
            assert engine.repository.get(record.request_id) == record
            assert record.state == "EXECUTING"
            assert (
                engine.repository.audit_for(record.request_id)[-1].event_type == "EXECUTION_STARTED"
            )
            return ActionExecutionResult(True, "OBSERVED_EXECUTION_OK")

    engine.executor = ObservingExecutor()
    assert engine.execute(approved.request_id, expected_version=3).state == "COMPLETED"


def test_execute_revalidates_policy_before_executor():
    check_order()


def test_require_approval_persists_executing_before_executor_call():
    check_order()


def test_revalidation_deny_transitions_to_denied_policy():
    engine, approved = make_engine(policy=PolicySpy([]))
    result = engine.execute(approved.request_id, expected_version=3)
    assert result.state == "DENIED_POLICY"
    assert result.decided_by == approved.decided_by
    assert result.version == 4
    assert engine.clock.calls == 1


def test_revalidation_deny_makes_zero_executor_calls():
    engine, approved = make_engine(policy=PolicySpy([]))
    result = engine.execute(approved.request_id, expected_version=3)
    assert engine.executor.calls == []
    assert result.latest_policy.decision == "DENY"
    assert engine.repository.audit_for(result.request_id)[-1].reason_code == "POLICY_NOT_FOUND"


def test_executor_success_transitions_to_completed():
    engine, record = make_engine()
    result = engine.execute(record.request_id, expected_version=3)
    assert result.state == "COMPLETED"
    assert result.execution_result_code == "FAKE_EXECUTION_SUCCEEDED"
    assert result.execution_error_code is None
    assert len(engine.executor.calls) == 1


def test_executor_failure_transitions_to_failed():
    engine, record = make_engine(mode="failure")
    result = engine.execute(record.request_id, expected_version=3)
    assert result.state == "FAILED"
    assert result.execution_error_code == result.execution_result_code == "FAKE_EXECUTION_FAILED"


def test_executor_exception_transitions_to_safe_failed():
    engine, record = make_engine(mode="exception")
    result = engine.execute(record.request_id, expected_version=3)
    assert result.state == "FAILED"
    assert result.execution_error_code == "EXECUTOR_EXCEPTION"
    assert result.execution_result_code is None


def test_executor_exception_text_is_not_persisted():
    class BrokenExecutor:
        def execute(self, record):
            raise RuntimeError("SYNTHETIC_PRIVATE_EXCEPTION_PAYLOAD")

    engine, record = make_engine(executor=BrokenExecutor())
    result = engine.execute(record.request_id, expected_version=3)
    evidence = repr(result) + repr(engine.repository.audit_for(result.request_id))
    assert "SYNTHETIC_PRIVATE_EXCEPTION_PAYLOAD" not in evidence
    assert "RuntimeError" not in evidence
    assert result.execution_error_code == "EXECUTOR_EXCEPTION"


def invalid_result(value):
    class InvalidExecutor:
        def execute(self, record):
            return value

    engine, record = make_engine(executor=InvalidExecutor())
    result = engine.execute(record.request_id, expected_version=3)
    assert result.state == "FAILED"
    assert result.execution_result_code is None
    assert result.execution_error_code == "EXECUTOR_INVALID_RESULT"
    assert (
        engine.repository.audit_for(result.request_id)[-1].reason_code == "EXECUTOR_INVALID_RESULT"
    )
    assert "SYNTHETIC_PRIVATE_RESULT" not in repr(result) + repr(
        engine.repository.audit_for(result.request_id)
    )


def test_invalid_executor_result_transitions_to_executor_invalid_result():
    invalid_result({"SYNTHETIC_PRIVATE_RESULT": "payload"})


def test_invalid_result_rejects_integer_success():
    invalid_result(ActionExecutionResult(1, "VALID_CODE"))


def test_invalid_result_rejects_string_success():
    invalid_result(ActionExecutionResult("true", "VALID_CODE"))


def test_invalid_result_rejects_empty_result_code():
    invalid_result(ActionExecutionResult(True, ""))


def test_invalid_result_rejects_result_code_with_space():
    invalid_result(ActionExecutionResult(True, "INVALID CODE"))


def test_invalid_result_rejects_non_string_unhashable_result_code():
    invalid_result(ActionExecutionResult(True, ["SYNTHETIC_PRIVATE_RESULT"]))


def test_invalid_result_rejects_wrong_result_object_type():
    class PretendResult:
        @property
        def success(self):
            raise AssertionError("arbitrary fields must never be read")

    invalid_result(PretendResult())


def test_failed_request_does_not_execute_again():
    engine, record = make_engine(mode="failure")
    failed = engine.execute(record.request_id, expected_version=3)
    with pytest.raises(Phase8DomainError):
        engine.execute(record.request_id, expected_version=failed.version)
    assert len(engine.executor.calls) == 1
    assert engine.clock.calls == 1


def test_completed_flow_has_canonical_audit_order():
    engine, record = make_engine()
    engine.execute(record.request_id, expected_version=3)
    assert [e.event_type for e in engine.repository.audit_for(record.request_id)] == [
        "REQUEST_CREATED",
        "POLICY_REQUIRES_APPROVAL",
        "REQUEST_APPROVED",
        "EXECUTION_STARTED",
        "EXECUTION_COMPLETED",
    ]


def test_failed_flow_has_execution_started_before_execution_failed():
    engine, record = make_engine(mode="failure")
    engine.execute(record.request_id, expected_version=3)
    assert [e.event_type for e in engine.repository.audit_for(record.request_id)][-2:] == [
        "EXECUTION_STARTED",
        "EXECUTION_FAILED",
    ]


def test_revalidation_updates_latest_policy_only():
    engine, record = make_engine(policy=PolicySpy([]))
    result = engine.execute(record.request_id, expected_version=3)
    assert result.latest_policy != record.latest_policy
    assert result.creation_policy is record.creation_policy
    assert result.context is record.context
    assert result.confidence is record.confidence
    assert result.created_at == record.created_at


@pytest.mark.parametrize("area,level", [("Revenda Sintetica", "HIGH"), ("Outra Area", "LOW")])
def test_confidence_does_not_change_policy_or_execution_gate(area, level):
    context = make_context(requester=replace(make_context().requester, area=area))
    engine, record = make_engine(context=context)
    assert record.confidence.level == level
    assert record.creation_policy.decision == "REQUIRE_APPROVAL"
    assert engine.execute(record.request_id, expected_version=3).state == "COMPLETED"


def test_execute_uses_single_operation_timestamp():
    engine, record = make_engine()
    result = engine.execute(record.request_id, expected_version=3)
    operation_time = DEFAULT_TIMESTAMP + timedelta(hours=1)
    assert result.state == "COMPLETED"
    assert engine.clock.calls == 1
    assert result.execution_started_at == result.execution_finished_at == operation_time
    assert [e.occurred_at for e in engine.repository.audit_for(record.request_id)[-2:]] == [
        operation_time,
        operation_time,
    ]


def test_executor_baseexception_is_not_swallowed():
    class InterruptExecutor:
        def execute(self, request):
            raise KeyboardInterrupt()

    engine, record = make_engine(executor=InterruptExecutor())
    with pytest.raises(KeyboardInterrupt):
        engine.execute(record.request_id, expected_version=3)
    assert engine.repository.get(record.request_id).state == "EXECUTING"
