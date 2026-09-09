# Fase 8: Aprovação e execução controlada

## 1. Objetivo

A Fase 8 introduz a primeira camada stateful do fluxo operacional do AI Service Desk. Ela recebe o `AccessRequestContext` determinístico da Fase 7, cria um registro interno auditável, submete somente solicitações permitidas à decisão humana, controla a máquina de estados e executa apenas por meio de um executor fake em memória.

A fase congela estes componentes de domínio:

```text
RequestLifecycleService
AccessRequestRecord
request_id
version / optimistic concurrency
RequestRepository
InMemoryRequestRepository
TechnicianIdentity
TechnicianAuthorizationRegistry
ApprovalService
AuditEvent append-only
ExecutionEngine
ActionExecutor
FakeActionExecutor
```

A Fase 8 não integra o CDM. A fronteira externa continua fechada. Não existe HTTP, `CDMAdapter`, API fake do CDM, persistência real, banco, routing, frontend, LLM ou retry de execução.

## 2. Baseline e fontes canônicas

Baseline obrigatório desta spec:

```text
main = 2f583b5b4921cd7b40ddde2978a2852ecca2251d
historical tests = 426 node IDs
```

Fontes canônicas herdadas:

```text
docs/roadmap.md
docs/architecture/2026-09-08-policy-execution-cdm-handoff.md
docs/superpowers/specs/2026-09-08-phase-7-policy-engine-design.md
```

A Fase 8 reutiliza diretamente os contratos homologados da Fase 7:

```text
AccessRequestContext
SessionIdentity
PolicyDecision
PolicyEngine.evaluate(...)
ConfidenceAssessment
assess_confidence(...)
```

Os seguintes arquivos são protegidos e não podem ser alterados pela implementação da Fase 8, salvo bloqueio técnico reproduzível e revisão explícita posterior:

```text
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/confidence.py
```

A Fase 8 deve adaptar-se aos contratos existentes. Ela não cria uma segunda policy, uma segunda representação de contexto ou uma segunda regra de confidence.

## 3. Escopo arquitetural

### 3.1 Reuso

A fase reutiliza:

- `AccessRequestContext` como snapshot completo do pedido preparado na Fase 7;
- `PolicyEngine.evaluate(context)` como única decisão de policy para criação e revalidação;
- `PolicyDecision.decision` com os únicos valores existentes `REQUIRE_APPROVAL` e `DENY`;
- `assess_confidence(context)` para preservar a avaliação contextual sem permitir que confidence altere autorização;
- `context.capability` como capability exigida do técnico;
- provenance já congelada no `AccessRequestContext`, incluindo `knowledge_id`, `playbook_id`, `playbook_version` e `step_id`.

### 3.2 Criação

A fase cria, conceitualmente, módulos novos para:

```text
request_lifecycle.py
request_repository.py
technician_authorization.py
approval.py
execution.py
```

A separação física final pode respeitar convenções do repositório, mas as responsabilidades descritas nesta spec não podem ser fundidas de modo a remover as fronteiras entre lifecycle, autorização humana, policy e execução.

### 3.3 Impacto

A Fase 8 impacta somente o domínio interno e seus testes/smoke futuros. Não há alteração de UI, API HTTP, banco, autenticação externa, CDM ou roteamento.

## 4. Fluxo completo da Fase 8

```text
AccessRequestContext da Fase 7
        ↓
RequestLifecycleService.create_request(...)
        ↓
validate_access_request_context(...)
        ↓
PolicyEngine.evaluate(...)
        ↓
assess_confidence(...)
        ↓
AccessRequestRecord TRIAGED, version=1
        ↓
        ├── PolicyDecision.DENY
        │       ↓
        │   DENIED_POLICY, version=2
        │
        └── PolicyDecision.REQUIRE_APPROVAL
                ↓
          PENDING_APPROVAL, version=2
                ↓
          ApprovalService
          ├── reject(...) -> REJECTED
          └── approve(...) -> APPROVED
                                  ↓
                            ExecutionEngine.execute(...)
                                  ↓
                            PolicyEngine.evaluate(...)
                                  ↓
                     ┌────────────┴────────────┐
                     │                         │
                   DENY                 REQUIRE_APPROVAL
                     │                         │
                     ↓                         ↓
               DENIED_POLICY             EXECUTING
               zero executor calls            ↓
                                        ActionExecutor
                                         /          \
                                      success      failure/exception
                                        ↓              ↓
                                    COMPLETED         FAILED
```

Invariantes estruturais:

- criação de request sempre reavalia policy;
- o `PolicyDecision` que eventualmente existia antes da Fase 8 não é aceito como autoridade para criação;
- `DENY` cria registro `DENIED_POLICY` auditável;
- `REQUIRE_APPROVAL` cria pendência humana;
- aprovação nunca chama executor;
- execução só começa a partir de `APPROVED`;
- policy é revalidada imediatamente antes da transição para `EXECUTING`;
- `DENY` na revalidação impede qualquer chamada ao executor;
- confidence é armazenada para contexto e auditoria, mas nunca altera policy, aprovação ou execução.

## 5. Estados congelados

O conjunto completo de estados da Fase 8 é exatamente:

```text
TRIAGED
PENDING_APPROVAL
APPROVED
REJECTED
DENIED_POLICY
EXECUTING
COMPLETED
FAILED
```

Nenhum estado adicional deve ser introduzido sem revisão da spec.

Estados terminais na Fase 8:

```text
REJECTED
DENIED_POLICY
COMPLETED
FAILED
```

`FAILED` é terminal nesta fase. Não existe retry, requeue, reset para `APPROVED` ou transição de volta para `EXECUTING`.

## 6. Matriz fechada de transições

As únicas transições permitidas entre estados existentes são:

```text
TRIAGED -> PENDING_APPROVAL
TRIAGED -> DENIED_POLICY
PENDING_APPROVAL -> APPROVED
PENDING_APPROVAL -> REJECTED
APPROVED -> EXECUTING
APPROVED -> DENIED_POLICY
EXECUTING -> COMPLETED
EXECUTING -> FAILED
```

Tabela normativa:

| origem | destino | responsável | condição |
| --- | --- | --- | --- |
| `TRIAGED` | `PENDING_APPROVAL` | `RequestLifecycleService` | policy de criação = `REQUIRE_APPROVAL` |
| `TRIAGED` | `DENIED_POLICY` | `RequestLifecycleService` | policy de criação = `DENY` |
| `PENDING_APPROVAL` | `APPROVED` | `ApprovalService` | técnico autorizado, não requester, versão válida |
| `PENDING_APPROVAL` | `REJECTED` | `ApprovalService` | técnico autorizado, não requester, versão válida |
| `APPROVED` | `EXECUTING` | `ExecutionEngine` | revalidation = `REQUIRE_APPROVAL`, CAS bem-sucedido |
| `APPROVED` | `DENIED_POLICY` | `ExecutionEngine` | revalidation = `DENY` |
| `EXECUTING` | `COMPLETED` | `ExecutionEngine` | executor retorna sucesso |
| `EXECUTING` | `FAILED` | `ExecutionEngine` | executor retorna falha, resultado inválido ou lança exceção capturada |

A criação inicial de um objeto em `TRIAGED` não é uma transição entre estados existentes. É a inicialização do lifecycle.

Qualquer tentativa de transição fora da matriz falha com erro explícito de domínio e não modifica registro, versão ou executor.

Não existem transições como:

```text
DENIED_POLICY -> APPROVED
DENIED_POLICY -> PENDING_APPROVAL
REJECTED -> APPROVED
FAILED -> EXECUTING
COMPLETED -> EXECUTING
PENDING_APPROVAL -> EXECUTING
TRIAGED -> APPROVED
```

## 7. AccessRequestRecord

`AccessRequestRecord` é o snapshot stateful da solicitação interna.

Contrato conceitual mínimo:

```python
@dataclass(frozen=True)
class AccessRequestRecord:
    request_id: str
    version: int
    state: RequestState
    context: AccessRequestContext
    creation_policy: PolicyDecision
    latest_policy: PolicyDecision
    confidence: ConfidenceAssessment
    created_at: datetime
    updated_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    execution_started_at: datetime | None
    execution_finished_at: datetime | None
    execution_result_code: str | None
    execution_error_code: str | None
```

Regras obrigatórias:

- o record é imutável em memória; atualizações produzem novo objeto;
- `request_id` nunca muda;
- `context` nunca muda depois da criação;
- `creation_policy` nunca muda;
- `confidence` nunca muda depois da criação;
- `created_at` nunca muda;
- `latest_policy` começa igual a `creation_policy` e só pode ser substituída pela policy revalidada antes da execução;
- `version` começa em `1` no `TRIAGED` inicial;
- toda transição persistida incrementa `version` exatamente em `+1`;
- `updated_at` muda em toda transição persistida;
- `decided_by` e `decided_at` permanecem `None` até aprovação ou rejeição humana;
- `decided_by` guarda o `technician_id` confiável que decidiu;
- em `APPROVED -> DENIED_POLICY` os campos de decisão humana permanecem preservados, pois a aprovação existiu historicamente;
- `execution_started_at` só é preenchido ao entrar em `EXECUTING`;
- `execution_finished_at` só é preenchido ao entrar em `COMPLETED` ou `FAILED`;
- `execution_error_code` só é preenchido em `FAILED`;
- `execution_result_code` pode registrar um código seguro do executor em `COMPLETED` ou `FAILED`.

A implementação deve validar coerência entre estado e campos opcionais. Exemplos:

```text
PENDING_APPROVAL + decided_by preenchido -> inválido
APPROVED + decided_by ausente -> inválido
EXECUTING + execution_started_at ausente -> inválido
COMPLETED + execution_finished_at ausente -> inválido
FAILED + execution_error_code ausente -> inválido
DENIED_POLICY criado diretamente + decided_by preenchido -> inválido
```

## 8. request_id determinístico

Na `InMemoryRequestRepository`, o `request_id` é determinístico e monotônico por instância do repositório:

```text
REQ-000001
REQ-000002
REQ-000003
```

Regras:

- não usar UUID;
- não usar timestamp;
- não usar hash de identidade;
- não usar email ou username no ID;
- a sequência começa em `1` em cada nova instância do repositório;
- a alocação é protegida pela mesma exclusão mútua usada pelas operações de repositório;
- a Fase 8 não promete estabilidade do contador após restart, porque o repositório é somente em memória.

O `request_id` não é fornecido pelo caller.

## 9. AuditEvent append-only

`AuditEvent` é um registro imutável de lifecycle. O repositório mantém eventos em ordem de append e nunca expõe operação de update ou delete.

Contrato conceitual mínimo:

```python
@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    event_type: str
    actor_type: Literal["SYSTEM", "TECHNICIAN"]
    actor_id: str
    from_state: RequestState | None
    to_state: RequestState
    record_version: int
    reason_code: str
    policy_id: str | None
    occurred_at: datetime
```

Eventos canônicos da Fase 8:

```text
REQUEST_CREATED
POLICY_REQUIRES_APPROVAL
POLICY_DENIED_AT_CREATION
REQUEST_APPROVED
REQUEST_REJECTED
POLICY_DENIED_BEFORE_EXECUTION
EXECUTION_STARTED
EXECUTION_COMPLETED
EXECUTION_FAILED
```

Semântica:

- `REQUEST_CREATED` registra `from_state=None`, `to_state=TRIAGED`, `record_version=1`;
- eventos de policy armazenam o `policy_id` correspondente;
- `REQUEST_APPROVED` e `REQUEST_REJECTED` usam `actor_type=TECHNICIAN` e `actor_id=technician_id`;
- eventos automáticos usam `actor_type=SYSTEM` e `actor_id=SYSTEM`;
- `EXECUTION_STARTED` prova que a revalidação permitiu prosseguir e que o estado foi persistido antes da chamada ao executor;
- `EXECUTION_FAILED` usa apenas código seguro, nunca mensagem bruta de exceção.

O `reason_code` de eventos de policy deve reutilizar o `PolicyDecision.reason_code` real. Códigos de lifecycle e executor são valores simbólicos estáveis definidos pela Fase 8.

A auditoria não duplica `purpose`, email, nome ou texto livre do request em cada evento. Esses dados já existem no snapshot do record. A auditoria também não persiste traceback, `repr(exception)` ou mensagem bruta de exceção.

## 10. RequestRepository

`RequestRepository` é a fronteira de armazenamento da Fase 8.

Interface conceitual:

```python
class RequestRepository(Protocol):
    def allocate_request_id(self) -> str: ...

    def create(
        self,
        record: AccessRequestRecord,
        *,
        audit_events: tuple[AuditEvent, ...],
    ) -> AccessRequestRecord: ...

    def get(self, request_id: str) -> AccessRequestRecord: ...

    def save(
        self,
        record: AccessRequestRecord,
        *,
        expected_version: int,
        audit_events: tuple[AuditEvent, ...],
    ) -> AccessRequestRecord: ...

    def audit_for(self, request_id: str) -> tuple[AuditEvent, ...]: ...
```

Não existem APIs de delete de request ou audit na Fase 8.

`audit_for(...)` retorna snapshot imutável, nunca a lista interna mutável.

## 11. InMemoryRequestRepository

`InMemoryRequestRepository` é a única implementação de repository da Fase 8.

Características obrigatórias:

- armazenamento em estruturas Python em memória;
- sem arquivo JSON persistente;
- sem SQLite;
- sem banco;
- sem cache externo;
- sem rede;
- exclusão mútua local para alocação de ID e compare-and-swap;
- cópias/snapshots imutáveis para leitura;
- audit trail append-only.

Na criação:

- `request_id` deve ser novo;
- `version` deve ser `1`;
- `state` deve ser `TRIAGED`;
- o evento `REQUEST_CREATED` deve corresponder ao mesmo `request_id` e `record_version=1`;
- record e evento são gravados na mesma seção crítica.

Em `save(...)`:

- o record existente deve existir;
- `expected_version` deve ser exatamente igual à versão atualmente armazenada;
- o novo record deve ter `version == expected_version + 1`;
- `request_id`, `context`, `creation_policy`, `confidence` e `created_at` devem ser iguais aos valores originais;
- todos os `AuditEvent` recebidos são validados antes da mutação;
- cada evento deve apontar para o mesmo `request_id` e para a nova `record_version` quando representa a transição;
- a atualização do record e o append dos eventos ocorrem atomicamente sob o lock;
- em qualquer erro de validação ou concorrência, não há escrita parcial.

## 12. Optimistic concurrency e version

Toda mutação depois da criação usa optimistic concurrency.

Contrato:

```text
caller leu version = N
caller solicita operação com expected_version = N
repository confirma current.version == N
nova versão persistida = N + 1
```

Se `current.version != expected_version`:

```text
ConcurrencyConflictError
reason_code = VERSION_CONFLICT
```

Consequências obrigatórias:

- stale approval não sobrescreve decisão mais nova;
- stale rejection não sobrescreve aprovação;
- duas execuções concorrentes não podem chamar o executor duas vezes;
- somente o caller que conseguir persistir `APPROVED -> EXECUTING` pode chamar `ActionExecutor`;
- o loser do compare-and-swap recebe `VERSION_CONFLICT` e faz zero chamadas ao executor;
- conflito não gera retry automático.

A Fase 8 não implementa locking distribuído. O CAS é local ao `InMemoryRequestRepository`.

## 13. RequestLifecycleService

`RequestLifecycleService` é o dono da criação do request e da matriz de transições.

Dependências:

```text
RequestRepository
PolicyEngine
clock timezone-aware
```

`assess_confidence(...)` é chamado durante a criação para congelar a avaliação contextual do request, sem participar de autorização.

Interface pública de criação:

```python
create_request(context: AccessRequestContext) -> AccessRequestRecord
```

Fluxo normativo:

1. validar `AccessRequestContext` pelo contrato já existente;
2. chamar `PolicyEngine.evaluate(context)` novamente;
3. chamar `assess_confidence(context)` separadamente;
4. somente após avaliações válidas, alocar `request_id`;
5. criar `AccessRequestRecord` em `TRIAGED`, `version=1`;
6. persistir `REQUEST_CREATED`;
7. se policy = `DENY`, aplicar `TRIAGED -> DENIED_POLICY`;
8. se policy = `REQUIRE_APPROVAL`, aplicar `TRIAGED -> PENDING_APPROVAL`;
9. retornar o record já em `DENIED_POLICY` ou `PENDING_APPROVAL`, normalmente em `version=2`.

A criação não aceita um `PolicyDecision` fornecido pelo caller como autoridade. Mesmo que um fluxo anterior tenha policy homologada, a Fase 8 reavalia com o `PolicyEngine` corrente.

Se a avaliação retorna `DENY`:

```text
record deve existir
state = DENIED_POLICY
executor calls = 0
nenhuma ação de approval permitida
audit contém REQUEST_CREATED + POLICY_DENIED_AT_CREATION
```

Se retorna `REQUIRE_APPROVAL`:

```text
record deve existir
state = PENDING_APPROVAL
executor calls = 0
audit contém REQUEST_CREATED + POLICY_REQUIRES_APPROVAL
```

Se validação de contexto ou construção/configuração do `PolicyEngine` falha antes de existir `PolicyDecision`, a criação falha como erro de domínio e não inventa um `DENY` sintético. O executor continua inacessível.

### 13.1 Dono das transições

A matriz da seção 6 é centralizada pelo `RequestLifecycleService`. `ApprovalService` e `ExecutionEngine` não duplicam a tabela de transições.

O mecanismo interno de transition recebe record atual, destino, `expected_version`, timestamp, alterações permitidas e eventos. Ele:

1. confirma que `(from_state, to_state)` existe na matriz;
2. constrói o novo record imutável com `version + 1`;
3. valida coerência do record;
4. delega o CAS atômico ao repository;
5. retorna somente o record efetivamente persistido.

Não deve existir uma API externa genérica que permita ao frontend ou a um caller futuro enviar livremente `to_state=APPROVED`. Os entrypoints de decisão continuam sendo `ApprovalService` e `ExecutionEngine`.

## 14. TechnicianIdentity

`TechnicianIdentity` representa o técnico autenticado/simulado pelo ambiente hospedeiro para ações humanas da Fase 8.

Contrato conceitual:

```python
@dataclass(frozen=True)
class TechnicianIdentity:
    technician_id: str
    username: str
    name: str
    email: str
```

Todos os campos são obrigatórios, textuais e não vazios.

A Fase 8 não cria login, senha, token de usuário ou sistema paralelo de autenticação.

`TechnicianIdentity` não é derivado da conversa do requester.

## 15. TechnicianAuthorizationRegistry

`TechnicianAuthorizationRegistry` mantém, em memória, a configuração explícita de quais capabilities cada técnico pode decidir.

Responsabilidades:

- armazenar identidade canônica por `technician_id`;
- armazenar conjunto explícito de capabilities por técnico;
- validar configuração em runtime;
- confirmar que a identidade apresentada corresponde à identidade registrada;
- responder autorização somente para a capability exata do request.

Interface conceitual:

```python
require_capability(
    technician: TechnicianIdentity,
    capability: str,
) -> None
```

Se o técnico não estiver registrado, sua identidade divergir da entrada canônica ou não possuir a capability:

```text
TechnicianAuthorizationError
reason_code = TECHNICIAN_CAPABILITY_REQUIRED
```

Não existe wildcard `*`, prefix match, fuzzy match ou herança implícita de capabilities na Fase 8.

O registry não escolhe técnico e não faz routing. O caller fornece o `TechnicianIdentity`. Seleção automática de responsável pertence à Fase 10.

## 16. Regra de self-decision

O requester nunca pode decidir o próprio request.

A regra vale para:

```text
approve
reject
```

Comparação determinística:

- `technician.username.strip().casefold()` contra `record.context.requester.username.strip().casefold()`;
- `technician.email.strip().casefold()` contra `record.context.requester.email.strip().casefold()`.

Se qualquer um dos dois identificadores coincidir:

```text
SelfDecisionError
reason_code = SELF_DECISION_NOT_ALLOWED
```

A operação:

- não muda state;
- não incrementa version;
- não chama executor;
- não produz aprovação ou rejeição.

Não existe exceção baseada em cargo, área, confidence ou capability.

## 17. ApprovalService

`ApprovalService` é o único entrypoint humano para decisão da pendência na Fase 8.

Dependências:

```text
RequestRepository
RequestLifecycleService
TechnicianAuthorizationRegistry
clock timezone-aware
```

O `ApprovalService` não recebe `ActionExecutor` e não recebe `ExecutionEngine` como dependência. Essa separação torna estrutural a regra `approve não executa`.

Interfaces:

```python
approve(
    request_id: str,
    technician: TechnicianIdentity,
    *,
    expected_version: int,
) -> AccessRequestRecord

reject(
    request_id: str,
    technician: TechnicianIdentity,
    *,
    expected_version: int,
) -> AccessRequestRecord
```

Sequência normativa de decisão:

1. carregar request;
2. exigir `state == PENDING_APPROVAL`;
3. exigir `technician` válido no registry;
4. exigir `record.context.capability` no conjunto autorizado do técnico;
5. bloquear self-decision;
6. aplicar transição com CAS;
7. preencher `decided_by=technician.technician_id`;
8. preencher `decided_at` timezone-aware;
9. append audit atômico com a transição.

`approve(...)`:

```text
PENDING_APPROVAL -> APPROVED
reason_code = APPROVED_BY_AUTHORIZED_TECHNICIAN
```

`reject(...)`:

```text
PENDING_APPROVAL -> REJECTED
reason_code = REJECTED_BY_AUTHORIZED_TECHNICIAN
```

Nenhum dos dois métodos chama executor.

### 17.1 DENIED_POLICY nunca é aprovável

Uma chamada de `approve(...)` ou `reject(...)` sobre `DENIED_POLICY` falha por estado inválido antes de qualquer tentativa de transição.

Resultado obrigatório:

```text
state permanece DENIED_POLICY
version permanece igual
executor calls = 0
```

## 18. ActionExecutor

`ActionExecutor` é a seam de execução da Fase 8 e da futura Fase 9.

Interface conceitual:

```python
class ActionExecutor(Protocol):
    def execute(self, request: AccessRequestRecord) -> ActionExecutionResult: ...
```

O request recebido pelo executor deve estar em `EXECUTING`.

Resultado conceitual mínimo:

```python
@dataclass(frozen=True)
class ActionExecutionResult:
    success: bool
    result_code: str
```

`result_code` é um código de máquina seguro. Não é corpo HTTP, traceback ou mensagem livre de exceção.

A Fase 8 não cria uma implementação real de integração. `ActionExecutor` não contém semântica CDM específica.

## 19. FakeActionExecutor

`FakeActionExecutor` é a única implementação concreta de executor da Fase 8.

Propriedades:

- totalmente em memória;
- determinístico;
- configurável para sucesso, falha ou exceção sintética;
- mantém contagem e sequência de chamadas para testes;
- não usa HTTP;
- não usa `requests`;
- não usa `httpx`;
- não usa subprocess;
- não usa shell;
- não usa Ollama;
- não usa `CDMAdapter`;
- não escreve arquivo persistente.

Códigos seguros mínimos:

```text
FAKE_EXECUTION_SUCCEEDED
FAKE_EXECUTION_FAILED
EXECUTOR_EXCEPTION
EXECUTOR_INVALID_RESULT
```

Para uma exceção sintética, o fake pode lançar `Exception` durante o teste. `ExecutionEngine` é responsável por capturá-la e convertê-la em `FAILED / EXECUTOR_EXCEPTION` sem persistir texto bruto da exceção.

## 20. ExecutionEngine

`ExecutionEngine` orquestra revalidação e chamada ao executor.

Dependências:

```text
RequestRepository
RequestLifecycleService
PolicyEngine
ActionExecutor
clock timezone-aware
```

Interface:

```python
execute(
    request_id: str,
    *,
    expected_version: int,
) -> AccessRequestRecord
```

### 20.1 Gate de estado

A execução só aceita:

```text
state == APPROVED
```

Qualquer outro estado falha antes de revalidação operacional ou executor.

Em particular:

```text
TRIAGED -> não executa
PENDING_APPROVAL -> não executa
REJECTED -> não executa
DENIED_POLICY -> não executa
EXECUTING -> não inicia segunda execução
COMPLETED -> não executa novamente
FAILED -> não possui retry
```

### 20.2 Revalidação obrigatória

Depois de carregar o record `APPROVED` e antes de chamar o executor:

```python
policy = PolicyEngine.evaluate(record.context)
```

A revalidação usa exatamente o `AccessRequestContext` preservado no record. Ela não busca novamente playbook, knowledge ou triage e não reconstrói provenance a partir do estado corrente do corpus.

Se a policy revalidada for `DENY`:

```text
APPROVED -> DENIED_POLICY
latest_policy = policy revalidada
executor calls = 0
```

Audit obrigatório:

```text
event_type = POLICY_DENIED_BEFORE_EXECUTION
reason_code = PolicyDecision.reason_code
policy_id = PolicyDecision.policy_id
```

Se a policy revalidada for `REQUIRE_APPROVAL`:

1. atualizar `latest_policy`;
2. aplicar CAS `APPROVED -> EXECUTING`;
3. preencher `execution_started_at`;
4. persistir `EXECUTION_STARTED`;
5. somente após sucesso do CAS chamar `ActionExecutor.execute(...)` exatamente uma vez.

O evento `EXECUTION_STARTED` reutiliza o `policy_id` e `reason_code` da revalidação, provando que policy foi verificada antes da chamada ao executor.

### 20.3 Sucesso

Se o executor retorna resultado válido com `success=True`:

```text
EXECUTING -> COMPLETED
execution_result_code = result.result_code
execution_error_code = None
execution_finished_at = timestamp timezone-aware
```

Audit:

```text
event_type = EXECUTION_COMPLETED
reason_code = result.result_code
```

### 20.4 Falha retornada

Se o executor retorna resultado válido com `success=False`:

```text
EXECUTING -> FAILED
execution_result_code = result.result_code
execution_error_code = result.result_code
execution_finished_at = timestamp timezone-aware
```

Audit:

```text
event_type = EXECUTION_FAILED
reason_code = result.result_code
```

### 20.5 Resultado inválido

Se o executor retorna objeto fora do contrato `ActionExecutionResult` ou `result_code` inválido:

```text
EXECUTING -> FAILED
execution_error_code = EXECUTOR_INVALID_RESULT
```

Nenhum dado arbitrário retornado pelo executor é persistido.

### 20.6 Exceção

Se `ActionExecutor.execute(...)` lança `Exception`:

```text
EXECUTING -> FAILED
execution_error_code = EXECUTOR_EXCEPTION
```

Regras:

- capturar `Exception`, não `BaseException`;
- não persistir mensagem da exceção;
- não persistir traceback;
- não usar nome da classe da exceção como código;
- audit usa somente `EXECUTOR_EXCEPTION`;
- o método retorna o record `FAILED` após persistir o resultado seguro.

## 21. Zero executor calls em caminhos bloqueados

A contagem do `FakeActionExecutor` deve permanecer zero quando:

```text
request creation -> DENY
request state != APPROVED
DENIED_POLICY recebe approve/reject
technician sem capability
self-decision
VERSION_CONFLICT antes de EXECUTING
policy revalidation -> DENY
```

A única fronteira que autoriza a chamada é:

```text
APPROVED
+
expected_version vigente
+
PolicyEngine.evaluate(...) = REQUIRE_APPROVAL
+
CAS APPROVED -> EXECUTING persistido com sucesso
```

Só depois desses quatro gates o executor é chamado.

## 22. Timestamps timezone-aware

Todos os timestamps persistidos ou auditados são timezone-aware.

Campos afetados:

```text
created_at
updated_at
decided_at
execution_started_at
execution_finished_at
AuditEvent.occurred_at
```

Condição mínima:

```python
timestamp.tzinfo is not None
timestamp.utcoffset() is not None
```

O default de runtime deve usar UTC timezone-aware. Testes podem injetar uma função de clock determinística. A função de clock é dependência técnica, não uma nova fonte de decisão de negócio.

Datetime naive é erro de domínio e não pode ser persistido.

## 23. Erros de domínio e reason codes

A Fase 8 deve usar erros explícitos e códigos estáveis. Conjunto mínimo:

```text
REQUEST_NOT_FOUND
INVALID_STATE_TRANSITION
VERSION_CONFLICT
TECHNICIAN_CAPABILITY_REQUIRED
SELF_DECISION_NOT_ALLOWED
AUDIT_EVENT_INVALID
RECORD_INVARIANT_INVALID
EXECUTOR_INVALID_RESULT
EXECUTOR_EXCEPTION
```

Semântica:

- `REQUEST_NOT_FOUND`: ID inexistente;
- `INVALID_STATE_TRANSITION`: origem/destino fora da matriz ou operação incompatível com state;
- `VERSION_CONFLICT`: optimistic concurrency falhou;
- `TECHNICIAN_CAPABILITY_REQUIRED`: técnico ausente, identidade divergente ou sem capability;
- `SELF_DECISION_NOT_ALLOWED`: requester tentou decidir o próprio request;
- `AUDIT_EVENT_INVALID`: evento não corresponde ao record/transição ou contém timestamp inválido;
- `RECORD_INVARIANT_INVALID`: record incoerente com seu state/campos;
- `EXECUTOR_INVALID_RESULT`: retorno do executor fora do contrato;
- `EXECUTOR_EXCEPTION`: exceção capturada com código seguro.

Erros de policy da Fase 7 permanecem pertencentes à Fase 7 e não são renomeados.

## 24. Ordem dos gates de segurança

### 24.1 Aprovação/rejeição

A ordem conceitual é:

```text
get request
-> state PENDING_APPROVAL
-> technician identity/capability
-> self-decision check
-> lifecycle transition
-> repository CAS
```

Nenhum gate anterior ao CAS produz executor call.

### 24.2 Execução

A ordem conceitual é:

```text
get request
-> state APPROVED
-> expected_version recebido
-> PolicyEngine.evaluate(context)
-> DENY ? DENIED_POLICY : continuar
-> lifecycle transition APPROVED -> EXECUTING com CAS
-> somente depois ActionExecutor.execute(...)
-> COMPLETED ou FAILED
```

A policy nunca é avaliada pelo executor.

## 25. Confidence permanece separado

A Fase 8 preserva `ConfidenceAssessment`, mas nenhuma destas interfaces aceita confidence como autorização:

```text
TechnicianAuthorizationRegistry.require_capability(...)
ApprovalService.approve(...)
ApprovalService.reject(...)
ExecutionEngine.execute(...)
PolicyEngine.evaluate(...)
```

Invariantes herdadas:

```text
SOLICITANTE + HIGH -> REQUIRE_APPROVAL
SOLICITANTE + LOW -> REQUIRE_APPROVAL
```

`HIGH` não remove aprovação humana.

`LOW` não bloqueia uma policy `REQUIRE_APPROVAL`.

## 26. Concorrência crítica

### 26.1 Dupla decisão humana

Dois técnicos leem:

```text
state = PENDING_APPROVAL
version = 2
```

Técnico A aprova com `expected_version=2`:

```text
APPROVED
version = 3
```

Técnico B tenta rejeitar com `expected_version=2`:

```text
VERSION_CONFLICT
record permanece APPROVED version=3
```

### 26.2 Dupla execução

Dois callers leem:

```text
state = APPROVED
version = N
```

Ambos revalidam policy como `REQUIRE_APPROVAL`. Somente um consegue persistir:

```text
APPROVED version=N
-> EXECUTING version=N+1
```

Somente esse caller chama o executor.

O segundo recebe `VERSION_CONFLICT` ou observa estado já não aprovável e faz zero executor calls.

Resultado obrigatório do cenário:

```text
total executor calls = 1
```

## 27. Auditoria mínima por fluxo

### 27.1 Permitido e concluído

```text
REQUEST_CREATED
POLICY_REQUIRES_APPROVAL
REQUEST_APPROVED
EXECUTION_STARTED
EXECUTION_COMPLETED
```

### 27.2 Permitido e rejeitado

```text
REQUEST_CREATED
POLICY_REQUIRES_APPROVAL
REQUEST_REJECTED
```

### 27.3 Negado na criação

```text
REQUEST_CREATED
POLICY_DENIED_AT_CREATION
```

### 27.4 Negado na revalidação

```text
REQUEST_CREATED
POLICY_REQUIRES_APPROVAL
REQUEST_APPROVED
POLICY_DENIED_BEFORE_EXECUTION
```

### 27.5 Executor falha

```text
REQUEST_CREATED
POLICY_REQUIRES_APPROVAL
REQUEST_APPROVED
EXECUTION_STARTED
EXECUTION_FAILED
```

Nenhum fluxo substitui, reordena ou apaga eventos anteriores.

## 28. Limites de segurança e zero execução externa

A Fase 8 não adiciona nem chama:

```text
HTTP
requests
httpx
urllib.request
CDMAdapter
CDM API
API fake do CDM
subprocess
shell
PowerShell
OllamaClient
LLM
embedding
SQLite
banco
arquivo JSON persistente
```

`FakeActionExecutor` executa apenas comportamento sintético em memória.

Nenhuma capability é derivada por LLM.

Nenhuma policy é derivada por LLM.

Nenhuma decisão humana é simulada automaticamente por confidence.

## 29. Fora do escopo

Fora do escopo explícito da Fase 8:

```text
HTTP
CDMAdapter
API fake do CDM
persistência real
SQLite
JSON persistente
banco
routing
frontend
LLM
retry de execução
```

Também ficam fora:

- service credential do CDM;
- idempotência externa do CDM;
- `external_id` real do CDM;
- consulta/criação de acesso em sistema externo;
- seleção automática de técnico;
- filas e telas de frontend;
- recuperação automática de `FAILED`.

## 30. Fronteira com a Fase 9

A Fase 9 implementará a integração CDM atrás da seam `ActionExecutor`.

A evolução esperada é:

```text
ExecutionEngine
    ↓
ActionExecutor
    ├── Fase 8: FakeActionExecutor
    └── Fase 9: executor de integração que usa CDMAdapter
```

A Fase 9 poderá adicionar:

```text
API local simulada do CDM
CDMAdapter
service credential
lookup de acesso
criação de acesso SOLICITANTE
idempotência externa
tratamento de HTTP
```

Ela não deve exigir alteração de `PolicyEngine`, de `AccessRequestContext` nem da máquina de estados básica da Fase 8 para simplesmente trocar o executor fake por uma implementação de integração.

## 31. Fronteira com a Fase 10

A Fase 10 é dona de routing e escalonamento.

Nesta fase:

- `TechnicianAuthorizationRegistry` responde se um técnico informado pode decidir a capability;
- o registry não escolhe técnico;
- não existe algoritmo `capability -> responsável`;
- não existe fila automática por técnico;
- não existe distribuição de workload.

A Fase 10 poderá construir routing sobre `context.capability` e `TechnicianIdentity` sem alterar a regra de autorização da Fase 8.

## 32. Matriz mínima de testes futuros da Fase 8

A implementação futura deve cobrir pelo menos:

1. criação `SOLICITANTE` com policy `REQUIRE_APPROVAL` -> `PENDING_APPROVAL`;
2. criação com policy `DENY` -> `DENIED_POLICY` auditável;
3. `DENIED_POLICY` não aceita approve;
4. `DENIED_POLICY` não aceita reject;
5. técnico sem capability não aprova;
6. técnico sem capability não rejeita;
7. técnico não registrado não decide;
8. identidade de técnico divergente do registry não decide;
9. requester com mesmo username do técnico não decide;
10. requester com mesmo email do técnico não decide;
11. comparação de self-decision é case-insensitive e ignora whitespace externo;
12. técnico autorizado aprova `PENDING_APPROVAL`;
13. técnico autorizado rejeita `PENDING_APPROVAL`;
14. approve não chama executor;
15. reject não chama executor;
16. execução em `PENDING_APPROVAL` falha;
17. execução em `DENIED_POLICY` falha;
18. execução em `REJECTED` falha;
19. execução em `COMPLETED` falha;
20. execução em `FAILED` falha e não oferece retry;
21. execução em `APPROVED` revalida policy antes do executor;
22. revalidation `DENY` -> `DENIED_POLICY`;
23. revalidation `DENY` -> zero executor calls;
24. revalidation `REQUIRE_APPROVAL` -> `APPROVED -> EXECUTING` antes da chamada;
25. executor success -> `COMPLETED`;
26. executor failure -> `FAILED`;
27. executor exception -> `FAILED / EXECUTOR_EXCEPTION`;
28. mensagem bruta da exception não aparece em record ou audit;
29. executor result inválido -> `FAILED / EXECUTOR_INVALID_RESULT`;
30. `FAILED` não executa novamente;
31. ID em memória começa em `REQ-000001`;
32. IDs subsequentes são determinísticos e monotônicos;
33. nova instância do repository reinicia sequência local em `REQ-000001`;
34. stale approval -> `VERSION_CONFLICT`;
35. stale rejection -> `VERSION_CONFLICT`;
36. dupla decisão concorrente preserva somente uma transição;
37. dupla execução concorrente produz exatamente uma chamada ao executor;
38. toda transição incrementa version em exatamente `+1`;
39. timestamps persistidos são timezone-aware;
40. datetime naive é rejeitado;
41. `audit_for` retorna tuple/snapshot não mutável;
42. audit antigo permanece prefixo lógico imutável após novas transições;
43. não existe API de delete/update de audit;
44. criação permitida possui `REQUEST_CREATED` e `POLICY_REQUIRES_APPROVAL`;
45. criação negada possui `REQUEST_CREATED` e `POLICY_DENIED_AT_CREATION`;
46. fluxo concluído possui ordem de eventos canônica;
47. fluxo falho possui `EXECUTION_STARTED` antes de `EXECUTION_FAILED`;
48. policy revalidada substitui somente `latest_policy`, preservando `creation_policy`;
49. `context` permanece idêntico em todas as versões;
50. confidence não altera policy nem execução;
51. `access_request.py` permanece byte-equivalent ao baseline;
52. `policy.py` permanece byte-equivalent ao baseline;
53. `confidence.py` permanece byte-equivalent ao baseline;
54. nenhum caminho da Fase 8 usa HTTP ou `CDMAdapter`;
55. nenhum caminho da Fase 8 usa LLM;
56. nenhum caminho da Fase 8 usa persistência real;
57. smoke sintético futuro prova os fluxos aprovado, rejeitado, negado, sucesso, falha e revalidation deny;
58. os 426 node IDs históricos continuam presentes.

Essa matriz é piso contratual, não orçamento final de quantidade de testes.

## 33. Baseline quantitativo

A implementação da Fase 8 parte obrigatoriamente de:

```text
historical node IDs = 426
```

Gate futuro de regressão deve provar por node ID, não apenas por contagem total:

```text
missing_historical_nodeids = 0
final_nodeids >= 426 + novos testes da Fase 8
```

É proibido satisfazer o baseline removendo, renomeando silenciosamente, desabilitando ou transformando testes históricos em skip.

## 34. Critérios de aceite futuros

A Fase 8 só poderá ser considerada concluída quando houver evidência de que:

- request creation reavalia policy;
- `DENY` cria `DENIED_POLICY` auditável;
- `DENIED_POLICY` nunca é aprovável;
- técnico precisa possuir exatamente a capability do request;
- requester não decide o próprio request;
- approve e reject são separados de execution;
- approve faz zero executor calls;
- execução exige `APPROVED`;
- policy é revalidada antes de qualquer executor call;
- revalidation `DENY` leva a `DENIED_POLICY`;
- revalidation `DENY` faz zero executor calls;
- executor success leva a `COMPLETED`;
- executor failure leva a `FAILED`;
- executor exception leva a `FAILED / EXECUTOR_EXCEPTION` sem texto bruto;
- `FAILED` não possui retry;
- audit é append-only;
- timestamps são timezone-aware;
- `InMemoryRequestRepository` é a única persistência da fase;
- `request_id` é determinístico no repository em memória;
- optimistic concurrency impede lost update;
- concorrência de execution produz no máximo uma executor call;
- os três arquivos protegidos da Fase 7 permanecem intactos;
- não há HTTP, `CDMAdapter`, API fake do CDM, persistência real, routing, frontend ou LLM;
- os 426 node IDs históricos são preservados.

## 35. Self-review obrigatório antes do plano

Antes de escrever qualquer plano de implementação, a spec aprovada deve ser revisada contra estes pontos:

```text
TODO ausente
TBD ausente
estados fechados
transições fechadas
autorização de técnico explícita
self-decision bloqueada em approve e reject
approve separado de execution
revalidação de policy anterior ao executor
revalidation DENY com zero executor calls
optimistic concurrency com expected_version
request_id determinístico
AuditEvent append-only
timestamps timezone-aware
FAILED terminal sem retry
arquivos protegidos intactos por contrato
Fase 9 restrita à integração CDM
Fase 10 restrita a routing/escalonamento
baseline de 426 node IDs explícito
```

A próxima etapa, somente após aprovação desta spec, é um plano TDD detalhado. Esta spec não implementa código e não materializa esse plano.
