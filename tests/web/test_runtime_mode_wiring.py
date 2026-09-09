from types import SimpleNamespace

from ai_service_desk.web import api as web_api


def test_create_app_uses_requested_runtime_mode(monkeypatch) -> None:
    calls = []
    runtime = SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(
        web_api.DemoRuntime,
        "create",
        classmethod(lambda cls, **kwargs: calls.append(kwargs) or runtime),
    )

    app = web_api.create_app(runtime_mode="LOCAL_AI")

    assert app.state.runtime is runtime
    assert app.state.owns_runtime is True
    assert calls == [{"mode": "LOCAL_AI"}]
