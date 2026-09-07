# AI Service Desk

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

O AI Service Desk é uma camada inteligente anterior à abertura de chamados de TI. A Fase 1 incorporou o motor local 2.1 ao pacote oficial `ai_service_desk`, preservando classificação conservadora, segurança, indexação reproduzível e retrieval com abstinência.

A Fase 2 foi dividida em dois trilhos:

- **Fase 2A, gate da competição:** retrieval demonstrável sobre um subconjunto real, controlado e determinístico de 240 tickets.
- **Fase 2B, evidência de escala:** auditoria e indexação do snapshot completo de 15.542 tickets, sem bloquear a evolução do produto.

A Fase 3 adiciona avaliação reproduzível, sweep de thresholds e uma decisão conservadora de calibração. O benchmark versionado é sintético e serve como evidência de regressão, não como medida de precisão do corpus corporativo.

Históricos recuperados são evidências não validadas. Eles não são soluções aprovadas e não autorizam ações.

## Requisitos

- Python 3.14
- Git
- Ollama somente para os comandos que usam modelos locais

## Ambiente local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Qualidade

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## CLI

A interface operacional oficial é:

```powershell
python -m ai_service_desk --help
```

Inspecionar um corpus sem exibir históricos e sem chamar IA:

```powershell
python -m ai_service_desk inspect --file <arquivo.csv>
```

Auditar um snapshot preparado contra um manifesto versionado, gerando somente relatório agregado:

```powershell
python -m ai_service_desk audit `
  --file <corpus.csv> `
  --manifest docs/data/phase-2-corpus-v1.json `
  --report <relatorio-agregado.json>
```

Gerar o subconjunto determinístico da Fase 2A, sem chamar Ollama:

```powershell
python -m ai_service_desk demo-subset `
  --file C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv `
  --output C:\ai-service-desk-data\phase-2\demo\demo_subset.csv `
  --report C:\ai-service-desk-data\phase-2\demo\reports\subset.json `
  --checkout (Get-Location) `
  --per-group 40
```

Validar retrieval sobre o subconjunto da competição:

```powershell
python -m ai_service_desk demo-smoke `
  --file C:\ai-service-desk-data\phase-2\demo\demo_subset.csv `
  --subset-report C:\ai-service-desk-data\phase-2\demo\reports\subset.json `
  --index C:\ai-service-desk-data\phase-2\demo\index `
  --report C:\ai-service-desk-data\phase-2\demo\reports\smoke.json `
  --checkout (Get-Location) `
  --url http://127.0.0.1:11434
```

Verificar o Ollama local e os modelos obrigatórios:

```powershell
python -m ai_service_desk doctor
```

A homologação de escala da Fase 2B usa `real-smoke`. Corpus, índice e relatório precisam estar fora do checkout Git:

```powershell
python -m ai_service_desk real-smoke `
  --file C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv `
  --manifest docs/data/phase-2-corpus-v1.json `
  --index C:\ai-service-desk-data\phase-2\index `
  --report C:\ai-service-desk-data\phase-2\reports\real-corpus-smoke.json `
  --checkout (Get-Location) `
  --url http://127.0.0.1:11434
```

Executar o benchmark sintético e a decisão de calibração da Fase 3:

```powershell
python -m ai_service_desk evaluate `
  --index <indice-sintetico-externo> `
  --cases tests/fixtures/phase3_eval_cases.jsonl `
  --report C:\ai-service-desk-data\phase-3\reports\phase3-evaluation.json `
  --checkout (Get-Location) `
  --url http://127.0.0.1:11434
```

Também estão disponíveis `show-index`, `prepare`, `index`, `import-legacy`, `search` e `validate`.

`doctor`, `index`, `import-legacy`, `search`, `validate`, `demo-smoke`, `real-smoke` e `evaluate` dependem do Ollama local. O cliente aceita somente HTTP em loopback e não baixa modelos automaticamente.

## Fase 2A: demonstração da competição

O subset padrão possui 240 registros reais, distribuídos deterministicamente em seis grupos de 40:

- CIGAM
- SIAGRI
- impressão
- acesso
- software
- casos gerais restantes

A escolha dentro de cada grupo é ordenada por SHA-256 do `ticket_id`. Isso torna a seleção reproduzível e evita escolher manualmente apenas casos com resultados convenientes.

Esse subset **não é um dataset de avaliação**. Ele não sustenta afirmações de precisão, recall, cobertura ou percentual global de automação. O objetivo da Fase 2A é demonstrar invariantes do produto com tempo de preparação compatível com a competição.

Os cenários automáticos cobrem CIGAM, SIAGRI, impressão, sistema inexistente e contexto CIGAM + SIAGRI ambíguo. A demonstração também verifica que o retrieval não promove evidência de outro sistema e que sabe retornar `SEM_CONTEXTO`, `CONTEXTO_AMBIGUO` ou `SEM_EVIDENCIA` quando necessário.

## Fase 2B: escala do corpus completo

O snapshot completo possui 15.542 tickets. Sua indexação continua válida como prova adicional de escala, integridade e retomada por checkpoint, mas não bloqueia interface, triagem conversacional ou demais funcionalidades voltadas à competição.

## Fase 3: avaliação e calibração

O benchmark `phase3-synthetic-v1` possui 28 consultas sintéticas com ground truth. Ele mede classificação, retrieval, abstinência, vazamento entre sistemas, falhas de contexto e latência.

O sweep compara `0.50`, `0.55`, `0.60`, `0.65`, `0.70`, `0.75` e `0.80`, reutilizando a mesma classificação e o mesmo embedding de cada consulta. Os hard gates exigem zero vazamento de sistema, zero aceitação insegura e zero falhas nos casos de sistema desconhecido e contexto ambíguo.

**As métricas sintéticas são evidência de regressão, não precisão no corpus real.** O threshold de runtime permanece em `0.65` com decisão `HOLD` porque ainda não existe um gold set corporativo real rotulado por humanos. Uma recomendação sintética não altera o runtime automaticamente.

Detalhes de métricas, privacidade e homologação estão em `docs/evaluation/phase-3.md`.

## Dados

Exports brutos do TiFlux, corpus corporativo real, subconjunto real da demo, embeddings, índices, logs e relatórios gerados ficam fora do Git. Os testes e o CI hospedado usam somente dados sintéticos.

O snapshot v1 da Fase 2 é descrito por `docs/data/phase-2-corpus-v1.json`. O manifesto guarda somente schema, contagens e fingerprints seguros. `base_ti_preparada.csv`, `demo_subset.csv`, `documents.jsonl` e `embeddings.npy` não são versionados.

O threshold `0.65` permanece oficial por decisão `HOLD` da Fase 3. Ele não é apresentado como probabilidade calibrada nem como evidência de precisão real enquanto não existir um gold set corporativo humano.

## CI e homologação

O CI hospedado valida instalação em Python 3.14, Ruff e pytest sem acessar Ollama ou dados corporativos reais.

A homologação local é separada:

- `.github/workflows/local-ai-smoke.yml` valida runner, Python, Ollama e modelos.
- `.github/workflows/engine-smoke.yml` valida o motor oficial ponta a ponta com corpus sintético.
- `.github/workflows/demo-retrieval-smoke.yml` é o gate da Fase 2A e valida o subconjunto real de 240 registros no Dell sem publicar dados.
- `.github/workflows/real-corpus-smoke.yml` valida o snapshot completo da Fase 2B como evidência adicional de escala.
- `.github/workflows/phase3-evaluation.yml` executa o benchmark sintético, a decisão de calibração e as invariantes seguras da demo no Dell.

Os workflows locais são manuais e executam no runner Windows homologado.

## Documentação

- Especificações: `docs/superpowers/specs/`
- Planos: `docs/superpowers/plans/`
- Avaliação e calibração: `docs/evaluation/phase-3.md`
- Manifesto seguro da Fase 2: `docs/data/phase-2-corpus-v1.json`
- Equivalência do motor 2.1: `docs/migration/engine-v2.1-equivalence.md`
- Homologação local: `docs/environment/local-demo.md`
- Roadmap: `docs/roadmap.md`
