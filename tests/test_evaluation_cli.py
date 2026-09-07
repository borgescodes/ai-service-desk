import contextlib
import io
import json
from pathlib import Path

from ai_service_desk import cli


def test_evaluate_forwards_paths_and_prints_only_aggregate_summary(
    tmp_path: Path, monkeypatch
) -> None:
    checkout = tmp_path / "repo"
    external = tmp_path / "external"
    checkout.mkdir()
    external.mkdir()
    report_path = external / "evaluation.json"
    captured: dict = {}

    def fake_run(index, cases, report, base_url, checkout_path):
        captured.update(
            index=index,
            cases=cases,
            report=report,
            base_url=base_url,
            checkout=checkout_path,
        )
        payload = {
            "version": 1,
            "benchmark": "phase3-synthetic-v1",
            "ok": True,
            "cases": 28,
            "thresholds": {
                "0.65": {
                    "intent_accuracy": 0.9,
                    "system_accuracy": 1.0,
                    "hit_at_3": 0.8,
                    "mrr": 0.7,
                    "correct_abstention_rate": 1.0,
                    "system_leakage_count": 0,
                    "unsafe_accept_count": 0,
                    "ambiguous_context_failures": 0,
                    "unknown_system_failures": 0,
                    "execution_failures": 0,
                }
            },
            "synthetic_recommendation": 0.60,
            "calibration": {
                "decision": "HOLD",
                "runtime_threshold": 0.65,
                "reason": "no_real_labeled_gold_set",
                "synthetic_recommendation": 0.60,
            },
        }
        Path(report).write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr(cli, "run_evaluation", fake_run, raising=False)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(
            [
                "evaluate",
                "--index",
                str(external / "index"),
                "--cases",
                "tests/fixtures/phase3_eval_cases.jsonl",
                "--report",
                str(report_path),
                "--checkout",
                str(checkout),
                "--url",
                "http://127.0.0.1:11434",
            ]
        )

    assert code == 0
    assert Path(captured["index"]) == external / "index"
    assert str(captured["cases"]).endswith("phase3_eval_cases.jsonl")
    assert Path(captured["report"]) == report_path
    assert captured["base_url"] == "http://127.0.0.1:11434"
    assert Path(captured["checkout"]) == checkout
    text = stdout.getvalue()
    assert "Avaliacao Fase 3 OK" in text
    assert "Casos: 28" in text
    assert "runtime threshold: 0.65" in text.lower()
    assert "SEGREDO-SINTETICO" not in text


def test_evaluate_returns_failure_when_hard_gates_fail(tmp_path: Path, monkeypatch) -> None:
    checkout = tmp_path / "repo"
    external = tmp_path / "external"
    checkout.mkdir()
    external.mkdir()

    def fake_run(index, cases, report, base_url, checkout_path):
        del index, cases, report, base_url, checkout_path
        return {
            "ok": False,
            "cases": 1,
            "thresholds": {"0.65": {}},
            "synthetic_recommendation": None,
            "calibration": {
                "decision": "HOLD",
                "runtime_threshold": 0.65,
                "reason": "no_real_labeled_gold_set",
                "synthetic_recommendation": None,
            },
        }

    monkeypatch.setattr(cli, "run_evaluation", fake_run, raising=False)
    code = cli.main(
        [
            "evaluate",
            "--index",
            str(external / "index"),
            "--cases",
            "tests/fixtures/phase3_eval_cases.jsonl",
            "--report",
            str(external / "report.json"),
            "--checkout",
            str(checkout),
        ]
    )
    assert code == 1
