# Fase 0 Repository Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a fundação reproduzível e verificável do AI Service Desk, sem migrar ainda o motor, o corpus TI ou qualquer lógica de IA.

**Architecture:** O repositório será backend-first, com um pacote Python 3.14 em layout `src/`, testes e qualidade determinística em GitHub-hosted CI, e homologação com Ollama mantida separada no runner Windows self-hosted já validado. A documentação será curta e dividida por responsabilidade: operação no `README.md`, regras no `AGENTS.md`, ambiente em `docs/environment/`, direção macro em `docs/roadmap.md`, e decisões/planos em `docs/superpowers/`.

**Tech Stack:** Python 3.14, setuptools, pip, pytest, Ruff, GitHub Actions, PowerShell para o smoke test local existente.

**Spec:** `docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md`

## Global Constraints

- Um único repositório, backend primeiro.
- Python 3.14 é a versão oficial da Fase 0.
- Usar `pyproject.toml`, `pip` e `.venv`; não introduzir Poetry ou uv.
- O pacote oficial deve usar layout `src/` com nome importável `ai_service_desk`.
- A Fase 0 não migra o motor atual e não adiciona dependências de LLM, embeddings ou retrieval.
- Não criar API web, banco, frontend, Docker, `.env.example` ou abstrações antecipadas.
- `pytest` e `ruff` são gates obrigatórios de qualidade.
- CI determinístico deve rodar em GitHub-hosted runner em pull requests.
- `local-ai-smoke.yml` deve permanecer separado, manual via `workflow_dispatch`, e usar o runner `[self-hosted, Windows, X64, ai-service-desk, ollama]`.
- Exports brutos do TiFlux ficam fora do Git.
- O corpus TI real preparado só entra a partir da Fase 1.
- Segredos, tokens, cookies, senhas, chaves e credenciais nunca entram no Git.
- Documentação em português; código, módulos, nomes técnicos e identificadores em inglês.
- Trabalhar na branch `phase-0-foundation` e integrar por pull request.
- Não fazer polling de GitHub Actions. Depois de abrir o PR e o CI iniciar, parar e aguardar o operador retornar com status ou log.
- Não afirmar conclusão sem evidência recente de `pytest`, `ruff check`, `ruff format --check`, import do pacote e CI remoto do PR.

---

## File Map

### Criar

- `pyproject.toml`: metadados do pacote, Python 3.14, dependências de desenvolvimento e configuração de pytest/Ruff.
- `src/ai_service_desk/__init__.py`: pacote Python mínimo, sem lógica de negócio.
- `tests/test_package.py`: prova de que o pacote oficial é importável.
- `.github/workflows/ci.yml`: CI determinístico em pull requests.
- `.gitignore`: exclusões de ambiente local, caches, segredos e artefatos gerados.
- `AGENTS.md`: regras normativas curtas para trabalho no repositório.
- `README.md`: entrada operacional curta do projeto.
- `docs/environment/local-demo.md`: ambiente Dell/Ollama/runner efetivamente validado.
- `docs/roadmap.md`: direção macro das fases 0 a 12.

### Preservar sem alteração nesta fase

- `.github/workflows/local-ai-smoke.yml`: smoke test manual já validado com Python local, Ollama, `qwen3.5:4b` e `qwen3-embedding:0.6b`.
- `docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md`: spec aprovada.
- `docs/superpowers/plans/2026-09-06-phase-0-repository-foundation.md`: este plano.

---

### Task 1: Bootstrap do pacote Python e gates locais

**Files:**
- Create: `pyproject.toml`
- Create: `tests/test_package.py`
- Create: `src/ai_service_desk/__init__.py`

**Interfaces:**
- Consumes: Python 3.14 e `pip` disponíveis no ambiente de desenvolvimento.
- Produces: pacote instalável `ai_service_desk`; extra de desenvolvimento `.[dev]`; comandos oficiais `pytest`, `ruff check .` e `ruff format --check .`.

> Nota de processo: `pyproject.toml` e o arquivo mínimo `__init__.py` são scaffolding/configuração sem comportamento de produto. A regra TDD será aplicada ao comportamento de produto a partir das fases em que ele existir. Nesta tarefa, o teste estrutural é a evidência do contrato de empacotamento e importação.

- [ ] **Step 1: Criar `pyproject.toml` com o contrato mínimo da Fase 0**

Conteúdo exato:

```toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-service-desk"
version = "0.1.0"
description = "Camada inteligente antes da abertura de chamados de TI."
readme = "README.md"
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

- [ ] **Step 2: Criar o ambiente virtual e instalar o projeto em modo editável**

No PowerShell, a partir da raiz do repositório:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Expected:

```text
Python 3.14.x
Successfully installed ... ai-service-desk ... pytest ... ruff ...
```

Se `python --version` não reportar 3.14.x, interromper a tarefa. Não flexibilizar `requires-python` para contornar o ambiente.

- [ ] **Step 3: Criar o teste estrutural de importação**

Criar `tests/test_package.py`:

```python
import importlib


def test_package_is_importable() -> None:
    module = importlib.import_module("ai_service_desk")

    assert module.__name__ == "ai_service_desk"
```

- [ ] **Step 4: Executar o teste antes de criar o pacote**

Run:

```powershell
python -m pytest tests/test_package.py -v
```

Expected: FAIL com `ModuleNotFoundError: No module named 'ai_service_desk'`.

Se a instalação editável feita no Step 2 tiver criado metadados mas nenhum pacote importável, o teste deve falhar exatamente pelo módulo ausente. Se a instalação falhar antes por ausência de `src/`, crie apenas o diretório físico `src` e repita a instalação, sem criar `src/ai_service_desk/__init__.py` antes desta evidência de falha.

- [ ] **Step 5: Criar o pacote mínimo**

Criar `src/ai_service_desk/__init__.py`:

```python
"""AI Service Desk backend package."""
```

Não adicionar `__version__`, configurações, clientes, providers ou lógica de negócio nesta fase.

- [ ] **Step 6: Reinstalar em modo editável e verificar o teste**

Run:

```powershell
python -m pip install -e ".[dev]"
python -m pytest tests/test_package.py -v
```

Expected:

```text
tests/test_package.py::test_package_is_importable PASSED
```

- [ ] **Step 7: Verificar os gates locais completos**

Run:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import ai_service_desk; print(ai_service_desk.__name__)"
```

Expected:

```text
All checks passed!
... files already formatted
1 passed
ai_service_desk
```

A mensagem exata de Ruff pode variar por versão, mas todos os comandos devem terminar com exit code 0.

- [ ] **Step 8: Commitar o bootstrap Python**

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
- Consumes: `pyproject.toml` e extra `.[dev]` criados na Task 1.
- Produces: job `quality` em `ubuntu-latest`, executado automaticamente em `pull_request`, com Python 3.14 e os três gates locais.

- [ ] **Step 1: Criar `.github/workflows/ci.yml`**

Conteúdo exato:

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
          cache: pip

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

Não adicionar Ollama, modelos, secrets, services, matrix de versões ou jobs Windows neste workflow.

- [ ] **Step 2: Verificar que o smoke local existente não foi modificado**

Run:

```bash
git diff main -- .github/workflows/local-ai-smoke.yml
```

Expected: saída vazia.

Se houver qualquer diff, restaurar o arquivo para a versão de `main` antes de continuar.

- [ ] **Step 3: Fazer validações locais do workflow e do projeto**

Run:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected: todos os comandos com exit code 0.

O teste definitivo de `.github/workflows/ci.yml` ocorrerá somente quando o pull request for aberto, porque é o GitHub Actions que valida a execução real do YAML e das actions utilizadas.

- [ ] **Step 4: Commitar o CI hospedado**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add hosted python quality checks"
```

---

### Task 3: Regras do repositório e proteção contra artefatos locais

**Files:**
- Create: `.gitignore`
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: regras aprovadas na spec.
- Produces: política normativa legível por humanos e agentes; exclusões mínimas para ambiente Python, segredos locais e artefatos gerados.

- [ ] **Step 1: Criar `.gitignore`**

Conteúdo exato:

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
!.env.example

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

A exceção `!.env.example` apenas permite que um arquivo desse nome seja versionado no futuro se uma fase realmente precisar dele. Não criar `.env.example` na Fase 0.

- [ ] **Step 2: Criar `AGENTS.md` curto e normativo**

Conteúdo exato:

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

- [ ] **Step 3: Verificar que arquivos locais e segredos comuns estão ignorados**

Run:

```bash
git check-ignore -v .venv .env artifacts/test.bin embeddings/index.npy logs/app.log reports/output.json
```

Expected: cada caminho deve aparecer associado a uma regra de `.gitignore`.

- [ ] **Step 4: Verificar que `.env.example` não está bloqueado pela regra de `.env.*`**

Run:

```bash
git check-ignore .env.example
```

Expected: nenhum output e exit code 1, indicando que `.env.example` seria versionável se futuramente criado.

- [ ] **Step 5: Verificar qualidade do repositório após os arquivos normativos**

Run:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected: todos os comandos com exit code 0.

- [ ] **Step 6: Commitar governança e ignore**

```bash
git add .gitignore AGENTS.md
git commit -m "docs: add repository working rules"
```

---

### Task 4: README, ambiente local e roadmap

**Files:**
- Create: `README.md`
- Create: `docs/environment/local-demo.md`
- Create: `docs/roadmap.md`

**Interfaces:**
- Consumes: comandos e política definidos nas Tasks 1 a 3 e fatos do ambiente já validados pelo smoke test.
- Produces: ponto de entrada operacional do projeto, registro do ambiente de homologação e sequência macro das fases.

- [ ] **Step 1: Criar `README.md`**

Conteúdo exato:

```markdown
# AI Service Desk

> O objetivo não é automatizar o chamado. É descobrir se o chamado precisa existir.

O AI Service Desk é uma camada inteligente anterior à abertura de chamados de TI. O produto evoluirá para entender solicitações, tentar resolvê-las com conhecimento e ações controladas e escalar apenas quando a intervenção humana for necessária.

A Fase 0 contém somente a fundação técnica do repositório. O motor atual, o corpus TI e as capacidades de IA entram em fases posteriores.

## Requisitos

- Python 3.14
- Git

## Ambiente local

No PowerShell:

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
- Planos de implementação: `docs/superpowers/plans/`
- Ambiente local de homologação: `docs/environment/local-demo.md`
- Roadmap macro: `docs/roadmap.md`

## Homologação local com IA

O smoke test com Ollama roda separadamente em um runner Windows self-hosted e é disparado manualmente por GitHub Actions. Consulte `docs/environment/local-demo.md` antes de executá-lo.
```

- [ ] **Step 2: Criar `docs/environment/local-demo.md`**

Conteúdo exato:

```markdown
# Ambiente local de homologação

Este documento registra o ambiente real usado para desenvolvimento e demonstração local do AI Service Desk. Ele descreve a máquina de homologação atual e não define a arquitetura permanente do produto web.

## Máquina

- Sistema operacional: Windows 11 Pro
- Equipamento: notebook Dell
- Processador: Intel Core 7 250U
- Memória: 32 GB RAM
- GPU: Intel integrada
- Armazenamento: aproximadamente 477 GB

## Python

- Versão validada: Python 3.14.7
- Ambiente do projeto: `.venv`
- Gerenciamento de dependências: `pip`

## Ollama

- Versão validada: Ollama 0.33.3
- API local: `http://localhost:11434`
- Modelo de chat obrigatório: `qwen3.5:4b`
- Modelo de embeddings obrigatório: `qwen3-embedding:0.6b`
- Dimensão validada do embedding: 1024

Chamadas de chat da aplicação devem usar `think=false` quando a fase correspondente implementar o cliente Ollama. O smoke test já usa essa configuração para evitar o custo desnecessário de raciocínio prolongado no ambiente local.

## GitHub self-hosted runner

- Nome: `ai-service-desk-dell`
- Labels: `self-hosted`, `Windows`, `X64`, `ai-service-desk`, `ollama`
- Diretório: `C:\actions-runner`
- Modo atual: interativo na sessão `juparana-pgm\pedro.borges`
- Serviço Windows: `Stopped` e `Disabled`

O serviço foi deixado desabilitado porque a conta de serviço não enxergava o mesmo ambiente Python/Ollama e a máquina apresenta falha no secure channel do domínio. Reparar o domínio ou criar uma conta de serviço corporativa não faz parte do escopo atual.

Para disponibilizar o runner:

```powershell
cd C:\actions-runner
.\run.cmd
```

A janela deve permanecer aberta durante a execução da homologação. O estado esperado é `Listening for Jobs`.

## Workflow de homologação

Arquivo: `.github/workflows/local-ai-smoke.yml`

Trigger: `workflow_dispatch`

Runner:

```text
[self-hosted, Windows, X64, ai-service-desk, ollama]
```

O smoke test verifica:

1. identidade e PowerShell do runner;
2. disponibilidade do Python local;
3. resposta do Ollama em `/api/tags`;
4. presença de `qwen3.5:4b` e `qwen3-embedding:0.6b`;
5. resposta de chat não vazia com `think=false`;
6. embedding com dimensão 1024.

O PowerShell do workflow usa `-ExecutionPolicy Bypass` somente no processo do job para contornar a política que bloqueou scripts temporários do GitHub Actions. Isso não altera permanentemente a Execution Policy do Windows.

## Regra operacional para Actions

Não fazer polling do workflow. Depois de disparar ou identificar uma execução, o operador acompanha o GitHub Actions e retorna com `success` ou com o log da etapa que falhou.

## Limite arquitetural

Ollama local é uma implementação de provedor de modelo para desenvolvimento e demonstração. O produto web futuro não deve assumir que o notebook Dell ou o Ollama local serão componentes obrigatórios de produção.
```

- [ ] **Step 3: Criar `docs/roadmap.md`**

Conteúdo exato:

```markdown
# Roadmap macro

Este roadmap registra a direção atual do AI Service Desk. Ele não é um backlog detalhado e não congela o desenho das fases futuras. Cada fase deve receber sua própria especificação, critérios de saída e plano antes da implementação.

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

O projeto não avança de fase apenas porque a anterior parece funcional. A transição exige evidência compatível com os critérios mensuráveis definidos na especificação da fase em execução.
```

- [ ] **Step 4: Verificar links e caminhos documentados**

Run:

```powershell
python -c "from pathlib import Path; paths = ['README.md', 'AGENTS.md', 'docs/environment/local-demo.md', 'docs/roadmap.md', 'docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md', 'docs/superpowers/plans/2026-09-06-phase-0-repository-foundation.md']; missing = [p for p in paths if not Path(p).is_file()]; print('missing:', missing); raise SystemExit(bool(missing))"
```

Expected:

```text
missing: []
```

- [ ] **Step 5: Verificar qualidade completa novamente**

Run:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import ai_service_desk; print(ai_service_desk.__name__)"
```

Expected: todos os comandos com exit code 0 e último output `ai_service_desk`.

- [ ] **Step 6: Commitar documentação operacional**

```bash
git add README.md docs/environment/local-demo.md docs/roadmap.md
git commit -m "docs: document phase 0 foundation"
```

---

### Task 5: Revisão integral contra a spec antes do PR

**Files:**
- Review: todos os arquivos adicionados na branch `phase-0-foundation`
- Preserve: `.github/workflows/local-ai-smoke.yml`

**Interfaces:**
- Consumes: entregáveis das Tasks 1 a 4 e a spec aprovada.
- Produces: branch pronta para revisão remota, sem itens fora de escopo e com evidência local fresca.

- [ ] **Step 1: Confirmar a lista de mudanças em relação a `main`**

Run:

```bash
git status --short
git diff --stat main...HEAD
git diff --name-status main...HEAD
```

Expected: mudanças somente nos seguintes caminhos, além da spec e deste plano já commitados:

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

`.github/workflows/local-ai-smoke.yml` não deve aparecer como modificado.

- [ ] **Step 2: Verificar explicitamente ausência de escopo antecipado**

Run:

```powershell
python -c "from pathlib import Path; forbidden = ['web', 'data', 'Dockerfile', 'docker-compose.yml', '.env.example']; found = [p for p in forbidden if Path(p).exists()]; print('forbidden_found:', found); raise SystemExit(bool(found))"
```

Expected:

```text
forbidden_found: []
```

Também revisar `pyproject.toml` e confirmar que `dependencies = []` e que o extra `dev` contém apenas pytest e Ruff.

- [ ] **Step 3: Executar a verificação local final da Fase 0**

Run:

```powershell
python --version
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -c "import ai_service_desk; print(ai_service_desk.__name__)"
```

Expected:

```text
Python 3.14.x
ruff check: exit 0
ruff format --check: exit 0
pytest: 1 passed
ai_service_desk
```

Não usar resultados de execução anteriores como evidência para este gate. Estes comandos precisam ser executados novamente imediatamente antes do PR.

- [ ] **Step 4: Verificar whitespace e integridade do diff**

Run:

```bash
git diff --check main...HEAD
```

Expected: saída vazia e exit code 0.

- [ ] **Step 5: Fazer revisão linha a linha dos critérios da spec**

Confirmar todos os itens:

```text
[ ] estrutura do repositório corresponde ao desenho aprovado
[ ] Python 3.14 declarado em requires-python
[ ] pacote instalável com pip install -e .[dev]
[ ] import ai_service_desk funciona
[ ] pytest passa
[ ] ruff check . passa
[ ] ruff format --check . passa
[ ] CI hospedado existe e usa pull_request
[ ] smoke local permanece manual via workflow_dispatch
[ ] documentação Dell/Ollama existe
[ ] política de dados e segredos está no AGENTS/spec
[ ] roadmap macro existe
[ ] motor atual não foi migrado
[ ] corpus TI não foi adicionado
[ ] nenhuma dependência de IA está no pyproject.toml
[ ] branch será integrada apenas por PR
```

Qualquer item não confirmado bloqueia o PR até ser corrigido.

- [ ] **Step 6: Garantir working tree limpa**

Run:

```bash
git status --short
```

Expected: saída vazia.

Se houver mudanças legítimas de documentação ou configuração resultantes da revisão, commitá-las com uma mensagem específica antes de continuar. Não criar commit genérico de "fixes" sem descrever a correção.

---

### Task 6: Abrir o pull request e validar o CI hospedado

**Files:**
- No file changes expected.
- Remote artifact: pull request `phase-0-foundation` -> `main`.

**Interfaces:**
- Consumes: branch verificada localmente na Task 5.
- Produces: PR revisável e execução real do workflow `CI` no GitHub-hosted runner.

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
- `pyproject.toml` com `pytest` e `ruff`
- CI GitHub-hosted em pull requests
- preservação do smoke test manual com Ollama
- `README.md`, `AGENTS.md`, ambiente local e roadmap
- spec e plano da Fase 0

## Fora de escopo

- motor atual
- corpus TI
- retrieval/embeddings/LLM no pacote
- API, banco, frontend e Docker

## Verificação local

- `python -m ruff check .`
- `python -m ruff format --check .`
- `python -m pytest`
- `python -c "import ai_service_desk"`

Spec: `docs/superpowers/specs/2026-09-06-phase-0-repository-foundation-design.md`
```

Base: `main`

Head: `phase-0-foundation`

- [ ] **Step 2: Parar após o disparo do CI remoto**

Depois que o PR for aberto, não consultar repetidamente o status do workflow.

Informar ao operador:

```text
O PR foi aberto e o CI hospedado precisa concluir o job "Python quality". Monitore a execução no GitHub e retorne com "success" ou com o log da etapa que falhou.
```

Não executar polling.

- [ ] **Step 3: Quando o operador retornar, verificar o resultado uma única vez se houver identificador disponível**

Se o operador retornar `success`, registrar essa evidência humana e, se houver run/PR identificável disponível no contexto, fazer no máximo uma leitura pontual do resultado concluído. Isso não é polling.

Se houver falha, usar o log retornado para diagnosticar a causa antes de alterar arquivos.

- [ ] **Step 4: Revisar o PR antes do merge**

Confirmar:

```text
[ ] CI "Python quality" concluído com success
[ ] diff do PR corresponde à Fase 0
[ ] nenhum segredo ou dado corporativo bruto foi adicionado
[ ] local-ai-smoke.yml não foi alterado sem necessidade
[ ] critérios da spec continuam atendidos
```

Somente após essas evidências a Fase 0 pode ser considerada pronta para merge.

- [ ] **Step 5: Merge somente após aprovação explícita do PR**

Não mover `main` diretamente e não fazer force push. Usar o fluxo normal de merge do pull request depois da revisão.

A conclusão da Fase 0 exige que o PR esteja integrado em `main` e que a verificação pós-merge necessária seja compatível com os critérios da spec.

---

## Final Verification Checklist

Antes de declarar a Fase 0 concluída, obter evidência fresca para todos os itens abaixo:

```text
[ ] Python reporta 3.14.x
[ ] pip install -e .[dev] conclui com sucesso
[ ] ruff check . retorna exit 0
[ ] ruff format --check . retorna exit 0
[ ] pytest retorna 1 passed e 0 failed
[ ] import ai_service_desk funciona
[ ] CI hospedado do PR retorna success
[ ] local-ai-smoke.yml continua manual e sem mudança funcional
[ ] README, AGENTS, local-demo e roadmap existem
[ ] spec e plano estão versionados
[ ] nenhum motor, corpus TI ou dependência de IA entrou na Fase 0
[ ] PR foi revisado antes do merge
```

O smoke test local com Ollama já é uma evidência separada do ambiente de homologação. Não é necessário dispará-lo para cada PR da Fase 0, porque o conteúdo do workflow deve ser preservado e o CI determinístico não depende de Ollama.
