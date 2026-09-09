from pathlib import Path

from fastapi.testclient import TestClient

from ai_service_desk.web.api import create_app
from ai_service_desk.web.demo_runtime import DemoRuntime


def _use_knowledge(runtime: DemoRuntime):
    result = runtime.send_message(
        "pedro-miranda",
        "Não consigo acessar o Microsoft 365 depois que esqueci minha senha.",
    )
    assert result["status"] == "KNOWLEDGE_FOUND"
    triage_engine, _ = runtime._triage["pedro-miranda"]
    assert triage_engine.knowledge_engine is runtime.knowledge_engine
    return triage_engine


def _open_mapping(runtime: DemoRuntime):
    matrix = runtime.knowledge_engine.matrix
    mapping = getattr(matrix, "_mmap", None)
    assert mapping is not None
    assert mapping.closed is False
    return matrix, mapping


def test_runtime_close_releases_knowledge_mapping_temp_dir_and_fake_cdm() -> None:
    runtime = DemoRuntime.create()
    temp_root = Path(runtime._temp.name)
    triage_engine = _use_knowledge(runtime)
    knowledge_engine = runtime.knowledge_engine
    matrix, mapping = _open_mapping(runtime)
    server = runtime.fake_cdm_server
    thread = runtime._fake_cdm_thread

    runtime.close()

    assert triage_engine.knowledge_engine is knowledge_engine
    assert matrix is knowledge_engine.matrix
    assert mapping.closed is True
    assert not temp_root.exists()
    assert server.fileno() == -1
    assert not thread.is_alive()
    assert runtime._temp is None
    assert runtime.fake_cdm_server is None
    assert runtime._fake_cdm_thread is None
    assert runtime._triage == {}
    assert runtime.knowledge_engine is None

    runtime.close()


def test_runtime_reset_after_knowledge_use_releases_previous_generation() -> None:
    runtime = DemoRuntime.create()
    try:
        _use_knowledge(runtime)
        first_root = Path(runtime._temp.name)
        _, first_mapping = _open_mapping(runtime)
        first_server = runtime.fake_cdm_server
        first_thread = runtime._fake_cdm_thread

        runtime.reset()

        assert first_mapping.closed is True
        assert not first_root.exists()
        assert first_server.fileno() == -1
        assert not first_thread.is_alive()
        assert Path(runtime._temp.name).exists()

        _use_knowledge(runtime)
        second_root = Path(runtime._temp.name)
        _, second_mapping = _open_mapping(runtime)
        second_server = runtime.fake_cdm_server
        second_thread = runtime._fake_cdm_thread

        runtime.reset()

        assert second_mapping.closed is True
        assert not second_root.exists()
        assert second_server.fileno() == -1
        assert not second_thread.is_alive()
        assert Path(runtime._temp.name).exists()
    finally:
        runtime.close()
        runtime.close()


def test_demo_reset_endpoint_releases_used_knowledge_generation() -> None:
    runtime = DemoRuntime.create()
    client = TestClient(create_app(runtime=runtime), client=("127.0.0.1", 50000))
    try:
        response = client.post(
            "/api/jup/messages",
            headers={"X-Demo-Identity": "pedro-miranda"},
            json={
                "message": "Não consigo acessar o Microsoft 365 depois que esqueci minha senha.",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "KNOWLEDGE_FOUND"

        old_root = Path(runtime._temp.name)
        _, old_mapping = _open_mapping(runtime)
        old_server = runtime.fake_cdm_server
        old_thread = runtime._fake_cdm_thread

        reset = client.post("/api/demo/reset")

        assert reset.status_code == 200
        assert reset.json() == {"ok": True}
        assert old_mapping.closed is True
        assert not old_root.exists()
        assert old_server.fileno() == -1
        assert not old_thread.is_alive()
        assert runtime.created_request_ids == []
        assert runtime.conversations == {}
        assert Path(runtime._temp.name).exists()
    finally:
        runtime.close()
