# Phase 9 CDM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar o `ExecutionEngine` homologado da Fase 8 a uma API local simulada do CDM, com service credential, consulta, criação `SOLICITANTE`, idempotência, erros tipados e smoke HTTP ponta a ponta.

**Architecture:** O núcleo da Fase 8 permanece byte-idêntico. A Fase 9 cria uma camada `integrations` com `CDMAdapter` e API fake HTTP em memória, mais um `CDMActionExecutor` novo que implementa o `ActionExecutor` existente. O adapter usa `requests`; o servidor fake usa apenas biblioteca padrão do Python 3.14.

**Tech Stack:** Python 3.14, `requests>=2.32,<3`, `http.server.ThreadingHTTPServer`, dataclasses, threading, pytest, Ruff 0.12.12.

**Spec:** `docs/superpowers/specs/2026-09-09-phase-9-cdm-integration-design.md`

## Global Constraints

- Baseline integrada: `fd48e294617ea4d4cff91effeec507abbf44e4d5`.
- Spec commit: `f97ed64095e5c1356769c7b9b400635e6068a241`.
- Baseline histórico da Fase 9: exatamente `701` pytest node IDs.
- A implementação inicia no head da branch `phase-9-cdm-integration` depois do commit deste plano. Não resetar para a spec commit nem para a `main` durante a execução.
- Python oficial: `3.14.x`.
- Ruff homologado: `0.12.12`.
- Apenas `SOLICITANTE` pode ser criado no CDM.
- `APROVADOR`, `ADMIN` e `SUPERADMIN` nunca podem ser criados pela API fake nem pelo executor.
- `CDM_API_TOKEN` vem do ambiente e nunca entra em Git, fixture, log, report, contexto, record ou audit.
- `GET /api/v1/access` não exige bearer nesta fase; `POST /api/v1/access` exige bearer.
- Idempotência é por `request_id`.
- Não existe retry automático de GET ou POST.
- Não existe persistência do simulador.
- Não adicionar framework web.
- Não adicionar banco, SQLite, JSON state file, fila, routing, frontend, OAuth, SSO ou API real.
- `ExecutionEngine` e o lifecycle da Fase 8 não são alterados para integrar o CDM.
- Exceção inesperada do executor continua sendo responsabilidade do `ExecutionEngine`, resultando no comportamento homologado `EXECUTOR_EXCEPTION`.
- Todos os 701 node IDs históricos devem permanecer coletáveis, com zero ausentes.

### Protected Phase 8 blobs

```text
src/ai_service_desk/engine/access_request.py = f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d
src/ai_service_desk/engine/policy.py = 60a4f3ae785353009c30b37f71e1ce91865b899e
src/ai_service_desk/engine/confidence.py = ffc0c212b455978f79a3591578f323ca0e9612dc
src/ai_service_desk/engine/request_lifecycle.py = dfd194ff8a364a0eb0d803409dad252ced216279
src/ai_service_desk/engine/request_repository.py = 5ccda3d30484729faa1a568cf64e20bfe55e595f
src/ai_service_desk/engine/technician_authorization.py = ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4
src/ai_service_desk/engine/approval.py = ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8
src/ai_service_desk/engine/execution.py = 908ceade729daa3e18b7b604549f635b33d4688f
src/ai_service_desk/engine/controlled_execution_smoke.py = e26766fdc35ff450d69a40a2516d193b7a90cb75
```

---

## File Structure

### Create

```text
src/ai_service_desk/integrations/__init__.py
src/ai_service_desk/integrations/cdm.py
src/ai_service_desk/integrations/cdm_fake_api.py
src/ai_service_desk/engine/cdm_execution.py
src/ai_service_desk/engine/cdm_integration_smoke.py
tests/integrations/test_cdm_contracts.py
tests/integrations/test_cdm_fake_store.py
tests/integrations/test_cdm_fake_api.py
tests/integrations/test_cdm_adapter.py
tests/engine/test_cdm_execution.py
tests/engine/test_cdm_integration_smoke.py
tests/fixtures/phase9_cdm_integration_cases.jsonl
.github/workflows/phase9-cdm-integration.yml
```

### Modify

```text
src/ai_service_desk/cli.py
tests/test_workflows.py
```

No other production file should be modified unless a failing test demonstrates a real blocker and the change is reviewed against the protected list.

---

### Task 1: Freeze Phase 9 baseline and add CDM contracts

**Files:**
- Create: `src/ai_service_desk/integrations/__init__.py`
- Create: `src/ai_service_desk/integrations/cdm.py`
- Create: `tests/integrations/test_cdm_contracts.py`

**Interfaces:**
- Produces: `AccessLookup`, `AccessCreationResult`, `CDMAdapterError` hierarchy, `validate_service_token`.
- Consumes: no Phase 9 component.

- [ ] **Step 1: Record baseline evidence before code**

Run:

```bash
git rev-parse HEAD
git status --short
python --version
python -m ruff --version
PYTHONPATH=src python -m pytest --collect-only -q > phase9-baseline-nodeids.txt
```

Expected:

```text
Python 3.14.x
ruff 0.12.12
701 collected tests
working tree clean
```

Store the baseline node ID file outside Git or in an ignored evidence directory.

- [ ] **Step 2: Verify protected blobs before code**

Run each:

```bash
git rev-parse HEAD:src/ai_service_desk/engine/access_request.py
git rev-parse HEAD:src/ai_service_desk/engine/policy.py
git rev-parse HEAD:src/ai_service_desk/engine/confidence.py
git rev-parse HEAD:src/ai_service_desk/engine/request_lifecycle.py
git rev-parse HEAD:src/ai_service_desk/engine/request_repository.py
git rev-parse HEAD:src/ai_service_desk/engine/technician_authorization.py
git rev-parse HEAD:src/ai_service_desk/engine/approval.py
git rev-parse HEAD:src/ai_service_desk/engine/execution.py
git rev-parse HEAD:src/ai_service_desk/engine/controlled_execution_smoke.py
```

Expected the exact SHAs from Global Constraints.

- [ ] **Step 3: Write failing contract tests**

Create tests that require exact frozen dataclasses and error codes:

```python
from dataclasses import FrozenInstanceError

import pytest

from ai_service_desk.integrations.cdm import (
    AccessCreationResult,
    AccessLookup,
    CDMAdapterError,
    CDMIdempotencyConflictError,
    CDMProtocolError,
    CDMRemoteInternalError,
    CDMRequestValidationError,
    CDMServiceAuthenticationError,
    CDMUnavailableError,
    validate_service_token,
)


def test_access_lookup_is_frozen():
    value = AccessLookup(False, "user@example.invalid", None, None, None)
    with pytest.raises(FrozenInstanceError):
        value.exists = True


def test_access_creation_result_is_frozen():
    value = AccessCreationResult("CREATED", "100001", "ACTIVE")
    with pytest.raises(FrozenInstanceError):
        value.status = "OTHER"


@pytest.mark.parametrize("value", [None, "", "   ", 123, True])
def test_service_token_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        validate_service_token(value)


def test_adapter_errors_expose_machine_reason_code():
    errors = [
        CDMRequestValidationError("bad"),
        CDMServiceAuthenticationError("bad"),
        CDMIdempotencyConflictError("bad"),
        CDMUnavailableError("bad"),
        CDMProtocolError("bad"),
        CDMRemoteInternalError("bad"),
    ]
    assert all(isinstance(error, CDMAdapterError) for error in errors)
    assert [error.reason_code for error in errors] == [
        "CDM_REQUEST_INVALID",
        "CDM_SERVICE_UNAUTHORIZED",
        "CDM_IDEMPOTENCY_CONFLICT",
        "CDM_UNAVAILABLE",
        "CDM_PROTOCOL_ERROR",
        "CDM_INTERNAL_ERROR",
    ]
```

- [ ] **Step 4: Run contract tests and verify RED**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_contracts.py -q
```

Expected: import/module failures because Phase 9 contracts do not exist yet.

- [ ] **Step 5: Implement minimal contracts**

Create `src/ai_service_desk/integrations/__init__.py` empty except package docstring.

Create in `cdm.py`:

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AccessLookup:
    exists: bool
    email: str
    role: str | None
    status: str | None
    access_id: str | None


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
```

Constructors for typed errors must never include the service token in the message.

- [ ] **Step 6: Run contract tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_contracts.py -q
```

Expected: PASS.

- [ ] **Step 7: Run relevant regression**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_phase8_security.py tests/engine/test_execution.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/ai_service_desk/integrations tests/integrations/test_cdm_contracts.py
git commit -m "feat: add CDM integration contracts"
```

---

### Task 2: Implement the in-memory CDM store and idempotency

**Files:**
- Create: `src/ai_service_desk/integrations/cdm_fake_api.py`
- Create: `tests/integrations/test_cdm_fake_store.py`

**Interfaces:**
- Produces: `StoredAccess`, `CDMFakeStore`, `CDMStoreConflict`.
- Consumes: service token validation from Task 1 only at server layer, not store layer.

- [ ] **Step 1: Write failing store tests**

Tests must cover:

```python
def test_first_create_allocates_single_access_id(): ...
def test_same_request_and_payload_replays_same_access(): ...
def test_same_request_with_different_payload_conflicts(): ...
def test_different_request_same_email_reports_existing_access(): ...
def test_two_threads_same_request_create_once(): ...
def test_two_threads_same_email_create_at_most_once(): ...
```

Use payloads exactly shaped as:

```python
PAYLOAD = {
    "request_id": "REQ-000001",
    "username": "synthetic.requester",
    "email": "synthetic.requester@example.invalid",
    "role": "SOLICITANTE",
}
```

Assert deterministic IDs:

```text
100001
100002
...
```

- [ ] **Step 2: Run store tests RED**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_fake_store.py -q
```

Expected: missing store classes.

- [ ] **Step 3: Implement immutable stored access and locked store**

Required shape:

```python
@dataclass(frozen=True)
class StoredAccess:
    access_id: str
    request_id: str
    username: str
    email: str
    role: str
    status: str


class CDMFakeStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._next_access_id = 100001
        self._access_by_email: dict[str, StoredAccess] = {}
        self._request_by_id: dict[str, StoredAccess] = {}

    def get_access(self, email: str) -> StoredAccess | None:
        key = email.strip().lower()
        with self._lock:
            return self._access_by_email.get(key)
```

Creation must run under the same lock from checking request ID and email through allocation and writes.

Return an explicit store outcome:

```text
CREATED
REPLAYED
ALREADY_EXISTS
```

Raise a dedicated conflict only for same `request_id` with different payload.

- [ ] **Step 4: Run store tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_fake_store.py -q
```

Expected: PASS including concurrency tests.

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/integrations/cdm_fake_api.py tests/integrations/test_cdm_fake_store.py
git commit -m "feat: add idempotent CDM fake store"
```

---

### Task 3: Implement the local HTTP CDM API

**Files:**
- Modify: `src/ai_service_desk/integrations/cdm_fake_api.py`
- Create: `tests/integrations/test_cdm_fake_api.py`

**Interfaces:**
- Produces: `build_cdm_server(host, port, service_token, *, store=None, fail_request_ids=None)` and `serve_cdm_api(...)`.
- Consumes: `CDMFakeStore`, `validate_service_token`.

- [ ] **Step 1: Write a reusable HTTP server test fixture**

Use `ThreadingHTTPServer` on port `0` and a daemon thread:

```python
@pytest.fixture
def cdm_server():
    server = build_cdm_server("127.0.0.1", 0, "test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield server, f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
```

- [ ] **Step 2: Write failing GET tests**

Cover:

```python
def test_get_missing_access_returns_exists_false(cdm_server): ...
def test_get_existing_access_returns_contract(cdm_server): ...
def test_get_requires_single_nonempty_email(cdm_server): ...
def test_unknown_route_returns_closed_404(cdm_server): ...
```

- [ ] **Step 3: Write failing POST tests**

Cover exact behavior:

```python
def test_post_requires_bearer(cdm_server): ...
def test_post_rejects_wrong_bearer(cdm_server): ...
def test_post_creates_solicitante(cdm_server): ...
def test_post_rejects_privileged_role(cdm_server): ...
def test_post_rejects_extra_fields(cdm_server): ...
def test_post_replay_returns_200_same_access_id(cdm_server): ...
def test_post_idempotency_conflict_returns_409(cdm_server): ...
def test_post_existing_access_returns_409_with_access_id(cdm_server): ...
def test_controlled_internal_error_hides_traceback_and_token(): ...
```

- [ ] **Step 4: Run HTTP tests RED**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_fake_api.py -q
```

- [ ] **Step 5: Implement handler factory and JSON responses**

Required route logic:

```text
GET  /api/v1/access?email=<email>
POST /api/v1/access
all other routes -> 404 CDM_ROUTE_NOT_FOUND
```

Use a helper that always emits:

```python
payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
self.send_response(status)
self.send_header("Content-Type", "application/json; charset=utf-8")
self.send_header("Content-Length", str(len(payload)))
self.end_headers()
self.wfile.write(payload)
```

Validate bearer with `hmac.compare_digest` and never echo the supplied token.

- [ ] **Step 6: Implement exact POST schema validation**

Rules:

```python
EXPECTED_FIELDS = {"request_id", "username", "email", "role"}
REQUEST_ID_RE = re.compile(r"^REQ-[0-9]{6}$")
```

Reject if:

```text
body is not dict
set(body) != EXPECTED_FIELDS
request_id does not match
username empty
email empty
role != SOLICITANTE
```

- [ ] **Step 7: Run HTTP tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_fake_api.py -q
```

- [ ] **Step 8: Run focused integration tests**

```bash
PYTHONPATH=src python -m pytest tests/integrations -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/ai_service_desk/integrations/cdm_fake_api.py tests/integrations/test_cdm_fake_api.py
git commit -m "feat: add local CDM HTTP simulator"
```

---

### Task 4: Implement `CDMAdapter`

**Files:**
- Modify: `src/ai_service_desk/integrations/cdm.py`
- Create: `tests/integrations/test_cdm_adapter.py`

**Interfaces:**
- Produces: `CDMAdapter.get_access(email)` and `CDMAdapter.create_access(...)`.
- Consumes: API contract from Task 3.

- [ ] **Step 1: Write failing happy-path adapter tests against the live fake API**

Create tests for:

```python
def test_get_access_returns_typed_lookup(): ...
def test_create_access_returns_created(): ...
def test_create_access_returns_replayed(): ...
def test_create_access_maps_existing_access_to_result(): ...
```

Assert no Authorization header is required for GET, and bearer is required for POST.

- [ ] **Step 2: Write failing error mapping tests**

Cover:

```python
def test_create_maps_400_to_validation_error(): ...
def test_create_maps_401_to_auth_error(): ...
def test_create_maps_idempotency_409_to_conflict_error(): ...
def test_500_maps_remote_internal_error(): ...
def test_connection_failure_maps_unavailable(): ...
def test_invalid_json_maps_protocol_error(): ...
def test_invalid_schema_maps_protocol_error(): ...
def test_unexpected_status_maps_protocol_error(): ...
def test_each_method_calls_session_request_once_only(): ...
```

For protocol tests, inject a small fake `requests.Session` object rather than modifying the server contract.

- [ ] **Step 3: Run adapter tests RED**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_adapter.py -q
```

- [ ] **Step 4: Implement constructor and URL normalization**

Required constructor:

```python
class CDMAdapter:
    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        timeout_seconds: float = 3.0,
        session: requests.Session | None = None,
    ):
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url deve ser texto nao vazio.")
        if type(timeout_seconds) not in {int, float} or isinstance(timeout_seconds, bool):
            raise ValueError("timeout_seconds invalido.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser positivo.")
        self.base_url = base_url.rstrip("/")
        self.service_token = validate_service_token(service_token)
        self.timeout_seconds = float(timeout_seconds)
        self.session = session if session is not None else requests.Session()
```

- [ ] **Step 5: Implement `get_access`**

Request exactly once:

```python
response = self.session.get(
    f"{self.base_url}/api/v1/access",
    params={"email": email},
    timeout=self.timeout_seconds,
)
```

Do not send bearer in GET.

Validate typed fields before constructing `AccessLookup`.

- [ ] **Step 6: Implement `create_access`**

Request exactly once:

```python
response = self.session.post(
    f"{self.base_url}/api/v1/access",
    json={
        "request_id": request_id,
        "username": username,
        "email": email,
        "role": role,
    },
    headers={"Authorization": f"Bearer {self.service_token}"},
    timeout=self.timeout_seconds,
)
```

Map statuses exactly as the spec. Never retry.

- [ ] **Step 7: Run adapter tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/integrations/test_cdm_adapter.py -q
```

- [ ] **Step 8: Run all integration tests**

```bash
PYTHONPATH=src python -m pytest tests/integrations -q
```

- [ ] **Step 9: Commit**

```bash
git add src/ai_service_desk/integrations/cdm.py tests/integrations/test_cdm_adapter.py
git commit -m "feat: add CDM HTTP adapter"
```

---

### Task 5: Bridge the CDM into the existing `ExecutionEngine`

**Files:**
- Create: `src/ai_service_desk/engine/cdm_execution.py`
- Create: `tests/engine/test_cdm_execution.py`

**Interfaces:**
- Produces: `CDMActionExecutor.execute(request)` returning existing `ActionExecutionResult`.
- Consumes: `AccessLookup`, `AccessCreationResult`, typed adapter errors, Phase 8 `AccessRequestRecord` and `ActionExecutionResult`.

- [ ] **Step 1: Write failing executor defense tests**

Use `tests.engine.phase8_helpers.make_record`.

Required tests:

```python
def test_requires_executing_state(): ...
def test_wrong_system_returns_context_invalid_without_adapter_call(): ...
def test_wrong_intent_returns_context_invalid_without_adapter_call(): ...
def test_wrong_capability_returns_context_invalid_without_adapter_call(): ...
def test_privileged_role_returns_context_invalid_without_adapter_call(): ...
```

Use an adapter spy with call counters.

- [ ] **Step 2: Write failing happy-path tests**

```python
def test_existing_active_solicitante_returns_success(): ...
def test_missing_access_creates_and_returns_created(): ...
def test_create_replayed_returns_success(): ...
def test_create_already_exists_returns_success(): ...
def test_existing_incompatible_access_returns_failure_without_post(): ...
```

Expected result codes:

```text
CDM_ACCESS_ALREADY_EXISTS
CDM_ACCESS_CREATED
CDM_REQUEST_REPLAYED
CDM_EXISTING_ACCESS_CONFLICT
```

- [ ] **Step 3: Write failing adapter error mapping tests**

Parametrize typed errors and expected result code:

```python
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (CDMRequestValidationError("x"), "CDM_REQUEST_INVALID"),
        (CDMServiceAuthenticationError("x"), "CDM_SERVICE_UNAUTHORIZED"),
        (CDMIdempotencyConflictError("x"), "CDM_IDEMPOTENCY_CONFLICT"),
        (CDMUnavailableError("x"), "CDM_UNAVAILABLE"),
        (CDMProtocolError("x"), "CDM_PROTOCOL_ERROR"),
        (CDMRemoteInternalError("x"), "CDM_INTERNAL_ERROR"),
    ],
)
def test_known_adapter_error_returns_failure(error, code): ...
```

Also test that an unexpected `RuntimeError` propagates from `CDMActionExecutor`.

- [ ] **Step 4: Run executor tests RED**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_cdm_execution.py -q
```

- [ ] **Step 5: Implement `CDMActionExecutor`**

Core flow:

```python
class CDMActionExecutor:
    def __init__(self, adapter):
        self.adapter = adapter

    def execute(self, request: AccessRequestRecord) -> ActionExecutionResult:
        if request.state != "EXECUTING":
            raise ValueError("Executor CDM exige request EXECUTING.")
        context = request.context
        if (
            context.system != CDM_SYSTEM
            or context.intent != CDM_ACCESS_INTENT
            or context.capability != CDM_ACCESS_CAPABILITY
            or context.requested_role != "SOLICITANTE"
        ):
            return ActionExecutionResult(False, "CDM_EXECUTION_CONTEXT_INVALID")

        try:
            lookup = self.adapter.get_access(context.requester.email)
            if lookup.exists:
                if lookup.role == "SOLICITANTE" and lookup.status == "ACTIVE":
                    return ActionExecutionResult(True, "CDM_ACCESS_ALREADY_EXISTS")
                return ActionExecutionResult(False, "CDM_EXISTING_ACCESS_CONFLICT")

            created = self.adapter.create_access(
                request.request_id,
                context.requester.username,
                context.requester.email,
                context.requested_role,
            )
        except CDMAdapterError as exc:
            return ActionExecutionResult(False, exc.reason_code)

        result_codes = {
            "CREATED": "CDM_ACCESS_CREATED",
            "REPLAYED": "CDM_REQUEST_REPLAYED",
            "ALREADY_EXISTS": "CDM_ACCESS_ALREADY_EXISTS",
        }
        return ActionExecutionResult(True, result_codes[created.outcome])
```

Do not catch generic `Exception` here.

- [ ] **Step 6: Run executor tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_cdm_execution.py -q
```

- [ ] **Step 7: Verify the unchanged Phase 8 engine handles unexpected executor exception**

Add one integration test constructing a real `ExecutionEngine` with a `CDMActionExecutor` whose adapter raises `RuntimeError`. Assert final record:

```text
state = FAILED
execution_error_code = EXECUTOR_EXCEPTION
```

Run:

```bash
PYTHONPATH=src python -m pytest tests/engine/test_cdm_execution.py -q
```

- [ ] **Step 8: Commit**

```bash
git add src/ai_service_desk/engine/cdm_execution.py tests/engine/test_cdm_execution.py
git commit -m "feat: connect CDM adapter to execution engine"
```

---

### Task 6: Build the six-case Phase 9 end-to-end smoke

**Files:**
- Create: `src/ai_service_desk/engine/cdm_integration_smoke.py`
- Create: `tests/engine/test_cdm_integration_smoke.py`
- Create: `tests/fixtures/phase9_cdm_integration_cases.jsonl`

**Interfaces:**
- Produces: `run_cdm_integration_smoke(cases_path, report_path, service_token)`.
- Consumes: real Fase 8 lifecycle/approval/execution plus fake HTTP API, `CDMAdapter`, `CDMActionExecutor`.

- [ ] **Step 1: Create the exact six-case fixture**

One JSON object per line with stable case IDs:

```jsonl
{"case_id":"CREATE_NEW_ACCESS","expected":"CDM_ACCESS_CREATED"}
{"case_id":"ACCESS_ALREADY_EXISTS","expected":"CDM_ACCESS_ALREADY_EXISTS"}
{"case_id":"IDEMPOTENT_REPLAY","expected":"REPLAYED"}
{"case_id":"IDEMPOTENCY_CONFLICT","expected":"CDM_IDEMPOTENCY_CONFLICT"}
{"case_id":"SERVICE_UNAUTHORIZED","expected":"CDM_SERVICE_UNAUTHORIZED"}
{"case_id":"REMOTE_INTERNAL_ERROR","expected":"CDM_INTERNAL_ERROR"}
```

Do not put token or corporate data in the fixture.

- [ ] **Step 2: Write failing smoke test**

```python
def test_phase9_smoke_runs_six_cases(tmp_path):
    report = run_cdm_integration_smoke(
        Path("tests/fixtures/phase9_cdm_integration_cases.jsonl"),
        tmp_path / "phase9.json",
        "synthetic-test-token",
    )
    assert report["ok"] is True
    assert report["case_count"] == 6
    assert len(report["cases"]) == 6
    assert "synthetic-test-token" not in json.dumps(report)
```

- [ ] **Step 3: Run smoke test RED**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_cdm_integration_smoke.py -q
```

- [ ] **Step 4: Implement server lifecycle with `try/finally`**

The smoke must:

```python
server = build_cdm_server("127.0.0.1", 0, service_token, ...)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    ... run six cases ...
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
```

- [ ] **Step 5: Use real Phase 8 lifecycle for execution cases**

For cases that exercise the engine:

```text
InMemoryRequestRepository
RequestLifecycleService
TechnicianAuthorizationRegistry
ApprovalService
ExecutionEngine
CDMActionExecutor
CDMAdapter
```

Create a synthetic `SessionIdentity` and `AccessRequestContext` with:

```text
system = CDM
intent = PROBLEMA_ACESSO
requested_role = SOLICITANTE
capability = CDM_ACCESS_REQUEST
```

Approve with an authorized technician different from requester.

- [ ] **Step 6: Verify report is aggregate and secret-free**

Allowed report fields:

```text
ok
case_count
cases[].case_id
cases[].ok
cases[].expected
cases[].actual
```

Do not store bearer headers, raw request bodies, service token or traceback.

- [ ] **Step 7: Run smoke tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_cdm_integration_smoke.py -q
```

- [ ] **Step 8: Commit**

```bash
git add src/ai_service_desk/engine/cdm_integration_smoke.py tests/engine/test_cdm_integration_smoke.py tests/fixtures/phase9_cdm_integration_cases.jsonl
git commit -m "test: add phase 9 CDM integration smoke"
```

---

### Task 7: Expose local API and smoke through the CLI

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Create: `tests/test_cdm_cli.py`

**Interfaces:**
- Produces commands `cdm-api` and `cdm-integration-smoke`.
- Consumes: `serve_cdm_api`, `run_cdm_integration_smoke`, `validate_service_token`.

- [ ] **Step 1: Write failing parser tests**

Assert parser accepts:

```text
cdm-api --host 127.0.0.1 --port 8765
cdm-integration-smoke --cases <path> --report <path>
```

Defaults:

```text
host 127.0.0.1
port 8765
```

- [ ] **Step 2: Write failing token tests**

Use monkeypatch on `os.environ`:

```python
def test_cdm_smoke_cli_requires_token(monkeypatch, capsys): ...
def test_cdm_api_cli_requires_token(monkeypatch, capsys): ...
```

No output may contain the token when present.

- [ ] **Step 3: Write failing smoke command output test**

Expected stdout on success:

```text
CDM INTEGRATION SMOKE OK
Casos sinteticos: 6
Relatorio agregado local: <path>
```

- [ ] **Step 4: Run CLI tests RED**

```bash
PYTHONPATH=src python -m pytest tests/test_cdm_cli.py -q
```

- [ ] **Step 5: Modify parser**

Add:

```python
cdm_api = sub.add_parser("cdm-api")
cdm_api.add_argument("--host", default="127.0.0.1")
cdm_api.add_argument("--port", type=int, default=8765)

cdm_smoke = sub.add_parser("cdm-integration-smoke")
cdm_smoke.add_argument("--cases", type=Path, required=True)
cdm_smoke.add_argument("--report", type=Path, required=True)
```

- [ ] **Step 6: Add command handlers**

Read token only from environment:

```python
token = validate_service_token(os.environ.get("CDM_API_TOKEN"))
```

For server:

```python
serve_cdm_api(args.host, args.port, token)
return 0
```

For smoke:

```python
report = run_cdm_integration_smoke(args.cases, args.report, token)
print("CDM INTEGRATION SMOKE OK" if report["ok"] else "CDM INTEGRATION SMOKE REQUER REVISAO")
print(f"Casos sinteticos: {report['case_count']}")
print("Relatorio agregado local: " + str(args.report))
return 0 if report["ok"] else 1
```

- [ ] **Step 7: Run CLI tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/test_cdm_cli.py -q
```

- [ ] **Step 8: Run official smoke command**

POSIX:

```bash
export CDM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
PYTHONPATH=src python -m ai_service_desk cdm-integration-smoke \
  --cases tests/fixtures/phase9_cdm_integration_cases.jsonl \
  --report /tmp/phase9-cdm-smoke.json
```

PowerShell:

```powershell
$env:CDM_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
python -m ai_service_desk cdm-integration-smoke `
  --cases tests/fixtures/phase9_cdm_integration_cases.jsonl `
  --report "$env:TEMP\phase9-cdm-smoke.json"
```

Expected:

```text
CDM INTEGRATION SMOKE OK
Casos sinteticos: 6
```

- [ ] **Step 9: Commit**

```bash
git add src/ai_service_desk/cli.py tests/test_cdm_cli.py
git commit -m "feat: expose CDM simulator commands"
```

---

### Task 8: Add Phase 9 security and regression invariants

**Files:**
- Create: `tests/engine/test_phase9_security.py`

**Interfaces:**
- Produces hard regression checks for protected blobs, HTTP boundary and secret handling.

- [ ] **Step 1: Write exact blob tests**

Mirror Phase 8's Git blob technique for all protected files from Global Constraints.

- [ ] **Step 2: Write HTTP boundary AST tests**

Assert `requests`, `urllib`, `http.client`, `socket` calls do not appear in:

```text
access_request.py
policy.py
confidence.py
request_lifecycle.py
request_repository.py
technician_authorization.py
approval.py
execution.py
cdm_execution.py
```

Allow HTTP implementation only under:

```text
integrations/cdm.py
integrations/cdm_fake_api.py
```

`cdm_execution.py` may import adapter contracts but not `requests`.

- [ ] **Step 3: Write token leakage tests**

Search versioned runtime/fixture content for obvious literal assignments to `CDM_API_TOKEN` and assert smoke report never contains a supplied synthetic token.

Do not flag the environment variable name itself. Flag literal bearer secrets and fixture values.

- [ ] **Step 4: Write role safety tests**

Assert direct POST of each role:

```text
APROVADOR
ADMIN
SUPERADMIN
```

returns 400 and creates no access.

- [ ] **Step 5: Run Phase 9 security tests**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_phase9_security.py -q
```

Expected: PASS.

- [ ] **Step 6: Run Phase 8 security regression**

```bash
PYTHONPATH=src python -m pytest tests/engine/test_phase8_security.py -q
```

Expected: PASS unchanged.

- [ ] **Step 7: Commit**

```bash
git add tests/engine/test_phase9_security.py
git commit -m "test: lock phase 9 integration boundaries"
```

---

### Task 9: Add hosted Phase 9 smoke workflow

**Files:**
- Create: `.github/workflows/phase9-cdm-integration.yml`
- Modify: `tests/test_workflows.py`

**Interfaces:**
- Produces a PR-triggered hosted smoke with ephemeral runtime token.

- [ ] **Step 1: Write failing workflow structure tests**

Require:

```text
workflow file exists
trigger = pull_request
Python = 3.14
Ruff = 0.12.12
no literal CDM_API_TOKEN value
smoke command uses six-case fixture
```

- [ ] **Step 2: Run workflow tests RED**

```bash
PYTHONPATH=src python -m pytest tests/test_workflows.py -q
```

- [ ] **Step 3: Create workflow**

Required structure:

```yaml
name: Phase 9 CDM integration

on:
  pull_request:

permissions:
  contents: read

jobs:
  phase9-cdm-integration:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      PYTHONPATH: src
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v7
        with:
          python-version: "3.14"
      - name: Install project
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]" "ruff==0.12.12"
      - name: Create ephemeral CDM token
        run: |
          python - <<'PY' >> "$GITHUB_ENV"
          import secrets
          print("CDM_API_TOKEN=" + secrets.token_urlsafe(32))
          PY
      - name: Ruff lint
        run: python -m ruff check .
      - name: Ruff format
        run: python -m ruff format --check .
      - name: Full pytest
        run: python -m pytest -q
      - name: Phase 9 smoke
        run: |
          python -m ai_service_desk cdm-integration-smoke \
            --cases tests/fixtures/phase9_cdm_integration_cases.jsonl \
            --report "$RUNNER_TEMP/phase9-cdm-integration.json"
```

No token literal belongs in YAML.

- [ ] **Step 4: Run workflow tests GREEN**

```bash
PYTHONPATH=src python -m pytest tests/test_workflows.py -q
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/phase9-cdm-integration.yml tests/test_workflows.py
git commit -m "ci: add phase 9 CDM integration smoke"
```

---

### Task 10: Final local gates, candidate freeze and draft PR

**Files:**
- No production changes expected.
- Evidence files remain outside Git or in ignored paths.

**Interfaces:**
- Produces final `CANDIDATE_HEAD` and evidence package.

- [ ] **Step 1: Freeze candidate**

Run:

```bash
git status --short
CANDIDATE_HEAD=$(git rev-parse HEAD)
echo "$CANDIDATE_HEAD"
```

PowerShell equivalent:

```powershell
$CANDIDATE_HEAD = (git rev-parse HEAD).Trim()
```

Working tree must be clean.

Any code correction after this point creates a new candidate and restarts all final gates.

- [ ] **Step 2: F1 quality gates**

```bash
python --version
python -m ruff --version
python -m ruff check .
python -m ruff format --check .
PYTHONPATH=src python -m pytest -q
```

Expected:

```text
Python 3.14.x
Ruff 0.12.12
zero lint errors
zero format errors
full pytest PASS
```

Record actual candidate test count. Do not hardcode the expected final count before collection.

- [ ] **Step 3: F2 historical node preservation**

Collect candidate IDs:

```bash
PYTHONPATH=src python -m pytest --collect-only -q > phase9-candidate-nodeids.txt
```

Compare against the baseline 701 IDs captured before Task 1.

Evidence must show:

```text
historical = 701
missing = 0
candidate = actual count
new = candidate - 701
```

- [ ] **Step 4: F3 protected blob equality**

Re-run all `git rev-parse HEAD:<path>` checks from Global Constraints and require exact equality.

Also run:

```bash
PYTHONPATH=src python -m pytest tests/engine/test_phase8_security.py tests/engine/test_phase9_security.py -q
```

- [ ] **Step 5: F4 official six-case smoke**

Generate a runtime-only token and run:

```bash
export CDM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
PYTHONPATH=src python -m ai_service_desk cdm-integration-smoke \
  --cases tests/fixtures/phase9_cdm_integration_cases.jsonl \
  --report /tmp/phase9-cdm-final.json
```

Expected:

```text
CDM INTEGRATION SMOKE OK
Casos sinteticos: 6
```

Verify the report text does not contain the token value.

- [ ] **Step 6: F5 local standalone API demonstration**

Start in one terminal with a runtime token:

```bash
export CDM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
PYTHONPATH=src python -m ai_service_desk cdm-api --host 127.0.0.1 --port 8765
```

From another terminal, use the adapter or a small Python one-liner to prove:

```text
GET missing access
POST authorized creation
GET existing active SOLICITANTE
repeated POST same request_id returns same access_id
```

Do not save the token into repository files.

- [ ] **Step 7: Publish exact candidate**

```bash
git push origin "$CANDIDATE_HEAD":refs/heads/phase-9-cdm-integration
```

Fetch and prove the remote branch equals `CANDIDATE_HEAD`.

No force push.

- [ ] **Step 8: Create draft PR**

```bash
gh pr create \
  --draft \
  --base main \
  --head phase-9-cdm-integration \
  --title "Phase 9: CDM integration"
```

PR body must record:

```text
candidate SHA
Python version
Ruff version
full pytest count
701 historical IDs preserved, zero missing
protected blobs exact
smoke 6/6
service token not versioned
no merge requested
```

- [ ] **Step 9: Hosted CI**

Per `AGENTS.md`, do not poll Actions.

Identify the PR runs for:

```text
CI
Phase 9 CDM integration
```

Report their URLs and stop. The operator returns with status/log.

- [ ] **Step 10: Final evidence after hosted CI returns**

If both hosted workflows pass on the exact candidate, produce:

```text
PHASE 9 FINAL EVIDENCE

Candidate SHA: <sha>
Remote branch SHA: <sha>
Python: 3.14.x
Ruff: 0.12.12
Full pytest: PASS, <actual> passed
Historical node IDs: 701
Candidate node IDs: <actual>
Missing historical IDs: 0
New node IDs: <actual - 701>
Protected Phase 8 blobs: PASS
Phase 8 security regression: PASS
Phase 9 security: PASS
Official CDM smoke: PASS 6/6
Standalone loopback API demo: PASS
Hosted CI: PASS <url>
Hosted Phase 9 smoke: PASS <url>
Draft PR: <url>
Final repository status: clean
Merge: NOT PERFORMED
```

Do not merge without explicit user authorization after final evidence.

---

## Self-Review Checklist

Before implementation starts, confirm this plan covers every spec requirement:

- [ ] API fake exists and uses standard library only.
- [ ] adapter uses existing `requests` dependency.
- [ ] no Phase 8 core file needs modification.
- [ ] only SOLICITANTE can be created.
- [ ] service token protects POST and is never versioned.
- [ ] GET follows canonical no-bearer contract.
- [ ] request_id idempotency covers replay and conflict.
- [ ] same email cannot receive duplicate access under concurrency.
- [ ] adapter validates response schemas fail-closed.
- [ ] no automatic retry exists.
- [ ] executor performs context defense before HTTP.
- [ ] adapter errors map to stable machine result codes.
- [ ] unexpected exceptions remain handled by existing ExecutionEngine.
- [ ] six-case end-to-end smoke exists.
- [ ] standalone API CLI exists.
- [ ] hosted workflow creates token only at runtime.
- [ ] 701 historical node IDs are preserved.
- [ ] protected blobs are verified at final gate.
- [ ] PR remains draft until explicit merge authorization.
