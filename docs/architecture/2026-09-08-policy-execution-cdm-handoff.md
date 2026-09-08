# Fases 7 a 10: Policy, aprovação, execução e integração CDM

> Documento arquitetural canônico para as fases posteriores à Fase 6.
>
> Base: `main` após o merge da Fase 6 em `cf44c7d2baf843d9ef3e6a8a14fc7b628c62d600`.
>
> Este documento deve ser lido antes da spec da Fase 7. Ele registra decisões já aprovadas para a primeira demonstração e não deve ser reaberto sem motivo técnico reproduzível.

## 1. Estado do projeto

- Fase 0. Fundação do repositório. Concluída.
- Fase 1. Motor atual reproduzível. Concluída.
- Fase 2. Retrieval no corpus TI real. Concluída para o gate de produto; 2B permanece como evidência adicional de escala.
- Fase 3. Avaliação e calibração. Concluída.
- Fase 4. FAQ e base de conhecimento. Concluída.
- Fase 5. Triagem conversacional. Concluída.
- Fase 6. Playbooks. Concluída.
- Fase 7. Policy Engine e contexto de solicitação. Próxima fase.
- Fase 8. Aprovação e execução controlada.
- Fase 9. Integração CDM.
- Fase 10. Roteamento e escalonamento.
- Fase 11. Aprendizado e prevenção.
- Fase 12. Interface web e demonstração final.

## 2. Objetivo da demonstração externa

A primeira demonstração de execução externa do agente terá somente uma integração real ou simulada de ponta a ponta: o CDM.

O caso principal será uma solicitação de acesso ao CDM para que um colaborador possa solicitar materiais para uma revenda.

O agente não cria o acesso automaticamente apenas porque o pedido parece coerente. O fluxo esperado é:

1. receber identidade já fornecida pela plataforma hospedeira;
2. entender e normalizar a solicitação;
3. consultar knowledge e playbook aprovados conforme as fases anteriores;
4. aplicar regras determinísticas de policy;
5. avaliar coerência contextual separadamente da autorização;
6. criar uma solicitação interna somente quando a policy permitir progressão;
7. encaminhar futuramente a solicitação ao técnico responsável pelo CDM;
8. permitir aprovação ou rejeição dentro da nossa plataforma;
9. revalidar policy antes de qualquer execução;
10. chamar a API do CDM somente após aprovação humana válida;
11. registrar decisão, aprovação, execução e resultado para auditoria;
12. barrar solicitações proibidas antes da fila de aprovação.

A criação efetiva do acesso não pertence à Fase 7.

## 3. Princípio arquitetural

Fluxo aprovado:

```text
Usuário
  ↓
SessionIdentity
  ↓
Triagem
  ↓
Knowledge APPROVED
  ↓
Playbook APPROVED
  ↓
Normalização do pedido
  ↓
Policy Engine
  ↓
Confidence Assessment
  ↓
Solicitação interna
  ↓
Roteamento
  ↓
Técnico responsável
  ↓
Aprovação humana
  ↓
Execution Engine
  ↓
CDM Adapter
  ↓
API do CDM
```

Fluxo proibido:

```text
LLM
  ↓
HTTP
  ↓
CDM
```

O modelo de linguagem nunca recebe liberdade para decidir autorização e executar diretamente uma chamada externa.

## 4. Escopo da primeira demonstração

Somente o CDM terá integração externa executável na primeira versão.

Outros domínios podem existir apenas para classificação e roteamento demonstrativo, por exemplo manutenção de computadores, Power BI, Microsoft 365 e ERP. Não é necessário implementar integração externa completa para esses domínios.

## 5. Identidade da sessão

Não será criado um segundo sistema de autenticação para a demonstração.

A plataforma hospedeira futuramente fornecerá o contexto autenticado do usuário. O domínio deve aceitar esse contexto como identidade da sessão.

Contrato mínimo conceitual:

```python
SessionIdentity(
    username: str,
    name: str,
    email: str,
    area: str,
)
```

Regras obrigatórias:

- identidade não é inferida a partir da conversa;
- `username`, `email` e `area` vêm do contexto de sessão;
- texto como "sou da Revenda" não pode sobrescrever uma sessão cuja área seja Financeiro;
- para desenvolvimento local, identidades de demonstração pré-cadastradas são aceitáveis;
- a interface local pode permitir escolher um usuário de demonstração;
- o backend trata essa identidade selecionada como contexto de sessão, não como texto livre enviado no chat;
- o provedor local deve poder ser substituído futuramente pelo contexto autenticado da plataforma sem alterar as regras de negócio.

## 6. Roles reais do CDM

O CDM possui quatro roles relevantes para este fluxo:

```text
SOLICITANTE
APROVADOR
ADMIN
SUPERADMIN
```

Somente `SOLICITANTE` é elegível ao fluxo de solicitação via agente.

`APROVADOR`, `ADMIN` e `SUPERADMIN` são privilegiados e não podem ser concedidos por este canal.

### 6.1 Regra de normalização do role

Pedido genérico de acesso, sem qualquer indicação de privilégio, é normalizado para `SOLICITANTE`.

Exemplos:

```text
"Preciso de acesso ao CDM"
-> SOLICITANTE

"Preciso acessar o CDM para solicitar materiais"
-> SOLICITANTE

"Preciso de acesso ao CDM para a revenda"
-> SOLICITANTE
```

Pedidos explícitos de privilégio preservam o role privilegiado:

```text
"Quero acesso de aprovador ao CDM"
-> APROVADOR

"Preciso ser admin do CDM"
-> ADMIN

"Preciso de superadmin"
-> SUPERADMIN
```

O normalizador também não pode transformar em `SOLICITANTE` um pedido inequivocamente equivalente a capacidade privilegiada apenas porque o nome literal da role não apareceu.

Exemplo:

```text
"Quero um perfil que permita aprovar solicitações no CDM"
-> intenção privilegiada de APROVADOR
-> nunca usar o default SOLICITANTE
```

Se a role for realmente ambígua:

```text
requested_role = UNKNOWN
```

`UNKNOWN` existe apenas durante preparação/triagem. Ele nunca é uma entrada autorizável para uma decisão positiva de policy. O fluxo deve pedir esclarecimento ou falhar fechado.

Não usar regra equivalente a:

```text
UNKNOWN -> SOLICITANTE
```

## 7. Separação obrigatória entre policy e confiança

### 7.1 Policy

Policy responde:

```text
Esta solicitação pode continuar no fluxo?
```

Decisões mínimas da primeira versão:

```text
REQUIRE_APPROVAL
DENY
```

Não existe `AUTO_APPROVE`.

Matriz inicial do CDM:

| Sistema | requested_role | Policy |
| --- | --- | --- |
| CDM | SOLICITANTE | REQUIRE_APPROVAL |
| CDM | APROVADOR | DENY |
| CDM | ADMIN | DENY |
| CDM | SUPERADMIN | DENY |

A policy é determinística e implementada em código ou configuração controlada. O LLM não inventa regra de autorização.

Role ausente, desconhecida, sistema sem policy, regra conflitante ou entrada inválida nunca recebe autorização implícita.

### 7.2 Confidence Assessment

Confiança responde:

```text
O pedido parece coerente com o contexto organizacional conhecido?
```

Valores mínimos:

```text
HIGH
LOW
```

Regra inicial da demonstração:

```text
área relacionada à Revenda
+
CDM
+
finalidade de solicitar materiais
-> HIGH
```

Exemplo fora do contexto esperado:

```text
área Financeiro
+
CDM
+
finalidade de solicitar materiais
-> LOW
```

Confiança ajuda o técnico na revisão. Ela nunca concede ou retira autorização por si só.

```text
HIGH != aprovado
LOW != negado
```

Consequências obrigatórias:

```text
SOLICITANTE + HIGH
-> REQUIRE_APPROVAL

SOLICITANTE + LOW
-> REQUIRE_APPROVAL

APROVADOR + HIGH
-> DENY

ADMIN + HIGH
-> DENY

SUPERADMIN + HIGH
-> DENY
```

## 8. Contratos conceituais da Fase 7

### 8.1 AccessRequestContext

A policy deve receber uma entrada estruturada, não reinterpretar a conversa inteira.

```python
AccessRequestContext(
    requester: SessionIdentity,
    system: str,
    intent: str,
    requested_role: str,
    purpose: str,
    playbook_id: str,
)
```

Exemplo:

```json
{
  "requester": {
    "username": "pedro.miranda",
    "name": "Pedro Miranda",
    "email": "pedro.miranda@juparana.com.br",
    "area": "Analista de Acesso ao Mercado • Revenda - Matriz"
  },
  "system": "CDM",
  "intent": "REQUEST_ACCESS",
  "requested_role": "SOLICITANTE",
  "purpose": "Solicitar materiais para a revenda",
  "playbook_id": "cdm_access_request"
}
```

Se informações obrigatórias estiverem ausentes ou ambíguas, o pedido deve voltar ao fluxo de esclarecimento ou terminar em erro seguro. A policy nunca assume um role privilegiado e nunca autoriza `UNKNOWN`.

### 8.2 PolicyDecision

```python
PolicyDecision(
    decision: Literal["REQUIRE_APPROVAL", "DENY"],
    policy_id: str,
    reason_code: str,
    reason: str,
)
```

Exemplo permitido:

```json
{
  "decision": "REQUIRE_APPROVAL",
  "policy_id": "CDM_SOLICITANTE_ACCESS",
  "reason_code": "CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL",
  "reason": "Acesso de solicitante ao CDM exige aprovação humana antes da execução."
}
```

Exemplo negado:

```json
{
  "decision": "DENY",
  "policy_id": "CDM_PRIVILEGED_ACCESS",
  "reason_code": "CDM_PRIVILEGED_ACCESS_NOT_ALLOWED",
  "reason": "Roles privilegiados do CDM não podem ser concedidos por este canal."
}
```

### 8.3 ConfidenceAssessment

```python
ConfidenceAssessment(
    level: Literal["HIGH", "LOW"],
    reasons: list[str],
)
```

`PolicyDecision` e `ConfidenceAssessment` são objetos separados.

## 9. Integração com Fases 5 e 6

A Fase 7 não deve reabrir o domínio da triagem nem transformar Playbook em policy.

A composição esperada é conceitualmente:

```text
SessionIdentity
+
TriageState / resultado de triagem
+
Knowledge result
+
Playbook result
        ↓
normalização controlada do pedido
        ↓
AccessRequestContext
        ↓
PolicyEngine
        +
ConfidenceAssessment
```

A Fase 6 continua responsável apenas por knowledge vinculada a playbook e por descriptors estruturados de `ACTION_PROPOSAL`/`capability` quando existirem.

A Fase 7 não cria segunda representação incompatível de `intent`, `system`, `playbook_id` ou requester se o repositório já possuir contratos semanticamente equivalentes.

## 10. Fail closed

As seguintes situações nunca produzem autorização implícita:

- policy inexistente;
- requested role ausente;
- requested role desconhecida;
- sistema não reconhecido;
- entrada inválida;
- erro ao carregar regras;
- conflito entre regras;
- decisão impossível de determinar.

O resultado deve ser erro de domínio seguro ou estado que impeça progressão para aprovação/execução.

Nunca usar fallback equivalente a:

```text
Não encontrei policy, então pode continuar.
```

## 11. Casos obrigatórios da demonstração

### Caso A. Solicitante coerente

Sessão relacionada à Revenda e pedido de acesso ao CDM para solicitar materiais.

Esperado:

```text
Sistema: CDM
Role: SOLICITANTE
Finalidade: solicitar materiais
Policy: REQUIRE_APPROVAL
Confidence: HIGH
Execução externa: nenhuma
```

### Caso B. Solicitante com contexto incomum

Sessão da área Financeiro e pedido comum de acesso ao CDM para solicitar materiais.

Esperado:

```text
Role: SOLICITANTE
Policy: REQUIRE_APPROVAL
Confidence: LOW
Execução externa: nenhuma
```

Baixa confiança não bloqueia automaticamente um pedido de `SOLICITANTE`.

### Caso C. Aprovador proibido

```text
"Preciso de acesso aprovador ao CDM."
```

Esperado:

```text
Role: APROVADOR
Policy: DENY
Reason: CDM_PRIVILEGED_ACCESS_NOT_ALLOWED
Fila de aprovação: não entra
Execução externa: proibida
Auditoria: obrigatória
```

### Caso D. Admin proibido

```text
"Preciso de acesso admin ao CDM."
```

Esperado:

```text
Role: ADMIN
Policy: DENY
```

### Caso E. Superadmin proibido

```text
"Preciso de superadmin no CDM."
```

Esperado:

```text
Role: SUPERADMIN
Policy: DENY
```

### Caso F. Pedido ambíguo de privilégio

Pedido que sugere privilégio, mas não permite determinar role com segurança.

Esperado:

```text
requested_role = UNKNOWN
nenhuma autorização
esclarecimento ou fail closed
```

## 12. Roteamento futuro

Roteamento completo pertence à Fase 10, mas os dados necessários devem ser preservados desde a Fase 7.

Direção futura:

```text
system = CDM
-> capability/domínio = CDM
-> técnico responsável pelo CDM
```

Uma decisão `DENY` não entra como pendência operacional de aprovação. Ela permanece auditável como solicitação bloqueada.

A demonstração poderá cadastrar responsáveis diferentes para CDM, Hardware, Power BI, Microsoft 365 e ERP sem exigir integração externa para todos eles.

## 13. Aprovação humana

Nenhum acesso ao CDM é criado automaticamente a partir de `HIGH`.

Fluxo futuro:

```text
PENDING_APPROVAL
  ↓
Técnico abre a solicitação
  ↓
[REJEITAR] [APROVAR]
  ↓
APROVAR
  ↓
Backend revalida policy
  ↓
Execution Engine
  ↓
CDM Adapter
  ↓
CDM API
```

Regras:

- aprovação é registrada com o técnico responsável;
- policy é revalidada imediatamente antes da execução;
- frontend nunca chama CDM diretamente;
- frontend chama nosso backend;
- somente o backend chama o adapter do CDM;
- alterações no frontend não podem contornar policy;
- uma solicitação `DENY` nunca possui ação de aprovação.

## 14. Estados futuros da solicitação

Modelo mínimo recomendado para a Fase 8:

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

Fluxo padrão:

```text
TRIAGED
-> PENDING_APPROVAL
-> APPROVED
-> EXECUTING
-> COMPLETED
```

Rejeição humana:

```text
PENDING_APPROVAL
-> REJECTED
```

Bloqueio por policy:

```text
TRIAGED
-> DENIED_POLICY
```

## 15. Dados a preservar para auditoria e fases posteriores

Modelo conceitual acumulado:

```text
request_id

requester
  username
  name
  email
  area

request
  system
  intent
  requested_role
  purpose

triage/playbook
  playbook_id

policy
  decision
  policy_id
  reason_code
  reason
  evaluated_at

assessment
  confidence
  confidence_reasons

routing
  capability
  technician_id

approval
  status
  decided_by
  decided_at

execution
  status
  external_id
  executed_at
  error_code
```

A Fase 7 não implementa todos esses blocos, mas seus contratos não devem impedir essa evolução.

## 16. Responsabilidade por fase

### Fase 7. Policy Engine e contexto de solicitação

Implementar:

- `SessionIdentity` ou reutilização de contrato equivalente;
- preparação/normalização de `AccessRequestContext`;
- normalização segura de role CDM;
- pedido genérico sem indicação de privilégio -> `SOLICITANTE`;
- `SOLICITANTE -> REQUIRE_APPROVAL`;
- `APROVADOR -> DENY`;
- `ADMIN -> DENY`;
- `SUPERADMIN -> DENY`;
- ausência/ambiguidade -> nenhuma autorização;
- fail closed;
- `PolicyDecision` estruturada;
- `ConfidenceAssessment` separado;
- avaliação contextual mínima;
- integração com saída normalizada das Fases 5 e 6;
- testes unitários e smoke sintético.

Não implementar:

- botão de aprovação;
- entidade completa de solicitação persistida;
- chamada HTTP ao CDM;
- API fake do CDM;
- criação de acesso;
- roteamento completo de técnicos;
- interface final.

### Fase 8. Aprovação e execução controlada

Implementar:

- entidade/registro de solicitação;
- máquina de estados;
- aprovação e rejeição humana;
- checagem de autorização do técnico;
- revalidação de policy;
- Execution Engine;
- auditoria de tentativa e resultado;
- garantia de que execução exige aprovação válida;
- executor fake em memória inicialmente.

### Fase 9. Integração CDM

Implementar:

- API local simulada do CDM;
- `CDMAdapter`;
- consulta de acesso;
- criação de acesso;
- autenticação simples de serviço;
- idempotência;
- tratamento de erros;
- ligação do Execution Engine ao adapter.

Quando a API real estiver disponível, substituir somente a implementação do adapter.

### Fase 10. Roteamento e escalonamento

Implementar:

- configuração mínima de técnicos e capacidades;
- mapeamento `CDM -> técnico CDM`;
- encaminhamento automático de solicitações permitidas;
- preservação do contexto coletado;
- `DENIED_POLICY` fora da fila de aprovação;
- domínios adicionais apenas para demonstrar responsáveis distintos.

### Fase 11. Aprendizado e prevenção

Permanece como etapa posterior, sem antecipar seu desenho nesta fase.

### Fase 12. Interface web e demonstração final

Demonstrar visualmente:

- usuário autenticado ou simulado;
- conversa;
- análise da solicitação;
- requested role normalizada;
- confidence;
- policy aplicada;
- técnico responsável;
- fila `PENDING_APPROVAL`;
- aprovação/rejeição;
- execução CDM;
- resultado da integração;
- histórico de `DENIED_POLICY`.

## 17. API simulada do CDM, contrato futuro mínimo

A API real do CDM não é requisito para a Fase 7.

Estratégia aprovada:

1. definir contrato esperado;
2. construir Fase 7 sem chamadas externas;
3. construir aprovação/execução controlada na Fase 8;
4. implementar API local simulada na Fase 9;
5. integrar via adapter;
6. substituir fake pelo CDM real sem alterar policy, playbooks ou regras de negócio.

### 17.1 Consultar acesso

```http
GET /api/v1/access?email=pedro.miranda@juparana.com.br
```

Exemplo sem acesso:

```json
{
  "exists": false,
  "email": "pedro.miranda@juparana.com.br"
}
```

Exemplo com acesso:

```json
{
  "exists": true,
  "email": "pedro.miranda@juparana.com.br",
  "role": "SOLICITANTE",
  "status": "ACTIVE",
  "access_id": "84721"
}
```

### 17.2 Criar acesso

```http
POST /api/v1/access
Content-Type: application/json
Authorization: Bearer <service-token>
```

Corpo:

```json
{
  "request_id": "REQ-000184",
  "username": "pedro.miranda",
  "email": "pedro.miranda@juparana.com.br",
  "role": "SOLICITANTE"
}
```

Resposta ilustrativa:

```json
{
  "success": true,
  "access_id": "84721",
  "status": "ACTIVE"
}
```

### 17.3 Idempotência

`request_id` é único no simulador. Repetir o mesmo pedido não cria dois acessos.

O adapter deve distinguir pelo menos:

```text
acesso criado
acesso já existente
requisição repetida
erro de validação
erro de autenticação do serviço
falha interna
```

### 17.4 Autenticação de serviço

Para desenvolvimento local, um token fixo via variável de ambiente é suficiente:

```text
CDM_API_TOKEN=<token-local>
```

Conceitos distintos:

```text
SessionIdentity
-> quem pediu

Service credential
-> qual serviço está autorizado a chamar o CDM
```

## 18. CDM Adapter futuro

Toda comunicação HTTP específica do CDM fica encapsulada no adapter.

Interface conceitual:

```python
class CDMAdapter:
    def get_access(self, email: str) -> AccessLookup:
        ...

    def create_access(
        self,
        request_id: str,
        username: str,
        email: str,
        role: str,
    ) -> AccessCreationResult:
        ...
```

Playbook, Policy Engine e UI não contêm HTTP específico do CDM.

## 19. Matriz mínima de testes da Fase 7

1. Revenda + pedido genérico de acesso ao CDM -> `SOLICITANTE`, `REQUIRE_APPROVAL`, `HIGH` quando finalidade compatível.
2. Financeiro + pedido genérico de acesso -> `SOLICITANTE`, `REQUIRE_APPROVAL`, `LOW`.
3. Revenda + `APROVADOR` -> `DENY`.
4. Revenda + `ADMIN` -> `DENY`.
5. Revenda + `SUPERADMIN` -> `DENY`.
6. Financeiro + qualquer role privilegiada -> `DENY`.
7. Pedido inequívoco de capacidade para aprovar solicitações -> nunca default para `SOLICITANTE`.
8. Role ambígua -> `UNKNOWN` durante normalização e nenhuma autorização implícita.
9. Role ausente em contexto que não pode usar o default seguro -> esclarecimento ou erro de domínio seguro.
10. Sistema sem policy -> fail closed.
11. Texto do usuário contradiz `SessionIdentity.area` -> usar a área da sessão.
12. `HIGH` não cria `AUTO_APPROVE`.
13. `LOW` não converte `SOLICITANTE` em `DENY`.
14. nenhum caminho da Fase 7 chama CDM, HTTP ou executor.
15. integração com resultado de playbook não duplica classificação, retrieval ou lógica de triagem.

## 20. Critérios de aceite da Fase 7

A Fase 7 só pode ser concluída quando houver evidência de que:

- a decisão de policy é determinística;
- nenhum LLM decide autorização;
- nenhum código da Fase 7 chama o CDM;
- pedido genérico de acesso ao CDM sem indicação de privilégio normaliza para `SOLICITANTE`;
- `SOLICITANTE` sempre exige aprovação humana;
- `APROVADOR`, `ADMIN` e `SUPERADMIN` são bloqueados;
- capacidade privilegiada explícita não cai no default `SOLICITANTE`;
- ambiguidade não recebe autorização implícita;
- `HIGH` não aprova automaticamente;
- `LOW` não rejeita automaticamente um pedido de `SOLICITANTE`;
- identidade vem do contexto de sessão;
- chat não altera identidade confiável;
- policy desconhecida falha de forma segura;
- decisão e motivo são estruturados e auditáveis;
- confidence permanece separada da autorização;
- testes cobrem a matriz mínima;
- integração usa contratos existentes das Fases 5 e 6 quando semanticamente compatíveis;
- nenhuma lógica de triagem, knowledge ou playbook é duplicada sem necessidade.

## 21. Instruções para o agente executor da Fase 7

Antes de alterar código:

1. ler `docs/roadmap.md` e este documento;
2. inspecionar a `main` pós Fase 6;
3. inspecionar especialmente Fases 4, 5 e 6;
4. identificar modelos, serviços, enums e padrões já existentes;
5. reutilizar contratos atuais quando semanticamente compatíveis;
6. não criar segunda representação de `intent`, `system`, `playbook` ou requester sem necessidade;
7. manter policy fora da camada de apresentação;
8. manter confidence separada de autorização;
9. não refatorar áreas não relacionadas para acomodar a fase;
10. propor arquitetura da Fase 7 antes de materializar spec;
11. após aprovação arquitetural, produzir spec;
12. somente depois da aprovação da spec produzir plano;
13. somente depois executar implementação TDD.

## 22. Decisões congeladas para a primeira demonstração

Não reabrir sem motivo técnico real:

- CDM é a única integração externa executável;
- a plataforma hospedeira fornece identidade do usuário;
- ambiente local usa identidades simuladas;
- não existe autenticação paralela criada pelo agente;
- roles CDM são `SOLICITANTE`, `APROVADOR`, `ADMIN`, `SUPERADMIN`;
- pedido genérico de acesso sem indicação de privilégio usa `SOLICITANTE`;
- somente `SOLICITANTE` pode seguir para aprovação;
- `APROVADOR`, `ADMIN` e `SUPERADMIN` são proibidos pelo canal do agente;
- não existe `AUTO_APPROVE`;
- confidence ajuda revisão, mas não autoriza;
- contexto incomum de um `SOLICITANTE` pode seguir para revisão humana;
- policy explícita pode barrar antes do técnico;
- bloqueios continuam auditáveis;
- aprovação acontece na nossa plataforma;
- frontend não chama CDM;
- backend revalida policy antes da execução;
- API simulada vem antes da integração real;
- HTTP do CDM fica encapsulado em adapter;
- fake e real compartilham o mesmo contrato de domínio;
- nenhum outro sistema precisa de integração automática na primeira versão.

## 23. Narrativa da demonstração final

### Cenário permitido

```text
Pedro Miranda
Revenda - Matriz
  ↓
"Preciso de acesso ao CDM para solicitar materiais."
  ↓
requested_role = SOLICITANTE
  ↓
Triagem
  ↓
Knowledge
  ↓
Playbook
  ↓
Policy = REQUIRE_APPROVAL
  ↓
Confidence = HIGH
  ↓
Roteamento = técnico CDM
  ↓
PENDING_APPROVAL
  ↓
Técnico aprova
  ↓
Policy revalidada
  ↓
CDM API
  ↓
Acesso SOLICITANTE criado
  ↓
COMPLETED
```

### Cenário bloqueado

```text
"Preciso de acesso aprovador/admin/superadmin ao CDM."
  ↓
role privilegiada
  ↓
Triagem / normalização
  ↓
Playbook quando aplicável
  ↓
Policy = DENY
  ↓
DENIED_POLICY
  ↓
Registro de auditoria
  ↓
Nenhuma fila de aprovação
  ↓
Nenhuma chamada ao CDM
```

## 24. Resultado arquitetural esperado

A demonstração não deve parecer um chatbot com acesso a uma API.

Ela deve mostrar um agente corporativo capaz de:

```text
entender
-> consultar conhecimento
-> seguir playbook
-> normalizar pedido
-> aplicar policy
-> avaliar contexto
-> encaminhar
-> solicitar aprovação humana
-> executar por integração controlada
-> auditar resultado
```

A segurança da solução está na separação entre entendimento, policy, confiança, aprovação e execução.
