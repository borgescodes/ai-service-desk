"""Estado conversacional focado para suporte de acesso ao Microsoft 365."""

import re
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from typing import Literal

from ai_service_desk.engine.access_request import SessionIdentity
from ai_service_desk.engine.technician_authorization import TechnicianIdentity
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
_PROCEDURE_FAILURE = re.compile(
    r"\b(?:deu errado|nao rolou|nao resolveu|nao funcionou|continua igual|"
    r"ainda nao consigo (?:entrar|acessar)|continua sem (?:entrar|acessar|acesso))\b"
)
_PROCEDURE_SUCCESS = re.compile(
    r"\b(?:deu certo|funcionou|consegui entrar|agora foi|resolvido|entrou normalmente)\b"
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
    PROCEDURE_SUCCEEDED = "PROCEDURE_SUCCEEDED"
    PROCEDURE_FAILED = "PROCEDURE_FAILED"
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
    resolved: bool | None = None
    resolved_by_guidance: bool | None = None

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
        if self.resolved is not None:
            result["resolved"] = self.resolved
        if self.resolved_by_guidance is not None:
            result["resolved_by_guidance"] = self.resolved_by_guidance
        return result


@dataclass(frozen=True)
class SupportHandoff:
    handoff_id: str
    system: str
    capability: str
    technician: TechnicianIdentity
    requester: SessionIdentity
    technical_summary: str
    source_conversation: SupportConversation
    confidence: dict | None = None

    def as_result(self) -> dict:
        result = {
            "handoff_id": self.handoff_id,
            "system": self.system,
            "capability": self.capability,
            "technician": {
                "technician_id": self.technician.technician_id,
                "username": self.technician.username,
                "name": self.technician.name,
                "email": self.technician.email,
            },
            "requester": {
                "username": self.requester.username,
                "name": self.requester.name,
                "email": self.requester.email,
                "area": self.requester.area,
                "identity_source": "BACKEND_SESSION_PROVIDER",
            },
            "technical_summary": self.technical_summary,
            "source_conversation": [
                {"role": item.role, "text": item.text} for item in self.source_conversation.history
            ],
        }
        if self.confidence is not None:
            result["confidence"] = dict(self.confidence)
        return result


class SupportHandoffStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, SupportHandoff] = {}

    def put(self, handoff: SupportHandoff) -> SupportHandoff:
        if (
            type(handoff) is not SupportHandoff
            or not handoff.handoff_id.strip()
            or not handoff.system.strip()
            or not handoff.capability.strip()
            or type(handoff.technician) is not TechnicianIdentity
            or type(handoff.requester) is not SessionIdentity
            or not handoff.technical_summary.strip()
            or type(handoff.source_conversation) is not SupportConversation
        ):
            raise ValueError("handoff inválido.")
        with self._lock:
            current = self._records.get(handoff.handoff_id)
            if current is None:
                self._records[handoff.handoff_id] = handoff
                return handoff
            if current == handoff:
                return current
            raise ValueError("handoff_id já possui conteúdo incompatível.")

    def get(self, handoff_id: str) -> SupportHandoff:
        with self._lock:
            current = self._records.get(handoff_id)
            if current is None:
                raise KeyError(handoff_id)
            return current

    def snapshot(self) -> tuple[SupportHandoff, ...]:
        with self._lock:
            return tuple(self._records[key] for key in sorted(self._records))


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
        """Processa um turno; o sinal opcional pode vir da interpretação semântica local."""
        if explicit_other_system:
            self.clear(identity_id)
            return None

        current = self.get(identity_id)
        if current.stage in {
            SupportStage.GUIDANCE_DELIVERED,
            SupportStage.RESOLVED,
            SupportStage.HANDOFF,
        }:
            return self._handle_procedure_result(identity_id, current, message, interpreted_signal)

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

    def _handle_procedure_result(
        self,
        identity_id: str,
        current: SupportConversation,
        message: str,
        interpreted_signal: LinguisticSignal | str | None,
    ) -> SupportTurn | None:
        signal = self._procedure_result_signal(message, interpreted_signal)

        if current.stage == SupportStage.RESOLVED:
            if signal == LinguisticSignal.PROCEDURE_SUCCEEDED:
                return SupportTurn(
                    status="SUPPORT_RESOLVED",
                    resolved=True,
                    resolved_by_guidance=True,
                )
            return None

        if current.stage == SupportStage.HANDOFF:
            if signal == LinguisticSignal.PROCEDURE_FAILED:
                return SupportTurn(status="SUPPORT_HANDOFF_PENDING")
            return None

        history = current.history + (SupportHistoryEntry("USER", message.strip()),)
        if signal == LinguisticSignal.PROCEDURE_SUCCEEDED:
            self._sessions[identity_id] = SupportConversation(
                stage=SupportStage.RESOLVED,
                original_symptom=current.original_symptom,
                evidence=current.evidence,
                questions_asked=current.questions_asked,
                procedure=current.procedure,
                history=history,
            )
            return SupportTurn(
                status="SUPPORT_RESOLVED",
                resolved=True,
                resolved_by_guidance=True,
            )

        if signal == LinguisticSignal.PROCEDURE_FAILED:
            self._sessions[identity_id] = SupportConversation(
                stage=SupportStage.HANDOFF,
                original_symptom=current.original_symptom,
                evidence=current.evidence,
                questions_asked=current.questions_asked,
                procedure=current.procedure,
                history=history,
            )
            return SupportTurn(status="SUPPORT_HANDOFF_PENDING")

        if self._is_result_question(message):
            self._sessions[identity_id] = SupportConversation(
                stage=current.stage,
                original_symptom=current.original_symptom,
                evidence=current.evidence,
                questions_asked=current.questions_asked,
                procedure=current.procedure,
                history=history,
            )
            return SupportTurn(status="GUIDANCE_AWAITING_RESULT")

        return None

    @staticmethod
    def _procedure_result_signal(
        message: str, interpreted_signal: LinguisticSignal | str | None
    ) -> LinguisticSignal:
        if interpreted_signal is not None:
            try:
                signal = LinguisticSignal(interpreted_signal)
            except ValueError:
                signal = LinguisticSignal.UNKNOWN
            if signal in {
                LinguisticSignal.PROCEDURE_SUCCEEDED,
                LinguisticSignal.PROCEDURE_FAILED,
            }:
                return signal

        if DemoSupportState._is_result_question(message):
            return LinguisticSignal.UNKNOWN

        normalized = normalize_text(message)
        # Negação vem antes de termos positivos como "funcionou".
        if _PROCEDURE_FAILURE.search(normalized):
            return LinguisticSignal.PROCEDURE_FAILED
        if _PROCEDURE_SUCCESS.search(normalized):
            return LinguisticSignal.PROCEDURE_SUCCEEDED
        return LinguisticSignal.UNKNOWN

    @staticmethod
    def _is_result_question(message: str) -> bool:
        stripped = message.strip()
        if stripped.endswith("?"):
            return True
        normalized = normalize_text(stripped)
        return bool(re.match(r"^(?:e se|vai|sera que)\b", normalized))

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
        # O troubleshooting focado desta demo é de autenticação/senha.
        # Teams genérico continua no fluxo de triagem existente, mesmo quando
        # a mensagem também menciona Office 365.
        if re.search(r"\bteams\b", normalized):
            return LinguisticSignal.UNKNOWN
        if _M365_TERMS.search(normalized) and _LOGIN_PROBLEM.search(normalized):
            return LinguisticSignal.M365_LOGIN_PROBLEM
        return LinguisticSignal.UNKNOWN
