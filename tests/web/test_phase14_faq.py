import json

import pytest
from fastapi.testclient import TestClient

from ai_service_desk.web.api import create_app
from ai_service_desk.web.demo_faq import DemoFaqCatalog
from ai_service_desk.web.demo_runtime import DemoRuntime

CATEGORIES = {
    "acessos-rotinas": "Acessos e rotinas",
    "erros-sistemas": "Erros em sistemas",
    "impressao-office-aplicativos": "Impressão, Office e aplicativos",
    "rede-internet": "Rede e internet",
}
TUTORIAL = "KB-SYN-FAQ-CDM-REQUEST-001"


@pytest.fixture
def runtime():
    instance = DemoRuntime.create()
    yield instance
    instance.close()


def test_four_problem_categories_and_combined_api_filter(runtime):
    client = TestClient(create_app(runtime=runtime))
    groups = client.get("/api/faq").json()["groups"]
    assert {group["key"]: group["label"] for group in groups} == CATEGORIES
    for category in CATEGORIES:
        items = client.get("/api/faq/search", params={"category": category}).json()["items"]
        assert items
        assert all(item["category_key"] == category for item in items)
    items = client.get(
        "/api/faq/search", params={"q": "CDM", "category": "acessos-rotinas"}
    ).json()["items"]
    assert TUTORIAL in {item["knowledge_id"] for item in items}
    assert all(item["category_key"] == "acessos-rotinas" for item in items)
    for params in [
        {"q": "zzzzzz", "category": "rede-internet"},
        {"category": "unknown"},
        {"q": "CDM", "category": "rede-internet"},
    ]:
        assert client.get("/api/faq/search", params=params).json()["items"] == []


def test_faq_source_is_separate_literal_approved_and_keeps_operational_ids(runtime):
    for _ in range(2):
        assert set(runtime.knowledge_engine.df.knowledge_id) == {
            "KB-SYN-CDM-ACCESS-001",
            "KB-SYN-M365-PASSWORD-001",
        }
        source = runtime.get_faq(TUTORIAL)
        assert source["provenance"]["source"] == "SYNTHETIC_DEMO"
        assert source["provenance"]["status"] == "APPROVED"
        assert source["provenance"]["version"] == 1
        assert source["answer"].startswith("Para solicitar seu acesso ao CDM:")
        assert "áreas de negócio" in source["answer"]
        assert "Microsoft 365" in source["answer"]
        assert "Solicitar Acesso" in source["answer"]
        assert not any(
            word in source["answer"].casefold() for word in ("role", "aprovador", "admin")
        )
        assert runtime.get_faq("KB-SYN-CDM-ACCESS-001")["answer"] == (
            "O acesso de solicitante ao CDM precisa de aprovação humana antes da liberação."
        )
        runtime.reset()


def test_explicit_tags_override_system_and_unapproved_never_leak(tmp_path):
    rows = []
    for index, category in enumerate(CATEGORIES):
        for status in ("APPROVED", "DRAFT", "RETIRED"):
            rows.append(
                {
                    "knowledge_id": f"KB-{index}-{status}",
                    "title": f"Ajuda {index}",
                    "question": "Como resolver?",
                    "answer": "1. Abra https://arbitrary.invalid/.",
                    "system": "CIGAM",
                    "intent": "PROBLEMA_ACESSO",
                    "tags": [f"faq-{category}"],
                    "source": "SYNTHETIC_DEMO",
                    "status": status,
                    "reviewed_by": "DEMO-REVIEWER",
                    "reviewed_at": "2026-09-13T09:00:00-03:00",
                    "version": 1,
                }
            )
    path = tmp_path / "faq.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    catalog = DemoFaqCatalog.from_sources([path])
    assert len(catalog.search("")) == 4
    for index, category in enumerate(CATEGORIES):
        item = catalog.search("", category)[0]
        assert item["knowledge_id"] == f"KB-{index}-APPROVED"
        assert item["category_key"] == category
        assert catalog.detail(item["knowledge_id"])["procedure_url"] is None


def test_only_exact_official_urls_are_projected(runtime):
    assert runtime.get_faq(TUTORIAL)["procedure_url"] == "https://cdm.juparana.com.br/"
    assert runtime.get_faq("KB-SYN-CDM-ACCESS-001")["procedure_url"] is None
    assert runtime.get_faq("KB-SYN-M365-PASSWORD-001")["procedure_url"] == (
        "https://mysignins.microsoft.com/security-info/password/change"
    )


def test_new_tutorial_is_discoverable_in_featured_access_group(runtime):
    group = next(g for g in runtime.list_faq()["groups"] if g["key"] == "acessos-rotinas")
    assert TUTORIAL in {item["knowledge_id"] for item in group["items"]}
