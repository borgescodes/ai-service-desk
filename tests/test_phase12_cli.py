import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_service_desk import phase12_cli


def test_phase12_handles_only_its_commands() -> None:
    assert phase12_cli.handles(["web-demo"])
    assert phase12_cli.handles(["web-demo-smoke"])
    assert not phase12_cli.handles(["learning-prevention-smoke"])
    assert not phase12_cli.handles([])


def test_web_demo_dispatches_loopback_host_port_and_mode(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        phase12_cli,
        "run_web_demo",
        lambda host, port, mode: calls.append((host, port, mode)),
    )

    assert (
        phase12_cli.main(
            [
                "web-demo",
                "--host",
                "127.0.0.1",
                "--port",
                "8123",
                "--mode",
                "LOCAL_AI",
            ]
        )
        == 0
    )
    assert calls == [("127.0.0.1", 8123, "LOCAL_AI")]


def test_web_demo_defaults_to_deterministic_mode(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        phase12_cli,
        "run_web_demo",
        lambda host, port, mode: calls.append((host, port, mode)),
    )

    assert phase12_cli.main(["web-demo"]) == 0
    assert calls == [("127.0.0.1", 8000, "DETERMINISTIC")]


def test_run_web_demo_forwards_mode_to_web_api(monkeypatch) -> None:
    calls = []
    fake_api = SimpleNamespace(run_web_demo=lambda **kwargs: calls.append(kwargs))
    monkeypatch.setitem(sys.modules, "ai_service_desk.web.api", fake_api)

    phase12_cli.run_web_demo("127.0.0.1", 8000, "LOCAL_AI")

    assert calls == [{"host": "127.0.0.1", "port": 8000, "mode": "LOCAL_AI"}]


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


def test_windows_launcher_pins_python_to_its_checkout() -> None:
    launcher = Path("run-web-demo.cmd").read_text(encoding="utf-8")

    assert 'set "PROJECT_ROOT=%~dp0"' in launcher
    assert 'pushd "%PROJECT_ROOT%"' in launcher
    assert 'set "PYTHONPATH=%PROJECT_ROOT%src;%PYTHONPATH%"' in launcher


def test_phase12_operator_docs_and_windows_launcher_cover_demo_flow() -> None:
    launcher = Path("run-web-demo.cmd").read_text(encoding="utf-8")
    environment = Path("docs/environment/web-demo.md").read_text(encoding="utf-8")
    script = Path("docs/demo/phase-12-demo-script.md").read_text(encoding="utf-8")

    assert "where node" in launcher
    assert "node web\\scripts\\build.mjs" in launcher
    assert "web-demo --mode LOCAL_AI --host 127.0.0.1 --port 8000" in launcher

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
