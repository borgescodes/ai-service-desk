# Phase 12 Web Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o Jup Resolve como aplicação web local demonstrável, conectando a UI a Knowledge, Playbook, Policy, request lifecycle, routing, approval, execução CDM e prevenção já homologados.

**Architecture:** A Fase 12 adiciona `ai_service_desk.web` como application layer fina e FastAPI como boundary HTTP. A demo usa stores in-memory, adapters determinísticos somente para classificação/embedding sintéticos e o fake CDM HTTP homologado. O frontend é uma SPA em HTML, CSS e ES Modules sem dependências npm de runtime, servida pelo próprio backend após build reproduzível.

**Tech Stack:** Python 3.14, FastAPI 0.141.1, Uvicorn 0.52.4, pytest, Ruff 0.12.12, HTML semântico, CSS, JavaScript ES Modules, Node `node:test` e GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-phase-12-web-demo-design.md`

## Global Constraints

- Base SHA: `a4c4dc25afd07f449036dd837dbcfa4a219806c2`.
- Historical baseline: exatamente `925` pytest node IDs.
- Branch: `phase-12-web-demo`.
- Empresa: `Juparanã`.
- Produto: `Jup Resolve`.
- Agente: `Jup`.
- Descriptor: `Assistente de IA da Juparanã`.
- Assinatura: `Inteligência para o Service Desk`.
- Brand green: `#45813C`.
- Brand yellow: `#EEB41E`.
- Brand gray: `#808285`.
- Brand white: `#FFFFFF`.
- Nenhum módulo core protegido da spec pode mudar.
- Frontend nunca decide policy, routing, approval, execution ou prevention.
- Frontend nunca chama CDM.
- Identity de demo é allowlisted pelo backend e nunca derivada do texto do chat.
- Demo deve funcionar sem internet e sem CDN.
- Nenhuma fonte proprietária é versionada sem licença.
- Todos os comportamentos de produto seguem RED, GREEN, REFACTOR.
- Configuração declarativa pode ser validada estruturalmente sem teste artificial.
- Nenhum merge faz parte deste plano.

---

## File Map

### Create

```text
src/ai_service_desk/web/__init__.py
src/ai_service_desk/web/demo_identity.py
src/ai_service_desk/web/demo_ai.py
src/ai_service_desk/web/demo_data.py
src/ai_service_desk/web/errors.py
src/ai_service_desk/web/presentation.py
src/ai_service_desk/web/demo_runtime.py
src/ai_service_desk/web/api.py
src/ai_service_desk/web/smoke.py
src/ai_service_desk/phase12_cli.py

tests/web/test_demo_identity.py
tests/web/test_demo_ai.py
tests/web/test_demo_runtime.py
tests/web/test_presentation.py
tests/web/test_api.py
tests/web/test_phase12_security.py
tests/web/test_web_demo_smoke.py
tests/test_phase12_cli.py
tests/test_phase12_workflow.py

web/package.json
web/src/index.html
web/src/styles.css
web/src/app.mjs
web/src/api.mjs
web/src/router.mjs
web/src/render.mjs
web/src/state.mjs
web/src/components.mjs
web/scripts/lint.mjs
web/scripts/build.mjs
web/tests/render.test.mjs
web/tests/state.test.mjs
web/tests/router.test.mjs

run-web-demo.cmd
docs/demo/phase-12-demo-script.md
docs/environment/web-demo.md
.github/workflows/phase12-web-demo.yml
```

### Modify

```text
pyproject.toml
src/ai_service_desk/__main__.py
README.md
```

### Protected and expected unchanged

Todos os módulos listados na seção `Proteção do domínio homologado` da spec.

---

## Task 1: Dependencies and Phase 12 CLI contract

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ai_service_desk/phase12_cli.py`
- Modify: `src/ai_service_desk/__main__.py`
- Create: `tests/test_phase12_cli.py`

**Interfaces:**
- Produces: CLI `web-demo`, CLI `web-demo-smoke`, dependency pins de FastAPI/Uvicorn.
- Consumes: dispatch pattern existente em `__main__.py`.

- [ ] **Step 1: Write failing CLI tests**

Testar:

```python
def test_phase12_dispatches_web_demo(monkeypatch):
    calls = []
    monkeypatch.setattr(phase12_cli, "run_web_demo", lambda host, port: calls.append((host, port)))
    assert phase12_cli.main(["web-demo", "--host", "127.0.0.1", "--port", "8123"]) == 0
    assert calls == [("127.0.0.1", 8123)]


def test_phase12_web_demo_rejects_non_loopback_host():
    with pytest.raises(SystemExit):
        phase12_cli.main(["web-demo", "--host", "0.0.0.0"])
```

Também testar que `__main__` delega comandos F12 sem alterar comandos anteriores.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_phase12_cli.py -q
```

Expected: FAIL porque `phase12_cli` e comandos ainda não existem.

- [ ] **Step 3: Add pinned dependencies and minimal CLI**

Adicionar em `dependencies`:

```toml
"fastapi==0.141.1",
"uvicorn==0.52.0",
```

Criar parser F12 com:

```text
web-demo --host 127.0.0.1 --port 8000
web-demo-smoke
```

`web-demo` aceita somente `127.0.0.1`, `localhost` ou `::1`.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/test_phase12_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ai_service_desk/phase12_cli.py src/ai_service_desk/__main__.py tests/test_phase12_cli.py
git commit -m "feat: add phase 12 web demo commands"
```

---

## Task 2: Demo identity provider

**Files:**
- Create: `src/ai_service_desk/web/__init__.py`
- Create: `src/ai_service_desk/web/demo_identity.py`
- Create: `tests/web/test_demo_identity.py`

**Interfaces:**
- Produces: `DemoIdentity`, `DemoIdentityProvider`, `IdentityNotFoundError`, `requester_identity()`, `technician_identity()`.
- Consumes: `SessionIdentity`, `TechnicianIdentity`.

- [ ] **Step 1: Write failing tests**

Exigir:

```text
provider lista somente identities predefinidas
pedro-miranda resolve requester sintético exato
tecnico-cdm resolve TechnicianIdentity TECH-CDM exata
identity desconhecida falha com IDENTITY_NOT_FOUND
requester não pode ser convertido em technician
technician sem requester profile não é usado como solicitante
payload público não contém capability mutável enviada pelo cliente
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_identity.py -q
```

Expected: FAIL por módulo ausente.

- [ ] **Step 3: Implement minimal provider**

`DemoIdentity` frozen contém:

```python
identity_id: str
name: str
username: str
email: str
area: str
role: Literal["REQUESTER", "TECHNICIAN"]
technician_id: str | None
capabilities: frozenset[str]
```

Criar exatamente as identities necessárias ao roteiro, incluindo `pedro-miranda` e `tecnico-cdm`.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_identity.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web tests/web/test_demo_identity.py
git commit -m "feat: add demo identity provider"
```

---

## Task 3: Deterministic demo AI adapters

**Files:**
- Create: `src/ai_service_desk/web/demo_ai.py`
- Create: `tests/web/test_demo_ai.py`

**Interfaces:**
- Produces: `DemoClassifierClient.chat(payload)`, `DemoEmbedder.embed(texts)`.
- Consumes: contracts de `classify_ticket` e `KnowledgeEngine`.

- [ ] **Step 1: Write failing tests**

Exigir:

```text
CDM access text -> payload válido PROBLEMA_ACESSO / CDM
Microsoft 365 password/access text -> PROBLEMA_ACESSO / OFFICE 365
unknown text -> OUTRO / vazio
classifier nunca lê identity
embedder possui model/digest/dimensions fixos
embedder é determinístico para mesma entrada
embedder retorna numpy float32 2D
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_ai.py -q
```

- [ ] **Step 3: Implement adapters**

`DemoClassifierClient.chat` lê somente a última mensagem do payload já construído pelo core e devolve o envelope que `classify_ticket` valida.

`DemoEmbedder` usa hashing determinístico de tokens para um vetor pequeno e normalizado. Ele não conhece policy, request, identity ou routing.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_ai.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/demo_ai.py tests/web/test_demo_ai.py
git commit -m "feat: add deterministic demo ai adapters"
```

---

## Task 4: Synthetic demo knowledge, playbook and prevention data

**Files:**
- Create: `src/ai_service_desk/web/demo_data.py`
- Create: `tests/web/test_demo_runtime.py`

**Interfaces:**
- Produces: `write_demo_knowledge(path)`, `write_demo_playbooks(path)`, `demo_outcomes()`.
- Consumes: schemas F4, F6 e F11.

- [ ] **Step 1: Write failing data tests inside runtime test module**

Exigir:

```text
knowledge source é validada por load_knowledge
playbook source é validada por load_playbooks
CDM article tem playbook APPROVED e ACTION_PROPOSAL CDM_ACCESS_REQUEST
M365 article é APPROVED e não possui playbook
outcomes passam validate_outcome_record
nenhum email/nome corporativo real aparece nos outcomes
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k demo_data
```

- [ ] **Step 3: Implement minimal synthetic data**

Knowledge IDs:

```text
KB-SYN-CDM-ACCESS-001
KB-SYN-M365-PASSWORD-001
```

Playbook:

```text
PB-SYN-CDM-ACCESS-001
STEP-CDM-ACCESS-01
CDM_ACCESS_REQUEST
```

Outcomes devem criar ao menos uma oportunidade recorrente explicável com `MIN_RECURRENCE = 3`.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k demo_data
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/demo_data.py tests/web/test_demo_runtime.py
git commit -m "feat: add synthetic web demo data"
```

---

## Task 5: Demo runtime composition and reset

**Files:**
- Create: `src/ai_service_desk/web/errors.py`
- Create: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `tests/web/test_demo_runtime.py`

**Interfaces:**
- Produces: `DemoRuntime`, `DemoRuntime.reset()`, `DemoRuntime.close()`, `DemoRuntime.send_message()`.
- Consumes: all homologated application/domain services listed in spec.

- [ ] **Step 1: Write failing runtime composition tests**

Exigir após `DemoRuntime.create()`:

```text
request repository vazio
routing store vazio
conversation vazia
fake CDM access_count 0
prevention fixture carregada
reset recria estado inicial
close encerra fake CDM server
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k runtime
```

- [ ] **Step 3: Implement composition**

No reset:

```text
TemporaryDirectory para artifacts demo
build_knowledge_index com DemoEmbedder
build_playbook_catalog
KnowledgeEngine
PlaybookEngine
InMemoryRequestRepository
PolicyEngine
RequestLifecycleService
TechnicianAuthorizationRegistry
RoutingRegistry
RoutingService
RoutedRequestService
ApprovalQueue
ApprovalService
build_cdm_server em 127.0.0.1:0
CDMAdapter
CDMActionExecutor
ExecutionEngine
InMemoryOutcomeStore + demo_outcomes
```

O fake CDM roda em thread daemon controlada pelo runtime e é fechado antes de recriar reset.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k runtime
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/errors.py src/ai_service_desk/web/demo_runtime.py tests/web/test_demo_runtime.py
git commit -m "feat: compose deterministic demo runtime"
```

---

## Task 6: Jup conversation orchestration

**Files:**
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `tests/web/test_demo_runtime.py`

**Interfaces:**
- Produces: `send_message(identity_id: str, message: str) -> dict`.
- Consumes: `TriageEngine`, `PlaybookEngine`, `prepare_access_request`, `RoutedRequestService`, `OutcomeCollector`.

- [ ] **Step 1: Write failing conversation tests**

Casos:

```text
mensagem vazia rejeitada
M365 -> KNOWLEDGE_FOUND, answer literal, zero requests
CDM -> PLAYBOOK_FOUND, request PENDING_APPROVAL, assignment TECH-CDM
CDM privileged role -> DENIED_POLICY e não entra na fila
texto insuficiente -> clarification sem request
texto não altera identity do requester
```

No caso CDM, verificar também:

```text
record.context.requester == provider requester
record.context.requested_role == SOLICITANTE
record.creation_policy.decision == REQUIRE_APPROVAL
record.confidence.level == HIGH
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k message
```

- [ ] **Step 3: Implement minimal orchestration**

Cada identity possui `TriageEngine`/state próprio. Ao terminal, nova mensagem começa nova interação em vez de reabrir state terminal.

Preservar metadata web por request:

```text
classification_confidence
source_interaction_id
```

Outcome de Knowledge é ingerido somente quando `KNOWLEDGE_FOUND` sem request.

Outcome de request pode ser atualizado por interaction IDs distintos por milestone, sem sobrescrever evidência histórica.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k message
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/demo_runtime.py tests/web/test_demo_runtime.py
git commit -m "feat: orchestrate jup demo conversations"
```

---

## Task 7: Request listing, detail and timeline

**Files:**
- Create: `src/ai_service_desk/web/presentation.py`
- Create: `tests/web/test_presentation.py`
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `tests/web/test_demo_runtime.py`

**Interfaces:**
- Produces: `present_request`, `present_timeline`, `DemoRuntime.list_requests`, `DemoRuntime.get_request`.
- Consumes: `AccessRequestRecord`, `AuditEvent`, routing assignment e web metadata.

- [ ] **Step 1: Write failing presentation tests**

Exigir:

```text
status labels em português
confidence HIGH não usa success semantic
percentual usa classification provenance quando existe
percentual ausente fica null, não inventado
policy reason_code não aparece no requester payload
timeline contém somente audit events existentes
requester só lista suas próprias requests
requester não abre request de outro requester
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_presentation.py tests/web/test_demo_runtime.py -q -k request
```

- [ ] **Step 3: Implement serializers and request queries**

Não serializar `__dict__` de dataclasses. Montar allowlist explícita de campos.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_presentation.py tests/web/test_demo_runtime.py -q -k request
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/presentation.py src/ai_service_desk/web/demo_runtime.py tests/web/test_presentation.py tests/web/test_demo_runtime.py
git commit -m "feat: present request lifecycle for web"
```

---

## Task 8: Operations approval queue

**Files:**
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `src/ai_service_desk/web/presentation.py`
- Modify: `tests/web/test_demo_runtime.py`

**Interfaces:**
- Produces: `DemoRuntime.list_approvals(identity_id)`.
- Consumes: `ApprovalQueue.pending`.

- [ ] **Step 1: Write failing queue tests**

Exigir:

```text
requester -> NOT_AUTHORIZED
TECH-CDM -> vê request CDM atribuída
outro técnico -> não vê request CDM
item sai da fila após decisão
payload inclui routing responsável, mas não concede autorização
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k approval_queue
```

- [ ] **Step 3: Implement queue adapter**

Resolver `TechnicianIdentity` no provider e chamar:

```python
approval_queue.pending(technician_id=technician.technician_id)
```

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k approval_queue
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web tests/web/test_demo_runtime.py
git commit -m "feat: expose routed approval inbox"
```

---

## Task 9: Approval, rejection and CDM execution

**Files:**
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `tests/web/test_demo_runtime.py`

**Interfaces:**
- Produces: `approve_request`, `reject_request`.
- Consumes: `ApprovalService`, `ExecutionEngine`, audit repository.

- [ ] **Step 1: Write failing decision tests**

Exigir:

```text
requester approve -> NOT_AUTHORIZED
TECH-CDM approve PENDING v2 -> ApprovalService é usado e final COMPLETED
approve response events incluem REQUEST_APPROVED, EXECUTION_STARTED, EXECUTION_COMPLETED
fake CDM access_count vira 1
stale expected_version -> VERSION_CONFLICT
reject -> REJECTED e nunca chama execution
privileged DENIED_POLICY nunca pode ser aprovado
execution failure fixture -> FAILED com mensagem segura
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k "approve or reject or execution"
```

- [ ] **Step 3: Implement decisions**

`approve_request`:

```python
approved = approval_service.approve(...)
final = execution_engine.execute(request_id, expected_version=approved.version)
```

Não chamar lifecycle transitions diretamente na web layer.

`reject_request` chama somente `ApprovalService.reject`.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_runtime.py -q -k "approve or reject or execution"
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/demo_runtime.py tests/web/test_demo_runtime.py
git commit -m "feat: connect approval to controlled cdm execution"
```

---

## Task 10: Prevention queries

**Files:**
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `src/ai_service_desk/web/presentation.py`
- Modify: `tests/web/test_demo_runtime.py`
- Modify: `tests/web/test_presentation.py`

**Interfaces:**
- Produces: `list_prevention`, `get_prevention`.
- Consumes: `PatternAggregator.aggregate`, `OpportunityEngine.generate`.

- [ ] **Step 1: Write failing prevention tests**

Exigir:

```text
requester não autorizado
TECH-CDM recebe oportunidades geradas pelo engine F11
IDs são os IDs reais de PreventionOpportunity
occurrence_count não é recalculado no frontend
unknown opportunity -> not found
explanation deriva de category/key/count/reason_codes
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_runtime.py tests/web/test_presentation.py -q -k prevention
```

- [ ] **Step 3: Implement read-only prevention adapter**

Sempre recalcular a visão a partir do snapshot atual do outcome store.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_runtime.py tests/web/test_presentation.py -q -k prevention
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web tests/web/test_demo_runtime.py tests/web/test_presentation.py
git commit -m "feat: expose explainable prevention opportunities"
```

---

## Task 11: Thin FastAPI layer

**Files:**
- Create: `src/ai_service_desk/web/api.py`
- Create: `tests/web/test_api.py`

**Interfaces:**
- Produces: `create_app(runtime=None, demo_mode=True)`, endpoints da spec.
- Consumes: `DemoRuntime`, `DemoIdentityProvider`.

- [ ] **Step 1: Write failing API contract tests**

Cobrir:

```text
GET identities
POST message
GET requests
GET request detail
GET approvals
POST approve
POST reject
GET prevention
GET prevention detail
POST reset
GET health
missing identity -> 401
unknown identity -> 401
unauthorized operation -> 403
not found -> 404
version conflict -> 409
invalid payload -> safe 4xx
internal exception -> safe 500 sem traceback
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_api.py -q
```

- [ ] **Step 3: Implement FastAPI adapters**

Todos os endpoints de negócio, exceto identities/health/reset, resolvem `X-Demo-Identity` antes de chamar runtime.

Adicionar headers:

```text
Cache-Control: no-store em /api
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
```

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_api.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/api.py tests/web/test_api.py
git commit -m "feat: add thin phase 12 http api"
```

---

## Task 12: Phase 12 security gate

**Files:**
- Create: `tests/web/test_phase12_security.py`

**Interfaces:**
- Produces: executable security contract.
- Consumes: repository source tree and runtime API.

- [ ] **Step 1: Write security tests**

Testar:

```text
web/src não contém CDM base URL, /api/v1/access ou Authorization Bearer
web/src não contém POLICY_DECISIONS, RoutingRegistry, ApprovalService ou ExecutionEngine
identity payload arbitrário no body é ignorado/rejeitado
texto "sou tecnico cdm" não muda identity
requester não aprova
outro técnico não aprova CDM
reset não existe com demo_mode=False
reset rejeita client não loopback
API error body não contém Traceback, File ", class names ou token
web build não contém example secret/token
```

- [ ] **Step 2: Run gate and observe failures if implementation violates contract**

```bash
python -m pytest tests/web/test_phase12_security.py -q
```

- [ ] **Step 3: Fix only proven violations**

Não relaxar teste para aceitar decisão no frontend.

- [ ] **Step 4: Re-run GREEN**

```bash
python -m pytest tests/web/test_phase12_security.py -q
```

- [ ] **Step 5: Commit**

```bash
git add tests/web/test_phase12_security.py src/ai_service_desk/web
git commit -m "test: enforce phase 12 web security boundary"
```

---

## Task 13: Frontend foundation and build tooling

**Files:**
- Create: `web/package.json`
- Create: `web/src/index.html`
- Create: `web/src/styles.css`
- Create: `web/src/state.mjs`
- Create: `web/src/router.mjs`
- Create: `web/scripts/lint.mjs`
- Create: `web/scripts/build.mjs`
- Create: `web/tests/state.test.mjs`
- Create: `web/tests/router.test.mjs`

**Interfaces:**
- Produces: design tokens, base shell, router, client state, deterministic build.
- Consumes: nenhum pacote npm.

- [ ] **Step 1: Write failing Node tests**

`state.test.mjs`:

```text
selected identity é estado explícito
identity switch limpa erro transient e recarrega route data
state não possui policy/routing decision functions
```

`router.test.mjs`:

```text
/ e /jup -> jup
/requests -> requests
/operations -> approvals
/operations/prevention -> prevention
rota desconhecida -> jup
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/state.test.mjs web/tests/router.test.mjs
```

Expected: FAIL por módulos ausentes.

- [ ] **Step 3: Implement base**

`styles.css` declara os tokens exatos da spec e layout shell desktop/mobile.

`package.json` contém apenas scripts, sem dependencies:

```json
{
  "private": true,
  "type": "module",
  "scripts": {
    "lint": "node scripts/lint.mjs",
    "test": "node --test tests/*.test.mjs",
    "build": "node scripts/build.mjs"
  }
}
```

- [ ] **Step 4: Run GREEN and build**

```bash
node --test web/tests/state.test.mjs web/tests/router.test.mjs
node web/scripts/lint.mjs
node web/scripts/build.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: establish jup resolve frontend foundation"
```

---

## Task 14: Frontend API client and safe rendering primitives

**Files:**
- Create: `web/src/api.mjs`
- Create: `web/src/render.mjs`
- Create: `web/src/components.mjs`
- Create: `web/tests/render.test.mjs`

**Interfaces:**
- Produces: `apiRequest`, `escapeHtml`, status/confidence render helpers, base components.
- Consumes: HTTP contracts da Task 11.

- [ ] **Step 1: Write failing render tests**

Exigir:

```text
escapeHtml neutraliza <script>, &, aspas
confidence HIGH renderiza label próprio e não success
status COMPLETED renderiza status sem depender só de cor
error state inclui retry copy
empty state inclui próxima ação quando aplicável
operation nav depende de can_operate recebido, não de nome da identity
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/render.test.mjs
```

- [ ] **Step 3: Implement primitives**

Todo texto vindo da API passa por `escapeHtml` antes de interpolação em HTML string.

Ícones usam SVG inline simples e acessível ou caracteres semânticos, sem CDN.

- [ ] **Step 4: Run GREEN**

```bash
node --test web/tests/render.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests/render.test.mjs
git commit -m "feat: add safe frontend rendering primitives"
```

---

## Task 15: App header, navigation and identity switcher

**Files:**
- Create: `web/src/app.mjs`
- Modify: `web/src/components.mjs`
- Modify: `web/src/styles.css`
- Modify: `web/tests/render.test.mjs`

**Interfaces:**
- Produces: `AppHeader`, `PrimaryNavigation`, `DemoIdentitySwitcher` behavior.
- Consumes: identities API and router.

- [ ] **Step 1: Add failing UI model tests**

Exigir:

```text
header mostra Jup Resolve e descriptor
Jup e Solicitações sempre visíveis
Operação somente can_operate
switcher usa IDs recebidos da API
switcher nunca edita username/email/role
aria-current acompanha route
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/*.test.mjs
```

- [ ] **Step 3: Implement header/navigation**

Desktop com navegação horizontal compacta. Mobile com nav adaptada sem esconder rota atual.

- [ ] **Step 4: Run GREEN**

```bash
node --test web/tests/*.test.mjs
node web/scripts/lint.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: add jup resolve navigation and demo identity switcher"
```

---

## Task 16: Jup surface

**Files:**
- Modify: `web/src/app.mjs`
- Modify: `web/src/components.mjs`
- Modify: `web/src/styles.css`
- Modify: `web/tests/render.test.mjs`

**Interfaces:**
- Produces: idle Jup view, conversation, composer, context panel, thinking/error states.
- Consumes: `POST /api/jup/messages`.

- [ ] **Step 1: Add failing Jup render tests**

Exigir:

```text
idle viewport contém Jup Resolve, greeting e composer
sem KPI cards
conversation contém user/Jup messages
context panel contém Sistema, Solicitação, Finalidade, Confiança, Policy, Próxima etapa
thinking tem aria-live
clarification mostra pergunta
knowledge answer preserva texto recebido
request created mostra request_id e waiting approval
API error mostra retry
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/render.test.mjs
```

- [ ] **Step 3: Implement Jup UI**

`JupAvatar` usa fallback monogram local e estrutura pronta para trocar por asset aprovado.

Desktop usa conversation + context grid. Mobile transforma context em accordion abaixo da conversa.

- [ ] **Step 4: Run GREEN**

```bash
node --test web/tests/*.test.mjs
node web/scripts/lint.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: build jup conversational workspace"
```

---

## Task 17: Requests surface

**Files:**
- Modify: `web/src/app.mjs`
- Modify: `web/src/components.mjs`
- Modify: `web/src/styles.css`
- Modify: `web/tests/render.test.mjs`

**Interfaces:**
- Produces: RequestList, RequestTimeline, empty/loading/error states.
- Consumes: request APIs.

- [ ] **Step 1: Add failing request UI tests**

Exigir:

```text
empty requests copy
list mostra title, ID, status, time
click abre detail
lifecycle usa somente timeline recebida
confidence não parece success/error
mobile detail não causa horizontal overflow por estrutura
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/render.test.mjs
```

- [ ] **Step 3: Implement requests UI**

Não inventar milestones ausentes.

- [ ] **Step 4: Run GREEN**

```bash
node --test web/tests/*.test.mjs
node web/scripts/lint.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: add requester lifecycle surface"
```

---

## Task 18: Operations approvals and execution progression

**Files:**
- Modify: `web/src/app.mjs`
- Modify: `web/src/components.mjs`
- Modify: `web/src/styles.css`
- Modify: `web/tests/render.test.mjs`

**Interfaces:**
- Produces: OperationInbox, ApprovalDetail, ExecutionProgress.
- Consumes: approvals and decision APIs.

- [ ] **Step 1: Add failing operations tests**

Exigir:

```text
empty queue
split view desktop
requester nunca recebe approve button
technician detail mostra requester/area/purpose/policy/confidence/routing
approve action entra em loading e evita duplicate submit
success só aparece após response COMPLETED
FAILED mostra recovery copy
reject visualmente distinto e confirmado quando necessário
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/render.test.mjs
```

- [ ] **Step 3: Implement operation inbox**

Enquanto POST está pendente:

```text
Aprovando solicitação...
```

Após resposta, renderizar `progress_events` reais.

- [ ] **Step 4: Run GREEN**

```bash
node --test web/tests/*.test.mjs
node web/scripts/lint.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: add controlled approval and execution ui"
```

---

## Task 19: Prevention surface

**Files:**
- Modify: `web/src/app.mjs`
- Modify: `web/src/components.mjs`
- Modify: `web/src/styles.css`
- Modify: `web/tests/render.test.mjs`

**Interfaces:**
- Produces: PreventionList, PreventionDetail.
- Consumes: prevention APIs.

- [ ] **Step 1: Add failing prevention UI tests**

Exigir:

```text
empty prevention
list não tem KPI header
cada item mostra occurrences, system, intent e category
click abre explicação
explanation inclui por que foi identificado
categoria vem do servidor
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/render.test.mjs
```

- [ ] **Step 3: Implement prevention UI**

Usar estrutura editorial operacional, não cards de dashboard.

- [ ] **Step 4: Run GREEN**

```bash
node --test web/tests/*.test.mjs
node web/scripts/lint.mjs
```

- [ ] **Step 5: Commit**

```bash
git add web
git commit -m "feat: add explainable prevention inbox"
```

---

## Task 20: Static serving and production local build

**Files:**
- Modify: `src/ai_service_desk/web/api.py`
- Modify: `src/ai_service_desk/phase12_cli.py`
- Modify: `web/scripts/build.mjs`
- Modify: `tests/web/test_api.py`

**Interfaces:**
- Produces: same-origin SPA serving from `web/dist`.
- Consumes: FastAPI static responses.

- [ ] **Step 1: Write failing static tests**

Exigir:

```text
/ entrega index build
/requests entrega SPA index
/api unknown continua JSON 404, não SPA
assets têm MIME correto
CSP não permite CDN
missing web/dist dá erro de startup orientado a build
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_api.py -q -k static
```

- [ ] **Step 3: Implement static serving**

Não servir `web/src` no modo de apresentação.

- [ ] **Step 4: Build and GREEN**

```bash
node web/scripts/build.mjs
python -m pytest tests/web/test_api.py -q -k static
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web src/ai_service_desk/phase12_cli.py web
git commit -m "feat: serve production web demo build"
```

---

## Task 21: Web demo smoke

**Files:**
- Create: `src/ai_service_desk/web/smoke.py`
- Create: `tests/web/test_web_demo_smoke.py`
- Modify: `src/ai_service_desk/phase12_cli.py`

**Interfaces:**
- Produces: `run_web_demo_smoke() -> dict`, CLI marker `WEB DEMO SMOKE OK`.
- Consumes: `DemoRuntime`.

- [ ] **Step 1: Write failing smoke test**

Assert exatamente dez cases:

```text
requester identity
knowledge no request
CDM request created
routing TECH-CDM
technician pending visibility
approve
CDM execution complete
requester completed visibility
policy denied absent from queue
prevention available
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_web_demo_smoke.py -q
```

- [ ] **Step 3: Implement smoke**

Report contém somente dados sintéticos seguros e booleanos/códigos agregados.

- [ ] **Step 4: Run GREEN and CLI**

```bash
python -m pytest tests/web/test_web_demo_smoke.py -q
python -m ai_service_desk web-demo-smoke
```

Expected stdout inclui:

```text
WEB DEMO SMOKE OK
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/smoke.py src/ai_service_desk/phase12_cli.py tests/web/test_web_demo_smoke.py
git commit -m "test: add deterministic phase 12 web demo smoke"
```

---

## Task 22: Windows runner and documentation

**Files:**
- Create: `run-web-demo.cmd`
- Create: `docs/environment/web-demo.md`
- Create: `docs/demo/phase-12-demo-script.md`
- Modify: `README.md`

**Interfaces:**
- Produces: reproducible operator workflow.
- Consumes: CLI/build commands.

- [ ] **Step 1: Add documentation contract to CLI/workflow tests where structural checks are useful**

Verificar que docs citam:

```text
pré-requisitos
build
execução
reset
fake CDM
frontend
backend
troubleshooting
hero flow
```

- [ ] **Step 2: Write `run-web-demo.cmd`**

Fluxo:

```bat
@echo off
setlocal
where node >nul 2>nul || exit /b 1
python --version || exit /b 1
node web\scripts\build.mjs || exit /b 1
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000
```

Não incluir token real ou variável de segredo.

- [ ] **Step 3: Write environment guide**

Documentar comandos individuais para diagnóstico e o reset local.

- [ ] **Step 4: Write final demo script**

Roteiro mínimo:

```text
1. abrir como Pedro
2. resolver M365 por Knowledge
3. solicitar CDM
4. mostrar contexto/confidence
5. trocar para Técnico CDM
6. abrir Pendências
7. aprovar
8. mostrar eventos reais de policy/execution
9. voltar ao Pedro
10. mostrar COMPLETED
11. abrir Prevenção
12. explicar recorrência
```

- [ ] **Step 5: Commit**

```bash
git add run-web-demo.cmd docs README.md
git commit -m "docs: add phase 12 demo runbook"
```

---

## Task 23: Phase 12 workflow

**Files:**
- Create: `.github/workflows/phase12-web-demo.yml`
- Create: `tests/test_phase12_workflow.py`

**Interfaces:**
- Produces: hosted PR gate.
- Consumes: all F12 commands and previous security/smoke gates.

- [ ] **Step 1: Write failing workflow structure test**

Exigir strings/steps para:

```text
Python 3.14
Ruff 0.12.12
historical baseline a4c4dc25...
historical expected 925
full pytest
Node setup
frontend lint
frontend tests
frontend build
protected blobs
Phase 8 security
Phase 9 security
Phase 10 security
Phase 11 security
Phase 12 security
Phase 10 smoke
Phase 11 smoke
Phase 12 smoke
working tree clean
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/test_phase12_workflow.py -q
```

- [ ] **Step 3: Create workflow**

Historical gate usa worktree detached no base SHA e compara sets de node IDs.

Build frontend pode gerar `web/dist`; remover `web/dist` antes do gate final de working tree ou manter `web/dist` ignorado.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/test_phase12_workflow.py -q
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/phase12-web-demo.yml tests/test_phase12_workflow.py
git commit -m "ci: add phase 12 web demo gate"
```

---

## Task 24: Full local verification before visual QA

**Files:** none unless a failing check proves a defect.

- [ ] **Step 1: Build frontend**

```bash
node web/scripts/build.mjs
```

Expected: PASS.

- [ ] **Step 2: Frontend lint and tests**

```bash
node web/scripts/lint.mjs
node --test web/tests/*.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Python quality**

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Security and smokes**

```bash
python -m pytest tests/engine/test_phase8_security.py -q
python -m pytest tests/engine/test_phase9_security.py -q
python -m pytest tests/engine/test_phase10_security.py -q
python -m pytest tests/engine/test_phase11_security.py -q
python -m pytest tests/web/test_phase12_security.py -q
python -m ai_service_desk routing-escalation-smoke
python -m ai_service_desk learning-prevention-smoke
python -m ai_service_desk web-demo-smoke
```

Expected: PASS.

- [ ] **Step 5: Historical and protected blob checks**

Comparar candidate contra `a4c4dc25...` e confirmar:

```text
historical_node_ids=925
missing_historical_node_ids=0
protected_blobs=PASS
```

Não avançar se qualquer core blob mudou.

---

## Task 25: Impeccable visual QA

**Files:**
- Modify: `web/src/styles.css`, `web/src/components.mjs` ou `web/src/app.mjs` somente quando findings comprovarem necessidade.
- Create: screenshots em diretório de evidência não necessariamente versionado.

**Interfaces:**
- Produces: visual review evidence.
- Consumes: production local build.

- [ ] **Step 1: Start production demo**

```bash
node web/scripts/build.mjs
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: Capture required desktop states**

Capturar em 1440px e revisar:

```text
Jup idle
Jup conversation
Requests
Operations approvals
Prevention
```

- [ ] **Step 3: Capture responsive states**

Capturar:

```text
1280px primary screens
390px Jup
390px operation detail
```

- [ ] **Step 4: Review against Impeccable gates**

Checar:

```text
task clarity
contrast
keyboard focus
touch targets
no horizontal overflow
async state clarity
empty/error states
spacing system
typography roles
product specificity
reduced motion
```

- [ ] **Step 5: Fix findings in one batch**

Para qualquer behavior bug, escrever RED test antes do fix. Para CSS-only visual corrections, aplicar correção declarativa e repetir lint/build.

- [ ] **Step 6: Confirm with at most one more capture round**

Registrar `PASS` ou findings explicitamente aceitos.

---

## Task 26: Candidate freeze and hosted homologation

**Files:** PR metadata only unless hosted failure proves a defect.

- [ ] **Step 1: Run verification-before-completion checks again on final SHA**

Repetir os gates da Task 24 após qualquer visual correction.

- [ ] **Step 2: Confirm working tree clean**

```bash
git status --short
```

Expected: empty.

- [ ] **Step 3: Push candidate and open Draft PR**

PR:

```text
Title: Phase 12: web interface and final demo
Base: main
Head: phase-12-web-demo
Draft: true
```

- [ ] **Step 4: Record candidate SHA**

```bash
git rev-parse HEAD
```

Não alterar candidate enquanto os workflows estiverem sendo homologados.

- [ ] **Step 5: Hosted workflow handling**

Identificar os runs do candidate e informar o que precisa concluir. Não fazer polling automático. O operador acompanha e retorna com status/log conforme `AGENTS.md`.

- [ ] **Step 6: Update PR final evidence only after all same-SHA workflows are green**

Corpo deve conter:

```text
## Phase 12 final evidence

Base SHA:
a4c4dc25afd07f449036dd837dbcfa4a219806c2

Candidate SHA:
<sha>

Python:
3.14.x

Ruff:
0.12.12

Python pytest:
<n> passed

Historical Python node IDs:
925

Missing historical:
0

New Python node IDs:
<n>

Frontend:
lint PASS
tests <n> PASS
build PASS

Protected core blobs:
PASS

Security F8:
PASS

Security F9:
PASS

Security F10:
PASS

Security F11:
PASS

Security F12:
PASS

Routing smoke:
PASS

Learning/prevention smoke:
PASS

Web demo smoke:
PASS

Visual review:
PASS / findings explicitly accepted

Hosted workflows:
PASS

Merge:
NOT PERFORMED
```

- [ ] **Step 7: Stop before merge**

Final state:

```text
OPEN
DRAFT
NOT MERGED
```

Não marcar Ready e não mergear sem autorização explícita.

---

## Self-review

### Spec coverage

O plano cobre stack, application/API layer, identities, conversation orchestration, requests, approvals, prevention, execution CDM, reset, security, frontend foundation, navigation, Jup, Requests, Operação, responsive, accessibility, build, smoke, docs, CI, visual QA e homologação.

### Placeholder scan

Nenhuma task depende de `TBD`, `TODO` ou implementação futura não definida.

### Type consistency

Interfaces centrais usadas por tasks posteriores:

```text
DemoIdentityProvider.resolve(identity_id)
DemoRuntime.send_message(identity_id, message)
DemoRuntime.list_requests(identity_id)
DemoRuntime.get_request(identity_id, request_id)
DemoRuntime.list_approvals(identity_id)
DemoRuntime.approve_request(identity_id, request_id, expected_version)
DemoRuntime.reject_request(identity_id, request_id, expected_version)
DemoRuntime.list_prevention(identity_id)
DemoRuntime.get_prevention(identity_id, opportunity_id)
create_app(runtime=None, demo_mode=True)
run_web_demo_smoke()
```

Esses nomes permanecem estáveis no restante do plano.
