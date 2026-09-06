# Fase 2 Retrieval no Corpus TI Real Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provar retrieval reproduzível sobre o snapshot real de 15.542 tickets de TI sem versionar dados corporativos, sem expor conteúdo em logs e sem alterar o algoritmo ou o threshold legado de `0.65`.

**Architecture:** Estender o motor oficial da Fase 1 com um módulo de auditoria segura do corpus e helpers de homologação agregada. `load_corpus`, `build_index`, `load_index`, `LocalEmbedder` e `RetrievalEngine` continuam sendo as implementações únicas. O corpus e o índice reais permanecem fora do checkout Git; o repositório contém somente contrato/fingerprint, código, testes sintéticos, workflow manual e documentação.

**Tech Stack:** Python 3.14, pandas, NumPy, Requests, pytest, Ruff, GitHub Actions, Windows PowerShell e Ollama local.

**Spec:** `docs/superpowers/specs/2026-09-06-phase-2-real-ti-corpus-retrieval-design.md`

## Global Constraints

- Python oficial: `>=3.14,<3.15`.
- Embedding real: `qwen3-embedding:0.6b`, dimensão `1024`.
- Receita: `texto_busca-plain-v1`.
- Threshold permanece `0.65`; não calibrar nesta fase.
- Snapshot v1: `15.542` linhas, `14.472` com histórico, `5` com `texto_limitado=true`.
- SHA-256 bruto esperado: `26b3ca70c91db22145cf16676c0d13a8b5c847e6303ee440a0806e395b6e12bb`.
- Hash canônico esperado: `3159a3430abfd6091b84e0216cd4cf9e029817357d0109ad6bc244ff5f5ec448`.
- `status_conhecimento=HISTORICO_NAO_VALIDADO` em 100% das linhas.
- Corpus real, `documents.jsonl`, `embeddings.npy`, índice parcial/completo e relatórios com conteúdo real nunca entram no Git nem em artifacts.
- CI hospedado usa somente fixtures sintéticas.
- Homologação real usa runner `[self-hosted, Windows, X64, ai-service-desk, ollama]`.
- Logs de homologação não podem imprimir ticket ID, número, título, descrição, `texto_busca` ou histórico.
- Similaridade continua sendo score, nunca probabilidade ou solução validada.

---

## File Structure

Arquivos novos:

- `src/ai_service_desk/engine/corpus.py`: contrato do snapshot, auditoria agregada, comparação com manifesto e validação segura de paths.
- `tests/engine/test_corpus.py`: testes unitários da auditoria e privacidade.
- `tests/fixtures/phase2_corpus.csv`: fixture sintética compatível com o schema real.
- `tests/fixtures/phase2_corpus_manifest.json`: manifesto sintético calculado a partir da fixture para testes.
- `docs/data/phase-2-corpus-v1.json`: contrato seguro do snapshot corporativo v1, sem conteúdo nem identificadores.
- `src/ai_service_desk/engine/real_smoke.py`: validação agregada de índice e invariantes de retrieval para homologação real.
- `tests/engine/test_real_smoke.py`: testes sintéticos dos helpers de homologação.
- `.github/workflows/real-corpus-smoke.yml`: workflow manual no Dell, sem upload de artifacts.

Arquivos modificados:

- `src/ai_service_desk/cli.py`: adicionar comando `audit` e entrada operacional para homologação segura.
- `tests/test_cli.py`: contrato do CLI sem vazamento.
- `.gitignore`: bloquear nomes canônicos de corpus/índice real no checkout, além dos diretórios gerados já existentes.
- `README.md`: documentar Fase 2, dados externos e comandos.
- `docs/environment/local-demo.md`: documentar diretório externo e operação do smoke real.

Não modificar o algoritmo em `retrieval.py` salvo se um teste de segurança revelar uma lacuna concreta. Não modificar `DEFAULT_THRESHOLD`.

---

### Task 1: Contrato e auditoria segura do snapshot

**Files:**
- Create: `src/ai_service_desk/engine/corpus.py`
- Create: `tests/engine/test_corpus.py`
- Create: `tests/fixtures/phase2_corpus.csv`
- Create: `tests/fixtures/phase2_corpus_manifest.json`
- Create: `docs/data/phase-2-corpus-v1.json`
- Reuse: `src/ai_service_desk/engine/data.py`
- Reuse: `src/ai_service_desk/engine/index.py`

**Interfaces:**
- Consumes: `load_corpus(path) -> pandas.DataFrame`, `corpus_bytes(data) -> bytes`, `file_hash(path) -> str`.
- Produces: `load_corpus_manifest(path: str | Path) -> dict`, `audit_corpus(corpus_path: str | Path, manifest_path: str | Path | None = None) -> dict`, `write_safe_report(path: str | Path, report: dict) -> None`, `ensure_external_path(path: str | Path, checkout: str | Path) -> Path`.

- [ ] **Step 1: Add a synthetic Phase 2 corpus fixture**

Create `tests/fixtures/phase2_corpus.csv` with semicolon delimiter and UTF-8 content using exactly these columns:

```text
ticket_id;ticket_number;title;description;created_at;catalogo;area;item;mesa;texto_busca;texto_limitado;historico_atendimento;apontamento_ids;status_conhecimento
1;1001;Falha CIGAM;Erro sintético;2026-01-01;Sistemas;CIGAM;ERP;TI;Assunto: Falha CIGAM Descricao: Erro sintético;false;Atendimento sintético sem dado real;10;HISTORICO_NAO_VALIDADO
2;1002;Falha SIAGRI;Erro sintético;2026-01-02;Sistemas;SIAGRI;ERP;TI;Assunto: Falha SIAGRI Descricao: Erro sintético;false;;11;HISTORICO_NAO_VALIDADO
3;1003;Impressora;Não imprime;2026-01-03;Impressoras;Infra;Impressão;TI;Assunto: Impressora Descricao: Não imprime;true;Orientação sintética;12;HISTORICO_NAO_VALIDADO
```

The fixture must contain no real ticket text, names, e-mails, IPs, CPFs, phone numbers, secrets or credentials.

- [ ] **Step 2: Write failing tests for aggregate audit**

Create `tests/engine/test_corpus.py` with tests equivalent to:

```python
from pathlib import Path

import pytest

from ai_service_desk.engine.corpus import audit_corpus, ensure_external_path

FIXTURE = Path("tests/fixtures/phase2_corpus.csv")


def test_audit_returns_only_aggregate_contract() -> None:
    report = audit_corpus(FIXTURE)

    assert report["rows"] == 3
    assert report["unique_ticket_ids"] == 3
    assert report["empty_ticket_ids"] == 0
    assert report["empty_search_texts"] == 0
    assert report["with_history"] == 2
    assert report["limited_texts"] == 1
    assert report["knowledge_status"] == {"HISTORICO_NAO_VALIDADO": 3}
    assert report["privacy"]["anonymization_claim"] is False
    serialized = str(report)
    assert "Falha CIGAM" not in serialized
    assert "1001" not in serialized
    assert "Atendimento sintético" not in serialized


def test_audit_detects_risk_counts_without_values(tmp_path: Path) -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    risky = tmp_path / "risky.csv"
    risky.write_text(source.replace("Erro sintético", "email pessoa@example.com"), encoding="utf-8")

    report = audit_corpus(risky)

    assert report["risk_counts"]["email"] > 0
    assert "pessoa@example.com" not in str(report)


def test_external_path_rejects_checkout_children(tmp_path: Path) -> None:
    checkout = tmp_path / "repo"
    checkout.mkdir()

    with pytest.raises(ValueError, match="fora do checkout"):
        ensure_external_path(checkout / "data" / "corpus.csv", checkout)

    external = tmp_path / "external" / "corpus.csv"
    assert ensure_external_path(external, checkout) == external.resolve()
```

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
python -m pytest tests/engine/test_corpus.py -v
```

Expected: collection or import failure because `ai_service_desk.engine.corpus` does not exist yet.

- [ ] **Step 4: Implement the minimal aggregate auditor**

Create `src/ai_service_desk/engine/corpus.py` with these rules:

```python
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ai_service_desk.engine.data import load_corpus
from ai_service_desk.engine.index import atomic_json, corpus_bytes, file_hash

EXPECTED_COLUMNS = (
    "ticket_id",
    "ticket_number",
    "title",
    "description",
    "created_at",
    "catalogo",
    "area",
    "item",
    "mesa",
    "texto_busca",
    "texto_limitado",
    "historico_atendimento",
    "apontamento_ids",
    "status_conhecimento",
)

RISK_PATTERNS = {
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "ipv4": re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"),
    "cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "phone": re.compile(r"(?<!\w)(?:\+55\s*)?\(?\d{2}\)?\s*9?\d{4}[- ]\d{4}(?!\d)"),
    "sensitive_term": re.compile(
        r"\b(senha|password|passwd|credencia\w*|token|secret|api[ _-]?key)\b", re.I
    ),
}


def ensure_external_path(path: str | Path, checkout: str | Path) -> Path:
    candidate = Path(path).resolve()
    root = Path(checkout).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate
    raise ValueError("Corpus, indice e relatorio reais devem ficar fora do checkout Git.")


def load_corpus_manifest(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Versao de manifesto de corpus nao suportada.")
    return data


def _risk_counts(data) -> dict[str, int]:
    columns = [column for column in EXPECTED_COLUMNS if column in data.columns]
    counts = {name: 0 for name in RISK_PATTERNS}
    for row in data[columns].fillna("").astype(str).itertuples(index=False, name=None):
        text = " ".join(row)
        for name, pattern in RISK_PATTERNS.items():
            if pattern.search(text):
                counts[name] += 1
    return counts


def audit_corpus(corpus_path: str | Path, manifest_path: str | Path | None = None) -> dict:
    path = Path(corpus_path)
    data = load_corpus(path)
    raw_hash = file_hash(path)
    canonical_hash = hashlib.sha256(corpus_bytes(data)).hexdigest()
    history = data["historico_atendimento"].astype(str).str.strip().ne("")
    limited = data["texto_limitado"].astype(str).str.lower().eq("true")
    report = {
        "version": 1,
        "rows": len(data),
        "columns": list(data.columns),
        "unique_ticket_ids": int(data["ticket_id"].nunique()),
        "empty_ticket_ids": int(data["ticket_id"].astype(str).str.strip().eq("").sum()),
        "empty_search_texts": int(data["texto_busca"].astype(str).str.strip().eq("").sum()),
        "with_history": int(history.sum()),
        "without_history": int((~history).sum()),
        "limited_texts": int(limited.sum()),
        "knowledge_status": {
            str(key): int(value)
            for key, value in data["status_conhecimento"]
            .value_counts(dropna=False)
            .to_dict()
            .items()
        },
        "raw_sha256": raw_hash,
        "canonical_sha256": canonical_hash,
        "max_lengths": {
            column: int(data[column].astype(str).str.len().max())
            for column in ("title", "description", "texto_busca", "historico_atendimento")
        },
        "risk_counts": _risk_counts(data),
        "privacy": {
            "rule_based_scan": True,
            "anonymization_claim": False,
            "human_review_required_before_history_display": True,
        },
    }
    if manifest_path is not None:
        validate_corpus_manifest(report, load_corpus_manifest(manifest_path))
        report["manifest_match"] = True
    return report


def validate_corpus_manifest(report: dict, manifest: dict) -> None:
    expected = manifest["expected"]
    checks = {
        "rows": report["rows"],
        "with_history": report["with_history"],
        "limited_texts": report["limited_texts"],
        "raw_sha256": report["raw_sha256"],
        "canonical_sha256": report["canonical_sha256"],
    }
    for key, actual in checks.items():
        if actual != expected[key]:
            raise ValueError(f"Snapshot divergente no campo agregado: {key}.")
    if report["columns"] != manifest["columns"]:
        raise ValueError("Schema do snapshot divergente do manifesto.")
    if report["unique_ticket_ids"] != report["rows"] or report["empty_ticket_ids"]:
        raise ValueError("ticket_id vazio ou duplicado no snapshot.")
    if report["empty_search_texts"]:
        raise ValueError("texto_busca vazio no snapshot.")
    if report["knowledge_status"] != {"HISTORICO_NAO_VALIDADO": report["rows"]}:
        raise ValueError("status_conhecimento invalido no snapshot.")


def write_safe_report(path: str | Path, report: dict) -> None:
    atomic_json(Path(path), report)
```

Keep the report strictly aggregate. Do not add ticket IDs, sample values, example texts or failing-row indexes.

- [ ] **Step 5: Create the synthetic manifest from the fixture's actual hashes**

Run a one-off local script against the fixture to obtain its `raw_sha256` and `canonical_sha256`, then create `tests/fixtures/phase2_corpus_manifest.json` with:

```json
{
  "version": 1,
  "name": "phase2-synthetic-v1",
  "columns": [
    "ticket_id",
    "ticket_number",
    "title",
    "description",
    "created_at",
    "catalogo",
    "area",
    "item",
    "mesa",
    "texto_busca",
    "texto_limitado",
    "historico_atendimento",
    "apontamento_ids",
    "status_conhecimento"
  ],
  "expected": {
    "rows": 3,
    "with_history": 2,
    "limited_texts": 1,
    "raw_sha256": "<actual fixture raw SHA-256>",
    "canonical_sha256": "<actual fixture canonical SHA-256>"
  }
}
```

Before committing, replace both literal hash markers with the values produced by the code. Do not commit the angle-bracket markers.

- [ ] **Step 6: Add manifest-comparison failure tests**

Add tests that copy the synthetic manifest and change each critical field independently. Assert `audit_corpus(..., manifest)` raises `ValueError` for changed rows, changed raw SHA, changed canonical SHA, changed schema and invalid status.

- [ ] **Step 7: Add the real snapshot safe manifest**

Create `docs/data/phase-2-corpus-v1.json` containing no ticket data:

```json
{
  "version": 1,
  "name": "phase-2-corpus-v1",
  "description": "Snapshot preparado do histórico de TI. Conteúdo corporativo permanece fora do Git.",
  "columns": [
    "ticket_id",
    "ticket_number",
    "title",
    "description",
    "created_at",
    "catalogo",
    "area",
    "item",
    "mesa",
    "texto_busca",
    "texto_limitado",
    "historico_atendimento",
    "apontamento_ids",
    "status_conhecimento"
  ],
  "expected": {
    "rows": 15542,
    "with_history": 14472,
    "limited_texts": 5,
    "raw_sha256": "26b3ca70c91db22145cf16676c0d13a8b5c847e6303ee440a0806e395b6e12bb",
    "canonical_sha256": "3159a3430abfd6091b84e0216cd4cf9e029817357d0109ad6bc244ff5f5ec448"
  },
  "knowledge_status": "HISTORICO_NAO_VALIDADO",
  "privacy": {
    "masking": "partial-rule-based",
    "anonymization_claim": false,
    "human_review_required_before_history_display": true
  }
}
```

- [ ] **Step 8: Run Task 1 tests GREEN**

Run:

```bash
python -m pytest tests/engine/test_corpus.py -v
python -m ruff check src/ai_service_desk/engine/corpus.py tests/engine/test_corpus.py
python -m ruff format --check src/ai_service_desk/engine/corpus.py tests/engine/test_corpus.py
```

Expected: all pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add src/ai_service_desk/engine/corpus.py tests/engine/test_corpus.py tests/fixtures/phase2_corpus.csv tests/fixtures/phase2_corpus_manifest.json docs/data/phase-2-corpus-v1.json
git commit -m "feat: audit prepared corpus snapshots"
```

---

### Task 2: CLI `audit` sem Ollama e sem vazamento

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `audit_corpus`, `write_safe_report`.
- Produces: CLI `python -m ai_service_desk audit --file ... --manifest ... --report ...`.

- [ ] **Step 1: Write failing CLI tests**

Add:

```python
def test_audit_writes_aggregate_report_without_ollama(tmp_path: Path, monkeypatch) -> None:
    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("audit must not create Ollama client")

    monkeypatch.setattr(cli, "OllamaClient", ForbiddenClient)
    report = tmp_path / "audit.json"
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(
            [
                "audit",
                "--file",
                "tests/fixtures/phase2_corpus.csv",
                "--manifest",
                "tests/fixtures/phase2_corpus_manifest.json",
                "--report",
                str(report),
            ]
        )

    assert code == 0
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["manifest_match"] is True
    assert "Falha CIGAM" not in report.read_text(encoding="utf-8")
    assert "Falha CIGAM" not in stdout.getvalue()
    assert "1001" not in stdout.getvalue()
```

Also update the help test to assert `"audit" in result.stdout`.

- [ ] **Step 2: Run focused CLI tests RED**

```bash
python -m pytest tests/test_cli.py::test_audit_writes_aggregate_report_without_ollama -v
```

Expected: parser rejects the unknown `audit` command.

- [ ] **Step 3: Add parser and command handling**

In `build_parser()` add:

```python
audit = sub.add_parser("audit")
audit.add_argument("--file", type=Path, required=True)
audit.add_argument("--manifest", type=Path, required=True)
audit.add_argument("--report", type=Path, required=True)
```

Import:

```python
from ai_service_desk.engine.corpus import audit_corpus, write_safe_report
```

Before any `OllamaClient` creation in `main()` add:

```python
if args.command == "audit":
    report = audit_corpus(args.file, args.manifest)
    write_safe_report(args.report, report)
    summary = {
        key: report[key]
        for key in (
            "rows",
            "unique_ticket_ids",
            "empty_ticket_ids",
            "empty_search_texts",
            "with_history",
            "limited_texts",
            "raw_sha256",
            "canonical_sha256",
            "manifest_match",
        )
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Auditoria por regras concluida. Nenhum conteudo de ticket foi exibido.")
    return 0
```

Do not print `columns`, `max_lengths` or `risk_counts` if later they acquire user-provided keys. The safe report file remains the complete aggregate contract.

- [ ] **Step 4: Run Task 2 tests GREEN**

```bash
python -m pytest tests/test_cli.py -v
python -m ruff check src/ai_service_desk/cli.py tests/test_cli.py
python -m ruff format --check src/ai_service_desk/cli.py tests/test_cli.py
```

Expected: all pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/ai_service_desk/cli.py tests/test_cli.py
git commit -m "feat: add safe corpus audit command"
```

---

### Task 3: Validação agregada do índice e invariantes reais

**Files:**
- Create: `src/ai_service_desk/engine/real_smoke.py`
- Create: `tests/engine/test_real_smoke.py`
- Reuse unchanged: `src/ai_service_desk/engine/index.py`
- Reuse unchanged unless a failing test proves otherwise: `src/ai_service_desk/engine/retrieval.py`

**Interfaces:**
- Consumes: `load_index`, `RetrievalEngine.search`, embedder metadata.
- Produces: `validate_real_index(index_directory, expected: dict) -> dict`, `run_safe_queries(engine, cases: list[dict]) -> list[dict]`, `build_real_smoke_report(...) -> dict`.

- [ ] **Step 1: Write failing tests for index aggregate validation**

Use a tiny synthetic index fixture built with a fake embedder. The test must assert the returned report contains only aggregate fields:

```python
def test_validate_real_index_reports_shape_and_integrity_without_documents(tmp_path: Path) -> None:
    # build small index using phase2 synthetic corpus and FakeEmbedder
    report = validate_real_index(
        tmp_path / "index",
        {
            "rows": 3,
            "dimensions": 4,
            "model": "synthetic-embedder",
            "model_digest": "digest-v1",
            "recipe": "texto_busca-plain-v1",
        },
    )

    assert report["rows"] == 3
    assert report["shape"] == [3, 4]
    assert report["finite"] is True
    assert report["normalized"] is True
    assert report["complete"] is True
    assert report["self_similarity"] > 0.999
    assert "documents" not in report
    assert "ticket_id" not in str(report)
```

- [ ] **Step 2: Write failing tests for safe query result projection**

Create a fake engine whose `search` returns candidate dictionaries containing forbidden fields. Assert `run_safe_queries` keeps only case name, expected system/intent, actual system/intent, status, candidate count, best score, pool size and pass/fail booleans.

Required assertions:

```python
assert "ticket_number" not in str(report)
assert "title" not in str(report)
assert "texto_busca" not in str(report)
assert "historico_atendimento" not in str(report)
```

Add explicit cases for:

- CIGAM single-system, candidate systems must all be compatible.
- SIAGRI single-system, same rule.
- unknown synthetic system, `SEM_CONTEXTO`, zero candidates.
- CIGAM + SIAGRI, `CONTEXTO_AMBIGUO`, zero candidates.
- printing query, `intent=PROBLEMA_IMPRESSAO`, any non-error status accepted.

- [ ] **Step 3: Run Task 3 tests RED**

```bash
python -m pytest tests/engine/test_real_smoke.py -v
```

Expected: import failure because `real_smoke.py` is missing.

- [ ] **Step 4: Implement safe index validation**

`validate_real_index` must call `load_index`, validate expected rows/dimensions/model/digest/recipe/source hash when supplied, verify `np.isfinite(matrix).all()`, verify row norms with `np.allclose(..., 1, atol=1e-4)`, and compute self-similarity of row `0` only as a numeric scalar. It must never serialize the selected document.

Return only:

```python
{
    "rows": int,
    "shape": [int, int],
    "dimensions": int,
    "model": str,
    "model_digest": str,
    "recipe": str,
    "source_hash": str,
    "complete": bool,
    "finite": bool,
    "normalized": bool,
    "self_similarity": float,
}
```

If any expected field differs, raise `ValueError` before queries run.

- [ ] **Step 5: Implement safe query projection and invariant checks**

`run_safe_queries` must accept cases shaped as:

```python
{
    "name": "cigam",
    "query": "No CIGAM aparece erro ao abrir uma rotina de exemplo.",
    "expected_system": "CIGAM",
    "allowed_statuses": ["ENCONTRADOS", "SEM_EVIDENCIA"],
}
```

The function must execute each query, inspect candidates in memory, assert invariant conditions and return only aggregate summaries. For single explicit CIGAM/SIAGRI cases, inspect each candidate's metadata for system compatibility but never include candidate fields in the summary.

Use these exact synthetic query strings for real homologation:

```text
No CIGAM aparece erro ao abrir uma rotina de exemplo.
No SIAGRI aparece erro ao abrir uma rotina de exemplo.
No sistema XYZ aparece um erro de exemplo.
CIGAM e SIAGRI apresentam um erro de exemplo.
A impressora de exemplo nao imprime.
```

- [ ] **Step 6: Implement the combined safe report**

`build_real_smoke_report` must return:

```python
{
    "version": 1,
    "ok": bool,
    "corpus": <aggregate audit report>,
    "index": <aggregate index report>,
    "queries": <aggregate query summaries>,
    "threshold": 0.65,
    "privacy": {
        "contains_ticket_content": False,
        "contains_ticket_identifiers": False,
        "history_displayed": False,
    },
}
```

Do not add timing logs containing per-ticket data. Numeric timings are acceptable only if needed later, but omit them in Phase 2 unless required by an existing contract.

- [ ] **Step 7: Run Task 3 tests GREEN**

```bash
python -m pytest tests/engine/test_real_smoke.py tests/engine/test_retrieval.py tests/engine/test_index.py -v
python -m ruff check src/ai_service_desk/engine/real_smoke.py tests/engine/test_real_smoke.py
python -m ruff format --check src/ai_service_desk/engine/real_smoke.py tests/engine/test_real_smoke.py
```

Expected: all pass and no change to retrieval threshold behavior.

- [ ] **Step 8: Commit Task 3**

```bash
git add src/ai_service_desk/engine/real_smoke.py tests/engine/test_real_smoke.py
git commit -m "feat: validate real retrieval safely"
```

---

### Task 4: Operação de homologação real no Dell

**Files:**
- Modify: `src/ai_service_desk/cli.py`
- Modify: `tests/test_cli.py`
- Create: `.github/workflows/real-corpus-smoke.yml`
- Modify: `.gitignore`
- Modify: `docs/environment/local-demo.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `audit_corpus`, `build_index`, `LocalEmbedder`, `OllamaClient`, `RetrievalEngine`, `validate_real_index`, `run_safe_queries`, `write_safe_report`.
- Produces: CLI `real-smoke` for one safe orchestration and manual workflow invoking it.

- [ ] **Step 1: Write failing parser/orchestration tests**

Add a CLI test that monkeypatches the orchestration function and verifies all paths and URL are forwarded without constructing output from ticket content:

```python
def test_real_smoke_forwards_external_paths(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    def fake_run(corpus, manifest, index, report, base_url, checkout):
        captured.update(
            corpus=corpus,
            manifest=manifest,
            index=index,
            report=report,
            base_url=base_url,
            checkout=checkout,
        )
        Path(report).write_text('{"ok": true}', encoding="utf-8")
        return {"ok": True, "index": {"rows": 3}, "queries": []}

    monkeypatch.setattr(cli, "run_real_smoke", fake_run)
    code = cli.main(
        [
            "real-smoke",
            "--file",
            str(tmp_path / "external" / "corpus.csv"),
            "--manifest",
            "tests/fixtures/phase2_corpus_manifest.json",
            "--index",
            str(tmp_path / "external" / "index"),
            "--report",
            str(tmp_path / "external" / "report.json"),
            "--checkout",
            str(tmp_path / "repo"),
        ]
    )
    assert code == 0
    assert captured["base_url"] == "http://127.0.0.1:11434"
```

- [ ] **Step 2: Add `run_real_smoke` orchestration**

Place orchestration in `real_smoke.py`. Required order:

1. `ensure_external_path` for corpus, index and report against checkout.
2. `audit_corpus(corpus, manifest)`.
3. create `OllamaClient` from loopback URL only.
4. create `LocalEmbedder` and verify model information.
5. `load_corpus(corpus)` then `build_index(data, index, embedder)` to build/resume.
6. build `RetrievalEngine(index, client, embedder, threshold=0.65)`.
7. validate index against snapshot expected values plus live `model_digest`.
8. execute the five synthetic safe queries.
9. write aggregate report locally.
10. close client in `finally`.

The function must not call `format_result` and must not print or return candidate bodies.

- [ ] **Step 3: Add CLI `real-smoke`**

Parser:

```python
real_smoke = sub.add_parser("real-smoke")
real_smoke.add_argument("--file", type=Path, required=True)
real_smoke.add_argument("--manifest", type=Path, required=True)
real_smoke.add_argument("--index", type=Path, required=True)
real_smoke.add_argument("--report", type=Path, required=True)
real_smoke.add_argument("--checkout", type=Path, required=True)
real_smoke.add_argument("--url", default=DEFAULT_URL)
```

Output on success is restricted to:

```text
REAL CORPUS SMOKE OK
Registros auditados: 15542
Vetores validados: 15542 x 1024
Casos sintéticos: 5
Relatório agregado local: <path>
```

On failure, existing top-level error handling prints only the exception message. Error messages in Phase 2 helpers must never interpolate ticket content or IDs.

- [ ] **Step 4: Extend `.gitignore` defensively**

Add explicit local-only patterns:

```gitignore
# Corporate data must stay outside Git
base_ti_preparada.csv
**/base_ti_preparada.csv
**/documents.jsonl
**/embeddings.npy
phase-2-data/
```

This is defense in depth, not permission to store real data under the checkout.

- [ ] **Step 5: Add the permanent manual workflow**

Create `.github/workflows/real-corpus-smoke.yml`:

```yaml
name: Real corpus smoke

on:
  workflow_dispatch:
    inputs:
      target_ref:
        description: Branch or SHA to validate
        required: true
        type: string
      corpus_path:
        description: Absolute path to base_ti_preparada.csv outside the checkout
        required: true
        default: C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv
        type: string
      index_path:
        description: Absolute path to local Phase 2 index outside the checkout
        required: true
        default: C:\ai-service-desk-data\phase-2\index
        type: string
      report_path:
        description: Absolute path to aggregate local report
        required: true
        default: C:\ai-service-desk-data\phase-2\reports\real-corpus-smoke.json
        type: string

permissions:
  contents: read

jobs:
  real-corpus-smoke:
    name: Windows real corpus smoke
    runs-on: [self-hosted, Windows, X64, ai-service-desk, ollama]
    timeout-minutes: 180

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
          if (-not $version.StartsWith("3.14.")) { throw "Python 3.14.x required. Found $version" }

      - name: Install project
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev]"

      - name: Audit, index and validate real corpus
        shell: powershell -NoProfile -ExecutionPolicy Bypass -Command ". '{0}'"
        run: |
          $ErrorActionPreference = "Stop"
          python -m ai_service_desk real-smoke `
            --file "${{ inputs.corpus_path }}" `
            --manifest "docs/data/phase-2-corpus-v1.json" `
            --index "${{ inputs.index_path }}" `
            --report "${{ inputs.report_path }}" `
            --checkout "$env:GITHUB_WORKSPACE" `
            --url "http://127.0.0.1:11434"
```

Do not add `actions/upload-artifact`. Do not `Get-Content` the local report. Do not enumerate candidate documents.

- [ ] **Step 6: Add workflow-structure tests without executing real data**

Create or extend a test that reads `.github/workflows/real-corpus-smoke.yml` as text and asserts:

```python
assert "workflow_dispatch" in workflow
assert "self-hosted" in workflow
assert "ollama" in workflow
assert "upload-artifact" not in workflow
assert "Get-Content" not in workflow
assert "--show-history" not in workflow
assert "base_ti_preparada.csv" in workflow
```

If no workflow-test file exists, add `tests/test_workflows.py` with this single responsibility.

- [ ] **Step 7: Document external data operation**

Update `docs/environment/local-demo.md` with:

```text
C:\ai-service-desk-data\phase-2\
  corpus\base_ti_preparada.csv
  index\
  reports\real-corpus-smoke.json
```

State explicitly that these paths are outside `C:\actions-runner\_work\...` and outside any repo clone. Document that `run.cmd` must remain open, exactly as in the current local runner workflow.

Update `README.md` with `audit` and `real-smoke` examples, plus the statement that the real corpus and index are never committed.

- [ ] **Step 8: Run Task 4 GREEN**

```bash
python -m pytest tests/test_cli.py tests/test_workflows.py tests/engine/test_real_smoke.py -v
python -m ruff check .
python -m ruff format --check .
```

Expected: all pass.

- [ ] **Step 9: Commit Task 4**

```bash
git add src/ai_service_desk/cli.py src/ai_service_desk/engine/real_smoke.py tests/test_cli.py tests/test_workflows.py .gitignore .github/workflows/real-corpus-smoke.yml docs/environment/local-demo.md README.md
git commit -m "feat: add real corpus homologation workflow"
```

---

### Task 5: Full verification, real Dell homologation and PR

**Files:**
- Review all Phase 2 changed files.
- No production file should be added in this task unless a verification failure requires a targeted fix with its own failing test first.

**Interfaces:**
- Consumes the complete Phase 2 implementation.
- Produces fresh CI evidence, real Dell smoke evidence and final PR ready for review.

- [ ] **Step 1: Verify no forbidden corporate artifacts are in Git**

Run:

```bash
git diff --name-only main...HEAD
git ls-files | grep -E '(^|/)(base_ti_preparada\.csv|documents\.jsonl|embeddings\.npy)$' && exit 1 || true
```

Expected: no corporate corpus/index artifact tracked. The only CSV added by Phase 2 is `tests/fixtures/phase2_corpus.csv` and it is synthetic.

- [ ] **Step 2: Run the full hosted-equivalent quality suite**

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected: all pass with Python 3.14. If the local executor is not Python 3.14, do not relax `requires-python`; use hosted PR CI as the executable acceptance environment.

- [ ] **Step 3: Review the threshold and algorithm diff**

Run:

```bash
git diff main...HEAD -- src/ai_service_desk/engine/retrieval.py src/ai_service_desk/cli.py
```

Expected: no change to retrieval threshold `0.65`, no reranker, no generation, no alternate retriever.

- [ ] **Step 4: Create the PR to `main`**

PR body must state:

- real corpus and index remain outside Git;
- audit report is aggregate only;
- hosted CI uses synthetic data only;
- real workflow has no upload-artifact;
- threshold `0.65` is unchanged;
- real Dell smoke is still a required gate before merge.

- [ ] **Step 5: Wait for hosted CI without polling outside the operator-approved window**

CI must prove on Python 3.14:

```text
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

Do not claim the phase is ready while CI is failing or pending.

- [ ] **Step 6: Prepare the Dell external directory**

Required operator state:

```text
C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv
C:\ai-service-desk-data\phase-2\index\
C:\ai-service-desk-data\phase-2\reports\
```

The corpus file must have raw SHA-256 `26b3ca70c91db22145cf16676c0d13a8b5c847e6303ee440a0806e395b6e12bb` before indexing. `C:\actions-runner\run.cmd` must show `Listening for Jobs`.

- [ ] **Step 7: Execute the permanent `Real corpus smoke`**

Use inputs:

```text
target_ref=phase-2-real-corpus
corpus_path=C:\ai-service-desk-data\phase-2\corpus\base_ti_preparada.csv
index_path=C:\ai-service-desk-data\phase-2\index
report_path=C:\ai-service-desk-data\phase-2\reports\real-corpus-smoke.json
```

If connector dispatch is unavailable, create a temporary push-trigger workflow that copies the permanent job exactly except for the trigger and fixed branch. It must be removed before final review. Never upload the report.

- [ ] **Step 8: Verify real smoke completion evidence**

The job must complete with success and the safe summary must establish:

```text
rows = 15542
shape = [15542, 1024]
model = qwen3-embedding:0.6b
recipe = texto_busca-plain-v1
source_hash = 3159a3430abfd6091b84e0216cd4cf9e029817357d0109ad6bc244ff5f5ec448
complete = true
five synthetic cases executed
unknown system -> SEM_CONTEXTO, 0 candidates
CIGAM + SIAGRI -> CONTEXTO_AMBIGUO, 0 candidates
printing -> PROBLEMA_IMPRESSAO
```

For CIGAM and SIAGRI, success means no cross-system candidate. It does not require `ENCONTRADOS`.

- [ ] **Step 9: Verify the local aggregate report does not leak content**

On the Dell, validate JSON keys only. The report must not contain keys:

```text
ticket_id
ticket_number
title
description
texto_busca
historico_atendimento
```

Do not print report values to GitHub Actions. A local structural validator should fail if forbidden keys are present anywhere recursively.

- [ ] **Step 10: Final diff review and PR review**

Confirm changed files match the approved scope, there are no temporary workflows, no real data, no new dependencies unless justified, and no open review threads. Add final Inline review evidence.

- [ ] **Step 11: Merge only after all Phase 2 exit criteria are evidenced**

Use merge commit, preserve implementation history, and pass the expected PR head SHA to avoid merging a moved branch.

- [ ] **Step 12: Confirm post-merge state**

Read PR state and `main` head. Record the merge commit. Phase 3 may start only after this confirmation.

---

## Self-Review Against the Spec

- Corpus v1 fingerprint, row counts, history count, limited-text count and status contract are implemented in Task 1.
- Aggregate-only reporting and risk-count privacy are implemented in Task 1 and Task 2.
- Corpus/index outside Git and outside checkout are enforced in Task 1, Task 4 and Task 5.
- Existing `build_index` and `RetrievalEngine` are reused. No parallel retrieval stack is introduced.
- Real index shape, model, digest, recipe, source hash, normalization and self-similarity are covered in Task 3 and Task 5.
- CIGAM, SIAGRI, unknown system, ambiguous system and printing smoke cases are covered in Task 3 and Task 5.
- Hosted CI remains synthetic in Tasks 1 through 5.
- Permanent manual Dell workflow with no artifacts is covered in Task 4.
- Threshold `0.65` remains unchanged and uncalibrated.
- No evaluation metrics such as precision, recall, MRR, nDCG or hit rate are added.
- No placeholders may remain in committed code, manifests or workflow. Hash markers in the synthetic manifest step must be replaced with actual fixture hashes before commit.
