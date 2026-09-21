from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ai_service_desk.engine.knowledge import approved_articles, load_knowledge

MAX_FAQ_RESULTS = 16
MAX_FEATURED_CATEGORIES = 4
MAX_FEATURED_PER_CATEGORY = 4
APPROVED_M365_PASSWORD_URL = "https://mysignins.microsoft.com/security-info/password/change"
APPROVED_PROCEDURE_URLS = {
    "KB-SYN-M365-PASSWORD-001": APPROVED_M365_PASSWORD_URL,
    "KB-SYN-FAQ-CDM-REQUEST-001": "https://cdm.juparana.com.br/",
}
FUNCTIONAL_ARTICLE_IDS = frozenset(APPROVED_PROCEDURE_URLS)

_FEATURED_CATEGORY_ORDER = (
    ("acessos-rotinas", "Acessos e rotinas"),
    ("erros-sistemas", "Erros em sistemas"),
    ("impressao-office-aplicativos", "Impressão, Office e aplicativos"),
    ("rede-internet", "Rede e internet"),
)


class FaqNotFoundError(ValueError):
    pass


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())


def _category(article: dict) -> tuple[str, str] | tuple[None, None]:
    system = _normalize(article.get("system", ""))
    tags = {_normalize(tag) for tag in article.get("tags", [])}
    intent = article.get("intent", "")

    for key, label in _FEATURED_CATEGORY_ORDER:
        if f"faq-{key}" in tags:
            return key, label
    if intent == "PROBLEMA_REDE" or tags & {"rede", "internet", "wifi", "wi-fi"}:
        return _FEATURED_CATEGORY_ORDER[3]
    if system in {"office 365", "microsoft 365", "outlook", "teams", "onedrive"} or tags & {
        "microsoft-365",
        "outlook",
        "teams",
        "onedrive",
    }:
        return _FEATURED_CATEGORY_ORDER[2]
    if intent == "PROBLEMA_IMPRESSAO" or tags & {"impressao", "impressora", "scanner"}:
        return _FEATURED_CATEGORY_ORDER[2]
    if intent == "PROBLEMA_ACESSO":
        return _FEATURED_CATEGORY_ORDER[0]
    if system or tags:
        return _FEATURED_CATEGORY_ORDER[1]
    return None, None


@dataclass(frozen=True)
class _Entry:
    article: dict
    category_key: str | None
    category_label: str | None


class DemoFaqCatalog:
    def __init__(self, entries: list[_Entry]) -> None:
        self._entries = entries
        self._by_id = {entry.article["knowledge_id"]: entry for entry in entries}

    @classmethod
    def from_sources(cls, sources: list[str | Path]) -> DemoFaqCatalog:
        merged: dict[str, dict] = {}
        for source in sources:
            for article in approved_articles(load_knowledge(source)):
                merged[article["knowledge_id"]] = article
        entries = []
        for article in merged.values():
            key, label = _category(article)
            entries.append(_Entry(article=article, category_key=key, category_label=label))
        entries.sort(
            key=lambda entry: (
                not any(tag.startswith("faq-") for tag in entry.article["tags"]),
                _normalize(entry.article["title"]),
                entry.article["knowledge_id"],
            )
        )
        return cls(entries)

    @staticmethod
    def _summary(entry: _Entry) -> dict:
        return {
            "knowledge_id": entry.article["knowledge_id"],
            "title": entry.article["title"],
            "question": entry.article["question"],
            "system": entry.article["system"],
            "category": entry.category_label or "Outros",
            "category_key": entry.category_key,
        }

    def featured_groups(self) -> list[dict]:
        groups = []
        for key, label in _FEATURED_CATEGORY_ORDER[:MAX_FEATURED_CATEGORIES]:
            entries = [entry for entry in self._entries if entry.category_key == key]
            functional = [
                entry
                for entry in entries
                if entry.article["knowledge_id"] in FUNCTIONAL_ARTICLE_IDS
            ]
            other = [entry for entry in entries if entry not in functional]
            items = [
                self._summary(entry) for entry in (functional + other)[:MAX_FEATURED_PER_CATEGORY]
            ]
            if items:
                groups.append({"key": key, "label": label, "items": items})
        return groups

    def search(self, query: str, category: str = "") -> list[dict]:
        normalized = _normalize(query)
        tokens = normalized.split()
        scored = []
        for entry in self._entries:
            if category and entry.category_key != category:
                continue
            article = entry.article
            haystacks = {
                "title": _normalize(article["title"]),
                "question": _normalize(article["question"]),
                "system": _normalize(article["system"]),
                "category": _normalize(entry.category_label or "Outros"),
                "tags": _normalize(" ".join(article["tags"])),
            }
            score = 0
            for token in tokens:
                if token in haystacks["title"]:
                    score += 8
                if token in haystacks["question"]:
                    score += 5
                if token in haystacks["system"] or token in haystacks["category"]:
                    score += 3
                if token in haystacks["tags"]:
                    score += 2
            if not tokens or score:
                scored.append((score, _normalize(article["title"]), article["knowledge_id"], entry))
        scored.sort(key=lambda row: (-row[0], row[1], row[2]))
        return [self._summary(row[3]) for row in scored[:MAX_FAQ_RESULTS]]

    def detail(self, knowledge_id: str) -> dict:
        entry = self._by_id.get(knowledge_id)
        if entry is None:
            raise FaqNotFoundError("Solução não encontrada.")
        detail = self._summary(entry)
        detail["answer"] = entry.article["answer"]
        detail["procedure_url"] = APPROVED_PROCEDURE_URLS.get(knowledge_id)
        detail["provenance"] = {
            field: entry.article[field] for field in ("source", "status", "version")
        }
        return detail
