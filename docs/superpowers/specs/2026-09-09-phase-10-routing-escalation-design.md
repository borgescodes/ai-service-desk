# Fase 10: Roteamento e escalonamento

## 1. Objetivo

A Fase 10 adiciona uma camada operacional determinística entre a criação da solicitação e a decisão humana. Ela responde, sem alterar policy, confidence ou lifecycle:

```text
Quem é responsável pela solicitação?
Para qual técnico ela deve ser encaminhada?
Ela deve aparecer na fila de aprovação?
```

O fluxo canônico passa a ser:

```text
AccessRequestContext
-> RequestLifecycleService.create_request(...)
-> PENDING_APPROVAL
-> RoutingService
-> RoutingAssignment
-> ApprovalQueue
-> ApprovalService
-> ExecutionEngine
-> CDMActionExecutor
-> CDMAdapter
```

Para `DENIED_POLICY`:

```text
AccessRequestContext
-> RequestLifecycleService.create_request(...)
-> DENIED_POLICY
-> sem RoutingAssignment
-> fora da ApprovalQueue
-> sem execução
```

"Escalonamento" nesta fase significa encaminhamento seguro ao responsável humano correto. Não significa SLA temporal, timeout, nível 1 para nível 2, pager, email, Slack ou plantão.

## 2. Baseline e fontes canônicas

Baseline da Fase 10:

```text
main = e5d0e3ccde56effff5c5f9558591b0d12c0740bb
historical pytest node IDs = 786
Python = 3.14.x
Ruff = 0.12.12
```

A evidência homologada da Fase 9 registrou `786 passed`, `786` candidate node IDs e zero ausentes. O merge da Fase 9 em `main` é o SHA acima.

Fontes obrigatórias lidas antes desta spec:

```text
AGENTS.md
docs/roadmap.md
docs/architecture/2026-09-08-policy-execution-cdm-handoff.md
docs/superpowers/specs/2026-09-09-phase-8-controlled-approval-execution-design.md
docs/superpowers/plans/2026-09-09-phase-8-controlled-approval-execution.md
docs/superpowers/specs/2026-09-09-phase-9-cdm-integration-design.md
docs/superpowers/plans/2026-09-09-phase-9-cdm-integration.md
```

## 3. Reuso obrigatório

A Fase 10 reutiliza diretamente:

```text
AccessRequestRecord.context.system
AccessRequestRecord.context.capability
AccessRequestRecord.state
AccessRequestRecord.confidence
TechnicianIdentity
TechnicianRegistryEntry
TechnicianAuthorizationRegistry
RequestLifecycleService
InMemoryRequestRepository
ApprovalService
```

Não é criado um segundo modelo de técnico, capability, request, policy, confidence ou lifecycle.

A regra de autorização humana permanece exclusivamente no mecanismo homologado:

```python
TechnicianAuthorizationRegistry.require_capability(...)
```

Routing seleciona um responsável operacional. Routing nunca concede autorização. `ApprovalService` continua executando a checagem final de capability quando um técnico tenta aprovar ou rejeitar.

## 4. Arquivos protegidos

A implementação deve funcionar sem alterar estes arquivos:

```text
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/confidence.py
src/ai_service_desk/engine/request_lifecycle.py
src/ai_service_desk/engine/request_repository.py
src/ai_service_desk/engine/technician_authorization.py
src/ai_service_desk/engine/approval.py
src/ai_service_desk/engine/execution.py
src/ai_service_desk/engine/cdm_execution.py
src/ai_service_desk/engine/cdm_integration_smoke.py
src/ai_service_desk/integrations/cdm.py
src/ai_service_desk/integrations/cdm_fake_api.py
```

Blobs registrados no baseline `e5d0e3ccde56effff5c5f9558591b0d12c0740bb`:

```text
access_request.py = f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d
policy.py = 60a4f3ae785353009c30b37f71e1ce91865b899e
confidence.py = ffc0c212b455978f79a3591578f323ca0e9612dc
request_lifecycle.py = dfd194ff8a364a0eb0d803409dad252ced216279
request_repository.py = 5ccda3d30484729faa1a568cf64e20bfe55e595f
technician_authorization.py = ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4
approval.py = ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8
execution.py = 908ceade729daa3e18b7b604549f635b33d4688f
cdm_execution.py = 516e258f2349fee42dbd963a7371d2ca3937ca69
cdm_integration_smoke.py = 07a9416a1c4727b224176ab0840067c536ffc1b9
integrations/cdm.py = 83cc0b23b27b1654912e4f9ba7162c0b0d5f7bfe
integrations/cdm_fake_api.py = 275b1833d5b27b09c0ffeae9f4484636d10afe63
```

Os testes de segurança e o workflow devem consultar o objeto Git de `HEAD` com `git rev-parse HEAD:<path>` e exigir igualdade exata.

## 5. Lifecycle permanece fechado

A Fase 10 não adiciona estados.

O conjunto continua exatamente:

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

Não existem nesta fase:

```text
ROUTED
UNROUTED
ROUTING_FAILED
```

Routing assignment vive fora de `AccessRequestRecord` e não altera a matriz de transições.

## 6. Chave de routing

A chave operacional é exatamente:

```text
(system, capability)
```

Exemplo canônico:

```text
("CDM", "CDM_ACCESS_REQUEST")
```

Não entram na chave:

```text
confidence
requested_role
requester.area
requester.email
purpose
playbook_id
```

Esses dados continuam preservados no request, mas não ampliam nem substituem a policy e não escolhem autorização por heurística.

`system` e `capability` da configuração de routing devem ser códigos simbólicos válidos compatíveis com `^[A-Z][A-Z0-9_]{2,119}$`.

## 7. RoutingRule

Contrato conceitual:

```python
@dataclass(frozen=True)
class RoutingRule:
    system: str
    capability: str
    technician: TechnicianIdentity
```

A regra guarda a identidade canônica completa do técnico. Não guarda apenas uma string livre de `technician_id`.

Isso permite validar a configuração sem modificar o registry homologado:

```python
authorization_registry.require_capability(
    rule.technician,
    rule.capability,
)
```

Se o técnico não existir no registry, a identidade divergir ou a capability estiver ausente, a construção do routing registry falha fechada.

## 8. RoutingRegistry

Responsabilidades:

```text
validar todas as regras
validar técnico contra TechnicianAuthorizationRegistry
indexar por chave exata system/capability
rejeitar duplicidade
resolver uma rota exata
falhar fechado em rota ausente
```

Construção em duas passagens conceituais:

```text
1. validar todas as regras, inclusive autorização da capability
2. somente depois construir o índice e validar unicidade da chave
```

Nenhuma configuração parcialmente válida pode operar.

Erros mínimos:

```text
ROUTING_RULE_INVALID
ROUTING_TECHNICIAN_NOT_AUTHORIZED
ROUTING_RULE_CONFLICT
ROUTE_NOT_FOUND
```

`ROUTING_TECHNICIAN_NOT_AUTHORIZED` encapsula a falha de configuração causada por `TechnicianAuthorizationRegistry.require_capability(...)`. O erro original não é tratado como permissão implícita.

Não existe wildcard, prefix match, fuzzy match, fallback por system ou escolha do primeiro técnico disponível.

## 9. RoutingAssignment

Contrato conceitual:

```python
@dataclass(frozen=True)
class RoutingAssignment:
    request_id: str
    system: str
    capability: str
    technician: TechnicianIdentity
```

O assignment é uma decisão operacional imutável para um request específico.

Ele não contém:

```text
policy decision
approval status
execution status
fila duplicada
credencial externa
```

O estado atual continua pertencendo ao `AccessRequestRecord`.

## 10. RoutingAssignmentStore

A implementação desta fase é somente em memória.

Interface conceitual:

```python
class RoutingAssignmentStore:
    def assign(self, assignment: RoutingAssignment) -> RoutingAssignment: ...
    def get(self, request_id: str) -> RoutingAssignment: ...
    def get_optional(self, request_id: str) -> RoutingAssignment | None: ...
    def snapshot(self) -> tuple[RoutingAssignment, ...]: ...
```

A implementação `InMemoryRoutingAssignmentStore` usa `threading.RLock`.

Regras:

1. primeiro assignment válido para `request_id` é armazenado;
2. repetição byte/logicamente idêntica retorna o assignment existente;
3. repetição idêntica não cria nova entrada;
4. mesmo `request_id` com qualquer destino incompatível falha;
5. conflito não sobrescreve o assignment atual;
6. `snapshot()` retorna tuple imutável em ordem determinística por `request_id`;
7. não existe delete ou atualização arbitrária nesta fase.

Erros mínimos:

```text
ROUTING_ASSIGNMENT_INVALID
ROUTING_ASSIGNMENT_NOT_FOUND
ROUTING_ASSIGNMENT_CONFLICT
```

A operação de check e write ocorre sob o mesmo `RLock`. Duas threads não podem atribuir silenciosamente o mesmo request a alvos diferentes.

## 11. RoutingService

Interface:

```python
class RoutingService:
    def route(self, request: AccessRequestRecord) -> RoutingAssignment: ...
```

Fluxo fechado:

```text
validar AccessRequestRecord exato
-> exigir state == PENDING_APPROVAL
-> resolver (context.system, context.capability)
-> construir RoutingAssignment
-> store.assign(...)
-> retornar assignment persistido
```

Somente `PENDING_APPROVAL` é roteável operacionalmente.

Chamadas diretas com:

```text
DENIED_POLICY
APPROVED
REJECTED
EXECUTING
COMPLETED
FAILED
TRIAGED
```

falham com:

```text
ROUTING_STATE_NOT_PENDING
```

Nenhuma dessas falhas cria assignment.

Routing não chama policy, não altera confidence, não aprova e não executa.

## 12. Composição automática request para routing

Nova camada de orquestração, sem alterar `RequestLifecycleService`:

```python
class RoutedRequestService:
    def create_request(self, context: AccessRequestContext) -> AccessRequestRecord: ...
```

Fluxo:

```text
record = lifecycle.create_request(context)
if record.state == PENDING_APPROVAL:
    routing.route(record)
return record
```

Se o lifecycle retornar `DENIED_POLICY`, `RoutingService.route` não é chamado.

Se o lifecycle retornar `PENDING_APPROVAL` e a rota estiver ausente ou inválida, o erro de routing é propagado. O request permanece auditável em `PENDING_APPROVAL`, mas fica sem assignment e, portanto, fora da fila. Não existe rollback do lifecycle, fallback de técnico ou alteração artificial de state.

Depois da correção da configuração, `RoutingService.route(record)` pode ser repetido explicitamente. Uma repetição idêntica é idempotente.

## 13. ApprovalQueue derivada

A fila não mantém uma segunda cópia de state.

Contrato conceitual:

```python
@dataclass(frozen=True)
class ApprovalQueueItem:
    request: AccessRequestRecord
    assignment: RoutingAssignment

class ApprovalQueue:
    def pending(self, *, technician_id: str | None = None) -> tuple[ApprovalQueueItem, ...]: ...
```

A fila é calculada a partir de:

```text
assignment_store.snapshot()
+
request_repository.get(request_id)
```

Um item aparece somente quando:

```text
assignment válido existe
AND
request.state == PENDING_APPROVAL
AND
assignment.system == request.context.system
AND
assignment.capability == request.context.capability
```

Qualquer inconsistência entre assignment e request falha fechada com erro explícito. Ela nunca é ocultada por filtro.

Depois de aprovação ou rejeição:

```text
state = APPROVED ou REJECTED
-> item desaparece automaticamente da próxima leitura da fila
```

`technician_id` é apenas filtro operacional por responsável atribuído. Ele não concede autorização. `ApprovalService` continua validando a capability quando a decisão é tentada.

## 14. DENIED_POLICY

Invariante central:

```text
DENIED_POLICY
-> nenhum RoutingAssignment
-> zero itens na ApprovalQueue
-> nenhuma aprovação possível
-> nenhuma execução
```

`RoutedRequestService` não chama routing quando o lifecycle produz `DENIED_POLICY`.

Uma tentativa direta de `RoutingService.route(denied_record)` falha com `ROUTING_STATE_NOT_PENDING` e zero mutação.

## 15. Relação entre routing e authorization

A relação é restritiva:

```text
TechnicianAuthorizationRegistry
-> define quem pode decidir cada capability

RoutingRegistry
-> escolhe, dentre técnicos já autorizados, o responsável operacional

ApprovalService
-> volta a exigir a capability na hora da decisão
```

Portanto:

```text
roteado para técnico X
!=
técnico X ganhou capability
```

A configuração de routing não pode cadastrar técnico sem a capability exata. Mesmo um request roteado corretamente não permite que outro técnico sem capability aprove ou rejeite.

## 16. Domínios demonstrativos

A demonstração deve possuir rotas distintas para pelo menos:

```text
CDM
HARDWARE
POWER_BI
MICROSOFT_365
ERP
```

Capabilities sintéticas correspondentes podem ser:

```text
CDM_ACCESS_REQUEST
HARDWARE_SUPPORT_REQUEST
POWER_BI_SUPPORT_REQUEST
MICROSOFT_365_SUPPORT_REQUEST
ERP_SUPPORT_REQUEST
```

Esses domínios adicionais são exercitados diretamente no `RoutingRegistry` e em testes/smoke de resolução. Eles não entram no `AccessRequestContext` CDM se isso exigir modificar a preparação da Fase 7 ou a policy.

Nenhum adapter externo, API, Graph, ERP, hardware ou Power BI é implementado.

## 17. Concorrência

O único novo estado mutável da fase é o store de assignments.

`InMemoryRoutingAssignmentStore.assign(...)` usa `RLock` envolvendo:

```text
lookup existente
-> comparação idempotente/conflitante
-> primeira escrita
```

Cenários obrigatórios:

```text
duas threads, mesmo request, mesmo assignment
-> uma entrada final, ambas recebem o mesmo assignment

duas threads, mesmo request, assignments incompatíveis
-> uma escrita vence, a outra recebe ROUTING_ASSIGNMENT_CONFLICT
-> uma única entrada final
```

A fila só lê snapshots e records atuais. Ela não precisa de lock próprio além dos locks internos dos stores/repositories já existentes.

## 18. Auditoria operacional

Não é adicionado um segundo `AuditEvent` ao lifecycle da Fase 8.

Motivos:

- os eventos da Fase 8 possuem schema fechado e versões canônicas;
- routing é deliberadamente externo ao lifecycle;
- modificar `AuditEvent` ou `request_lifecycle.py` violaria a fronteira protegida sem necessidade.

O `RoutingAssignment` imutável e o snapshot do store são a evidência operacional desta fase. Persistência e histórico durável de routing ficam fora do escopo.

## 19. Segurança

Testes específicos devem provar:

```text
DENIED_POLICY nunca entra na fila
routing não executa HTTP
routing não chama CDM
routing não importa CDMAdapter
routing não altera policy
routing não altera confidence
routing não aprova automaticamente
routing não ignora TechnicianAuthorizationRegistry
rota desconhecida falha fechada
rota duplicada falha fechada
rota para técnico incompatível falha fechada
assignment conflitante falha fechada
routing de state diferente de PENDING_APPROVAL falha fechado
arquivos protegidos permanecem exatos
```

Módulos runtime da Fase 10 não podem importar:

```text
requests
urllib
http.client
socket
```

Também não podem importar:

```text
ai_service_desk.integrations.cdm
ai_service_desk.integrations.cdm_fake_api
ai_service_desk.engine.cdm_execution
```

## 20. Smoke oficial

O smoke é determinístico, local e sem LLM, Ollama ou rede.

Novo comando:

```text
python -m ai_service_desk routing-escalation-smoke
```

O comando é roteado por um módulo CLI aditivo da Fase 10, seguindo o padrão separado criado na Fase 9. Não é necessário modificar o CLI legado grande.

Casos exatos mínimos:

1. `CDM_ALLOWED_PENDING_AND_QUEUED`;
2. `IDEMPOTENT_ROUTING`;
3. `DENIED_POLICY_OUTSIDE_QUEUE`;
4. `UNKNOWN_ROUTE_FAILS_CLOSED`;
5. `INCOMPATIBLE_TECHNICIAN_CONFIG_REJECTED`;
6. `DISTINCT_DOMAIN_OWNERS`;
7. `QUEUE_ITEM_LEAVES_AFTER_DECISION`;
8. `AUTHORIZATION_REMAINS_FINAL_GATE`.

Saída de sucesso:

```text
ROUTING ESCALATION SMOKE OK
Casos sinteticos: 8
```

O relatório do smoke é somente agregado e não contém dados corporativos.

## 21. CLI aditivo

Para não tocar no `cli.py` legado, criar:

```text
src/ai_service_desk/phase10_cli.py
```

E estender apenas o dispatcher pequeno em:

```text
src/ai_service_desk/__main__.py
```

Ordem:

```text
phase10_cli.handles(argv)
phase9_cli.handles(argv)
cli.main(argv)
```

O comando da Fase 10 não constrói Ollama e não exige `CDM_API_TOKEN`.

## 22. CI

Criar:

```text
.github/workflows/phase10-routing-escalation.yml
```

Trigger obrigatório:

```text
pull_request
```

Configuração:

```text
ubuntu-latest
fetch-depth: 0
Python 3.14
Ruff 0.12.12
PYTHONPATH=src
```

Gates mínimos e ordem:

```text
checkout full history
setup Python 3.14
install project + Ruff 0.12.12
Ruff lint
Ruff format --check
historical node ID preservation contra e5d0e3cc...
full pytest
protected blob verification
Phase 8 security
Phase 9 security
Phase 10 security
Phase 10 routing smoke
working tree clean
```

O gate histórico imprime exatamente os campos:

```text
historical_node_ids=786
candidate_node_ids=<n>
missing_historical_node_ids=0
new_node_ids=<n>
```

A comparação usa conjuntos reais de node IDs coletados por `pytest --collect-only -q`, não apenas diferença de contagem.

## 23. Fora do escopo

Não implementar:

```text
frontend
dashboard web
Fase 11
aprendizado
analytics preventivo
integração real adicional
OAuth
SSO
novo auth
banco
SQLite
JSON persistente
Redis
Celery
Kafka
n8n
Slack
email automático
SLA temporal
escalonamento por timeout
auto approval
retry CDM
novo role CDM
mudança de policy
mudança de confidence
mudança do lifecycle
API externa de Hardware
API Power BI
Microsoft Graph
API ERP
```

## 24. Critérios de saída

A Fase 10 só pode ser homologada quando houver evidência no mesmo candidate SHA de que:

- `main` baseline foi `e5d0e3ccde56effff5c5f9558591b0d12c0740bb`;
- Python é `3.14.x`;
- Ruff é `0.12.12`;
- lint e format passam;
- full pytest passa;
- os 786 node IDs históricos continuam presentes;
- zero node IDs históricos estão ausentes;
- novos node IDs são contabilizados pelo conjunto real;
- os 12 protected blobs são exatos;
- oito states e transições da Fase 8 permanecem intactos;
- Phase 8 security passa;
- Phase 9 security passa;
- Phase 10 security passa;
- CDM permitido chega a `PENDING_APPROVAL`, recebe responsável CDM e aparece na fila;
- routing repetido é idempotente;
- assignment conflitante falha fechado sob concorrência e sem concorrência;
- `DENIED_POLICY` possui zero assignments e zero queue items;
- rota desconhecida não escolhe técnico arbitrário;
- técnico sem capability não pode compor rota;
- pelo menos três domínios têm responsáveis distintos, e o smoke cobre cinco;
- aprovação ou rejeição remove automaticamente o item da visão pending;
- routing não permite aprovação por técnico sem capability;
- nenhum módulo runtime da Fase 10 possui HTTP ou CDM integration imports;
- smoke oficial passa `8/8` com marcador inequívoco;
- workflow dedicado passa no PR;
- working tree do runner permanece limpo após os gates;
- Draft PR permanece aberto e não mergeado.

## 25. Decisão arquitetural final

A direção recomendada foi validada contra o código existente e é adotada.

A implementação cria uma camada nova de routing e uma fila derivada. Ela não modifica o lifecycle homologado, não cria outro modelo de técnico e não adiciona permissão.

O desenho final é:

```text
RequestLifecycleService
        |
        v
PENDING_APPROVAL
        |
        v
RoutedRequestService
        |
        v
RoutingService
        |
        +-> RoutingRegistry
        |       |
        |       +-> TechnicianAuthorizationRegistry.require_capability
        |
        +-> InMemoryRoutingAssignmentStore
                    |
                    v
               ApprovalQueue
                    |
                    v
               ApprovalService
                    |
                    v
              ExecutionEngine
                    |
                    v
                   CDM
```

Isso preserva as fronteiras das Fases 7, 8 e 9 e fecha a Fase 10 sem antecipar a Fase 11.