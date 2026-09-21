import hashlib
import json
import re
import unicodedata

import numpy as np

from ai_service_desk.web.general_triage import is_general_it_problem

_CDM_SYSTEM = re.compile(r"\b(?:cdm|central de dados mestres)\b")
_PRIVILEGED_ROLE = re.compile(
    r"\b(?:adm|admin|administrador(?:a)?|administrativ(?:o|a)|superadmin)\b"
)
_OTHER_EXPLICIT_SYSTEM = re.compile(
    r"\b(?:sap|siagri|cigam|metadados|portal rh|office|microsoft 365|m365|"
    r"outlook|teams|onedrive|one drive|ubs)\b"
)
_MATERIAL = re.compile(r"\bmateria(?:l|is)\b")
_REVENDA = re.compile(r"\brevenda\b")
_CDM_REQUEST_LANGUAGE = re.compile(
    r"\b(?:preciso|quero|acesso|acessar|entrar|solicitar|pedir|libera|liberar|perfil|sou)\b"
)
_ACCESS_EVIDENCE = re.compile(
    r"\b(?:acesso|acess(?:ar|a|am)|entr(?:ar|a|am)|senha|permissao|permissoes|"
    r"libera|liberar|perfil)\b"
)


class DemoClassifierClient:
    def chat(self, payload: dict) -> dict:
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("Payload de classificação sem mensagens.")
        last = messages[-1]
        if not isinstance(last, dict) or last.get("role") != "user":
            raise ValueError("Última mensagem deve ser do usuário.")
        text = last.get("content")
        if not isinstance(text, str):
            raise ValueError("Mensagem de classificação inválida.")

        normalized = _normalize(text)
        if _focused_cdm_access(normalized):
            result = {
                "intent": "PROBLEMA_ACESSO",
                "system": "CDM",
                "entities": {},
                "confidence": 0.92,
            }
        elif any(
            term in normalized for term in ("microsoft 365", "office 365", "office365")
        ) and _access_language(normalized):
            result = {
                "intent": "PROBLEMA_ACESSO",
                "system": "OFFICE 365",
                "entities": {},
                "confidence": 0.91,
            }
        elif is_general_it_problem(text):
            result = {
                "intent": "ERRO_SISTEMA",
                "system": "",
                "entities": {},
                "confidence": 0.9,
            }
        else:
            result = {
                "intent": "OUTRO",
                "system": "",
                "entities": {},
                "confidence": 0.35,
            }
        return {"message": {"content": json.dumps(result, ensure_ascii=False)}}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def _access_language(text: str) -> bool:
    return any(
        term in text
        for term in (
            "acesso",
            "acessar",
            "entrar",
            "senha",
            "permissao",
            "permissoes",
            "libera",
            "liberar",
        )
    )


def _focused_cdm_access(text: str) -> bool:
    explicit_cdm = _CDM_SYSTEM.search(text) is not None
    privileged = _PRIVILEGED_ROLE.search(text) is not None
    if explicit_cdm and (_access_language(text) or privileged):
        return True

    if _OTHER_EXPLICIT_SYSTEM.search(text):
        return False

    if privileged and _CDM_REQUEST_LANGUAGE.search(text):
        return True

    return (
        _MATERIAL.search(text) is not None
        and _REVENDA.search(text) is not None
        and _ACCESS_EVIDENCE.search(text) is not None
    )


class DemoEmbedder:
    model = "jup-demo-hash-v1"
    digest = "phase12-demo-embedder-v1"
    dimensions = 32

    def embed(self, texts: list[str]) -> np.ndarray:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise ValueError("DemoEmbedder exige lista de textos.")
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"[a-z0-9]+", _normalize(text)):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimensions
                matrix[row, index] += 1.0
            norm = float(np.linalg.norm(matrix[row]))
            if norm:
                matrix[row] /= norm
        return matrix
