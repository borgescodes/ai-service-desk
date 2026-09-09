from pathlib import Path

from ai_service_desk import phase11_cli

ROOT = Path(__file__).resolve().parents[1]


def test_phase11_cli_handles_only_learning_prevention_smoke() -> None:
    assert phase11_cli.handles(["learning-prevention-smoke"]) is True
    assert phase11_cli.handles(["routing-escalation-smoke"]) is False
    assert phase11_cli.handles([]) is False


def test_phase11_cli_runs_official_smoke_without_external_configuration(capsys) -> None:
    exit_code = phase11_cli.main(["learning-prevention-smoke"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "LEARNING PREVENTION SMOKE OK\nCasos sinteticos: 10\n"
    assert captured.err == ""


def test_main_dispatches_phase11_before_previous_phase_commands() -> None:
    source = (ROOT / "src" / "ai_service_desk" / "__main__.py").read_text(encoding="utf-8")
    phase11 = source.index("if phase11_cli.handles(argv):")
    phase10 = source.index("if phase10_cli.handles(argv):")
    phase9 = source.index("if phase9_cli.handles(argv):")
    legacy = source.index("raise SystemExit(cli.main(argv))")
    assert phase11 < phase10 < phase9 < legacy
