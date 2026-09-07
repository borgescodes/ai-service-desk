# Fase 3: avaliação e calibração

A Fase 3 adiciona uma camada reproduzível de avaliação ao motor existente. Ela mede classificação, retrieval, abstinência e invariantes de segurança sem alterar o algoritmo de retrieval para melhorar o benchmark.

## O que é avaliado

O benchmark versionado `phase3-synthetic-v1` possui 28 consultas sintéticas e um corpus totalmente fictício. Ele cobre CIGAM, SIAGRI, impressão, rede, acesso, instalação de software, orientação, sistema desconhecido, contexto ambíguo e casos de evidência fraca.

As métricas agregadas incluem:

- `intent_accuracy`
- `system_accuracy`
- `hit_at_1`
- `hit_at_3`
- `mrr`
- `precision_at_3`
- `correct_abstention_rate`
- `unsafe_accept_count`
- `system_leakage_count`
- `ambiguous_context_failures`
- `unknown_system_failures`
- `execution_failures`
- latência p50 e p95

O sweep compara os thresholds `0.50`, `0.55`, `0.60`, `0.65`, `0.70`, `0.75` e `0.80`. Cada consulta é classificada e embeddada uma única vez; apenas o filtro de retrieval é repetido por threshold.

## Como interpretar os números

**Synthetic benchmark metrics are regression evidence, not real-corpus accuracy.**

As métricas do benchmark sintético são evidência de regressão, não precisão do corpus real. Elas não sustentam afirmações de precisão, recall, cobertura, taxa de resolução ou percentual de automação sobre os 240 tickets da demo ou sobre o snapshot completo de 15.542 tickets.

O subconjunto real da Fase 2A continua sendo usado somente para invariantes operacionais e de segurança. Seus históricos permanecem `HISTORICO_NAO_VALIDADO`.

## Hard gates

Uma recomendação sintética de threshold só é considerada elegível quando todos os seguintes contadores são zero:

```text
system_leakage_count
unsafe_accept_count
ambiguous_context_failures
unknown_system_failures
```

O relatório operacional também exige `execution_failures == 0` no threshold de runtime para retornar `ok=true`.

Entre thresholds sintéticos elegíveis, a ordenação prioriza, nesta ordem:

1. maior `correct_abstention_rate`;
2. maior `hit_at_3`;
3. maior `mrr`;
4. menor threshold em caso de empate completo.

Essa recomendação é apenas evidência experimental. Ela não altera configuração de produção.

## Decisão de calibração

**Runtime threshold remains 0.65 because no real human-labeled gold set exists.**

A decisão da Fase 3 é `HOLD`: o threshold oficial permanece em `0.65` enquanto não existir um conjunto corporativo real, rotulado por humanos e versionado para avaliação.

O campo `confidence` do classificador não é tratado como probabilidade calibrada e não participa da escolha do threshold.

Quando um gold set corporativo humano existir, uma eventual mudança de threshold deverá ser explícita, revisada e separada da recomendação sintética.

## Privacidade do relatório

O comando `evaluate` persiste somente métricas agregadas, recomendação sintética e decisão de calibração. O relatório declara explicitamente que não inclui:

- texto das consultas;
- identificadores de candidatos;
- conteúdo corporativo.

Nenhum artefato do workflow é enviado ao GitHub Actions. O relatório local fica fora do checkout Git.

## Execução local

O workflow permanente é `.github/workflows/phase3-evaluation.yml` e roda no runner Windows homologado com as labels `self-hosted`, `Windows`, `X64`, `ai-service-desk` e `ollama`.

Ele:

1. valida Python 3.14;
2. verifica os modelos Ollama locais;
3. constrói um índice temporário do corpus sintético em `RUNNER_TEMP`;
4. executa o benchmark e o sweep de thresholds;
5. grava o relatório agregado em `C:\ai-service-desk-data\phase-3\reports`;
6. reutiliza a demo real de 240 tickets apenas para verificar invariantes seguros da Fase 2A;
7. não usa `--show-history` e não publica artefatos.

Execução equivalente do avaliador:

```powershell
python -m ai_service_desk evaluate `
  --index <indice-sintetico-externo> `
  --cases tests/fixtures/phase3_eval_cases.jsonl `
  --report C:\ai-service-desk-data\phase-3\reports\phase3-evaluation.json `
  --checkout (Get-Location) `
  --url http://127.0.0.1:11434
```

## Critério para encerrar a Fase 3

A fase só é considerada homologada quando:

- CI hospedado passa em Python 3.14, Ruff e pytest;
- workflow local conclui com os modelos reais do Dell;
- hard gates no threshold `0.65` permanecem zerados;
- não há falhas de execução;
- o relatório continua agregado e sem conteúdo corporativo;
- o PR passa por revisão final antes do merge.
