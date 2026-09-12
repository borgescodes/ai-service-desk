import json

import pytest

from ai_service_desk.web.demo_faq import DemoFaqCatalog, FaqNotFoundError


def _article(
    knowledge_id: str,
    *,
    status: str = "APPROVED",
    system: str = "SIAGRI",
    intent: str = "PROBLEMA_ACESSO",
    tags: list[str] | None = None,
    title: str = "Acesso ao SIAGRI",
    question: str = "Não consigo acessar o SIAGRI.",
    answer: str = "Orientação aprovada.",
) -> dict:
    return {
        "knowledge_id": knowledge_id,
        "title": title,
        "question": question,
        "answer": answer,
        "system": system,
        "intent": intent,
        "tags": tags or ["acesso"],
        "source": "SYNTHETIC_DEMO",
        "status": status,
        "reviewed_by": "DEMO-REVIEWER" if status == "APPROVED" else "",
        "reviewed_at": "2026-09-12T09:00:00-03:00" if status == "APPROVED" else "",
        "version": 1,
    }


def _write(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_catalog_exposes_only_approved_and_never_review_metadata(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(
        source,
        [
            _article("KB-APPROVED"),
            _article("KB-DRAFT", status="DRAFT"),
            _article("KB-RETIRED", status="RETIRED"),
        ],
    )
    catalog = DemoFaqCatalog.from_sources([source])

    items = catalog.search("")

    assert [item["knowledge_id"] for item in items] == ["KB-APPROVED"]
    assert "answer" not in items[0]
    assert "reviewed_by" not in items[0]
    assert "reviewed_at" not in items[0]
    assert "source" not in items[0]


def test_featured_groups_have_at_most_four_groups_and_four_items_each(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    rows = []
    for index in range(6):
        rows.append(_article(f"KB-SIAGRI-{index}", title=f"SIAGRI {index}"))
    for index in range(3):
        rows.append(
            _article(
                f"KB-CIGAM-{index}",
                system="CIGAM",
                title=f"CIGAM {index}",
                question="CIGAM não abre.",
            )
        )
    _write(source, rows)
    catalog = DemoFaqCatalog.from_sources([source])

    groups = catalog.featured_groups()

    assert len(groups) <= 4
    assert all(len(group["items"]) <= 4 for group in groups)
    assert sum(len(group["items"]) for group in groups) <= 16


def test_search_is_accent_insensitive_and_deterministic(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(
        source,
        [
            _article(
                "KB-CIGAM", system="CIGAM", title="Acesso ao CIGAM", question="CIGAM não abre."
            ),
            _article("KB-SIAGRI", title="Acesso ao SIAGRI", question="SIAGRI não abre."),
        ],
    )
    catalog = DemoFaqCatalog.from_sources([source])

    first = catalog.search("nao abre cigam")
    second = catalog.search("não abre CIGAM")

    assert first == second
    assert first[0]["knowledge_id"] == "KB-CIGAM"


def test_m365_password_detail_exposes_only_fixed_procedure_url(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(
        source,
        [
            _article(
                "KB-SYN-M365-PASSWORD-001",
                system="OFFICE 365",
                title="Recuperar acesso ao Microsoft 365",
                question="Minha senha não funciona.",
                tags=["senha", "microsoft-365"],
            )
        ],
    )
    detail = DemoFaqCatalog.from_sources([source]).detail("KB-SYN-M365-PASSWORD-001")

    assert (
        detail["procedure_url"] == "https://mysignins.microsoft.com/security-info/password/change"
    )


def test_unknown_detail_fails_closed(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(source, [_article("KB-ONE")])
    catalog = DemoFaqCatalog.from_sources([source])

    with pytest.raises(FaqNotFoundError):
        catalog.detail("KB-MISSING")
