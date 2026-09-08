from pathlib import Path

from ai_service_desk import cli


def test_phase6_parser_accepts_exact_commands() -> None:
    parser = cli.build_parser()
    validate = parser.parse_args(["playbook-validate", "--file", "x.jsonl"])
    build = parser.parse_args(
        ["playbook-build", "--file", "x.jsonl", "--knowledge-index", "k", "--output", "o"]
    )
    smoke = parser.parse_args(
        [
            "playbook-smoke",
            "--knowledge-index",
            "k",
            "--playbooks",
            "p",
            "--cases",
            "c",
            "--work-directory",
            "w",
            "--report",
            "r",
        ]
    )
    assert validate.command == "playbook-validate"
    assert build.command == "playbook-build"
    assert smoke.command == "playbook-smoke"
    for args in (validate, build, smoke):
        assert not hasattr(args, "url")
        assert not hasattr(args, "query")


def test_validate_output_safe_and_no_ollama(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "load_playbooks",
        lambda path: [
            {"status": "APPROVED"},
            {"status": "APPROVED"},
            {"status": "DRAFT"},
            {"status": "RETIRED"},
        ],
    )
    monkeypatch.setattr(
        cli,
        "OllamaClient",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Ollama forbidden")),
    )
    assert cli.main(["playbook-validate", "--file", "x.jsonl"]) == 0
    out = capsys.readouterr().out
    assert "Total: 4" in out and "APPROVED: 2" in out and "DRAFT: 1" in out and "RETIRED: 1" in out
    assert "capability" in out
    assert "DEMO_PRINT_QUEUE_CLEAR" not in out


def test_build_and_smoke_output_safe_and_no_ollama(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli,
        "build_playbook_catalog",
        lambda *a, **k: {"domain": "APPROVED_PLAYBOOK", "approved_playbooks": 2, "active_links": 3},
    )
    monkeypatch.setattr(cli, "run_playbook_smoke", lambda *a, **k: {"ok": True, "cases": [{}] * 10})
    monkeypatch.setattr(
        cli,
        "OllamaClient",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Ollama forbidden")),
    )
    assert (
        cli.main(["playbook-build", "--file", "p", "--knowledge-index", "k", "--output", "o"]) == 0
    )
    assert (
        cli.main(
            [
                "playbook-smoke",
                "--knowledge-index",
                "k",
                "--playbooks",
                "p",
                "--cases",
                "c",
                "--work-directory",
                "w",
                "--report",
                str(tmp_path / "r.json"),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Playbook catalog: APPROVED_PLAYBOOK" in out
    assert "Playbooks APPROVED: 2" in out
    assert "Links ativos: 3" in out
    assert "PLAYBOOK SMOKE OK" in out
    assert "Casos sinteticos: 10" in out
    assert "DEMO_PRINT_QUEUE_CLEAR" not in out
