import importlib
import importlib.util

import pytest


def vocabulary():
    name = "ai_service_desk.web.business_context"
    assert importlib.util.find_spec(name) is not None, "F12 business vocabulary is missing"
    return importlib.import_module(name).BusinessVocabulary()


@pytest.mark.parametrize(
    ("text", "systems", "product"),
    [
        ("Esqueci minha senha do Office", ("OFFICE 365",), ""),
        ("Não consigo entrar no M365", ("OFFICE 365",), ""),
        ("Meu Teams não entra", ("OFFICE 365",), "TEAMS"),
        ("Outlook não abre", ("OFFICE 365",), "OUTLOOK"),
        ("O One Drive não sincroniza", ("OFFICE 365",), "ONEDRIVE"),
        ("Teams no Office 365 não entra", ("OFFICE 365",), "TEAMS"),
        ("Preciso acessar o CDM", ("CDM",), ""),
        ("Central de Dados Mestres", ("CDM",), ""),
        ("Preciso cadastrar um material para revenda", ("CDM",), ""),
        ("Preciso criar cadastro de materiais para a revenda", ("CDM",), ""),
        ("Preciso comprar material", (), ""),
        ("Preciso fazer um pedido de material", (), ""),
        ("Estou com problema em um material", (), ""),
        ("Não preciso cadastrar material para revenda", (), ""),
        ("Como comprar material? Revenda. Cadastro.", (), ""),
        ("Preciso cadastrar material para revenda no SIAGRI", ("SIAGRI",), ""),
        ("Portal RH não abre", ("PORTAL RH",), ""),
        ("PortalRH não abre", ("PORTAL RH",), ""),
        ("Metadados não entra", ("METADADOS",), ""),
        ("Ordem de compra no CIGAM", ("CIGAM 11",), ""),
        ("Cigan travou", ("CIGAM 11",), ""),
        ("O SAP está com erro", ("SAP",), ""),
        ("S/4HANA", ("SAP",), ""),
        ("O SIAGRI está travando", ("SIAGRI",), ""),
        ("Não consigo acessar o sistema", (), ""),
        ("SAP e Portal RH não entram", ("SAP", "PORTAL RH"), ""),
        ("METADADOS e CIGAM", ("METADADOS", "CIGAM 11"), ""),
        ("officeiro sapato cdmx", (), ""),
    ],
)
def test_business_meaning_uses_curated_evidence(text, systems, product):
    resolver = vocabulary()
    assert set(resolver.systems(text)) == set(systems)
    assert resolver.entities(text).get("product", "") == product


def test_prompt_is_functional_current_and_has_no_historical_procedures():
    resolver = vocabulary()
    prompt = resolver.prompt()
    assert "BUSINESS_CONTEXT_CURRENT" in prompt
    assert "revenda" in prompt.casefold()
    assert "implantação" in prompt.casefold()
    assert "não são a mesma aplicação" in prompt.casefold()
    assert len(prompt) < 6500
    for forbidden in (
        "historico_atendimento",
        "ticket_id",
        "Supabase",
        "SQL",
        "RLS",
        "Edge Functions",
        "service role",
        "payload SAP",
        "http",
        "token",
    ):
        assert forbidden.casefold() not in prompt.casefold()


def test_historical_candidate_does_not_create_a_second_corporate_truth():
    resolver = vocabulary()
    assert resolver.canonical("Cigan") == "CIGAM 11"
    assert resolver.canonical("Ofice") is None
    assert resolver.systems("Cadastrar material para revenda") == ("CDM",)
    assert resolver.systems("Cadastrar material para revenda no Cigan") == ("CIGAM 11",)
