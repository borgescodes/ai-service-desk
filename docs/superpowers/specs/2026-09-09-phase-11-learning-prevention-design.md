# Fase 11: Aprendizado e prevenção

## 1. Objetivo

A Fase 11 adiciona uma camada analítica determinística depois do fluxo operacional homologado. Ela transforma resultados estruturados de interações em padrões explicáveis e oportunidades para revisão humana.

Fluxo:

```text
interações e resultados estruturados
-> OutcomeRecord
-> InMemoryOutcomeStore
-> PatternAggregator
-> OpportunityEngine
-> PreventionOpportunity
-> revisão humana futura
```

A fase não treina modelo, não muda autorização e não altera automaticamente conteúdo oficial.

Princípios centrais:

```text
OPERAR != APRENDER
APRENDER != AUTORIZAR
DETECTAR OPORTUNIDADE != ALTERAR O SISTEMA AUTOMATICAMENTE
```

## 2. Baseline

Baseline integrada:

```text
main = 81a748921ba01393285da2e2d2ebc9371c890e2c
Phase 10 candidate parent = 57997768fd4461cc32bdc4414ef0e51e2a42e77e
historical pytest node IDs = 847
Python homologado = 3.14.x
Ruff homologado = 0.12.12
branch = phase-11-learning-prevention
```

A implementação deve preservar todos os 847 node IDs históricos.

## 3. Não objetivos

Fora de escopo:

- frontend ou dashboard;
- Fase 12;
- fine tuning, online learning, RL, RLHF ou alteração de pesos;
- alteração automática de embedding, threshold ou retrieval;
- autoedição de Knowledge, Playbook ou Policy;
- `AUTO_APPROVE`;
- execução ou retry automático;
- nova integração externa;
- banco, Redis, fila, cron, background worker, data warehouse ou BI externo;
- LLM como classificador de recorrência;
- clustering semântico como gate.

## 4. Reuso obrigatório

A camada analítica é somente leitora das fases anteriores.

Fontes reutilizáveis:

- `TriageState` e resultado público de triagem;
- resultado de Knowledge com `knowledge_id`;
- resultado de Playbook com `playbook_id`, `playbook_version` e steps estruturados;
- `AccessRequestContext`;
- `AccessRequestRecord`;
- `PolicyDecision` já congelada dentro do request;
- `ConfidenceAssessment` apenas como metadado preexistente, nunca como gate analítico de autorização;
- `RoutingAssignment`;
- códigos seguros de `execution_result_code` e `execution_error_code`.

`AuditEvent` continua sendo a trilha autoritativa do lifecycle da Fase 8. A Fase 11 não replica eventos para um segundo audit log e não reconta cada transição como uma nova interação. O primeiro desenho usa um resumo analítico por interação para evitar dupla contagem.

## 5. Arquitetura

A implementação cria um domínio isolado:

```text
src/ai_service_desk/engine/learning_prevention.py
src/ai_service_desk/engine/learning_prevention_smoke.py
```

`learning_prevention.py` contém apenas contratos, validação, store em memória, adapters de coleta, agregação e geração de oportunidades. Não importa HTTP, CDM, ApprovalService ou ExecutionEngine.

`learning_prevention_smoke.py` carrega somente fixture sintética versionada e executa dez casos determinísticos.

## 6. OutcomeRecord

`OutcomeRecord` é um snapshot factual pequeno de uma interação. Existe no máximo um record persistido por `interaction_id` dentro de um `InMemoryOutcomeStore`.

Contrato:

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

- `interaction_id` é obrigatório, opaco, até 120 caracteres;
- `system`, `intent` e `outcome` são códigos estruturados não vazios;
- `capability`, `knowledge_id`, `playbook_id`, `step_id` e `reason_code` podem ser vazios quando o fato real não os possui;
- `playbook_version` é `None` quando não existe playbook e inteiro positivo quando existe;
- `playbook_id`, `playbook_version` e `step_id` devem ser coerentes entre si;
- `area` é um atributo estruturado de contexto, não texto de conversa;
- nenhum campo aceita transcript, answer, purpose, nome, username, email, token, segredo, traceback ou mensagem bruta de exceção;
- o record é imutável.

A Fase 11 não versiona records corporativos reais. Runtime permanece em memória e a fixture de Git é totalmente sintética.

## 7. Vocabulário fechado de outcomes

A primeira versão reconhece exatamente:

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

Cada outcome precisa ser demonstrável por uma superfície já existente:

- `RESOLVED_BY_KNOWLEDGE`: triagem terminou `ANSWERED` com `KNOWLEDGE_FOUND`;
- `GUIDED_BY_PLAYBOOK`: resolução de playbook terminou `PLAYBOOK_FOUND`;
- `ROUTED_TO_HUMAN`: request `PENDING_APPROVAL` possui `RoutingAssignment` compatível;
- `APPROVED`: `AccessRequestRecord.state == APPROVED`;
- `REJECTED`: `AccessRequestRecord.state == REJECTED`;
- `DENIED_POLICY`: `AccessRequestRecord.state == DENIED_POLICY`;
- `EXECUTION_COMPLETED`: `AccessRequestRecord.state == COMPLETED`;
- `EXECUTION_FAILED`: `AccessRequestRecord.state == FAILED`.

`TRIAGED` e `EXECUTING` não viram outcomes analíticos nesta fase porque representam snapshots transitórios. O collector falha explicitamente se receber um snapshot sem outcome demonstrável.

## 8. OutcomeCollector

`OutcomeCollector` projeta objetos homologados para `OutcomeRecord` sem mutá-los.

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

- adapters validam o tipo e o status real antes de projetar;
- Knowledge só aceita `ANSWERED` + `KNOWLEDGE_FOUND` e copia somente ID e dimensões estruturadas;
- Playbook só aceita `PLAYBOOK_FOUND` e preserva `playbook_id` e `playbook_version`;
- request chama `validate_access_request_record(record)` antes da projeção;
- `PENDING_APPROVAL` exige `RoutingAssignment` com mesmo `request_id`, `system` e `capability`;
- estados finais usam os códigos seguros já persistidos no record;
- nenhuma função chama policy, approval, execution, CDM ou routing service;
- os adapters não modificam nenhum objeto de entrada.

## 9. Store idempotente e concorrente

`InMemoryOutcomeStore` usa `threading.RLock`.

Interface:

```python
class InMemoryOutcomeStore:
    def ingest(self, record: OutcomeRecord) -> OutcomeRecord: ...
    def get(self, interaction_id: str) -> OutcomeRecord: ...
    def snapshot(self) -> tuple[OutcomeRecord, ...]: ...
```

Semântica:

1. primeiro record válido para um `interaction_id` é armazenado;
2. replay logicamente idêntico retorna o record existente;
3. replay não aumenta contagem;
4. mesmo ID com qualquer payload diferente falha com `OUTCOME_CONFLICT`;
5. `snapshot()` retorna tuple imutável em ordem de `interaction_id`;
6. não existe delete ou update arbitrário;
7. check e write ficam sob o mesmo `RLock`.

Erros de domínio expõem `reason_code` estável.

## 10. Agregação de padrões

A chave primária de recorrência é exatamente:

```text
(system, intent, capability, area)
```

Ela representa uma classe operacional observável de demanda. `knowledge_id`, `playbook_id`, `outcome` e `reason_code` permanecem dimensões de evidência dentro do padrão e não dividem a chave principal.

Contrato:

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

`PatternAggregator.aggregate(snapshot)`:

- valida todos os records;
- agrupa por chave exata;
- conta uma vez cada record do snapshot;
- ordena `PatternKey`, IDs e contagens canonicamente;
- não usa embeddings, similaridade, score ou LLM;
- produz o mesmo resultado para o mesmo conjunto de records independentemente da ordem de entrada.

## 11. Threshold

A única configuração de recorrência desta versão é:

```text
LEARNING_RULES_VERSION = 1
MIN_RECURRENCE = 3
```

O número é explícito, versionado e coberto por testes. Não existe score mágico, ajuste automático ou relação com o threshold de Knowledge `0.65`.

## 12. PreventionOpportunity

Contrato:

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

`opportunity_id` é determinístico a partir de `category + PatternKey`, usando SHA-256 sobre representação canônica e prefixo `OPP-`. Não contém PII nem depende de ordem de execução.

A oportunidade é somente recomendação para revisão humana. Não possui método de aplicar mudança.

## 13. Categorias e regras determinísticas

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

Emitir quando todas as evidências do padrão:

- não possuem `knowledge_id`;
- possuem outcome `ROUTED_TO_HUMAN`.

### PLAYBOOK_GAP

Emitir quando todas as evidências do padrão:

- possuem `knowledge_id` não vazio;
- não possuem `playbook_id`;
- possuem outcome `ROUTED_TO_HUMAN`.

### HUMAN_DEPENDENCY

Emitir quando todas as evidências do padrão possuem outcome `ROUTED_TO_HUMAN`.

### AUTOMATION_CANDIDATE

Emitir quando todas as evidências do padrão:

- possuem a mesma capability não vazia, já garantida pela PatternKey;
- possuem exatamente um `playbook_id` não vazio no conjunto agregado;
- possuem outcome `ROUTED_TO_HUMAN`.

Isso registra apenas uma candidata futura. Não executa automação e não concede autorização.

### PREVENTION_CANDIDATE

Emitir para qualquer padrão recorrente. A semântica é: existe demanda repetitiva suficiente para investigação de prevenção na origem. Não significa que a causa raiz seja conhecida.

### EXECUTION_RELIABILITY_ISSUE

Emitir quando o padrão possui pelo menos `MIN_RECURRENCE` evidências com outcome `EXECUTION_FAILED`.

Oportunidades podem se sobrepor. Por exemplo, um padrão pode ser simultaneamente `HUMAN_DEPENDENCY` e `KNOWLEDGE_GAP`. Cada categoria explica uma dimensão diferente da mesma evidência.

## 14. OpportunityEngine

Interface:

```python
class OpportunityEngine:
    def generate(
        self,
        patterns: tuple[PatternAggregate, ...],
    ) -> tuple[PreventionOpportunity, ...]: ...
```

Regras:

- nenhuma chamada externa;
- nenhuma mutação das evidências;
- categorias avaliadas em ordem canônica fixa;
- resultado ordenado por `(key, category, opportunity_id)`;
- mesma entrada gera exatamente mesma saída;
- `reason_codes` da oportunidade são somente códigos estruturados observados nas evidências e códigos analíticos estáveis da própria regra, nunca texto gerado.

## 15. Feedback humano

A primeira implementação não cria lifecycle de oportunidade. `OPEN`, `ACKNOWLEDGED`, `DISMISSED` e `ACCEPTED` ficam fora do escopo até existir necessidade de produto na Fase 12 ou posterior.

Essa decisão evita criar um segundo workflow sem interface de revisão.

## 16. Relação com Knowledge

A Fase 11 pode detectar `KNOWLEDGE_GAP`, mas não pode:

- escrever em source de Knowledge;
- alterar status para `APPROVED`;
- publicar answer;
- reconstruir ou substituir provenance;
- mudar threshold `0.65`.

Qualquer sugestão futura de conteúdo é `PROPOSED`, `DRAFT` ou `CANDIDATE` fora deste runtime, nunca `APPROVED` automaticamente.

## 17. Relação com Playbooks

`PLAYBOOK_GAP` e `AUTOMATION_CANDIDATE` não criam nem editam playbooks. O catálogo `APPROVED_PLAYBOOK` continua fail closed e exclusivamente humano.

## 18. Relação com Policy, Approval e Routing

Analytics não importa nem chama `PolicyEngine`, `ApprovalService`, `TechnicianAuthorizationRegistry`, `RoutingService` ou `RoutedRequestService`.

`RoutingAssignment` pode ser consumido apenas como evidência de que um request foi encaminhado a humano. Isso não concede capability, não muda técnico e não altera fila.

Frequência histórica de aprovação nunca vira autorização.

## 19. Relação com Execution e CDM

Analytics não importa nem chama `ExecutionEngine`, `CDMActionExecutor`, `CDMAdapter` ou API fake. Apenas `AccessRequestRecord.execution_result_code` e `execution_error_code`, já sanitizados, podem ser projetados.

Falha repetida gera `EXECUTION_RELIABILITY_ISSUE`. Não há retry, correção automática ou chamada CDM.

## 20. Privacidade

A Fase 11 usa minimização de dados:

- nenhum transcript;
- nenhum `answer`;
- nenhum `purpose`;
- nenhum nome, username, email ou technician email;
- nenhum token ou segredo;
- nenhum traceback ou mensagem bruta;
- fixture somente sintética;
- runtime store somente em memória;
- CLI imprime apenas categorias, chaves sintéticas, contagens e IDs seguros da fixture.

## 21. Fixture de demonstração

Criar:

```text
tests/fixtures/phase11_learning_prevention_cases.jsonl
```

A fixture contém records sintéticos suficientes para provar:

- recorrência resolvida por Knowledge;
- Knowledge gap;
- Playbook gap;
- dependência humana;
- candidata a automação;
- candidata a prevenção;
- falha repetida de execução.

Identificadores são sintéticos e nenhum email é necessário.

## 22. Smoke oficial

O smoke possui exatamente dez casos:

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

Saída CLI obrigatória:

```text
LEARNING PREVENTION SMOKE OK
Casos sinteticos: 10
```

O smoke não usa Ollama, rede, CDM real, serviço SaaS ou corpus corporativo.

## 23. Segurança

Os testes da Fase 11 devem provar:

- todos os 18 blobs protegidos permanecem exatos;
- `learning_prevention.py` e seu smoke não importam `requests`, `urllib`, `http.client`, `socket`, `ai_service_desk.integrations.cdm`, `ai_service_desk.integrations.cdm_fake_api` ou `ai_service_desk.engine.cdm_execution`;
- analytics não possui imports de `ApprovalService`, `ExecutionEngine`, `PolicyEngine` ou serviços mutadores de routing;
- geração de oportunidade não altera objetos de policy, request, knowledge, playbook ou routing usados como entrada;
- fixture não contém segredo, email real ou transcript;
- não existe chamada externa em smoke.

## 24. Arquivos protegidos e blobs do baseline

No baseline `81a748921ba01393285da2e2d2ebc9371c890e2c`:

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
src/ai_service_desk/integrations/cdm.py = 83cc0b23b27b09c30b37f71e1ce91865b899e
```

Correção do último item: o blob canônico real de `src/ai_service_desk/integrations/cdm.py` é `83cc0b23b27b1654912e4f9ba7162c0b0d5f7bfe`. Os demais:

```text
src/ai_service_desk/integrations/cdm_fake_api.py = 275b1833d5b27b09c0ffeae9f4484636d10afe63
src/ai_service_desk/engine/routing.py = 5c29d443801c26fa54a305a6403949681bae076a
src/ai_service_desk/engine/routing_escalation_smoke.py = 34cc749ac4abdc48a1d8200a2e32c2635773a42c
```

O teste e o workflow devem usar o blob canônico corrigido. A linha ilustrativa incorreta acima não deve ser usada como gate.

## 25. CLI

Criar `phase11_cli.py` e adicionar dispatch mínimo em `__main__.py` antes das CLIs das Fases 10 e 9.

Comando:

```text
python -m ai_service_desk learning-prevention-smoke
```

Nenhuma segunda CLI é necessária nesta fase.

## 26. Workflow

Criar:

```text
.github/workflows/phase11-learning-prevention.yml
```

Trigger `pull_request`, `fetch-depth: 0`, Python `3.14`, Ruff `0.12.12`, `PYTHONPATH=src`.

Gates:

1. Runtime versions.
2. Ruff lint.
3. Ruff format `--check`.
4. Preservação dos 847 node IDs históricos contra o baseline.
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

## 27. Critérios de saída

A Fase 11 está pronta para homologação somente quando o mesmo candidate SHA provar:

- Python 3.14.x;
- Ruff 0.12.12;
- lint e format passam;
- full pytest passa;
- 847 node IDs históricos presentes;
- zero históricos ausentes;
- novos IDs contabilizados;
- 18 protected blobs exatos;
- Phase 8, 9, 10 e 11 security passam;
- Phase 10 routing smoke passa;
- Phase 11 smoke passa 10/10;
- idempotência e conflito fail closed passam;
- mesma fixture produz mesmos padrões, contagens, oportunidades e ordem;
- nenhum HTTP ou integração externa nova existe na Fase 11;
- nenhuma mutação automática de Knowledge, Playbook, Policy, routing, approval ou execution existe;
- Draft PR está aberto, não mergeado e apontando para o candidate homologado.

Qualquer correção após congelar o candidate cria novo candidate SHA e invalida a homologação anterior.