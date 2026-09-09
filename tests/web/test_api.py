from fastapi.testclient import TestClient

from ai_service_desk.web.api import create_app
from ai_service_desk.web.demo_runtime import DemoRuntime


def _client(runtime: DemoRuntime, *, demo_mode: bool = True, host: str = "127.0.0.1"):
    app = create_app(runtime=runtime, demo_mode=demo_mode)
    return TestClient(app, client=(host, 50000))


def test_http_flow_browser_to_api_to_domain_and_back_to_requester() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        created = client.post(
            "/api/jup/messages",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={"message": "Preciso de acesso ao CDM para solicitar materiais para uma revenda."},
        )
        assert created.status_code == 200
        request_id = created.json()["request_id"]
        assert created.json()["state"] == "PENDING_APPROVAL"
        assert runtime.fake_cdm_store.access_count == 0

        requester_before = client.get(
            f"/api/requests/{request_id}",
            headers={"X-Demo-Identity": "pedro-miranda"},
        )
        assert requester_before.status_code == 200
        assert requester_before.json()["state"] == "PENDING_APPROVAL"

        queue = client.get(
            "/api/operations/approvals",
            headers={"X-Demo-Identity": "tecnico-cdm"},
        )
        assert queue.status_code == 200
        assert [item["request_id"] for item in queue.json()] == [request_id]

        approved = client.post(
            f"/api/requests/{request_id}/approve",
            headers={"X-Demo-Identity": "tecnico-cdm"},
            json={"expected_version": 2},
        )
        assert approved.status_code == 200
        assert approved.json()["state"] == "COMPLETED"
        assert runtime.fake_cdm_store.access_count == 1

        requester_after = client.get(
            f"/api/requests/{request_id}",
            headers={"X-Demo-Identity": "pedro-miranda"},
        )
        assert requester_after.status_code == 200
        assert requester_after.json()["state"] == "COMPLETED"
        assert requester_after.json()["state_label"] == "Concluída"
    finally:
        runtime.close()


def test_api_requires_controlled_demo_identity() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        response = client.get("/api/requests")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "IDENTITY_REQUIRED"

        response = client.get(
            "/api/requests",
            headers={"X-Demo-Identity": "not-allowlisted"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "IDENTITY_NOT_FOUND"
    finally:
        runtime.close()


def test_api_rejects_requester_approval_without_external_execution() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        request_id = client.post(
            "/api/jup/messages",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={"message": "Preciso de acesso ao CDM para solicitar materiais para uma revenda."},
        ).json()["request_id"]

        response = client.post(
            f"/api/requests/{request_id}/approve",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={"expected_version": 2},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "NOT_AUTHORIZED"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_api_maps_version_conflict_without_traceback() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        request_id = client.post(
            "/api/jup/messages",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={"message": "Preciso de acesso ao CDM para solicitar materiais para uma revenda."},
        ).json()["request_id"]

        response = client.post(
            f"/api/requests/{request_id}/approve",
            headers={"X-Demo-Identity": "tecnico-cdm"},
            json={"expected_version": 1},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "VERSION_CONFLICT"
        assert "Traceback" not in response.text
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_api_reject_path_is_exposed_without_execution() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        request_id = client.post(
            "/api/jup/messages",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={"message": "Preciso de acesso ao CDM para solicitar materiais para uma revenda."},
        ).json()["request_id"]

        response = client.post(
            f"/api/requests/{request_id}/reject",
            headers={"X-Demo-Identity": "tecnico-cdm"},
            json={"expected_version": 2},
        )
        assert response.status_code == 200
        assert response.json()["state"] == "REJECTED"
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_api_sets_no_store_and_security_headers() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
    finally:
        runtime.close()


def test_prevention_api_is_technician_only_and_uses_runtime_projection() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        requester = client.get(
            "/api/operations/prevention",
            headers={"X-Demo-Identity": "pedro-miranda"},
        )
        assert requester.status_code == 403
        assert requester.json()["error"]["code"] == "NOT_AUTHORIZED"

        response = client.get(
            "/api/operations/prevention",
            headers={"X-Demo-Identity": "tecnico-cdm"},
        )
        assert response.status_code == 200
        assert response.json() == runtime.list_prevention("tecnico-cdm")
        assert response.json()

        opportunity_id = response.json()[0]["opportunity_id"]
        detail = client.get(
            f"/api/operations/prevention/{opportunity_id}",
            headers={"X-Demo-Identity": "tecnico-cdm"},
        )
        assert detail.status_code == 200
        assert detail.json() == response.json()[0]
    finally:
        runtime.close()


def test_prevention_api_maps_unknown_opportunity_to_not_found() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        response = client.get(
            "/api/operations/prevention/OPP-DOES-NOT-EXIST",
            headers={"X-Demo-Identity": "tecnico-cdm"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PREVENTION_NOT_FOUND"
    finally:
        runtime.close()


def test_demo_reset_recreates_mutable_state_only_on_loopback() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime)
    try:
        client.post(
            "/api/jup/messages",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={"message": "Preciso de acesso ao CDM para solicitar materiais para uma revenda."},
        )
        assert runtime.created_request_ids

        response = client.post("/api/demo/reset")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert runtime.created_request_ids == []
        assert runtime.conversations == {}
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_demo_reset_is_not_registered_outside_demo_mode() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime, demo_mode=False)
    try:
        response = client.post("/api/demo/reset")
        assert response.status_code == 404
    finally:
        runtime.close()


def test_demo_reset_rejects_non_loopback_client_and_ignores_forwarded_header() -> None:
    runtime = DemoRuntime.create()
    client = _client(runtime, host="203.0.113.9")
    try:
        response = client.post(
            "/api/demo/reset",
            headers={"X-Forwarded-For": "127.0.0.1"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "LOOPBACK_REQUIRED"
    finally:
        runtime.close()
