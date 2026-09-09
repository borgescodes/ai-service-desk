# Phase 10 Routing and Escalation Implementation Plan

**Goal:** Implementar roteamento operacional determinístico, assignment idempotente, fila de aprovação derivada e encaminhamento automático de requests `PENDING_APPROVAL`, sem alterar policy, confidence, lifecycle ou integração CDM homologados.

**Architecture:** A Fase 10 cria `routing.py` como domínio separado. `RoutingRegistry` valida regras contra `TechnicianAuthorizationRegistry`; `InMemoryRoutingAssignmentStore` garante idempotência e conflito fail-closed sob `RLock`; `RoutingService` só roteia `PENDING_APPROVAL`; `ApprovalQueue` deriva sua visão do repository atual mais assignments; `RoutedRequestService` compõe lifecycle e routing sem alterar o lifecycle. Um smoke local de oito casos e um workflow `pull_request` fecham os gates.

**Tech Stack:** Python 3.14, dataclasses, threading.RLock, pytest, Ruff 0.12.12, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-phase-10-routing-escalation-design.md`

## Global constraints

- Base SHA: `e5d0e3ccde56effff5c5f9558591b0d12c0740bb`.
- Historical baseline: exatamente `786` pytest node IDs.
- Branch: `phase-10-routing-escalation`.
- Nenhum dos 12 arquivos protegidos pode mudar.
- Estados da Fase 8 permanecem exatamente os oito homologados.
- Routing não chama policy, executor, CDM, HTTP, LLM ou Ollama.
- Routing não concede autorização. `ApprovalService` continua sendo o gate humano final.
- Somente `PENDING_APPROVAL` é roteável e elegível à fila.
- `DENIED_POLICY` nunca recebe assignment nem queue item.
- Route key exata: `(system, capability)`.
- Sem wildcard, prefix, fuzzy ou fallback.
- Assignment idêntico é idempotente. Assignment incompatível para o mesmo request falha fechado.
- Store de assignment usa `RLock` para check e write atômicos.
- Fila é derivada. Não guarda state duplicado.
- Domínios não CDM são demonstrativos e não possuem adapters externos.

## Task 1. Contratos de routing e registry fail-closed

**Create:**

```text
src/ai_service_desk/engine/routing.py
tests/engine/test_routing_registry.py
```

**RED:** criar testes para imports ausentes e depois para:

```text
RoutingRule frozen
RoutingAssignment frozen
regra inválida -> ROUTING_RULE_INVALID
rota duplicada -> ROUTING_RULE_CONFLICT
técnico ausente/sem capability -> ROUTING_TECHNICIAN_NOT_AUTHORIZED
resolve exato
rota ausente -> ROUTE_NOT_FOUND
sem wildcard/prefix/fuzzy
```

Run:

```text
python -m pytest tests/engine/test_routing_registry.py -q
```

Expected RED antes da implementação.

**GREEN:** implementar `Phase10RoutingError`, erros tipados, validação simbólica e `RoutingRegistry` em duas passagens. Usar `authorization_registry.require_capability(rule.technician, rule.capability)` durante a validação completa antes da indexação.

Commit esperado:

```text
feat: add fail-closed routing registry
```

## Task 2. Assignment store idempotente e concorrente

**Modify:** `src/ai_service_desk/engine/routing.py`

**Create:** `tests/engine/test_routing_assignment_store.py`

**RED:** testar:

```text
primeiro assignment grava
repetição idêntica retorna o existente
snapshot possui uma única entrada
mesmo request com assignment incompatível -> ROUTING_ASSIGNMENT_CONFLICT
get ausente -> ROUTING_ASSIGNMENT_NOT_FOUND
entrada inválida -> ROUTING_ASSIGNMENT_INVALID
snapshot tuple e ordem determinística
```

Adicionar RED concorrente com duas threads e `Barrier`:

```text
mesmo request + mesmo assignment -> uma entrada
mesmo request + dois destinos -> um vencedor e um conflito
```

**GREEN:** implementar `InMemoryRoutingAssignmentStore` com um único `RLock` envolvendo lookup, comparação e escrita.

Commit:

```text
feat: add idempotent routing assignment store
```

## Task 3. RoutingService

**Modify:** `src/ai_service_desk/engine/routing.py`

**Create:** `tests/engine/test_routing_service.py`

**RED:** cobrir:

```text
PENDING_APPROVAL + rota válida -> assignment
route repetido -> mesmo assignment
DENIED_POLICY -> ROUTING_STATE_NOT_PENDING e zero assignment
APPROVED/REJECTED/EXECUTING/COMPLETED/FAILED/TRIAGED -> falha fechada
route inexistente -> ROUTE_NOT_FOUND e zero assignment
assignment conflitante -> falha fechada
```

**GREEN:** `RoutingService.route(record)` valida `AccessRequestRecord`, exige `PENDING_APPROVAL`, resolve regra exata, cria assignment e delega ao store.

Commit:

```text
feat: add phase 10 routing service
```

## Task 4. ApprovalQueue derivada

**Modify:** `src/ai_service_desk/engine/routing.py`

**Create:** `tests/engine/test_approval_queue.py`

**RED:** provar:

```text
PENDING_APPROVAL + assignment -> item presente
filtro por technician_id
aprovação -> item desaparece
rejeição -> item desaparece
DENIED_POLICY -> ausente
assignment sem request -> falha fechada
assignment divergente de system/capability -> ROUTING_QUEUE_INCONSISTENT
```

**GREEN:** fila percorre snapshot do assignment store, carrega record atual no `RequestRepository` e inclui apenas state `PENDING_APPROVAL`. Nenhuma cópia de state é persistida.

Commit:

```text
feat: add derived approval queue
```

## Task 5. Composição automática request para routing

**Modify:** `src/ai_service_desk/engine/routing.py`

**Create:** `tests/engine/test_routed_request_service.py`

**RED:** provar:

```text
SOLICITANTE CDM -> lifecycle PENDING_APPROVAL -> assignment automático -> fila
ADMIN CDM -> DENIED_POLICY -> zero assignment -> zero fila
PENDING_APPROVAL com rota ausente -> erro explícito, request permanece auditável e sem assignment
```

**GREEN:** implementar `RoutedRequestService.create_request(context)` compondo apenas `RequestLifecycleService` e `RoutingService`.

Commit:

```text
feat: compose request creation with routing
```

## Task 6. Domínios demonstrativos e segurança de autorização

**Create:** `tests/engine/test_phase10_domains.py`

**RED/GREEN por configuração:** usar os contratos já implementados para provar cinco rotas distintas:

```text
CDM -> TECH-CDM
HARDWARE -> TECH-HARDWARE
POWER_BI -> TECH-BI
MICROSOFT_365 -> TECH-M365
ERP -> TECH-ERP
```

Nenhum `AccessRequestContext` sintético não CDM será forçado pelo lifecycle. A demonstração desses domínios ocorre diretamente no registry/resolver.

Também provar:

```text
routing para TECH-CDM não permite aprovação por outro técnico sem CDM_ACCESS_REQUEST
ApprovalService continua emitindo TECHNICIAN_CAPABILITY_REQUIRED
```

Commit:

```text
test: prove distinct routing domains and authorization boundary
```

## Task 7. Phase 10 security invariants

**Create:** `tests/engine/test_phase10_security.py`

Testes obrigatórios:

```text
12 protected Git blobs exatos por git rev-parse HEAD:<path>
REQUEST_STATES continua com oito estados exatos
ALLOWED_TRANSITIONS continua com oito transições exatas
routing.py sem requests/urllib/http.client/socket
routing.py sem imports de integrations.cdm, integrations.cdm_fake_api, engine.cdm_execution
routing não chama HTTP/CDM em runtime monkeypatchado
DENIED_POLICY zero assignment e zero fila
rota duplicada falha fechada
rota desconhecida falha fechada
configuração de técnico incompatível falha fechada
routing não altera context, creation_policy, latest_policy ou confidence
```

Commit:

```text
test: lock phase 10 routing security boundaries
```

## Task 8. Smoke oficial de oito casos

**Create:**

```text
src/ai_service_desk/engine/routing_escalation_smoke.py
tests/engine/test_routing_escalation_smoke.py
```

Casos exatos:

```text
CDM_ALLOWED_PENDING_AND_QUEUED
IDEMPOTENT_ROUTING
DENIED_POLICY_OUTSIDE_QUEUE
UNKNOWN_ROUTE_FAILS_CLOSED
INCOMPATIBLE_TECHNICIAN_CONFIG_REJECTED
DISTINCT_DOMAIN_OWNERS
QUEUE_ITEM_LEAVES_AFTER_DECISION
AUTHORIZATION_REMAINS_FINAL_GATE
```

Report permitido:

```text
ok
case_count
cases[].case_id
cases[].ok
cases[].expected
cases[].actual
```

Sem identity corporativa, purpose, tokens ou dados livres.

Run:

```text
python -m pytest tests/engine/test_routing_escalation_smoke.py -q
```

Commit:

```text
test: add phase 10 routing escalation smoke
```

## Task 9. CLI aditivo

**Create:**

```text
src/ai_service_desk/phase10_cli.py
tests/test_phase10_cli.py
```

**Modify:**

```text
src/ai_service_desk/__main__.py
```

Parser aceita:

```text
routing-escalation-smoke
```

Stdout de sucesso:

```text
ROUTING ESCALATION SMOKE OK
Casos sinteticos: 8
```

O handler da Fase 10 deve ser avaliado antes do handler da Fase 9 e do CLI legado. Ele não constrói Ollama e não exige token CDM.

Commit:

```text
feat: expose phase 10 routing smoke cli
```

## Task 10. Workflow dedicado e gates

**Create:**

```text
.github/workflows/phase10-routing-escalation.yml
```

**Modify:**

```text
tests/test_workflows.py
```

Workflow `pull_request`, `fetch-depth: 0`, Python `3.14`, Ruff `0.12.12`, `PYTHONPATH=src`.

Steps obrigatórios:

```text
Ruff lint
Ruff format --check
historical node ID preservation from e5d0e3cc...
full pytest
protected blob verification
Phase 8 security
Phase 9 security
Phase 10 security
Phase 10 routing smoke
working tree clean
```

O script histórico compara conjuntos reais e imprime:

```text
historical_node_ids=786
candidate_node_ids=<n>
missing_historical_node_ids=0
new_node_ids=<n>
```

Commit:

```text
ci: add phase 10 routing gates
```

## Final gates

Congelar um único candidate SHA e executar no mesmo SHA:

```text
python --version
python -m ruff --version
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m pytest tests/engine/test_phase8_security.py -q
python -m pytest tests/engine/test_phase9_security.py -q
python -m pytest tests/engine/test_phase10_security.py -q
python -m ai_service_desk routing-escalation-smoke
python -m pytest --collect-only -q
```

E provar:

```text
Python = 3.14.x
Ruff = 0.12.12
historical = 786
missing = 0
new = real set difference
protected blobs = exact
Phase 8 invariants = PASS
Phase 9 invariants = PASS
Phase 10 security = PASS
DENIED_POLICY queue count = 0
routing smoke = PASS 8/8
no new external integration
working tree = clean
```

Qualquer correção após o candidate gera novo SHA e reinicia todos os gates.

Depois dos gates, publicar branch, abrir Draft PR `Phase 10: routing and escalation`, verificar hosted CI e workflow da Fase 10 no mesmo head SHA, atualizar o PR com evidência final e não fazer merge.