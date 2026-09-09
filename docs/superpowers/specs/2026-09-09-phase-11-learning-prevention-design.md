# Fase 11: Aprendizado e prevenção

## 1. Objetivo

A Fase 11 adiciona uma camada analítica determinística depois do fluxo operacional homologado. Ela transforma resultados estruturados das interações em padrões explicáveis e oportunidades para revisão humana.

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

A fase não treina modelo, não altera autorização e não publica conteúdo oficial.

## 2. Baseline

```text
main = 81a748921ba01393285da2e2d2ebc9371c890e2c
Phase 10 candidate parent = 57997768fd4461cc32bdc4414ef0e51e2a42e77e
historical pytest node IDs = 847
Python homologado = 3.14.x
Ruff homologado = 0.12.12
branch = phase-11-learning-prevention
```

Todos os 847 node IDs históricos devem permanecer coletáveis.

## 3. Não objetivos

Fora de escopo:

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

A camada analítica é somente leitora. Ela pode consumir:

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

`AuditEvent` continua sendo a trilha autoritativa do lifecycle da Fase 8. A Fase 11 não cria um segundo audit log e não transforma cada transição em uma nova ocorrência. A primeira versão usa um resumo analítico por interação para evitar dupla contagem.

## 5. Arquitetura

Novos módulos de domínio:

```text
src/ai_service_desk/engine/learning_prevention.py
src/ai_service_desk/engine/learning_prevention_smoke.py
```

`learning_prevention.py` contém contratos, validação, store em memória, collectors somente leitura, agregação e geração de oportunidades.

`learning_prevention_smoke.py` usa somente fixture sintética versionada.

Não há HTTP, CDM, ApprovalService, ExecutionEngine ou PolicyEngine no runtime da Fase 11.

## 6. OutcomeRecord

`OutcomeRecord` é um snapshot factual pequeno. Existe no máximo um record armazenado por `interaction_id` em um `InMemoryOutcomeStore`.

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
- `system`, `intent` e `outcome` são códigos estruturados não vazios;
- `capability`, `knowledge_id`, `playbook_id`, `step_id` e `reason_code` podem ser vazios quando a evidência real não os possui;
- `playbook_version` é `None` sem playbook e inteiro positivo quando há playbook;
- `playbook_id`, `playbook_version` e `step_id` são coerentes entre si;
- `area` é atributo estruturado, não texto de conversa;
- nenhum campo aceita transcript, `answer`, `purpose`, nome, username, email, token, segredo, traceback ou mensagem bruta de exceção;
- o record é imutável.

A Fase 11 não versiona dados corporativos reais. Runtime fica em memória e a fixture Git é totalmente sintética.

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

Proveniência de cada outcome:

- `RESOLVED_BY_KNOWLEDGE`: triagem `ANSWERED` com `KNOWLEDGE_FOUND`;
- `GUIDED_BY_PLAYBOOK`: resultado `PLAYBOOK_FOUND`;
- `ROUTED_TO_HUMAN`: request `PENDING_APPROVAL` com `RoutingAssignment` compatível;
- `APPROVED`, `REJECTED`, `DENIED_POLICY`: estado equivalente de `AccessRequestRecord`;
- `EXECUTION_COMPLETED`: state `COMPLETED`;
- `EXECUTION_FAILED`: state `FAILED`.

`TRIAGED` e `EXECUTING` são snapshots transitórios e não viram outcome nesta fase.

## 8. OutcomeCollector

Interfaces:

```python
OutcomeCollector.from_knowledge(
    interaction_id: str,
    triage: TriageState,
    result: Mapping[str, object],
    *,
    area: str = "",
) -> OutcomeRecord

OutcomeCollector.from_playbook(
    interaction_id: str,
    triage: TriageState,
    result: Mapping[str, object],
    *,
    area: str = "",
) -> OutcomeRecord

OutcomeCollector.from_request(
    interaction_id: str,
    record: AccessRequestRecord,
    assignment: RoutingAssignment | None = None,
) -> OutcomeRecord
```

Regras:

- adapters validam tipo e status real antes de projetar;
- Knowledge só aceita `ANSWERED` + `KNOWLEDGE_FOUND`;
- Playbook só aceita `PLAYBOOK_FOUND`;
- request chama `validate_access_request_record(record)`;
- `PENDING_APPROVAL` exige assignment com mesmo `request_id`, `system` e `capability`;
- estados finais usam apenas códigos seguros do record;
- nenhuma função chama policy, approval, execution, CDM ou routing service;
- nenhum objeto de entrada é modificado.

## 9. Ingestão, idempotência e concorrência

`InMemoryOutcomeStore` usa `threading.RLock`.

```python
class InMemoryOutcomeStore:
    def ingest(self, record: OutcomeRecord) -> OutcomeRecord: ...
    def get(self, interaction_id: str) -> OutcomeRecord: ...
    def snapshot(self) -> tuple[OutcomeRecord, ...]: ...
```

Semântica:

1. primeiro record válido é armazenado;
2. replay idêntico retorna o existente;
3. replay idêntico não aumenta contagem;
4. mesmo ID com payload diferente falha `OUTCOME_CONFLICT`;
5. snapshot é tuple em ordem de `interaction_id`;
6. não há delete ou update arbitrário;
7. check e write são atômicos sob o mesmo `RLock`.

## 10. Agregação e chave de padrão

A chave primária é exatamente:

```text
(system, intent, capability, area)
```

`knowledge_id`, `playbook_id`, `outcome` e `reason_code` são dimensões de evidência, não parte da chave principal.

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
    knowledge_ids: tuple[str, ...]
    playbook_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
```

`PatternAggregator.aggregate(snapshot)` valida records, agrupa por chave exata, conta uma vez cada interação e ordena tudo canonicamente. A mesma coleção em qualquer ordem gera o mesmo resultado.

Não existe embedding, similaridade, LLM ou score.

## 11. Thresholds

Configuração explícita e versionada:

```text
LEARNING_RULES_VERSION = 1
MIN_RECURRENCE = 3
```

O valor `3` é coberto por testes e não muda automaticamente. Ele não tem relação com o threshold de Knowledge `0.65`, que permanece intacto.

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

A oportunidade é somente recomendação para revisão humana. Não há API para aplicá-la automaticamente.

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

Todas as evidências do padrão não têm `knowledge_id` e têm outcome `ROUTED_TO_HUMAN`.

### PLAYBOOK_GAP

Todas têm `knowledge_id`, nenhuma tem `playbook_id` e todas têm outcome `ROUTED_TO_HUMAN`.

### HUMAN_DEPENDENCY

Todas têm outcome `ROUTED_TO_HUMAN`.

### AUTOMATION_CANDIDATE

Todas têm outcome `ROUTED_TO_HUMAN`, capability não vazia e exatamente um `playbook_id` não vazio no agregado.

É apenas uma candidata futura. Nenhuma automação é executada.

### PREVENTION_CANDIDATE

Qualquer padrão recorrente gera oportunidade de investigar prevenção na origem. Isso não afirma causa raiz.

### EXECUTION_RELIABILITY_ISSUE

O padrão possui pelo menos `MIN_RECURRENCE` evidências `EXECUTION_FAILED`.

Categorias podem se sobrepor porque explicam dimensões diferentes da mesma recorrência.

## 14. OpportunityEngine e explicabilidade

```python
class OpportunityEngine:
    def generate(
        self,
        patterns: tuple[PatternAggregate, ...],
    ) -> tuple[PreventionOpportunity, ...]: ...
```

Regras:

- avaliação em ordem fixa de categorias;
- saída canônica por `(key, category, opportunity_id)`;
- mesma entrada gera mesma saída;
- `occurrence_count`, `evidence_ids`, `PatternKey` e `reason_codes` explicam por que a oportunidade existe;
- nenhum texto gerado por LLM entra na decisão.

## 15. Feedback humano

A primeira implementação não cria lifecycle de oportunidade. `OPEN`, `ACKNOWLEDGED`, `DISMISSED` e `ACCEPTED` ficam fora desta fase porque ainda não existe interface de revisão. Isso evita criar um segundo workflow antes da Fase 12.

## 16. Relação com Knowledge

`KNOWLEDGE_GAP` nunca escreve em source de Knowledge, nunca altera status para `APPROVED`, nunca publica `answer`, nunca substitui provenance e nunca altera o threshold `0.65`.

Qualquer sugestão futura de conteúdo deverá permanecer `PROPOSED`, `DRAFT` ou `CANDIDATE` até revisão humana.

## 17. Relação com Playbooks

`PLAYBOOK_GAP` e `AUTOMATION_CANDIDATE` não criam nem editam playbooks. `APPROVED_PLAYBOOK` continua humano e fail closed.

## 18. Relação com Policy, Approval e Routing

Analytics não chama `PolicyEngine`, `ApprovalService`, `TechnicianAuthorizationRegistry`, `RoutingService` ou `RoutedRequestService`.

`RoutingAssignment` pode ser lido apenas para provar encaminhamento humano. Frequência histórica de aprovação nunca vira autorização.

## 19. Relação com Execution e CDM

Analytics não chama `ExecutionEngine`, `CDMActionExecutor`, `CDMAdapter` ou API fake. Somente os códigos sanitizados já presentes em `AccessRequestRecord` podem ser projetados.

Falha repetida produz `EXECUTION_RELIABILITY_ISSUE`, sem retry ou correção automática.

## 20. Privacidade

Minimização obrigatória:

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

A fixture é sintética e o store fica em memória. CLI e smoke expõem somente chaves sintéticas, categorias, contagens e IDs seguros.

## 21. Fixture de demonstração

Criar:

```text
tests/fixtures/phase11_learning_prevention_cases.jsonl
```

Ela deve provar Knowledge recorrente, Knowledge gap, Playbook gap, routing humano, candidata a automação, prevenção e falha repetida de execução. Nenhum ticket corporativo real é usado.

## 22. Smoke oficial

Exatamente dez casos:

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

Saída CLI:

```text
LEARNING PREVENTION SMOKE OK
Casos sinteticos: 10
```

Sem Ollama, rede, CDM real, SaaS ou corpus corporativo.

## 23. Segurança

Testes devem provar:

- 18 blobs protegidos exatos;
- módulos da Fase 11 sem `requests`, `urllib`, `http.client`, `socket` e imports de CDM;
- `learning_prevention.py` sem `PolicyEngine`, `ApprovalService`, `ExecutionEngine`, `RoutingService` ou `RoutedRequestService`;
- oportunidade não altera policy, request, knowledge, playbook ou routing usados como evidência;
- fixture não contém segredo, email ou transcript;
- smoke não chama rede.

## 24. Blobs protegidos do baseline

Valores canônicos no baseline `81a748921ba01393285da2e2d2ebc9371c890e2c`:

```text
src/ai_service_desk/engine/knowledge.py = 233d60bea6e0616d6b3968760f1bce09fc393d08
src/ai_service_desk/engine/knowledge_retrieval.py = cf559b66c9a9d150628eeb0d8db195f7a51a34e7
src/ai_service_desk/engine/triage.py = c5ab48f7194fab561f9062c3ab5798c86ec0a8a0
src/ai_service_desk/engine/playbook.py = 947fa1c888688a28a35826bc5a03286f46d0269a
src/ai_service_desk/engine/access_request.py = f34fc3f0e22d82b8bf8f13439ed78a7d31d5869d
src/ai_service_desk/engine/policy.py = 60a4f3ae785353009c30b37f71e1ce91865b899e
src/ai_service_desk/engine/confidence.py = ffc0c212b455978f79a3591578f323ca0e9612dc
src/ai_service_desk/engine/request_lifecycle.py = dfd194ff8a364a0eb0d803409dad252ced216279
src/ai_service_desk/engine/request_repository.py = 5ccda3d30484729faa1a568cf64e20bfe55e595f
src/ai_service_desk/engine/technician_authorization.py = ca7fad92b5ad7422cbd8d0b844aa0fe6cd47c1f4
src/ai_service_desk/engine/approval.py = ae64166a6c2595ff65fd65af7fd5b98ed71a5bb8
src/ai_service_desk/engine/execution.py = 908ceade729daa3e18b7b604549f635b33d4688f
src/ai_service_desk/engine/cdm_execution.py = 516e258f2349fee42dbd963a7371d2ca3937ca69
src/ai_service_desk/engine/cdm_integration_smoke.py = 07a9416a1c4727b224176ab0840067c536ffc1b9
src/ai_service_desk/integrations/cdm.py = 83cc0b23b27b1654912e4f9ba7162c0b0d5f7bfe
src/ai_service_desk/integrations/cdm_fake_api.py = 275b1833d5b27b09c0ffeae9f4484636d10afe63
src/ai_service_desk/engine/routing.py = 5c29d443801c26fa54a305a6403949681bae076a
src/ai_service_desk/engine/routing_escalation_smoke.py = 34cc749ac4abdc48a1d8200a2e32c2635773a42c
```

O teste e o workflow consultam `git rev-parse HEAD:<path>` e exigem igualdade exata.

## 25. CLI

Criar `phase11_cli.py` e adicionar dispatch mínimo em `__main__.py`, antes das CLIs das Fases 10 e 9.

```text
python -m ai_service_desk learning-prevention-smoke
```

Nenhuma segunda CLI é necessária.

## 26. Workflow

Criar `.github/workflows/phase11-learning-prevention.yml` com `pull_request`, `fetch-depth: 0`, Python `3.14`, Ruff `0.12.12` e `PYTHONPATH=src`.

Gates:

1. Runtime versions.
2. Ruff lint.
3. Ruff format `--check`.
4. Preservação dos 847 node IDs históricos.
5. Full pytest.
6. Verificação dos 18 blobs.
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

## 27. Critérios de saída

O mesmo candidate SHA precisa provar:

```text
Python 3.14.x
Ruff 0.12.12
Ruff lint PASS
Ruff format PASS
full pytest PASS
historical = 847
missing historical = 0
new node IDs contabilizados
18 protected blobs PASS
Phase 8 security PASS
Phase 9 security PASS
Phase 10 security PASS
Phase 11 security PASS
Phase 10 routing smoke PASS
Phase 11 smoke PASS 10/10
nenhuma integração externa nova
nenhuma mutação automática de Knowledge/Playbook/Policy
working tree clean
Draft PR OPEN / DRAFT / NOT MERGED
```

Qualquer correção depois do candidate gera novo SHA e invalida evidência anterior.