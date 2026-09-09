from ai_service_desk.engine.routing_escalation_smoke import (
    ROUTING_ESCALATION_CASE_IDS,
    run_routing_escalation_smoke,
)


def test_phase10_smoke_runs_exact_eight_cases():
    report = run_routing_escalation_smoke()
    assert report["ok"] is True
    assert report["case_count"] == 8
    assert tuple(item["case_id"] for item in report["cases"]) == ROUTING_ESCALATION_CASE_IDS
    assert all(item["ok"] is True for item in report["cases"])


def test_phase10_smoke_report_is_aggregate_only():
    report = run_routing_escalation_smoke()
    assert set(report) == {"ok", "case_count", "cases"}
    for item in report["cases"]:
        assert set(item) == {"case_id", "ok", "expected", "actual"}
