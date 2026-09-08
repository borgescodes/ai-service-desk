# Phase 6: Playbooks declarativos

Data: 2026-09-08

Status: desenho aprovado para revisao antes do plano de implementacao

Base: `main` apos merge da Fase 5, commit `96fc2fd8b7c867fa7340dc75fddcbc37cbcff5c7`

## 1. Objetivo

A Fase 6 introduz playbooks como conteudo estruturado, versionado e aprovado por humanos, associado exclusivamente a `knowledge_id` proveniente da base `APPROVED_KNOWLEDGE`.

O objetivo e permitir que um resultado de knowledge aprovado possa ter um procedimento declarativo explicitamente vinculado, sem qualquer selecao probabilistica e sem qualquer execucao real.

Fluxo aprovado:

```text
triagem
  -> knowledge APPROVED
  -> knowledge_id
  -> playbook declarativo explicitamente vinculado
```

A Fase 6 nao faz retrieval semantico de playbooks, nao usa LLM para escolher playbook, nao usa embeddings, nao faz segunda classificacao e nao executa comandos, scripts, chamadas de API ou qualquer outra acao na maquina.

## 2. Principios obrigatorios

1. Playbook e conteudo declarativo, nao executor.
2. A associacao operacional e exclusivamente por `knowledge_id` exato.
3. `knowledge APPROVED -> 0..1 playbook APPROVED`.
4. `playbook APPROVED -> 1..N knowledge APPROVED`.
5. Dois playbooks `APPROVED` para o mesmo `knowledge_id` sao erro de configuracao e fazem o build falhar.
6. Nao existe prioridade, ranking, desempate, score, LLM, embedding ou escolha pelo primeiro registro.
7. `DRAFT` e `RETIRED` nunca fornecem step text operacional.
8. Provenance do catalogo e fail-closed. Corrupcao ou divergencia nao vira estado normal de negocio.
9. A Fase 6 pode apresentar passos declarativos, mas nao decide permissao e nao executa capability.
10. Policy Engine pertence a Fase 7. Execucao controlada pertence a Fase 8.
11. Fixtures e playbooks versionados nesta fase sao 100% sinteticos.
12. Historico corporativo real, tickets reais, comandos corporativos e procedimentos ainda nao aprovados nao entram no Git.

## 3. Escopo

A Fase 6 inclui:

- schema estrito de playbook;
- lifecycle `DRAFT`, `APPROVED`, `RETIRED`;
- steps declarativos estruturados;
- capability simbolica em `ACTION_PROPOSAL`;
- validacao estrutural do source;
- build deterministico de catalogo operacional contra um indice `APPROVED_KNOWLEDGE` valido;
- validacao referencial por `knowledge_id` presente no indice aprovado;
- validacao de cardinalidade ativa;
- provenance fail-closed vinculando source, catalogo e provenance de knowledge;
- resolucao exata por `knowledge_id`;
- resultado de maquina separado de formatacao para usuario;
- smoke sintetico de 10 casos;
- documentacao operacional e CI da fase.

## 4. Fora de escopo

A Fase 6 nao implementa:

- comando shell;
- PowerShell;
- script;
- executavel;
- argumentos de processo;
- API call;
- metodo HTTP;
- URL operacional;
- credencial, token ou segredo;
- alteracao de arquivo, registro, processo ou configuracao;
- executor de capability;
- policy engine;
- verificacao de permissao;
- aprovacao humana de acao;
- integracao com sistemas corporativos;
- criacao automatica de ticket;
- novo retrieval;
- nova classificacao;
- frontend.

Campos ou mecanismos equivalentes a `command`, `script`, `powershell`, `shell`, `executable`, `args`, `api_url`, `http_method`, `credential`, `token` ou executor nao pertencem ao schema da Fase 6.

## 5. Arquitetura

A Fase 6 e aditiva e fica depois da Fase 5.

```text
TriageEngine
    |
    | KNOWLEDGE_FOUND
    v
knowledge_id
    |
    v
PlaybookEngine
    |
    +--> KNOWLEDGE_ONLY
    |
    +--> PLAYBOOK_FOUND
    |
    `--> PLAYBOOK_UNAVAILABLE
```

Erros de integridade nao aparecem nesse diagrama como status de negocio. Se o catalogo nao puder ser carregado com integridade comprovada, o `PlaybookEngine` nao inicia e nenhuma resolucao e realizada.

A Fase 6 nao altera o contrato publico da triagem. `TriageEngine.step(...)` continua encerrando seu dominio em `KNOWLEDGE_FOUND`, `NEEDS_CLARIFICATION` ou `TRIAGE_ABSTAINED` conforme o contrato da Fase 5.

O caller ou orquestrador compoe os dois dominios quando necessario:

```text
knowledge result
+
playbook result
```

O resultado proprio da Fase 6 nao replica o objeto completo de knowledge.

## 6. Schema do source de playbook

Cada linha do source JSONL e um objeto com exatamente estes campos:

```text
playbook_id
title
description
knowledge_ids
steps
source
status
reviewed_by
reviewed_at
version
```

Exemplo sintetico:

```json
{
  "playbook_id": "PB-SYN-PRINT-001",
  "title": "Recuperar fila de impressao ficticia",
  "description": "Procedimento sintetico aprovado para diagnostico de uma fila ficticia.",
  "knowledge_ids": ["KB-SYN-PRINT-001"],
  "steps": [
    {
      "step_id": "STEP-01",
      "type": "CHECK",
      "title": "Verificar a fila",
      "instruction": "Confirme se existe um documento ficticio preso na fila.",
      "capability": ""
    },
    {
      "step_id": "STEP-02",
      "type": "ACTION_PROPOSAL",
      "title": "Considerar limpeza da fila ficticia",
      "instruction": "A limpeza do item ficticio pode ser considerada como proxima acao.",
      "capability": "DEMO_PRINT_QUEUE_CLEAR"
    }
  ],
  "source": "SYNTHETIC_DEMO",
  "status": "APPROVED",
  "reviewed_by": "synthetic-reviewer",
  "reviewed_at": "2026-09-08T01:00:00-03:00",
  "version": 1
}
```

### 6.1 Regras dos campos

`playbook_id`:

- texto nao vazio;
- maximo definido pela implementacao, recomendado 120 caracteres;
- unico em todo o source.

`title`:

- texto nao vazio;
- texto de apresentacao do procedimento.

`description`:

- texto nao vazio;
- descreve o objetivo do playbook sem conter implementacao executavel.

`knowledge_ids`:

- lista com pelo menos um item;
- cada item e texto nao vazio;
- sem duplicidade dentro do mesmo playbook;
- a validacao estrutural nao consulta knowledge;
- o build operacional exige que cada ID esteja presente no indice `APPROVED_KNOWLEDGE` validado.

`steps`:

- lista ordenada com pelo menos um step;
- `step_id` unico dentro do playbook;
- a ordem da lista e a ordem declarativa oficial.

`source`:

- texto nao vazio;
- identifica a origem administrativa do conteudo.

`status`:

- exatamente `DRAFT`, `APPROVED` ou `RETIRED`.

`reviewed_by` e `reviewed_at`:

- `APPROVED` exige ambos preenchidos;
- `reviewed_at` deve ser ISO 8601 com timezone;
- `DRAFT` e `RETIRED` podem manter metadados administrativos, mas isso nao os torna operacionais.

`version`:

- inteiro positivo;
- mudanca material de steps, capability ou semantica operacional exige incremento de versao no processo de governanca.

Campos ausentes ou extras tornam o registro invalido.

## 7. Lifecycle

### 7.1 DRAFT

Pode existir no source para revisao, mas nunca entra no catalogo operacional com seu conteudo de steps.

Um knowledge que possua apenas vinculo com `DRAFT` pode resultar em `PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED` em um catalogo valido.

### 7.2 APPROVED

E o unico lifecycle que pode fornecer steps operacionais declarativos.

Exige review valido e todos os `knowledge_ids` elegiveis no indice `APPROVED_KNOWLEDGE` utilizado no build.

### 7.3 RETIRED

Nunca fornece steps operacionais.

Um knowledge que possua apenas vinculo `RETIRED`, sem `APPROVED` e sem `DRAFT`, pode resultar em `PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED` em um catalogo valido.

### 7.4 Multiplos inativos

Mais de um playbook inativo pode apontar para o mesmo `knowledge_id` sem criar selecao operacional, pois nenhum deles fornece steps.

Quando nao existe `APPROVED` e ha pelo menos um `DRAFT`, o reason interno e `PLAYBOOK_NOT_APPROVED`.

Quando nao existe `APPROVED` nem `DRAFT` e ha ao menos um `RETIRED`, o reason interno e `PLAYBOOK_RETIRED`.

Essa precedencia e deterministica e representa lifecycle, nao escolha de candidato.

## 8. Cardinalidade e conflito

Contrato formal:

```text
knowledge APPROVED -> 0..1 playbook APPROVED
playbook APPROVED  -> 1..N knowledge APPROVED
```

Um mesmo playbook `APPROVED` pode ser compartilhado por varios `knowledge_id` quando o procedimento aprovado e o mesmo.

Dois ou mais playbooks `APPROVED` que referenciem o mesmo `knowledge_id` tornam a configuracao invalida. O build deve falhar explicitamente.

Nao existe fallback para escolher um dos playbooks conflitantes.

A validacao de conflito ocorre no build antes da publicacao do catalogo operacional.

## 9. Step schema

Cada step possui exatamente:

```text
step_id
type
title
instruction
capability
```

Tipos permitidos:

```text
INSTRUCTION
CHECK
ACTION_PROPOSAL
```

### 9.1 INSTRUCTION

Instrucao manual ou orientacao declarativa ao usuario.

`capability` deve ser string vazia.

### 9.2 CHECK

Solicita uma verificacao humana ou confirmacao declarativa.

Nao le estado da maquina automaticamente.

`capability` deve ser string vazia.

### 9.3 ACTION_PROPOSAL

Representa uma acao conceitual que uma fase futura pode submeter ao Policy Engine.

`capability` e obrigatoria e deve ser um identificador simbolico estavel, nao um comando.

Formato recomendado para capability:

```text
^[A-Z][A-Z0-9_]{2,119}$
```

Exemplo:

```text
DEMO_PRINT_QUEUE_CLEAR
```

A Fase 6 nao sabe como executar essa capability e nao possui mapeamento capability -> comando.

Uma capability nao pode conter comando shell, argumentos, URL, credencial ou codigo executavel.

## 10. Separacao entre contrato de maquina e apresentacao

A Fase 6 possui duas superficies distintas.

### 10.1 Machine result

O resultado de maquina preserva metadados estruturados necessarios para composicao e para a Fase 7.

Para `PLAYBOOK_FOUND`:

```json
{
  "status": "PLAYBOOK_FOUND",
  "reason": "MATCH",
  "knowledge_id": "KB-SYN-PRINT-001",
  "playbook": {
    "playbook_id": "PB-SYN-PRINT-001",
    "title": "Recuperar fila de impressao ficticia",
    "description": "Procedimento sintetico aprovado para diagnostico de uma fila ficticia.",
    "version": 1,
    "steps": [
      {
        "step_id": "STEP-02",
        "type": "ACTION_PROPOSAL",
        "title": "Considerar limpeza da fila ficticia",
        "instruction": "A limpeza do item ficticio pode ser considerada como proxima acao.",
        "capability": "DEMO_PRINT_QUEUE_CLEAR"
      }
    ]
  }
}
```

A Fase 6 nao replica `answer`, `question`, `system`, `intent`, `score`, `threshold` ou outros campos do objeto de knowledge.

### 10.2 User-facing formatting

O formatter voltado ao usuario pode mostrar:

- titulo do playbook;
- descricao aprovada;
- ordem dos steps;
- titulo do step;
- instrucao do step;
- indicacao textual de que `ACTION_PROPOSAL` e apenas uma acao proposta.

O formatter voltado ao usuario nao mostra automaticamente:

- `capability`;
- `reviewed_by`;
- hashes;
- provenance;
- lifecycle interno;
- reasons tecnicos;
- comandos, scripts ou parametros de execucao.

Para `ACTION_PROPOSAL`, uma apresentacao aceitavel e equivalente a:

```text
Acao proposta: a limpeza do item ficticio pode ser considerada como proxima acao.
```

Nao e aceitavel afirmar que a acao foi executada ou que o usuario tem permissao para executa-la.

O formatter nao duplica o `answer` da Fase 5. O caller compoe knowledge e playbook quando necessario.

## 11. Estados publicos da Fase 6

Existem exatamente tres estados normais de negocio.

### 11.1 KNOWLEDGE_ONLY

Catalogo valido, `knowledge_id` elegivel e nenhum vinculo de playbook existente.

```json
{
  "status": "KNOWLEDGE_ONLY",
  "reason": "NO_PLAYBOOK",
  "knowledge_id": "KB-SYN-VPN-001",
  "playbook": null
}
```

### 11.2 PLAYBOOK_FOUND

Catalogo valido e exatamente um playbook `APPROVED` ativo para o `knowledge_id`.

```text
status = PLAYBOOK_FOUND
reason = MATCH
```

### 11.3 PLAYBOOK_UNAVAILABLE

Reservado a lifecycle conhecido em um catalogo valido.

Reasons permitidos nesta fase:

```text
PLAYBOOK_NOT_APPROVED
PLAYBOOK_RETIRED
```

O resultado nao inclui step text de playbook inativo.

Exemplo:

```json
{
  "status": "PLAYBOOK_UNAVAILABLE",
  "reason": "PLAYBOOK_NOT_APPROVED",
  "knowledge_id": "KB-SYN-SOFTWARE-001",
  "playbook": null
}
```

A UI futura nao e obrigada a expor o reason de lifecycle. Pode apresentar uma mensagem generica de indisponibilidade.

## 12. Erros de integridade e fail-closed

Os seguintes casos nao sao `PLAYBOOK_UNAVAILABLE`:

- sidecar de provenance ausente;
- provenance invalida;
- dominio incorreto;
- `catalog_hash` divergente;
- source hash divergente;
- sidecar copiado de outro catalogo;
- catalogo truncado ou parcial;
- catalogo adulterado;
- knowledge provenance divergente;
- `knowledge_source_hash` divergente;
- schema operacional invalido;
- dois playbooks `APPROVED` para o mesmo `knowledge_id`;
- representacao interna inconsistente.

Esses casos causam erro explicito de build ou carga. O `PlaybookEngine` nao deve ficar disponivel para `resolve()`.

Nao existe fallback para `KNOWLEDGE_ONLY`, `PLAYBOOK_UNAVAILABLE` ou qualquer outro status quando a integridade nao puder ser provada.

CLI ou workflow que encontre esse erro deve terminar com exit code diferente de zero e sem exibir step text operacional.

## 13. Validacao estrutural

`playbook-validate` e puramente estrutural.

Ele valida o source JSONL sem Ollama, embeddings ou acesso ao indice de knowledge.

Deve rejeitar pelo menos:

- JSON invalido;
- UTF-8 invalido;
- arquivo vazio;
- campo ausente;
- campo extra;
- `playbook_id` vazio ou duplicado;
- status fora do contrato;
- `APPROVED` sem review valido;
- `knowledge_ids` vazio ou com duplicidade interna;
- `steps` vazio;
- `step_id` duplicado dentro do playbook;
- step type invalido;
- `ACTION_PROPOSAL` sem capability valida;
- capability nao vazia em `INSTRUCTION` ou `CHECK`;
- `version` invalida.

`playbook-validate` nao afirma que os vinculos de knowledge sao operacionais.

## 14. Build do catalogo operacional

`playbook-build` recebe:

```text
playbook source JSONL
indice APPROVED_KNOWLEDGE
output directory
```

Sequencia obrigatoria:

1. carregar o indice de knowledge usando a validacao fail-closed existente da Fase 4;
2. obter somente os `knowledge_id` presentes nesse indice aprovado;
3. validar estruturalmente o source de playbooks;
4. validar que cada `knowledge_id` referenciado existe no indice aprovado;
5. tratar qualquer ID ausente do indice como referencia nao elegivel e rejeitar o build;
6. validar cardinalidade de playbooks `APPROVED` por `knowledge_id`;
7. compilar conteudo completo somente de playbooks `APPROVED`;
8. compilar somente metadados minimos de lifecycle para `DRAFT` e `RETIRED`;
9. compilar a lista de `eligible_knowledge_ids` do indice aprovado;
10. escrever o catalogo completo de forma atomica;
11. calcular e verificar o hash do catalogo publicado;
12. escrever o sidecar de provenance somente depois do catalogo completo;
13. reler catalogo e provenance e validar a combinacao antes de declarar sucesso.

A Fase 6 nao precisa ler o source bruto da Fase 4 para diferenciar knowledge inexistente de knowledge `DRAFT` ou `RETIRED`. Se o ID nao esta no indice `APPROVED_KNOWLEDGE`, ele nao e elegivel para vinculo operacional.

## 15. Catalogo operacional

Arquivos previstos no diretorio compilado:

```text
playbook-catalog.json
playbook-provenance.json
```

O catalogo deve ter estrutura equivalente a:

```json
{
  "catalog_schema_version": 1,
  "domain": "APPROVED_PLAYBOOK",
  "eligible_knowledge_ids": [
    "KB-SYN-CIGAM-ACCESS-001",
    "KB-SYN-PRINT-001"
  ],
  "playbooks": {
    "PB-SYN-PRINT-001": {
      "playbook_id": "PB-SYN-PRINT-001",
      "title": "Recuperar fila de impressao ficticia",
      "description": "Procedimento sintetico aprovado para diagnostico de uma fila ficticia.",
      "knowledge_ids": ["KB-SYN-PRINT-001"],
      "version": 1,
      "steps": []
    }
  },
  "active_by_knowledge_id": {
    "KB-SYN-PRINT-001": "PB-SYN-PRINT-001"
  },
  "inactive_by_knowledge_id": {
    "KB-SYN-SOFTWARE-001": [
      {
        "playbook_id": "PB-SYN-SOFTWARE-001",
        "status": "DRAFT",
        "version": 1
      }
    ]
  }
}
```

Regras:

- `playbooks` contem somente playbooks `APPROVED` com conteudo operacional completo;
- `active_by_knowledge_id` possui no maximo um playbook por knowledge;
- `inactive_by_knowledge_id` nao contem `title`, `description`, `instruction`, `capability` nem step text de DRAFT/RETIRED;
- `eligible_knowledge_ids` contem apenas IDs do indice `APPROVED_KNOWLEDGE` validado durante o build.

## 16. Provenance do catalogo

Constantes conceituais:

```text
PLAYBOOK_SCHEMA_VERSION = 1
PLAYBOOK_CATALOG_SCHEMA_VERSION = 1
PLAYBOOK_DOMAIN = APPROVED_PLAYBOOK
CATALOG_RECIPE = playbook-catalog-v1
```

O sidecar deve conter um conjunto fechado de campos equivalente a:

```text
version
domain
playbook_schema_version
catalog_schema_version
catalog_recipe
source_hash
catalog_hash
approved_playbooks
active_links
knowledge_domain
knowledge_schema_version
knowledge_source_hash
knowledge_provenance_hash
```

Regras:

- `source_hash` vincula a provenance ao source de playbooks usado no build;
- `catalog_hash` vincula a provenance ao conteudo exato do catalogo operacional;
- `knowledge_domain` deve corresponder a `APPROVED_KNOWLEDGE`;
- `knowledge_schema_version` deve corresponder ao schema de knowledge validado;
- `knowledge_source_hash` deve corresponder ao `source_hash` da provenance de knowledge;
- `knowledge_provenance_hash` deve ser calculado a partir de uma representacao canonica da provenance validada de knowledge e vincula o catalogo a essa provenance completa;
- qualquer divergencia faz a carga falhar;
- sidecar ausente faz a carga falhar;
- campos ausentes, extras ou invalidos fazem a carga falhar.

A provenance e escrita apenas depois que o catalogo foi concluido. Se houver falha entre a escrita do catalogo e a escrita do sidecar, a proxima carga falha fechado por ausencia de provenance.

## 17. Carga do PlaybookEngine

O `PlaybookEngine` recebe o diretorio do catalogo e a provenance corrente do indice de knowledge usado pelo caller.

Na inicializacao ele deve:

1. ler `playbook-provenance.json`;
2. validar schema e dominio;
3. ler `playbook-catalog.json`;
4. validar schema operacional;
5. recalcular `catalog_hash`;
6. validar cardinalidade interna;
7. validar que todo `active_by_knowledge_id` referencia playbook `APPROVED` presente no catalogo;
8. validar que todos os IDs ativos e elegiveis sao consistentes;
9. comparar `knowledge_domain`, `knowledge_schema_version`, `knowledge_source_hash` e `knowledge_provenance_hash` com a provenance corrente de knowledge;
10. somente entao permitir resolucao.

Qualquer falha interrompe a carga explicitamente.

## 18. Resolucao

A operacao principal e deterministica.

Interface conveniente aprovada:

```text
PlaybookEngine.resolve(knowledge)
```

O adapter valida que a entrada e um mapping e extrai somente `knowledge_id`.

O nucleo da resolucao depende apenas do ID:

```text
resolve_knowledge_id(knowledge_id)
```

Campos adicionais do objeto de knowledge nao sao copiados nem reinterpretados.

Antes de resolver, `knowledge_id` deve existir em `eligible_knowledge_ids`. Um ID que nao pertença ao conjunto aprovado do catalogo e erro de entrada, nao `KNOWLEDGE_ONLY`.

Algoritmo:

```text
knowledge_id elegivel?
    nao -> erro explicito
    sim -> existe active_by_knowledge_id?
             sim -> PLAYBOOK_FOUND
             nao -> existe inactive metadata?
                      nao -> KNOWLEDGE_ONLY
                      sim -> existe DRAFT?
                               sim -> PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED
                               nao -> PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED
```

Nao ha chamada de IA ou acesso semantico nesse fluxo.

## 19. Contrato para a Fase 7

A Fase 7 nao deve reinterpretar `instruction` para descobrir uma acao.

Para cada `ACTION_PROPOSAL`, a Fase 6 ja fornece identificacao de maquina suficiente:

```text
knowledge_id
playbook_id
playbook_version
step_id
type
capability
```

Exemplo conceitual de entrada futura para o Policy Engine:

```json
{
  "knowledge_id": "KB-SYN-PRINT-001",
  "playbook_id": "PB-SYN-PRINT-001",
  "playbook_version": 1,
  "step_id": "STEP-02",
  "type": "ACTION_PROPOSAL",
  "capability": "DEMO_PRINT_QUEUE_CLEAR"
}
```

A Fase 7 podera decidir policy em termos como `ALLOWED`, `DENIED`, `REQUIRES_APPROVAL` ou outros definidos em sua propria spec.

Esses estados nao pertencem a Fase 6.

A Fase 6 tambem nao define capability -> implementacao. Esse mapeamento pertence a Fase 8 ou a camada de execucao aprovada posteriormente.

A estabilidade entre fases depende de:

- `playbook_id` estavel;
- `playbook_version` explicita;
- `step_id` estavel dentro da versao;
- `type` estruturado;
- `capability` simbolica para `ACTION_PROPOSAL`.

## 20. Formatos CLI previstos

A implementacao posterior deve prever:

```text
playbook-validate
playbook-build
playbook-smoke
```

### playbook-validate

- validacao estrutural do source;
- sem Ollama;
- sem embedding;
- sem knowledge lookup;
- nao imprime step text por padrao.

### playbook-build

- usa indice `APPROVED_KNOWLEDGE` validado;
- compila catalogo e provenance;
- falha em referencia nao elegivel ou conflito;
- sidecar apenas apos catalogo completo.

### playbook-smoke

- usa somente fixtures sinteticas;
- testa composicao Phase 4 -> Phase 5 -> Phase 6 quando necessario;
- nunca chama executor;
- relatorio agregado nao inclui step text, capability ou answer aprovado.

## 21. Fixtures sinteticas

Arquivos previstos:

```text
playbooks/phase6_synthetic_playbooks.jsonl
tests/fixtures/phase6_playbook_cases.jsonl
```

Os playbooks sinteticos podem referenciar apenas `knowledge_id` existentes na fixture sintetica da Fase 4 quando o caso precisa ser operacionalmente valido.

Fixtures negativas podem conter referencias inventadas apenas para provar rejeicao.

Nenhum dado corporativo real deve ser versionado.

## 22. Smoke da Fase 6

O smoke oficial contem exatamente 10 casos sinteticos.

1. `approved-single-link`: knowledge aprovado com um playbook `APPROVED` retorna `PLAYBOOK_FOUND`.
2. `approved-shared-playbook`: dois knowledge IDs aprovados referenciam o mesmo playbook `APPROVED`, provando cardinalidade 1:N.
3. `knowledge-only`: knowledge aprovado sem qualquer link retorna `KNOWLEDGE_ONLY / NO_PLAYBOOK`.
4. `draft-only`: knowledge com apenas vinculo DRAFT retorna `PLAYBOOK_UNAVAILABLE / PLAYBOOK_NOT_APPROVED` e nenhum step text e carregado.
5. `retired-only`: knowledge com apenas vinculo RETIRED retorna `PLAYBOOK_UNAVAILABLE / PLAYBOOK_RETIRED` e nenhum step text e carregado.
6. `approved-conflict`: dois playbooks `APPROVED` para o mesmo knowledge fazem o build falhar.
7. `ineligible-knowledge-reference`: referencia ausente do indice `APPROVED_KNOWLEDGE` faz o build falhar.
8. `catalog-integrity`: catalogo adulterado ou incompleto e rejeitado na carga, sem status de negocio.
9. `knowledge-provenance-mismatch`: catalogo ligado a outra provenance de knowledge e rejeitado na carga.
10. `action-proposal-contract`: capability valida aparece no machine result, nao aparece no formatter de usuario e nenhum executor e chamado.

O smoke nao substitui os testes unitarios de todas as variantes de corrupcao.

## 23. Testes obrigatorios

A implementacao deve incluir testes explicitos para, no minimo:

### 23.1 Schema e lifecycle

- source valido;
- campos ausentes;
- campos extras;
- `playbook_id` duplicado;
- status invalido;
- `APPROVED` sem review valido;
- step type invalido;
- `ACTION_PROPOSAL` sem capability;
- capability invalida;
- capability presente em `INSTRUCTION`;
- capability presente em `CHECK`;
- `step_id` duplicado;
- `knowledge_ids` vazio;
- `knowledge_id` duplicado dentro do mesmo playbook.

### 23.2 Referencias e cardinalidade

- knowledge elegivel no indice aprovado;
- knowledge sem link retorna `KNOWLEDGE_ONLY`;
- referencia nao elegivel rejeita build;
- um playbook APPROVED pode ligar 1:N knowledge;
- dois APPROVED para o mesmo `knowledge_id` rejeitam build;
- DRAFT e RETIRED nao entram em `active_by_knowledge_id`;
- DRAFT e RETIRED nao carregam seus steps, instructions ou capabilities no catalogo operacional.

### 23.3 Provenance fail-closed

Testes separados e explicitos para:

- `playbook-provenance.json` ausente;
- sidecar copiado de outro catalogo;
- `catalog_hash` adulterado;
- catalogo truncado;
- catalogo parcial;
- catalogo adulterado mantendo JSON valido;
- dominio incorreto;
- schema de provenance invalido;
- `knowledge_source_hash` ligado a outro corpus;
- `knowledge_provenance_hash` divergente;
- source hash divergente;
- representacao interna com active link apontando para playbook inexistente;
- representacao interna com conflito de dois APPROVED para o mesmo knowledge.

Todos esses casos devem resultar em erro explicito de build ou carga. Nenhum deles pode retornar `PLAYBOOK_UNAVAILABLE` ou `KNOWLEDGE_ONLY`.

### 23.4 Machine result e formatter

- machine result de `ACTION_PROPOSAL` contem `capability`;
- machine result contem `knowledge_id`, `playbook_id`, `playbook_version`, `step_id` e `type` suficientes para Phase 7;
- formatter para usuario nao exibe capability;
- formatter nao exibe reviewer, hashes ou provenance;
- formatter nao e obrigado a expor `PLAYBOOK_RETIRED` ou lifecycle especifico;
- formatter nao afirma permissao;
- formatter nao afirma execucao;
- formatter nao duplica o answer de knowledge.

### 23.5 Zero execucao

- resolver nao importa nem chama executor;
- nenhum `subprocess` e necessario ao runtime Phase 6;
- nenhum cliente HTTP e chamado para executar step;
- nenhum shell e invocado;
- `ACTION_PROPOSAL` com capability valida continua sendo apenas dado estruturado;
- teste deve usar spy/fake que falharia caso um executor fosse chamado, comprovando zero chamada.

## 24. Relatorio de smoke e privacidade

O relatorio agregado deve conter somente metadados seguros, por exemplo:

```text
case_name
expected_status
actual_status
expected_reason
actual_reason
expected_playbook_id
actual_playbook_id
passed
```

Para casos de integridade pode registrar apenas o tipo seguro do erro esperado/observado.

O relatorio nao inclui:

- messages;
- transcript;
- answer de knowledge;
- title ou instruction de playbook;
- capability;
- ticket ID real;
- dado corporativo;
- hash de corpus corporativo em output publico.

## 25. Arquivos previstos para implementacao futura

Dominio:

```text
src/ai_service_desk/engine/playbook.py
src/ai_service_desk/engine/playbook_resolution.py
src/ai_service_desk/engine/playbook_smoke.py
```

Fixtures:

```text
playbooks/phase6_synthetic_playbooks.jsonl
tests/fixtures/phase6_playbook_cases.jsonl
```

Testes:

```text
tests/engine/test_playbook.py
tests/engine/test_playbook_resolution.py
tests/engine/test_playbook_smoke.py
tests/test_playbook_cli.py
tests/test_workflows.py
```

Operacao e documentacao:

```text
src/ai_service_desk/cli.py
.github/workflows/phase6-playbook-smoke.yml
docs/playbooks/phase-6.md
README.md
```

Esta spec:

```text
docs/superpowers/specs/2026-09-08-phase-6-playbooks-design.md
```

O plano de implementacao sera um artefato separado e so sera criado apos aprovacao explicita desta spec.

## 26. Arquivos protegidos nesta fase

Nao ha expectativa de alterar:

```text
src/ai_service_desk/engine/classification.py
src/ai_service_desk/engine/retrieval.py
src/ai_service_desk/engine/index.py
src/ai_service_desk/engine/knowledge.py
src/ai_service_desk/engine/knowledge_retrieval.py
src/ai_service_desk/engine/triage.py
```

Qualquer necessidade de alterar esses arquivos exige primeiro um bloqueio tecnico reproduzivel, causa raiz documentada, menor mudanca possivel e avaliacao de regressao.

## 27. Riscos de regressao e mitigacoes

### 27.1 Acoplamento com triagem

Risco: transformar playbook em parte obrigatoria de `TriageEngine`.

Mitigacao: resolver playbook somente depois de `KNOWLEDGE_FOUND`, por composicao externa.

### 27.2 Duplicacao do dominio knowledge

Risco: Fase 6 copiar answer, title, system, intent e outros campos.

Mitigacao: resultado proprio contem apenas `status`, `reason`, `knowledge_id` e `playbook`.

### 27.3 Conteudo inativo virar orientacao

Risco critico: DRAFT/RETIRED fornecerem steps.

Mitigacao: catalogo operacional mantem conteudo completo apenas de APPROVED. Inativos preservam somente metadata minima de lifecycle.

### 27.4 Corrupcao mascarada como indisponibilidade

Risco critico: provenance invalida ser apresentada como `PLAYBOOK_UNAVAILABLE`.

Mitigacao: carga fail-closed antes de qualquer resolucao.

### 27.5 Mudanca de knowledge sem rebuild do playbook

Risco: catalogo permanecer ligado a uma base diferente.

Mitigacao: `knowledge_source_hash` e `knowledge_provenance_hash` fazem parte da provenance do catalogo e sao comparados em runtime.

### 27.6 Capability virar executor escondido

Risco: Phase 6 armazenar implementacao real dentro da capability.

Mitigacao: capability e somente identificador simbolico com formato restrito. Nao existem campos de comando, argumentos ou endpoint.

### 27.7 Regressao das Fases 1 a 5

Mitigacao: implementacao aditiva, arquivos protegidos, suite completa anterior obrigatoriamente verde e smoke Phase 6 independente.

## 28. Criterios de aceite da Fase 6

A Fase 6 so pode ser considerada concluida quando houver evidencia de que:

- selecao e exclusivamente por `knowledge_id`;
- zero LLM calls sao usadas para escolher playbook;
- zero embeddings sao usados para escolher playbook;
- zero segunda classificacao ocorre;
- zero acao real e executada;
- somente `APPROVED` fornece steps;
- DRAFT/RETIRED nunca fornecem step text operacional;
- `knowledge APPROVED -> 0..1 playbook APPROVED` e imposto;
- `playbook APPROVED -> 1..N knowledge APPROVED` funciona;
- conflito de dois APPROVED falha build;
- referencia nao presente no indice APPROVED falha build;
- provenance e fail-closed;
- sidecar ausente falha carga;
- catalogo adulterado falha carga;
- catalogo truncado falha carga;
- sidecar de outro catalogo falha carga;
- provenance de knowledge divergente falha carga;
- machine result preserva capability;
- formatter de usuario nao exibe capability;
- `KNOWLEDGE_ONLY`, `PLAYBOOK_FOUND` e `PLAYBOOK_UNAVAILABLE` funcionam apenas em catalogo valido;
- 10/10 casos do smoke sintetico passam;
- toda a suite das Fases 1 a 5 permanece verde;
- CI hospedado fica verde;
- homologacao Dell passa no head final;
- PR recebe revisao final;
- merge ocorre somente apos aprovacao explicita.

## 29. Fronteira formal entre Fase 6 e Fase 7

A Fase 6 responde:

```text
qual playbook aprovado esta explicitamente ligado a este knowledge_id?
quais passos declarativos fazem parte desse playbook?
qual capability simbolica um ACTION_PROPOSAL representa?
```

A Fase 6 nao responde:

```text
o usuario pode executar essa capability?
a capability exige aprovacao?
a capability e permitida neste ambiente?
qual comando implementa a capability?
a acao foi executada com sucesso?
```

Essas perguntas pertencem respectivamente ao Policy Engine e a Execucao Controlada.

A Fase 7 deve consumir os identificadores estruturados da Fase 6 sem precisar analisar ou reescrever texto livre.

## 30. Decisao arquitetural consolidada

O contrato da Fase 6 e:

```text
Knowledge APPROVED
        |
        | knowledge_id exato
        v
Playbook Catalog valido
        |
        +-- nenhum link ------------> KNOWLEDGE_ONLY
        |
        +-- somente link inativo ---> PLAYBOOK_UNAVAILABLE
        |
        +-- um APPROVED ------------> PLAYBOOK_FOUND
        |
        `-- integridade invalida ----> erro de carga/build, sem fallback
```

Playbook nesta fase:

```text
e conteudo
e estruturado
e aprovado
e versionado
e auditavel
pode declarar capabilities
nao decide policy
nao executa capability
nao conhece executor
```

Essa fronteira preserva os contratos das Fases 1 a 5 e prepara uma interface estruturada para a Fase 7 sem antecipar policy ou execucao.
