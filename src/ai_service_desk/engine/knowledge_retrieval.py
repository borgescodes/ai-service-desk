"""Context-gated retrieval over approved knowledge only."""

import math
from dataclasses import asdict

import numpy as np
import pandas as pd

from ai_service_desk.engine.classification import (
    SYSTEM_ALIASES,
    classify_ticket,
    explicit_systems,
)
from ai_service_desk.engine.knowledge import load_knowledge_index
from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_matrix, normalize_text

DEFAULT_KNOWLEDGE_THRESHOLD = 0.65


def _system_matches(article_system: str, target: str) -> bool:
    article = normalize_text(article_system)
    wanted = normalize_text(target)
    if article == wanted:
        return True
    target_aliases = {normalize_text(value) for value in SYSTEM_ALIASES.get(target, (target,))}
    if article in target_aliases:
        return True
    for canonical, aliases in SYSTEM_ALIASES.items():
        normalized = {normalize_text(canonical), *(normalize_text(value) for value in aliases)}
        if wanted in normalized and article in normalized:
            return True
    return False


def _base_result(classification: TicketClassification, threshold: float, reason: str) -> dict:
    return {
        "status": "NO_APPROVED_KNOWLEDGE",
        "reason": reason,
        "threshold": float(threshold),
        "score": None,
        "classification": asdict(classification),
        "knowledge": None,
    }


def _eligible_pool(
    data: pd.DataFrame,
    classification: TicketClassification,
    text: str,
) -> tuple[np.ndarray, str]:
    if len(explicit_systems(text)) > 1:
        return np.array([], dtype=int), "CONTEXTO_AMBIGUO"

    target_system = classification.system.strip()
    if target_system:
        system_indices = np.asarray(
            [
                index
                for index, value in enumerate(data["system"].astype(str).tolist())
                if _system_matches(value, target_system)
            ],
            dtype=int,
        )
        if not len(system_indices):
            known = target_system in SYSTEM_ALIASES or any(
                _system_matches(canonical, target_system) for canonical in SYSTEM_ALIASES
            )
            return np.array([], dtype=int), "SYSTEM_MISMATCH" if known else "UNKNOWN_SYSTEM"
    else:
        system_indices = np.flatnonzero(data["system"].astype(str).str.strip().eq("").to_numpy())
        if not len(system_indices):
            return np.array([], dtype=int), "SYSTEM_MISMATCH"

    intent_indices = np.asarray(
        [index for index in system_indices if str(data.iloc[int(index)]["intent"]) == classification.intent],
        dtype=int,
    )
    if not len(intent_indices):
        return np.array([], dtype=int), "INTENT_MISMATCH"
    return intent_indices, "MATCH"


def retrieve_knowledge(
    data: pd.DataFrame,
    matrix,
    query,
    classification: TicketClassification,
    text: str,
    threshold: float = DEFAULT_KNOWLEDGE_THRESHOLD,
) -> dict:
    if not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("Limiar de knowledge deve estar entre -1 e 1.")
    if not isinstance(text, str) or not text.strip() or len(text) > 3000:
        raise ValueError("Consulta de knowledge invalida.")
    matrix_values = np.asarray(matrix, dtype=np.float32)
    query_values = np.asarray(query, dtype=np.float32)
    if (
        matrix_values.ndim != 2
        or query_values.ndim != 1
        or len(data) != matrix_values.shape[0]
        or len(query_values) != matrix_values.shape[1]
    ):
        raise ValueError("Dimensoes de consulta, knowledge e indice nao correspondem.")
    if not np.isfinite(matrix_values).all() or not np.isfinite(query_values).all():
        raise ValueError("Vetores de knowledge invalidos.")

    pool, reason = _eligible_pool(data, classification, text)
    if reason != "MATCH":
        return _base_result(classification, threshold, reason)

    normalized_matrix = normalize_matrix(matrix_values)
    normalized_query = normalize_matrix(query_values.reshape(1, -1))[0]
    scores = normalized_matrix @ normalized_query
    best_index = int(pool[np.argmax(scores[pool])])
    best_score = float(scores[best_index])
    if best_score < float(threshold):
        result = _base_result(classification, threshold, "BELOW_THRESHOLD")
        result["score"] = best_score
        return result

    row = data.iloc[best_index]
    return {
        "status": "KNOWLEDGE_FOUND",
        "reason": "MATCH",
        "threshold": float(threshold),
        "score": best_score,
        "classification": asdict(classification),
        "knowledge": {
            "knowledge_id": str(row["knowledge_id"]),
            "title": str(row["title"]),
            "answer": str(row["answer"]),
            "system": str(row["system"]),
            "intent": str(row["intent"]),
            "version": int(row["version"]),
        },
    }


def format_knowledge_result(result: dict) -> str:
    if result["status"] == "KNOWLEDGE_FOUND":
        return str(result["knowledge"]["answer"]) + "\n"
    return (
        "Nao encontrei uma orientacao validada suficiente para resolver isso automaticamente. "
        f"Motivo: {result['reason']}.\n"
    )


class KnowledgeEngine:
    def __init__(
        self,
        index_directory,
        client,
        embedder,
        threshold: float = DEFAULT_KNOWLEDGE_THRESHOLD,
    ):
        self.df, self.matrix, self.provenance = load_knowledge_index(index_directory)
        if (
            self.provenance["model"] != embedder.model
            or self.provenance["model_digest"] != embedder.digest
            or self.provenance["dimensions"] != embedder.dimensions
        ):
            raise ValueError("Modelo de consulta diferente do indice de knowledge aprovado.")
        if not math.isfinite(threshold) or not -1 <= threshold <= 1:
            raise ValueError("Limiar de knowledge deve estar entre -1 e 1.")
        self.client = client
        self.embedder = embedder
        self.threshold = float(threshold)

    def search(self, text: str) -> dict:
        classification = classify_ticket(text, self.client.chat)
        pool, reason = _eligible_pool(self.df, classification, text)
        if reason != "MATCH":
            return _base_result(classification, self.threshold, reason)
        if not len(pool):
            return _base_result(classification, self.threshold, "NO_ELIGIBLE_KNOWLEDGE")
        query = self.embedder.embed([text])[0]
        return retrieve_knowledge(
            self.df,
            self.matrix,
            query,
            classification,
            text,
            threshold=self.threshold,
        )
