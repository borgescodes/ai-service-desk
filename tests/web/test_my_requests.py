import pytest

from ai_service_desk.web.demo_runtime import DemoRuntime
from ai_service_desk.web.errors import WebDemoError


def _create_cdm_request(runtime: DemoRuntime, identity_id: str = "pedro-miranda") -> str:
    result = runtime.send_message(
        identity_id,
        "Preciso de acesso ao CDM para solicitar materiais para uma revenda.",
    )
    assert result["status"] == "REQUEST_CREATED"
    return result["request_id"]


def test_request_status_query_returns_empty_authoritative_summary() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message("pedro-miranda", "Como estão minhas solicitações?")

        assert result["status"] == "REQUESTS_LISTED"
        assert result["request_summary"] == {"count": 0, "items": []}
        assert result["assistant_message"] == "Você ainda não tem solicitações para acompanhar."
        assert result["presentation"] == {"cta": None}
    finally:
        runtime.close()


def test_request_status_query_uses_only_current_requester_records_and_labels() -> None:
    runtime = DemoRuntime.create()
    try:
        request_id = _create_cdm_request(runtime)
        result = runtime.send_message("pedro-miranda", "Tenho alguma solicitação pendente?")

        assert result["status"] == "REQUESTS_LISTED"
        assert result["request_summary"] == {
            "count": 1,
            "items": [
                {
                    "request_id": request_id,
                    "system": "CDM",
                    "state_label": "Aguardando aprovação",
                }
            ],
        }
        assert request_id in result["assistant_message"]
        assert "CDM · Aguardando aprovação" in result["assistant_message"]
        assert "PENDING_APPROVAL" not in result["assistant_message"]
        assert result["presentation"] == {"cta": "REQUESTS"}
    finally:
        runtime.close()


def test_request_status_query_lists_multiple_records_from_the_same_backend_source() -> None:
    runtime = DemoRuntime.create()
    try:
        first = _create_cdm_request(runtime)
        runtime.reset_conversation("pedro-miranda")
        second = _create_cdm_request(runtime)

        result = runtime.send_message("pedro-miranda", "Quais pedidos eu tenho?")

        assert result["request_summary"]["count"] == 2
        assert [item["request_id"] for item in result["request_summary"]["items"]] == [
            first,
            second,
        ]
        assert "Você tem 2 solicitações para acompanhar." in result["assistant_message"]
    finally:
        runtime.close()


def test_requester_cannot_receive_another_requesters_summary() -> None:
    runtime = DemoRuntime.create()
    try:
        other = runtime.identity_provider.configure_requester(
            name="Ana da Silva",
            email="ana.silva@juparana.com.br",
            job_title="Analista",
            area="Revenda",
        )
        other_request = _create_cdm_request(runtime, other.identity_id)

        result = runtime.send_message("pedro-miranda", "Como estão minhas solicitações?")

        assert result["request_summary"] == {"count": 0, "items": []}
        assert other_request not in result["assistant_message"]
    finally:
        runtime.close()


def test_technician_cannot_use_requester_request_status_capability() -> None:
    runtime = DemoRuntime.create()
    try:
        with pytest.raises(WebDemoError) as exc_info:
            runtime.send_message("tecnico-cdm", "/solicitacoes")

        assert exc_info.value.code == "NOT_AUTHORIZED"
    finally:
        runtime.close()


def test_request_status_natural_language_calls_list_requests() -> None:
    runtime = DemoRuntime.create()
    try:
        calls = []
        original = runtime.list_requests

        def tracked(identity_id: str):
            calls.append(identity_id)
            return original(identity_id)

        runtime.list_requests = tracked
        runtime.send_message("pedro-miranda", "Como estão minhas solicitações?")

        assert calls == ["pedro-miranda"]
    finally:
        runtime.close()


def test_specific_cdm_request_query_does_not_invent_a_request() -> None:
    runtime = DemoRuntime.create()
    try:
        result = runtime.send_message("pedro-miranda", "Como está meu pedido do CDM?")

        assert result["request_summary"] == {"count": 0, "items": []}
        assert "REQ-" not in result["assistant_message"]
    finally:
        runtime.close()


def test_slash_command_uses_the_same_request_status_capability_without_interpretation() -> None:
    runtime = DemoRuntime.create()
    try:
        calls = []
        original = runtime.list_requests

        def tracked(identity_id: str):
            calls.append(identity_id)
            return original(identity_id)

        runtime.list_requests = tracked
        result = runtime.send_message("pedro-miranda", "/solicitacoes")

        assert result["status"] == "REQUESTS_LISTED"
        assert calls == ["pedro-miranda"]
    finally:
        runtime.close()
