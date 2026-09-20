"""Coleta observável e limitada, sem procedimentos, para o suporte geral."""

import re
from dataclasses import dataclass, replace

from ai_service_desk.engine.validation import normalize_text
from ai_service_desk.web.demo_support import SupportHistoryEntry

_DEVICE = re.compile(
    r"\b(?:pc|computador|notebook|windows|monitor|tela|leitor|impressora|"
    r"teclado|mouse|scanner|celular|aplicativo|programa|sistema)\b"
)
_SYMPTOM = re.compile(
    r"\b(?:trav\w*|lent\w*|erro|falha|parou|nao (?:liga|abre|funciona|le)|"
    r"pisc\w*|apag\w*|problema)\b"
)
_CONTEXT = re.compile(
    r"\b(?:quando|desde|principalmente|somente|apenas|ao (?:abrir|usar)|"
    r"mas|mensagem|ja consigo acessar|erro\s+\w+\s+\w+)\b"
)
_CANNOT_ANSWER = re.compile(
    r"\b(?:nao sei|nao (?:tenho|estou com) certeza|nao consigo (?:dizer|explicar|informar)|"
    r"nao (?:lembro|saberia)|sem certeza|sei la|nenhuma ideia)\b"
)
_WANTS_INSTRUCTIONS = re.compile(
    r"\b(?:so me (?:diz|diga)|o que (?:eu )?(?:tenho que|devo) fazer|"
    r"nao precisa chamar|nao quero (?:suporte|responder))\b"
)
_VAGUE = re.compile(r"(?:sim|nao|isso|ok|aham|continua|igual|ta ruim|entendi)[.!? ]*")

QUESTIONS = {
    "scope": (
        "Isso acontece no computador todo ou principalmente quando você abre algum programa?",
        "A lentidão afeta o computador todo ou aparece principalmente em algum programa?",
    ),
    "behavior": (
        "O que você observa quando o problema acontece?",
        "Como o problema aparece para você durante o uso?",
    ),
    "reader": (
        "Ele ainda acende ou parou completamente?",
        "O leitor ainda dá algum sinal de que está ligado?",
    ),
    "timing": (
        "Em que situação isso costuma acontecer?",
        "Quando você percebe esse problema durante o uso?",
    ),
}


def is_general_it_problem(message: str) -> bool:
    text = normalize_text(message)
    return bool(_DEVICE.search(text) and _SYMPTOM.search(text))


@dataclass(frozen=True)
class GeneralTriage:
    original_symptom: str
    system: str
    intent: str
    history: tuple[SupportHistoryEntry, ...] = ()
    questions: tuple[str, ...] = ()
    handoff_id: str = ""

    def collect(self, message: str, *, sufficient_initial=False):
        """O modelo não controla o orçamento nem a condição terminal."""
        text = normalize_text(message).strip()
        current = replace(self, history=(*self.history, SupportHistoryEntry("USER", message)))
        useful_answer = bool(self.questions and not _VAGUE.fullmatch(text))
        finish = (
            len(self.questions) >= 2
            or bool(_CANNOT_ANSWER.search(text))
            or bool(_WANTS_INSTRUCTIONS.search(text))
            or useful_answer
            or (not self.questions and (sufficient_initial or bool(_CONTEXT.search(text))))
        )
        if finish:
            return current, None
        if self.questions:
            dimension = "timing" if self.questions[0] == "behavior" else "behavior"
        elif re.search(r"\b(?:lent\w*|trav\w*)\b", text):
            dimension = "scope"
        elif "leitor" in text:
            dimension = "reader"
        else:
            dimension = "timing"
        return replace(current, questions=(*self.questions, dimension)), dimension

    def with_response(self, response: str):
        return replace(self, history=(*self.history, SupportHistoryEntry("ASSISTANT", response)))
