import json
from pathlib import Path

from ai_service_desk.engine import real_smoke


def test_run_demo_smoke_uses_subset_report_rows_and_hash(tmp_path: Path, monkeypatch) -> None:
    external = tmp_path / "external"
    checkout = tmp_path / "repo"
    external.mkdir()
    checkout.mkdir()
    subset_report = external / "subset.json"
    subset_report.write_text(
        json.dumps(
            {
                "selected_rows": 6,
                "subset_canonical_sha256": "subset-hash-v1",
            }
        ),
        encoding="utf-8",
    )
    captured: dict = {}

    def fake_run(corpus, index, report, base_url, checkout_path, expected, corpus_report):
        captured.update(
            corpus=Path(corpus),
            index=Path(index),
            report=Path(report),
            base_url=base_url,
            checkout=Path(checkout_path),
            expected=expected,
            corpus_report=corpus_report,
        )
        return {"ok": True, "threshold": 0.65}

    monkeypatch.setattr(real_smoke, "_run_smoke", fake_run, raising=False)

    result = real_smoke.run_demo_smoke(
        external / "demo.csv",
        subset_report,
        external / "index",
        external / "smoke.json",
        "http://127.0.0.1:11434",
        checkout,
    )

    assert result["ok"] is True
    assert captured["expected"] == {
        "rows": 6,
        "canonical_sha256": "subset-hash-v1",
    }
    assert captured["corpus_report"] == {
        "rows": 6,
        "manifest_match": True,
    }
