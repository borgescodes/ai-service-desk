# Fase 7: Policy Engine e contexto de solicitação

## 1. Objetivo

A Fase 7 introduz uma camada determinística de policy entre os resultados confiáveis das Fases 4, 5 e 6 e a futura criação de uma solicitação interna na Fase 8.

A fase deve transformar identidade de sessão confiável, contexto já resolvido pela triagem e provenance estruturada de um `ACTION_PROPOSAL` em três resultados de domínio:

```text
AccessRequestContext
PolicyDecision
ConfidenceAssessment
```

A Fase 7 não executa ações, não persiste solicitações, não aprova acessos e não chama o CDM.

A arquitetura escolhida é a Opção A, com três módulos de domínio:

```text
access_request.py
policy.py
confidence.py
```

Não haverá catálogo declarativo de policy nesta fase.

## 2. Fontes canônicas e restrições herdadas

Esta spec materializa as decisões registradas em:

```text
docs/roadmap.md
docs/architecture/2026-09-08-policy-execution-cdm-handoff.md
```

As fronteiras das fases anteriores permanecem válidas:

- Fase 4 é dona de knowledge `APPROVED`, provenance e retrieval seguro.
- Fase 5 é dona da triagem conversacional, de `TriageState` e da resolução de `intent`, `system`, `problem_text`, `entities` e confidence de classificação.
- Fase 6 é dona do vínculo determinístico entre knowledge e playbook e do descriptor estruturado de `ACTION_PROPOSAL`.
- Fase 7 não duplica retrieval, classificação, resolução de playbook ou execução.

Decisões congeladas para a primeira demonstração:

- CDM é a única integração externa executável futura.
- A plataforma hospedeira fornece a identidade do usuário.
- O ambiente local pode usar identidades sintéticas.
- Não existe autenticação paralela criada pelo agente.
- Roles CDM são `SOLICITANTE`, `APROVADOR`, `ADMIN` e `SUPERADMIN`.
- Somente `SOLICITANTE` pode seguir para aprovação humana.
- `APROVADOR`, `ADMIN` e `SUPERADMIN` são proibidos por este canal.
- Não existe `AUTO_APPROVE`.
- Confidence não concede nem retira autorização.
- Nenhum LLM decide autorização.
- Nenhum caminho da Fase 7 chama HTTP, executor ou CDM.

## 3. Arquitetura

Fluxo da Fase 7:

```text
SessionIdentity
+
TriageState resolvido
  intent
  system
  problem_text
+
ACTION_PROPOSAL descriptor da Fase 6
  knowledge_id
  playbook_id
  playbook_version
  step_id
  type
  capability
        ↓
prepare_access_request(...)
  CDM-specific na Fase 7
        ↓
AccessRequestPreparation
        ↓ READY
AccessRequestContext
        ├──────────────→ PolicyEngine.evaluate(...)
        │                    ↓
        │        validate_access_request_context(...)
        │                    ↓
        │              PolicyDecision
        │
        └──────────────→ assess_confidence(...)
                             ↓
                 validate_access_request_context(...)
                             ↓
                     ConfidenceAssessment
```

Se a role permanecer ambígua:

```text
AccessRequestPreparation.status = NEEDS_CLARIFICATION
requested_role = UNKNOWN
context = None
```

Nesse caso `PolicyEngine` não recebe um contexto autorizável.

`PolicyEngine.evaluate(...)` e `assess_confidence(...)` validam o `AccessRequestContext` de forma independente na própria entrada pública. Nenhum deles confia que o objeto necessariamente foi produzido por `prepare_access_request(...)` ou validado pela outra função. Essa propriedade é necessária para a revalidação futura da Fase 8, quando um contexto poderá ser reconstituído a partir de dados persistidos.

A fase termina após produzir contexto, policy e confidence. `request_id`, persistência, `PENDING_APPROVAL`, aprovação humana, revalidação antes de execução, `ExecutionEngine`, `CDMAdapter` e API do CDM pertencem às Fases 8 e 9.

## 4. Reuso obrigatório das Fases 4, 5 e 6

### 4.1 Fase 4

`knowledge.py` e `knowledge_retrieval.py` não devem ser alterados para acomodar a Fase 7.

A Fase 7 recebe knowledge já resolvida pelo fluxo anterior. Ela não lê índice, dataframe, embeddings, manifesto ou provenance de knowledge diretamente.

### 4.2 Fase 5

A Fase 7 reutiliza o contrato de triagem atual, em especial:

```text
TriageState.intent
TriageState.system
TriageState.problem_text
```

`PROBLEMA_ACESSO` permanece o intent canônico existente para acesso e permissões. A Fase 7 não cria uma segunda taxonomia pública chamada `REQUEST_ACCESS`.

A ação operacional é distinguida pela capability estruturada da Fase 6:

```text
system = CDM
intent = PROBLEMA_ACESSO
capability = CDM_ACCESS_REQUEST
```

`triage.py` permanece intacto.

A única alteração permitida na fronteira de classificação é estritamente aditiva em `classification.py`:

```python
"CDM": ("cdm",)
```

em `SYSTEM_ALIASES`.

Não devem ser alterados prompt, intents, recovery, heurísticas ou comportamento existente sem bloqueio técnico reproduzível e revisão arquitetural específica.

### 4.3 Fase 6

A Fase 7 consome o verdadeiro descriptor produzido por:

```python
action_proposal_descriptor(...)
```

O descriptor de entrada possui:

```text
knowledge_id
playbook_id
playbook_version
step_id
type
capability
```

A preparação valida obrigatoriamente:

```text
type == ACTION_PROPOSAL
```

O campo `type` não precisa permanecer duplicado em `AccessRequestContext`, pois a preparação aceita apenas descriptors validados como `ACTION_PROPOSAL`.

Os demais campos de provenance não podem ser descartados.

A Fase 7 nunca interpreta `title`, `description` ou `instruction` para descobrir uma ação ou autorização.

## 5. Contratos de domínio

Os contratos devem seguir o padrão atual do repositório, preferencialmente `@dataclass(frozen=True)` e valores simbólicos estáveis em strings. Não é necessária nova dependência.

### 5.1 SessionIdentity

Contrato:

```python
SessionIdentity(
    username: str,
    name: str,
    email: str,
    area: str,
)
```

Todos os campos são obrigatórios, textuais, não vazios e limitados em tamanho pelo domínio.

A origem desses campos é contexto confiável de sessão. Eles nunca são inferidos da conversa.

Regras obrigatórias:

- `username`, `name`, `email` e `area` não são extraídos de `problem_text`, `entities` ou qualquer outra fala do usuário.
- texto do chat não sobrescreve identidade confiável.
- `SessionIdentity.area`, nome, email e cargo nunca participam da normalização de `requested_role`.
- identidade participa de `requester`, confidence contextual e auditoria futura.

Exemplo obrigatório:

```text
SessionIdentity.area = Financeiro
chat = "sou da Revenda e preciso de acesso ao CDM"

area confiável = Financeiro
```

É proibida qualquer regra equivalente a:

```text
"ele é da Revenda, então deve ser SOLICITANTE"
```

### 5.2 RequestedRole e normalização

Valores possíveis durante preparação:

```text
SOLICITANTE
APROVADOR
ADMIN
SUPERADMIN
UNKNOWN
```

`UNKNOWN` é um estado de preparação. Ele não entra em um `AccessRequestContext` pronto para policy.

Na Fase 7, esse conjunto de roles e seu normalizador pertencem exclusivamente ao caso de acesso ao CDM. O normalizador não é um mecanismo genérico para sistemas futuros.

A normalização de role é lexical, determinística e baseada somente no conteúdo do pedido relacionado ao role.

Ela não usa:

```text
SessionIdentity.area
SessionIdentity.name
SessionIdentity.email
cargo
classification confidence
knowledge answer
playbook instruction
LLM
embedding
fuzzy matching
```

O texto original é preservado. Uma cópia normalizada com a função determinística já existente `normalize_text(...)` pode ser usada para comparação lexical.

### 5.3 Precedência fechada do RoleNormalizer

A ordem é normativa e fail-safe:

```text
1. conflito entre roles conhecidos
   -> UNKNOWN

2. intenção privilegiada inequívoca
   -> role privilegiado correspondente

3. role privilegiado nominal
   -> role correspondente

4. SOLICITANTE explícito
   -> SOLICITANTE

5. expressão ambígua de privilégio
   -> UNKNOWN

6. acesso genérico sem sinal de privilégio
   -> SOLICITANTE

7. qualquer caso restante sem determinação segura
   -> UNKNOWN
```

O default `SOLICITANTE` é a última regra positiva e existe porque o conteúdo do pedido representa acesso genérico sem sinal de privilégio. Identidade do solicitante não participa desse default.

Conflito entre roles conhecidos tem precedência sobre qualquer regra individual.

Casos normativos mínimos:

| Pedido | Resultado |
| --- | --- |
| `acesso ao CDM` | `SOLICITANTE` |
| `quero acesso aprovador` | `APROVADOR` |
| `quero poder aprovar solicitações` | `APROVADOR` |
| `admin e superadmin` | `UNKNOWN` |
| `perfil privilegiado` | `UNKNOWN` |
| `solicitante e admin` | `UNKNOWN` |

A primeira versão deve possuir léxico fechado suficiente para esses casos e para as quatro roles reais do CDM. Novos sinônimos não entram por aproximação ou modelo. Eles exigem extensão explícita acompanhada de teste.

Uma intenção privilegiada inequívoca de aprovação deve reconhecer pelo menos o conceito lexical de `aprovar solicitações` e suas variações estritamente definidas pela implementação, sem fuzzy matching.

Uma expressão como `perfil privilegiado`, sem role específica determinável, permanece `UNKNOWN`.

O normalizador só é chamado depois de `prepare_access_request(...)` comprovar que o pedido pertence ao domínio CDM suportado nesta fase. Sistemas ou capabilities futuros não podem reutilizar esse default `SOLICITANTE` sem uma extensão arquitetural explícita e seu próprio contrato de normalização.

### 5.4 Purpose

`purpose` preserva evidência do usuário. Ele não é produzido nem reescrito por LLM.

Na primeira versão:

```text
purpose = TriageState.problem_text.strip()
```

A preparação valida que o valor é texto não vazio dentro do limite aceito pela triagem.

A normalização lexical usada para role ou confidence opera sobre cópias do texto. O campo persistível de `purpose` mantém a evidência textual recebida, removendo apenas whitespace externo.

### 5.5 AccessRequestPreparation

Contrato conceitual:

```python
AccessRequestPreparation(
    status: Literal["READY", "NEEDS_CLARIFICATION"],
    requested_role: Literal[
        "SOLICITANTE",
        "APROVADOR",
        "ADMIN",
        "SUPERADMIN",
        "UNKNOWN",
    ],
    reason_code: str,
    context: AccessRequestContext | None,
)
```

Regras:

```text
role concreta
-> READY
-> context preenchido

UNKNOWN
-> NEEDS_CLARIFICATION
-> context = None
```

`UNKNOWN` não é convertido em `SOLICITANTE` por fallback.

`reason_code` possui conjunto fechado e corresponde exatamente à regra de precedência que encerrou a normalização:

| Regra | status | requested_role | reason_code |
| --- | --- | --- | --- |
| conflito entre roles conhecidos | NEEDS_CLARIFICATION | UNKNOWN | `ROLE_CONFLICT` |
| intenção privilegiada inequívoca | READY | role privilegiado correspondente | `ROLE_PRIVILEGED_INTENT_MATCH` |
| role privilegiado nominal | READY | role privilegiado correspondente | `ROLE_PRIVILEGED_NOMINAL_MATCH` |
| SOLICITANTE explícito | READY | SOLICITANTE | `ROLE_SOLICITANTE_EXPLICIT` |
| expressão ambígua de privilégio | NEEDS_CLARIFICATION | UNKNOWN | `ROLE_PRIVILEGE_AMBIGUOUS` |
| acesso genérico sem sinal de privilégio | READY | SOLICITANTE | `ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE` |
| caso restante sem determinação segura | NEEDS_CLARIFICATION | UNKNOWN | `ROLE_UNRESOLVED` |

Nenhum outro valor de `reason_code` é produzido por `AccessRequestPreparation` nesta fase.

Casos normativos de reason code:

```text
"acesso ao CDM"
-> SOLICITANTE
-> ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE

"quero acesso aprovador"
-> APROVADOR
-> ROLE_PRIVILEGED_NOMINAL_MATCH

"quero poder aprovar solicitações"
-> APROVADOR
-> ROLE_PRIVILEGED_INTENT_MATCH

"admin e superadmin"
-> UNKNOWN
-> ROLE_CONFLICT

"perfil privilegiado"
-> UNKNOWN
-> ROLE_PRIVILEGE_AMBIGUOUS

"solicitante e admin"
-> UNKNOWN
-> ROLE_CONFLICT
```

Erros estruturais ou pedidos fora do domínio CDM suportado não são representados como `AccessRequestPreparation`. Descriptor corrompido, identidade inválida, contexto de triagem inválido, tipo diferente de `ACTION_PROPOSAL` ou combinação fora do escopo CDM resultam em erro explícito de domínio.

### 5.6 AccessRequestContext

Contrato:

```python
AccessRequestContext(
    requester: SessionIdentity,
    system: str,
    intent: str,
    requested_role: Literal[
        "SOLICITANTE",
        "APROVADOR",
        "ADMIN",
        "SUPERADMIN",
    ],
    purpose: str,
    knowledge_id: str,
    playbook_id: str,
    playbook_version: int,
    step_id: str,
    capability: str,
)
```

O contexto preserva integralmente a provenance útil do `ACTION_PROPOSAL` da Fase 6:

```text
knowledge_id
playbook_id
playbook_version
step_id
capability
```

A Fase 8 poderá persistir exatamente esses valores sem reconstruir qual knowledge, versão de playbook ou step originou a solicitação.

`type` é validado como `ACTION_PROPOSAL` durante preparação e não é mantido no contexto para evitar duplicação de uma invariável já garantida.

A preparação deve rejeitar descriptors com campos ausentes, tipos inválidos, `playbook_version` não positivo, capability vazia ou `type` diferente de `ACTION_PROPOSAL`.

`access_request.py` deve expor uma validação estrutural reutilizável:

```python
validate_access_request_context(context: AccessRequestContext) -> None
```

Essa validação é independente da preparação e verifica pelo menos:

- `context` possui o tipo de domínio esperado.
- `requester` é uma `SessionIdentity` estruturalmente válida.
- `system`, `intent`, `purpose`, `knowledge_id`, `playbook_id`, `step_id` e `capability` são strings não vazias dentro dos limites do domínio.
- `requested_role` é uma das quatro roles concretas aceitas pelo contrato da Fase 7.
- `playbook_version` é inteiro positivo.

A validação estrutural não decide policy e não exige que exista regra para a combinação recebida. Um contexto pode ser estruturalmente válido e ainda assim ser desconhecido pela policy, caso em que o resultado continua sendo `DENY / POLICY_NOT_FOUND`.

A função também não aplica a normalização CDM. Ela apenas valida o objeto já construído. Isso permite que a Fase 8 revalide objetos reconstituídos sem refazer interpretação de texto.

### 5.7 PolicyDecision

Contrato:

```python
PolicyDecision(
    decision: Literal["REQUIRE_APPROVAL", "DENY"],
    policy_id: str,
    reason_code: str,
    reason: str,
)
```

Não existe `AUTO_APPROVE`.

`reason` é texto determinístico definido pela própria policy. Ele não é gerado por LLM.

### 5.8 ConfidenceAssessment

Contrato:

```python
ConfidenceAssessment(
    level: Literal["HIGH", "LOW"],
    reason_codes: tuple[str, ...],
)
```

`reason_codes` são códigos de máquina estáveis. Não há texto humano variável nesse contrato.

Conjunto fechado da Fase 7:

```text
CONTEXT_NOT_CDM_ACCESS_REQUEST
AREA_MATCH_REVENDA
AREA_OUTSIDE_REVENDA
PURPOSE_MATCH_MATERIAL_REQUEST
PURPOSE_NOT_CONFIRMED
```

A composição e a ordem são normativas.

Para contexto CDM elegível ao assessor:

```text
system = CDM
intent = PROBLEMA_ACESSO
capability = CDM_ACCESS_REQUEST
```

`reason_codes` contém exatamente dois códigos e sempre nesta ordem:

```text
1. dimensão de área
   AREA_MATCH_REVENDA
   ou
   AREA_OUTSIDE_REVENDA

2. dimensão de purpose
   PURPOSE_MATCH_MATERIAL_REQUEST
   ou
   PURPOSE_NOT_CONFIRMED
```

Portanto os únicos tuples válidos para contexto CDM da Fase 7 são:

```python
("AREA_MATCH_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST")
("AREA_MATCH_REVENDA", "PURPOSE_NOT_CONFIRMED")
("AREA_OUTSIDE_REVENDA", "PURPOSE_MATCH_MATERIAL_REQUEST")
("AREA_OUTSIDE_REVENDA", "PURPOSE_NOT_CONFIRMED")
```

O primeiro tuple resulta em `HIGH`. Os outros três resultam em `LOW`.

Para um `AccessRequestContext` estruturalmente válido que não corresponda exatamente ao trio CDM acima, o assessor não aplica heurísticas de Revenda ou materiais. O resultado é exatamente:

```python
ConfidenceAssessment(
    level="LOW",
    reason_codes=("CONTEXT_NOT_CDM_ACCESS_REQUEST",),
)
```

Não há códigos adicionais, omissões ou ordenação dinâmica nesta fase.

A apresentação humana desses códigos pertence a uma camada futura.

## 6. Preparação do AccessRequestContext

`access_request.py` é responsável por:

```text
SessionIdentity
TriageState relevante
ACTION_PROPOSAL descriptor
        ↓
validação estrutural de entrada
validação de escopo CDM da Fase 7
normalização determinística de requested_role CDM
preservação de purpose
preservação de provenance
        ↓
AccessRequestPreparation
```

A preparação não consulta knowledge novamente e não resolve playbook novamente.

Nesta fase, `prepare_access_request(...)` é explicitamente CDM-specific. Apesar do nome do contrato, ele não é um preparador genérico para sistemas ou capabilities futuras.

Antes de chamar qualquer regra do normalizador de role, deve comprovar exatamente:

```text
TriageState.system = CDM
TriageState.intent = PROBLEMA_ACESSO
descriptor.type = ACTION_PROPOSAL
descriptor.capability = CDM_ACCESS_REQUEST
```

A capability vem do descriptor da Fase 6. Ela não é inferida do texto do usuário.

Se `system`, `intent` ou `capability` não corresponderem ao trio suportado, `prepare_access_request(...)` encerra com erro explícito de domínio de pedido não suportado nesta fase. Ele não chama o RoleNormalizer, não aplica default `SOLICITANTE` e não produz `AccessRequestPreparation`.

Isso é diferente de um `AccessRequestContext` já existente e estruturalmente válido que seja entregue diretamente ao `PolicyEngine`. O engine continua responsável por bloquear combinações sem policy com `DENY / POLICY_NOT_FOUND`.

O RoleNormalizer da Fase 7 pertence ao domínio CDM. Sistemas ou capabilities futuros exigem preparador e normalização próprios antes de poderem produzir um contexto compatível. Nenhuma role CDM deve ser inferida para outro sistema apenas porque o texto contém uma expressão genérica de acesso.

A única saída não excepcional sem contexto é `requested_role = UNKNOWN`, que permanece contexto incompleto e produz `NEEDS_CLARIFICATION` com um dos reason codes fechados definidos na seção 5.5.

## 7. Policy Engine

`policy.py` contém regras imutáveis em código para a primeira demonstração.

Interface conceitual:

```python
PolicyEngine.evaluate(context: AccessRequestContext) -> PolicyDecision
```

O engine é puro, sem estado externo e sem I/O.

Toda chamada pública começa obrigatoriamente por:

```python
validate_access_request_context(context)
```

Essa validação ocorre mesmo quando o chamador afirma que o contexto veio de `prepare_access_request(...)`. A Fase 8 poderá reconstruir um `AccessRequestContext` persistido e chamar `evaluate(...)` diretamente para revalidação. Portanto a segurança do engine não depende da preparação original.

Se a validação estrutural falhar, `evaluate(...)` propaga um erro explícito de domínio e não produz `PolicyDecision`.

A chave de policy deve considerar:

```text
system
capability
requested_role
```

Isso evita que uma capability futura diferente no mesmo sistema receba acidentalmente a policy de criação de acesso.

Matriz inicial:

| system | capability | requested_role | decision |
| --- | --- | --- | --- |
| CDM | CDM_ACCESS_REQUEST | SOLICITANTE | REQUIRE_APPROVAL |
| CDM | CDM_ACCESS_REQUEST | APROVADOR | DENY |
| CDM | CDM_ACCESS_REQUEST | ADMIN | DENY |
| CDM | CDM_ACCESS_REQUEST | SUPERADMIN | DENY |

Decisão permitida:

```text
policy_id = CDM_SOLICITANTE_ACCESS
reason_code = CDM_SOLICITANTE_REQUIRES_HUMAN_APPROVAL
decision = REQUIRE_APPROVAL
```

Decisão para role privilegiada:

```text
policy_id = CDM_PRIVILEGED_ACCESS
reason_code = CDM_PRIVILEGED_ACCESS_NOT_ALLOWED
decision = DENY
```

### 7.1 Construção, validação runtime e conflito de chave

Mesmo sem catálogo externo, as regras em código não podem depender apenas de type hints nem de um `dict` literal que permita sobrescrita silenciosa de chave duplicada.

A implementação deve declarar as regras como uma sequência explícita de entradas. Antes de qualquer indexação, cada item da sequência é validado em runtime como `PolicyRule` completo. Type hints não substituem essa validação.

Cada `PolicyRule` deve satisfazer exatamente:

- o objeto é uma instância de `PolicyRule`;
- `system` é string não vazia com até 120 caracteres;
- `capability` é string simbólica válida com até 120 caracteres e respeita `^[A-Z][A-Z0-9_]{2,119}$`;
- `requested_role` é uma das roles concretas `SOLICITANTE`, `APROVADOR`, `ADMIN` ou `SUPERADMIN`;
- `decision` é exatamente `REQUIRE_APPROVAL` ou `DENY`;
- `policy_id` é código de máquina válido segundo `^[A-Z][A-Z0-9_]{2,119}$`;
- `reason_code` é código de máquina válido segundo `^[A-Z][A-Z0-9_]{2,119}$`;
- `reason` é string não vazia com até 500 caracteres.

Ao encontrar qualquer rule inválida, a construção falha antes de criar ou preencher o índice:

```text
PolicyConfigurationError
reason_code = POLICY_RULE_INVALID
```

O engine com configuração inválida não fica operacional e não produz `PolicyDecision`.

A construção é obrigatoriamente em duas passagens conceituais:

```text
1. validar todas as rules em runtime
2. somente depois indexar e validar unicidade das chaves
```

Essa ordem garante que uma rule inválida nunca seja mascarada por conflito de chave. Se uma sequência contém uma rule inválida e também uma chave duplicada, o resultado é `POLICY_RULE_INVALID` porque a indexação ainda não começou.

Depois que todas as rules estiverem válidas, o índice interno usa a chave:

```text
(system, capability, requested_role)
```

Ao encontrar duas rules válidas com a mesma chave, mesmo que tenham a mesma decisão, a construção deve falhar com erro explícito de configuração:

```text
PolicyConfigurationError
reason_code = POLICY_RULE_CONFLICT
```

Nenhuma das regras conflitantes prevalece. Não existe `last write wins`, merge ou sobrescrita silenciosa.

O engine com configuração conflitante não fica operacional e não pode produzir `REQUIRE_APPROVAL`. Esse comportamento é fail-closed e detectável por teste.

Os testes devem conseguir injetar tanto rules estruturalmente inválidas quanto uma sequência sintética de rules válidas com chave duplicada e observar os reason codes distintos.

### 7.2 Fail-closed e distinção entre desconhecido e inválido

A Fase 7 distingue quatro casos.

Contexto estruturalmente válido, porém sem regra conhecida:

```text
decision = DENY
reason_code = POLICY_NOT_FOUND
```

Um `policy_id` estável de fallback, por exemplo `FAIL_CLOSED_UNKNOWN_POLICY`, identifica essa decisão.

Isso inclui combinações válidas de `system`, `capability` e role concreta sem entrada na tabela de policy.

Entrada estruturalmente inválida ou corrompida:

```text
erro explícito de domínio
```

Não é permitido transformar corrupção de contrato em `POLICY_NOT_FOUND`.

Configuração de policy inválida:

```text
PolicyConfigurationError
reason_code = POLICY_RULE_INVALID
```

Isso inclui rule com `decision`, `requested_role`, `capability`, `system`, `policy_id`, `reason_code` ou `reason` fora do contrato runtime definido na seção 7.1.

Configuração de policy conflitante, depois de todas as rules passarem pela validação runtime:

```text
PolicyConfigurationError
reason_code = POLICY_RULE_CONFLICT
```

Não é permitido indexar configuração inválida nem escolher silenciosamente uma das regras conflitantes.

Exemplos de erro estrutural do contexto:

- `requester` inválido.
- `requested_role` fora do contrato concreto.
- `purpose` vazio.
- provenance ausente ou mal tipada.
- `playbook_version <= 0`.
- capability vazia.

Exemplos de contexto válido mas não conhecido:

- `system` textual válido sem policy cadastrada.
- capability simbólica válida sem policy cadastrada.
- combinação válida de sistema, capability e role sem regra.

Nunca existe fallback equivalente a:

```text
não encontrei policy, então pode continuar
```

## 8. Confidence separado da autorização

`confidence.py` possui interface independente:

```python
assess_confidence(context: AccessRequestContext) -> ConfidenceAssessment
```

Toda chamada pública começa obrigatoriamente por:

```python
validate_access_request_context(context)
```

Essa chamada é independente da validação feita pelo `PolicyEngine.evaluate(...)`. `assess_confidence(...)` não assume que policy já foi executada, nem que a preparação original ocorreu no mesmo processo.

Se a validação estrutural falhar, `assess_confidence(...)` produz erro explícito de domínio e não retorna um `ConfidenceAssessment`.

`PolicyEngine.evaluate(...)` não recebe `ConfidenceAssessment` nem valor de confidence.

`assess_confidence(...)` não recebe ou altera `PolicyDecision`.

A separação é estrutural, não apenas uma convenção.

As regras de área e finalidade desta fase são CDM-specific. Elas só se aplicam quando:

```text
system = CDM
intent = PROBLEMA_ACESSO
capability = CDM_ACCESS_REQUEST
```

Se qualquer uma dessas três condições não for satisfeita em um contexto estruturalmente válido, o resultado é `LOW` com exatamente:

```python
reason_codes = ("CONTEXT_NOT_CDM_ACCESS_REQUEST",)
```

Nesse caso nenhuma regra de Revenda ou materiais é avaliada.

Para o contexto CDM suportado, a regra mínima da demonstração é:

```text
requester.area contém o conceito lexical Revenda
+
purpose confirma solicitar materiais
-> HIGH
```

Para a primeira versão, `AREA_MATCH_REVENDA` pode ser determinado pela presença lexical determinística de `revenda` na área confiável da sessão.

`PURPOSE_MATCH_MATERIAL_REQUEST` deve exigir evidência lexical determinística de solicitação de materiais no `purpose`. Não há LLM, embedding ou inferência aberta.

A composição é feita em duas dimensões, sempre na mesma ordem:

```text
area_code = AREA_MATCH_REVENDA
            ou AREA_OUTSIDE_REVENDA

purpose_code = PURPOSE_MATCH_MATERIAL_REQUEST
               ou PURPOSE_NOT_CONFIRMED

reason_codes = (area_code, purpose_code)
```

`HIGH` exige simultaneamente:

```python
reason_codes == (
    "AREA_MATCH_REVENDA",
    "PURPOSE_MATCH_MATERIAL_REQUEST",
)
```

Qualquer outro tuple CDM válido resulta em `LOW`.

Invariantes obrigatórias:

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

Um caso com área Revenda e purpose perfeito nunca modifica a proibição de `SUPERADMIN`.

## 9. Ausência de LLM, HTTP e executor

A Fase 7 não adiciona nem chama:

```text
OllamaClient
chat completion
embedding
requests
HTTP client
subprocess
shell
PowerShell
executor
ExecutionEngine
CDMAdapter
CDM API
```

Role e purpose são derivados deterministicamente de dados já disponíveis.

A capability é recebida estruturada da Fase 6.

Nenhuma decisão da Fase 7 depende da disponibilidade do Ollama.

## 10. Integração com a Fase 8

A Fase 7 entrega dados suficientes para a Fase 8 criar e auditar uma solicitação sem reconstruir contexto anterior.

Dados que já devem estar preservados:

```text
requester
system
intent
requested_role
purpose
knowledge_id
playbook_id
playbook_version
step_id
capability
policy decision
policy_id
reason_code
confidence level
confidence reason_codes
```

A Fase 8 será responsável por adicionar pelo menos:

```text
request_id
estado persistido
PENDING_APPROVAL
aprovação ou rejeição humana
decided_by
decided_at
auditoria persistida
revalidação de policy
ExecutionEngine com executor fake
```

Na futura revalidação, a Fase 8 deve usar os dados preservados da solicitação e o mesmo contrato de `PolicyEngine`. Ela não deve reconstruir provenance procurando novamente o playbook corrente, pois a versão corrente pode ter mudado desde a criação da solicitação.

A Fase 8 poderá reconstruir `AccessRequestContext` a partir da solicitação persistida e chamar `PolicyEngine.evaluate(...)` diretamente. Por isso `evaluate(...)` valida o contexto independentemente de `prepare_access_request(...)`. Se a Fase 8 também recalcular confidence, `assess_confidence(...)` faz sua própria validação independente.

A Fase 7 não implementa nenhuma dessas responsabilidades da Fase 8.

## 11. Alteração aditiva em classification.py

A inclusão de CDM em `SYSTEM_ALIASES` segue TDD e deve ser a única mudança de comportamento prevista na classificação nesta fase.

Antes da alteração, deve existir um teste RED que espere:

```python
explicit_systems("acesso ao CDM") == ["CDM"]
```

No baseline atual esse teste deve falhar porque CDM ainda não está registrado.

Somente depois do RED é adicionada a entrada:

```python
"CDM": ("cdm",)
```

O GREEN deve provar no mínimo:

```text
CDM isolado
-> CDM

CDM + CIGAM
-> contexto multi-sistema

aliases anteriores
-> continuam funcionando
```

Nenhum teste anterior de classificação ou triagem pode ser removido para acomodar a mudança.

`triage.py` permanece intacto.

## 12. Integração de teste com a Fase 6

As fixtures homologadas das Fases 4 e 6 não serão alteradas apenas para incluir CDM:

```text
knowledge/phase4_synthetic_faq.jsonl
playbooks/phase6_synthetic_playbooks.jsonl
```

Para provar o contrato da Fase 6, um teste da própria Fase 7 constrói em memória um playbook sintético mínimo e passa um step pelo verdadeiro:

```python
action_proposal_descriptor(...)
```

Exemplo conceitual de dados sintéticos:

```text
knowledge_id = KB-SYN-CDM-ACCESS-001
playbook_id = PB-SYN-CDM-ACCESS-001
playbook_version = 1
step_id = STEP-CDM-ACCESS-01
type = ACTION_PROPOSAL
capability = CDM_ACCESS_REQUEST
```

O teste deve provar que `prepare_access_request(...)` preserva exatamente:

```text
knowledge_id
playbook_id
playbook_version
step_id
capability
```

E deve provar que `type` diferente de `ACTION_PROPOSAL` é rejeitado antes da criação do contexto.

Nenhum teste da Fase 7 interpreta `instruction` para descobrir a capability.

## 13. Matriz mínima de testes

### 13.1 RoleNormalizer

Casos obrigatórios:

```text
"acesso ao CDM"
-> SOLICITANTE
-> ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE

"quero acesso aprovador"
-> APROVADOR
-> ROLE_PRIVILEGED_NOMINAL_MATCH

"quero poder aprovar solicitações"
-> APROVADOR
-> ROLE_PRIVILEGED_INTENT_MATCH

"admin e superadmin"
-> UNKNOWN
-> ROLE_CONFLICT

"perfil privilegiado"
-> UNKNOWN
-> ROLE_PRIVILEGE_AMBIGUOUS

"solicitante e admin"
-> UNKNOWN
-> ROLE_CONFLICT
```

Cobrir também:

- `ADMIN` nominal isolado com `ROLE_PRIVILEGED_NOMINAL_MATCH`.
- `SUPERADMIN` nominal isolado com `ROLE_PRIVILEGED_NOMINAL_MATCH`.
- `SOLICITANTE` explícito isolado com `ROLE_SOLICITANTE_EXPLICIT`.
- mais de uma role conhecida sempre gera `UNKNOWN / ROLE_CONFLICT`.
- expressão privilegiada ambígua nunca cai no default e usa `ROLE_PRIVILEGE_AMBIGUOUS`.
- acesso genérico usa `SOLICITANTE` somente depois de todas as verificações anteriores e usa `ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE`.
- texto sem evidência suficiente e sem acesso genérico resulta em `UNKNOWN / ROLE_UNRESOLVED`.
- role normalizer não recebe identidade como argumento ou, se a API de preparação possuir identidade, os testes provam que mudar identidade não muda o resultado da normalização para o mesmo pedido.
- `prepare_access_request(...)` não chama o normalizador para sistema diferente de CDM.
- `prepare_access_request(...)` não chama o normalizador para capability diferente de `CDM_ACCESS_REQUEST`.
- um pedido genérico de acesso para sistema futuro não recebe `SOLICITANTE` por reutilização do default CDM.

### 13.2 Identidade

Casos obrigatórios:

```text
SessionIdentity.area = Financeiro
chat contém "sou da Revenda"
-> requester.area permanece Financeiro
```

Cobrir também:

- nome do chat não substitui `requester.name`.
- email do chat não substitui `requester.email`.
- identidade estruturalmente inválida é rejeitada.

### 13.3 Provenance

Cobrir:

- descriptor real de `action_proposal_descriptor(...)` com `CDM_ACCESS_REQUEST`.
- `knowledge_id` preservado.
- `playbook_id` preservado.
- `playbook_version` preservado.
- `step_id` preservado.
- `capability` preservada.
- `type != ACTION_PROPOSAL` rejeitado.
- descriptor com campo obrigatório ausente rejeitado.
- versão não positiva rejeitada.

### 13.4 Validação independente do contexto

Cobrir:

- `PolicyEngine.evaluate(...)` rejeita `AccessRequestContext` estruturalmente inválido mesmo sem passar por `prepare_access_request(...)`.
- `assess_confidence(...)` rejeita o mesmo tipo de contexto inválido independentemente de policy.
- um contexto reconstituído válido pode ser entregue diretamente a `PolicyEngine.evaluate(...)`.
- um contexto reconstituído válido pode ser entregue diretamente a `assess_confidence(...)`.
- `validate_access_request_context(...)` não exige existência de policy.

### 13.5 Policy

Cobrir matriz completa:

```text
CDM + CDM_ACCESS_REQUEST + SOLICITANTE
-> REQUIRE_APPROVAL

CDM + CDM_ACCESS_REQUEST + APROVADOR
-> DENY

CDM + CDM_ACCESS_REQUEST + ADMIN
-> DENY

CDM + CDM_ACCESS_REQUEST + SUPERADMIN
-> DENY
```

Casos críticos adicionais:

```text
SUPERADMIN + área Revenda + purpose perfeito
-> DENY

SOLICITANTE + LOW
-> REQUIRE_APPROVAL

SOLICITANTE + HIGH
-> REQUIRE_APPROVAL
```

Policy desconhecida:

```text
contexto estruturalmente válido sem regra
-> DENY
-> POLICY_NOT_FOUND
```

Contrato inválido:

```text
-> erro explícito
```

Configuração inválida de rule:

```text
rule com decision, requested_role, capability ou campo estrutural fora do contrato
-> PolicyConfigurationError
-> POLICY_RULE_INVALID
-> nenhuma indexação ou decisão produzida
```

Os testes de configuração inválida devem cobrir pelo menos `decision`, `requested_role`, `capability`, `system`, `policy_id`, `reason_code` e `reason`, incluindo tipo ou valor inválido conforme o contrato da seção 7.1.

Conflito de rules válidas:

```text
duas rules válidas com a mesma chave
(system, capability, requested_role)
-> PolicyConfigurationError
-> POLICY_RULE_CONFLICT
-> nenhuma decisão produzida
```

Um teste combinado deve provar a ordem fail-closed da construção:

```text
sequência contém rule inválida e também chave duplicada
-> POLICY_RULE_INVALID
```

Isso demonstra que todas as rules são validadas antes da indexação e que conflito não mascara configuração inválida.

Cobrir idempotência lógica da decisão:

```text
mesmo AccessRequestContext avaliado repetidamente
-> mesmo PolicyDecision
```

### 13.6 Confidence

Cobrir exatamente:

```python
Revenda + CDM + finalidade de solicitar materiais
-> ConfidenceAssessment(
       level="HIGH",
       reason_codes=(
           "AREA_MATCH_REVENDA",
           "PURPOSE_MATCH_MATERIAL_REQUEST",
       ),
   )

Revenda + CDM + purpose sem evidência de materiais
-> ConfidenceAssessment(
       level="LOW",
       reason_codes=(
           "AREA_MATCH_REVENDA",
           "PURPOSE_NOT_CONFIRMED",
       ),
   )

Financeiro + CDM + finalidade de solicitar materiais
-> ConfidenceAssessment(
       level="LOW",
       reason_codes=(
           "AREA_OUTSIDE_REVENDA",
           "PURPOSE_MATCH_MATERIAL_REQUEST",
       ),
   )

Financeiro + CDM + purpose sem evidência de materiais
-> ConfidenceAssessment(
       level="LOW",
       reason_codes=(
           "AREA_OUTSIDE_REVENDA",
           "PURPOSE_NOT_CONFIRMED",
       ),
   )
```

Para contexto estruturalmente válido fora do trio CDM suportado:

```python
-> ConfidenceAssessment(
       level="LOW",
       reason_codes=("CONTEXT_NOT_CDM_ACCESS_REQUEST",),
   )
```

Os testes devem provar a ordem `área` antes de `purpose` e que nenhum código é omitido quando o contexto pertence ao caso CDM.

Os testes de confidence não devem importar ou executar regras internas de autorização para chegar ao nível de confidence.

### 13.7 Isolamento de execução

Deve existir teste que prove que os caminhos da Fase 7 não chamam integração externa ou executor.

Pontos proibidos podem ser substituídos por doubles que falham imediatamente se chamados.

A evidência esperada é zero chamadas a HTTP, subprocesso, Ollama ou executor.

## 14. Smoke sintético da Fase 7

A Fase 7 deve possuir smoke determinístico próprio, sem Ollama.

Arquivos previstos:

```text
src/ai_service_desk/engine/policy_smoke.py
tests/fixtures/phase7_policy_cases.jsonl
.github/workflows/phase7-policy-smoke.yml
```

O smoke cobre pelo menos a matriz mínima de segurança do handoff canônico e os casos críticos desta spec.

O relatório persistido deve conter somente metadados sintéticos necessários à verificação, por exemplo:

```text
case_name
actual_role
actual_decision
reason_code
confidence
passed
```

O relatório não deve persistir:

```text
nome real
email real
area corporativa real
texto bruto de usuário
purpose bruto
knowledge answer
playbook instruction
credencial
```

As identidades do smoke são sintéticas.

## 15. Arquivos previstos para implementação futura

Novos arquivos de produção:

```text
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/confidence.py
src/ai_service_desk/engine/policy_smoke.py
```

Novos testes e fixtures:

```text
tests/engine/test_access_request.py
tests/engine/test_policy.py
tests/engine/test_confidence.py
tests/engine/test_policy_smoke.py
tests/fixtures/phase7_policy_cases.jsonl
```

Novo workflow:

```text
.github/workflows/phase7-policy-smoke.yml
```

Alterações pequenas previstas:

```text
src/ai_service_desk/engine/classification.py
src/ai_service_desk/cli.py
tests/engine/test_classification.py
tests/test_workflows.py
```

`tests/engine/test_triage.py` só deve mudar se for necessário adicionar uma regressão de reconhecimento de CDM sem alterar `triage.py`. Nenhuma mudança de comportamento de triagem é parte da fase.

Arquivos protegidos que não devem mudar sem bloqueio técnico reproduzível:

```text
src/ai_service_desk/engine/knowledge.py
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/engine/triage.py
src/ai_service_desk/engine/playbook.py
src/ai_service_desk/engine/playbook_resolution.py
knowledge/phase4_synthetic_faq.jsonl
playbooks/phase6_synthetic_playbooks.jsonl
```

## 16. Baseline quantitativo e regressão

A Fase 6 encerrou com baseline de:

```text
319 testes
```

A implementação da Fase 7 deve preservar todos os testes anteriores e adicionar seus próprios testes.

Critério quantitativo:

```text
total final >= 319 + novos testes adicionados pela Fase 7
```

Nenhum teste anterior pode ser apagado, desabilitado, marcado como skip ou fundido artificialmente apenas para manter a suíte verde.

A implementação deve registrar evidência de coleta e execução da suíte completa antes de declarar a fase concluída.

Além do `pytest`, permanecem os gates normativos do repositório:

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

## 17. Riscos de regressão e mitigação

### 17.1 Segunda taxonomia de intent

Risco: criar `REQUEST_ACCESS` em paralelo a `PROBLEMA_ACESSO`.

Mitigação: reutilizar `PROBLEMA_ACESSO` e usar `CDM_ACCESS_REQUEST` como capability estruturada.

### 17.2 Role derivada de identidade

Risco: inferir `SOLICITANTE` porque a pessoa pertence à Revenda.

Mitigação: role normalizer usa somente conteúdo do pedido. Identity não participa da API de normalização de role.

### 17.3 Default inseguro

Risco: sinais de privilégio não reconhecidos caírem em `SOLICITANTE`.

Mitigação: precedência fechada, conflitos primeiro, ambiguidade privilegiada antes do default, default apenas para acesso genérico sem sinal de privilégio.

### 17.4 Confidence influenciar autorização

Risco: `HIGH` gerar aprovação automática ou `LOW` gerar bloqueio.

Mitigação: APIs e módulos separados. `PolicyEngine.evaluate(...)` não recebe confidence. `assess_confidence(...)` não recebe policy.

### 17.5 Provenance perdida entre Fase 6 e Fase 8

Risco: persistir somente `playbook_id` e depois tentar descobrir qual versão e step originaram a solicitação.

Mitigação: `AccessRequestContext` preserva `knowledge_id`, `playbook_id`, `playbook_version`, `step_id` e `capability` desde a Fase 7.

### 17.6 Reinterpretação de texto de playbook

Risco: policy procurar palavras em `instruction`.

Mitigação: capability vem do descriptor estruturado verdadeiro da Fase 6. Texto editorial não entra na decisão.

### 17.7 Regressão de classificação

Risco: inclusão de CDM alterar heurísticas ou aliases existentes.

Mitigação: alteração estritamente aditiva em `SYSTEM_ALIASES`, teste RED antes da alteração e regressões para CDM isolado, CDM com CIGAM e aliases anteriores.

### 17.8 Antecipação da Fase 8

Risco: Fase 7 começar a persistir request, aprovação ou auditoria completa.

Mitigação: Fase 7 produz objetos estruturados em memória. Persistência e máquina de estados começam na Fase 8.

### 17.9 Antecipação da Fase 9

Risco: introduzir HTTP, fake CDM ou adapter para provar o fluxo.

Mitigação: nenhuma dependência de CDM existe na Fase 7. O smoke é totalmente local e determinístico.

### 17.10 Normalizador CDM aplicado a domínio futuro

Risco: um sistema futuro reutilizar `prepare_access_request(...)` e receber `SOLICITANTE` pelo default CDM.

Mitigação: o preparador da Fase 7 exige exatamente `CDM + PROBLEMA_ACESSO + CDM_ACCESS_REQUEST` antes de normalizar role. Outro domínio recebe erro de pedido não suportado e precisa de preparador próprio.

### 17.11 Revalidação confiar na preparação original

Risco: Fase 8 reconstruir contexto persistido inválido e `PolicyEngine` assumir que ele já foi validado na criação.

Mitigação: `PolicyEngine.evaluate(...)` e `assess_confidence(...)` chamam `validate_access_request_context(...)` independentemente em toda entrada pública.

### 17.12 Regra duplicada sobrescrita silenciosamente

Risco: duas policies com a mesma chave entrarem em um mapa e a última sobrescrever a anterior.

Mitigação: índice de rules é construído por rotina que rejeita chave duplicada com `PolicyConfigurationError / POLICY_RULE_CONFLICT` antes de qualquer decisão.

### 17.13 Type hints tratados como validação de policy

Risco: uma `PolicyRule` construída em runtime com `decision`, role, capability ou campo estrutural inválido chegar ao índice porque a anotação de tipo não executa validação.

Mitigação: todas as rules são validadas em runtime em primeira passagem. Qualquer violação produz `PolicyConfigurationError / POLICY_RULE_INVALID`; somente uma sequência integralmente válida segue para indexação e checagem de conflitos.

## 18. Critérios de aceite da Fase 7

A implementação futura só pode ser considerada concluída quando houver evidência de que:

- `SessionIdentity` é a única fonte de identidade confiável.
- chat não altera username, name, email ou area.
- role normalizer não usa identidade.
- role normalizer é lexical e determinístico.
- o role normalizer da Fase 7 só é aplicado ao domínio `CDM + PROBLEMA_ACESSO + CDM_ACCESS_REQUEST`.
- sistemas e capabilities futuros não recebem roles CDM por meio de `prepare_access_request(...)`.
- não existe LLM na normalização de role ou purpose.
- `purpose` preserva `TriageState.problem_text` como evidência do usuário.
- precedência fechada do normalizador está coberta por testes.
- cada saída de `AccessRequestPreparation` usa exatamente um dos sete `reason_code` definidos na seção 5.5.
- conflito entre roles conhecidas produz `UNKNOWN / ROLE_CONFLICT`.
- intenção privilegiada inequívoca preserva role privilegiada e usa `ROLE_PRIVILEGED_INTENT_MATCH`.
- expressão privilegiada ambígua produz `UNKNOWN / ROLE_PRIVILEGE_AMBIGUOUS`.
- acesso genérico sem sinal de privilégio usa `SOLICITANTE` somente como última regra positiva e usa `ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE`.
- `UNKNOWN` nunca vira autorização implícita.
- `AccessRequestContext` preserva `knowledge_id`, `playbook_id`, `playbook_version`, `step_id` e `capability`.
- descriptor da Fase 6 é validado como `ACTION_PROPOSAL`.
- integração de teste usa o verdadeiro `action_proposal_descriptor(...)`.
- fixtures homologadas das Fases 4 e 6 permanecem inalteradas para o caso CDM.
- `CDM` é adicionado a `SYSTEM_ALIASES` de forma estritamente aditiva.
- `triage.py` permanece intacto.
- `PolicyEngine.evaluate(...)` valida `AccessRequestContext` independentemente da preparação original.
- `assess_confidence(...)` valida `AccessRequestContext` independentemente da preparação e de policy.
- toda `PolicyRule` é validada em runtime antes da indexação.
- rule inválida é detectada como `PolicyConfigurationError / POLICY_RULE_INVALID` e impede construção do engine.
- regra de policy duplicada, depois de validação runtime bem-sucedida, é detectada como `PolicyConfigurationError / POLICY_RULE_CONFLICT` e nunca sobrescrita silenciosamente.
- configuração contendo rule inválida e também chave duplicada falha como `POLICY_RULE_INVALID`, comprovando validação antes da indexação.
- `SOLICITANTE` sempre produz `REQUIRE_APPROVAL` para `CDM_ACCESS_REQUEST`.
- `APROVADOR`, `ADMIN` e `SUPERADMIN` sempre produzem `DENY` para `CDM_ACCESS_REQUEST`.
- `SUPERADMIN` continua `DENY` mesmo com área Revenda e purpose perfeitamente coerente.
- `HIGH` nunca aprova automaticamente.
- `LOW` nunca converte `SOLICITANTE` em `DENY`.
- contexto estruturalmente válido sem policy produz `DENY / POLICY_NOT_FOUND`.
- contrato inválido ou corrompido produz erro explícito, não `POLICY_NOT_FOUND`.
- `ConfidenceAssessment` usa somente os `reason_codes` fechados da seção 5.8.
- contexto CDM produz exatamente dois reason codes na ordem área, purpose.
- contexto válido fora do trio CDM produz exatamente `LOW / (CONTEXT_NOT_CDM_ACCESS_REQUEST,)` e não aplica heurísticas CDM.
- policy e confidence permanecem estruturalmente separados.
- nenhum caminho chama Ollama, HTTP, subprocesso, executor ou CDM.
- nenhum comportamento das Fases 4, 5 e 6 é duplicado sem necessidade.
- os 319 testes do baseline permanecem presentes e passando, somados aos novos testes da Fase 7.
- lint e format checks permanecem verdes.

## 19. Resultado arquitetural esperado

Ao final da Fase 7, o sistema deve conseguir demonstrar de forma determinística:

```text
identidade confiável
+
pedido de acesso ao CDM já triado
+
ação proposta por playbook aprovado
        ↓
validação de que o pedido pertence ao domínio CDM suportado
        ↓
role CDM solicitada normalizada com fail-safe
        ↓
contexto com provenance completa
        ↓
validação independente do contexto
        ↓
policy determinística e fail-closed
        +
confidence contextual independente
```

Exemplo permitido:

```text
SessionIdentity.area = Revenda
pedido = "preciso de acesso ao CDM para solicitar materiais"
requested_role = SOLICITANTE
preparation_reason = ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE
policy = REQUIRE_APPROVAL
confidence = HIGH
confidence_reason_codes = (
    AREA_MATCH_REVENDA,
    PURPOSE_MATCH_MATERIAL_REQUEST,
)
execução externa = nenhuma
```

Exemplo com contexto incomum:

```text
SessionIdentity.area = Financeiro
pedido = "preciso de acesso ao CDM para solicitar materiais"
requested_role = SOLICITANTE
preparation_reason = ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE
policy = REQUIRE_APPROVAL
confidence = LOW
confidence_reason_codes = (
    AREA_OUTSIDE_REVENDA,
    PURPOSE_MATCH_MATERIAL_REQUEST,
)
execução externa = nenhuma
```

Exemplo bloqueado:

```text
pedido = "preciso de superadmin no CDM"
requested_role = SUPERADMIN
preparation_reason = ROLE_PRIVILEGED_NOMINAL_MATCH
policy = DENY
confidence = HIGH ou LOW sem efeito sobre policy
execução externa = nenhuma
```

A segurança da Fase 7 está na separação entre identidade confiável, preparação CDM-specific, normalização de pedido, provenance estruturada, validação independente de contexto, policy determinística e confidence contextual. Aprovação, persistência e execução permanecem fora desta fronteira.