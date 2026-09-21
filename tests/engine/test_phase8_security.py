import ast
import builtins
import os
import socket
import subprocess
import urllib.request
from pathlib import Path

import pytest
import requests

from ai_service_desk.engine.execution import FakeActionExecutor
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from tests.engine.phase16_authorized_blobs import PHASE16_AUTHORIZED_EXTENSIONS
from tests.engine.test_approval import make_system
from tests.engine.test_execution import PolicySpy, make_engine
from tests.engine.test_technician_authorization import TECH

ROOT = Path(__file__).resolve().parents[2]
PROTECTED_BLOBS = {
    "src/ai_service_desk/engine/access_request.py": "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
    "src/ai_service_desk/engine/policy.py": "60a4f3ae785353009c30b37f71e1ce91865b899e",
    "src/ai_service_desk/engine/confidence.py": "ffc0c212b455978f79a3591578f323ca0e9612dc",
}
CORE_MODULES = (
    "request_lifecycle.py",
    "request_repository.py",
    "technician_authorization.py",
    "approval.py",
    "execution.py",
)
RUNTIME_MODULES = CORE_MODULES + ("controlled_execution_smoke.py",)


@pytest.mark.parametrize(
    ("path", "expected_sha"),
    PROTECTED_BLOBS.items(),
    ids=("access_request", "policy", "confidence"),
)
def test_phase7_protected_git_blob_is_exact(path, expected_sha):
    authorized_extensions = {
        "src/ai_service_desk/engine/access_request.py": (
            "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
            "515a23a38791edd4e11f675804062aa9305a1d25",
        ),
        "src/ai_service_desk/engine/confidence.py": (
            "ffc0c212b455978f79a3591578f323ca0e9612dc",
            "9864ed510a0de3270d30e9088aec407bfd16392d",
        ),
    }
    authorized_extensions.update(PHASE16_AUTHORIZED_EXTENSIONS)
    if path in authorized_extensions:
        historical, authorized = authorized_extensions[path]
        assert expected_sha == historical
        expected_sha = authorized
    completed = subprocess.run(
        (
            ["git", "hash-object", path]
            if path in PHASE16_AUTHORIZED_EXTENSIONS
            else ["git", "rev-parse", f"HEAD:{path}"]
        ),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == expected_sha


def imports_and_calls(modules):
    names = set()
    for module in modules:
        tree = ast.parse(
            (ROOT / "src/ai_service_desk/engine" / module).read_text(encoding="utf-8-sig")
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Call):
                names.add(ast.unparse(node.func))
    return names


def test_phase8_runtime_has_no_http_or_cdm_adapter():
    names = imports_and_calls(RUNTIME_MODULES)
    forbidden = {
        "requests",
        "httpx",
        "urllib",
        "http",
        "socket",
        "subprocess",
        "os",
        "CDMAdapter",
        "eval",
        "exec",
        "__import__",
        "importlib",
    }
    assert not {name for name in names if any(part in forbidden for part in name.split("."))}


def test_phase8_runtime_has_no_llm_ollama_or_embedding():
    names = imports_and_calls(RUNTIME_MODULES)
    assert not {
        name
        for name in names
        if ("ollama" in name.lower() or "embed" in name.lower() or "llm" in name.lower().split("."))
    }


def test_phase8_stateful_core_has_no_real_persistence():
    names = imports_and_calls(CORE_MODULES)
    forbidden = {
        "open",
        "Path",
        "sqlite3",
        "sqlalchemy",
        "json",
        "atomic_json",
        "write_text",
        "write_bytes",
        "shelve",
        "pickle",
    }
    assert not {name for name in names if any(part in forbidden for part in name.split("."))}


def test_phase8_runtime_makes_zero_external_calls_and_writes(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("attempted")
        raise AssertionError("External execution forbidden")

    with monkeypatch.context() as patch:
        patch.setattr(requests.Session, "request", forbidden)
        patch.setattr(urllib.request, "urlopen", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(subprocess, "run", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        patch.setattr(os, "system", forbidden)
        patch.setattr(OllamaClient, "__init__", forbidden)
        patch.setattr(LocalEmbedder, "embed", forbidden)
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(Path, "write_text", forbidden)
        patch.setattr(Path, "write_bytes", forbidden)
        for mode, state in (
            ("success", "COMPLETED"),
            ("failure", "FAILED"),
            ("exception", "FAILED"),
            ("invalid_result", "FAILED"),
        ):
            engine, approved = make_engine(mode=mode)
            assert engine.execute(approved.request_id, expected_version=3).state == state
        engine, approved = make_engine(policy=PolicySpy([]))
        assert engine.execute(approved.request_id, expected_version=3).state == "DENIED_POLICY"
        assert engine.executor.calls == []
        for role, method in (("SOLICITANTE", "reject"), ("ADMIN", None)):
            _, _, approval, record = make_system(role)
            if method:
                assert (
                    approval.reject(record.request_id, TECH, expected_version=2).state == "REJECTED"
                )
            else:
                assert record.state == "DENIED_POLICY"
    assert attempts == []


@pytest.mark.parametrize("method,state", [("approve", "APPROVED"), ("reject", "REJECTED")])
def test_human_decision_never_calls_fake_executor(monkeypatch, method, state):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("attempted")
        raise AssertionError("Human decision must not execute")

    monkeypatch.setattr(FakeActionExecutor, "execute", forbidden)
    _, _, approval, pending = make_system()
    assert getattr(approval, method)(pending.request_id, TECH, expected_version=2).state == state
    assert attempts == []
