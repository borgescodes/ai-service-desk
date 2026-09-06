# Fase 1 Current Engine Reproducible Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar o motor local 2.1 para o pacote oficial `ai_service_desk`, preservando classificação conservadora, segurança de rede e dados, indexação reproduzível, retrieval com contexto e abstinência, sem usar o corpus corporativo real.

**Architecture:** O motor será incorporado em módulos focados sob `src/ai_service_desk/engine/`, com CLI oficial em `python -m ai_service_desk`. O CI hospedado continuará determinístico e sem Ollama real. A homologação ponta a ponta ocorrerá em workflow manual separado no runner Windows Dell, usando somente corpus sintético e os modelos locais aprovados.

**Tech Stack:** Python 3.14, setuptools, pip, NumPy, pandas, Requests, pytest, Ruff, GitHub Actions, PowerShell e Ollama local.

**Spec:** `docs/superpowers/specs/2026-09-06-phase-1-current-engine-reproducible-design.md`

## Global Constraints

- Python oficial: `>=3.14,<3.15`.
- Runtime dependencies permitidas nesta fase: `numpy>=2.0,<3`, `pandas>=2.2,<4`, `requests>=2.32,<3`.
- Development dependencies continuam apenas com pytest e Ruff.
- Não adicionar FastAPI, Pydantic, LangChain, LlamaIndex, ChromaDB, FAISS, SQLAlchemy, SDK de provedor externo ou framework de agentes.
- Código de produção deve existir somente no pacote `src/ai_service_desk/`. Não copiar `motor-local` como segunda aplicação.
- Não depender do ZIP legado, de `classificar_ticket`, `busca_core`, `app.*` ou caminhos externos ao repositório.
- Não versionar corpus corporativo real, exports TiFlux brutos, embeddings corporativos, índices corporativos, logs, relatórios gerados ou segredos.
- Fixtures e smoke tests usam exclusivamente dados sintéticos.
- Modelo de classificação: `qwen3.5:4b`.
- Modelo de embeddings: `qwen3-embedding:0.6b`.
- Dimensão esperada dos embeddings: `1024`.
- Receita de índice: `texto_busca-plain-v1`.
- Threshold legado padrão: `0.65`. Não calibrar nesta fase.
- `top_k` padrão: `5`. `min_matches` padrão: `3`.
- Candidatos são sempre `HISTORICO_NAO_VALIDADO`. Nunca chamar candidato de solução aprovada.
- Ollama aceita somente HTTP em loopback: `localhost`, `127.0.0.1` ou `::1`.
- Requests para Ollama usam `trust_env=False` e `allow_redirects=False`.
- `.github/workflows/local-ai-smoke.yml` permanece separado e sem mudança funcional não necessária.
- CI hospedado não chama Ollama real.
- Não fazer polling de GitHub Actions. O operador acompanha execuções remotas e retorna com `success` ou com o log da etapa que falhou.
- Toda implementação de comportamento usa TDD: teste falhando, implementação mínima, teste passando.
- Antes de afirmar conclusão, executar verificação fresca dos gates aplicáveis.

## Topologia de branches e workflows

Existe uma limitação operacional do GitHub Actions que precisa ser tratada explicitamente: `workflow_dispatch` só recebe eventos quando o arquivo do workflow existe no branch padrão. Portanto, a Fase 1 usa dois pull requests revisados:

1. PR de design/bootstrap: branch `phase-1-engine`, contendo spec, este plano e `.github/workflows/engine-smoke.yml`. Esse PR coloca o workflow manual no `main` antes da homologação da implementação.
2. PR de implementação: branch `phase-1-engine-implementation`, criada a partir do `main` já contendo o workflow. O `engine-smoke.yml` recebe `target_ref` e faz checkout dessa branch para validar o código antes do merge.

Essa divisão não altera o escopo funcional. Ela torna executável o critério já aprovado de que `engine-smoke.yml` deve passar antes do merge da implementação.

## File Map

**Criar no PR de design/bootstrap:**

- `.github/workflows/engine-smoke.yml`: homologação manual do motor contra um `target_ref` explícito.

**Criar no PR de implementação:**

- `src/ai_service_desk/engine/__init__.py`: exports mínimos do motor.
- `src/ai_service_desk/engine/types.py`: `TicketClassification`.
- `src/ai_service_desk/engine/validation.py`: normalização de texto e vetores.
- `src/ai_service_desk/engine/classification.py`: contrato de classificação e grounding literal.
- `src/ai_service_desk/engine/data.py`: carga, sanitização e preparação TiFlux.
- `src/ai_service_desk/engine/ollama.py`: cliente loopback e embedder local.
- `src/ai_service_desk/engine/index.py`: índice NumPy, manifesto, checkpoint e importação legado.
- `src/ai_service_desk/engine/retrieval.py`: pool por contexto, threshold, abstinência e `RetrievalEngine`.
- `src/ai_service_desk/engine/smoke.py`: validação funcional real no Dell.
- `src/ai_service_desk/cli.py`: parser e orquestração dos comandos oficiais.
- `src/ai_service_desk/__main__.py`: entrada `python -m ai_service_desk`.
- `tests/engine/test_validation.py`.
- `tests/engine/test_classification.py`.
- `tests/engine/test_data.py`.
- `tests/engine/test_ollama.py`.
- `tests/engine/test_index.py`.
- `tests/engine/test_retrieval.py`.
- `tests/engine/test_smoke.py`.
- `tests/test_cli.py`.
- `tests/fixtures/engine_smoke_corpus.csv`: corpus sintético para homologação.
- `docs/migration/engine-v2.1-equivalence.md`: destino dos 75 testes legados.

**Modificar no PR de implementação:**

- `pyproject.toml`: adicionar as três dependências de runtime.
- `README.md`: documentar CLI e separação entre CI e homologação real.

**Preservar:**

- `.github/workflows/ci.yml`: continua determinístico em PR.
- `.github/workflows/local-ai-smoke.yml`: continua responsável somente por infraestrutura Ollama.
- specs e planos da Fase 0.
- spec e plano da Fase 1.

---

### Task 1: Bootstrap do workflow manual da Fase 1

**Files:**
- Create: `.github/workflows/engine-smoke.yml`
- Preserve: `.github/workflows/local-ai-smoke.yml`

**Interfaces:**
- Consumes: input manual `target_ref`, runner `[self-hosted, Windows, X64, ai-service-desk, ollama]` e Python/Ollama existentes no Dell.
- Produces: workflow `Engine smoke` capaz de fazer checkout de uma branch ou SHA de implementação e executar `python -m ai_service_desk validate`.

- [ ] **Step 1: Criar o workflow manual na branch `phase-1-engine`**

```yaml
name: Engine smoke

on:
  workflow_dispatch:
    inputs:
      target_ref:
        description: Branch or SHA to validate
        required: true
        type: string

permissions:
  contents: read

jobs:
  engine-smoke:
    name: Windows engine smoke
    runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
    timeout-minutes: 15

    steps:
      - name: Checkout target ref
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.target_ref }}

      - name: Verify Python 3.14
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $version = python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
          Write-Host "Python: $version"
          if (-not $version.StartsWith("3.14.")) {
            throw "Engine smoke requires Python 3.14.x. Found $version"
          }

      - name: Install project
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Validate official engine
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          $index = Join-Path $env:RUNNER_TEMP "ai-service-desk-engine-$env:GITHUB_RUN_ID"
          $report = Join-Path $env:RUNNER_TEMP "ai-service-desk-engine-$env:GITHUB_RUN_ID.json"
          python -m ai_service_desk validate `
            --file tests/fixtures/engine_smoke_corpus.csv `
            --index $index `
            --report $report `
            --url http://127.0.0.1:11434
          Get-Content $report
```

O workflow não deve incluir trigger `push` ou `pull_request`. Ele não deve alterar nem chamar `local-ai-smoke.yml`.

- [ ] **Step 2: Validar estruturalmente o arquivo e a preservação do smoke de infraestrutura**

```powershell
python -c "from pathlib import Path; text = Path('.github/workflows/engine-smoke.yml').read_text(encoding='utf-8'); required = ['workflow_dispatch:', 'target_ref:', 'Windows engine smoke', 'python -m ai_service_desk validate', 'tests/fixtures/engine_smoke_corpus.csv']; missing = [item for item in required if item not in text]; print('missing:', missing); raise SystemExit(bool(missing))"
git diff main -- .github/workflows/local-ai-smoke.yml
git diff --check
```

Expected: `missing: []`, nenhum diff em `local-ai-smoke.yml` e `git diff --check` sem saída.

- [ ] **Step 3: Commitar o workflow no PR de design/bootstrap**

```bash
git add .github/workflows/engine-smoke.yml docs/superpowers/specs/2026-09-06-phase-1-current-engine-reproducible-design.md docs/superpowers/plans/2026-09-06-phase-1-current-engine-reproducible.md
git commit -m "ci: bootstrap phase 1 engine smoke"
```

Se spec e plano já estiverem commitados, `git add` adicionará somente o workflow.

- [ ] **Step 4: Abrir o PR de design/bootstrap**

Título:

```text
docs: define phase 1 engine migration
```

Body:

```markdown
## Objetivo

Versiona a spec e o plano aprovados da Fase 1 e instala o workflow manual `engine-smoke.yml` no branch padrão para permitir homologar a futura branch de implementação antes do merge.

## Incluído

- spec da Fase 1
- plano de implementação
- workflow manual `Engine smoke` com input `target_ref`

## Fora de escopo

- código do motor
- corpus corporativo
- embeddings ou índice corporativo
- mudanças funcionais em `local-ai-smoke.yml`

## Verificação

- CI determinístico do PR
- revisão do diff
- `local-ai-smoke.yml` preservado
```

Base: `main`. Head: `phase-1-engine`.

- [ ] **Step 5: Parar após o CI ser disparado**

Informar ao operador:

```text
O PR de design/bootstrap está aberto. Monitore o job "Python quality" e retorne com "success" ou com o log da etapa que falhou. Não há polling automático.
```

- [ ] **Step 6: Após retorno `success`, revisar e integrar o PR**

Confirmar em uma leitura pontual:

```text
[ ] CI = success
[ ] somente spec, plano e engine-smoke.yml estão no diff
[ ] local-ai-smoke.yml sem mudança funcional
[ ] workflow é somente workflow_dispatch
```

Fazer merge normal por pull request. Não usar force push.

- [ ] **Step 7: Criar a branch de implementação a partir do `main` atualizado**

```bash
git checkout main
git pull --ff-only
git checkout -b phase-1-engine-implementation
```

Expected: `engine-smoke.yml`, spec e plano já existem no branch novo.

---

### Task 2: Dependências, tipos e validação vetorial

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ai_service_desk/engine/__init__.py`
- Create: `src/ai_service_desk/engine/types.py`
- Create: `src/ai_service_desk/engine/validation.py`
- Create: `tests/engine/test_validation.py`

**Interfaces:**
- Consumes: Python 3.14, NumPy.
- Produces: `TicketClassification`, `normalize_text(value: str) -> str`, `normalize_matrix(matrix) -> np.ndarray`.

- [ ] **Step 1: Adicionar somente as dependências de runtime aprovadas**

Substituir `dependencies = []` em `pyproject.toml` por:

```toml
dependencies = [
    "numpy>=2.0,<3",
    "pandas>=2.2,<4",
    "requests>=2.32,<3",
]
```

Não alterar `requires-python`, pytest ou Ruff.

- [ ] **Step 2: Instalar o projeto na versão oficial de Python**

```powershell
python --version
python -m pip install -e ".[dev]"
```

Expected: Python 3.14.x e instalação com exit code 0. Se o ambiente não tiver Python 3.14, não flexibilizar `requires-python`; usar o CI remoto para o gate de instalação.

- [ ] **Step 3: Escrever os testes falhando para tipos e normalização**

`tests/engine/test_validation.py`:

```python
import numpy as np
import pytest

from ai_service_desk.engine.types import TicketClassification
from ai_service_desk.engine.validation import normalize_matrix, normalize_text


def test_ticket_classification_preserves_contract() -> None:
    classification = TicketClassification("ERRO_SISTEMA", "CIGAM", {"rotina": "001024"}, 0.9)
    assert classification.intent == "ERRO_SISTEMA"
    assert classification.system == "CIGAM"
    assert classification.entities == {"rotina": "001024"}
    assert classification.confidence == 0.9


def test_normalize_text_removes_accents_and_collapses_separators() -> None:
    assert normalize_text("  Conexão CIGAM_11  ") == "conexao cigam 11"


def test_normalize_matrix_returns_float32_unit_vectors() -> None:
    matrix = normalize_matrix([[3.0, 4.0], [0.0, 2.0]])
    assert matrix.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(matrix, axis=1), [1.0, 1.0])


@pytest.mark.parametrize("matrix", [[1.0, 2.0], [[0.0, 0.0]], [[np.nan, 1.0]], [[np.inf, 1.0]]])
def test_normalize_matrix_rejects_invalid_vectors(matrix: object) -> None:
    with pytest.raises(ValueError):
        normalize_matrix(matrix)
```

- [ ] **Step 4: Rodar os testes e confirmar RED**

```powershell
python -m pytest tests/engine/test_validation.py -v
```

Expected: collection/import failure porque `ai_service_desk.engine` ainda não existe.

- [ ] **Step 5: Criar a implementação mínima**

`src/ai_service_desk/engine/types.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class TicketClassification:
    intent: str
    system: str
    entities: dict[str, str]
    confidence: float
```

`src/ai_service_desk/engine/validation.py`:

```python
import re
import unicodedata
import numpy as np


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_matrix(matrix: object) -> np.ndarray:
    value = np.asarray(matrix, dtype=np.float32)
    if value.ndim != 2 or value.shape[0] == 0 or value.shape[1] == 0:
        raise ValueError("Matrix must have rows and columns.")
    if not np.isfinite(value).all():
        raise ValueError("Embedding contains non-finite values.")
    norms = np.linalg.norm(value, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms <= 0):
        raise ValueError("Embedding contains a zero norm vector.")
    return value / norms
```

`src/ai_service_desk/engine/__init__.py`:

```python
"""Core engine for the AI Service Desk."""
from ai_service_desk.engine.types import TicketClassification
__all__ = ["TicketClassification"]
```

- [ ] **Step 6: Confirmar GREEN e gates**

```powershell
python -m pytest tests/engine/test_validation.py -v
python -m ruff check src/ai_service_desk/engine tests/engine/test_validation.py
python -m ruff format --check src/ai_service_desk/engine tests/engine/test_validation.py
```

- [ ] **Step 7: Commitar**

```bash
git add pyproject.toml src/ai_service_desk/engine tests/engine/test_validation.py
git commit -m "feat: add engine core validation"
```

---

### Task 3: Classificação conservadora e grounding literal

**Files:**
- Create: `src/ai_service_desk/engine/classification.py`
- Create: `tests/engine/test_classification.py`

**Interfaces:**
- Consumes: `TicketClassification`, `normalize_text`, callable `chat(payload: dict) -> dict`.
- Produces: `build_payload`, `validate_classification`, `explicit_systems`, `preserve_evidence`, `classify_ticket`.

- [ ] **Step 1: Escrever os testes falhando de contrato e regressão**

Cobrir diretamente no novo arquivo: payload com `think=false`, `stream=false`, temperatura zero e schema fechado; CIGAM e SIAGRI explícitos; sistema desconhecido literal; sistema inventado removido; múltiplos sistemas ambíguos; rotina e filial somente literais; `supercigam` não casa com `CIGAM`; input vazio e maior que 3000; `system=None`; entidade não string; `confidence=True`, NaN, infinito e fora de `[0,1]`; `done_reason=length`.

Exemplo obrigatório:

```python
def test_explicit_cigam_overrides_invented_model_system_and_routine() -> None:
    response = {
        "message": {
            "content": '{"intent":"LIBERACAO_ROTINA","system":"SAP","entities":{"rotina":"123"},"confidence":0.85}'
        }
    }
    result = classify_ticket("preciso liberar a rotina 001024 no CIGAM", lambda payload: response)
    assert result.system == "CIGAM"
    assert result.entities["rotina"] == "001024"
```

- [ ] **Step 2: Rodar RED**

```powershell
python -m pytest tests/engine/test_classification.py -v
```

- [ ] **Step 3: Implementar constantes e contrato**

Usar exatamente os 8 intents aprovados e os aliases canônicos `CIGAM`, `SIAGRI`, `OUTLOOK`, `TEAMS`, `OFFICE 365`, `WHATSAPP`, `WINDOWS`. `build_payload` deve rejeitar input inválido antes de chamar HTTP e retornar `model=qwen3.5:4b`, `think=False`, `stream=False`, `temperature=0`, `num_ctx=4096`, `num_predict=384` e JSON schema com `additionalProperties=False`.

`validate_classification` deve exigir exatamente as chaves `intent`, `system`, `entities`, `confidence`, limitar `system` a 120 caracteres, `entities` a 12 pares string/string e cada valor a 500 caracteres, e rejeitar bool/NaN/infinito em `confidence`.

- [ ] **Step 4: Implementar grounding literal e `classify_ticket`**

A recuperação de sistema deve seguir esta ordem:

```python
names = explicit_systems(text)
if len(names) == 1:
    return names[0]
if len(names) > 1:
    return ""
match = re.search(r"\bsistema\s+([a-z][a-z0-9_.-]{1,40})\b", normalize_text(text))
if match and match.group(1) not in common_words | generic_system_words:
    return match.group(1).upper()
if normalize_text(model_system) not in generic_system_words and contains_name(text, model_system):
    return model_system.strip()
return ""
```

`preserve_evidence` remove qualquer `rotina`, `routine`, `filial` ou `branch` inventada pelo modelo e reinsere somente regex literal do texto. `classify_ticket(text, chat)` chama `chat(build_payload(text))`, valida `message.content`, rejeita `done_reason=length`, faz `json.loads`, valida o objeto e aplica `preserve_evidence`.

- [ ] **Step 5: Confirmar GREEN e gates**

```powershell
python -m pytest tests/engine/test_classification.py tests/engine/test_validation.py -v
python -m ruff check src/ai_service_desk/engine/classification.py tests/engine/test_classification.py
python -m ruff format --check src/ai_service_desk/engine/classification.py tests/engine/test_classification.py
```

- [ ] **Step 6: Commitar**

```bash
git add src/ai_service_desk/engine/classification.py tests/engine/test_classification.py
git commit -m "feat: migrate conservative ticket classification"
```

---

### Task 4: Carga, sanitização e preparação de dados

**Files:**
- Create: `src/ai_service_desk/engine/data.py`
- Create: `tests/engine/test_data.py`

**Interfaces:**
- Consumes: pandas, `normalize_text`.
- Produces: `clean_text`, `sensitive`, `sanitize`, `load_corpus`, `prepare_tiflux`.

- [ ] **Step 1: Escrever RED para dados sintéticos**

Criar arquivos somente em `tmp_path`. Cobrir IDs preservados como texto, colunas obrigatórias, duplicados, corpus vazio, HTML/script/control chars, mascaramento de URL/email/IP/CPF/telefone, filtro sensível, tickets abertos/cancelados, escopo TI, apontamentos órfãos, ordenação por data, mensagens genéricas, `texto_busca` limitado a 6000 e `HISTORICO_NAO_VALIDADO`.

- [ ] **Step 2: Rodar RED**

```powershell
python -m pytest tests/engine/test_data.py -v
```

- [ ] **Step 3: Implementar limpeza e carga**

Usar `REQUIRED_COLUMNS={ticket_id,ticket_number,title,texto_busca}`, os 10 termos TI da implementação 2.1 e regex sensível `senha|password|passwd|credencia\w*|token|secret|api[ _-]?key`. `sanitize` deve substituir URLs, emails, IPv4, CPF, telefone e nomes conhecidos pelos marcadores `[URL]`, `[EMAIL]`, `[IP]`, `[CPF]`, `[TELEFONE]`, `[PESSOA]`.

`load_corpus` lê `;`, `utf-8-sig`, `dtype=str`, `keep_default_na=False`, rejeita corpus vazio, IDs vazios/duplicados e `texto_busca` vazio, cria colunas opcionais ausentes e força `status_conhecimento=HISTORICO_NAO_VALIDADO`.

- [ ] **Step 4: Implementar `prepare_tiflux`**

A função lê os dois exports com tabulação, valida IDs, calcula `apontamentos_orfaos`, mantém somente ticket fechado não cancelado, aplica escopo TI quando solicitado, elimina todo ticket que tenha apontamento sensível, ordena apontamentos por `created_at`, `date` ou `beginning`, remove mensagens genéricas e pesquisa de satisfação, sanitiza título/descrição/histórico, limita `texto_busca` a 6000 e produz relatório com as contagens da spec.

Teste representativo:

```python
assert data["ticket_id"].tolist() == ["1"]
assert data.loc[0, "historico_atendimento"] == "Primeiro apontamento\nSegundo apontamento"
assert report["apontamentos_orfaos"] == 1
assert report["excluidos_abertos_ou_cancelados"] == 1
```

- [ ] **Step 5: Confirmar GREEN e gates**

```powershell
python -m pytest tests/engine/test_data.py -v
python -m ruff check src/ai_service_desk/engine/data.py tests/engine/test_data.py
python -m ruff format --check src/ai_service_desk/engine/data.py tests/engine/test_data.py
```

- [ ] **Step 6: Commitar**

```bash
git add src/ai_service_desk/engine/data.py tests/engine/test_data.py
git commit -m "feat: migrate local data preparation"
```

---

### Task 5: Cliente Ollama somente loopback e embedder local

**Files:**
- Create: `src/ai_service_desk/engine/ollama.py`
- Create: `tests/engine/test_ollama.py`

**Interfaces:**
- Produces: `OllamaError`, `OllamaClient`, `LocalEmbedder`.
- `OllamaClient.chat(payload: dict) -> dict` é usado pela classificação.
- `LocalEmbedder.embed(texts: list[str]) -> np.ndarray` retorna matriz normalizada.

- [ ] **Step 1: Criar HTTP server controlado no teste e RED**

Usar `ThreadingHTTPServer(('127.0.0.1', 0), Handler)`. O handler deve implementar `/api/tags`, `/api/version`, `/api/show`, `/api/chat`, `/api/embed`, uma rota 302 e uma rota de JSON inválido. Testar host remoto recusado, `trust_env=False`, modelo ausente, modelo cloud, UTF-8 na classificação, batch de embeddings, `truncate=False`, vetor zero, redirect e JSON malformado.

- [ ] **Step 2: Rodar RED**

```powershell
python -m pytest tests/engine/test_ollama.py -v
```

- [ ] **Step 3: Implementar `OllamaClient`**

Validar URL com `urlparse`: scheme `http`, hostname em `127.0.0.1|localhost|::1`, sem user/password/query/fragment e path somente vazio ou `/`. Timeout entre 1 e 1800. Criar `requests.Session()` e definir `trust_env=False`. `_request` aceita somente path iniciado por `/api/`, usa timeout `(5, read_timeout)` e `allow_redirects=False`, converte timeout/conexão/request error em `OllamaError`, recusa 3xx e qualquer HTTP fora de 2xx.

`model_info` consulta `/api/tags` e `/api/show`, recusa nomes `:cloud` ou `-cloud`, `remote_host`, `remote_model`, modelo ausente e digest vazio. Nenhum fluxo baixa modelo.

- [ ] **Step 4: Implementar `LocalEmbedder`**

Padrões: model `qwen3-embedding:0.6b`, dimensions `1024`, digest vindo de `model_info`. `embed` exige lista não vazia de strings não vazias e chama `/api/embed` com `truncate=False`, `keep_alive=30m`, `num_ctx=4096`. Normalizar com `normalize_matrix` e exigir shape `(len(texts), dimensions)`.

- [ ] **Step 5: Confirmar GREEN e gates**

```powershell
python -m pytest tests/engine/test_ollama.py tests/engine/test_classification.py -v
python -m ruff check src/ai_service_desk/engine/ollama.py tests/engine/test_ollama.py
python -m ruff format --check src/ai_service_desk/engine/ollama.py tests/engine/test_ollama.py
```

- [ ] **Step 6: Commitar**

```bash
git add src/ai_service_desk/engine/ollama.py tests/engine/test_ollama.py
git commit -m "feat: add loopback ollama client"
```

---

### Task 6: Índice NumPy com proveniência, checkpoint e importação legado

**Files:**
- Create: `src/ai_service_desk/engine/index.py`
- Create: `tests/engine/test_index.py`

**Interfaces:**
- Consumes: `load_corpus`, `normalize_matrix`, embedder com `model`, `digest`, `dimensions`, `embed`.
- Produces: `RECIPE`, `atomic_json`, `build_index`, `load_index`, `import_legacy`.

- [ ] **Step 1: Escrever RED com `FakeEmbedder` determinístico**

Cobrir: build/load alinhado, `recipe=texto_busca-plain-v1`, metadata `rows/dimensions/model/model_digest/complete`, índice completo não reembeda, corpus alterado não reutiliza, lote 1..100, matriz corrompida, índice incompleto, batch shape errado, checkpoint não repete lote confirmado, digest incompatível no uso e import legado aceito/rejeitado por três sentinelas.

Teste de retomada obrigatório:

```python
class FailingSecondBatchEmbedder(FakeEmbedder):
    def embed(self, texts: list[str]) -> np.ndarray:
        if self.calls and not self.failed:
            self.failed = True
            self.calls.append(list(texts))
            raise RuntimeError("synthetic interruption")
        return super().embed(texts)


def test_resume_does_not_repeat_committed_batch(tmp_path: Path) -> None:
    embedder = FailingSecondBatchEmbedder()
    with pytest.raises(RuntimeError):
        build_index(corpus(), tmp_path / "index", embedder, batch_size=2)
    build_index(corpus(), tmp_path / "index", embedder, batch_size=2)
    assert embedder.calls.count(["texto a", "texto b"]) == 1
```

- [ ] **Step 2: Rodar RED**

```powershell
python -m pytest tests/engine/test_index.py -v
```

- [ ] **Step 3: Implementar persistência atômica e manifesto**

`RECIPE="texto_busca-plain-v1"`. `atomic_json` usa `mkstemp`, `json.dump(... allow_nan=False)`, `flush`, `fsync`, `os.replace`. `file_hash` usa SHA-256 em blocos. `corpus_bytes` serializa registros `fillna('')` em JSONL com chaves ordenadas. `index_lock` usa `O_CREAT|O_EXCL` e sempre remove `index.lock` no finally.

Manifesto inicial:

```python
state = {
    "version": 1,
    "source_hash": source_hash,
    "rows": len(data),
    "dimensions": embedder.dimensions,
    "model": embedder.model,
    "model_digest": embedder.digest,
    "recipe": RECIPE,
    "completed": 0,
    "complete": False,
    "batches": [],
    "legacy_import": False,
}
```

- [ ] **Step 4: Implementar build e resume**

Antes de cada retomada, comparar `source_hash`, `rows`, `dimensions`, `model`, `model_digest`, `recipe`, hash de `documents.jsonl`, shape da matriz parcial e SHA-256 de cada batch confirmado. Em cada batch: gerar embedding, normalizar, validar shape/norma, escrever matriz, `flush`, anexar `{start,end,sha256}`, atualizar `completed`, gravar manifesto atômico. Somente após todos os batches: gravar `matrix_hash`, então `complete=True` e persistir novamente.

- [ ] **Step 5: Implementar load e import legado**

`load_index` rejeita manifesto ausente, version diferente de 1, incompleto, receita incompatível, hash de documentos/matriz divergente, vetores não normalizados e desalinhamento de linhas.

`import_legacy` exige destino novo, lê `amostra_indexada.csv` e `embeddings.npy`, normaliza a matriz, recalcula posições `{0, len//2, len-1}`, exige similaridade de cada sentinela `>=0.999`, grava cópias novas e manifesto com `legacy_import=True`, `sentinel_rows` e `provenance_note` declarando que três sentinelas não provam todos os vetores.

- [ ] **Step 6: Confirmar GREEN e gates**

```powershell
python -m pytest tests/engine/test_index.py -v
python -m ruff check src/ai_service_desk/engine/index.py tests/engine/test_index.py
python -m ruff format --check src/ai_service_desk/engine/index.py tests/engine/test_index.py
```

- [ ] **Step 7: Commitar**

```bash
git add src/ai_service_desk/engine/index.py tests/engine/test_index.py
git commit -m "feat: migrate reproducible numpy index"
```

---

### Task 7: Retrieval com contexto, segurança e abstinência

**Files:**
- Create: `src/ai_service_desk/engine/retrieval.py`
- Create: `tests/engine/test_retrieval.py`

**Interfaces:**
- Produces: `select_context_pool`, `filter_by_threshold`, `retrieve`, `format_result`, `RetrievalEngine`.

- [ ] **Step 1: Escrever RED do núcleo com corpus sintético em memória**

Usar 3 documentos CIGAM e 1 Outlook, matriz normalizada conhecida e query `[1,0]`. Testar: candidato de outro sistema excluído mesmo com score maior; threshold 0.9 retorna `SEM_EVIDENCIA` e `[]`; sistema XYZ retorna `SEM_CONTEXTO`; contexto CIGAM escasso ainda bloqueia Outlook; CIGAM+SIAGRI retorna `CONTEXTO_AMBIGUO`; dimensão incompatível falha; histórico não altera ranking; formatter contém `HISTORICO_NAO_VALIDADO` e não imprime histórico por padrão; conteúdo com termo sensível não vira candidato.

- [ ] **Step 2: Rodar RED**

```powershell
python -m pytest tests/engine/test_retrieval.py -v
```

- [ ] **Step 3: Implementar pool e threshold**

Migrar os `INTENT_TERMS` legados para impressão, rede, liberação de rotina e acesso. `select_context_pool` começa na base geral, restringe por sistema ou intent somente quando houver pelo menos `min_matches=3`. `filter_by_threshold` mantém score `>=threshold`, ordena descrescente e limita a `top_k`.

- [ ] **Step 4: Implementar `retrieve` com barreira de sistema**

Validar threshold finito `[-1,1]`, `top_k` inteiro 1..20, shapes e finitude. Normalizar query, calcular dot product. Inicializar resultado com `status=SEM_EVIDENCIA`, `classification=asdict`, threshold, `pool_size`, `total_documents`, `best_score`, `candidates`, `warnings`, `timings`.

Se `explicit_systems(text)` tiver mais de um, retornar imediatamente `CONTEXTO_AMBIGUO`. Se `classification.system` estiver preenchido, filtrar candidatos compatíveis pelos aliases em metadata, title e `texto_busca`. Se nenhum compatível existir em toda a base, retornar `SEM_CONTEXTO`. Nunca completar resultados com outro sistema. Depois remover registros cujo `texto_busca`, `title` ou `historico_atendimento` seja sensível. Aplicar threshold. Cada candidato deve ser sanitizado e conter `status_conhecimento=HISTORICO_NAO_VALIDADO`.

- [ ] **Step 5: Implementar formatter e `RetrievalEngine`**

O formatter não pode chamar score de probabilidade, não pode chamar candidato de solução aprovada e só imprime `historico_atendimento` quando `show_history=True`.

`RetrievalEngine.__init__` chama `load_index` e rejeita diferença de model, model_digest ou dimensions. `search` mede classificação, embedding, busca e total; usa `classify_ticket(text, client.chat)`, `embedder.embed([text])[0]` e `retrieve`.

- [ ] **Step 6: Confirmar GREEN e gates**

```powershell
python -m pytest tests/engine/test_retrieval.py -v
python -m pytest tests/engine -v
python -m ruff check src/ai_service_desk/engine/retrieval.py tests/engine/test_retrieval.py
python -m ruff format --check src/ai_service_desk/engine/retrieval.py tests/engine/test_retrieval.py
```

- [ ] **Step 7: Commitar**

```bash
git add src/ai_service_desk/engine/retrieval.py tests/engine/test_retrieval.py
git commit -m "feat: migrate contextual retrieval engine"
```

---

### Task 8: Validação funcional e corpus sintético de homologação

**Files:**
- Create: `src/ai_service_desk/engine/smoke.py`
- Create: `tests/engine/test_smoke.py`
- Create: `tests/fixtures/engine_smoke_corpus.csv`

**Interfaces:**
- Produces: `run_validation(corpus, index, report_path, base_url, legacy, threshold) -> dict`.

- [ ] **Step 1: Criar corpus sintético fixo**

Usar exatamente 8 linhas artificiais com IDs `SYN-001` a `SYN-008`, cobrindo CIGAM erro, CIGAM rotina 1024, impressora, rede, SIAGRI, Outlook, CIGAM acesso e um registro CIGAM bloqueado por palavra `senha`. As queries dos quatro casos de smoke devem ser idênticas ao `texto_busca` de suas linhas relevantes para tornar o self-match/retrieval determinístico.

- [ ] **Step 2: Escrever RED do relatório em falha de Ollama**

```python
class FailingClient:
    def __init__(self, base_url: str):
        raise RuntimeError("synthetic connection failure")


def test_validation_writes_report_when_ollama_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(smoke, "OllamaClient", FailingClient)
    report_path = tmp_path / "report.json"
    report = smoke.run_validation(
        Path("tests/fixtures/engine_smoke_corpus.csv"),
        tmp_path / "index",
        report_path,
    )
    assert report["ok"] is False
    assert "synthetic connection failure" in report["error"]
    assert report_path.is_file()
```

- [ ] **Step 3: Implementar `run_validation`**

O relatório registra schema version, timestamp UTC, Python, plataforma, NumPy, pandas, Requests, limitações, versão Ollama, modelos/digest, reutilização de índice, rows/shape, self-match e casos. Os quatro casos são: CIGAM erro, impressora, rotina 1024 CIGAM, sistema XYZ. O self-match precisa ser `>=0.99`. Para XYZ, `candidates=[]`. Para impressora, deve existir candidato. Para rotina, entity `rotina=1024`. O relatório é sempre gravado via `atomic_json` no `finally`, inclusive em erro ou Ctrl+C.

- [ ] **Step 4: Confirmar GREEN**

```powershell
python -m pytest tests/engine/test_smoke.py -v
python -m ruff check src/ai_service_desk/engine/smoke.py tests/engine/test_smoke.py
python -m ruff format --check src/ai_service_desk/engine/smoke.py tests/engine/test_smoke.py
```

- [ ] **Step 5: Commitar**

```bash
git add src/ai_service_desk/engine/smoke.py tests/engine/test_smoke.py tests/fixtures/engine_smoke_corpus.csv
git commit -m "test: add synthetic engine smoke validation"
```

---

### Task 9: CLI oficial em `python -m ai_service_desk`

**Files:**
- Create: `src/ai_service_desk/cli.py`
- Create: `src/ai_service_desk/__main__.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Produces comandos: `doctor`, `inspect`, `show-index`, `prepare`, `index`, `import-legacy`, `search`, `validate`.

- [ ] **Step 1: Escrever RED do CLI**

Testar: `--help` sem Ollama; `inspect --file tests/fixtures/engine_smoke_corpus.csv` mostra `Registros: 8` e não imprime histórico; `show-index` ausente retorna 1 sem traceback; `prepare` recusa sobrescrever output; `validate` encaminha todos os argumentos para `run_validation`; `--context-json` sem `--query` falha antes de salvar conversa.

- [ ] **Step 2: Criar parser**

Todos os nomes de comando ficam em inglês. `inspect` exige `--file`. `show-index` exige `--index`. `prepare` exige `--tickets --appointments --output` e aceita `--scope ti|todos`. `index` exige `--file --index`, aceita `--batch-size` e `--url`. `import-legacy` exige `--source --index`, aceita `--url`. `search` exige `--index`, aceita `--query --show-history --context-json --threshold --url`. `validate` exige `--file --index --report`, aceita `--legacy --threshold --url`. URL padrão sempre `http://127.0.0.1:11434` e threshold padrão `0.65`.

- [ ] **Step 3: Implementar `main` sem regra de negócio duplicada**

`inspect` chama `load_corpus` e imprime apenas contagem/colunas. `show-index` chama `load_index` e mostra somente rows, dimensions, model, model_digest, complete, recipe. `prepare` chama `prepare_tiflux`, recusa output existente, grava CSV e report JSON. `validate` chama `run_validation` e retorna 0/1 conforme `report['ok']`. Os demais comandos criam `OllamaClient`; `doctor` verifica versão e os dois modelos; `index` chama `build_index` com progresso; `import-legacy` chama `import_legacy`; `search` cria `RetrievalEngine`, suporta query única ou loop sem memória. Exceções operacionais conhecidas geram `ERRO: ...` em stderr e exit 1, sem traceback.

`src/ai_service_desk/__main__.py`:

```python
from ai_service_desk.cli import main
raise SystemExit(main())
```

- [ ] **Step 4: Confirmar GREEN offline**

```powershell
python -m pytest tests/test_cli.py -v
python -m ai_service_desk --help
python -m ai_service_desk inspect --file tests/fixtures/engine_smoke_corpus.csv
python -m ruff check src/ai_service_desk/cli.py src/ai_service_desk/__main__.py tests/test_cli.py
python -m ruff format --check src/ai_service_desk/cli.py src/ai_service_desk/__main__.py tests/test_cli.py
```

- [ ] **Step 5: Commitar**

```bash
git add src/ai_service_desk/cli.py src/ai_service_desk/__main__.py tests/test_cli.py
git commit -m "feat: add official engine cli"
```

---

### Task 10: Equivalência dos 75 testes e documentação operacional

**Files:**
- Create: `docs/migration/engine-v2.1-equivalence.md`
- Modify: `README.md`

**Interfaces:**
- Produces rastreabilidade de cada node id legado para `MIGRADO`, `SUBSTITUIDO_POR_TESTE_EQUIVALENTE`, `FORA_DE_ESCOPO` ou `OBSOLETO_COM_JUSTIFICATIVA`.

- [ ] **Step 1: Criar documento de equivalência**

O documento explica que 75 é baseline, não meta. Inserir tabela `Legacy node id | Status | New test or justification` com uma linha para cada node id coletado do motor 2.1. Nenhum node id pode ser agrupado ou omitido. Os node ids abrangem 8 testes de `test_busca_core.py`, 7 de `test_classificacao.py`, 4 de CLI, 18 contratos, 8 data, 18 HTTP/retrieval, 10 index e 1 integração, total 75.

- [ ] **Step 2: Verificar a contagem**

Criar lista temporária fora do Git com os 75 node ids congelados no baseline e executar script que confirme `len(ids)==75` e que cada string aparece exatamente uma vez no documento. O script deve falhar se houver ausente ou duplicado.

- [ ] **Step 3: Atualizar README**

Documentar:

```powershell
python -m ai_service_desk --help
python -m ai_service_desk inspect --file <arquivo.csv>
python -m ai_service_desk doctor
```

Explicar que `doctor` exige Ollama real, CI hospedado não usa Ollama, corpus real/exports/embeddings/índices continuam fora do Git e homologação completa usa `engine-smoke.yml` manual no Dell.

- [ ] **Step 4: Rodar gates**

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
git diff --check
```

- [ ] **Step 5: Commitar**

```bash
git add README.md docs/migration/engine-v2.1-equivalence.md
git commit -m "docs: record engine migration equivalence"
```

---

### Task 11: Verificação integral antes do PR de implementação

**Files:**
- Review: branch `phase-1-engine-implementation`
- Preserve: `.github/workflows/local-ai-smoke.yml`

- [ ] **Step 1: Conferir diff**

```bash
git status --short
git diff --stat main...HEAD
git diff --name-status main...HEAD
git diff main -- .github/workflows/local-ai-smoke.yml
```

Expected: working tree limpa e sem diff funcional em `local-ai-smoke.yml`.

- [ ] **Step 2: Confirmar dependências exatas**

```powershell
python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); assert d['project']['dependencies']==['numpy>=2.0,<3','pandas>=2.2,<4','requests>=2.32,<3']; print(d['project']['dependencies'])"
```

- [ ] **Step 3: Confirmar ausência de arquitetura paralela e imports legados**

```powershell
python -c "from pathlib import Path; forbidden=['motor-local','classificar_ticket.py','busca_core.py','requirements.txt','setup.ps1','run_tests.py','web','Dockerfile','docker-compose.yml']; found=[p for p in forbidden if Path(p).exists()]; print('forbidden_found:',found); raise SystemExit(bool(found))"
```

```bash
git grep -n -E '(^| )(from|import) (classificar_ticket|busca_core|app)(\.| |$)' -- src tests || true
```

- [ ] **Step 4: Rodar verificação determinística fresca**

```powershell
python --version
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m ai_service_desk --help
python -m ai_service_desk inspect --file tests/fixtures/engine_smoke_corpus.csv
```

Se o ambiente local não tiver Python 3.14, não alterar `requires-python`; o CI remoto comprova instalação oficial.

- [ ] **Step 5: `doctor` somente com Ollama real**

```powershell
python -m ai_service_desk doctor
```

Esse gate deve rodar no Dell ou no engine smoke. Não falsificar nem bypassar.

- [ ] **Step 6: Verificar whitespace e arquivos indevidos**

```bash
git diff --check main...HEAD
git diff --numstat main...HEAD
```

Não permitir `.npy`, `.zip`, TSV corporativo ou CSV que não seja a fixture sintética aprovada.

- [ ] **Step 7: Checklist da spec**

Confirmar um a um: pacote oficial único; grounding literal; ambiguidade segura; loopback/proxy/redirect; embeddings inválidos; manifesto/proveniência; checkpoint/resume; import por sentinelas; barreira de sistema; threshold 0.65; `SEM_EVIDENCIA`, `SEM_CONTEXTO`, `CONTEXTO_AMBIGUO`; `HISTORICO_NAO_VALIDADO`; dados sintéticos; 75 testes mapeados; CI sem Ollama; local smoke separado.

---

### Task 12: PR de implementação, CI e Engine smoke

**Files:**
- No file changes expected.
- Remote: PR `phase-1-engine-implementation` -> `main`.

- [ ] **Step 1: Abrir PR**

Título:

```text
feat: migrate reproducible local engine
```

Body deve resumir os módulos migrados, declarar fora de escopo corpus real, calibração, geração de solução, RAG/API/frontend, listar gates determinísticos e indicar que `Engine smoke` será executado com `target_ref=phase-1-engine-implementation` após CI verde.

- [ ] **Step 2: Parar após CI disparar**

Informar:

```text
O PR de implementação foi aberto. Monitore o job "Python quality" e retorne com "success" ou com o log da etapa que falhou. Não farei polling.
```

- [ ] **Step 3: Processar retorno do CI**

Com `success`, registrar a evidência e no máximo fazer uma leitura pontual do run concluído para confirmar SHA. Em falha, usar o log fornecido e aplicar systematic-debugging antes de alterar código.

- [ ] **Step 4: Disparar `Engine smoke`**

Executar manualmente o workflow já existente no `main` com:

```text
target_ref = phase-1-engine-implementation
```

Ele precisa provar Python 3.14, instalação editável, os dois modelos, classificação real, embedding 1024, índice sintético, self-match `>=0.99`, quatro casos funcionais e `report.ok=true`.

- [ ] **Step 5: Parar após o smoke ser disparado**

Informar:

```text
O Engine smoke foi disparado. Acompanhe no GitHub e retorne com "success" ou com o log da etapa que falhou. Não farei polling.
```

- [ ] **Step 6: Revisar antes do merge**

Exigir:

```text
[ ] CI Python quality = success
[ ] Engine smoke = success no SHA atual
[ ] diff somente Fase 1
[ ] nenhum segredo ou corpus real
[ ] local-ai-smoke.yml separado
[ ] equivalência dos 75 testes completa
[ ] nenhuma thread bloqueante
[ ] critérios da spec atendidos
```

Qualquer commit depois do engine smoke invalida aquela evidência e exige novo smoke para o novo SHA.

- [ ] **Step 7: Merge**

Integrar por pull request normal. Não mover `main` diretamente e não usar force push.

---

## Final Verification Checklist

```text
[ ] Python 3.14.x no CI e engine smoke
[ ] pip install -e .[dev] com sucesso
[ ] deps runtime exatamente NumPy, pandas e Requests nos ranges aprovados
[ ] ruff check . exit 0
[ ] ruff format --check . exit 0
[ ] pytest sem falhas
[ ] pacote oficial contém classification, data, ollama, index, retrieval e CLI
[ ] evidência literal prevalece sobre invenção do modelo
[ ] múltiplos sistemas -> CONTEXTO_AMBIGUO
[ ] SEM_EVIDENCIA -> candidates=[]
[ ] sistema desconhecido nunca promove outro sistema
[ ] conteúdo sensível excluído
[ ] Ollama rejeita host remoto, proxy, redirect e cloud model
[ ] embedding NaN, infinito e zero rejeitados
[ ] índice verifica source_hash, matrix_hash, recipe, model, digest e dimensions
[ ] checkpoint e retomada testados
[ ] import-legacy usa três sentinelas e destino novo
[ ] candidatos sempre HISTORICO_NAO_VALIDADO
[ ] somente fixture sintética de tickets no Git
[ ] 75 testes legados possuem destino documentado
[ ] CI hospedado sem Ollama real
[ ] local-ai-smoke.yml separado
[ ] engine-smoke.yml success para SHA integrado
[ ] PR revisado antes do merge
```

A Fase 2 só começa depois dessa checklist estar satisfeita. Corpus TI real e avaliação de retrieval permanecem fora desta implementação.
