# Fase 6: Playbooks declarativos

A Fase 6 adiciona conteúdo operacional estruturado após a triagem, sem executar ações. O fluxo é determinístico:

```text
triagem -> knowledge APPROVED -> knowledge_id -> playbook declarativo
```

A associação é exclusivamente por `knowledge_id`. Não existe retrieval semântico de playbooks, segunda classificação, LLM, embedding ou escolha probabilística.

## Lifecycle e cardinalidade

Os status de source são `DRAFT`, `APPROVED` e `RETIRED`.

- somente `APPROVED` fornece conteúdo operacional;
- `DRAFT` e `RETIRED` aparecem no catálogo somente como metadata mínima de vínculo, sem título, descrição, steps, instruction ou capability;
- um knowledge APPROVED pode ter de zero a um playbook APPROVED;
- um playbook APPROVED pode referenciar um ou mais knowledge IDs APPROVED;
- dois playbooks APPROVED para o mesmo `knowledge_id` são erro de integridade, sem prioridade ou desempate.

## Steps

Os tipos válidos são:

- `INSTRUCTION`: orientação manual, sem capability;
- `CHECK`: verificação humana, sem leitura automática do equipamento;
- `ACTION_PROPOSAL`: possibilidade de ação futura, com `capability` simbólica.

`capability` é um identificador de máquina, por exemplo `DEMO_PRINT_QUEUE_CLEAR`. Ela não é comando, script ou executor e não é mostrada automaticamente ao usuário.

A Fase 6 não aceita campos de execução como `command`, `script`, `powershell`, `shell`, `executable`, `args`, URL de API, método HTTP, credencial ou token.

## Catálogo e provenance fail-closed

`playbook-build` usa um índice `APPROVED_KNOWLEDGE` já validado por `load_knowledge_index(...)`. Um mapping fornecido pelo caller não substitui essa cadeia de confiança.

O build produz localmente:

```text
playbook-catalog.json
playbook-provenance.json
```

O catálogo é escrito primeiro, relido e validado, e somente depois o sidecar de provenance é escrito. O sidecar vincula o source de playbooks, o hash canônico do catálogo e a provenance corrente do índice de knowledge.

Na carga, sidecar ausente, schema inválido, domínio incorreto, hash divergente, catálogo truncado/adulterado, binding de knowledge divergente ou conflito de ownership causam erro explícito. Corrupção nunca é convertida em `KNOWLEDGE_ONLY` ou `PLAYBOOK_UNAVAILABLE`.

## Resultados de máquina

Os resultados normais da Fase 6 são:

```text
KNOWLEDGE_ONLY / NO_PLAYBOOK
PLAYBOOK_FOUND / MATCH
PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED
PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED
```

O resultado próprio da Fase 6 contém somente `status`, `reason`, `knowledge_id` e `playbook`. O objeto de knowledge da Fase 5 continua pertencendo ao caller/orquestrador.

Para um `ACTION_PROPOSAL`, a projeção para a Fase 7 contém:

```text
knowledge_id
playbook_id
playbook_version
step_id
type
capability
```

O formatter de usuário mostra apenas título, descrição, título/instrução dos steps e indicação textual de ação proposta. Ele não expõe capability, reviewer, hashes ou lifecycle interno e não afirma que a ação está autorizada ou executada.

## Fronteira Fase 7 e Fase 8

A Fase 7, Policy Engine, poderá consumir a `capability` estruturada para decidir política. Ela não deve reinterpretar o texto de `instruction` para descobrir uma ação.

A Fase 8 poderá mapear uma capability previamente autorizada para uma implementação controlada. A Fase 6 não possui esse mapeamento nem chama executor algum.

## CLI

Validar source sem IA:

```powershell
python -m ai_service_desk playbook-validate `
  --file playbooks/phase6_synthetic_playbooks.jsonl
```

Construir catálogo contra knowledge APPROVED validada:

```powershell
python -m ai_service_desk playbook-build `
  --file playbooks/phase6_synthetic_playbooks.jsonl `
  --knowledge-index <indice-knowledge> `
  --output <diretorio-catalogo>
```

Executar o smoke oficial de 10 casos:

```powershell
python -m ai_service_desk playbook-smoke `
  --knowledge-index <indice-knowledge> `
  --playbooks playbooks/phase6_synthetic_playbooks.jsonl `
  --cases tests/fixtures/phase6_playbook_cases.jsonl `
  --work-directory <diretorio-temporario> `
  --report <relatorio-local.json>
```

Os três comandos da Fase 6 não criam `OllamaClient`. A preparação do índice de knowledge é um pré-requisito da Fase 4 e pode usar o embedding local já homologado.

## Privacidade

Playbooks e fixtures versionados são 100% sintéticos. Não entram no Git histórico corporativo, texto real de ticket, hostnames, credenciais, procedimentos internos reais, catálogo gerado, provenance gerada ou relatórios de smoke.

O relatório de smoke contém somente status/reasons/IDs sintéticos e booleans agregados. Não contém answer de knowledge, texto dos steps ou capability.

## Homologação Dell

No head exato candidato:

```powershell
git rev-parse HEAD

$index = Join-Path $env:TEMP "phase6-knowledge-manual"
$catalog = Join-Path $env:TEMP "phase6-playbook-catalog-manual"
$work = Join-Path $env:TEMP "phase6-playbook-work-manual"
$report = Join-Path $env:TEMP "phase6-playbook-smoke-manual.json"

Remove-Item -Recurse -Force $index,$catalog,$work -ErrorAction SilentlyContinue
Remove-Item -Force $report -ErrorAction SilentlyContinue

python -m ai_service_desk knowledge-index `
  --file knowledge/phase4_synthetic_faq.jsonl `
  --index "$index" `
  --batch-size 10 `
  --url http://127.0.0.1:11434

python -m ai_service_desk playbook-validate `
  --file playbooks/phase6_synthetic_playbooks.jsonl

python -m ai_service_desk playbook-build `
  --file playbooks/phase6_synthetic_playbooks.jsonl `
  --knowledge-index "$index" `
  --output "$catalog"

python -m ai_service_desk playbook-smoke `
  --knowledge-index "$index" `
  --playbooks playbooks/phase6_synthetic_playbooks.jsonl `
  --cases tests/fixtures/phase6_playbook_cases.jsonl `
  --work-directory "$work" `
  --report "$report"

$LASTEXITCODE
```

Evidência esperada no final:

```text
PLAYBOOK SMOKE OK
Casos sinteticos: 10
0
```

O relatório permanece local e não deve ser impresso ou publicado.
