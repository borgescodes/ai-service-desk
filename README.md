# AI Service Desk

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

O AI Service Desk é uma camada inteligente anterior à abertura de chamados de TI. O produto evoluirá para entender solicitações, tentar resolvê-las com conhecimento e ações controladas e escalar apenas quando a intervenção humana for necessária.

A Fase 0 contém somente a fundação técnica do repositório. O motor atual, o corpus TI e as capacidades de IA entram em fases posteriores.

## Requisitos

- Python 3.14
- Git

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

## Documentação

- Especificações: `docs/superpowers/specs/`
- Planos: `docs/superpowers/plans/`
- Homologação local: `docs/environment/local-demo.md`
- Roadmap: `docs/roadmap.md`

## Homologação local com IA

O smoke test com Ollama roda separadamente em um runner Windows self-hosted e é disparado manualmente por GitHub Actions. Consulte `docs/environment/local-demo.md` antes de executá-lo.
