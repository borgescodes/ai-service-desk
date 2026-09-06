"""Context-aware retrieval over unvalidated historical tickets."""

import math
import re
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

from ai_service_desk.engine.classification import (
    SYSTEM_ALIASES,
    classify_ticket,
    explicit_systems,
)
from ai_service_desk.engine.data import clean_text, sanitize, sensitive
from ai_service_desk.engine.index import load_index
from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_matrix, normalize_text

INTENT_TERMS = {
    "PROBLEMA_IMPRESSAO": ("impressora", "scanner", "nao imprime"),
    "PROBLEMA_REDE": ("rede", "internet", "conexao", "vpn"),
    "LIBERACAO_ROTINA": ("liberacao de rotinas", "liberar rotina", "liberacao de rotina"),
    "PROBLEMA_ACESSO": ("acesso", "liberar acesso"),
}
METADATA_COLUMNS = ("catalogo", "area", "item")


def _contains_name(text: str, name: str) -> bool:
    normalized_name = normalize_text(name)
    if not normalized_name:
        return False
    return bool(
        re.search(rf"(?<!\w){re.escape(normalized_name)}(?!\w)", normalize_text(text))
    )


def _term_mask(data: pd.DataFrame, columns: tuple[str, ...], terms: tuple[str, ...]) -> np.ndarray:
    mask = np.zeros(len(data), dtype=bool)
    normalized_terms = tuple(normalize_text(term) for term in terms if normalize_text(term))
    for column in columns:
        if column not in data.columns:
            continue
        values = data[column].map(normalize_text)
        for term in normalized_terms:
            mask |= values.str.contains(re.escape(term), regex=True, na=False).to_numpy()
    return mask


def select_context_pool(
    data: pd.DataFrame,
    system: str,
    intent: str,
    min_matches: int = 3,
) -> np.ndarray:
    all_indices = np.arange(len(data), dtype=int)
    pool = all_indices
    system_norm = normalize_text(system)
    if system_norm:
        matches = np.flatnonzero(_term_mask(data, METADATA_COLUMNS, (system_norm,)))
        if len(matches) >= min_matches:
            pool = matches
    terms = INTENT_TERMS.get(intent, ())
    if terms:
        subset = data.iloc[pool]
        matches = _term_mask(subset, ("catalogo", "area", "item", "texto_busca"), terms)
        selected = pool[np.flatnonzero(matches)]
        if len(selected) >= min_matches:
            pool = selected
    return np.asarray(pool, dtype=int)


def filter_by_threshold(
    scores: np.ndarray,
    indices: np.ndarray,
    threshold: float = 0.65,
    top_k: int = 5,
) -> np.ndarray:
    score_values = np.asarray(scores, dtype=np.float32)
    index_values = np.asarray(indices, dtype=int)
    eligible = index_values[score_values[index_values] >= float(threshold)]
    if not len(eligible):
        return np.array([], dtype=int)
    ordered = eligible[np.argsort(score_values[eligible])[::-1]]
    return ordered[: max(0, int(top_k))]


def _system_matches(row: dict, aliases: tuple[str, ...]) -> bool:
    value = " ".join(
        str(row.get(key, "")) for key in ("catalogo", "area", "item", "title", "texto_busca")
    )
    return any(_contains_name(value, alias) for alias in aliases)


def retrieve(
    data: pd.DataFrame,
    matrix,
    query,
    classification: TicketClassification,
    text: str,
    threshold: float = 0.65,
    top_k: int = 5,
    min_matches: int = 3,
) -> dict:
    if not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("Limiar deve estar entre -1 e 1.")
    if not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ValueError("top_k deve estar entre 1 e 20.")
    matrix_values = np.asarray(matrix, dtype=np.float32)
    query_values = np.asarray(query, dtype=np.float32)
    if (
        matrix_values.ndim != 2
        or query_values.ndim != 1
        or len(data) != matrix_values.shape[0]
        or len(query_values) != matrix_values.shape[1]
    ):
        raise ValueError("Dimensoes de consulta, documentos e indice nao correspondem.")
    if not np.isfinite(matrix_values).all() or not np.isfinite(query_values).all():
        raise ValueError("Vetores invalidos.")
    normalized_query = normalize_matrix(query_values.reshape(1, -1))[0]
    scores = matrix_values @ normalized_query
    result = {
        "status": "SEM_EVIDENCIA",
        "classification": asdict(classification),
        "threshold": float(threshold),
        "context_mode": "",
        "pool_size": 0,
        "total_documents": len(data),
        "best_score": None,
        "candidates": [],
        "warnings": [
            "Historicos nao validados. Similaridade nao e probabilidade nem autorizacao."
        ],
        "timings": {},
    }
    if len(explicit_systems(text)) > 1:
        result.update(
            status="CONTEXTO_AMBIGUO",
            context_mode=(
                "Mais de um sistema explicito. Confirmar o alvo antes de restringir a busca."
            ),
        )
        return result

    pool = select_context_pool(data, classification.system, classification.intent, min_matches)
    result["context_mode"] = "Contexto de intencao ou base geral"
    if classification.system:
        aliases = SYSTEM_ALIASES.get(classification.system, (classification.system,))
        rows = data.fillna("").to_dict("records")
        compatible = np.array(
            [index for index in pool if _system_matches(rows[int(index)], aliases)], dtype=int
        )
        if not len(compatible):
            compatible = np.array(
                [index for index in range(len(data)) if _system_matches(rows[index], aliases)],
                dtype=int,
            )
        if not len(compatible):
            result.update(
                status="SEM_CONTEXTO",
                context_mode=(
                    "Fallback exploratorio: nenhum historico compativel com o sistema explicito."
                ),
            )
            return result
        pool = compatible
        result["context_mode"] = "Sistema explicito: " + classification.system
        if len(pool) < min_matches:
            result["warnings"].append(
                "Contexto escasso. Outros sistemas nao foram usados para completar resultados."
            )

    safe: list[int] = []
    blocked = 0
    for index in pool:
        row = data.iloc[int(index)]
        combined = " ".join(
            str(row.get(key, "")) for key in ("texto_busca", "title", "historico_atendimento")
        )
        if sensitive(combined):
            blocked += 1
        else:
            safe.append(int(index))
    pool = np.asarray(safe, dtype=int)
    result["pool_size"] = len(pool)
    if blocked:
        result["warnings"].append(
            f"{blocked} registros com termos sensiveis foram excluidos dos candidatos."
        )
    if len(pool):
        result["best_score"] = float(scores[pool].max())
    indices = filter_by_threshold(scores, pool, threshold, top_k)
    for index in indices:
        row = data.iloc[int(index)]
        result["candidates"].append(
            {
                "ticket_id": str(row.get("ticket_id", "")),
                "ticket_number": str(row.get("ticket_number", "")),
                "score": float(scores[index]),
                "title": sanitize(row.get("title", "")),
                "catalogo": str(row.get("catalogo", "")),
                "area": str(row.get("area", "")),
                "item": str(row.get("item", "")),
                "texto_busca": sanitize(row.get("texto_busca", "")),
                "historico_atendimento": sanitize(row.get("historico_atendimento", "")),
                "status_conhecimento": "HISTORICO_NAO_VALIDADO",
            }
        )
    if result["candidates"]:
        result["status"] = "ENCONTRADOS"
    return result


def format_result(result: dict, show_history: bool = False) -> str:
    classification = result["classification"]
    lines = [
        "",
        "Sistema identificado: " + (classification["system"] or "nao informado / ambiguo"),
        "Intencao: " + classification["intent"],
        "Contexto: " + result["context_mode"],
        f"Documentos candidatos: {result['pool_size']} de {result['total_documents']}",
        f"Limiar experimental: {result['threshold']:.4f}",
    ]
    if result.get("best_score") is not None:
        lines.append(f"Melhor score no contexto: {result['best_score']:.4f}")
    if result["status"] == "CONTEXTO_AMBIGUO":
        lines.append(
            "Qual dos sistemas e o alvo deste atendimento? Nenhum historico sera usado como procedimento."
        )
    elif not result["candidates"]:
        lines.append("Nenhum historico suficientemente semelhante foi encontrado.")
        lines.append(
            "Proxima etapa sugerida: coletar mais informacoes ou encaminhar a um tecnico. Nada foi executado."
        )
    else:
        lines.append(
            f"\n{len(result['candidates'])} historico(s) candidato(s). Nao sao solucoes aprovadas."
        )
        for position, row in enumerate(result["candidates"], 1):
            lines.extend(
                [
                    f"\n{position}. Score: {row['score']:.4f} | Ticket: {row['ticket_number']}",
                    "   Titulo: " + row["title"],
                    "   Classificacao: "
                    + " > ".join(row[key] for key in ("catalogo", "area", "item")),
                    "   Problema: " + clean_text(row["texto_busca"])[:350],
                    "   Estado: HISTORICO_NAO_VALIDADO",
                ]
            )
            if show_history:
                lines.append(
                    "   Registro de atendimento (revisar): "
                    + (row["historico_atendimento"] or "Sem texto util.")[:1800]
                )
    if result.get("timings"):
        lines.append(
            "\nTempos medidos: "
            + ", ".join(f"{key}={value:.2f}s" for key, value in result["timings"].items())
        )
    for warning in result["warnings"]:
        lines.append("Aviso: " + warning)
    return "\n".join(lines) + "\n"


class RetrievalEngine:
    def __init__(
        self,
        index_directory,
        client,
        embedder,
        threshold: float = 0.65,
        top_k: int = 5,
    ):
        self.df, self.matrix, self.manifest = load_index(index_directory)
        if (
            self.manifest["model"] != embedder.model
            or self.manifest["model_digest"] != embedder.digest
        ):
            raise ValueError("Modelo de consulta diferente do modelo do indice. Gere indice compativel.")
        if self.manifest["dimensions"] != embedder.dimensions:
            raise ValueError("Dimensoes do modelo diferentes do indice.")
        self.client = client
        self.embedder = embedder
        self.threshold = threshold
        self.top_k = top_k

    def search(self, text: str) -> dict:
        start = time.perf_counter()
        classification = classify_ticket(text, self.client.chat)
        after_classification = time.perf_counter()
        query = self.embedder.embed([text])[0]
        after_embedding = time.perf_counter()
        result = retrieve(
            self.df,
            self.matrix,
            query,
            classification,
            text,
            self.threshold,
            self.top_k,
        )
        finish = time.perf_counter()
        result["timings"] = {
            "classificacao": after_classification - start,
            "embedding": after_embedding - after_classification,
            "busca": finish - after_embedding,
            "total": finish - start,
        }
        return result
