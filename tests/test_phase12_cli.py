from pathlib import Path

import pytest

from ai_service_desk import phase12_cli


def test_phase12_handles_only_its_commands() -> None:
    assert phase12_cli.handles(["web-demo"])
    assert phase12_cli.handles(["web-demo-smoke"])
    assert not phase12_cli.handles(["learning-prevention-smoke"])
    assert not phase12_cli.handles([])


def test_web_demo_dispatches_loopback_host_and_port(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(phase12_cli, "run_web_demo", lambda host, port: calls.append((host, port)))

    assert phase12_cli.main(["web-demo", "--host", "127.0.0.1", "--port", "8123"]) == 0
    assert calls == [("127.0.0.1", 8123)]


def test_web_demo_rejects_non_loopback_host() -> None:
    with pytest.raises(SystemExit):
        phase12_cli.main(["web-demo", "--host", "0.0.0.0"])


def test_web_demo_smoke_prints_marker(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        phase12_cli,
        "run_web_demo_smoke",
        lambda: {"ok": True, "cases": [{"passed": True}] * 10},
    )

    assert phase12_cli.main(["web-demo-smoke"]) == 0
    output = capsys.readouterr().out
    assert "WEB DEMO SMOKE OK" in output
    assert "10/10" in output


def test_phase12_operator_docs_and_windows_launcher_cover_demo_flow() -> None:
    launcher = Path("run-web-demo.cmd").read_text(encoding="utf-8")
    environment = Path("docs/environment/web-demo.md").read_text(encoding="utf-8")
    script = Path("docs/demo/phase-12-demo-script.md").read_text(encoding="utf-8")

    assert "where node" in launcher
    assert "node web\\scripts\\build.mjs" in launcher
    assert "web-demo --host 127.0.0.1 --port 8000" in launcher

    for marker in [
        "Pré-requisitos",
        "Build",
        "Execução",
        "Reset",
        "fake CDM",
        "Frontend",
        "Backend",
        "Troubleshooting",
    ]:
        assert marker in environment

    for marker in [
        "Pedro",
        "Microsoft 365",
        "CDM",
        "O que entendi",
        "Técnico CDM",
        "Pendências",
        "COMPLETED",
        "Prevenção",
    ]:
        assert marker in script
