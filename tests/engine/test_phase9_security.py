import ast
import subprocess
import threading
from pathlib import Path

import pytest
import requests

from ai_service_desk.integrations.cdm_fake_api import build_cdm_server
from tests.engine.phase16_authorized_blobs import PHASE16_AUTHORIZED_EXTENSIONS

ROOT = Path(__file__).resolve().parents[2]
PROTECTED_BLOBS = {
    "src/ai_service_desk/engine/access_request.py": "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
    "src/ai_service_desk/engine/policy.py": "60a4f3ae785353009c30b37f71e1ce91865b899e",
    "src/ai_service_desk/engine/confidence.py": "ffc0c212b455978f79a3591578f323ca0e9612dc",
    "src/ai_service_desk/engine/request_lifecycle.py": ("dfd194ff8a364a0eb0d803409dad252ced216279"),
    "src/ai_service_desk/engine/request_repository.py": (
        "5ccda3d30484729faa1a568cf64e20bfe55e595f"
    ),
    "src/ai_service_desk/engine/technician_authorization.py": (
        "ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4"
    ),
    "src/ai_service_desk/engine/approval.py": "ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8",
    "src/ai_service_desk/engine/execution.py": "908ceade729daa3e18b7b604549f635b33d4688f",
    "src/ai_service_desk/engine/controlled_execution_smoke.py": (
        "e26766fdc35ff450d69a40a2516d193b7a90cb75"
    ),
}
HTTP_FREE_MODULES = (
    "access_request.py",
    "policy.py",
    "confidence.py",
    "request_lifecycle.py",
    "request_repository.py",
    "technician_authorization.py",
    "approval.py",
    "execution.py",
    "cdm_execution.py",
)


@pytest.mark.parametrize(("path", "expected_sha"), PROTECTED_BLOBS.items())
def test_phase8_protected_blobs_remain_exact(path, expected_sha):
    authorized_extensions = {
        "src/ai_service_desk/engine/access_request.py": (
            "f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d",
            "515a23a38791edd4e11f675804062aa9305a1d25",
        ),
        "src/ai_service_desk/engine/confidence.py": (
            "ffc0c212b455978f79a3591578f323ca0e9612dc",
            "9864ed510a0de3270d30e9088aec407bfd16392d",
        ),
        "src/ai_service_desk/engine/request_lifecycle.py": (
            "dfd194ff8a364a0eb0d803409dad252ced216279",
            "6ab28ad86d7d40e4873e9a76b6c3cd9f3b4c843b",
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


def _import_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.name for alias in node.names)
    return names


def test_http_is_absent_from_phase8_core_and_cdm_executor():
    forbidden = {"requests", "urllib", "http.client", "socket"}
    for module in HTTP_FREE_MODULES:
        names = _import_names(ROOT / "src" / "ai_service_desk" / "engine" / module)
        assert not {
            name
            for name in names
            if any(name == item or name.startswith(item + ".") for item in forbidden)
        }


def test_runtime_and_fixture_do_not_contain_test_service_tokens():
    paths = [
        ROOT / "src/ai_service_desk/integrations/cdm.py",
        ROOT / "src/ai_service_desk/integrations/cdm_fake_api.py",
        ROOT / "src/ai_service_desk/engine/cdm_execution.py",
        ROOT / "src/ai_service_desk/engine/cdm_integration_smoke.py",
        ROOT / "tests/fixtures/phase9_cdm_integration_cases.jsonl",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "synthetic-test-token" not in text
        assert "test-token" not in text
        assert "phase9-security-token" not in text


@pytest.mark.parametrize("role", ["APROVADOR", "ADMIN", "SUPERADMIN"])
def test_privileged_roles_are_rejected_without_state(role):
    token = "phase9-security-token"
    server = build_cdm_server("127.0.0.1", 0, token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        response = requests.post(
            f"http://{host}:{port}/api/v1/access",
            json={
                "request_id": "REQ-000001",
                "username": "synthetic.requester",
                "email": "synthetic.requester@example.invalid",
                "role": role,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=2,
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "CDM_REQUEST_INVALID"
        assert server.store.access_count == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
