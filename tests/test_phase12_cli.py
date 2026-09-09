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
