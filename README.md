# AI Service Desk

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

O AI Service Desk é uma camada inteligente anterior à abertura de chamados de TI. A Fase 1 incorporou o motor local 2.1 ao pacote oficial `ai_service_desk`, preservando classificação conservadora, segurança, indexação reproduzível e retrieval com abstinência. A Fase 2 adiciona auditoria e homologação reproduzível sobre um snapshot corporativo mantido fora do Git.

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

Verificar o Ollama local e os modelos obrigatórios:

```powershell
python -m ai_service_desk doctor
```

A homologação completa da Fase 2 usa `real-smoke`. Corpus, índice e relatório precisam estar fora do checkout Git:

```powershell
python -m ai_service_desk real-smoke `
  --file C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv `
  --manifest docs/data/phase-2-corpus-v1.json `
  --index C:\ai-service-desk-data\phase-2\index `
  --report C:\ai-service-desk-data\phase-2\reports\real-corpus-smoke.json `
  --checkout (Get-Location) `
  --url http://127.0.0.1:11434
```

Também estão disponíveis `show-index`, `prepare`, `index`, `import-legacy`, `search` e `validate`.

`doctor`, `index`, `import-legacy`, `search`, `validate` e `real-smoke` dependem do Ollama local. O cliente aceita somente HTTP em loopback e não baixa modelos automaticamente.

## Dados

Exports brutos do TiFlux, corpus corporativo real, embeddings, índices, logs e relatórios gerados ficam fora do Git. Os testes e o CI hospedado usam somente dados sintéticos.

O snapshot v1 da Fase 2 é descrito por `docs/data/phase-2-corpus-v1.json`. O manifesto guarda somente schema, contagens e fingerprints seguros. O arquivo `base_ti_preparada.csv`, `documents.jsonl` e `embeddings.npy` não são versionados.

O threshold `0.65` é comportamento legado reproduzido. Ele ainda não é um valor calibrado. Avaliação e calibração pertencem à Fase 3.

## CI e homologação

O CI hospedado valida instalação em Python 3.14, Ruff e pytest sem acessar Ollama ou dados corporativos reais.

A homologação local é separada:

- `.github/workflows/local-ai-smoke.yml` valida runner, Python, Ollama e modelos.
- `.github/workflows/engine-smoke.yml` valida o motor oficial ponta a ponta com corpus sintético.
- `.github/workflows/real-corpus-smoke.yml` audita, indexa e valida invariantes sobre o snapshot real mantido no Dell, sem publicar corpus, índice ou relatório como artifact.

Os workflows locais são manuais e executam no runner Windows homologado.

## Documentação

- Especificações: `docs/superpowers/specs/`
- Planos: `docs/superpowers/plans/`
- Manifesto seguro da Fase 2: `docs/data/phase-2-corpus-v1.json`
- Equivalência do motor 2.1: `docs/migration/engine-v2.1-equivalence.md`
- Homologação local: `docs/environment/local-demo.md`
- Roadmap: `docs/roadmap.md`
