# Fase 12, Interface web e demonstração final

## 1. Objetivo

A Fase 12 transforma o domínio homologado das Fases 1 a 11 em um produto demonstrável no navegador, sem mover decisões de negócio para a apresentação.

O produto final desta fase é:

```text
Browser
↓
Jup Resolve Web
↓
API HTTP fina
↓
serviços de domínio homologados
↓
resultado estruturado
↓
UI
```

A experiência deve provar, no mesmo processo local, três capacidades distintas:

1. resolução por Knowledge sem criar request;
2. solicitação CDM ponta a ponta, com routing, aprovação, revalidação de policy e execução;
3. leitura explicável das oportunidades de prevenção da Fase 11.

A Fase 12 adiciona uma camada. Ela não reescreve o domínio.

## 2. Baseline

Base obrigatória:

```text
a4c4dc25afd07f449036dd837dbcfa4a219806c2
```

Esse commit é o merge do PR 14 e contém a Fase 11 homologada.

Baseline histórica Python:

```text
925 pytest node IDs
```

Branch:

```text
phase-12-web-demo
```

Runtime esperado:

```text
Python 3.14.x
Ruff 0.12.12
```

## 3. Não objetivos

Não fazem parte desta fase:

```text
produção cloud
Docker complexo
Kubernetes
login real
SSO real
RBAC corporativo novo
banco corporativo
observability SaaS
analytics externo
Power BI real
ERP real
Microsoft Graph
integração Hardware
n8n
Slack
e-mail
Kafka
Celery
Redis
mobile app nativo
Electron
PWA offline sofisticada
treinamento de modelo
autoedição de Knowledge
autoedição de Playbook
mudança de Policy
AUTO_APPROVE
```

Também não fazem parte desta fase um dashboard executivo, uma nova marca de IA ou uma reimplementação do motor conversacional.

## 4. Feature shaping

### 4.1 Reuse

A camada web reutiliza diretamente:

```text
classification.classify_ticket
TriageEngine
KnowledgeEngine
PlaybookEngine
action_proposal_descriptor
prepare_access_request
PolicyEngine
assess_confidence
InMemoryRequestRepository
RequestLifecycleService
TechnicianAuthorizationRegistry
ApprovalService
ExecutionEngine
CDMActionExecutor
CDMAdapter
CDMFakeStore / build_cdm_server
RoutingRegistry
InMemoryRoutingAssignmentStore
RoutingService
RoutedRequestService
ApprovalQueue
InMemoryOutcomeStore
OutcomeCollector
PatternAggregator
OpportunityEngine
```

Nenhum desses serviços ganha uma versão equivalente no frontend.

### 4.2 Create

A Fase 12 cria:

```text
web application layer
FastAPI HTTP API
demo identity provider
deterministic demo AI adapters
demo orchestration runtime
request presentation index
frontend SPA local
frontend build/test/lint scripts
Phase 12 security tests
Phase 12 web demo smoke
Phase 12 workflow
demo script
local execution documentation
```

### 4.3 Impact

Novos diretórios principais:

```text
src/ai_service_desk/web/
web/
docs/demo/
```

Arquivos de integração permitidos:

```text
pyproject.toml
src/ai_service_desk/__main__.py
README.md
.github/workflows/phase12-web-demo.yml
```

Os módulos core protegidos permanecem imutáveis.

### 4.4 Risks

Riscos que a arquitetura deve bloquear:

```text
duplicar regra no frontend
alterar core homologado
introduzir auth paralelo
permitir identity arbitrária
UI afirmar sucesso antes do backend
demo depender de internet
reset tocar estado fora da demo
font licensing
acessibilidade insuficiente
build frontend complexo
expor reason_code, traceback, segredo ou token ao browser
```

### 4.5 Acceptance

A fase só é funcionalmente aceita quando é possível observar:

```text
Knowledge APPROVED resolve sem request
CDM cria request real pelo domínio
request PENDING_APPROVAL é roteada pelo domínio
somente Técnico CDM compatível vê sua pendência
ApprovalService continua sendo o gate humano
ExecutionEngine revalida policy
CDMActionExecutor chama CDMAdapter
request chega a COMPLETED ou FAILED pelo backend
solicitante vê lifecycle real
Prevenção deriva de PatternAggregator + OpportunityEngine
frontend não contém regra de policy, routing ou approval
identidade textual de chat não altera a sessão
```

## 5. Stack

### 5.1 Backend HTTP

Escolha:

```text
FastAPI 0.141.1
Uvicorn 0.52.4
```

Motivos:

1. encaixa no projeto Python 3.14 existente;
2. permite API fina e tipada sem infraestrutura adicional;
3. serve o build estático no mesmo processo;
4. mantém a demo local com um único runtime principal;
5. evita introduzir Node no backend.

As versões são fixadas para a fase, reduzindo variação no ambiente de apresentação.

### 5.2 Frontend

Escolha:

```text
HTML semântico
CSS próprio
JavaScript ES Modules
Node apenas para lint, tests e build
zero dependências npm de runtime
```

React, TypeScript e Vite eram a direção preferida do handoff, caso fossem a alternativa mais simples após inspeção. O baseline real não possui Node, frontend, package manager ou design system. Para esta demo, adicionar React, Vite, TypeScript, Vitest e Testing Library criaria um grafo de dependências maior do que a interface exige.

A SPA em ES Modules preserva separação de responsabilidades, suporta testes por módulos puros e reduz risco operacional da apresentação.

O frontend compilado é um diretório estático reproduzível. A demo não depende de hot reload.

### 5.3 Node

Node é ferramenta de verificação e build, não parte do backend.

Não há dependência npm. Portanto:

```text
sem node_modules
sem npx em runtime
sem CDN
sem instalação de pacote frontend
```

O workflow usa uma versão explícita de Node hospedado para executar:

```text
node web/scripts/lint.mjs
node --test web/tests/*.test.mjs
node web/scripts/build.mjs
```

## 6. Arquitetura

### 6.1 Boundary

```text
Browser
  │
  │ HTTP JSON, same origin
  v
FastAPI
  │
  ├── resolve DemoIdentity por ID allowlisted
  ├── valida payload HTTP
  ├── chama DemoRuntime
  └── serializa View Models
        │
        v
serviços homologados F1 a F11
```

FastAPI não implementa policy, confidence, routing, approval, execution ou prevention.

### 6.2 Pacote web

Estrutura prevista:

```text
src/ai_service_desk/web/
├── __init__.py
├── api.py
├── demo_ai.py
├── demo_data.py
├── demo_identity.py
├── demo_runtime.py
├── errors.py
├── presentation.py
└── smoke.py
```

Responsabilidades:

`demo_identity.py`
: allowlist de identidades sintéticas e conversão para `SessionIdentity` ou `TechnicianIdentity`.

`demo_ai.py`
: adapters determinísticos usados somente na demo para produzir a interface já exigida pelos contratos de classificação e embeddings. Não decide policy, approval, routing ou execution.

`demo_data.py`
: dados sintéticos de Knowledge, Playbook e outcomes usados para inicializar o runtime reproduzível.

`demo_runtime.py`
: composição de application services, estado in-memory, conversação, criação de request, listagem, approval, execution e prevention.

`presentation.py`
: serialização e tradução de estados internos para linguagem de produto. Não toma decisão de negócio.

`api.py`
: validação HTTP, resolução de identity, status HTTP, headers seguros e static serving.

`smoke.py`
: smoke determinístico do fluxo principal diretamente sobre o application layer.

## 7. Proteção do domínio homologado

Os seguintes blobs do baseline são protegidos:

```text
src/ai_service_desk/engine/knowledge.py
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/engine/triage.py
src/ai_service_desk/engine/playbook.py
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/confidence.py
src/ai_service_desk/engine/request_lifecycle.py
src/ai_service_desk/engine/request_repository.py
src/ai_service_desk/engine/technician_authorization.py
src/ai_service_desk/engine/approval.py
src/ai_service_desk/engine/execution.py
src/ai_service_desk/engine/cdm_execution.py
src/ai_service_desk/integrations/cdm.py
src/ai_service_desk/integrations/cdm_fake_api.py
src/ai_service_desk/engine/routing.py
src/ai_service_desk/engine/learning_prevention.py
```

A proteção usa o blob SHA exato existente em `a4c4dc25afd07f449036dd837dbcfa4a219806c2`.

`playbook_resolution.py` e `classification.py` são consumidos e também devem permanecer sem alteração nesta fase, salvo necessidade demonstrada antes de qualquer modificação.

## 8. Identidade de demonstração

### 8.1 Sem segundo sistema de autenticação

Não existe login local.

O frontend recebe de:

```text
GET /api/session/identities
```

uma lista fechada de IDs de demonstração.

Cada request autenticado da SPA envia:

```text
X-Demo-Identity: <identity_id>
```

O backend aceita apenas IDs existentes no provider local.

O browser nunca envia:

```text
username arbitrário
email arbitrário
area arbitrária
technician_id arbitrário
capability arbitrária
role arbitrária
```

A mensagem de chat não participa da resolução de identity.

### 8.2 Identidades iniciais

Solicitante:

```text
identity_id: pedro-miranda
name: Pedro Miranda
username: pedro.miranda
email: pedro.miranda@example.invalid
area: Revenda - Matriz
role: REQUESTER
```

Técnico CDM:

```text
identity_id: tecnico-cdm
name: Técnico CDM
username: tecnico.cdm
email: tecnico.cdm@example.invalid
technician_id: TECH-CDM
role: TECHNICIAN
capabilities: CDM_ACCESS_REQUEST
```

Uma terceira identidade técnica sintética pode provar isolamento de fila, desde que não seja usada como atalho de autorização.

## 9. Demo AI determinística

A demo final deve funcionar sem internet e sem depender de Ollama.

Isso não cria um novo motor de classificação. O adapter determinístico produz a resposta sintética com o mesmo formato esperado por `classify_ticket`, e o core continua validando a classificação.

O adapter cobre somente os cenários declarados da demo:

```text
CDM / problema de acesso
Microsoft 365 / reset ou problema de acesso
texto insuficiente ou não reconhecido
```

O embedder determinístico implementa o contrato já esperado por `KnowledgeEngine`. A base sintética contém no máximo um artigo elegível por combinação de sistema e intent necessária para o roteiro, portanto não existe regra paralela de ranking no adapter.

Essa camada fica isolada em `ai_service_desk.web` e é proibida fora do modo demo.

## 10. Knowledge e Playbook da demo

Os dados da demo passam pelos builders homologados:

```text
build_knowledge_index
↓
KnowledgeEngine
↓
TriageEngine
↓
PlaybookEngine
```

Knowledge sintética mínima:

```text
KB-SYN-CDM-ACCESS-001
KB-SYN-M365-PASSWORD-001
```

O artigo CDM possui um Playbook APPROVED com `ACTION_PROPOSAL`:

```text
PB-SYN-CDM-ACCESS-001
STEP-CDM-ACCESS-01
CDM_ACCESS_REQUEST
```

O artigo Microsoft 365 não possui playbook. Seu `answer` APPROVED é devolvido literalmente, provando o fluxo sem request.

Nenhuma resposta oficial é reescrita pelo frontend.

## 11. Orquestração de conversa

### 11.1 Fluxo

```text
mensagem
↓
TriageEngine.step
↓
KNOWLEDGE_FOUND ?
├── não -> clarification ou abstention
└── sim
    ↓
    PlaybookEngine.resolve
    ├── KNOWLEDGE_ONLY -> answer literal, sem request
    └── PLAYBOOK_FOUND
        ↓
        ACTION_PROPOSAL
        ↓
        prepare_access_request
        ├── NEEDS_CLARIFICATION -> pergunta
        └── READY
            ↓
            RoutedRequestService.create_request
```

`RoutedRequestService` continua decidindo se existe routing após o estado real produzido pelo lifecycle.

### 11.2 Conversas

Estado de conversa é in-memory e keyed por `identity_id`.

Cada conversa registra somente o necessário para renderização da demo:

```text
message id
role
text
created_at
structured context
request_id opcional
```

O texto não altera identity.

## 12. Requests e presentation index

`InMemoryRequestRepository` não expõe snapshot global. A camada web não modifica esse core.

Como todos os requests da demo são criados pelo `DemoRuntime`, ele mantém um índice somente de IDs:

```text
created_request_ids: list[str]
```

O record continua sendo lido do repository homologado.

Listagem do solicitante filtra por identidade imutável de `record.context.requester`.

Nenhuma cópia de record é persistida em paralelo.

## 13. Routing e Operação

A fila operacional usa diretamente:

```text
ApprovalQueue.pending(technician_id=...)
```

`Operação` só é anunciada no payload de identity quando a identity é técnica.

Um técnico sem capability de CDM não recebe o item CDM na sua fila.

Routing nunca equivale a autorização para aprovar. O POST de approval sempre passa por `ApprovalService`.

## 14. Aprovação e execução

### 14.1 Endpoint de aprovação

O body contém apenas:

```json
{
  "expected_version": 2
}
```

A identity técnica é resolvida pelo header allowlisted.

Fluxo:

```text
ApprovalService.approve
↓
record APPROVED
↓
ExecutionEngine.execute
↓
PolicyEngine.evaluate novamente
↓
EXECUTING
↓
CDMActionExecutor
↓
CDMAdapter
↓
fake CDM local
↓
COMPLETED ou FAILED
```

### 14.2 Progressão visual sem mentira

O backend síncrono pode terminar a execução antes da resposta HTTP. A UI não inventa estados intermediários.

A resposta do approval inclui uma sequência de eventos derivada de `repository.audit_for(request_id)`:

```text
REQUEST_APPROVED
EXECUTION_STARTED
EXECUTION_COMPLETED
```

ou o caminho real de falha/denial.

Enquanto a chamada está pendente, a UI mostra apenas:

```text
Aprovando solicitação...
```

Depois da resposta do backend, a UI pode revelar visualmente os eventos reais em sequência. Ela nunca apresenta sucesso antes de receber `COMPLETED`.

Com `prefers-reduced-motion`, os eventos aparecem sem animação temporal.

## 15. Fake CDM

O runtime de demo inicia `build_cdm_server` em loopback com porta efêmera.

O token é um valor sintético criado em memória para o processo da demo. Ele não é versionado como credencial corporativa e nunca é serializado para o browser.

Fluxo obrigatório:

```text
Browser
↓
Jup Resolve API
↓
ApprovalService / ExecutionEngine
↓
CDMActionExecutor
↓
CDMAdapter
↓
fake CDM HTTP loopback
```

O frontend não conhece URL, porta ou token do CDM.

## 16. Prevenção

O reset da demo carrega outcomes sintéticos estruturados em `InMemoryOutcomeStore`.

A API executa:

```text
store.snapshot
↓
PatternAggregator.aggregate
↓
OpportunityEngine.generate
```

A UI mostra o resultado serializado. Ela não cria categorias próprias.

Cada detalhe de oportunidade exibe:

```text
sistema
intent em linguagem de produto
área predominante
ocorrências
categoria
por que foi identificado
```

A explicação é derivada de `PatternKey`, `occurrence_count`, `category`, `evidence_ids` e `reason_codes`. Nenhum LLM interpreta prevenção.

## 17. Demo reset

Endpoint:

```text
POST /api/demo/reset
```

Existe somente na app criada com `demo_mode=True`.

Condições:

1. aceita somente conexão loopback;
2. recria repositories, stores, conversations, assignments, fake CDM e fixtures;
3. não toca arquivo corporativo, endpoint externo ou banco;
4. não reutiliza identity enviada pelo body;
5. retorna confirmação segura, sem segredo.

Reiniciar o processo também reseta a demo.

## 18. API

### 18.1 Endpoints

```text
GET  /api/session/identities
POST /api/jup/messages
GET  /api/requests
GET  /api/requests/{request_id}
GET  /api/operations/approvals
POST /api/requests/{request_id}/approve
POST /api/requests/{request_id}/reject
GET  /api/operations/prevention
GET  /api/operations/prevention/{opportunity_id}
POST /api/demo/reset
GET  /api/health
```

Não há `POST /api/session/select`. A seleção é estado local da SPA e o backend resolve cada request de forma independente pelo header allowlisted.

### 18.2 Erros

Envelope público:

```json
{
  "error": {
    "code": "NOT_AUTHORIZED",
    "message": "Você não tem permissão para esta ação.",
    "recoverable": true
  }
}
```

Nunca enviar traceback, nome de classe Python, token ou exceção bruta.

Mapeamentos gerais:

```text
payload inválido -> 400/422 com mensagem segura
identity inválida -> 401
role/capability incompatível -> 403
request inexistente -> 404
version conflict -> 409
estado inválido -> 409
falha interna -> 500 com mensagem genérica recuperável
```

## 19. Presentation model

A API não devolve dataclasses cruas.

### 19.1 Request summary

Campos públicos previstos:

```text
request_id
title
system
purpose
status
status_label
updated_at
requester
area
confidence
policy
routing
```

### 19.2 Confidence

Confidence não usa semântica de transação.

O domínio de request possui `HIGH` ou `LOW`. A conversa também possui o valor numérico da classificação que originou o contexto.

Para requests criados na demo, o runtime preserva essa provenance em metadata web keyed por `request_id`.

Exemplo:

```text
92% · Alta confiança
```

Esse percentual vem da classificação da conversa, não é calculado a partir de `HIGH`.

Se um record não possuir essa provenance, a API deve devolver valor numérico `null` e a UI mostra somente:

```text
Alta confiança
```

Nunca transformar `HIGH` em sucesso ou `LOW` em erro.

### 19.3 Policy

Solicitante recebe linguagem de produto, por exemplo:

```text
Requer aprovação humana
Bloqueada pela política de acesso
```

`reason_code` interno não é exibido ao solicitante.

O perfil operacional pode receber explicação segura do `PolicyDecision.reason`, mas não objeto Python ou stack trace.

### 19.4 Timeline

A timeline é derivada de `AuditEvent` real.

Mapeamentos de apresentação não criam evento ausente.

## 20. Rotas web

```text
/           -> Jup
/jup        -> Jup
/requests   -> Solicitações
/operations -> Operação / Pendências
/operations/prevention -> Operação / Prevenção
```

A SPA usa History API e o backend entrega `index.html` nas rotas não API.

## 21. Navegação

Navegação primária:

```text
Jup
Solicitações
Operação
```

`Operação` depende de `identity.permissions.can_operate` vindo da API. O frontend não infere isso pelo nome.

Dentro de Operação:

```text
Pendências
Prevenção
```

Não existe sidebar administrativa extensa.

## 22. Design Foundation v1

### 22.1 Brand tokens locked

```text
brand.green   #45813C
brand.yellow  #EEB41E
brand.gray    #808285
brand.white   #FFFFFF
```

### 22.2 Product surfaces

```text
surface.canvas       #F7F9F7
surface.primary      #FFFFFF
surface.secondary    #F1F5F1
surface.brand-soft   #EEF6EC

text.primary         #182019
text.secondary       #5F6961
text.muted           #6B756D

border.default       #DCE4DD
border.subtle        #E9EEEA
```

### 22.3 Actions

```text
action.primary.background #45813C
action.primary.foreground #FFFFFF
action.primary.hover      #376B31
action.accent.background  #EEB41E
action.accent.foreground  #202319
focus.ring                #EEB41E
```

### 22.4 Semantic tokens

Marca e semântica são separadas:

```text
semantic.success.foreground #245D37
semantic.success.surface    #EDF7F0
semantic.warning.foreground #714B00
semantic.warning.surface    #FFF4D6
semantic.danger.foreground  #9B2C24
semantic.danger.surface     #FCEDEA
semantic.info.foreground    #285A72
semantic.info.surface       #EDF5F8
```

O amarelo da marca não significa warning. O verde da marca não significa sucesso.

### 22.5 Geometry

```text
radius.sm   8px
radius.md   12px
radius.lg   16px
radius.full 999px
```

### 22.6 Spacing

```text
space.1   4px
space.2   8px
space.3   12px
space.4   16px
space.6   24px
space.8   32px
space.10  40px
space.12  48px
space.16  64px
```

### 22.7 Interaction tokens

```text
interaction.hover    rgba(24, 32, 25, 0.05)
interaction.pressed  rgba(24, 32, 25, 0.09)
interaction.selected #EEF6EC
interaction.disabled 0.48

control.height.sm 36px
control.height.md 44px
control.height.lg 52px

icon.sm 16px
icon.md 20px
icon.lg 24px

motion.fast   150ms
motion.normal 220ms
motion.slow   320ms

overlay.scrim rgba(24, 32, 25, 0.42)

table.row.height    52px
table.header.height 44px

layout.content.max  1440px
layout.page.gutter  clamp(16px, 3vw, 40px)
```

## 23. Tipografia

BrandBook define:

```text
font.brand = Magistral
```

O repositório não contém asset de fonte licenciado para web e a Fase 12 não assume licença de distribuição.

Portanto:

```text
font.brand = Magistral, quando o asset licenciado estiver disponível
font.ui = ui-sans-serif, system-ui, "Segoe UI", sans-serif
```

A demo não baixa fontes externas.

O fallback de UI é deliberado para chat, tabela, input, badge e texto longo. Nenhum arquivo Magistral é versionado nesta fase.

## 24. Jup avatar

O baseline não contém o asset aprovado do Jup.

A Fase 12 não redesenha o personagem.

A interface cria um `JupAvatar` substituível com fallback não ilustrativo, um monograma funcional da marca, usado somente quando há presença real do agente:

```text
home
resposta do Jup
thinking
análise
proposta de ação
execução assistida
```

Quando o asset aprovado for entregue, a troca deve ser local ao componente, sem alterar layout ou lógica.

## 25. Direção visual

Modo:

```text
Operate
```

Princípio:

```text
Verde estrutura.
Amarelo chama atenção.
Branco dá espaço.
```

Assinatura visual do produto:

```text
linguagem natural à esquerda
+
contexto operacional estruturado à direita
```

Proibidos como linguagem principal:

```text
AI gradient
roxo
azul elétrico
neon
glow
holographic border
sparkles
dashboard com KPI cards
sidebar SaaS genérica
clone visual do ChatGPT
```

Cards normais usam borda e superfície. Sombras ficam restritas a elementos realmente elevados.

## 26. Superfície Jup

### 26.1 Idle

Primeira viewport:

```text
Jup Resolve
[Jup]
Olá, Pedro.
Como posso ajudar?
[ Descreva o que você precisa... ]
```

Sem KPI, dashboard ou hero marketing.

### 26.2 Workspace

Após a primeira mensagem:

```text
┌───────────────────────────────────────┬──────────────────────┐
│ CONVERSA                              │ O QUE ENTENDI        │
│                                       │                      │
│ Pedro                                 │ Sistema              │
│ mensagem                              │ Solicitação          │
│                                       │ Finalidade           │
│ Jup                                   │ Confiança            │
│ resposta                              │ Policy               │
│                                       │ Próxima etapa        │
│ [ input ]                             │                      │
└───────────────────────────────────────┴──────────────────────┘
```

O painel não expõe `reason_code`, classe Python ou traceback ao solicitante.

## 27. Superfície Solicitações

Objetivo:

```text
O que aconteceu com o que eu pedi?
```

Lista focada em título, request id, estado e tempo.

Detalhe contém timeline derivada somente de eventos reais.

Em mobile, lista abre detalhe como página/painel, sem split view comprimida.

## 28. Superfície Operação

### 28.1 Pendências

Desktop usa split view:

```text
fila à esquerda
+
detalhe à direita
```

Ações:

```text
Rejeitar
Aprovar
```

Somente aparecem para identity autorizada e item pendente.

### 28.2 Prevenção

Lista oportunidades explicáveis. Não existe cabeçalho de KPIs.

O detalhe responde:

```text
qual padrão foi observado
quantas ocorrências
qual área
qual classificação
a evidência estruturada que sustentou a oportunidade
```

## 29. Estados obrigatórios

A UI implementa:

```text
idle
thinking
clarification needed
knowledge found
playbook guidance
request created
waiting approval
policy blocked
approved
rejected
executing
execution completed
execution failed
route unavailable
empty requests
empty approval queue
empty prevention
loading
network/API error
not authorized
```

Um mesmo componente pode cobrir mais de um estado quando a semântica for equivalente, desde que o feedback continue explícito.

## 30. Loading e erros

Conversa:

```text
Jup thinking state
```

Listas:

```text
loading textual simples
```

Ações críticas:

```text
Aprovando solicitação...
Executando acesso no CDM...
```

Erro de execução:

```text
Não foi possível concluir a execução no CDM.
A solicitação continua registrada.
Tente novamente a partir da operação quando o serviço estiver disponível.
```

Nenhum traceback é apresentado.

## 31. Acessibilidade

Obrigatório:

```text
WCAG AA para texto normal
focus visível
navegação por teclado
labels reais
aria-live para status assíncrono relevante
aria-current na navegação
sem cor como única indicação
touch target de aproximadamente 44px quando aplicável
prefers-reduced-motion
ordem de heading coerente
```

O `focus.ring` usa amarelo da marca com offset suficiente para contraste.

## 32. Responsividade

Validação principal:

```text
1440px
1280px
390px
```

Desktop:

```text
header completo
conversation + context panel
split view operacional
```

Mobile:

```text
header compacto
navegação adaptada
context panel vira accordion/sheet inline
split view vira lista -> detalhe
composer permanece alcançável
nenhuma informação crítica desaparece
```

## 33. Motion

Permitido:

```text
Jup thinking
entrada de resposta
mudança de contexto
progressão approval -> execution
mudança de status
```

Duração padrão entre 150ms e 320ms.

Sem bounce, parallax ou motion decorativo constante.

Com reduced motion, a transição visual é removida ou reduzida a troca imediata de estado.

## 34. Componentes mínimos

```text
AppHeader
PrimaryNavigation
DemoIdentitySwitcher
JupAvatar
Conversation
MessageBubble
Composer
ContextPanel
ConfidenceIndicator
StatusBadge
RequestList
RequestTimeline
OperationInbox
ApprovalDetail
ExecutionProgress
PreventionList
PreventionDetail
EmptyState
ErrorState
Button
Input
Dialog/Sheet somente se necessário no breakpoint mobile
```

Não existe design system separado. Componentes são extraídos apenas quando repetem papel real.

## 35. Frontend state model

A SPA mantém apenas:

```text
selectedIdentityId
currentRoute
server payloads
loading/error state
local conversation render state recebido da API
```

Ela não mantém cópia autoritativa de:

```text
policy
routing assignment
approval state
execution state
prevention category
```

A cada ação mutadora, o estado seguinte vem do servidor.

## 36. Security

A Fase 12 deve provar por teste e inspeção:

```text
frontend não contém Policy Engine
frontend não decide approval
frontend não decide routing
frontend não chama CDM
texto de chat não muda SessionIdentity
X-Demo-Identity aceita somente allowlist
backend revalida autorização no ApprovalService
backend revalida policy no ExecutionEngine
reset existe somente em demo mode e loopback
nenhuma credencial real versionada
nenhum token CDM no browser
nenhum segredo em web/dist
nenhum traceback na resposta pública
```

Headers de resposta recomendados:

```text
Cache-Control: no-store para /api
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Content-Security-Policy compatível com assets same-origin
```

## 37. Testing backend

Framework:

```text
pytest
```

Cobertura mínima:

```text
demo identity allowlist
identity fora da allowlist
chat / Jup flow
clarification
knowledge result sem request
playbook CDM cria request
request listing isolada por requester
request detail autorizado
request detail não autorizado
approval queue por técnico
approve
reject
policy denied
execution failure
prevention list
prevention detail
invalid request
reset somente demo loopback
presentation não expõe internals
```

A API é testada com funções da aplicação e, quando necessário, client HTTP coerente com FastAPI.

## 38. Testing frontend

Framework:

```text
node:test
node:assert
```

Módulos de apresentação são funções puras sempre que possível.

Cobertura mínima:

```text
Jup home
conversation render
context panel
confidence render
request lifecycle
operation role visibility
approval hidden/disabled when unauthorized
approval execution progress
execution error
prevention detail
empty states
API error
identity switching
HTML escaping de conteúdo vindo do servidor
```

## 39. Frontend build

`web/scripts/build.mjs`:

1. remove `web/dist` anterior;
2. copia apenas assets de `web/src` necessários ao runtime;
3. valida existência de `index.html`, CSS e entry module;
4. rejeita URL externa de asset ou CDN;
5. escreve build reproduzível sem timestamp variável.

A aplicação de produção local usa `web/dist`.

## 40. Lint frontend

`web/scripts/lint.mjs`:

1. executa `node --check` em módulos JS;
2. valida que arquivos runtime não contêm URL de CDN;
3. valida que não há inline event handlers HTML;
4. falha em referências explícitas a CDM API no frontend;
5. não substitui testes de comportamento.

## 41. Smoke da Fase 12

Marcador:

```text
WEB DEMO SMOKE OK
```

Casos:

```text
1. requester identity válida
2. Knowledge resolution sem request
3. CDM request criada
4. routing para TECH-CDM
5. Técnico CDM visualiza pendência
6. approve
7. CDM execution completa
8. requester vê COMPLETED
9. policy denied não entra na fila
10. prevention opportunities disponíveis
```

O smoke roda application orchestration diretamente, sem browser, e usa somente fixtures sintéticas.

## 42. Hero flow CDM

### Cena 1

Identity:

```text
Pedro Miranda
Revenda - Matriz
```

Mensagem:

```text
Preciso de acesso ao CDM para solicitar materiais para uma revenda.
```

Esperado:

```text
system CDM
intent PROBLEMA_ACESSO
requested_role SOLICITANTE
confidence HIGH
policy REQUIRE_APPROVAL
request PENDING_APPROVAL
routing TECH-CDM
```

### Cena 2

Trocar identity no header para Técnico CDM.

Abrir Operação, Pendências.

A request deve aparecer pela `ApprovalQueue` filtrada.

### Cena 3

Aprovar.

A resposta deve provar por audit real:

```text
REQUEST_APPROVED
EXECUTION_STARTED
EXECUTION_COMPLETED
```

O record final deve ser `COMPLETED` e o fake CDM deve conter o acesso.

### Cena 4

Voltar para Pedro.

Solicitações mostra a mesma request concluída e sua timeline real.

## 43. Knowledge no-ticket flow

Mensagem sintética de demonstração sobre Microsoft 365 deve:

```text
TriageEngine
↓
KnowledgeEngine
↓
KNOWLEDGE_FOUND
↓
PLAYBOOK result KNOWLEDGE_ONLY
↓
answer literal APPROVED
↓
OutcomeCollector.from_knowledge
↓
zero request criada
```

Mensagem de apresentação:

```text
Nem todo problema precisa virar chamado.
```

## 44. Prevention flow

Abrir Operação, Prevenção.

A API deriva oportunidades da Fase 11 em tempo de leitura.

Mensagem:

```text
O Jup Resolve não apenas atende melhor.
Ele ajuda a identificar o que não deveria continuar gerando demanda.
```

## 45. Execução local

Comandos de diagnóstico:

```text
python -m ai_service_desk web-demo --host 127.0.0.1 --port 8000
node web/scripts/lint.mjs
node --test web/tests/*.test.mjs
node web/scripts/build.mjs
python -m ai_service_desk web-demo-smoke
```

Entrada Windows:

```text
run-web-demo.cmd
```

O script deve validar o build e iniciar a API em loopback.

A demo normal não requer servidor frontend separado.

## 46. Visual review

Capturas obrigatórias:

```text
Jup idle desktop
Jup conversation desktop
Requests desktop
Operations approvals desktop
Prevention desktop
mobile Jup
mobile operation detail
```

Viewports:

```text
1440px
1280px
390px
```

A captura deve ser aberta e revisada. Um workflow pode gerar screenshots automatizados, mas a confirmação visual continua humana/agente por inspeção das imagens.

Critérios:

```text
sem overflow
hierarquia clara
estado legível
primeira viewport orientada à ação
context panel memorável e útil
sem UI genérica de IA
brand Juparanã reconhecível
focus e contraste coerentes
mobile sem informação crítica perdida
```

## 47. Impeccable quality gates

Após o fluxo funcional:

1. revisar primeiro viewport;
2. revisar hierarquia, spacing e typography;
3. validar estados async, empty, error e permission;
4. validar keyboard/focus e reduced motion;
5. validar desktop e mobile;
6. corrigir problemas em lote;
7. fazer no máximo uma rodada adicional de confirmação.

Não fazer polishing infinito.

## 48. CI

Arquivo:

```text
.github/workflows/phase12-web-demo.yml
```

Trigger obrigatório:

```text
pull_request
```

Gates:

```text
Python 3.14
Ruff 0.12.12
Python lint
Python format
historical pytest node preservation, baseline 925
full pytest
Node runtime explícito
frontend lint
frontend tests
frontend build
protected core blob verification
Phase 8 security
Phase 9 security
Phase 10 security
Phase 11 security
Phase 12 security
Phase 10 smoke
Phase 11 smoke
Phase 12 web demo smoke
working tree clean após builds limpos
```

Frontend test count é reportado separadamente de pytest node IDs.

## 49. Historical node gate

Base:

```text
a4c4dc25afd07f449036dd837dbcfa4a219806c2
```

Esperado:

```text
historical_node_ids=925
candidate_node_ids=<n>
missing_historical_node_ids=0
new_node_ids=<n>
```

Se historical não for exatamente 925, o workflow falha.

## 50. Protected blobs gate

O workflow compara `HEAD:<path>` com o blob SHA do baseline para todos os módulos protegidos desta spec.

Qualquer mudança falha antes da homologação.

## 51. Critérios de saída

Candidate só pode ser congelado quando houver evidência recente de:

```text
Python 3.14.x
Ruff 0.12.12
python -m ruff check . PASS
python -m ruff format --check . PASS
python -m pytest -q PASS
historical Python node IDs = 925
missing historical = 0
frontend lint PASS
frontend tests PASS
frontend build PASS
Phase 8 security PASS
Phase 9 security PASS
Phase 10 security PASS
Phase 11 security PASS
Phase 12 security PASS
Phase 10 routing smoke PASS
Phase 11 learning prevention smoke PASS
Phase 12 web demo smoke PASS
protected core blobs PASS
visual review PASS ou findings explicitamente aceitos
working tree clean
hosted workflows green no mesmo SHA
Draft PR com evidência final
```

## 52. Pull request

Título:

```text
Phase 12: web interface and final demo
```

Base:

```text
main
```

Head:

```text
phase-12-web-demo
```

Estado final da fase antes de autorização de merge:

```text
OPEN
DRAFT
NOT MERGED
```

Não marcar Ready e não mergear sem autorização explícita.

## 53. Narrativa final

A demonstração deve comunicar:

```text
Jup entende.
↓
Resolve quando pode.
↓
Orienta quando existe playbook.
↓
Controla risco com policy.
↓
Encaminha quando precisa de humano.
↓
Executa CDM somente após aprovação.
↓
Mostra o resultado ao solicitante.
↓
Aprende com padrões estruturados.
↓
Ajuda a prevenir recorrência.
```

Mensagem final:

```text
O objetivo não é atender mais chamados.

É fazer com que menos demandas precisem virar chamados,
automatizar com segurança o que puder ser automatizado
e dar contexto ao humano quando ele for necessário.
```
