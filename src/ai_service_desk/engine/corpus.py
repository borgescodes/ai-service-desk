from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ai_service_desk.engine.data import load_corpus
from ai_service_desk.engine.index import atomic_json, corpus_bytes, file_hash

EXPECTED_COLUMNS = (
    "ticket_id",
    "ticket_number",
    "title",
    "description",
    "created_at",
    "catalogo",
    "area",
    "item",
    "mesa",
    "texto_busca",
    "texto_limitado",
    "historico_atendimento",
    "apontamento_ids",
    "status_conhecimento",
)

RISK_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "ipv4": re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"),
    "cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "phone": re.compile(r"(?<!\w)(?:\+55\s*)?\(?\d{2}\)?\s*9?\d{4}[- ]\d{4}(?!\d)"),
    "sensitive_term": re.compile(
        r"\b(senha|password|passwd|credencia\w*|token|secret|api[ _-]?key)\b", re.I
    ),
}


def ensure_external_path(path: str | Path, checkout: str | Path) -> Path:
    candidate = Path(path).resolve()
    root = Path(checkout).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate
    raise ValueError("Corpus, indice e relatorio reais devem ficar fora do checkout Git.")


def load_corpus_manifest(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Versao de manifesto de corpus nao suportada.")
    return data


def _risk_counts(data) -> dict[str, int]:
    columns = [column for column in EXPECTED_COLUMNS if column in data.columns]
    counts = {name: 0 for name in RISK_PATTERNS}
    for row in data[columns].fillna("").astype(str).itertuples(index=False, name=None):
        text = " ".join(row)
        for name, pattern in RISK_PATTERNS.items():
            if pattern.search(text):
                counts[name] += 1
    return counts


def audit_corpus(corpus_path: str | Path, manifest_path: str | Path | None = None) -> dict:
    path = Path(corpus_path)
    data = load_corpus(path)
    raw_hash = file_hash(path)
    canonical_hash = hashlib.sha256(corpus_bytes(data)).hexdigest()
    history = data["historico_atendimento"].astype(str).str.strip().ne("")
    limited = data["texto_limitado"].astype(str).str.lower().eq("true")
    report = {
        "version": 1,
        "rows": len(data),
        "columns": list(data.columns),
        "unique_ticket_ids": int(data["ticket_id"].nunique()),
        "empty_ticket_ids": int(data["ticket_id"].astype(str).str.strip().eq("").sum()),
        "empty_search_texts": int(data["texto_busca"].astype(str).str.strip().eq("").sum()),
        "with_history": int(history.sum()),
        "without_history": int((~history).sum()),
        "limited_texts": int(limited.sum()),
        "knowledge_status": {
            str(key): int(value)
            for key, value in data["status_conhecimento"]
            .value_counts(dropna=False)
            .to_dict()
            .items()
        },
        "raw_sha256": raw_hash,
        "canonical_sha256": canonical_hash,
        "max_lengths": {
            column: int(data[column].astype(str).str.len().max())
            for column in ("title", "description", "texto_busca", "historico_atendimento")
        },
        "risk_counts": _risk_counts(data),
        "privacy": {
            "rule_based_scan": True,
            "anonymization_claim": False,
            "human_review_required_before_history_display": True,
        },
    }
    if manifest_path is not None:
        validate_corpus_manifest(report, load_corpus_manifest(manifest_path))
        report["manifest_match"] = True
    return report


def validate_corpus_manifest(report: dict, manifest: dict) -> None:
    expected = manifest["expected"]
    checks = {
        "rows": report["rows"],
        "with_history": report["with_history"],
        "limited_texts": report["limited_texts"],
        "raw_sha256": report["raw_sha256"],
        "canonical_sha256": report["canonical_sha256"],
    }
    for key, actual in checks.items():
        if actual != expected[key]:
            raise ValueError(f"Snapshot divergente no campo agregado: {key}.")
    if report["columns"] != manifest["columns"]:
        raise ValueError("Schema do snapshot divergente do manifesto.")
    if report["unique_ticket_ids"] != report["rows"] or report["empty_ticket_ids"]:
        raise ValueError("ticket_id vazio ou duplicado no snapshot.")
    if report["empty_search_texts"]:
        raise ValueError("texto_busca vazio no snapshot.")
    if report["knowledge_status"] != {"HISTORICO_NAO_VALIDADO": report["rows"]}:
        raise ValueError("status_conhecimento invalido no snapshot.")


def write_safe_report(path: str | Path, report: dict) -> None:
    atomic_json(Path(path), report)
