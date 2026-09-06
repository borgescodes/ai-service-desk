# Fase 0 Repository Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a fundação reproduzível e verificável do AI Service Desk, sem migrar ainda o motor, o corpus TI ou qualquer lógica de IA.

**Architecture:** O repositório será backend-first, com pacote Python 3.14 em layout `src/`, qualidade determinística em GitHub-hosted CI e homologação com Ollama separada no runner Windows self-hosted já validado. A documentação será dividida por responsabilidade: operação no `README.md`, regras no `AGENTS.md`, ambiente em `docs/environment/`, direção em `docs/roadmap.md`, specs e planos em `docs/superpowers/`.

**Tech Stack:** Python 3.14, setuptools, pip, pytest, Ruff, GitHub Actions, PowerShell no smoke test local existente.

**Spec:** `docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md`

## Global Constraints

- Um único repositório, backend primeiro.
- Python 3.14 é a versão oficial da Fase 0.
- Usar `pyproject.toml`, `pip` e `.venv`; não introduzir Poetry ou uv.
- O pacote oficial usa layout `src/` e nome importável `ai_service_desk`.
- A Fase 0 não migra o motor atual e não adiciona dependências de LLM, embeddings ou retrieval.
- Não criar API web, banco, frontend, Docker, `.env.example` ou abstrações antecipadas.
- `pytest` e `ruff` são gates obrigatórios.
- CI determinístico roda em GitHub-hosted runner em pull requests.
- `.github/workflows/local-ai-smoke.yml` permanece separado, manual via `workflow_dispatch`, usando `[self-hosted, Windows, X64, ai-service-desk, ollama]`.
- Exports brutos do TiFlux ficam fora do Git; corpus TI real preparado só entra a partir da Fase 1.
- Segredos, senhas, tokens, cookies, chaves e credenciais nunca entram no Git.
- Documentação em português; código, módulos, testes e identificadores em inglês.
- Trabalhar em `phase-0-foundation` e integrar por pull request.
- Não fazer polling de GitHub Actions. Depois de abrir o PR, parar e aguardar o operador retornar com status ou log.
- Não afirmar conclusão sem evidência recente dos gates locais aplicáveis e do CI remoto do PR.

---

## File Map

**Criar:**

- `pyproject.toml`: empacotamento, Python 3.14, pytest e Ruff.
- `src/ai_service_desk/__init__.py`: pacote mínimo, sem lógica de negócio.
- `tests/test_package.py`: contrato de importação.
- `.github/workflows/ci.yml`: CI determinístico de PR.
- `.gitignore`: caches, ambiente local, segredos e artefatos gerados.
- `AGENTS.md`: regras normativas.
- `README.md`: entrada operacional.
- `docs/environment/local-demo.md`: ambiente Dell/Ollama/runner.
- `docs/roadmap.md`: fases 0 a 12.

**Preservar sem alteração funcional:**

- `.github/workflows/local-ai-smoke.yml`
- `docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md`
- `docs/superpowers/plans/2026-09-06-phase-0-repository-foundation.md`

---

### Task 1: Bootstrap do pacote Python

**Files:**
- Create: `pyproject.toml`
- Create: `tests/test_package.py`
- Create: `src/ai_service_desk/__init__.py`

**Interfaces:**
- Consumes: Python 3.14 e pip.
- Produces: pacote instalável `ai_service_desk`, extra `.[dev]`, comandos `python -m pytest`, `python -m ruff check .` e `python -m ruff format --check .`.

- [ ] **Step 1: Criar `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-service-desk"
version = "0.1.0"
description = "Camada inteligente antes da abertura de chamados de TI."
requires-python = ">=3.14,<3.15"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "ruff>=0.12",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

- [ ] **Step 2: Preparar ambiente e instalar ferramentas do projeto antes de existir o pacote**

PowerShell, na raiz do repositório:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
New-Item -ItemType Directory -Force src, tests | Out-Null
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Expected: `python --version` reporta `Python 3.14.x` e a instalação termina com exit code 0. Se não for 3.14.x, interromper; não flexibilizar `requires-python`.

- [ ] **Step 3: Escrever o teste estrutural antes de criar o pacote**

`tests/test_package.py`:

```python
import importlib


def test_package_is_importable() -> None:
    module = importlib.import_module("ai_service_desk")

    assert module.__name__ == "ai_service_desk"
```

- [ ] **Step 4: Rodar o teste e confirmar a falha esperada**

```powershell
python -m pytest tests/test_package.py -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'ai_service_desk'`.

- [ ] **Step 5: Criar a implementação mínima**

`src/ai_service_desk/__init__.py`:

```python
"""AI Service Desk backend package."""
```

Não adicionar versão, configuração, cliente de modelo, provider ou lógica de negócio.

- [ ] **Step 6: Reinstalar e confirmar o teste verde**

```powershell
python -m pip install -e ".[dev]"
python -m pytest tests/test_package.py -v
```

Expected: `test_package_is_importable PASSED`.

- [ ] **Step 7: Rodar todos os gates locais**

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import ai_service_desk; print(ai_service_desk.__name__)"
```

Expected: todos exit code 0, `pytest` com `1 passed` e último output `ai_service_desk`.

- [ ] **Step 8: Commitar**

```bash
git add pyproject.toml src/ai_service_desk/__init__.py tests/test_package.py
git commit -m "build: bootstrap python project"
```

---

### Task 2: CI determinístico em pull requests

**Files:**
- Create: `.github/workflows/ci.yml`
- Preserve: `.github/workflows/local-ai-smoke.yml`

**Interfaces:**
- Consumes: `pyproject.toml` e `.[dev]` da Task 1.
- Produces: job `Python quality` em `ubuntu-latest`, executado em `pull_request`.

- [ ] **Step 1: Criar `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  pull_request:

permissions:
  contents: read

jobs:
  quality:
    name: Python quality
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.14"

      - name: Install project
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Ruff lint
        run: python -m ruff check .

      - name: Ruff format
        run: python -m ruff format --check .

      - name: Pytest
        run: python -m pytest
```

Não adicionar Ollama, modelos, secrets, matrix, services ou job Windows neste workflow.

- [ ] **Step 2: Confirmar que o smoke local não mudou**

```bash
git diff main -- .github/workflows/local-ai-smoke.yml
```

Expected: saída vazia.

- [ ] **Step 3: Rodar gates locais após adicionar o YAML**

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected: exit code 0. A validação real do workflow ocorre quando o PR dispara GitHub Actions.

- [ ] **Step 4: Commitar**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add hosted python quality checks"
```

---

### Task 3: Governança e `.gitignore`

**Files:**
- Create: `.gitignore`
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: regras aprovadas na spec.
- Produces: política normativa e bloqueio básico de arquivos locais/sensíveis.

- [ ] **Step 1: Criar `.gitignore`**

```gitignore
# Python
.venv/
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/

# Test and lint caches
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Local environment and secrets
.env
.env.*

# IDE and OS
.vscode/
.idea/
.DS_Store
Thumbs.db

# Generated project artifacts
artifacts/
embeddings/
logs/
reports/
```

Não criar `.env.example` nesta fase.

- [ ] **Step 2: Criar `AGENTS.md`**

```markdown
# AGENTS.md

## Escopo

Estas regras valem para todo o repositório AI Service Desk.

## Fluxo de trabalho

- Trabalhe em branch curta e integre mudanças por pull request.
- Não implemente uma fase futura antes de fechar os critérios de saída da fase atual.
- Use TDD para comportamento de produto: teste falhando, implementação mínima, teste passando.
- Arquivos puramente declarativos ou de configuração podem ser validados estruturalmente sem teste artificial.
- Antes de concluir uma mudança, execute `python -m pytest`, `python -m ruff check .` e `python -m ruff format --check .`.
- Não afirme sucesso ou conclusão sem evidência recente das verificações aplicáveis.

## GitHub Actions

- O CI hospedado valida mudanças determinísticas em pull requests.
- O runner Windows self-hosted é usado para homologações explícitas com Ollama.
- Não faça polling de GitHub Actions.
- Quando uma execução remota for necessária, dispare ou identifique o run, informe o que precisa concluir e pare. O operador acompanha o GitHub e retorna com status ou log.

## Dados e segredos

- Nunca versione senhas, tokens, cookies, chaves, credenciais ou arquivos `.env` com valores reais.
- Exports brutos do TiFlux ficam fora do Git.
- Dados corporativos preparados podem ser versionados quando a fase correspondente autorizar e houver verificação específica antes do commit.
- Corpus TI real não entra antes da Fase 1.
- Embeddings, caches, logs e relatórios gerados ficam fora do Git por padrão.

## Documentação

- Documentação explicativa deve ser escrita em português.
- Código, módulos, arquivos técnicos, testes e identificadores devem usar nomes em inglês.
- Mantenha este arquivo curto e normativo.
- Arquitetura detalhada pertence a `docs/superpowers/specs/`.
- Planos de implementação pertencem a `docs/superpowers/plans/`.
- Ambiente de homologação pertence a `docs/environment/`.
```

- [ ] **Step 3: Validar regras de ignore**

```bash
git check-ignore -v .venv .env .env.example artifacts/test.bin embeddings/index.npy logs/app.log reports/output.json
```

Expected: todos os caminhos aparecem como ignorados por uma regra de `.gitignore`.

- [ ] **Step 4: Rodar gates e commit**

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected: exit code 0.

```bash
git add .gitignore AGENTS.md
git commit -m "docs: add repository working rules"
```

---

### Task 4: Documentação operacional e roadmap

**Files:**
- Create: `README.md`
- Create: `docs/environment/local-demo.md`
- Create: `docs/roadmap.md`

**Interfaces:**
- Consumes: comandos das Tasks 1 a 3 e fatos já validados do Dell/Ollama/runner.
- Produces: entrada do projeto, registro do ambiente atual e sequência macro das fases.

- [ ] **Step 1: Criar `README.md`**

```markdown
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
```

- [ ] **Step 2: Criar `docs/environment/local-demo.md`**

```markdown
# Ambiente local de homologação

Este documento registra a máquina usada para desenvolvimento e demonstração local. Ele não define a arquitetura permanente do produto web.

## Máquina

- Sistema operacional: Windows 11 Pro
- Equipamento: notebook Dell
- Processador: Intel Core 7 250U
- Memória: 32 GB RAM
- GPU: Intel integrada
- Armazenamento: aproximadamente 477 GB

## Python e Ollama

- Python: 3.14.7
- Ambiente do projeto: `.venv`
- Dependências: `pip`
- Ollama: 0.33.3
- API: `http://localhost:11434`
- Chat: `qwen3.5:4b`
- Embeddings: `qwen3-embedding:0.6b`
- Dimensão validada do embedding: 1024

Chamadas de chat da aplicação devem usar `think=false` quando o cliente Ollama for implementado. O smoke test já usa essa configuração.

## GitHub self-hosted runner

- Nome: `ai-service-desk-dell`
- Labels: `self-hosted`, `Windows`, `X64`, `ai-service-desk`, `ollama`
- Diretório: `C:\actions-runner`
- Sessão: `juparana-pgm\pedro.borges`
- Modo: interativo via `run.cmd`
- Serviço Windows: `Stopped` e `Disabled`

O serviço permanece desabilitado porque o contexto de serviço não enxergava o mesmo Python/Ollama e a máquina apresenta secure channel de domínio quebrado. Reparar o domínio não faz parte do escopo atual.

Para disponibilizar o runner:

```powershell
cd C:\actions-runner
.\run.cmd
```

A janela deve permanecer aberta e mostrar `Listening for Jobs`.

## Workflow de homologação

Arquivo: `.github/workflows/local-ai-smoke.yml`

Trigger: `workflow_dispatch`

Runner: `[self-hosted, Windows, X64, ai-service-desk, ollama]`

O smoke verifica identidade do runner, Python local, `/api/tags`, presença dos dois modelos, chat com `think=false` e embedding com dimensão 1024.

O workflow usa `-ExecutionPolicy Bypass` somente no processo do job. Isso não altera permanentemente a Execution Policy do Windows.

## Regra operacional

Não fazer polling. Depois de disparar ou identificar um run, o operador acompanha o GitHub Actions e retorna com `success` ou com o log da etapa que falhou.

## Limite arquitetural

Ollama local é uma implementação de provedor de modelo para desenvolvimento e demonstração. O produto web futuro não deve depender conceitualmente deste notebook ou deste Ollama local.
```

- [ ] **Step 3: Criar `docs/roadmap.md`**

```markdown
# Roadmap macro

Este roadmap registra a direção atual do AI Service Desk. Ele não é backlog detalhado e não congela o desenho das fases futuras. Cada fase recebe sua própria especificação, critérios de saída e plano antes da implementação.

| Fase | Objetivo |
| --- | --- |
| 0 | Fundação do repositório |
| 1 | Motor atual reproduzível |
| 2 | Retrieval no corpus TI real |
| 3 | Avaliação e calibração |
| 4 | FAQ e base de conhecimento |
| 5 | Triagem conversacional |
| 6 | Playbooks |
| 7 | Policy engine |
| 8 | Execução controlada |
| 9 | Integrações de sistemas |
| 10 | Escalonamento e roteamento |
| 11 | Aprendizado e prevenção |
| 12 | Interface web e demonstração final |

## Regra de progressão

O projeto não avança apenas porque uma fase parece funcional. A transição exige evidência compatível com os critérios mensuráveis definidos na especificação da fase em execução.
```

- [ ] **Step 4: Verificar caminhos documentados**

```powershell
python -c "from pathlib import Path; paths = ['README.md', 'AGENTS.md', 'docs/environment/local-demo.md', 'docs/roadmap.md', 'docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md', 'docs/superpowers/plans/2026-09-06-phase-0-repository-foundation.md']; missing = [p for p in paths if not Path(p).is_file()]; print('missing:', missing); raise SystemExit(bool(missing))"
```

Expected: `missing: []`.

- [ ] **Step 5: Rodar gates e commit**

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import ai_service_desk; print(ai_service_desk.__name__)"
```

Expected: todos exit code 0 e último output `ai_service_desk`.

```bash
git add README.md docs/environment/local-demo.md docs/roadmap.md
git commit -m "docs: document phase 0 foundation"
```

---

### Task 5: Verificação integral antes do PR

**Files:**
- Review: todos os arquivos da branch `phase-0-foundation`
- Preserve: `.github/workflows/local-ai-smoke.yml`

**Interfaces:**
- Consumes: Tasks 1 a 4 e a spec aprovada.
- Produces: branch pronta para revisão remota com evidência local fresca.

- [ ] **Step 1: Conferir o diff contra `main`**

```bash
git status --short
git diff --stat main...HEAD
git diff --name-status main...HEAD
git diff main -- .github/workflows/local-ai-smoke.yml
```

Expected: working tree limpa; `local-ai-smoke.yml` sem diff. Mudanças permitidas:

```text
.github/workflows/ci.yml
.gitignore
AGENTS.md
README.md
pyproject.toml
src/ai_service_desk/__init__.py
tests/test_package.py
docs/environment/local-demo.md
docs/roadmap.md
docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md
docs/superpowers/plans/2026-09-06-phase-0-repository-foundation.md
```

- [ ] **Step 2: Confirmar ausência de escopo antecipado**

```powershell
python -c "from pathlib import Path; forbidden = ['web', 'data', 'Dockerfile', 'docker-compose.yml', '.env.example']; found = [p for p in forbidden if Path(p).exists()]; print('forbidden_found:', found); raise SystemExit(bool(found))"
```

Expected: `forbidden_found: []`.

Confirmar também em `pyproject.toml`: `dependencies = []`; extra `dev` contém somente pytest e Ruff.

- [ ] **Step 3: Executar a verificação local final, sem reutilizar resultado antigo**

```powershell
python --version
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import ai_service_desk; print(ai_service_desk.__name__)"
```

Expected: Python 3.14.x, todos os gates exit code 0, `pytest` com `1 passed`, import com output `ai_service_desk`.

- [ ] **Step 4: Verificar whitespace**

```bash
git diff --check main...HEAD
```

Expected: saída vazia e exit code 0.

- [ ] **Step 5: Revisar critérios da spec um a um**

```text
[ ] estrutura corresponde ao desenho aprovado
[ ] Python 3.14 declarado em requires-python
[ ] pip install -e .[dev] funciona
[ ] import ai_service_desk funciona
[ ] pytest passa
[ ] ruff check . passa
[ ] ruff format --check . passa
[ ] CI hospedado existe e usa pull_request
[ ] smoke local permanece manual via workflow_dispatch
[ ] documentação Dell/Ollama existe
[ ] política de dados e segredos está registrada
[ ] roadmap existe
[ ] motor atual não foi migrado
[ ] corpus TI não foi adicionado
[ ] nenhuma dependência de IA foi adicionada
[ ] integração será somente por PR
```

Qualquer item não confirmado bloqueia a abertura do PR.

---

### Task 6: Abrir PR e validar o CI hospedado

**Files:**
- No file changes expected.
- Remote artifact: pull request `phase-0-foundation` -> `main`.

**Interfaces:**
- Consumes: branch verificada na Task 5.
- Produces: PR revisável e execução real do job `Python quality`.

- [ ] **Step 1: Abrir o pull request**

Título:

```text
build: establish phase 0 repository foundation
```

Body:

```markdown
## Objetivo

Implementa a Fase 0 do AI Service Desk: fundação do repositório, pacote Python 3.14, qualidade determinística, documentação e governança.

## Incluído

- pacote `ai_service_desk` em layout `src/`
- `pyproject.toml` com pytest e Ruff
- CI GitHub-hosted em pull requests
- preservação do smoke test manual com Ollama
- README, AGENTS, ambiente local e roadmap
- spec e plano da Fase 0

## Fora de escopo

- motor atual
- corpus TI
- retrieval, embeddings e LLM no pacote
- API, banco, frontend e Docker

## Verificação local

- `python -m ruff check .`
- `python -m ruff format --check .`
- `python -m pytest`
- `python -c "import ai_service_desk"`

Spec: `docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md`
```

Base: `main`. Head: `phase-0-foundation`.

- [ ] **Step 2: Parar após o CI ser disparado**

Informar ao operador:

```text
O PR foi aberto e o CI hospedado precisa concluir o job "Python quality". Monitore no GitHub e retorne com "success" ou com o log da etapa que falhou.
```

Não consultar repetidamente o status.

- [ ] **Step 3: Processar o retorno do operador**

Se retornar `success`, registrar essa evidência e, somente se necessário e já houver identificador disponível, fazer no máximo uma leitura pontual do run concluído. Se retornar falha, usar o log fornecido para diagnosticar a causa antes de qualquer alteração.

- [ ] **Step 4: Revisar o PR antes do merge**

```text
[ ] CI Python quality = success
[ ] diff corresponde à Fase 0
[ ] nenhum segredo ou export bruto foi adicionado
[ ] local-ai-smoke.yml não sofreu mudança funcional
[ ] critérios da spec continuam atendidos
```

- [ ] **Step 5: Integrar somente após revisão**

Usar o fluxo normal de merge do pull request. Não mover `main` diretamente e não fazer force push.

---

## Final Verification Checklist

Antes de declarar a Fase 0 concluída, exigir evidência fresca de:

```text
[ ] Python 3.14.x
[ ] pip install -e .[dev] com sucesso
[ ] ruff check . exit 0
[ ] ruff format --check . exit 0
[ ] pytest 1 passed, 0 failed
[ ] import ai_service_desk funciona
[ ] CI hospedado do PR = success
[ ] local-ai-smoke.yml permanece manual e separado
[ ] README, AGENTS, local-demo e roadmap existem
[ ] spec e plano estão versionados
[ ] nenhum motor, corpus TI ou dependência de IA entrou na Fase 0
[ ] PR foi revisado antes do merge
```

O smoke test local com Ollama é evidência separada do ambiente de homologação e não precisa ser disparado em todo PR da Fase 0, pois o workflow deve ser preservado sem alteração funcional.
