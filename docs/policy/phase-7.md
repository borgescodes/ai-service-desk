# Fase 7: Policy Engine

## Escopo

A Fase 7 recebe identidade confiavel, `TriageState` resolvido e um descriptor `ACTION_PROPOSAL` da Fase 6. Ela produz preparacao, contexto, policy e confidence. Nao cria request persistido, nao aprova, nao executa, nao chama HTTP, Ollama, CDMAdapter ou executor.

## Contratos

O fluxo e:

```text
SessionIdentity -> TriageState ANSWERED -> ACTION_PROPOSAL descriptor -> AccessRequestPreparation
READY -> AccessRequestContext -> PolicyEngine + ConfidenceAssessment
NEEDS_CLARIFICATION -> no PolicyDecision and no ConfidenceAssessment
```

O intent permanece `PROBLEMA_ACESSO` e a capability operacional e `CDM_ACCESS_REQUEST`.

## Normalizacao de role

A precedencia e fechada e usa exatamente:

```text
ROLE_CONFLICT
ROLE_PRIVILEGED_INTENT_MATCH
ROLE_PRIVILEGED_NOMINAL_MATCH
ROLE_SOLICITANTE_EXPLICIT
ROLE_PRIVILEGE_AMBIGUOUS
ROLE_GENERIC_ACCESS_DEFAULT_SOLICITANTE
ROLE_UNRESOLVED
```

Role deriva somente do texto do pedido. Identidade, area e confidence nao alteram role.

## Preparacao CDM-specific

`prepare_access_request(...)` aceita somente `CDM + PROBLEMA_ACESSO + CDM_ACCESS_REQUEST`. `purpose` e `TriageState.problem_text.strip()`. Descriptor diferente de `ACTION_PROPOSAL` ou provenance invalida falha explicitamente.

## Policy fail-closed

Matriz:

```text
CDM + CDM_ACCESS_REQUEST + SOLICITANTE -> REQUIRE_APPROVAL
CDM + CDM_ACCESS_REQUEST + APROVADOR -> DENY
CDM + CDM_ACCESS_REQUEST + ADMIN -> DENY
CDM + CDM_ACCESS_REQUEST + SUPERADMIN -> DENY
```

Contexto valido sem rule retorna `DENY / POLICY_NOT_FOUND`. Toda `PolicyRule` e validada em runtime antes de indexacao. Configuracao invalida falha com `PolicyConfigurationError / POLICY_RULE_INVALID`. Depois de todas as rules serem validas, chave duplicada falha com `PolicyConfigurationError / POLICY_RULE_CONFLICT`.

## Confidence separado

Confidence nunca entra na policy. Para CDM, os reason codes ficam sempre em ordem area, purpose:

```text
AREA_MATCH_REVENDA ou AREA_OUTSIDE_REVENDA
PURPOSE_MATCH_MATERIAL_REQUEST ou PURPOSE_NOT_CONFIRMED
```

Contexto valido fora do dominio CDM retorna `CONTEXT_NOT_CDM_ACCESS_REQUEST`. HIGH nunca aprova e LOW nunca nega SOLICITANTE.

## Provenance da Fase 6

O contexto preserva `knowledge_id`, `playbook_id`, `playbook_version`, `step_id` e `capability` do descriptor real da Fase 6.

## CLI

```powershell
$report = Join-Path $env:TEMP "phase7-policy-smoke-manual.json"
Remove-Item -Force $report -ErrorAction SilentlyContinue

python -m ai_service_desk policy-smoke `
  --cases tests/fixtures/phase7_policy_cases.jsonl `
  --report "$report"

$LASTEXITCODE
```

Saida esperada:

```text
POLICY SMOKE OK
Casos sinteticos: 15
0
```

## Privacidade

O relatorio persistido do smoke nao inclui identidade, email, area corporativa, texto bruto, purpose, capability, knowledge ID ou playbook ID. A fixture e totalmente sintetica e usa `@example.invalid`.

## Fronteira com a Fase 8

Persistencia, `request_id`, estado `PENDING_APPROVAL`, aprovacao/rejeicao humana, auditoria persistida e execucao ficam fora da Fase 7.

## Homologacao Dell

Despache `.github/workflows/phase7-policy-smoke.yml` com `target_ref` igual ao SHA final exato de 40 caracteres. O workflow, imediatamente apos `actions/checkout`, compara `git rev-parse HEAD` diretamente com `target_ref` e falha antes de instalar Python se houver divergencia. Nao existe dependencia de `PHASE7_CANDIDATE_SHA`.

## Baseline de regressao

O baseline historico imutavel possui `319` node IDs. Com `105` novos node IDs planejados, incluindo os dois casos runtime adicionais autorizados no Gate 5, o piso final inicial e `424` testes coletados. Nenhum dos 319 node IDs historicos pode desaparecer.
