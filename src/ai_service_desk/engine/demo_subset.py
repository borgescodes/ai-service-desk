from __future__ import annotations

import hashlib
import re

import pandas as pd

from ai_service_desk.engine.index import corpus_bytes
from ai_service_desk.engine.validation import normalize_text

DEMO_RECIPE = "competition-demo-v1"
GROUPS = ("cigam", "siagri", "printing", "access", "software", "general")
SEARCH_COLUMNS = ("catalogo", "area", "item", "title", "texto_busca")
PATTERNS = {
    "cigam": re.compile(r"\bcigam\b"),
    "siagri": re.compile(r"\bsiagri\b"),
    "printing": re.compile(r"\b(impressora|impressao|imprimir|printer)\b"),
    "access": re.compile(r"\b(acesso|login|autenticacao|entrar)\b"),
    "software": re.compile(r"\b(instalacao|instalar|software|programa|aplicativo)\b"),
}


def _stable_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _search_text(data: pd.DataFrame) -> pd.Series:
    parts = []
    for column in SEARCH_COLUMNS:
        if column in data.columns:
            parts.append(data[column].fillna("").astype(str))
        else:
            parts.append(pd.Series("", index=data.index, dtype=str))
    combined = parts[0]
    for part in parts[1:]:
        combined = combined.str.cat(part, sep=" ")
    return combined.map(normalize_text)


def _canonical_hash(data: pd.DataFrame) -> str:
    return hashlib.sha256(corpus_bytes(data)).hexdigest()


def build_demo_subset(data: pd.DataFrame, per_group: int = 40) -> tuple[pd.DataFrame, dict]:
    if not isinstance(per_group, int) or not 1 <= per_group <= 100:
        raise ValueError("per_group deve estar entre 1 e 100.")
    if "ticket_id" not in data.columns or data.empty:
        raise ValueError("Corpus de demo sem ticket_id ou vazio.")
    ticket_ids = data["ticket_id"].astype(str)
    if ticket_ids.str.strip().eq("").any() or ticket_ids.duplicated().any():
        raise ValueError("Corpus de demo possui ticket_id vazio ou duplicado.")

    working = data.copy()
    working["_demo_text"] = _search_text(working)
    working["_demo_hash"] = ticket_ids.map(_stable_hash)

    selected_indices: list[int] = []
    used: set[int] = set()
    group_counts: dict[str, int] = {}

    for group in GROUPS[:-1]:
        pattern = PATTERNS[group]
        candidates = working[
            working["_demo_text"].map(lambda value: bool(pattern.search(value)))
            & ~working.index.isin(used)
        ].sort_values("_demo_hash")
        if len(candidates) < per_group:
            raise ValueError(
                f"Grupo {group} possui somente {len(candidates)} candidatos; esperado {per_group}."
            )
        chosen = list(candidates.index[:per_group])
        selected_indices.extend(chosen)
        used.update(chosen)
        group_counts[group] = len(chosen)

    remaining = working[~working.index.isin(used)].sort_values("_demo_hash")
    if len(remaining) < per_group:
        raise ValueError(
            f"Grupo general possui somente {len(remaining)} candidatos; esperado {per_group}."
        )
    chosen = list(remaining.index[:per_group])
    selected_indices.extend(chosen)
    group_counts["general"] = len(chosen)

    subset = data.loc[selected_indices].copy().reset_index(drop=True)
    report = {
        "version": 1,
        "recipe": DEMO_RECIPE,
        "source_rows": int(len(data)),
        "selected_rows": int(len(subset)),
        "per_group": int(per_group),
        "groups": group_counts,
        "source_canonical_sha256": _canonical_hash(data),
        "subset_canonical_sha256": _canonical_hash(subset),
    }
    return subset, report
