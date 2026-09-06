"""Manual end-to-end validation for the local Ollama environment."""

import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from ai_service_desk.engine.data import load_corpus
from ai_service_desk.engine.index import atomic_json, build_index, import_legacy
from ai_service_desk.engine.ollama import LocalEmbedder, OllamaClient
from ai_service_desk.engine.retrieval import RetrievalEngine

CASES = [
    ("cigam", "o cigam fecha quando tento faturar", "ERRO_SISTEMA", "CIGAM"),
    (
        "impressora",
        "documento fica preso na fila e a impressora nao imprime",
        "PROBLEMA_IMPRESSAO",
        "",
    ),
    ("rotina", "preciso liberar a rotina 1024 do cigam", "LIBERACAO_ROTINA", "CIGAM"),
    ("desconhecido", "o sistema XYZ trava quando salvo", "ERRO_SISTEMA", "XYZ"),
]


def run_validation(
    corpus: str | Path,
    index: str | Path,
    report_path: str | Path,
    base_url: str = "http://127.0.0.1:11434",
    legacy: str | Path | None = None,
    threshold: float = 0.65,
) -> dict:
    report: dict = {
        "schema_version": 1,
        "ok": False,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "requests": requests.__version__,
        },
        "limitations": [
            "Teste funcional com quatro frases. Nao e medida de acuracia.",
            "Historico semelhante nao e solucao aprovada. Limiar experimental.",
        ],
        "cases": [],
        "index_reuse": None,
    }
    client = None
    started = time.perf_counter()
    try:
        client = OllamaClient(base_url)
        report["ollama_version"] = client.version()
        classifier = client.model_info("qwen3.5:4b")
        report["classifier_model"] = classifier.get("name", "qwen3.5:4b")
        report["classifier_digest"] = classifier["digest"]
        embedder = LocalEmbedder(client)
        report["embedding_model"] = embedder.model
        report["embedding_digest"] = embedder.digest
        index_path = Path(index)
        if not (index_path / "manifest.json").exists():
            imported = False
            if legacy:
                legacy_path = Path(legacy)
                if (legacy_path / "embeddings.npy").exists() and (
                    legacy_path / "amostra_indexada.csv"
                ).exists():
                    try:
                        import_legacy(legacy_path, index_path, embedder)
                        imported = True
                        report["index_reuse"] = (
                            "Importado; estrutura e tres sentinelas verificados."
                        )
                    except ValueError as exc:
                        report["index_reuse"] = "Nao reutilizado: " + str(exc)
            if not imported:
                data = load_corpus(corpus)
                build_index(data, index_path, embedder, batch_size=10)
                report["index_reuse"] = "Novo indice criado localmente."
        else:
            report["index_reuse"] = "Indice existente; manifesto e hashes verificados na leitura."

        engine = RetrievalEngine(index_path, client, embedder, threshold)
        report["rows"] = len(engine.df)
        report["shape"] = list(engine.matrix.shape)
        sample_text = engine.df.iloc[0].texto_busca
        query = embedder.embed([sample_text])[0]
        score = float(engine.matrix[0] @ query)
        report["self_match"] = {"score": score, "passed": score >= 0.99}

        for key, text, intent, system in CASES:
            result = engine.search(text)
            classification = result["classification"]
            checks = {
                "intent": classification["intent"] == intent,
                "system": classification["system"] == system,
            }
            if key == "rotina":
                checks["rotina_1024"] = classification["entities"].get("rotina") == "1024"
            if key == "desconhecido":
                checks["sem_historico_de_outro_sistema"] = not result["candidates"]
            if key == "impressora":
                checks["ao_menos_um_candidato"] = bool(result["candidates"])
            report["cases"].append(
                {
                    "name": key,
                    "query": text,
                    "classification": classification,
                    "checks": checks,
                    "passed": all(checks.values()),
                    "status": result["status"],
                    "context_mode": result["context_mode"],
                    "pool_size": result["pool_size"],
                    "best_score": result["best_score"],
                    "threshold": threshold,
                    "timings_seconds": result["timings"],
                    "candidates": [
                        {
                            "ticket_id": row["ticket_id"],
                            "ticket_number": row["ticket_number"],
                            "score": row["score"],
                        }
                        for row in result["candidates"]
                    ],
                }
            )
        report["ok"] = report["self_match"]["passed"] and all(
            case["passed"] for case in report["cases"]
        )
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        report["error"] = str(exc)
    except KeyboardInterrupt:
        report["error"] = "Interrompido pelo usuario. Indice pode ser retomado."
    finally:
        if client:
            client.close()
        report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        atomic_json(Path(report_path), report)
    return report
