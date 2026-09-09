from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ai_service_desk.engine.request_lifecycle import (
    ConcurrencyConflictError,
    InvalidStateTransitionError,
    RequestNotFoundError,
)
from ai_service_desk.web.demo_identity import IdentityNotFoundError
from ai_service_desk.web.demo_runtime import DEFAULT_DEMO_MODE, DemoRuntime
from ai_service_desk.web.errors import WebDemoError

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
_CSP = (
    "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
    "style-src 'self'; script-src 'self'"
)


class MessageBody(BaseModel):
    message: str = Field(min_length=1, max_length=3000)


class DecisionBody(BaseModel):
    expected_version: int = Field(gt=0)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _default_static_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "web" / "dist"


def _resolve_static_dir(static_dir: str | Path | None) -> Path | None:
    if static_dir is None:
        return None
    root = Path(static_dir).resolve()
    if not root.is_dir() or not (root / "index.html").is_file():
        raise RuntimeError(
            "Build web ausente. Execute `cd web && npm run build` antes de iniciar a demo."
        )
    return root


def create_app(
    runtime: DemoRuntime | None = None,
    *,
    runtime_mode: str = DEFAULT_DEMO_MODE,
    demo_mode: bool = True,
    static_dir: str | Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Jup Resolve", docs_url=None, redoc_url=None)
    app.state.runtime = runtime if runtime is not None else DemoRuntime.create(mode=runtime_mode)
    app.state.owns_runtime = runtime is None
    app.state.demo_mode = demo_mode
    app.state.static_dir = _resolve_static_dir(static_dir)

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = _CSP
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(IdentityNotFoundError)
    async def identity_not_found_handler(_request: Request, exc: IdentityNotFoundError):
        return _error(401, exc.code, "Identidade de demonstração não reconhecida.")

    @app.exception_handler(WebDemoError)
    async def web_demo_error_handler(_request: Request, exc: WebDemoError):
        if exc.code == "IDENTITY_REQUIRED":
            status = 401
        elif exc.code == "PREVENTION_NOT_FOUND":
            status = 404
        elif exc.code == "ROUTING_INCONSISTENT":
            status = 409
        else:
            status = 403
        return _error(status, exc.code, str(exc))

    @app.exception_handler(RequestNotFoundError)
    async def request_not_found_handler(_request: Request, exc: RequestNotFoundError):
        return _error(404, exc.reason_code, "Solicitação não encontrada.")

    @app.exception_handler(ConcurrencyConflictError)
    async def version_conflict_handler(_request: Request, exc: ConcurrencyConflictError):
        return _error(
            409,
            exc.reason_code,
            "A solicitação foi alterada. Recarregue e tente novamente.",
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def transition_error_handler(_request: Request, exc: InvalidStateTransitionError):
        return _error(
            409,
            exc.reason_code,
            "A solicitação não aceita esta operação no estado atual.",
        )

    @app.exception_handler(Exception)
    async def safe_internal_error_handler(_request: Request, _exc: Exception):
        return _error(500, "INTERNAL_ERROR", "Não foi possível concluir a operação.")

    def identity(x_demo_identity: str | None) -> str:
        if x_demo_identity is None or not x_demo_identity.strip():
            raise WebDemoError("IDENTITY_REQUIRED", "Selecione uma identidade de demonstração.")
        value = x_demo_identity.strip()
        app.state.runtime.identity_provider.resolve(value)
        return value

    def require_loopback(request: Request) -> None:
        client = request.client
        host = client.host if client is not None else ""
        if host not in _LOOPBACK_HOSTS:
            raise WebDemoError(
                "LOOPBACK_REQUIRED",
                "Reset da demonstração exige acesso local.",
            )

    @app.get("/api/health")
    def health():
        return {"ok": True, "product": "Jup Resolve", "demo": bool(app.state.demo_mode)}

    @app.get("/api/session/identities")
    def identities():
        return app.state.runtime.identity_provider.public_identities()

    @app.post("/api/jup/messages")
    def send_message(body: MessageBody, x_demo_identity: str | None = Header(default=None)):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.send_message(identity_id, body.message)

    @app.get("/api/requests")
    def list_requests(x_demo_identity: str | None = Header(default=None)):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.list_requests(identity_id)

    @app.get("/api/requests/{request_id}")
    def request_detail(request_id: str, x_demo_identity: str | None = Header(default=None)):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.get_request(identity_id, request_id)

    @app.get("/api/operations/approvals")
    def approvals(x_demo_identity: str | None = Header(default=None)):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.list_approvals(identity_id)

    @app.get("/api/operations/approvals/{request_id}")
    def operational_detail(request_id: str, x_demo_identity: str | None = Header(default=None)):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.get_operational_request(identity_id, request_id)

    @app.get("/api/operations/prevention")
    def prevention(x_demo_identity: str | None = Header(default=None)):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.list_prevention(identity_id)

    @app.get("/api/operations/prevention/{opportunity_id}")
    def prevention_detail(
        opportunity_id: str,
        x_demo_identity: str | None = Header(default=None),
    ):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.get_prevention(identity_id, opportunity_id)

    @app.post("/api/requests/{request_id}/approve")
    def approve(
        request_id: str,
        body: DecisionBody,
        x_demo_identity: str | None = Header(default=None),
    ):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.approve_request(
            identity_id,
            request_id,
            expected_version=body.expected_version,
        )

    @app.post("/api/requests/{request_id}/reject")
    def reject(
        request_id: str,
        body: DecisionBody,
        x_demo_identity: str | None = Header(default=None),
    ):
        identity_id = identity(x_demo_identity)
        return app.state.runtime.reject_request(
            identity_id,
            request_id,
            expected_version=body.expected_version,
        )

    if demo_mode:

        @app.post("/api/demo/reset")
        def reset_demo(request: Request):
            require_loopback(request)
            app.state.runtime.reset()
            return {"ok": True}

    if app.state.static_dir is not None:
        static_root: Path = app.state.static_dir
        index_file = static_root / "index.html"

        @app.get("/{path:path}")
        def serve_web(path: str):
            if path == "api" or path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            requested = (static_root / path).resolve() if path else index_file
            try:
                requested.relative_to(static_root)
            except ValueError:
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            if requested.is_file():
                return FileResponse(requested)
            return FileResponse(index_file, media_type="text/html")

    @app.on_event("shutdown")
    def shutdown_runtime() -> None:
        if app.state.owns_runtime:
            app.state.runtime.close()

    return app


def run_web_demo(*, host: str, port: int, mode: str = DEFAULT_DEMO_MODE) -> None:
    uvicorn.run(
        create_app(runtime_mode=mode, static_dir=_default_static_dir()),
        host=host,
        port=port,
        log_level="info",
    )
