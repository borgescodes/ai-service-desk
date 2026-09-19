import pytest

from ai_service_desk.web.demo_identity import (
    DemoIdentityProvider,
    IdentityConfigurationError,
    IdentityNotFoundError,
)


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
    assert requester.job_title == "Colaborador"


def test_provider_configures_distinct_requesters_with_arbitrary_areas() -> None:
    provider = DemoIdentityProvider()

    ana = provider.configure_requester(
        name=" Ana da Silva ",
        email="ANA.SILVA@juparana.com.br",
        job_title=" Analista UBS ",
        area=" UBS ",
    )
    carlos = provider.configure_requester(
        name="Carlos Souza",
        email="carlos.souza@juparana.com.br",
        job_title="Analista Financeiro",
        area="Financeiro",
    )

    assert ana.identity_id != carlos.identity_id
    assert provider.requester_identity(ana.identity_id).name == "Ana da Silva"
    assert provider.requester_identity(ana.identity_id).email == "ana.silva@juparana.com.br"
    assert provider.requester_identity(ana.identity_id).job_title == "Analista UBS"
    assert provider.requester_identity(carlos.identity_id).area == "Financeiro"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", " "),
        ("email", "ana.silva"),
        ("email", "ana.silva@example.com"),
        ("job_title", ""),
        ("area", "\t"),
    ],
)
def test_provider_rejects_invalid_requester_configuration(field: str, value: str) -> None:
    payload = {
        "name": "Ana da Silva",
        "email": "ana.silva@juparana.com.br",
        "job_title": "Analista UBS",
        "area": "UBS",
    }
    payload[field] = value

    with pytest.raises(IdentityConfigurationError):
        DemoIdentityProvider().configure_requester(**payload)


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
