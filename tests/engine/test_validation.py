import numpy as np
import pytest

from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_matrix, normalize_text


def test_ticket_classification_preserves_contract() -> None:
    classification = TicketClassification("ERRO_SISTEMA", "CIGAM", {"rotina": "001024"}, 0.9)
    assert classification.intent == "ERRO_SISTEMA"
    assert classification.system == "CIGAM"
    assert classification.entities == {"rotina": "001024"}
    assert classification.confidence == 0.9


def test_normalize_text_removes_accents_and_collapses_separators() -> None:
    assert normalize_text("  Conexao CIGAM_11  ") == "conexao cigam 11"


def test_normalize_matrix_returns_float32_unit_vectors() -> None:
    matrix = normalize_matrix([[3.0, 4.0], [0.0, 2.0]])
    assert matrix.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), [1.0, 1.0])


@pytest.mark.parametrize(
    "matrix",
    [
        [1.0, 2.0],
        [[0.0, 0.0]],
        [[np.nan, 1.0]],
        [[np.inf, 1.0]],
    ],
)
def test_normalize_matrix_rejects_invalid_vectors(matrix: object) -> None:
    with pytest.raises(ValueError):
        normalize_matrix(matrix)
