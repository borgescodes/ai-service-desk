from dataclasses import dataclass
from typing import Literal

import requests

from ai_service_desk.engine.cdm_scope import LOCAL_CDM_SCOPE_CATALOG


@dataclass(frozen=True)
class AccessLookup:
    exists: bool
    email: str
    role: str | None
    status: str | None
    access_id: str | None
    business_scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AccessCreationResult:
    outcome: Literal["CREATED", "REPLAYED", "ALREADY_EXISTS"]
    access_id: str
    status: str


class CDMAdapterError(RuntimeError):
    reason_code = "CDM_ADAPTER_ERROR"


class CDMRequestValidationError(CDMAdapterError):
    reason_code = "CDM_REQUEST_INVALID"


class CDMServiceAuthenticationError(CDMAdapterError):
    reason_code = "CDM_SERVICE_UNAUTHORIZED"


class CDMIdempotencyConflictError(CDMAdapterError):
    reason_code = "CDM_IDEMPOTENCY_CONFLICT"


class CDMUnavailableError(CDMAdapterError):
    reason_code = "CDM_UNAVAILABLE"


class CDMProtocolError(CDMAdapterError):
    reason_code = "CDM_PROTOCOL_ERROR"


class CDMRemoteInternalError(CDMAdapterError):
    reason_code = "CDM_INTERNAL_ERROR"


def validate_service_token(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("CDM_API_TOKEN deve ser texto nao vazio.")
    return value


def _json_object(response: requests.Response) -> dict[str, object]:
    try:
        body = response.json()
    except ValueError as exc:
        raise CDMProtocolError("Resposta CDM nao contem JSON valido.") from exc
    if type(body) is not dict:
        raise CDMProtocolError("Resposta CDM deve ser objeto JSON.")
    return body


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CDMProtocolError("Resposta CDM contem texto invalido.")
    return value


class CDMAdapter:
    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        timeout_seconds: float = 3.0,
        session: requests.Session | None = None,
        scope_catalog=LOCAL_CDM_SCOPE_CATALOG,
    ):
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url deve ser texto nao vazio.")
        if type(timeout_seconds) not in {int, float} or isinstance(timeout_seconds, bool):
            raise ValueError("timeout_seconds invalido.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser positivo.")
        self.scope_catalog = scope_catalog
        self.base_url = base_url.rstrip("/")
        self.service_token = validate_service_token(service_token)
        self.timeout_seconds = float(timeout_seconds)
        self.session = session if session is not None else requests.Session()

    def get_access(self, email: str) -> AccessLookup:
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/access",
                params={"email": email},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CDMUnavailableError("CDM indisponivel.") from exc
        if response.status_code == 400:
            raise CDMRequestValidationError("Consulta CDM rejeitada.")
        if 500 <= response.status_code <= 599:
            raise CDMRemoteInternalError("CDM retornou falha interna.")
        if response.status_code != 200:
            raise CDMProtocolError("Status inesperado na consulta CDM.")
        body = _json_object(response)
        allowed_shapes = (
            {"exists", "email"},
            {"exists", "email", "role", "status", "access_id"},
            {"exists", "email", "role", "status", "access_id", "business_scopes"},
        )
        if set(body) not in allowed_shapes:
            raise CDMProtocolError("Schema inesperado na consulta CDM.")
        exists = body.get("exists")
        email_value = _text(body.get("email"))
        if type(exists) is not bool:
            raise CDMProtocolError("exists deve ser bool exato.")
        if not exists:
            if set(body) != {"exists", "email"}:
                raise CDMProtocolError("Consulta sem acesso contem campos extras.")
            return AccessLookup(False, email_value, None, None, None)
        role = _text(body.get("role"))
        status = _text(body.get("status"))
        access_id = _text(body.get("access_id"))
        if role != "SOLICITANTE" or status != "ACTIVE":
            raise CDMProtocolError("Acesso CDM retornou role ou status fora do contrato.")
        scopes = body.get("business_scopes", [])
        if not isinstance(scopes, list) or any(
            not isinstance(scope, str) or scope not in {s.key for s in self.scope_catalog.scopes}
            for scope in scopes
        ):
            raise CDMProtocolError("Escopos CDM inválidos.")
        return AccessLookup(True, email_value, role, status, access_id, tuple(scopes))

    def create_access(
        self,
        request_id: str,
        username: str,
        email: str,
        role: str,
        *,
        business_scopes: tuple[str, ...] = (),
    ) -> AccessCreationResult:
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/access",
                json={
                    "request_id": request_id,
                    "username": username,
                    "email": email,
                    "role": role,
                    **({"business_scopes": list(business_scopes)} if business_scopes else {}),
                },
                headers={"Authorization": f"Bearer {self.service_token}"},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise CDMUnavailableError("CDM indisponivel.") from exc

        if response.status_code == 400:
            raise CDMRequestValidationError("Criacao CDM rejeitada.")
        if response.status_code == 401:
            raise CDMServiceAuthenticationError("Credencial de servico rejeitada pelo CDM.")
        if 500 <= response.status_code <= 599:
            raise CDMRemoteInternalError("CDM retornou falha interna.")

        body = _json_object(response)
        if response.status_code in {200, 201}:
            expected_outcome = "CREATED" if response.status_code == 201 else "REPLAYED"
            if (
                set(body) != {"success", "outcome", "access_id", "status"}
                or body.get("success") is not True
                or body.get("outcome") != expected_outcome
            ):
                raise CDMProtocolError("Resposta de criacao CDM fora do contrato.")
            access_id = _text(body.get("access_id"))
            status = _text(body.get("status"))
            if status != "ACTIVE":
                raise CDMProtocolError("Status de acesso CDM fora do contrato.")
            return AccessCreationResult(expected_outcome, access_id, status)

        if response.status_code == 409:
            code = body.get("error_code")
            if code == "CDM_ACCESS_ALREADY_EXISTS":
                if (
                    set(body) != {"success", "error_code", "access_id", "status"}
                    or body.get("success") is not False
                ):
                    raise CDMProtocolError("Resposta de acesso existente fora do contrato.")
                access_id = _text(body.get("access_id"))
                status = _text(body.get("status"))
                if status != "ACTIVE":
                    raise CDMProtocolError("Status de acesso existente fora do contrato.")
                return AccessCreationResult("ALREADY_EXISTS", access_id, status)
            if code == "CDM_IDEMPOTENCY_CONFLICT":
                raise CDMIdempotencyConflictError("Conflito de idempotencia no CDM.")
            raise CDMProtocolError("Conflito CDM desconhecido.")

        raise CDMProtocolError("Status inesperado na criacao CDM.")
