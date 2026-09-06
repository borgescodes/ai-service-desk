# AI Service Desk

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

O AI Service Desk é uma camada inteligente anterior à abertura de chamados de TI. A Fase 1 incorpora o motor local 2.1 ao pacote oficial `ai_service_desk`, preservando classificação conservadora, segurança, indexação reproduzível e retrieval com abstinência.

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

Verificar o Ollama local e os modelos obrigatórios:

```powershell
python -m ai_service_desk doctor
```

Também estão disponíveis `show-index`, `prepare`, `index`, `import-legacy`, `search` e `validate`.

`doctor`, `index`, `import-legacy`, `search` e `validate` dependem do Ollama local. O cliente aceita somente HTTP em loopback e não baixa modelos automaticamente.

## Dados

Exports brutos do TiFlux, corpus corporativo real, embeddings, índices, logs e relatórios gerados ficam fora do Git. Os testes e a homologação versionada usam somente dados sintéticos.

O threshold `0.65` é comportamento legado reproduzido. Ele ainda não é um valor calibrado.

## CI e homologação

O CI hospedado valida instalação em Python 3.14, Ruff e pytest sem acessar Ollama real.

A homologação local é separada:

- `.github/workflows/local-ai-smoke.yml` valida runner, Python, Ollama e modelos.
- `.github/workflows/engine-smoke.yml` valida o motor oficial ponta a ponta com corpus sintético.

Os workflows locais são manuais e executam no runner Windows homologado.

## Documentação

- Especificações: `docs/superpowers/specs/`
- Planos: `docs/superpowers/plans/`
- Equivalência do motor 2.1: `docs/migration/engine-v2.1-equivalence.md`
- Homologação local: `docs/environment/local-demo.md`
- Roadmap: `docs/roadmap.md`
