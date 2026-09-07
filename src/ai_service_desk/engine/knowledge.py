"""Approved knowledge schema and private index adapter for Phase 4."""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from ai_service_desk.engine.classification import ALLOWED_INTENTS

KNOWLEDGE_SCHEMA_VERSION = 1
KNOWLEDGE_DOMAIN = "APPROVED_KNOWLEDGE"
PROJECTION_RECIPE = "knowledge-search-v1"
ALLOWED_STATUSES = {"DRAFT", "APPROVED", "RETIRED"}
PUBLIC_FIELDS = {
    "knowledge_id",
    "title",
    "question",
    "answer",
    "system",
    "intent",
    "tags",
    "source",
    "status",
    "reviewed_by",
    "reviewed_at",
    "version",
}


def _required_text(article: dict, field: str, limit: int) -> str:
    value = article.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} deve ser texto nao vazio com ate {limit} caracteres.")
    return value


def _optional_text(article: dict, field: str, limit: int) -> str:
    value = article.get(field)
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{field} deve ser texto com ate {limit} caracteres.")
    return value


def _validate_reviewed_at(value: str) -> None:
    if not value:
        return
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("reviewed_at deve ser ISO 8601 com timezone.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at deve ser ISO 8601 com timezone.")


def _validate_article(article: object) -> dict:
    if not isinstance(article, dict):
        raise ValueError("Cada artigo de knowledge deve ser um objeto JSON.")
    if set(article) != PUBLIC_FIELDS:
        missing = sorted(PUBLIC_FIELDS - set(article))
        extra = sorted(set(article) - PUBLIC_FIELDS)
        details = []
        if missing:
            details.append("ausentes=" + ",".join(missing))
        if extra:
            details.append("extras=" + ",".join(extra))
        raise ValueError("campos de knowledge invalidos: " + "; ".join(details))

    _required_text(article, "knowledge_id", 120)
    _required_text(article, "title", 180)
    _required_text(article, "question", 1200)
    _required_text(article, "answer", 5000)
    _optional_text(article, "system", 120)
    _required_text(article, "source", 120)
    reviewed_by = _optional_text(article, "reviewed_by", 120)
    reviewed_at = _optional_text(article, "reviewed_at", 80)

    intent = article["intent"]
    if not isinstance(intent, str) or intent not in ALLOWED_INTENTS:
        raise ValueError("intent fora do contrato oficial.")

    status = article["status"]
    if not isinstance(status, str) or status not in ALLOWED_STATUSES:
        raise ValueError("status deve ser DRAFT, APPROVED ou RETIRED.")

    tags = article["tags"]
    if (
        not isinstance(tags, list)
        or len(tags) > 12
        or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 60 for tag in tags)
    ):
        raise ValueError("tags deve conter ate 12 textos nao vazios com ate 60 caracteres.")

    version = article["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        raise ValueError("version deve ser inteiro positivo.")

    _validate_reviewed_at(reviewed_at)
    if status == "APPROVED" and (not reviewed_by.strip() or not reviewed_at):
        raise ValueError("Artigo APPROVED exige reviewed_by e reviewed_at validos para review.")

    return dict(article)


def load_knowledge(path: str | Path) -> list[dict]:
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ValueError("Arquivo de knowledge nao encontrado.")
    articles: list[dict] = []
    seen: set[str] = set()
    try:
        with source.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"JSON invalido na linha {line_number}.") from exc
                article = _validate_article(raw)
                knowledge_id = article["knowledge_id"]
                if knowledge_id in seen:
                    raise ValueError(f"knowledge_id duplicado: {knowledge_id}")
                seen.add(knowledge_id)
                articles.append(article)
    except UnicodeDecodeError as exc:
        raise ValueError("Knowledge deve ser JSONL UTF-8 valido.") from exc
    if not articles:
        raise ValueError("Base de knowledge vazia.")
    return articles


def approved_articles(articles: list[dict]) -> list[dict]:
    return [dict(article) for article in articles if article.get("status") == "APPROVED"]


def _project_approved_articles(articles: list[dict]) -> pd.DataFrame:
    rows: list[dict] = []
    for source in articles:
        article = _validate_article(source)
        if article["status"] != "APPROVED":
            raise ValueError("A projecao de indice aceita somente artigos APPROVED.")
        tags = list(article["tags"])
        semantic_text = "\n".join(
            [
                article["title"],
                article["question"],
                article["system"],
                article["intent"],
                " ".join(tags),
            ]
        )
        rows.append(
            {
                "ticket_id": article["knowledge_id"],
                "texto_busca": semantic_text,
                **article,
                "tags": tags,
            }
        )
    return pd.DataFrame(rows)
