# Fase 11: Aprendizado e prevenção

## 1. Objetivo

A Fase 11 adiciona uma camada analítica determinística depois do fluxo operacional homologado. O sistema registra apenas resultados estruturados, agrega recorrência e produz oportunidades explicáveis para revisão humana futura.

```text
interações e resultados estruturados
-> OutcomeRecord
-> InMemoryOutcomeStore
-> PatternAggregator
-> OpportunityEngine
-> PreventionOpportunity
-> revisão humana futura
```

Princípios centrais:

```text
OPERAR != APRENDER
APRENDER != AUTORIZAR
DETECTAR OPORTUNIDADE != ALTERAR O SISTEMA AUTOMATICAMENTE
```

A fase não treina modelo, não muda autorização e não publica conteúdo oficial.

## 2. Baseline

```text
main = 81a748921ba01393285da2e2d2ebc9371c890e2c
Phase 10 candidate parent = 57997768fd4461cc32bdc4414ef0e51e2a42e77e
historical pytest node IDs = 847
Python = 3.14.x
Ruff = 0.12.12
branch = phase-11-learning-prevention
```

Todos os 847 node IDs históricos devem permanecer presentes.

## 3. Não objetivos

Ficam fora de escopo:

- frontend, dashboard e Fase 12;
- fine tuning, online learning, RL, RLHF ou alteração de pesos;
- alteração automática de embeddings ou thresholds;
- autoedição de Knowledge, Playbook ou Policy;
- `AUTO_APPROVE`;
- execução ou retry automático;
- nova integração externa;
- banco, Redis, fila, cron, background worker, data warehouse ou BI externo;
- LLM, clustering semântico, fuzzy matching ou score como gate de recorrência.

## 4. Fontes de evidência e reuso

A camada analítica é somente leitora. Ela pode consumir fatos já homologados de:

```text
TriageState
resultado de Knowledge
resultado de Playbook
AccessRequestContext
AccessRequestRecord
PolicyDecision já congelada no record
ConfidenceAssessment já congelada no record
RoutingAssignment
execution_result_code
execution_error_code
```

`AuditEvent` continua sendo a trilha autoritativa do lifecycle da Fase 8. A Fase 11 não cria um segundo audit log e não transforma cada transição em nova ocorrência. Existe um resumo analítico por interação para impedir dupla contagem.

## 5. Arquitetura

Novos módulos de domínio:

```text
src/ai_service_desk/engine/learning_prevention.py
src/ai_service_desk/engine/learning_prevention_smoke.py
```

`learning_prevention.py` contém contratos, validação, store em memória, collectors somente leitura, agregação e geração de oportunidades.

`learning_prevention_smoke.py` lê somente a fixture sintética versionada e usa o domínio analítico local.

Nenhum módulo da Fase 11 chama HTTP, CDM, PolicyEngine, ApprovalService, ExecutionEngine ou serviços mutadores de routing.

## 6. OutcomeRecord

`OutcomeRecord` é um snapshot factual pequeno e imutável. Existe no máximo um record armazenado por `interaction_id`.

```python
@dataclass(frozen=True)
class OutcomeRecord:
    interaction_id: str
    system: str
    intent: str
    capability: str
    area: str
    knowledge_id: str
    playbook_id: str
    playbook_version: int | None
    step_id: str
    outcome: str
    reason_code: str
```

Regras:

- `interaction_id` é obrigatório, opaco e tem até 120 caracteres;
- `system`, `intent` e `outcome` são estruturados e não vazios;
- `capability`, `knowledge_id`, `playbook_id`, `step_id` e `reason_code` podem ser vazios quando a evidência real não os possui;
- `playbook_version` é `None` sem playbook e inteiro positivo quando há playbook;
- `playbook_id`, `playbook_version` e `step_id` precisam ser coerentes;
- `area` é atributo estruturado, não texto de conversa;
- não existem transcript, `answer`, `purpose`, nome, username, email, token, segredo, traceback ou mensagem bruta de exceção no contrato.

Runtime permanece em memória. Nenhum dado corporativo real é versionado pela Fase 11.

## 7. Vocabulário fechado de outcomes

```text
RESOLVED_BY_KNOWLEDGE
GUIDED_BY_PLAYBOOK
ROUTED_TO_HUMAN
APPROVED
REJECTED
DENIED_POLICY
EXECUTION_COMPLETED
EXECUTION_FAILED
```

Proveniência:

- `RESOLVED_BY_KNOWLEDGE`: triagem `ANSWERED` com `KNOWLEDGE_FOUND`;
- `GUIDED_BY_PLAYBOOK`: resultado `PLAYBOOK_FOUND`;
- `ROUTED_TO_HUMAN`: request `PENDING_APPROVAL` com `RoutingAssignment` compatível;
- `APPROVED`, `REJECTED`, `DENIED_POLICY`: estado equivalente do `AccessRequestRecord`;
- `EXECUTION_COMPLETED`: state `COMPLETED`;
- `EXECUTION_FAILED`: state `FAILED`.

`TRIAGED` e `EXECUTING` são transitórios e não viram outcomes analíticos.

## 8. OutcomeCollector

Interfaces públicas:

```python
OutcomeCollector.from_knowledge(...)
OutcomeCollector.from_playbook(...)
OutcomeCollector.from_request(...)
```

Regras:

- Knowledge exige `ANSWERED` + `KNOWLEDGE_FOUND`;
- Playbook exige `PLAYBOOK_FOUND`;
- request é validado por `validate_access_request_record`;
- `PENDING_APPROVAL` exige assignment com mesmo `request_id`, `system` e `capability`;
- estados finais usam apenas códigos seguros já persistidos;
- collectors não chamam policy, approval, execution, CDM ou routing service;
- collectors não mutam objetos de entrada.

## 9. Ingestão, idempotência e concorrência

`InMemoryOutcomeStore` usa `threading.RLock`.

```python
class InMemoryOutcomeStore:
    def ingest(self, record: OutcomeRecord) -> OutcomeRecord: ...
    def get(self, interaction_id: str) -> OutcomeRecord: ...
    def snapshot(self) -> tuple[OutcomeRecord, ...]: ...
```

Semântica:

1. primeiro payload válido para um ID é armazenado;
2. replay idêntico retorna o record existente;
3. replay idêntico não aumenta contagem;
4. mesmo ID com payload diferente falha com `OUTCOME_CONFLICT`;
5. snapshot é tuple ordenada por `interaction_id`;
6. não existe delete ou update arbitrário;
7. check e write ficam sob o mesmo `RLock`.

## 10. Agregação e chave de padrão

A chave primária é exatamente:

```text
(system, intent, capability, area)
```

`knowledge_id`, `playbook_id`, `outcome` e `reason_code` são dimensões de evidência e não dividem a chave principal.

```python
@dataclass(frozen=True, order=True)
class PatternKey:
    system: str
    intent: str
    capability: str
    area: str

@dataclass(frozen=True)
class PatternAggregate:
    key: PatternKey
    occurrence_count: int
    evidence_ids: tuple[str, ...]
    outcome_counts: tuple[tuple[str, int], ...]
    knowledge_count: int
    knowledge_ids: tuple[str, ...]
    playbook_count: int
    playbook_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
```

`knowledge_count` é a quantidade de evidências do padrão com `knowledge_id` não vazio. `playbook_count` é a quantidade com `playbook_id` não vazio. Esses contadores existem somente para provar cobertura total ou parcial do padrão. Eles impedem que cobertura parcial gere falso `KNOWLEDGE_GAP`, `PLAYBOOK_GAP` ou `AUTOMATION_CANDIDATE`.

`PatternAggregator.aggregate` valida records, agrupa por chave exata, conta cada interação uma vez e ordena resultados, IDs e contagens canonicamente. A mesma coleção em qualquer ordem gera o mesmo aggregate.

Não existe embedding, similaridade, LLM ou score.

## 11. Thresholds

Configuração fechada:

```text
LEARNING_RULES_VERSION = 1
MIN_RECURRENCE = 3
```

O threshold é explícito, versionado e coberto por testes. Não muda automaticamente e não tem relação com o threshold de Knowledge `0.65`.

## 12. PreventionOpportunity

```python
@dataclass(frozen=True)
class PreventionOpportunity:
    opportunity_id: str
    category: str
    key: PatternKey
    occurrence_count: int
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
```

`opportunity_id` é determinístico a partir de `category + PatternKey`, usando SHA-256 de representação canônica e prefixo `OPP-`.

A oportunidade é somente recomendação. Não existe API que aplique mudança operacional.

## 13. Categorias e regras

Categorias fechadas:

```text
KNOWLEDGE_GAP
PLAYBOOK_GAP
HUMAN_DEPENDENCY
AUTOMATION_CANDIDATE
PREVENTION_CANDIDATE
EXECUTION_RELIABILITY_ISSUE
```

Todas exigem `occurrence_count >= MIN_RECURRENCE`.

### KNOWLEDGE_GAP

Emitir somente quando todas as evidências são `ROUTED_TO_HUMAN` e `knowledge_count == 0`.

### PLAYBOOK_GAP

Emitir somente quando todas são `ROUTED_TO_HUMAN`, `knowledge_count == occurrence_count` e `playbook_count == 0`.

### HUMAN_DEPENDENCY

Emitir quando todas as evidências são `ROUTED_TO_HUMAN`.

### AUTOMATION_CANDIDATE

Emitir quando todas são `ROUTED_TO_HUMAN`, capability é não vazia, `playbook_count == occurrence_count` e existe exatamente um `playbook_id` no aggregate.

É candidata futura, nunca execução automática.

### PREVENTION_CANDIDATE

Qualquer padrão recorrente gera recomendação de investigação preventiva. Isso não afirma causa raiz.

### EXECUTION_RELIABILITY_ISSUE

Emitir quando o aggregate contém pelo menos `MIN_RECURRENCE` outcomes `EXECUTION_FAILED`.

Categorias podem se sobrepor porque explicam dimensões diferentes da mesma recorrência.

## 14. OpportunityEngine e explicabilidade

`OpportunityEngine.generate` recebe aggregates e devolve tuple canônica de oportunidades.

Regras:

- mesma entrada produz mesma saída;
- saída é ordenada por `(PatternKey, category, opportunity_id)`;
- nenhuma regra usa LLM ou score probabilístico;
- cada oportunidade expõe chave, quantidade, `evidence_ids` e `reason_codes`;
- frequência histórica nunca vira autorização.

## 15. Feedback humano

A primeira implementação não cria lifecycle de oportunidade. `OPEN`, `ACKNOWLEDGED`, `DISMISSED` e `ACCEPTED` ficam fora desta fase porque ainda não existe interface de revisão. Isso evita introduzir um segundo workflow antes da Fase 12.

## 16. Relação com Knowledge

`KNOWLEDGE_GAP` não escreve em source de Knowledge, não altera status para `APPROVED`, não publica `answer`, não substitui provenance e não muda o threshold `0.65`.

Sugestões futuras de conteúdo deverão permanecer `PROPOSED`, `DRAFT` ou `CANDIDATE` até revisão humana.

## 17. Relação com Playbooks

`PLAYBOOK_GAP` e `AUTOMATION_CANDIDATE` não criam nem editam playbooks. `APPROVED_PLAYBOOK` continua humano e fail closed.

## 18. Relação com Policy, Approval e Routing

Analytics não chama `PolicyEngine`, `ApprovalService`, `TechnicianAuthorizationRegistry`, `RoutingService` ou `RoutedRequestService`.

`RoutingAssignment` é lido apenas como evidência de encaminhamento humano. Routing nunca é reescrito pela camada analítica.

## 19. Relação com Execution e CDM

Analytics não chama `ExecutionEngine`, `CDMActionExecutor`, `CDMAdapter` ou API fake. Somente códigos sanitizados já presentes no `AccessRequestRecord` podem ser projetados.

Falha repetida gera `EXECUTION_RELIABILITY_ISSUE`, sem retry ou correção automática.

## 20. Privacidade

A Fase 11 aplica minimização:

```text
sem transcript
sem answer
sem purpose
sem nome
sem username
sem email
sem token
sem segredo
sem traceback
sem mensagem bruta de exceção
```

A fixture é sintética, o store é em memória e CLI/smoke expõem somente categorias, chaves sintéticas, contagens e IDs seguros.

## 21. Fixture de demonstração

Fixture canônica:

```text
tests/fixtures/phase11_learning_prevention_cases.jsonl
```

Ela contém 15 outcomes sintéticos organizados em cinco padrões, cobrindo Knowledge resolvido, Knowledge gap, Playbook gap, routing humano, candidata a automação, prevenção e falha repetida de execução.

Nenhum ticket corporativo real é usado.

## 22. Smoke oficial

O smoke cobre exatamente dez casos:

```text
KNOWLEDGE_RECURRING_RESOLVES
KNOWLEDGE_GAP
HUMAN_DEPENDENCY
AUTOMATION_CANDIDATE
PREVENTION_CANDIDATE
EXECUTION_RELIABILITY_ISSUE
IDEMPOTENT_INGESTION
CONFLICT_FAILS_CLOSED
ANALYTICS_DOES_NOT_MUTATE_OPERATIONAL_STATE
DETERMINISTIC_SNAPSHOT
```

Saída oficial:

```text
LEARNING PREVENTION SMOKE OK
Casos sinteticos: 10
```

Sem Ollama, rede, CDM real, SaaS ou corpus corporativo.

## 23. Segurança e arquivos protegidos

Os testes da Fase 11 exigem que os 18 arquivos protegidos do baseline permaneçam com os blobs exatos capturados antes da primeira mudança:

```text
knowledge.py
knowledge_retrieval.py
triage.py
playbook.py
access_request.py
policy.py
confidence.py
request_lifecycle.py
request_repository.py
technician_authorization.py
approval.py
execution.py
cdm_execution.py
cdm_integration_smoke.py
integrations/cdm.py
integrations/cdm_fake_api.py
routing.py
routing_escalation_smoke.py
```

Os valores canônicos são fixados em `tests/engine/test_phase11_security.py` e repetidos no workflow dedicado. O gate usa `git rev-parse HEAD:<path>`.

Também é obrigatório provar:

- sem imports de `requests`, `urllib`, `http.client`, `socket` ou módulos CDM na Fase 11;
- sem imports de mutadores de Policy, Approval, Execution ou Routing;
- schema sem PII ou texto livre operacional proibido;
- fixture sem email, segredo ou token;
- oportunidade não muta request ou assignment usados como evidência.

## 24. CLI

Interface mínima:

```text
python -m ai_service_desk learning-prevention-smoke
```

`phase11_cli.py` é despachado antes dos comandos das Fases 10 e 9. Nenhuma segunda CLI é necessária.

## 25. CI e homologação

Workflow dedicado:

```text
.github/workflows/phase11-learning-prevention.yml
```

Configuração:

```text
pull_request
fetch-depth: 0
Python 3.14
Ruff 0.12.12
PYTHONPATH=src
```

Gates:

1. Runtime versions.
2. Ruff lint.
3. Ruff format `--check`.
4. Preservação dos 847 node IDs históricos.
5. Full pytest.
6. Verificação dos 18 blobs protegidos.
7. Phase 8 security regression.
8. Phase 9 security regression.
9. Phase 10 security regression.
10. Phase 11 security.
11. Phase 10 routing smoke.
12. Phase 11 learning/prevention smoke.
13. Working tree clean.

O gate histórico imprime:

```text
historical_node_ids=847
candidate_node_ids=<n>
missing_historical_node_ids=0
new_node_ids=<n>
```

## 26. Critérios de saída

A Fase 11 só pode ser homologada quando um único candidate SHA comprovar:

```text
Python 3.14.x
Ruff 0.12.12
Ruff lint PASS
Ruff format PASS
full pytest PASS
historical node IDs = 847
missing historical = 0
new node IDs contabilizados
18 protected blobs PASS
Phase 8 security PASS
Phase 9 security PASS
Phase 10 security PASS
Phase 11 security PASS
Phase 10 routing smoke PASS
Phase 11 learning/prevention smoke PASS 10/10
nenhuma integração externa nova
nenhuma mutação automática de Knowledge/Playbook/Policy
working tree clean
Draft PR OPEN / DRAFT / NOT MERGED
```

Qualquer correção depois de congelar o candidate cria novo SHA e invalida toda evidência anterior.