import json

from ai_service_desk.engine.evaluation import build_evaluation_report


def test_build_evaluation_report_contains_only_aggregate_metrics() -> None:
    metrics = {
        0.65: {
            "cases": 28,
            "intent_accuracy": 0.9,
            "system_accuracy": 1.0,
            "hit_at_3": 0.8,
            "mrr": 0.7,
            "correct_abstention_rate": 1.0,
            "unsafe_accept_count": 0,
            "system_leakage_count": 0,
            "ambiguous_context_failures": 0,
            "unknown_system_failures": 0,
            "execution_failures": 0,
        }
    }
    report = build_evaluation_report(metrics, 0.60, has_real_gold=False)
    text = json.dumps(report, ensure_ascii=False)

    assert report["version"] == 1
    assert report["benchmark"] == "phase3-synthetic-v1"
    assert report["cases"] == 28
    assert report["calibration"]["decision"] == "HOLD"
    assert report["calibration"]["runtime_threshold"] == 0.65
    assert report["privacy"] == {
        "query_text_included": False,
        "candidate_identifiers_included": False,
        "corporate_content_included": False,
    }
    assert "query" not in text.lower()
    assert "candidate_ids" not in text
    assert "SYN-CIG-01" not in text


def test_build_evaluation_report_fails_runtime_hard_gate() -> None:
    metrics = {
        0.65: {
            "cases": 1,
            "unsafe_accept_count": 1,
            "system_leakage_count": 0,
            "ambiguous_context_failures": 0,
            "unknown_system_failures": 0,
            "execution_failures": 0,
        }
    }
    report = build_evaluation_report(metrics, None, has_real_gold=False)
    assert report["ok"] is False
