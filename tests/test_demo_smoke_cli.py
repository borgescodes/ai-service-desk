import contextlib
import io
from pathlib import Path

from ai_service_desk import cli


def test_demo_smoke_forwards_external_paths_and_prints_only_aggregate(
    tmp_path: Path, monkeypatch
) -> None:
    external = tmp_path / "external"
    checkout = tmp_path / "repo"
    external.mkdir()
    checkout.mkdir()
    captured: dict = {}

    def fake_run(corpus, subset_report, index, report, base_url, checkout_path):
        captured.update(
            corpus=Path(corpus),
            subset_report=Path(subset_report),
            index=Path(index),
            report=Path(report),
            base_url=base_url,
            checkout=Path(checkout_path),
        )
        return {
            "ok": True,
            "index": {"rows": 6, "shape": [6, 1024]},
            "queries": [{"name": "cigam", "ok": True}],
        }

    monkeypatch.setattr(cli, "run_demo_smoke", fake_run, raising=False)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(
            [
                "demo-smoke",
                "--file",
                str(external / "demo.csv"),
                "--subset-report",
                str(external / "subset.json"),
                "--index",
                str(external / "index"),
                "--report",
                str(external / "smoke.json"),
                "--checkout",
                str(checkout),
            ]
        )

    assert code == 0
    assert captured["base_url"] == "http://127.0.0.1:11434"
    assert captured["corpus"] == external / "demo.csv"
    assert captured["subset_report"] == external / "subset.json"
    assert captured["index"] == external / "index"
    assert captured["report"] == external / "smoke.json"
    assert captured["checkout"] == checkout
    output = stdout.getvalue()
    assert "DEMO RETRIEVAL SMOKE OK" in output
    assert "6 x 1024" in output
    assert "ticket" not in output.lower()
