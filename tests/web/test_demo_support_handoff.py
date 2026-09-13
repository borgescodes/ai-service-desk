import pytest

from ai_service_desk.engine.routing import RouteNotFoundError
from ai_service_desk.web.demo_identity import DemoIdentityProvider
from ai_service_desk.web.demo_runtime import DemoRuntime


def _send(runtime: DemoRuntime, message: str) -> dict:
    return runtime.send_message("pedro-miranda", message)


def test_m365_specialist_identity_has_exact_support_capability() -> None:
    provider = DemoIdentityProvider()
    technician = provider.technician_identity("tecnico-m365")

    assert technician.technician_id == "TECH-M365"
    assert technician.name == "Técnico Microsoft 365"
    assert provider.technician_capabilities("tecnico-m365") == frozenset(
        {"MICROSOFT_365_SUPPORT_REQUEST"}
    )


def test_m365_support_route_is_exact_and_does_not_reuse_cdm_capability() -> None:
    runtime = DemoRuntime.create()
    try:
        technician = runtime.routing_registry.resolve(
            "MICROSOFT_365", "MICROSOFT_365_SUPPORT_REQUEST"
        )
        assert technician.technician_id == "TECH-M365"

        with pytest.raises(RouteNotFoundError):
            runtime.routing_registry.resolve("MICROSOFT_365", "CDM_ACCESS_REQUEST")
    finally:
        runtime.close()


def test_m365_handoff_is_idempotent_and_records_one_routed_outcome() -> None:
    runtime = DemoRuntime.create()
    try:
        baseline_ids = {item.interaction_id for item in runtime.outcome_store.snapshot()}
        _send(runtime, "Esqueci minha senha do Microsoft 365.")

        first = _send(runtime, "Não resolveu.")
        second = _send(runtime, "Continua sem acessar.")

        first_handoff = first["support_handoff"]
        second_handoff = second["support_handoff"]
        assert first_handoff["handoff_id"] == second_handoff["handoff_id"]
        assert first_handoff["technician"]["technician_id"] == "TECH-M365"
        assert first_handoff["requester"]["name"] == "Pedro Miranda"
        assert first_handoff["requester"]["area"] == "Revenda - Matriz"
        assert runtime.created_request_ids == []
        assert runtime.fake_cdm_store.access_count == 0

        outcomes = runtime.outcome_store.snapshot()
        routed = [
            item
            for item in outcomes
            if item.interaction_id not in baseline_ids
            and item.outcome == "ROUTED_TO_HUMAN"
            and item.capability == "MICROSOFT_365_SUPPORT_REQUEST"
        ]
        assert len(routed) == 1
        assert routed[0].knowledge_id == "KB-SYN-M365-PASSWORD-001"
    finally:
        runtime.close()


def test_reset_clears_m365_support_handoff_store() -> None:
    runtime = DemoRuntime.create()
    try:
        _send(runtime, "Esqueci minha senha do Microsoft 365.")
        result = _send(runtime, "Não resolveu.")
        handoff_id = result["support_handoff"]["handoff_id"]
        assert runtime.support_handoff_store.get(handoff_id).handoff_id == handoff_id

        runtime.reset()

        assert runtime.support_handoff_store.snapshot() == ()
        fresh = _send(runtime, "Funcionou.")
        assert not fresh.get("support_handoff")
        assert not fresh.get("resolved")
    finally:
        runtime.close()
