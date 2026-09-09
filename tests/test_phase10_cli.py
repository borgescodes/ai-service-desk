from ai_service_desk import phase10_cli


def test_parser_accepts_routing_escalation_smoke():
    args = phase10_cli.build_parser().parse_args(["routing-escalation-smoke"])
    assert args.command == "routing-escalation-smoke"


def test_handler_recognizes_only_phase10_command():
    assert phase10_cli.handles(["routing-escalation-smoke"])
    assert not phase10_cli.handles(["cdm-integration-smoke"])
    assert not phase10_cli.handles([])


def test_routing_smoke_cli_prints_aggregate_success(monkeypatch, capsys):
    monkeypatch.setattr(
        phase10_cli,
        "run_routing_escalation_smoke",
        lambda: {"ok": True, "case_count": 8, "cases": []},
    )
    code = phase10_cli.main(["routing-escalation-smoke"])
    output = capsys.readouterr()
    assert code == 0
    assert "ROUTING ESCALATION SMOKE OK" in output.out
    assert "Casos sinteticos: 8" in output.out
