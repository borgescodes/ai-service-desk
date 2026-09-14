import hashlib
import json
import re
import unicodedata

import numpy as np

from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_text

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
        and _CDM_REQUEST_LANGUAGE.search(text) is not None
    )


COMPACT_SCENARIOS = ["CDM_ACCESS", "M365_SUPPORT", "OTHER_IT", "UNKNOWN"]
COMPACT_SIGNALS = [
    "ACCESS_REQUEST",
    "PRIVILEGED_ACCESS",
    "LOGIN_PROBLEM",
    "PASSWORD_EVIDENCE",
    "SUCCESS",
    "FAILURE",
    "UNKNOWN",
]

_COMPACT_SYSTEM_PROMPT = "\n".join(
    (
        "Jup: classifique suporte de TI. Só interprete; backend decide e executa.",
        "scenario: CDM_ACCESS=acesso/permissão no CDM/Central de Dados Mestres; "
        "M365_SUPPORT=login/senha no Microsoft 365/Office/Outlook; "
        "OTHER_IT=outro TI; UNKNOWN=incerto. "
        "Cadastro de material sem pedido de acesso não é CDM_ACCESS.",
        "signal: ACCESS_REQUEST=acesso normal; PRIVILEGED_ACCESS=adm/admin/administrativo/"
        "administrador/superadmin; LOGIN_PROBLEM=falha de acesso; PASSWORD_EVIDENCE=senha; "
        "SUCCESS=funcionou/deu certo; FAILURE=não resolveu/deu errado/não rolou; UNKNOWN=demais.",
        "BUSINESS_CONTEXT_CURRENT vem do backend; não amplie sistemas nem invente identidade, "
        "autorização, policy, aprovação, IDs, routing ou resultado. Só JSON do schema.",
    )
)


def build_compact_interpretation_payload(text: str) -> dict:
    if not isinstance(text, str) or not text.strip() or len(text) > 3000:
        raise ValueError("Mensagem inválida para interpretação LOCAL_AI.")
    return {
        "model": "qwen3.5:4b",
        "think": False,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 1024, "num_predict": 32},
        "messages": [
            {"role": "system", "content": _COMPACT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "format": {
            "type": "object",
            "properties": {
                "scenario": {"type": "string", "enum": COMPACT_SCENARIOS},
                "signal": {"type": "string", "enum": COMPACT_SIGNALS},
            },
            "required": ["scenario", "signal"],
            "additionalProperties": False,
        },
    }


def parse_compact_interpretation_response(payload: dict) -> tuple[str, str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
        raise ValueError("Resposta LOCAL_AI sem message válida.")
    if payload.get("done_reason") == "length":
        raise ValueError("Resposta LOCAL_AI truncada.")
    content = payload["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Resposta LOCAL_AI sem conteúdo.")
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Resposta LOCAL_AI não contém JSON válido.") from exc
    if not isinstance(data, dict) or set(data) != {"scenario", "signal"}:
        raise ValueError("Resposta LOCAL_AI fora do contrato compacto.")
    scenario = data["scenario"]
    signal = data["signal"]
    if scenario not in COMPACT_SCENARIOS or signal not in COMPACT_SIGNALS:
        raise ValueError("Resposta LOCAL_AI usa enum inválido.")
    return scenario, signal


def _compact_intent(text: str, scenario: str, signal: str, has_system: bool) -> str:
    normalized = normalize_text(text)
    textual_access = _ACCESS_EVIDENCE.search(normalized) is not None
    privileged_access = (
        signal == "PRIVILEGED_ACCESS" and _PRIVILEGED_ROLE.search(normalized) is not None
    )
    if (
        signal
        in {
            "ACCESS_REQUEST",
            "LOGIN_PROBLEM",
            "PASSWORD_EVIDENCE",
        }
        and textual_access
    ):
        return "PROBLEMA_ACESSO"
    if privileged_access:
        return "PROBLEMA_ACESSO"
    if textual_access:
        return "PROBLEMA_ACESSO"
    if re.search(r"\b(?:instalar|instalacao)\b", normalized):
        return "INSTALACAO_SOFTWARE"
    if re.search(r"\b(?:erro|travando|travou|nao abre|nao sincroniza)\b", normalized):
        return "ERRO_SISTEMA"
    if has_system:
        return "ORIENTACAO"
    return "OUTRO"


def compact_interpretation_to_classification(
    text: str,
    scenario: str,
    signal: str,
    resolver,
) -> TicketClassification:
    systems = tuple(resolver.systems(text))
    system = systems[0] if len(systems) == 1 else ""
    # O cenário do modelo não cria sistema sozinho. O resolver curado precisa sustentar o valor.
    intent = _compact_intent(text, scenario, signal, bool(system))
    entities = dict(resolver.entities(text))
    return TicketClassification(intent, system, entities, 0.95)


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
