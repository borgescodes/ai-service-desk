from fastapi.testclient import TestClient

from ai_service_desk.web.api import create_app
from ai_service_desk.web.demo_runtime import DemoRuntime


def test_faq_is_public_and_approved_only():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["groups"]) <= 4
        assert all(len(group["items"]) <= 4 for group in payload["groups"])
        assert all("answer" not in item for group in payload["groups"] for item in group["items"])
    finally:
        runtime.close()


def test_faq_search_is_public_and_limited():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq/search", params={"q": "cigam"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == len(payload["items"])
        assert payload["total"] <= 16
    finally:
        runtime.close()


def test_faq_detail_returns_literal_answer_and_fixed_microsoft_url():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq/KB-SYN-M365-PASSWORD-001")
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"].startswith("Vamos redefinir sua senha do Microsoft 365.")
        assert (
            payload["procedure_url"]
            == "https://mysignins.microsoft.com/security-info/password/change"
        )
    finally:
        runtime.close()


def test_faq_unknown_id_is_404_without_internal_details():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq/KB-MISSING")
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == "FAQ_NOT_FOUND"
        assert "traceback" not in response.text.casefold()
    finally:
        runtime.close()
