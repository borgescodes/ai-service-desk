# Fase 3 Avaliacao e Calibracao

## Estado

Design da Fase 3 para o trilho da competicao. Esta fase parte da Fase 2A integrada em `main` e nao depende da conclusao da indexacao completa da Fase 2B.

## Objetivo

Criar uma avaliacao reproduzivel do classificador e do retrieval, comparar o comportamento de diferentes thresholds e registrar uma decisao de calibracao auditavel, sem transformar benchmark sintetico em alegacao de precisao sobre o corpus corporativo real.

A Fase 3 deve responder quatro perguntas:

1. O classificador identifica corretamente intencao e sistema nos cenarios controlados?
2. O retrieval encontra evidencia relevante em um corpus sintetico com ground truth conhecido?
3. O motor se abstem corretamente quando deve e preserva a barreira de sistema?
4. Existe evidencia suficiente para alterar o threshold legado `0.65`?

Uma decisao de manter `0.65` por falta de evidencia real rotulada e um resultado valido de calibracao. O sistema nao deve se autoajustar usando dados reais sem rotulos.

## Principios

1. O algoritmo de retrieval da Fase 2 nao e reescrito nesta fase.
2. O threshold nao muda automaticamente.
3. Dados corporativos reais, textos de tickets, historicos e identificadores reais permanecem fora do Git e dos logs.
4. Benchmark sintetico mede comportamento controlado, nao qualidade global do corpus real.
5. O campo `confidence` do classificador continua sendo autoavaliacao do modelo, nao probabilidade calibrada.
6. Nenhum percentual de automacao, precisao ou resolucao do ambiente real sera inferido a partir do benchmark sintetico.
7. Qualquer futura alteracao do threshold exige evidencia rotulada e criterio de decisao versionado.
8. A avaliacao deve priorizar falsos positivos e vazamento entre sistemas sobre aumento de cobertura.

## Reuso obrigatorio

A Fase 3 reutiliza:

- `classify_ticket` para classificacao com o modelo local;
- `RetrievalEngine` e `retrieve` para o mesmo comportamento de busca da Fase 2;
- `LocalEmbedder` e o modelo `qwen3-embedding:0.6b`;
- `build_index` e `load_index` para indice reproduzivel;
- a fixture sintetica como padrao seguro do CI hospedado;
- o indice real da demo de 240 tickets apenas para invariantes de seguranca, sem ground truth de relevancia;
- o runner Dell homologado para avaliacao com Ollama real;
- o padrao de relatorios agregados e sem conteudo corporativo.

Nao criar outro retriever, reranker, banco vetorial ou pipeline de embeddings.

## Escopo da competicao

A Fase 3 e deliberadamente pequena. Ela possui dois benchmarks complementares.

### Benchmark A: sintetico com ground truth

Versionado no repositorio e composto por:

```text
tests/fixtures/phase3_eval_corpus.csv
tests/fixtures/phase3_eval_cases.jsonl
```

O corpus e inteiramente ficticio. Cada caso pode declarar:

```json
{
  "id": "printer-01",
  "query": "A impressora do exemplo nao imprime.",
  "expected_intent": "PROBLEMA_IMPRESSAO",
  "expected_system": "",
  "relevant_ticket_ids": ["SYN-PRN-01"],
  "must_abstain": false
}
```

Casos de seguranca podem omitir documentos relevantes e exigir abstinencia:

```json
{
  "id": "ambiguous-01",
  "query": "CIGAM e SIAGRI apresentam erro.",
  "expected_intent": "ERRO_SISTEMA",
  "expected_system": "",
  "relevant_ticket_ids": [],
  "must_abstain": true,
  "expected_status": "CONTEXTO_AMBIGUO"
}
```

O benchmark v1 deve cobrir pelo menos:

- CIGAM;
- SIAGRI;
- impressao;
- rede;
- acesso;
- instalacao de software;
- orientacao;
- contexto desconhecido;
- contexto ambiguo;
- consultas com score abaixo do threshold;
- casos em que existe evidencia relevante conhecida.

A meta e aproximadamente 24 a 32 consultas sinteticas. Nao ha beneficio de criar centenas de casos para a competicao.

### Benchmark B: seguranca sobre a demo real

Usa o indice real de 240 tickets da Fase 2A, mas somente com queries sinteticas sem ground truth de ticket relevante.

Ele verifica:

- CIGAM nunca promove evidencia de SIAGRI;
- SIAGRI nunca promove evidencia de CIGAM;
- sistema desconhecido retorna `SEM_CONTEXTO`;
- CIGAM + SIAGRI retorna `CONTEXTO_AMBIGUO`;
- impressao mantem `PROBLEMA_IMPRESSAO`;
- qualquer candidato continua `HISTORICO_NAO_VALIDADO`;
- nenhum conteudo ou identificador real e incluido no relatorio.

Esse benchmark nao calcula precision, recall, hit rate ou MRR no corpus real, pois nao existe ground truth real rotulado.

## Schema dos casos

Cada linha JSONL possui:

```text
id                  string unica
query               string sintetica
expected_intent     intent oficial ou vazio
expected_system     sistema esperado ou vazio
relevant_ticket_ids lista de IDs sinteticos
must_abstain        boolean
expected_status     opcional
```

Validacoes:

- `id` unica e nao vazia;
- `query` nao vazia e com limite compativel com o classificador;
- intent precisa pertencer ao contrato oficial quando informado;
- `relevant_ticket_ids` deve conter somente strings sinteticas no benchmark versionado;
- `must_abstain=true` nao pode declarar documento relevante;
- `expected_status`, quando presente, deve pertencer aos status oficiais usados pelo retrieval.

## Metricas

### Classificacao

- `intent_accuracy`;
- `system_accuracy`;
- contagem total de casos avaliados.

### Retrieval sintetico

- `hit_at_1`;
- `hit_at_3`;
- `mrr`;
- `precision_at_3` quando existe ground truth;
- `correct_abstention_rate`;
- `unsafe_accept_count`;
- `system_leakage_count`.

### Operacao

- latencia total `p50`;
- latencia total `p95`;
- numero de falhas de execucao.

Scores de similaridade continuam sendo scores. Eles nao sao probabilidades.

## Sweep de threshold

O avaliador compara, por padrao:

```text
0.50
0.55
0.60
0.65
0.70
0.75
0.80
```

Classificacao e embedding da query devem ser calculados uma vez por caso. O sweep reutiliza esses resultados e chama o mesmo `retrieve` para cada threshold.

Nao fazer sete chamadas ao LLM e sete embeddings da mesma query.

## Politica de selecao

Nenhum threshold pode ser recomendado se violar qualquer hard gate:

```text
system_leakage_count == 0
unsafe_accept_count == 0
ambiguous_context_failures == 0
unknown_system_failures == 0
```

Entre thresholds que passam os hard gates, o relatorio sintetico ordena candidatos por:

1. maior `correct_abstention_rate`;
2. maior `hit_at_3`;
3. maior `mrr`;
4. menor threshold somente como ultimo desempate, para evitar perda de cobertura desnecessaria.

Essa ordenacao produz um `synthetic_recommendation`, nao uma alteracao automatica da configuracao de producao.

## Regra para alterar o threshold oficial

O threshold oficial pode mudar somente se existir um conjunto real rotulado por humanos ou outro ground truth real aprovado e se:

1. o benchmark real utilizar a mesma receita/modelo do indice homologado;
2. os hard gates de seguranca continuarem zerados;
3. a nova opcao superar `0.65` nas metricas primarias definidas antes de observar os resultados;
4. o conjunto rotulado e sua metodologia estiverem documentados;
5. a mudanca ocorrer em PR separado ou commit explicitamente identificado como decisao de calibracao.

Como a Fase 3 da competicao nao possui atualmente um gold set corporativo humano, a decisao esperada e:

```text
runtime_threshold = 0.65
calibration_decision = HOLD
reason = no_real_labeled_gold_set
```

Se o benchmark sintetico recomendar outro valor, ele sera registrado apenas como diagnostico.

## Implementacao

Adicionar modulo:

```text
src/ai_service_desk/engine/evaluation.py
```

Responsabilidades:

- carregar e validar casos JSONL;
- avaliar resultados sem imprimir queries ou candidatos corporativos;
- calcular metricas puras;
- executar sweep com classificacao/embedding reutilizados;
- produzir recomendacao sintetica;
- produzir decisao final `HOLD` quando nao existir gold set real.

Nao modificar `retrieve` para encaixar o benchmark. O avaliador deve consumir o contrato existente.

## CLI

Adicionar comando:

```text
python -m ai_service_desk evaluate \
  --index <index> \
  --cases <cases.jsonl> \
  --report <report.json> \
  --checkout <checkout> \
  --url http://127.0.0.1:11434
```

Para benchmark sintetico, o indice pode estar em diretorio temporario ou externo. Para benchmark sobre dados reais, indice e relatorio devem continuar fora do checkout.

O comando imprime apenas resumo:

```text
casos
intent_accuracy
system_accuracy
hit_at_3
mrr
correct_abstention_rate
system_leakage_count
synthetic_recommendation
calibration_decision
runtime_threshold
```

Nunca imprime query, titulo, ticket ID real, descricao, `texto_busca` ou historico.

## Relatorio

O JSON de avaliacao e agregado e pode incluir resultados por `case_id`, mas nunca o texto da query nem conteudo de candidatos reais.

Formato conceitual:

```json
{
  "version": 1,
  "benchmark": "phase3-synthetic-v1",
  "cases": 28,
  "thresholds": {
    "0.50": {"hit_at_3": 0.0},
    "0.65": {"hit_at_3": 0.0}
  },
  "synthetic_recommendation": 0.65,
  "calibration": {
    "decision": "HOLD",
    "runtime_threshold": 0.65,
    "reason": "no_real_labeled_gold_set"
  }
}
```

## Workflow local

Adicionar:

```text
.github/workflows/phase3-evaluation.yml
```

Runner:

```text
[self-hosted, Windows, X64, ai-service-desk, ollama]
```

Fluxo:

1. checkout do `target_ref`;
2. Python 3.14;
3. instalar projeto;
4. construir indice do corpus sintetico em diretorio temporario;
5. executar avaliacao sintetica com o Ollama real;
6. validar hard gates;
7. executar benchmark de seguranca sobre o indice de 240 tickets da demo;
8. gravar somente relatorio agregado da parte real fora do checkout;
9. nao usar `upload-artifact` para dados reais.

O benchmark sintetico pode permanecer no workspace porque nao contem dados corporativos.

## CI hospedado

O CI hospedado nao usa Ollama.

Testes devem cobrir:

- schema de casos;
- metricas com resultados artificiais;
- MRR e hit@k;
- abstinencia correta/incorreta;
- deteccao de vazamento de sistema;
- politica de recomendacao;
- decisao `HOLD` sem gold set real;
- CLI sem vazamento;
- estrutura segura do workflow.

## Nao objetivos

Nao fazem parte da Fase 3:

- criar base de conhecimento;
- gerar respostas com RAG;
- promover historicos a procedimentos aprovados;
- reranker;
- fine tuning;
- treinamento do modelo;
- alteracao de embeddings;
- interface web;
- policy engine;
- execucao de acoes;
- afirmar percentual de chamados evitaveis com base no benchmark sintetico.

## Riscos e mitigacoes

### Benchmark sintetico otimista

Mitigacao: relatorios e documentacao dizem explicitamente que metricas sinteticas nao representam o corpus real.

### Ajustar threshold para melhorar demo

Mitigacao: threshold oficial nao muda sem gold set real rotulado.

### Repetir classificacao e embedding sete vezes

Mitigacao: cache por caso dentro da execucao do sweep.

### Vazamento de conteudo corporativo

Mitigacao: benchmark B usa apenas queries sinteticas e relatorio agregado sem candidatos ou textos.

### Confundir `confidence` com probabilidade

Mitigacao: `confidence` nao entra na politica de threshold e permanece descrito como autoavaliacao do classificador.

## Superficies esperadas

```text
src/ai_service_desk/engine/evaluation.py
src/ai_service_desk/cli.py
tests/fixtures/phase3_eval_corpus.csv
tests/fixtures/phase3_eval_cases.jsonl
tests/engine/test_evaluation.py
tests/test_cli.py
tests/test_workflows.py
.github/workflows/phase3-evaluation.yml
docs/evaluation/phase-3.md
README.md
docs/roadmap.md
```

Arquivos adicionais so devem ser criados se forem necessarios pelo desenho real.

## Gates objetivos de progresso

O percentual da Fase 3 sera medido pelos seguintes gates:

1. 10% - arquitetura atual inspecionada e escopo fechado;
2. 20% - spec e plano materializados;
3. 30% - schema e benchmark sintetico versionados e validados;
4. 40% - metricas puras implementadas com testes;
5. 50% - sweep de threshold implementado sem chamadas duplicadas ao modelo;
6. 60% - CLI e relatorio seguro implementados;
7. 70% - CI hospedado verde;
8. 80% - avaliacao local no Dell verde com modelos reais;
9. 90% - decisao de calibracao e documentacao final registradas;
10. 100% - revisao final, PR verde e merge em `main`.

## Criterios de saida

A Fase 3 esta concluida quando:

1. benchmark sintetico possui ground truth explicito e versionado;
2. metricas e sweep sao deterministas dado o mesmo resultado de modelo/embedding;
3. hard gates de seguranca sao aplicados antes de qualquer recomendacao;
4. benchmark da demo real nao afirma metricas de relevancia sem ground truth;
5. nenhuma query ou conteudo corporativo e exposto nos relatorios reais;
6. CI hospedado passa Python 3.14, Ruff e pytest;
7. workflow local passa no Dell com Ollama real;
8. decisao de calibracao e registrada;
9. `0.65` permanece se nao houver evidencia real rotulada para justificar mudanca;
10. PR final nao contem corpus real, subset real, indice real ou relatorio corporativo.
