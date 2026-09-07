import json
from pathlib import Path

import numpy as np
import pytest

from ai_service_desk.engine.index import build_index, load_index
from ai_service_desk.engine.knowledge import (
    _project_approved_articles,
    approved_articles,
    load_knowledge,
)


class FakeEmbedder:
    model = "qwen3-embedding:0.6b"
    digest = "phase4-test-digest"
    dimensions = 3

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray([[len(text) + 1, 2, 3] for text in texts], dtype=np.float32)


def valid_article(
    knowledge_id: str = "KB-SYN-CIGAM-ACCESS-001",
    status: str = "APPROVED",
) -> dict:
    reviewed_by = "synthetic-reviewer" if status == "APPROVED" else ""
    reviewed_at = "2026-09-07T12:00:00-03:00" if status == "APPROVED" else ""
    return {
        "knowledge_id": knowledge_id,
        "title": "Acesso sintetico ao CIGAM",
        "question": "Nao consigo acessar o CIGAM.",
        "answer": "Procedimento sintetico aprovado para demonstracao.",
        "system": "CIGAM",
        "intent": "PROBLEMA_ACESSO",
        "tags": ["acesso", "cigam"],
        "source": "SYNTHETIC_DEMO",
        "status": status,
        "reviewed_by": reviewed_by,
        "reviewed_at": reviewed_at,
        "version": 1,
    }


def write_articles(tmp_path: Path, articles: list[dict], name: str = "knowledge.jsonl") -> Path:
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps(article, ensure_ascii=False) + "\n" for article in articles),
        encoding="utf-8",
    )
    return path


def test_load_knowledge_accepts_exact_public_schema(tmp_path: Path) -> None:
    path = write_articles(tmp_path, [valid_article()])
    articles = load_knowledge(path)
    assert articles == [valid_article()]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda item: item.update(answer=""), "answer"),
        (lambda item: item.update(intent="INVENTADO"), "intent"),
        (lambda item: item.update(status="PUBLISHED"), "status"),
        (lambda item: item.update(version=0), "version"),
        (lambda item: item.update(tags=["x" * 61]), "tags"),
        (lambda item: item.update(extra="x"), "campos"),
    ],
)
def test_load_knowledge_rejects_schema_violations(tmp_path: Path, mutate, match: str) -> None:
    article = valid_article()
    mutate(article)
    path = write_articles(tmp_path, [article])
    with pytest.raises(ValueError, match=match):
        load_knowledge(path)


def test_load_knowledge_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = write_articles(tmp_path, [valid_article(), valid_article()])
    with pytest.raises(ValueError, match="duplicado"):
        load_knowledge(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [("reviewed_by", ""), ("reviewed_at", ""), ("reviewed_at", "2026-09-07T12:00:00")],
)
def test_approved_requires_reviewer_and_timezone_aware_timestamp(
    tmp_path: Path, field: str, value: str
) -> None:
    article = valid_article()
    article[field] = value
    path = write_articles(tmp_path, [article])
    with pytest.raises(ValueError, match="review"):
        load_knowledge(path)


def test_draft_and_retired_are_valid_source_states_but_not_approved(tmp_path: Path) -> None:
    draft = valid_article("KB-SYN-DRAFT-001", "DRAFT")
    retired = valid_article("KB-SYN-RETIRED-001", "RETIRED")
    path = write_articles(tmp_path, [draft, retired])
    loaded = load_knowledge(path)
    assert approved_articles(loaded) == []


def test_private_projection_uses_knowledge_id_and_excludes_answer_from_embedding_text() -> None:
    article = valid_article()
    projected = _project_approved_articles([article])
    assert projected.ticket_id.tolist() == [article["knowledge_id"]]
    assert projected.knowledge_id.tolist() == [article["knowledge_id"]]
    assert projected.status.tolist() == ["APPROVED"]
    assert projected.iloc[0].texto_busca == (
        article["title"]
        + "\n"
        + article["question"]
        + "\n"
        + article["system"]
        + "\n"
        + article["intent"]
        + "\n"
        + " ".join(article["tags"])
    )
    assert article["answer"] not in projected.iloc[0].texto_busca


def test_projection_rejects_non_approved_articles() -> None:
    with pytest.raises(ValueError, match="APPROVED"):
        _project_approved_articles([valid_article("KB-SYN-DRAFT-001", "DRAFT")])


def test_build_index_round_trip_preserves_approved_knowledge_metadata(tmp_path: Path) -> None:
    approved = valid_article()
    source = [
        approved,
        valid_article("KB-SYN-DRAFT-001", "DRAFT"),
        valid_article("KB-SYN-RETIRED-001", "RETIRED"),
    ]
    projected = _project_approved_articles(approved_articles(source))
    root = tmp_path / "index"
    build_index(projected, root, FakeEmbedder(), batch_size=1)
    loaded, _, manifest = load_index(root)

    assert len(loaded) == 1
    row = loaded.iloc[0]
    assert row["knowledge_id"] == approved["knowledge_id"]
    assert row["answer"] == approved["answer"]
    assert row["system"] == approved["system"]
    assert row["intent"] == approved["intent"]
    assert row["status"] == "APPROVED"
    assert row["reviewed_by"] == approved["reviewed_by"]
    assert row["reviewed_at"] == approved["reviewed_at"]
    assert int(row["version"]) == approved["version"]
    assert row["ticket_id"] == approved["knowledge_id"]
    assert manifest["rows"] == 1


def test_answer_change_changes_source_hash_without_changing_embedding_text(tmp_path: Path) -> None:
    first = valid_article()
    second = valid_article()
    second["answer"] = "Outra resposta sintetica aprovada."

    first_projection = _project_approved_articles([first])
    second_projection = _project_approved_articles([second])
    assert first_projection.iloc[0].texto_busca == second_projection.iloc[0].texto_busca

    first_state = build_index(first_projection, tmp_path / "first", FakeEmbedder(), batch_size=1)
    second_state = build_index(second_projection, tmp_path / "second", FakeEmbedder(), batch_size=1)
    assert first_state["source_hash"] != second_state["source_hash"]
