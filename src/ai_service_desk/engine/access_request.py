from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.classification import ALLOWED_INTENTS
from ai_service_desk.engine.playbook import CAPABILITY_RE
from ai_service_desk.engine.triage import TriageState

RequestedRole = Literal["SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN", "UNKNOWN"]
ConcreteRequestedRole = Literal["SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN"]
PreparationStatus = Literal["READY", "NEEDS_CLARIFICATION"]

CDM_SYSTEM = "CDM"
CDM_ACCESS_INTENT = "PROBLEMA_ACESSO"
CDM_ACCESS_CAPABILITY = "CDM_ACCESS_REQUEST"
CONCRETE_ROLES = frozenset({"SOLICITANTE", "APROVADOR", "ADMIN", "SUPERADMIN"})

ROLE_CONFLICT = "ROLE_CONFLICT"
ROLE_PRIVILEGED_INTENT_MATCH = "ROLE_PRIVILEGED_INTENT_MATCH"
ROLE_PRIVILEGED_NOMINAL_MATCH = "ROLE_PRIVILEGED_NOMINAL_MATCH"
ROLE_SOLICITANTE_EXPLICIT = "ROLE_SOLICITANTE_EXPLICIT"
ROLE_PRIVILEGE_AMBIGUOUS = "ROLE_PRIVILEGE_AMBIGUOUS"
ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE = "ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE"
ROLE_UNRESOLVED = "ROLE_UNRESOLVED"
PREPARATION_REASON_CODES = frozenset(
    {
        ROLE_CONFLICT,
        ROLE_PRIVILEGED_INTENT_MATCH,
        ROLE_PRIVILEGED_NOMINAL_MATCH,
        ROLE_SOLICITANTE_EXPLICIT,
        ROLE_PRIVILEGE_AMBIGUOUS,
        ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE,
        ROLE_UNRESOLVED,
    }
)


class AccessRequestValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SessionIdentity:
    username: str
    name: str
    email: str
    area: str


@dataclass(frozen=True)
class AccessRequestContext:
    requester: SessionIdentity
    system: str
    intent: str
    requested_role: ConcreteRequestedRole
    purpose: str
    knowledge_id: str
    playbook_id: str
    playbook_version: int
    step_id: str
    capability: str


@dataclass(frozen=True)
class AccessRequestPreparation:
    status: PreparationStatus
    requested_role: RequestedRole
    reason_code: str
    context: AccessRequestContext | None


def _required_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise AccessRequestValidationError(
            f"{field} deve ser texto nao vazio com ate {limit} caracteres."
        )
    return value


def validate_session_identity(identity: SessionIdentity) -> None:
    if not isinstance(identity, SessionIdentity):
        raise AccessRequestValidationError("requester deve ser SessionIdentity.")
    _required_text(identity.username, "username", 120)
    _required_text(identity.name, "name", 180)
    _required_text(identity.email, "email", 320)
    _required_text(identity.area, "area", 180)


def validate_access_request_context(context: AccessRequestContext) -> None:
    if not isinstance(context, AccessRequestContext):
        raise AccessRequestValidationError("context deve ser AccessRequestContext.")
    validate_session_identity(context.requester)
    _required_text(context.system, "system", 120)
    intent = _required_text(context.intent, "intent", 120)
    if intent not in ALLOWED_INTENTS:
        raise AccessRequestValidationError("intent fora do contrato existente.")
    if context.requested_role not in CONCRETE_ROLES:
        raise AccessRequestValidationError("requested_role fora do contrato concreto.")
    _required_text(context.purpose, "purpose", 3000)
    _required_text(context.knowledge_id, "knowledge_id", 120)
    _required_text(context.playbook_id, "playbook_id", 120)
    if (
        isinstance(context.playbook_version, bool)
        or not isinstance(context.playbook_version, int)
        or context.playbook_version <= 0
    ):
        raise AccessRequestValidationError("playbook_version deve ser inteiro positivo.")
    _required_text(context.step_id, "step_id", 120)
    capability = _required_text(context.capability, "capability", 120)
    if not CAPABILITY_RE.fullmatch(capability):
        raise AccessRequestValidationError("capability deve ser simbolica valida.")
