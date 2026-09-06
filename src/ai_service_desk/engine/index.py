"""Reproducible NumPy index with checkpoints and provenance."""

import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

from ai_service_desk.engine.data import load_corpus
from ai_service_desk.engine.validation import normalize_matrix

RECIPE = "texto_busca-plain-v1"


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def corpus_bytes(data: pd.DataFrame) -> bytes:
    lines = [
        json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False)
        for row in data.fillna("").to_dict("records")
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


@contextmanager
def index_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "index.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(
            "Indice bloqueado por outra execucao. Se houve queda, confirme que nao ha indexacao "
            "ativa antes de remover index.lock."
        ) from exc
    os.write(descriptor, str(os.getpid()).encode())
    os.close(descriptor)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def _validate_data(data: pd.DataFrame) -> None:
    if data.empty or not {"ticket_id", "texto_busca"} <= set(data.columns):
        raise ValueError("Corpus vazio ou sem campos obrigatorios.")
    if data.ticket_id.duplicated().any() or data.ticket_id.astype(str).str.strip().eq("").any():
        raise ValueError("IDs vazios ou duplicados.")
    if not data.texto_busca.map(lambda value: isinstance(value, str) and bool(value.strip())).all():
        raise ValueError("Texto de busca vazio.")


def _validate_vectors(matrix: np.ndarray, rows: int, dimensions: int) -> None:
    if matrix.shape != (rows, dimensions):
        raise ValueError("Dimensoes de embeddings nao correspondem aos documentos/modelo.")
    if not np.isfinite(matrix).all() or not np.allclose(
        np.linalg.norm(matrix, axis=1), 1, atol=1e-4
    ):
        raise ValueError("Vetores nao finitos, zerados ou nao normalizados.")


def build_index(
    data: pd.DataFrame,
    directory: str | Path,
    embedder,
    batch_size: int = 10,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    _validate_data(data)
    if not isinstance(batch_size, int) or not 1 <= batch_size <= 100:
        raise ValueError("Lote deve estar entre 1 e 100.")
    root = Path(directory)
    raw = corpus_bytes(data)
    source_hash = hashlib.sha256(raw).hexdigest()
    dimensions = embedder.dimensions
    with index_lock(root):
        manifest_path = root / "manifest.json"
        matrix_path = root / "embeddings.npy"
        documents_path = root / "documents.jsonl"
        expected = {
            "source_hash": source_hash,
            "rows": len(data),
            "dimensions": dimensions,
            "model": embedder.model,
            "model_digest": embedder.digest,
            "recipe": RECIPE,
        }
        if manifest_path.exists():
            state = json.loads(manifest_path.read_text(encoding="utf-8"))
            if any(state.get(key) != value for key, value in expected.items()):
                raise ValueError(
                    "Indice pertence a outro corpus, modelo ou configuracao. Use outra pasta de indice."
                )
            if not documents_path.exists() or file_hash(documents_path) != source_hash:
                raise ValueError("Metadados alterados no indice.")
            if state.get("complete"):
                load_index(root)
                return state
            matrix = np.load(matrix_path, mmap_mode="r+", allow_pickle=False)
            if matrix.shape != (len(data), dimensions):
                raise ValueError("Matriz parcial com dimensoes incorretas.")
            for batch in state.get("batches", []):
                actual = hashlib.sha256(
                    matrix[batch["start"] : batch["end"]].tobytes()
                ).hexdigest()
                if actual != batch["sha256"]:
                    raise ValueError("Lote salvo esta corrompido. Use outro indice.")
        else:
            if matrix_path.exists() or documents_path.exists():
                raise ValueError("Pasta de indice contem arquivos sem manifesto. Use uma nova pasta.")
            documents_path.write_bytes(raw)
            matrix = np.lib.format.open_memmap(
                matrix_path,
                mode="w+",
                dtype=np.float32,
                shape=(len(data), dimensions),
            )
            matrix.flush()
            state = {
                "version": 1,
                "completed": 0,
                "complete": False,
                "batches": [],
                "legacy_import": False,
                **expected,
            }
            atomic_json(manifest_path, state)
        try:
            start = state["completed"]
            if not 0 <= start <= len(data):
                raise ValueError("Checkpoint invalido.")
            while start < len(data):
                end = min(start + batch_size, len(data))
                batch = normalize_matrix(embedder.embed(data.texto_busca.iloc[start:end].tolist()))
                _validate_vectors(batch, end - start, dimensions)
                matrix[start:end] = batch
                matrix.flush()
                state["batches"].append(
                    {
                        "start": start,
                        "end": end,
                        "sha256": hashlib.sha256(batch.tobytes()).hexdigest(),
                    }
                )
                state["completed"] = end
                atomic_json(manifest_path, state)
                if progress:
                    progress(end, len(data))
                start = end
            state["matrix_hash"] = file_hash(matrix_path)
            state["complete"] = True
            atomic_json(manifest_path, state)
        finally:
            del matrix
        return state


def load_index(directory: str | Path) -> tuple[pd.DataFrame, np.ndarray, dict]:
    root = Path(directory)
    manifest_path = root / "manifest.json"
    documents_path = root / "documents.jsonl"
    matrix_path = root / "embeddings.npy"
    if not manifest_path.exists():
        raise ValueError("Indice nao encontrado. Execute index ou import-legacy.")
    state = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        state.get("version") != 1
        or not state.get("complete")
        or state.get("completed") != state.get("rows")
    ):
        raise ValueError("Indice incompleto. Repita a indexacao para retomar.")
    if state.get("recipe") != RECIPE:
        raise ValueError("Receita de embedding incompativel.")
    if not documents_path.exists() or not matrix_path.exists():
        raise ValueError("Indice incompleto ou corrompido.")
    if file_hash(documents_path) != state["source_hash"] or file_hash(matrix_path) != state.get(
        "matrix_hash"
    ):
        raise ValueError("Indice alterado ou corrompido. Hash nao corresponde.")
    with documents_path.open(encoding="utf-8") as handle:
        data = pd.DataFrame([json.loads(line) for line in handle if line.strip()])
    _validate_data(data)
    matrix = np.load(matrix_path, allow_pickle=False, mmap_mode="r")
    _validate_vectors(matrix, len(data), state["dimensions"])
    if len(data) != state["rows"]:
        raise ValueError("Alinhamento de documentos invalido.")
    return data, matrix, state


def import_legacy(source: str | Path, target: str | Path, embedder) -> dict:
    source_path = Path(source)
    root = Path(target)
    if root.resolve() == source_path.resolve():
        raise ValueError("Importe em pasta nova, nunca sobre a origem.")
    data = load_corpus(source_path / "amostra_indexada.csv")
    original = np.load(source_path / "embeddings.npy", allow_pickle=False)
    matrix = normalize_matrix(original)
    _validate_vectors(matrix, len(data), embedder.dimensions)
    positions = sorted({0, len(data) // 2, len(data) - 1})
    sentinels = normalize_matrix(embedder.embed(data.texto_busca.iloc[positions].tolist()))
    if sentinels.shape != matrix[positions].shape or np.any(
        np.sum(sentinels * matrix[positions], axis=1) < 0.999
    ):
        raise ValueError(
            "Vetores antigos nao correspondem aos sentinelas do modelo atual. Gere um indice novo."
        )
    with index_lock(root):
        if (root / "manifest.json").exists() or (root / "embeddings.npy").exists():
            raise ValueError("Destino ja possui indice. Use outra pasta.")
        raw = corpus_bytes(data)
        (root / "documents.jsonl").write_bytes(raw)
        np.save(root / "embeddings.npy", matrix, allow_pickle=False)
        state = {
            "version": 1,
            "rows": len(data),
            "dimensions": embedder.dimensions,
            "model": embedder.model,
            "model_digest": embedder.digest,
            "recipe": RECIPE,
            "source_hash": hashlib.sha256(raw).hexdigest(),
            "matrix_hash": file_hash(root / "embeddings.npy"),
            "completed": len(data),
            "complete": True,
            "batches": [],
            "legacy_import": True,
            "sentinel_rows": positions,
            "provenance_note": (
                "Importacao legada validada por estrutura e tres sentinelas, "
                "nao por todos os vetores."
            ),
        }
        atomic_json(root / "manifest.json", state)
        return state
