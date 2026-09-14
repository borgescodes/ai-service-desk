import pytest

from ai_service_desk.web.demo_identity import DemoIdentityProvider, IdentityNotFoundError


def test_provider_lists_only_predefined_public_identities() -> None:
    provider = DemoIdentityProvider()
    payloads = provider.public_identities()

    assert {item["identity_id"] for item in payloads} == {
        "pedro-miranda",
        "tecnico-cdm",
        "tecnico-m365",
        "tecnico-geral",
    }
    assert all("capabilities" not in item for item in payloads)


def test_demo_requester_resolves_exact_trusted_identity() -> None:
    requester = DemoIdentityProvider().requester_identity("pedro-miranda")

    assert requester.username == "fulano.tal"
    assert requester.name == "Fulano de Tal"
    assert requester.email == "fulano.tal@juparana.com.br"
    assert requester.area == "Revenda - Matriz"


def test_tecnico_cdm_resolves_exact_technician_identity_and_provider_capability() -> None:
    provider = DemoIdentityProvider()
    technician = provider.technician_identity("tecnico-cdm")

    assert technician.technician_id == "TECH-CDM"
    assert provider.technician_capabilities("tecnico-cdm") == frozenset({"CDM_ACCESS_REQUEST"})


def test_unknown_identity_fails_closed() -> None:
    with pytest.raises(IdentityNotFoundError) as exc_info:
        DemoIdentityProvider().resolve("not-allowlisted")

    assert exc_info.value.code == "IDENTITY_NOT_FOUND"


def test_requester_cannot_be_converted_to_technician() -> None:
    with pytest.raises(IdentityNotFoundError):
        DemoIdentityProvider().technician_identity("pedro-miranda")


def test_technician_is_not_used_as_requester() -> None:
    with pytest.raises(IdentityNotFoundError):
        DemoIdentityProvider().requester_identity("tecnico-cdm")
