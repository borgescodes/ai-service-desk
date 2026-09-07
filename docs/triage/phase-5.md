# Fase 5: triagem conversacional

A Fase 5 adiciona uma triagem multi-turno curta e deterministica antes da consulta a knowledge `APPROVED`. O objetivo e coletar apenas o contexto que falta para decidir se existe orientacao oficial suficiente, sem transformar o sistema em um chatbot aberto.

## Escopo

A triagem:

- reutiliza `classify_ticket`;
- preserva contexto entre no maximo 3 mensagens do usuario;
- faz no maximo 2 perguntas de esclarecimento;
- consulta somente a knowledge `APPROVED` da Fase 4;
- devolve o `answer` aprovado literalmente quando existe match;
- abstém quando o contexto continua insuficiente ou quando a Fase 4 nao encontra knowledge suficiente.

A Fase 5 nao cria ticket, nao executa acoes na maquina, nao inicia playbooks, nao aplica policy engine, nao implementa frontend e nao usa historico nao validado como orientacao oficial.

## Estado persistivel

`TriageState` contem somente:

```text
version
session_id
status
turn_count
clarification_count
problem_text
intent
system
entities
confidence
pending_field
asked_fields
```

`session_id` e opaco. O caller e responsavel por persistir o estado futuramente. O motor nao possui banco, cache global ou session store.

O estado nunca armazena transcript completo, mensagens do assistente, `answer` de knowledge, texto de artigo, embeddings, scores, historicos de ticket ou `ticket_id` historico.

## Merge de contexto

A precedencia e:

1. estado `ANSWERED` ou `ABSTAINED` e terminal;
2. correcao explicita e inequivoca de system atualiza somente `system`;
3. resposta curta a `pending_field=system` atualiza somente `system`;
4. resposta a `pending_field=problem` substitui o contexto substantivo;
5. nova descricao substantiva substitui `problem_text`, `intent`, `entities` e `confidence`;
6. novo system explicito unico substitui o anterior;
7. multiplos systems explicitos sem correcao permanecem ambiguos;
8. mudanca de intent ocorre apenas por nova descricao substantiva.

Quando uma nova descricao substitui o problema, entities antigas sao descartadas. Um system previamente resolvido e preservado apenas quando a nova descricao nao fornece nova evidencia de system.

## Limites

```text
MAX_USER_TURNS = 3
MAX_CLARIFICATIONS = 2
```

O terceiro turno e processado integralmente e pode resultar em `KNOWLEDGE_FOUND`. Um quarto turno e rejeitado antes da classificacao. Se o terceiro turno ainda exigiria outra pergunta, a triagem termina com `MAX_TURNS`. Uma terceira pergunta de esclarecimento nunca e emitida.

Cada campo pode ser perguntado no maximo uma vez no mesmo contexto substantivo.

## Resultados publicos

Existem tres status publicos:

- `NEEDS_CLARIFICATION`: existe uma pergunta objetiva que ainda pode completar o contexto;
- `KNOWLEDGE_FOUND`: a Fase 4 encontrou knowledge `APPROVED` suficiente;
- `TRIAGE_ABSTAINED`: a triagem terminou sem orientacao oficial suficiente.

Estados internos `ANSWERED` e `ABSTAINED` sao terminais e nao podem ser reabertos.

`confidence` permanece apenas como metadado da classificacao e nunca participa de uma decisao.

## Fronteira com a Fase 4

`KnowledgeEngine.search(text)` permanece retrocompativel.

A Fase 5 usa duas interfaces aditivas:

```text
KnowledgeEngine.search_classified(text, classification)
KnowledgeEngine.available_systems(intent)
```

`search_classified()` evita uma segunda classificacao da mesma mensagem e reutiliza os mesmos gates, embedding, threshold e contrato de resultado da Fase 4.

`available_systems()` expõe somente metadados de disponibilidade. A triagem nao acessa `documents.jsonl`, matriz, manifest, provenance ou `KnowledgeEngine.df` diretamente.

## Query e threshold

O threshold permanece exatamente `0.65` e pertence ao `KnowledgeEngine`.

A query de knowledge pode conter somente:

- o `problem_text` atual fornecido pelo usuario;
- o system resolvido fornecido pelo usuario quando necessario.

A triagem nao adiciona labels de intent, tags de knowledge, sinonimos, titles, answers, historico ou frases artificiais para aumentar similaridade. Em correcao ou desambiguacao, somente aliases conhecidos conflitantes podem ser removidos lexicalmente antes de acrescentar o system final.

## Privacidade

Todas as fixtures versionadas sao sinteticas. Nenhuma conversa real ou dado corporativo entra no Git.

O report de smoke grava apenas metadados agregados por caso:

```text
case_name
expected_status
actual_status
reason
expected_knowledge_id
actual_knowledge_id
turn_count
clarification_count
passed
```

O report nao grava mensagens, transcript ou `answer`.

## Smoke sintetico

A fixture possui exatamente 10 cenarios em:

```text
tests/fixtures/phase5_triage_conversations.jsonl
```

Executar localmente:

```powershell
python -m ai_service_desk triage-smoke `
  --index C:\ai-service-desk-data\phase-5\index `
  --cases tests/fixtures/phase5_triage_conversations.jsonl `
  --report C:\ai-service-desk-data\phase-5\reports\smoke.json `
  --url http://127.0.0.1:11434
```

A homologacao esperada imprime somente o resumo agregado, incluindo `TRIAGE SMOKE OK` e `Casos sinteticos: 10`. O workflow manual `.github/workflows/phase5-triage-smoke.yml` usa o runner Dell homologado, Ollama em loopback, a FAQ sintetica da Fase 4 e a fixture sintetica da Fase 5, sem upload do report.
