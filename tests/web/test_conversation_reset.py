from fastapi.testclient import TestClient

from ai_service_desk.web.api import create_app
from ai_service_desk.web.demo_runtime import DemoRuntime


def test_new_chat_clears_context_but_preserves_request_and_routing():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        headers = {"X-Demo-Identity": "pedro-miranda"}
        created = client.post(
            "/api/jup/messages",
            headers=headers,
            json={"message": "Preciso de acesso ao CDM para solicitar materiais para uma revenda."},
        ).json()
        before = runtime.list_requests("pedro-miranda")
        response = client.post("/api/jup/conversation/reset", headers=headers)
        assert response.status_code == 200
        assert runtime.list_requests("pedro-miranda") == before
        assert runtime.list_approvals("tecnico-cdm")[0]["request_id"] == created["request_id"]
        assert "pedro-miranda" not in runtime._triage
        assert not runtime.conversations.get("pedro-miranda")
        assert runtime.fake_cdm_store.access_count == 0
    finally:
        runtime.close()


def test_new_chat_requires_requester_identity():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        assert client.post("/api/jup/conversation/reset").status_code == 401
        response = client.post(
            "/api/jup/conversation/reset", headers={"X-Demo-Identity": "tecnico-cdm"}
        )
        assert response.status_code == 403
    finally:
        runtime.close()


def test_operational_handoffs_only_reach_assigned_technician_and_survive_new_chat():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        runtime.send_message("pedro-miranda", "Esqueci minha senha do Microsoft 365.")
        handoff = runtime.send_message("pedro-miranda", "Não resolveu.")["support_handoff"]
        response = client.get(
            "/api/operations/handoffs", headers={"X-Demo-Identity": "tecnico-m365"}
        )
        assert response.status_code == 200
        assert response.json() == [handoff]
        assert (
            client.get(
                "/api/operations/handoffs", headers={"X-Demo-Identity": "tecnico-cdm"}
            ).json()
            == []
        )
        assert (
            client.get(
                "/api/operations/handoffs", headers={"X-Demo-Identity": "pedro-miranda"}
            ).status_code
            == 403
        )
        runtime.reset_conversation("pedro-miranda")
        assert runtime.support_handoff_store.get(handoff["handoff_id"]).as_result() == handoff
        runtime.send_message("pedro-miranda", "Esqueci minha senha do Microsoft 365.")
        second = runtime.send_message("pedro-miranda", "Não resolveu.")["support_handoff"]
        assert second["handoff_id"] != handoff["handoff_id"]
    finally:
        runtime.close()
