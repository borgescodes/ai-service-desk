import hmac
import json
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from ai_service_desk.engine.cdm_scope import LOCAL_CDM_SCOPE_CATALOG
from ai_service_desk.integrations.cdm import validate_service_token


@dataclass(frozen=True)
class StoredAccess:
    access_id: str
    request_id: str
    username: str
    email: str
    role: str
    status: str
    business_scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoreCreateResult:
    outcome: Literal["CREATED", "REPLAYED", "ALREADY_EXISTS"]
    access: StoredAccess


class CDMStoreConflict(RuntimeError):
    pass


class CDMFakeStore:
    def __init__(self, scope_catalog=LOCAL_CDM_SCOPE_CATALOG):
        self.scope_catalog = scope_catalog
        self._lock = Lock()
        self._next_access_id = 100001
        self._access_by_email: dict[str, StoredAccess] = {}
        self._request_by_id: dict[str, StoredAccess] = {}

    @property
    def access_count(self) -> int:
        with self._lock:
            return len(self._access_by_email)

    def get_access(self, email: str) -> StoredAccess | None:
        key = email.strip().lower()
        with self._lock:
            return self._access_by_email.get(key)

    def create_access(
        self,
        *,
        request_id: str,
        username: str,
        email: str,
        role: str,
        business_scopes: tuple[str, ...] = (),
    ) -> StoreCreateResult:
        normalized_email = email.strip().lower()
        with self._lock:
            by_request = self._request_by_id.get(request_id)
            if by_request is not None:
                if (
                    by_request.username == username
                    and by_request.email == normalized_email
                    and by_request.role == role
                    and by_request.business_scopes == business_scopes
                ):
                    return StoreCreateResult("REPLAYED", by_request)
                raise CDMStoreConflict("request_id reutilizado com payload diferente.")

            by_email = self._access_by_email.get(normalized_email)
            if by_email is not None:
                return StoreCreateResult("ALREADY_EXISTS", by_email)

            access = StoredAccess(
                access_id=str(self._next_access_id),
                request_id=request_id,
                username=username,
                email=normalized_email,
                role=role,
                status="ACTIVE",
                business_scopes=business_scopes,
            )
            self._next_access_id += 1
            self._access_by_email[normalized_email] = access
            self._request_by_id[request_id] = access
            return StoreCreateResult("CREATED", access)


EXPECTED_FIELDS = {"request_id", "username", "email", "role"}
REQUEST_ID_RE = re.compile(r"^REQ-[0-9]{6}$")


def _error_body(code: str, message: str) -> dict[str, object]:
    return {"success": False, "error_code": code, "message": message}


def _build_handler(service_token: str, store: CDMFakeStore, fail_request_ids: frozenset[str]):
    class CDMRequestHandler(BaseHTTPRequestHandler):
        server_version = "CDMFake/1.0"
        sys_version = ""

        def log_message(self, format: str, *args: object) -> None:
            return

        def _json(self, status: int, body: dict[str, object]) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _route_not_found(self) -> None:
            self._json(404, _error_body("CDM_ROUTE_NOT_FOUND", "Rota nao encontrada."))

        def _discard_request_body(self) -> None:
            try:
                remaining = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path != "/api/v1/access":
                self._route_not_found()
                return
            params = parse_qs(parsed.query, keep_blank_values=True)
            if (
                set(params) != {"email"}
                or len(params["email"]) != 1
                or not params["email"][0].strip()
            ):
                self._json(400, _error_body("CDM_REQUEST_INVALID", "email invalido."))
                return
            email = params["email"][0].strip().lower()
            access = store.get_access(email)
            if access is None:
                self._json(200, {"exists": False, "email": email})
                return
            self._json(
                200,
                {
                    "exists": True,
                    "email": access.email,
                    "role": access.role,
                    "status": access.status,
                    "access_id": access.access_id,
                    **(
                        {"business_scopes": list(access.business_scopes)}
                        if access.business_scopes
                        else {}
                    ),
                },
            )

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path != "/api/v1/access" or parsed.query:
                self._route_not_found()
                return

            expected = f"Bearer {service_token}"
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, expected):
                # Unread POST bytes can abort the connection before Windows receives the 401.
                self._discard_request_body()
                self._json(
                    401,
                    _error_body("CDM_SERVICE_UNAUTHORIZED", "Credencial de servico invalida."),
                )
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                body = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, _error_body("CDM_REQUEST_INVALID", "JSON invalido."))
                return

            if type(body) is not dict or set(body) not in (
                EXPECTED_FIELDS,
                EXPECTED_FIELDS | {"business_scopes"},
            ):
                self._json(400, _error_body("CDM_REQUEST_INVALID", "Schema invalido."))
                return

            request_id = body.get("request_id")
            username = body.get("username")
            email = body.get("email")
            role = body.get("role")
            scopes = body.get("business_scopes", [])
            if (
                not isinstance(request_id, str)
                or REQUEST_ID_RE.fullmatch(request_id) is None
                or not isinstance(username, str)
                or not username.strip()
                or not isinstance(email, str)
                or not email.strip()
                or role != "SOLICITANTE"
                or not isinstance(scopes, list)
                or len(scopes) != len(set(str(scope) for scope in scopes))
                or any(
                    not isinstance(scope, str)
                    or scope not in {s.key for s in store.scope_catalog.scopes}
                    for scope in scopes
                )
            ):
                self._json(400, _error_body("CDM_REQUEST_INVALID", "Campos invalidos."))
                return

            if request_id in fail_request_ids:
                self._json(500, _error_body("CDM_INTERNAL_ERROR", "Falha interna controlada."))
                return

            try:
                result = store.create_access(
                    request_id=request_id,
                    username=username,
                    email=email,
                    role=role,
                    business_scopes=tuple(scopes),
                )
            except CDMStoreConflict:
                self._json(
                    409,
                    _error_body("CDM_IDEMPOTENCY_CONFLICT", "Conflito de idempotencia."),
                )
                return

            if result.outcome == "ALREADY_EXISTS":
                self._json(
                    409,
                    {
                        "success": False,
                        "error_code": "CDM_ACCESS_ALREADY_EXISTS",
                        "access_id": result.access.access_id,
                        "status": result.access.status,
                    },
                )
                return

            status = 201 if result.outcome == "CREATED" else 200
            self._json(
                status,
                {
                    "success": True,
                    "outcome": result.outcome,
                    "access_id": result.access.access_id,
                    "status": result.access.status,
                },
            )

    return CDMRequestHandler


def build_cdm_server(
    host: str,
    port: int,
    service_token: str,
    *,
    store: CDMFakeStore | None = None,
    fail_request_ids: set[str] | frozenset[str] | None = None,
) -> ThreadingHTTPServer:
    token = validate_service_token(service_token)
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host deve ser texto nao vazio.")
    if type(port) is not int or not (0 <= port <= 65535):
        raise ValueError("port invalida.")
    actual_store = store if store is not None else CDMFakeStore()
    failures = frozenset(fail_request_ids or ())
    server = ThreadingHTTPServer((host, port), _build_handler(token, actual_store, failures))
    server.store = actual_store
    return server


def serve_cdm_api(host: str, port: int, service_token: str) -> None:
    server = build_cdm_server(host, port, service_token)
    try:
        server.serve_forever()
    finally:
        server.server_close()
