from dataclasses import dataclass
from typing import Literal

from ai_service_desk.engine.access_request import SessionIdentity
from ai_service_desk.engine.technician_authorization import TechnicianIdentity


class IdentityNotFoundError(ValueError):
    code = "IDENTITY_NOT_FOUND"


@dataclass(frozen=True)
class DemoIdentity:
    identity_id: str
    name: str
    username: str
    email: str
    area: str
    role: Literal["REQUESTER", "TECHNICIAN"]
    technician_id: str | None = None
    capabilities: frozenset[str] = frozenset()


_IDENTITIES = (
    DemoIdentity(
        identity_id="pedro-miranda",
        name="Pedro Miranda",
        username="pedro.miranda",
        email="pedro.miranda@example.invalid",
        area="Revenda - Matriz",
        role="REQUESTER",
    ),
    DemoIdentity(
        identity_id="tecnico-cdm",
        name="Técnico CDM",
        username="tecnico.cdm",
        email="tecnico.cdm@example.invalid",
        area="Tecnologia da Informação",
        role="TECHNICIAN",
        technician_id="TECH-CDM",
        capabilities=frozenset({"CDM_ACCESS_REQUEST"}),
    ),
    DemoIdentity(
        identity_id="tecnico-geral",
        name="Técnico Geral",
        username="tecnico.geral",
        email="tecnico.geral@example.invalid",
        area="Tecnologia da Informação",
        role="TECHNICIAN",
        technician_id="TECH-GENERAL",
        capabilities=frozenset(),
    ),
)


class DemoIdentityProvider:
    def __init__(self) -> None:
        self._identities = {identity.identity_id: identity for identity in _IDENTITIES}

    def resolve(self, identity_id: str) -> DemoIdentity:
        identity = self._identities.get(identity_id)
        if identity is None:
            raise IdentityNotFoundError("Identidade de demonstração não reconhecida.")
        return identity

    def public_identities(self) -> list[dict]:
        return [
            {
                "identity_id": identity.identity_id,
                "name": identity.name,
                "area": identity.area,
                "role": identity.role,
                "can_operate": identity.role == "TECHNICIAN",
            }
            for identity in _IDENTITIES
        ]

    def requester_identity(self, identity_id: str) -> SessionIdentity:
        identity = self.resolve(identity_id)
        if identity.role != "REQUESTER":
            raise IdentityNotFoundError("Identidade não possui perfil de solicitante.")
        return SessionIdentity(
            username=identity.username,
            name=identity.name,
            email=identity.email,
            area=identity.area,
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
