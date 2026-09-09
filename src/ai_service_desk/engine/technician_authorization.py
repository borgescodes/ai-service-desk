from dataclasses import dataclass

from ai_service_desk.engine.policy import MACHINE_CODE_RE
from ai_service_desk.engine.request_lifecycle import Phase8DomainError


@dataclass(frozen=True)
class TechnicianIdentity:
    technician_id: str
    username: str
    name: str
    email: str


@dataclass(frozen=True)
class TechnicianRegistryEntry:
    identity: TechnicianIdentity
    capabilities: frozenset[str]


class TechnicianRegistryConfigurationError(Phase8DomainError):
    pass


class TechnicianAuthorizationError(Phase8DomainError):
    pass


def _identity_valid(identity):
    if type(identity) is not TechnicianIdentity:
        return False
    return all(
        isinstance(value, str) and value.strip() and len(value) <= limit
        for value, limit in (
            (identity.technician_id, 120),
            (identity.username, 120),
            (identity.name, 180),
            (identity.email, 320),
        )
    )


def _capability_valid(capability):
    return isinstance(capability, str) and MACHINE_CODE_RE.fullmatch(capability) is not None


class TechnicianAuthorizationRegistry:
    def __init__(self, entries):
        if not isinstance(entries, list | tuple):
            raise TechnicianRegistryConfigurationError(
                "TECHNICIAN_REGISTRY_INVALID", "Entradas invalidas."
            )
        validated = []
        for entry in entries:
            if (
                type(entry) is not TechnicianRegistryEntry
                or not _identity_valid(entry.identity)
                or not isinstance(entry.capabilities, set | frozenset | list | tuple)
                or not all(_capability_valid(capability) for capability in entry.capabilities)
            ):
                raise TechnicianRegistryConfigurationError(
                    "TECHNICIAN_REGISTRY_INVALID", "Entrada invalida."
                )
            validated.append(TechnicianRegistryEntry(entry.identity, frozenset(entry.capabilities)))
        by_id = {}
        usernames = set()
        emails = set()
        for entry in validated:
            identity = entry.identity
            key = identity.technician_id.strip().casefold()
            username = identity.username.strip().casefold()
            email = identity.email.strip().casefold()
            if key in by_id or username in usernames or email in emails:
                raise TechnicianRegistryConfigurationError(
                    "TECHNICIAN_REGISTRY_CONFLICT", "Identidade duplicada."
                )
            by_id[key] = entry
            usernames.add(username)
            emails.add(email)
        self._by_id = by_id

    def require_capability(self, technician: TechnicianIdentity, capability: str) -> None:
        if _identity_valid(technician) and _capability_valid(capability):
            entry = self._by_id.get(technician.technician_id.strip().casefold())
            if (
                entry is not None
                and technician == entry.identity
                and capability in entry.capabilities
            ):
                return
        raise TechnicianAuthorizationError(
            "TECHNICIAN_CAPABILITY_REQUIRED", "Tecnico sem autorizacao exata."
        )
