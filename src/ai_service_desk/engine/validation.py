import re
import unicodedata

import numpy as np


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_matrix(matrix: object) -> np.ndarray:
    value = np.asarray(matrix, dtype=np.float32)
    if value.ndim != 2 or value.shape[0] == 0 or value.shape[1] == 0:
        raise ValueError("Matrix must have rows and columns.")
    if not np.isfinite(value).all():
        raise ValueError("Embedding contains non-finite values.")
    norms = np.linalg.norm(value, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms <= 0):
        raise ValueError("Embedding contains a zero norm vector.")
    return value / norms
