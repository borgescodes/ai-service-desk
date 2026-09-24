import os
import subprocess
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


@pytest.mark.parametrize(
    ("env_file", "process_provider", "expected_provider", "expected_model", "expected_key"),
    [
        (None, None, "", "", ""),
        (
            "# comentário\n\nJUP_CHAT_PROVIDER=groq\n"
            "GROQ_MODEL=openai/gpt-oss-120b\nGROQ_API_KEY=file-secret\nIGNORED=value\n",
            None,
            "groq",
            "openai/gpt-oss-120b",
            "file-secret",
        ),
        (
            "JUP_CHAT_PROVIDER=groq\nGROQ_MODEL=file-model\nGROQ_API_KEY=file-secret\n",
            "ollama",
            "ollama",
            "file-model",
            "file-secret",
        ),
    ],
)
def test_windows_launcher_loads_only_expected_local_env_without_overriding_process(
    tmp_path,
    env_file,
    process_provider,
    expected_provider,
    expected_model,
    expected_key,
) -> None:
    launcher = tmp_path / "run-web-demo.cmd"
    launcher.write_text(Path("run-web-demo.cmd").read_text(encoding="utf-8"), encoding="utf-8")
    if env_file is not None:
        (tmp_path / ".env.local").write_text(env_file, encoding="utf-8")
    build_script = tmp_path / "web" / "scripts" / "build.mjs"
    build_script.parent.mkdir(parents=True)
    build_script.write_text("", encoding="utf-8")
    package = tmp_path / "src" / "ai_service_desk"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import os\n"
        "assert os.environ.get('JUP_CHAT_PROVIDER', '') == os.environ['EXPECT_PROVIDER']\n"
        "assert os.environ.get('GROQ_MODEL', '') == os.environ['EXPECT_MODEL']\n"
        "assert os.environ.get('GROQ_API_KEY', '') == os.environ['EXPECT_KEY']\n"
        "assert 'IGNORED' not in os.environ\n"
        "print('LAUNCH_OK')\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    for name in ("JUP_CHAT_PROVIDER", "GROQ_MODEL", "GROQ_API_KEY", "IGNORED"):
        env.pop(name, None)
    if process_provider is not None:
        env["JUP_CHAT_PROVIDER"] = process_provider
    env.update(
        {
            "EXPECT_PROVIDER": expected_provider,
            "EXPECT_MODEL": expected_model,
            "EXPECT_KEY": expected_key,
        }
    )

    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(launcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "LAUNCH_OK" in result.stdout
    assert "file-secret" not in result.stdout
    assert "file-secret" not in result.stderr


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
