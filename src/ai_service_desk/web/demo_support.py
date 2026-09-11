"""Estado conversacional focado para suporte de acesso ao Microsoft 365."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from ai_service_desk.engine.validation import normalize_text

MAX_DIAGNOSTIC_QUESTIONS = 3

_QUESTIONS = (
    "A mensagem menciona senha ou mostra outro erro?",
    "Você também tentou entrar pelo navegador?",
    "Você lembra da senha atual ou acredita que pode ter esquecido?",
)
_M365_TERMS = re.compile(r"\b(?:office|office 365|microsoft 365|m365|outlook|e mail|email)\b")
_LOGIN_PROBLEM = re.compile(
    r"\b(?:nao (?:entra|consigo (?:entrar|acessar))|sem acesso|acesso bloqueado)\b"
)
_PASSWORD_EVIDENCE = re.compile(
    r"\b(?:senha(?: esta)? errada|senha incorreta|esqueci (?:a|minha) senha|"
    r"nao lembro (?:a|minha) senha|trocar (?:a|minha) senha|redefinir (?:a|minha) senha)\b"
)


class SupportStage(StrEnum):
    IDLE = "IDLE"
    DIAGNOSING = "DIAGNOSING"
    GUIDANCE_DELIVERED = "GUIDANCE_DELIVERED"
    RESOLVED = "RESOLVED"
    HANDOFF = "HANDOFF"


class LinguisticSignal(StrEnum):
    M365_LOGIN_PROBLEM = "M365_LOGIN_PROBLEM"
    PASSWORD_EVIDENCE = "PASSWORD_EVIDENCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SupportProcedure:
    knowledge_id: str
    answer: str
    url: str


@dataclass(frozen=True)
class SupportHistoryEntry:
    role: Literal["USER", "ASSISTANT"]
    text: str


@dataclass(frozen=True)
class SupportConversation:
    stage: SupportStage = SupportStage.IDLE
    original_symptom: str = ""
    evidence: tuple[str, ...] = ()
    questions_asked: tuple[str, ...] = ()
    procedure: SupportProcedure | None = None
    history: tuple[SupportHistoryEntry, ...] = ()


@dataclass(frozen=True)
class SupportTurn:
    status: str
    question: str | None = None
    knowledge_id: str | None = None
    answer: str | None = None
    procedure_url: str | None = None

    def as_result(self) -> dict:
        result = {"status": self.status, "request_id": None}
        if self.question is not None:
            result["question"] = self.question
        if self.knowledge_id is not None:
            result["knowledge_id"] = self.knowledge_id
        if self.answer is not None:
            result["answer"] = self.answer
        if self.procedure_url is not None:
            result["procedure_url"] = self.procedure_url
        return result


class DemoSupportState:
    """Mantém diagnóstico M365 por identidade dentro de um runtime."""

    def __init__(self) -> None:
        self._sessions: dict[str, SupportConversation] = {}

    def get(self, identity_id: str) -> SupportConversation:
        return self._sessions.get(identity_id, SupportConversation())

    def clear(self, identity_id: str) -> None:
        self._sessions.pop(identity_id, None)

    def handle(
        self,
        identity_id: str,
        message: str,
        *,
        interpreted_signal: LinguisticSignal | str | None = None,
        explicit_other_system: bool = False,
    ) -> SupportTurn | None:
        """Processa um turno; o sinal opcional será fornecido pela interpretação da Task 8."""
        if explicit_other_system:
            self.clear(identity_id)
            return None

        current = self.get(identity_id)
        signal = self._signal(message, interpreted_signal)
        starts_dialogue = signal in {
            LinguisticSignal.M365_LOGIN_PROBLEM,
            LinguisticSignal.PASSWORD_EVIDENCE,
        }
        if current.stage == SupportStage.IDLE and not starts_dialogue:
            return None
        if current.stage not in {SupportStage.IDLE, SupportStage.DIAGNOSING}:
            return None

        original = current.original_symptom or message.strip()
        history = current.history + (SupportHistoryEntry("USER", message.strip()),)
        evidence = current.evidence
        if current.stage == SupportStage.DIAGNOSING and message.strip() not in evidence:
            evidence += (message.strip(),)
        if signal == LinguisticSignal.PASSWORD_EVIDENCE:
            if message.strip() not in evidence:
                evidence += (message.strip(),)
            self._sessions[identity_id] = SupportConversation(
                stage=SupportStage.DIAGNOSING,
                original_symptom=original,
                evidence=evidence,
                questions_asked=current.questions_asked,
                history=history,
            )
            return SupportTurn(status="PASSWORD_EVIDENCE_COLLECTED")

        if len(current.questions_asked) >= MAX_DIAGNOSTIC_QUESTIONS:
            self._sessions[identity_id] = SupportConversation(
                stage=SupportStage.HANDOFF,
                original_symptom=original,
                evidence=evidence,
                questions_asked=current.questions_asked,
                history=history,
            )
            return SupportTurn(status="TRIAGE_ABSTAINED")

        question = _QUESTIONS[len(current.questions_asked)]
        questions = current.questions_asked + (question,)
        self._sessions[identity_id] = SupportConversation(
            stage=SupportStage.DIAGNOSING,
            original_symptom=original,
            evidence=evidence,
            questions_asked=questions,
            history=history + (SupportHistoryEntry("ASSISTANT", question),),
        )
        return SupportTurn(status="NEEDS_CLARIFICATION", question=question)

    def record_guidance(self, identity_id: str, procedure: SupportProcedure) -> None:
        current = self.get(identity_id)
        self._sessions[identity_id] = SupportConversation(
            stage=SupportStage.GUIDANCE_DELIVERED,
            original_symptom=current.original_symptom,
            evidence=current.evidence,
            questions_asked=current.questions_asked,
            procedure=procedure,
            history=current.history + (SupportHistoryEntry("ASSISTANT", procedure.answer),),
        )

    @staticmethod
    def _signal(
        message: str, interpreted_signal: LinguisticSignal | str | None
    ) -> LinguisticSignal:
        if interpreted_signal is not None:
            try:
                return LinguisticSignal(interpreted_signal)
            except ValueError:
                return LinguisticSignal.UNKNOWN
        normalized = normalize_text(message)
        if _PASSWORD_EVIDENCE.search(normalized):
            return LinguisticSignal.PASSWORD_EVIDENCE
        if _M365_TERMS.search(normalized) and _LOGIN_PROBLEM.search(normalized):
            return LinguisticSignal.M365_LOGIN_PROBLEM
        return LinguisticSignal.UNKNOWN
