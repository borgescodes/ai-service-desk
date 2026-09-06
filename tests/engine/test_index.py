import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ai_service_desk.engine.index import RECIPE, build_index, import_legacy, load_index
from ai_service_desk.engine.validation import normalize_matrix


class FakeEmbedder:
    model = "qwen3-embedding:0.6b"
    digest = "fake-test-digest"
    dimensions = 3

    def __init__(self, fail_call: int | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_call = fail_call

    def embed(self, texts: list[str]) -> np.ndarray:
        self.calls.append(list(texts))
        if len(self.calls) == self.fail_call:
            raise RuntimeError("synthetic interruption")
        return np.asarray([[len(text) + 1, 1, 2] for text in texts], dtype=np.float32)


@pytest.fixture
def corpus() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticket_id": str(index),
                "ticket_number": str(index),
                "title": "A",
                "texto_busca": f"problema {index}",
                "historico_atendimento": "nao e solucao validada",
            }
            for index in range(5)
        ]
    )


def test_build_and_load_preserve_alignment_and_manifest(tmp_path: Path, corpus: pd.DataFrame) -> None:
    embedder = FakeEmbedder()
    state = build_index(corpus, tmp_path / "index", embedder, batch_size=2)
    data, matrix, loaded = load_index(tmp_path / "index")
    assert matrix.shape == (5, 3)
    assert data.ticket_id.tolist() == corpus.ticket_id.tolist()
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), 1, atol=1e-6)
    assert loaded["recipe"] == RECIPE == "texto_busca-plain-v1"
    assert loaded["rows"] == 5
    assert loaded["dimensions"] == 3
    assert loaded["model"] == embedder.model
    assert loaded["model_digest"] == embedder.digest
    assert loaded["complete"] is True
    assert loaded["completed"] == 5
    assert "matrix_hash" in state


def test_resume_does_not_repeat_committed_batch(tmp_path: Path, corpus: pd.DataFrame) -> None:
    first = FakeEmbedder(fail_call=2)
    with pytest.raises(RuntimeError):
        build_index(corpus, tmp_path / "index", first, batch_size=2)
    second = FakeEmbedder()
    build_index(corpus, tmp_path / "index", second, batch_size=2)
    assert [item for batch in second.calls for item in batch] == corpus.texto_busca.tolist()[2:]


def test_completed_index_does_not_reembed(tmp_path: Path, corpus: pd.DataFrame) -> None:
    build_index(corpus, tmp_path / "index", FakeEmbedder(), batch_size=2)
    embedder = FakeEmbedder(fail_call=1)
    build_index(corpus, tmp_path / "index", embedder, batch_size=2)
    assert embedder.calls == []


def test_incomplete_changed_corrupt_and_digest_mismatch_are_refused(
    tmp_path: Path, corpus: pd.DataFrame
) -> None:
    incomplete = tmp_path / "incomplete"
    with pytest.raises(RuntimeError):
        build_index(corpus, incomplete, FakeEmbedder(fail_call=2), batch_size=2)
    with pytest.raises(ValueError):
        load_index(incomplete)

    root = tmp_path / "root"
    build_index(corpus, root, FakeEmbedder(), batch_size=2)
    changed = corpus.copy()
    changed.loc[0, "texto_busca"] = "outro"
    with pytest.raises(ValueError):
        build_index(changed, root, FakeEmbedder(), batch_size=2)
    mismatch = FakeEmbedder()
    mismatch.digest = "changed"
    with pytest.raises(ValueError):
        build_index(corpus, root, mismatch, batch_size=2)
    matrix = np.load(root / "embeddings.npy")
    matrix[0] = 0
    np.save(root / "embeddings.npy", matrix)
    with pytest.raises(ValueError):
        load_index(root)


def test_batch_size_and_wrong_shape_are_refused(tmp_path: Path, corpus: pd.DataFrame) -> None:
    for size in (0, 101):
        with pytest.raises(ValueError):
            build_index(corpus, tmp_path / f"size-{size}", FakeEmbedder(), batch_size=size)
    embedder = FakeEmbedder()
    embedder.embed = lambda texts: np.ones((1, 3), dtype=np.float32)  # type: ignore[method-assign]
    with pytest.raises(ValueError):
        build_index(corpus, tmp_path / "shape", embedder, batch_size=2)
    manifest = tmp_path / "shape" / "manifest.json"
    if manifest.exists():
        assert json.loads(manifest.read_text(encoding="utf-8"))["completed"] == 0


def test_import_legacy_uses_three_sentinels_and_new_destination(
    tmp_path: Path, corpus: pd.DataFrame
) -> None:
    source = tmp_path / "old"
    source.mkdir()
    embedder = FakeEmbedder()
    corpus.to_csv(source / "amostra_indexada.csv", sep=";", encoding="utf-8-sig", index=False)
    np.save(
        source / "embeddings.npy",
        normalize_matrix(embedder.embed(corpus.texto_busca.tolist())),
    )
    state = import_legacy(source, tmp_path / "new", embedder)
    data, matrix, loaded = load_index(tmp_path / "new")
    assert len(data) == 5
    assert matrix.shape == (5, 3)
    assert state["legacy_import"] is True
    assert loaded["sentinel_rows"] == [0, 2, 4]
    assert "nao" in loaded["provenance_note"].lower()
    with pytest.raises(ValueError):
        import_legacy(source, source, embedder)


def test_import_legacy_rejects_different_vectors(tmp_path: Path, corpus: pd.DataFrame) -> None:
    source = tmp_path / "old"
    source.mkdir()
    embedder = FakeEmbedder()
    corpus.to_csv(source / "amostra_indexada.csv", sep=";", index=False)
    np.save(source / "embeddings.npy", np.tile([0, 1, 0], (5, 1)).astype("float32"))
    with pytest.raises(ValueError):
        import_legacy(source, tmp_path / "new", embedder)


def test_document_hash_and_recipe_tampering_are_refused(tmp_path: Path, corpus: pd.DataFrame) -> None:
    root = tmp_path / "index"
    build_index(corpus, root, FakeEmbedder(), batch_size=2)
    documents = root / "documents.jsonl"
    documents.write_text(documents.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_index(root)

    root2 = tmp_path / "index2"
    build_index(corpus, root2, FakeEmbedder(), batch_size=2)
    manifest = json.loads((root2 / "manifest.json").read_text(encoding="utf-8"))
    manifest["recipe"] = "other-recipe"
    (root2 / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Receita"):
        load_index(root2)


def test_index_lock_prevents_concurrent_writer(tmp_path: Path, corpus: pd.DataFrame) -> None:
    root = tmp_path / "index"
    root.mkdir()
    (root / "index.lock").write_text("other", encoding="utf-8")
    with pytest.raises(ValueError, match="bloqueado"):
        build_index(corpus, root, FakeEmbedder(), batch_size=2)
