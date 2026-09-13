from ai_service_desk.web.smoke import run_web_demo_smoke

_EXPECTED_CASES = [
    "REQUESTER_IDENTITY",
    "KNOWLEDGE_NO_REQUEST",
    "CDM_REQUEST_CREATED",
    "ROUTING_TECH_CDM",
    "TECHNICIAN_PENDING_VISIBILITY",
    "APPROVAL",
    "CDM_EXECUTION_COMPLETE",
    "REQUESTER_COMPLETED_VISIBILITY",
    "POLICY_DENIED_ABSENT_FROM_QUEUE",
    "PREVENTION_AVAILABLE",
]


def test_web_demo_smoke_proves_exactly_ten_deterministic_cases() -> None:
    report = run_web_demo_smoke()

    assert report["ok"] is True
    assert report["total"] == 10
    assert [case["name"] for case in report["cases"]] == _EXPECTED_CASES
    assert all(case["passed"] is True for case in report["cases"])
    assert all(set(case) == {"name", "passed", "actual"} for case in report["cases"])


def test_web_demo_smoke_report_contains_no_demo_personal_identifiers() -> None:
    rendered = repr(run_web_demo_smoke()).casefold()

    assert "pedro miranda" not in rendered
    assert "pedro.miranda" not in rendered
    assert "@" not in rendered
