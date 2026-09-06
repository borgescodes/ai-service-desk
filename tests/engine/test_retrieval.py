from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ai_service_desk.engine.retrieval import RetrievalEngine, format_result, retrieve
from ai_service_desk.engine.types import TicketClassification


@pytest.fixture
def data() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticket_id": "0",
                "ticket_number": "0",
                "title": "CIGAM falha",
                "texto_busca": "CIGAM falha ao abrir",
                "catalogo": "Sistemas",
                "area": "Cigam 11",
                "item": "",
                "historico_atendimento": "registro interno",
            },
            {
                "ticket_id": "1",
                "ticket_number": "1",
                "title": "CIGAM erro",
                "texto_busca": "erro CIGAM",
                "catalogo": "Sistemas",
                "area": "Cigam 11",
                "item": "",
                "historico_atendimento": "registro interno",
            },
            {
                "ticket_id": "2",
                "ticket_number": "2",
                "title": "CIGAM trava",
                "texto_busca": "CIGAM trava",
                "catalogo": "Sistemas",
                "area": "Cigam 11",
                "item": "",
                "historico_atendimento": "registro interno",
            },
            {
                "ticket_id": "3",
                "ticket_number": "3",
                "title": "Outlook",
                "texto_busca": "email nao recebe notas",
                "catalogo": "Microsoft Office 365",
                "area": "Outlook",
                "item": "",
                "historico_atendimento": "registro interno",
            },
        ]
    )


@pytest.fixture
def matrix() -> np.ndarray:
    return np.asarray(
        [[0.8, 0.6], [0.6, 0.8], [0.5, 0.8660254], [1, 0]], dtype=np.float32
    )


@pytest.fixture
def query() -> np.ndarray:
    return np.asarray([1, 0], dtype=np.float32)


def classification(system: str = "CIGAM") -> TicketClassification:
    return TicketClassification("ERRO_SISTEMA", system, {}, 0.99)


def test_wrong_system_is_excluded_even_when_highest_score(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    result = retrieve(data, matrix, query, classification(), "CIGAM fecha ao faturar")
    assert [item["ticket_id"] for item in result["candidates"]] == ["0"]
    assert result["status"] == "ENCONTRADOS"


def test_no_evidence_when_scores_are_below_threshold(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    result = retrieve(data, matrix, query, classification(), "CIGAM", threshold=0.9)
    assert result["candidates"] == []
    assert result["status"] == "SEM_EVIDENCIA"


def test_unknown_system_never_maps_to_another(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    result = retrieve(data, matrix, query, classification("XYZ"), "sistema XYZ travou")
    assert result["status"] == "SEM_CONTEXTO"
    assert result["candidates"] == []


def test_sparse_context_still_blocks_other_system(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    sparse = data.iloc[[0, 3]].reset_index(drop=True)
    result = retrieve(sparse, matrix[[0, 3]], query, classification(), "CIGAM trava")
    assert [item["ticket_id"] for item in result["candidates"]] == ["0"]


def test_two_explicit_systems_return_ambiguous(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    result = retrieve(data, matrix, query, classification(), "integracao CIGAM e SIAGRI falhou")
    assert result["status"] == "CONTEXTO_AMBIGUO"
    assert result["candidates"] == []


def test_dimensions_and_parameters_are_validated(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    with pytest.raises(ValueError):
        retrieve(data, matrix, [1, 0, 0], classification(), "CIGAM")
    with pytest.raises(ValueError):
        retrieve(data, matrix, query, classification(), "CIGAM", threshold=float("nan"))
    with pytest.raises(ValueError):
        retrieve(data, matrix, query, classification(), "CIGAM", top_k=0)


def test_history_does_not_affect_ranking(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    first = retrieve(data, matrix, query, classification(), "CIGAM")
    changed = data.copy()
    changed["historico_atendimento"] = "mudanca administrativa"
    second = retrieve(changed, matrix, query, classification(), "CIGAM")
    assert [item["score"] for item in first["candidates"]] == [
        item["score"] for item in second["candidates"]
    ]


def test_formatter_never_claims_verified_solution_or_prints_history_by_default(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    result = retrieve(data, matrix, query, classification(), "CIGAM")
    output = format_result(result)
    assert "HISTORICO_NAO_VALIDADO" in output
    assert "99%" not in output
    assert "registro interno" not in output


def test_sensitive_history_is_not_exposed_as_candidate(
    data: pd.DataFrame, matrix: np.ndarray, query: np.ndarray
) -> None:
    changed = data.copy()
    changed.loc[0, "historico_atendimento"] = "senha: not-a-real-password"
    result = retrieve(changed, matrix, query, classification(), "CIGAM")
    assert result["candidates"] == []


class FakeEmbedder:
    model = "qwen3-embedding:0.6b"
    digest = "digest"
    dimensions = 2

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))


class FakeClient:
    def chat(self, payload: dict) -> dict:
        return {
            "message": {
                "content": '{"intent":"ERRO_SISTEMA","system":"CIGAM","entities":{},"confidence":0.9}'
            }
        }


def test_engine_rejects_embedder_provenance_mismatch(tmp_path: Path, data: pd.DataFrame) -> None:
    from ai_service_desk.engine.index import build_index

    root = tmp_path / "index"
    embedder = FakeEmbedder()
    build_index(data, root, embedder, batch_size=2)
    changed = FakeEmbedder()
    changed.digest = "other"
    with pytest.raises(ValueError):
        RetrievalEngine(root, FakeClient(), changed)


def test_intent_can_restrict_pool_when_it_has_enough_matches() -> None:
    from ai_service_desk.engine.retrieval import select_context_pool

    data = pd.DataFrame(
        [
            {
                "catalogo": "Impressoras",
                "area": "Impressora",
                "item": "Nao imprime",
                "texto_busca": "impressora nao imprime",
            },
            {
                "catalogo": "Impressoras",
                "area": "Impressora",
                "item": "Scanner",
                "texto_busca": "scanner parado",
            },
            {
                "catalogo": "Impressoras",
                "area": "Impressora",
                "item": "Fila",
                "texto_busca": "nao imprime",
            },
            {
                "catalogo": "Sistemas",
                "area": "Cigam",
                "item": "Erro",
                "texto_busca": "cigam falhou",
            },
        ]
    )
    pool = select_context_pool(data, "", "PROBLEMA_IMPRESSAO", min_matches=3)
    assert pool.tolist() == [0, 1, 2]


def test_threshold_filter_orders_descending() -> None:
    from ai_service_desk.engine.retrieval import filter_by_threshold

    scores = np.array([0.51, 0.81, 0.66, 0.64, 0.72], dtype=np.float32)
    indices = filter_by_threshold(scores, np.arange(5), threshold=0.65, top_k=3)
    assert indices.tolist() == [1, 4, 2]
