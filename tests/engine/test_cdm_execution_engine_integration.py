from ai_service_desk.engine.cdm_execution import CDMActionExecutor
from tests.engine.test_execution import make_engine


class BrokenCDMAdapter:
    def get_access(self, email):
        raise RuntimeError("SYNTHETIC_CDM_PRIVATE_FAILURE")


def test_unexpected_cdm_adapter_exception_uses_existing_execution_engine_failure_path():
    engine, approved = make_engine(executor=CDMActionExecutor(BrokenCDMAdapter()))
    result = engine.execute(approved.request_id, expected_version=approved.version)
    assert result.state == "FAILED"
    assert result.execution_error_code == "EXECUTOR_EXCEPTION"
    assert result.execution_result_code is None
    evidence = repr(result) + repr(engine.repository.audit_for(result.request_id))
    assert "SYNTHETIC_CDM_PRIVATE_FAILURE" not in evidence
