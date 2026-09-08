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
        ↓
AccessRequestPreparation
        ↓ READY
AccessRequestContext
        ├──────────────→ PolicyEngine.evaluate(...)
        │                    ↓
        │              PolicyDecision
        │
        └──────────────→ assess_confidence(...)
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

Erros estruturais não são representados como `NEEDS_CLARIFICATION`. Descriptor corrompido, identidade inválida, contexto de triagem inválido ou tipo diferente de `ACTION_PROPOSAL` resultam em erro explícito de domínio.

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

Códigos mínimos:

```text
AREA_MATCH_REVENDA
PURPOSE_MATCH_MATERIAL_REQUEST
AREA_OUTSIDE_REVENDA
PURPOSE_NOT_CONFIRMED
```

Se o assessor receber um contexto válido fora do domínio CDM, pode usar um código determinístico adicional como `SYSTEM_NOT_CDM` e retornar `LOW`.

A apresentação humana desses códigos pertence a uma camada futura.

## 6. Preparação do AccessRequestContext

`access_request.py` é responsável por:

```text
SessionIdentity
TriageState relevante
ACTION_PROPOSAL descriptor
        ↓
validação estrutural
normalização determinística de requested_role
preservação de purpose
preservação de provenance
        ↓
AccessRequestPreparation
```

A preparação não consulta knowledge novamente e não resolve playbook novamente.

Pré-condições para o caso CDM da primeira demonstração:

```text
system = CDM
intent = PROBLEMA_ACESSO
capability = CDM_ACCESS_REQUEST
```

A capability vem do descriptor da Fase 6. Ela não é inferida do texto do usuário.

A preparação não deve ocultar contexts válidos futuros de outros sistemas. Se `system` ou `capability` forem estruturalmente válidos, mas não tiverem policy cadastrada, isso poderá chegar ao Policy Engine e será bloqueado como policy desconhecida.

A única exceção é `requested_role = UNKNOWN`, que permanece contexto incompleto e não vira `AccessRequestContext` pronto.

## 7. Policy Engine

`policy.py` contém regras imutáveis em código para a primeira demonstração.

Interface conceitual:

```python
PolicyEngine.evaluate(context: AccessRequestContext) -> PolicyDecision
```

O engine é puro, sem estado externo e sem I/O.

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

### 7.1 Fail-closed e distinção entre desconhecido e inválido

A Fase 7 distingue dois casos.

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

Exemplos de erro estrutural:

- `requester` inválido.
- `requested_role` fora do contrato concreto.
- `purpose` vazio.
- provenance ausente ou mal tipada.
- `playbook_version <= 0`.
- capability vazia.

Exemplos de válido mas não conhecido:

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

`PolicyEngine.evaluate(...)` não recebe `ConfidenceAssessment` nem valor de confidence.

`assess_confidence(...)` não recebe ou altera `PolicyDecision`.

A separação é estrutural, não apenas uma convenção.

Regra mínima da demonstração:

```text
requester.area contém o conceito lexical Revenda
+
system = CDM
+
purpose confirma solicitar materiais
-> HIGH
```

Para a primeira versão, `AREA_MATCH_REVENDA` pode ser determinado pela presença lexical determinística de `revenda` na área confiável da sessão.

`PURPOSE_MATCH_MATERIAL_REQUEST` deve exigir evidência lexical determinística de solicitação de materiais no `purpose`. Não há LLM, embedding ou inferência aberta.

Caso a área não corresponda:

```text
AREA_OUTSIDE_REVENDA
```

Caso a finalidade não seja confirmada:

```text
PURPOSE_NOT_CONFIRMED
```

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

"quero acesso aprovador"
-> APROVADOR

"quero poder aprovar solicitações"
-> APROVADOR

"admin e superadmin"
-> UNKNOWN

"perfil privilegiado"
-> UNKNOWN

"solicitante e admin"
-> UNKNOWN
```

Cobrir também:

- `ADMIN` nominal isolado.
- `SUPERADMIN` nominal isolado.
- `SOLICITANTE` explícito isolado.
- mais de uma role conhecida sempre gera `UNKNOWN`.
- expressão privilegiada ambígua nunca cai no default.
- acesso genérico usa `SOLICITANTE` somente depois de todas as verificações anteriores.
- texto sem evidência suficiente e sem acesso genérico resulta em `UNKNOWN`.
- role normalizer não recebe identidade como argumento ou, se a API de preparação possuir identidade, os testes provam que mudar identidade não muda o resultado da normalização para o mesmo pedido.

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

### 13.4 Policy

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

Cobrir idempotência lógica da decisão:

```text
mesmo AccessRequestContext avaliado repetidamente
-> mesmo PolicyDecision
```

### 13.5 Confidence

Cobrir:

```text
Revenda + CDM + finalidade de solicitar materiais
-> HIGH
-> AREA_MATCH_REVENDA
-> PURPOSE_MATCH_MATERIAL_REQUEST

Financeiro + CDM + finalidade de solicitar materiais
-> LOW
-> AREA_OUTSIDE_REVENDA
```

Cobrir finalidade não confirmada:

```text
Revenda + CDM + purpose sem evidência de materiais
-> LOW
-> PURPOSE_NOT_CONFIRMED
```

Os testes de confidence não devem importar ou executar regras internas de autorização para chegar ao nível de confidence.

### 13.6 Isolamento de execução

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

## 18. Critérios de aceite da Fase 7

A implementação futura só pode ser considerada concluída quando houver evidência de que:

- `SessionIdentity` é a única fonte de identidade confiável.
- chat não altera username, name, email ou area.
- role normalizer não usa identidade.
- role normalizer é lexical e determinístico.
- não existe LLM na normalização de role ou purpose.
- `purpose` preserva `TriageState.problem_text` como evidência do usuário.
- precedência fechada do normalizador está coberta por testes.
- conflito entre roles conhecidas produz `UNKNOWN`.
- intenção privilegiada inequívoca preserva role privilegiada.
- expressão privilegiada ambígua produz `UNKNOWN`.
- acesso genérico sem sinal de privilégio usa `SOLICITANTE` somente como última regra positiva.
- `UNKNOWN` nunca vira autorização implícita.
- `AccessRequestContext` preserva `knowledge_id`, `playbook_id`, `playbook_version`, `step_id` e `capability`.
- descriptor da Fase 6 é validado como `ACTION_PROPOSAL`.
- integração de teste usa o verdadeiro `action_proposal_descriptor(...)`.
- fixtures homologadas das Fases 4 e 6 permanecem inalteradas para o caso CDM.
- `CDM` é adicionado a `SYSTEM_ALIASES` de forma estritamente aditiva.
- `triage.py` permanece intacto.
- `SOLICITANTE` sempre produz `REQUIRE_APPROVAL` para `CDM_ACCESS_REQUEST`.
- `APROVADOR`, `ADMIN` e `SUPERADMIN` sempre produzem `DENY` para `CDM_ACCESS_REQUEST`.
- `SUPERADMIN` continua `DENY` mesmo com área Revenda e purpose perfeitamente coerente.
- `HIGH` nunca aprova automaticamente.
- `LOW` nunca converte `SOLICITANTE` em `DENY`.
- contexto estruturalmente válido sem policy produz `DENY / POLICY_NOT_FOUND`.
- contrato inválido ou corrompido produz erro explícito, não `POLICY_NOT_FOUND`.
- `ConfidenceAssessment` usa `reason_codes` estáveis.
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
pedido de acesso já triado
+
ação proposta por playbook aprovado
        ↓
role solicitada normalizada com fail-safe
        ↓
contexto com provenance completa
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
policy = REQUIRE_APPROVAL
confidence = HIGH
execução externa = nenhuma
```

Exemplo com contexto incomum:

```text
SessionIdentity.area = Financeiro
pedido = "preciso de acesso ao CDM para solicitar materiais"
requested_role = SOLICITANTE
policy = REQUIRE_APPROVAL
confidence = LOW
execução externa = nenhuma
```

Exemplo bloqueado:

```text
pedido = "preciso de superadmin no CDM"
requested_role = SUPERADMIN
policy = DENY
confidence = HIGH ou LOW sem efeito sobre policy
execução externa = nenhuma
```

A segurança da Fase 7 está na separação entre identidade confiável, normalização de pedido, provenance estruturada, policy determinística e confidence contextual. Aprovação, persistência e execução permanecem fora desta fronteira.