import re
from dataclasses import dataclass
from threading import RLock
from typing import Literal

from ai_service_desk.engine.access_request import SessionIdentity
from ai_service_desk.engine.technician_authorization import TechnicianIdentity


class IdentityNotFoundError(ValueError):
    code = "IDENTITY_NOT_FOUND"


class IdentityConfigurationError(ValueError):
    code = "INVALID_DEMO_IDENTITY"


@dataclass(frozen=True)
class DemoIdentity:
    identity_id: str
    name: str
    username: str
    email: str
    area: str
    job_title: str
    role: Literal["REQUESTER", "TECHNICIAN"]
    technician_id: str | None = None
    capabilities: frozenset[str] = frozenset()


_IDENTITIES = (
    DemoIdentity(
        identity_id="pedro-miranda",
        name="Fulano de Tal",
        username="fulano.tal",
        email="fulano.tal@juparana.com.br",
        area="Revenda - Matriz",
        job_title="Colaborador",
        role="REQUESTER",
    ),
    DemoIdentity(
        identity_id="tecnico-cdm",
        name="Técnico CDM",
        username="tecnico.cdm",
        email="tecnico.cdm@example.invalid",
        area="Tecnologia da Informação",
        job_title="Especialista CDM",
        role="TECHNICIAN",
        technician_id="TECH-CDM",
        capabilities=frozenset({"CDM_ACCESS_REQUEST"}),
    ),
    DemoIdentity(
        identity_id="tecnico-m365",
        name="Técnico Microsoft 365",
        username="tecnico.m365",
        email="tecnico.m365@example.invalid",
        area="Tecnologia da Informação",
        job_title="Especialista Microsoft 365",
        role="TECHNICIAN",
        technician_id="TECH-M365",
        capabilities=frozenset({"MICROSOFT_365_SUPPORT_REQUEST"}),
    ),
    DemoIdentity(
        identity_id="tecnico-geral",
        name="Técnico Geral",
        username="tecnico.geral",
        email="tecnico.geral@example.invalid",
        area="Tecnologia da Informação",
        job_title="Técnico de Suporte",
        role="TECHNICIAN",
        technician_id="TECH-GENERAL",
        capabilities=frozenset({"GENERAL_IT_SUPPORT"}),
    ),
)


class DemoIdentityProvider:
    def __init__(self) -> None:
        self._identities = {identity.identity_id: identity for identity in _IDENTITIES}
        self._next_requester_id = 1
        self._lock = RLock()

    @staticmethod
    def _required(value: object, field: str, limit: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise IdentityConfigurationError(
                f"{field} deve ser texto não vazio com até {limit} caracteres."
            )
        return value.strip()

    @staticmethod
    def public_identity(identity: DemoIdentity) -> dict:
        payload = {
            "identity_id": identity.identity_id,
            "name": identity.name,
            "area": identity.area,
            "role": identity.role,
            "can_operate": identity.role == "TECHNICIAN",
        }
        if identity.role == "REQUESTER":
            payload.update(email=identity.email, job_title=identity.job_title)
        return payload

    def configure_requester(
        self,
        *,
        name: str,
        email: str,
        job_title: str,
        area: str,
    ) -> DemoIdentity:
        clean_name = self._required(name, "name", 180)
        clean_email = self._required(email, "email", 320).lower()
        clean_job_title = self._required(job_title, "job_title", 180)
        clean_area = self._required(area, "area", 180)
        if not re.fullmatch(
            r"[a-z0-9]+(?:[._%+-][a-z0-9]+)*@juparana\.com\.br",
            clean_email,
        ):
            raise IdentityConfigurationError(
                "email deve ser um endereço corporativo @juparana.com.br válido."
            )

        with self._lock:
            identity_id = f"demo-requester-{self._next_requester_id}"
            self._next_requester_id += 1
            identity = DemoIdentity(
                identity_id=identity_id,
                name=clean_name,
                username=clean_email.partition("@")[0],
                email=clean_email,
                area=clean_area,
                job_title=clean_job_title,
                role="REQUESTER",
            )
            self._identities[identity_id] = identity
        return identity

    def resolve(self, identity_id: str) -> DemoIdentity:
        with self._lock:
            identity = self._identities.get(identity_id)
        if identity is None:
            raise IdentityNotFoundError("Identidade de demonstração não reconhecida.")
        return identity

    def public_identities(self) -> list[dict]:
        with self._lock:
            return [self.public_identity(identity) for identity in self._identities.values()]

    def requester_identity(self, identity_id: str) -> SessionIdentity:
        identity = self.resolve(identity_id)
        if identity.role != "REQUESTER":
            raise IdentityNotFoundError("Identidade não possui perfil de solicitante.")
        return SessionIdentity(
            username=identity.username,
            name=identity.name,
            email=identity.email,
            area=identity.area,
            job_title=identity.job_title,
        )

    def technician_identity(self, identity_id: str) -> TechnicianIdentity:
        identity = self.resolve(identity_id)
        if identity.role != "TECHNICIAN" or identity.technician_id is None:
            raise IdentityNotFoundError("Identidade não possui perfil técnico.")
        return TechnicianIdentity(
            technician_id=identity.technician_id,
            username=identity.username,
            name=identity.name,
            email=identity.email,
        )

    def technician_capabilities(self, identity_id: str) -> frozenset[str]:
        identity = self.resolve(identity_id)
        if identity.role != "TECHNICIAN":
            raise IdentityNotFoundError("Identidade não possui perfil técnico.")
        return identity.capabilities
