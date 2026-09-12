# Phase 13 Requester Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o Jup Resolve em uma experiência desktop de autoatendimento para o solicitante, com FAQ APPROVED como porta de entrada, chat dedicado do Jup, identidade Juparanã própria e operação técnica removida da navegação pública, sem alterar as decisões de domínio homologadas na Fase 12.

**Architecture:** A mudança permanece na application layer `ai_service_desk.web` e no frontend ES Modules. Um novo catálogo de FAQ projeta somente Knowledge `APPROVED` já existente, expõe endpoints HTTP seguros e determinísticos e alimenta a nova home `/`; o chat `/jup` continua usando o runtime da Fase 12 sem mudar seu contrato de decisão. A UI pública resolve uma identity demo allowlisted por rota, nunca por texto ou seletor visível.

**Tech Stack:** Python 3.14, FastAPI 0.141.1, pytest, Ruff 0.12.12, HTML semântico, CSS próprio, JavaScript ES Modules, Node `node:test`, zero dependências npm de runtime.

**Spec:** `docs/superpowers/specs/2026-09-12-phase-13-requester-experience-design.md`

## Global Constraints

- Base SHA exato: `96d88ed58df5e2d007aedd8cbed2f2c779750e05`.
- Criar nova branch/worktree: `phase-13-requester-experience`.
- Não alterar `phase-12-web-demo`, Draft PR #15 ou o candidate homologado.
- Desktop-only: QA em `1280`, `1440` e `1600` px; não criar trabalho de mobile/tablet.
- Empresa: `Juparanã`.
- Produto: `Jup Resolve`.
- Agente: `Jup`.
- Brand green: `#45813C`.
- Brand yellow: `#EEB41E`.
- Brand gray: `#808285`.
- Brand white: `#FFFFFF`.
- Sem slogans ou copy de autopromoção na UI.
- `/` é Soluções/FAQ; `/jup` é chat.
- Header público contém somente `Jup Resolve`, `Soluções`, `Falar com o Jup`.
- Nenhum seletor de identity na UI pública.
- Operação/Prevenção não aparecem na nav pública.
- FAQ publica apenas Knowledge `APPROVED`.
- `DRAFT`, `RETIRED`, `HISTORICO_NAO_VALIDADO` nunca viram orientação.
- Histórico do Drive é fonte de priorização, não de resposta oficial.
- Máximo `16` soluções; máximo `4` categorias destacadas; máximo `4` itens por categoria.
- Link Microsoft permitido: `https://mysignins.microsoft.com/security-info/password/change`.
- Frontend nunca decide policy, routing, approval, execution ou prevention.
- Frontend nunca chama CDM/Ollama diretamente.
- Identity nunca vem do texto do chat.
- Nenhum módulo core protegido pode mudar.
- Sem framework frontend, CDN, fonte externa ou dependência npm de runtime.
- TDD estrito: `RED -> GREEN -> REFACTOR`.
- Commits pequenos por task.
- Não fazer push, merge, Ready for Review ou delete de branch sem autorização explícita.

---

## Execution Preflight

Antes de editar:

```bash
git status --short
git rev-parse HEAD
git branch --show-current
```

O ponto de partida deve ser exatamente:

```text
96d88ed58df5e2d007aedd8cbed2f2c779750e05
```

Criar worktree/branch isolado conforme `superpowers:using-git-worktrees`.

No worktree novo, executar Impeccable context uma vez. A direção visual já foi aprovada; não reabrir escolha estética para o usuário. Antes do primeiro edit de UI, carregar o craft floor e usar a orientação de `animate`/`colorize` durante execução e finish review.

Se `jup-avatar-animated.zip` não estiver disponível no workspace, Tasks 1–6 e 8–9 podem seguir; Task 7 deve parar no ponto explicitado, sem gerar mascote substituto.

---

## File Map

### Create

```text
src/ai_service_desk/web/demo_faq.py
tests/web/test_demo_faq.py
tests/web/test_faq_api.py

web/src/solutions.mjs
web/src/knowledge_content.mjs
web/src/jup_visual.mjs
web/src/jup_visual_assets.mjs               # criado somente após inspeção do asset fornecido
web/src/assets/jup/*                        # somente assets fornecidos pelo usuário

web/tests/solutions.test.mjs
web/tests/knowledge-content.test.mjs
web/tests/jup-visual.test.mjs
web/tests/requester-experience.test.mjs

docs/demo/phase-13-requester-experience.md
```

### Modify

```text
src/ai_service_desk/web/demo_runtime.py
src/ai_service_desk/web/api.py

web/src/app.mjs
web/src/components.mjs
web/src/render.mjs
web/src/router.mjs
web/src/state.mjs
web/src/styles.css
web/scripts/lint.mjs

web/tests/router.test.mjs
web/tests/render.test.mjs
web/tests/task9-safe-ui.test.mjs

tests/web/test_phase12_security.py
docs/environment/web-demo.md
```

### Protected and expected unchanged

```text
src/ai_service_desk/engine/access_request.py
src/ai_service_desk/engine/policy.py
src/ai_service_desk/engine/request_lifecycle.py
src/ai_service_desk/engine/request_repository.py
src/ai_service_desk/engine/approval.py
src/ai_service_desk/engine/execution.py
src/ai_service_desk/engine/cdm_execution.py
src/ai_service_desk/integrations/cdm.py
src/ai_service_desk/integrations/cdm_fake_api.py
```

Não alterar `src/ai_service_desk/engine/knowledge.py`; consumir `load_knowledge()` e `approved_articles()`.

---

### Task 1: Approved FAQ catalog in the web application layer

**Files:**
- Create: `src/ai_service_desk/web/demo_faq.py`
- Create: `tests/web/test_demo_faq.py`

**Interfaces:**
- Consumes: `load_knowledge(path)`, `approved_articles(articles)` from `ai_service_desk.engine.knowledge`.
- Produces: `DemoFaqCatalog.from_sources(sources)`, `featured_groups()`, `search(query)`, `detail(knowledge_id)`.
- Produces safe public fields only: `knowledge_id`, `title`, `question`, `system`, `category`, `answer` on detail, and exact allowlisted `procedure_url` when applicable.

- [ ] **Step 1: Write failing catalog tests**

Create `tests/web/test_demo_faq.py` with tests equivalent to:

```python
import json

import pytest

from ai_service_desk.web.demo_faq import DemoFaqCatalog, FaqNotFoundError


def _article(
    knowledge_id: str,
    *,
    status: str = "APPROVED",
    system: str = "SIAGRI",
    intent: str = "PROBLEMA_ACESSO",
    tags: list[str] | None = None,
    title: str = "Acesso ao SIAGRI",
    question: str = "Não consigo acessar o SIAGRI.",
    answer: str = "Orientação aprovada.",
) -> dict:
    return {
        "knowledge_id": knowledge_id,
        "title": title,
        "question": question,
        "answer": answer,
        "system": system,
        "intent": intent,
        "tags": tags or ["acesso"],
        "source": "SYNTHETIC_DEMO",
        "status": status,
        "reviewed_by": "DEMO-REVIEWER" if status == "APPROVED" else "",
        "reviewed_at": "2026-09-12T09:00:00-03:00" if status == "APPROVED" else "",
        "version": 1,
    }


def _write(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_catalog_exposes_only_approved_and_never_review_metadata(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(
        source,
        [
            _article("KB-APPROVED"),
            _article("KB-DRAFT", status="DRAFT"),
            _article("KB-RETIRED", status="RETIRED"),
        ],
    )
    catalog = DemoFaqCatalog.from_sources([source])

    items = catalog.search("")

    assert [item["knowledge_id"] for item in items] == ["KB-APPROVED"]
    assert "answer" not in items[0]
    assert "reviewed_by" not in items[0]
    assert "reviewed_at" not in items[0]
    assert "source" not in items[0]


def test_featured_groups_have_at_most_four_groups_and_four_items_each(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    rows = []
    for index in range(6):
        rows.append(_article(f"KB-SIAGRI-{index}", title=f"SIAGRI {index}"))
    for index in range(3):
        rows.append(
            _article(
                f"KB-CIGAM-{index}",
                system="CIGAM",
                title=f"CIGAM {index}",
                question="CIGAM não abre.",
            )
        )
    _write(source, rows)
    catalog = DemoFaqCatalog.from_sources([source])

    groups = catalog.featured_groups()

    assert len(groups) <= 4
    assert all(len(group["items"]) <= 4 for group in groups)
    assert sum(len(group["items"]) for group in groups) <= 16


def test_search_is_accent_insensitive_and_deterministic(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(
        source,
        [
            _article("KB-CIGAM", system="CIGAM", title="Acesso ao CIGAM", question="CIGAM não abre."),
            _article("KB-SIAGRI", title="Acesso ao SIAGRI", question="SIAGRI não abre."),
        ],
    )
    catalog = DemoFaqCatalog.from_sources([source])

    first = catalog.search("nao abre cigam")
    second = catalog.search("não abre CIGAM")

    assert first == second
    assert first[0]["knowledge_id"] == "KB-CIGAM"


def test_m365_password_detail_exposes_only_fixed_procedure_url(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(
        source,
        [
            _article(
                "KB-SYN-M365-PASSWORD-001",
                system="OFFICE 365",
                title="Recuperar acesso ao Microsoft 365",
                question="Minha senha não funciona.",
                tags=["senha", "microsoft-365"],
            )
        ],
    )
    detail = DemoFaqCatalog.from_sources([source]).detail("KB-SYN-M365-PASSWORD-001")

    assert detail["procedure_url"] == "https://mysignins.microsoft.com/security-info/password/change"


def test_unknown_detail_fails_closed(tmp_path):
    source = tmp_path / "knowledge.jsonl"
    _write(source, [_article("KB-ONE")])
    catalog = DemoFaqCatalog.from_sources([source])

    with pytest.raises(FaqNotFoundError):
        catalog.detail("KB-MISSING")
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_demo_faq.py -q
```

Expected: FAIL because `demo_faq.py` does not exist.

- [ ] **Step 3: Implement the minimal catalog**

Create `src/ai_service_desk/web/demo_faq.py` with these contracts:

```python
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ai_service_desk.engine.knowledge import approved_articles, load_knowledge

MAX_FAQ_RESULTS = 16
MAX_FEATURED_CATEGORIES = 4
MAX_FEATURED_PER_CATEGORY = 4
APPROVED_M365_PASSWORD_URL = "https://mysignins.microsoft.com/security-info/password/change"

_FEATURED_CATEGORY_ORDER = (
    ("siagri", "SIAGRI"),
    ("cigam", "CIGAM"),
    ("microsoft-365", "Microsoft 365"),
    ("equipamentos-impressao", "Equipamentos e impressão"),
)


class FaqNotFoundError(ValueError):
    pass


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())


def _category(article: dict) -> tuple[str, str] | tuple[None, None]:
    system = _normalize(article.get("system", ""))
    tags = {_normalize(tag) for tag in article.get("tags", [])}
    intent = article.get("intent", "")

    if "siagri" in system or "siagri" in tags:
        return "siagri", "SIAGRI"
    if "cigam" in system or "cigam" in tags:
        return "cigam", "CIGAM"
    if (
        system in {"office 365", "microsoft 365", "outlook", "teams", "onedrive"}
        or tags & {"microsoft-365", "outlook", "teams", "onedrive"}
    ):
        return "microsoft-365", "Microsoft 365"
    if intent == "PROBLEMA_IMPRESSAO" or tags & {"impressao", "impressora", "scanner"}:
        return "equipamentos-impressao", "Equipamentos e impressão"
    return None, None


@dataclass(frozen=True)
class _Entry:
    article: dict
    category_key: str | None
    category_label: str | None


class DemoFaqCatalog:
    def __init__(self, entries: list[_Entry]) -> None:
        self._entries = entries
        self._by_id = {entry.article["knowledge_id"]: entry for entry in entries}

    @classmethod
    def from_sources(cls, sources: list[str | Path]) -> "DemoFaqCatalog":
        merged: dict[str, dict] = {}
        for source in sources:
            for article in approved_articles(load_knowledge(source)):
                merged[article["knowledge_id"]] = article
        entries = []
        for article in merged.values():
            key, label = _category(article)
            entries.append(_Entry(article=article, category_key=key, category_label=label))
        entries.sort(key=lambda entry: (_normalize(entry.article["title"]), entry.article["knowledge_id"]))
        return cls(entries)

    @staticmethod
    def _summary(entry: _Entry) -> dict:
        return {
            "knowledge_id": entry.article["knowledge_id"],
            "title": entry.article["title"],
            "question": entry.article["question"],
            "system": entry.article["system"],
            "category": entry.category_label or "Outros",
        }

    def featured_groups(self) -> list[dict]:
        groups = []
        for key, label in _FEATURED_CATEGORY_ORDER[:MAX_FEATURED_CATEGORIES]:
            items = [
                self._summary(entry)
                for entry in self._entries
                if entry.category_key == key
            ][:MAX_FEATURED_PER_CATEGORY]
            if items:
                groups.append({"key": key, "label": label, "items": items})
        return groups

    def search(self, query: str) -> list[dict]:
        normalized = _normalize(query)
        tokens = normalized.split()
        scored = []
        for entry in self._entries:
            article = entry.article
            haystacks = {
                "title": _normalize(article["title"]),
                "question": _normalize(article["question"]),
                "system": _normalize(article["system"]),
                "category": _normalize(entry.category_label or "Outros"),
                "tags": _normalize(" ".join(article["tags"])),
            }
            score = 0
            for token in tokens:
                if token in haystacks["title"]:
                    score += 8
                if token in haystacks["question"]:
                    score += 5
                if token in haystacks["system"] or token in haystacks["category"]:
                    score += 3
                if token in haystacks["tags"]:
                    score += 2
            if not tokens or score:
                scored.append((score, _normalize(article["title"]), article["knowledge_id"], entry))
        scored.sort(key=lambda row: (-row[0], row[1], row[2]))
        return [self._summary(row[3]) for row in scored[:MAX_FAQ_RESULTS]]

    def detail(self, knowledge_id: str) -> dict:
        entry = self._by_id.get(knowledge_id)
        if entry is None:
            raise FaqNotFoundError("Solução não encontrada.")
        detail = self._summary(entry)
        detail["answer"] = entry.article["answer"]
        detail["procedure_url"] = (
            APPROVED_M365_PASSWORD_URL
            if knowledge_id == "KB-SYN-M365-PASSWORD-001"
            else None
        )
        return detail
```

Keep the catalog inside `ai_service_desk.web`; do not change the Fase 4 schema.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests/web/test_demo_faq.py -q
python -m ruff check src/ai_service_desk/web/demo_faq.py tests/web/test_demo_faq.py
python -m ruff format --check src/ai_service_desk/web/demo_faq.py tests/web/test_demo_faq.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_service_desk/web/demo_faq.py tests/web/test_demo_faq.py
git commit -m "feat: add approved FAQ catalog"
```

---

### Task 2: FAQ runtime and HTTP API

**Files:**
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `src/ai_service_desk/web/api.py`
- Create: `tests/web/test_faq_api.py`
- Modify: `tests/web/test_phase12_security.py`

**Interfaces:**
- Consumes: `DemoFaqCatalog.from_sources()`.
- Produces runtime methods `list_faq()`, `search_faq(query)`, `get_faq(knowledge_id)`.
- Produces HTTP `GET /api/faq`, `GET /api/faq/search?q=...`, `GET /api/faq/{knowledge_id}`.
- Endpoints do not require `X-Demo-Identity`.

- [ ] **Step 1: Write failing API tests**

Create `tests/web/test_faq_api.py`:

```python
from fastapi.testclient import TestClient

from ai_service_desk.web.api import create_app
from ai_service_desk.web.demo_runtime import DemoRuntime


def test_faq_is_public_and_approved_only():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["groups"]) <= 4
        assert all(len(group["items"]) <= 4 for group in payload["groups"])
        assert all("answer" not in item for group in payload["groups"] for item in group["items"])
    finally:
        runtime.close()


def test_faq_search_is_public_and_limited():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq/search", params={"q": "cigam"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == len(payload["items"])
        assert payload["total"] <= 16
    finally:
        runtime.close()


def test_faq_detail_returns_literal_answer_and_fixed_microsoft_url():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq/KB-SYN-M365-PASSWORD-001")
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"].startswith("Vamos redefinir sua senha do Microsoft 365.")
        assert payload["procedure_url"] == "https://mysignins.microsoft.com/security-info/password/change"
    finally:
        runtime.close()


def test_faq_unknown_id_is_404_without_internal_details():
    runtime = DemoRuntime.create()
    try:
        client = TestClient(create_app(runtime=runtime))
        response = client.get("/api/faq/KB-MISSING")
        assert response.status_code == 404
        payload = response.json()
        assert payload["error"]["code"] == "FAQ_NOT_FOUND"
        assert "traceback" not in response.text.casefold()
    finally:
        runtime.close()
```

Add a security assertion to `tests/web/test_phase12_security.py` that FAQ responses do not expose `reviewed_by`, `reviewed_at`, raw `source`, tokens, credentials, or arbitrary URLs.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests/web/test_faq_api.py tests/web/test_phase12_security.py -q
```

Expected: FAQ routes are 404 / methods absent.

- [ ] **Step 3: Wire catalog into DemoRuntime without changing conversational Knowledge**

In `DemoRuntime.reset()`:

```python
from ai_service_desk.web.demo_faq import DemoFaqCatalog, FaqNotFoundError
```

Immediately after `knowledge_source = write_demo_knowledge(root / "knowledge.jsonl")`, resolve the existing repository FAQ source:

```python
phase4_faq_source = Path(__file__).resolve().parents[3] / "knowledge" / "phase4_synthetic_faq.jsonl"
self.faq_catalog = DemoFaqCatalog.from_sources([phase4_faq_source, knowledge_source])
```

Do not feed `phase4_faq_source` into `build_knowledge_index()` for the conversation runtime. Keep the focused F12 index unchanged.

Add:

```python
def list_faq(self) -> dict:
    groups = self.faq_catalog.featured_groups()
    return {"groups": groups, "total": sum(len(group["items"]) for group in groups)}


def search_faq(self, query: str) -> dict:
    items = self.faq_catalog.search(query)
    return {"items": items, "total": len(items)}


def get_faq(self, knowledge_id: str) -> dict:
    try:
        return self.faq_catalog.detail(knowledge_id)
    except FaqNotFoundError as exc:
        raise WebDemoError("FAQ_NOT_FOUND", "Solução não encontrada.") from exc
```

- [ ] **Step 4: Add API routes and explicit 404 mapping**

In the existing `WebDemoError` handler, map:

```python
elif exc.code == "FAQ_NOT_FOUND":
    status = 404
```

Add routes before the static fallback:

```python
@app.get("/api/faq")
def faq():
    return app.state.runtime.list_faq()


@app.get("/api/faq/search")
def faq_search(q: str = ""):
    return app.state.runtime.search_faq(q)


@app.get("/api/faq/{knowledge_id}")
def faq_detail(knowledge_id: str):
    return app.state.runtime.get_faq(knowledge_id)
```

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests/web/test_demo_faq.py tests/web/test_faq_api.py tests/web/test_phase12_security.py -q
python -m ruff check src/ai_service_desk/web tests/web/test_demo_faq.py tests/web/test_faq_api.py
python -m ruff format --check src/ai_service_desk/web tests/web/test_demo_faq.py tests/web/test_faq_api.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_service_desk/web/demo_runtime.py src/ai_service_desk/web/api.py tests/web/test_faq_api.py tests/web/test_phase12_security.py
git commit -m "feat: expose approved FAQ API"
```

---

### Task 3: Public routes and route-controlled demo identity

**Files:**
- Modify: `web/src/router.mjs`
- Modify: `web/src/state.mjs`
- Modify: `web/src/app.mjs`
- Modify: `web/tests/router.test.mjs`
- Modify: `web/tests/state.test.mjs`
- Create: `web/tests/requester-experience.test.mjs`

**Interfaces:**
- Produces routes `solutions`, `solution`, `jup`, `requests`, `approvals`, `prevention`.
- Produces `routeParams(pathname)` for `knowledgeId`.
- Produces `demoIdentityForPath(pathname)` with fixed allowlisted demo IDs.
- Public routes use `pedro-miranda`; hidden operational routes use fixed technician IDs.

- [ ] **Step 1: Write failing route tests**

Update `web/tests/router.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { demoIdentityForPath, resolveRoute, routeParams, routePath } from '../src/router.mjs';

for (const [path, expected] of [
  ['/', 'solutions'],
  ['/jup', 'jup'],
  ['/solucoes/KB-SYN-CIGAM-ACCESS-001', 'solution'],
  ['/requests', 'requests'],
  ['/demo/operacao/cdm', 'approvals'],
  ['/demo/operacao/m365', 'approvals'],
  ['/demo/operacao/prevention', 'prevention'],
  ['/operations', 'approvals'],
  ['/operations/prevention', 'prevention'],
  ['/unknown', 'solutions'],
]) {
  test(`${path} resolves to ${expected}`, () => assert.equal(resolveRoute(path), expected));
}

test('solution route extracts a decoded knowledge id', () => {
  assert.deepEqual(routeParams('/solucoes/KB-SYN-CIGAM-ACCESS-001'), {
    knowledgeId: 'KB-SYN-CIGAM-ACCESS-001',
  });
});

test('public and operational paths resolve only fixed demo identities', () => {
  assert.equal(demoIdentityForPath('/'), 'pedro-miranda');
  assert.equal(demoIdentityForPath('/jup'), 'pedro-miranda');
  assert.equal(demoIdentityForPath('/demo/operacao/cdm'), 'tecnico-cdm');
  assert.equal(demoIdentityForPath('/demo/operacao/m365'), 'tecnico-m365');
  assert.equal(demoIdentityForPath('/demo/operacao/prevention'), 'tecnico-geral');
});

test('routePath builds a dedicated solution path', () => {
  assert.equal(
    routePath('solution', { knowledgeId: 'KB A/B' }),
    '/solucoes/KB%20A%2FB',
  );
});
```

Create a source-level invariant in `web/tests/requester-experience.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('../src/app.mjs', import.meta.url), 'utf8');

test('public identity is route controlled instead of a visible persisted selector', () => {
  assert.doesNotMatch(appSource, /jup-demo-identity/);
  assert.doesNotMatch(appSource, /#demo-identity/);
});
```

- [ ] **Step 2: Run RED**

```bash
npm --prefix web test
```

Expected: route tests fail because `/` still resolves to `jup` and route identity helpers do not exist.

- [ ] **Step 3: Implement router helpers**

`web/src/router.mjs` must use exact fixed paths; do not read identity from query params:

```js
const STATIC_ROUTES = new Map([
  ['/', 'solutions'],
  ['/jup', 'jup'],
  ['/requests', 'requests'],
  ['/demo/operacao/cdm', 'approvals'],
  ['/demo/operacao/m365', 'approvals'],
  ['/demo/operacao/prevention', 'prevention'],
  ['/operations', 'approvals'],
  ['/operations/prevention', 'prevention'],
]);

export function resolveRoute(pathname) {
  if (/^\/solucoes\/[^/]+$/.test(pathname)) return 'solution';
  return STATIC_ROUTES.get(pathname) ?? 'solutions';
}

export function routeParams(pathname) {
  const match = pathname.match(/^\/solucoes\/([^/]+)$/);
  return match ? { knowledgeId: decodeURIComponent(match[1]) } : {};
}

export function routePath(route, params = {}) {
  if (route === 'solutions') return '/';
  if (route === 'jup') return '/jup';
  if (route === 'requests') return '/requests';
  if (route === 'solution') return `/solucoes/${encodeURIComponent(params.knowledgeId)}`;
  if (route === 'prevention') return '/demo/operacao/prevention';
  return '/demo/operacao/cdm';
}

export function demoIdentityForPath(pathname) {
  if (pathname === '/demo/operacao/m365') return 'tecnico-m365';
  if (pathname === '/demo/operacao/prevention') return 'tecnico-geral';
  if (pathname === '/demo/operacao/cdm' || pathname === '/operations') return 'tecnico-cdm';
  if (pathname === '/operations/prevention') return 'tecnico-geral';
  return 'pedro-miranda';
}
```

- [ ] **Step 4: Refactor bootstrap identity selection**

In `app.mjs`, remove localStorage-driven public selection. Keep `/api/session/identities` only to validate the fixed route identity and retrieve safe display name/area.

At bootstrap and popstate:

```js
const desiredIdentityId = demoIdentityForPath(window.location.pathname);
const identity = identities.find((item) => item.identity_id === desiredIdentityId);
if (!identity) throw new Error('Identidade de demonstração esperada não está disponível.');
state.identityId = desiredIdentityId;
```

When navigating between public and operational routes, recompute the route identity before `loadRoute()`.

Do not add any query-string identity override.

- [ ] **Step 5: Run GREEN**

```bash
npm --prefix web test
npm --prefix web run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/router.mjs web/src/state.mjs web/src/app.mjs web/tests/router.test.mjs web/tests/state.test.mjs web/tests/requester-experience.test.mjs
git commit -m "refactor: focus public demo on requester routes"
```

---

### Task 4: Solutions home and dynamic FAQ search

**Files:**
- Create: `web/src/solutions.mjs`
- Modify: `web/src/app.mjs`
- Modify: `web/src/state.mjs`
- Create: `web/tests/solutions.test.mjs`
- Modify: `web/tests/requester-experience.test.mjs`

**Interfaces:**
- Produces `renderSolutionsHome({ groups, searchQuery, searchResults, searching })`.
- Produces `faqSearchPath(query)`.
- App loads `/api/faq` on `/` and debounces `/api/faq/search?q=...` by ~140 ms.

- [ ] **Step 1: Write failing renderer tests**

Create `web/tests/solutions.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { faqSearchPath, renderSolutionsHome } from '../src/solutions.mjs';

const groups = [
  {
    key: 'cigam',
    label: 'CIGAM',
    items: [
      {
        knowledge_id: 'KB-CIGAM',
        title: 'CIGAM não abre',
        question: 'Não consigo acessar o CIGAM.',
        system: 'CIGAM',
        category: 'CIGAM',
      },
    ],
  },
];

test('solutions home is task-first and does not contain marketing copy', () => {
  const html = renderSolutionsHome({ groups, searchQuery: '', searchResults: null, searching: false });
  assert.match(html, /Como podemos ajudar\?/);
  assert.match(html, /Pesquise por um problema, sistema ou dúvida/);
  assert.match(html, /CIGAM não abre/);
  assert.match(html, /Não encontrou o que precisa\?/);
  assert.match(html, /Falar com o Jup/);
  assert.doesNotMatch(html, /Assistente de IA|Inteligência para|transforme|revolucione/i);
});

test('solutions home renders result mode without category card grid', () => {
  const html = renderSolutionsHome({
    groups,
    searchQuery: 'cigam',
    searchResults: groups[0].items,
    searching: false,
  });
  assert.match(html, /1 solução encontrada/);
  assert.match(html, /data-knowledge-id="KB-CIGAM"/);
  assert.doesNotMatch(html, /dashboard-card|metric-card|feature-card/);
});

test('empty search result leads directly to Jup', () => {
  const html = renderSolutionsHome({
    groups,
    searchQuery: 'xyz',
    searchResults: [],
    searching: false,
  });
  assert.match(html, /Nenhuma solução encontrada/);
  assert.match(html, /href="\/jup"/);
});

test('faq search path encodes the query', () => {
  assert.equal(faqSearchPath('cigam azul'), '/api/faq/search?q=cigam%20azul');
});
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/solutions.test.mjs
```

Expected: module absent.

- [ ] **Step 3: Implement `solutions.mjs` with semantic lists**

Use `escapeHtml` for every backend field. Render category groups as `<section>` + `<ul>`/`<li>` lists, not cards.

`faqSearchPath()`:

```js
export function faqSearchPath(query) {
  return `/api/faq/search?q=${encodeURIComponent(String(query ?? '').trim())}`;
}
```

Every topic link must be built from the safe item identifier:

```js
const href = `/solucoes/${encodeURIComponent(item.knowledge_id)}`;
return `<a href="${href}" data-solution-link data-knowledge-id="${escapeHtml(item.knowledge_id)}">${escapeHtml(item.title)}</a>`;
```

No `innerHTML` interpolation of unescaped backend text.

- [ ] **Step 4: Wire `/` loading and debounce in `app.mjs`**

Extend state with:

```js
faqGroups: [],
faqSearchQuery: '',
faqSearchResults: null,
faqSearching: false,
faqSearchTimer: null,
```

On `solutions` route:

```js
const payload = await apiRequest('/api/faq');
state.faqGroups = payload.groups ?? [];
state.routeData = { loaded: true };
```

Bind `#faq-search` input. On each input:

1. update `state.faqSearchQuery`;
2. clear prior timeout;
3. if query is empty, set results `null` and render;
4. otherwise set `faqSearching=true` and schedule one request after `140` ms;
5. ignore stale responses by comparing the query captured at request time with current state.

No semantic ranking in JS; consume backend order.

- [ ] **Step 5: Run GREEN**

```bash
node --test web/tests/solutions.test.mjs web/tests/requester-experience.test.mjs
npm --prefix web test
npm --prefix web run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/solutions.mjs web/src/app.mjs web/src/state.mjs web/tests/solutions.test.mjs web/tests/requester-experience.test.mjs
git commit -m "feat: add requester solutions home"
```

---

### Task 5: Safe solution detail and FAQ-to-Jup transition

**Files:**
- Create: `web/src/knowledge_content.mjs`
- Modify: `web/src/solutions.mjs`
- Modify: `web/src/components.mjs`
- Modify: `web/src/app.mjs`
- Create: `web/tests/knowledge-content.test.mjs`
- Modify: `web/tests/solutions.test.mjs`
- Modify: `web/tests/task9-safe-ui.test.mjs`

**Interfaces:**
- Produces `renderApprovedKnowledgeBody({ text, procedureUrl })` reused by FAQ and Jup messages.
- Produces `renderSolutionDetail(detail)`.
- `/jup?from=<knowledge_id>` shows UI-only source context; POST `/api/jup/messages` remains unchanged in this phase.

- [ ] **Step 1: Write failing safe-content tests**

Create `web/tests/knowledge-content.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderApprovedKnowledgeBody } from '../src/knowledge_content.mjs';

const SAFE_URL = 'https://mysignins.microsoft.com/security-info/password/change';

test('approved numbered procedure keeps semantic ordered list and exact safe anchor', () => {
  const html = renderApprovedKnowledgeBody({
    text: 'Procedimento\n\n1. Acesse a página.\n2. Confirme sua identidade.\n\nDepois, teste novamente.',
    procedureUrl: SAFE_URL,
  });
  assert.match(html, /<ol class="procedure-steps">/);
  assert.match(html, new RegExp(`href="${SAFE_URL.replaceAll('/', '\\/')}"`));
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test('arbitrary URL is never promoted to an anchor', () => {
  const html = renderApprovedKnowledgeBody({
    text: '1. Acesse https://evil.example/test',
    procedureUrl: 'https://evil.example/test',
  });
  assert.doesNotMatch(html, /<a /);
  assert.match(html, /https:\/\/evil\.example\/test/);
});

test('knowledge body escapes active markup', () => {
  const html = renderApprovedKnowledgeBody({ text: '<img src=x onerror=alert(1)>', procedureUrl: null });
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});
```

Extend `solutions.test.mjs`:

```js
import { renderSolutionDetail } from '../src/solutions.mjs';

test('solution detail uses literal approved answer and two outcome actions', () => {
  const html = renderSolutionDetail({
    knowledge_id: 'KB-CIGAM',
    title: 'CIGAM não abre',
    answer: 'Feche a sessão e tente novamente.',
    system: 'CIGAM',
    category: 'CIGAM',
    procedure_url: null,
  });
  assert.match(html, /CIGAM não abre/);
  assert.match(html, /Feche a sessão e tente novamente\./);
  assert.match(html, /Resolveu\?/);
  assert.match(html, />Sim</);
  assert.match(html, /Ainda preciso de ajuda/);
  assert.match(html, /\/jup\?from=KB-CIGAM/);
});
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/knowledge-content.test.mjs web/tests/solutions.test.mjs
```

Expected: missing module/functions.

- [ ] **Step 3: Extract the existing Task 9 procedure renderer**

Move safe paragraph/numbered-step rendering out of `components.mjs` into `knowledge_content.mjs`.

Exact safe URL constant remains:

```js
export const APPROVED_PROCEDURE_URL = 'https://mysignins.microsoft.com/security-info/password/change';
```

The renderer may create an anchor only when:

```js
procedureUrl === APPROVED_PROCEDURE_URL
```

Keep the first numbered item as the linked step, preserving current Task 9 behavior and tests.

- [ ] **Step 4: Add solution detail route loading**

When `state.route === 'solution'`:

```js
const { knowledgeId } = routeParams(window.location.pathname);
const detail = await apiRequest(`/api/faq/${encodeURIComponent(knowledgeId)}`);
state.routeData = { loaded: true, detail };
```

`renderSolutionDetail()` must render:

- back link `/`;
- category/system label;
- title;
- literal approved answer through `renderApprovedKnowledgeBody`;
- `Sim` link/button that returns to `/` without claiming persistence;
- `Ainda preciso de ajuda` link `/jup?from=<knowledge_id>`.

- [ ] **Step 5: Add UI-only FAQ context on `/jup?from=`**

On Jup route load, parse only the `from` parameter:

```js
const sourceId = new URLSearchParams(window.location.search).get('from');
```

If present, fetch `/api/faq/{id}` and store only safe summary fields under `state.faqContext`.

Pass `sourceContext: state.faqContext` in the existing `renderJupWorkspace()` argument object. The component must render the literal prefix `Você estava vendo:` followed by `escapeHtml(sourceContext.title)`.

Do not prepend text to the user's message. Do not change `/api/jup/messages`. Do not seed triage automatically in this phase.

- [ ] **Step 6: Run GREEN and preserve Task 9 security**

```bash
node --test web/tests/knowledge-content.test.mjs web/tests/solutions.test.mjs web/tests/task9-safe-ui.test.mjs
npm --prefix web test
npm --prefix web run lint
python -m pytest tests/web/test_phase12_security.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/knowledge_content.mjs web/src/solutions.mjs web/src/components.mjs web/src/app.mjs web/tests/knowledge-content.test.mjs web/tests/solutions.test.mjs web/tests/task9-safe-ui.test.mjs
git commit -m "feat: add safe FAQ detail flow"
```

---

### Task 6: Rebuild public header and dedicated Jup chat

**Files:**
- Modify: `web/src/components.mjs`
- Modify: `web/src/render.mjs`
- Modify: `web/src/app.mjs`
- Modify: `web/tests/render.test.mjs`
- Modify: `web/tests/requester-experience.test.mjs`
- Modify: `web/tests/conversation.test.mjs`

**Interfaces:**
- Produces `renderPublicHeader(activeRoute)` and an operational header isolated from public navigation.
- `renderJupWorkspace()` no longer renders a permanent right-side “O que entendi” panel.
- Existing approved procedure and safe handoff output remain intact.

- [ ] **Step 1: Write failing public-shell tests**

Add to `requester-experience.test.mjs`:

```js
import { renderAppHeader, renderJupWorkspace } from '../src/components.mjs';

test('public header contains only requester navigation', () => {
  const html = renderAppHeader({ activeRoute: 'solutions', operational: false });
  assert.match(html, /Jup Resolve/);
  assert.match(html, />Soluções</);
  assert.match(html, />Falar com o Jup</);
  assert.doesNotMatch(html, /Identidade demo|Operação|Prevenção|Assistente de IA|Inteligência para/i);
  assert.doesNotMatch(html, /<select/);
});

test('empty Jup workspace is concise and task-first', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [],
    understood: null,
    loading: false,
    sourceContext: null,
  });
  assert.match(html, /Como posso ajudar\?/);
  assert.match(html, /Descreva o que aconteceu/);
  assert.doesNotMatch(html, /Eu organizo o contexto|O que entendi|Contexto estruturado/i);
});

test('structured request context is compact instead of a permanent side panel', () => {
  const html = renderJupWorkspace({
    identity: { name: 'Pedro Miranda' },
    messages: [{ role: 'USER', text: 'Preciso de acesso ao CDM.' }],
    understood: { system: 'CDM', request: 'SOLICITANTE', next_step: 'Aguardando aprovação' },
    loading: false,
    sourceContext: null,
  });
  assert.match(html, /CDM/);
  assert.match(html, /Aguardando aprovação/);
  assert.doesNotMatch(html, /understood-panel/);
  assert.doesNotMatch(html, /Policy|Confiança/);
});
```

- [ ] **Step 2: Run RED**

```bash
node --test web/tests/requester-experience.test.mjs web/tests/conversation.test.mjs
```

Expected: current header and workspace violate the new contract.

- [ ] **Step 3: Split public and operational header behavior**

`renderAppHeader()` accepts:

```js
{
  activeRoute,
  operational = false,
}
```

Public mode must render this structure, with `aria-current="page"` added only to the active link:

```html
<header class="app-header app-header--public">
  <a class="brand-lockup" href="/" data-route="solutions">Jup Resolve</a>
  <nav class="primary-nav" aria-label="Navegação principal">
    <a href="/" data-route="solutions">Soluções</a>
    <a href="/jup" data-route="jup">Falar com o Jup</a>
  </nav>
</header>
```

Operational mode may show `Operação` / `Prevenção`, but never an identity selector.

`app.mjs` determines `operational` from route `approvals`/`prevention`.

- [ ] **Step 4: Redesign Jup workspace structure without changing message submission**

Keep:

```text
message POST
assistant_message
procedure_url
support_handoff
request detail lookup
```

Remove the permanent right panel.

If `understood` exists, project only safe compact values already obtained from backend, e.g. system + next_step. Do not show `policy`, raw confidence or internal IDs in public chat.

Empty state copy exactly:

```text
Como posso ajudar?
Descreva o que aconteceu...
```

Do not add explanatory paragraph.

- [ ] **Step 5: Run GREEN**

```bash
node --test web/tests/requester-experience.test.mjs web/tests/conversation.test.mjs web/tests/render.test.mjs web/tests/task9-safe-ui.test.mjs
npm --prefix web test
npm --prefix web run lint
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/components.mjs web/src/render.mjs web/src/app.mjs web/tests/render.test.mjs web/tests/requester-experience.test.mjs web/tests/conversation.test.mjs
git commit -m "refactor: make Jup a dedicated requester conversation"
```

---

### Task 7: Integrate the provided Jup visual states and purposeful motion

**Files:**
- Create: `web/src/jup_visual.mjs`
- Create: `web/src/jup_visual_assets.mjs`
- Create: `web/src/assets/jup/*` from the user-provided package only
- Modify: `web/src/components.mjs`
- Modify: `web/src/app.mjs`
- Create: `web/tests/jup-visual.test.mjs`

**Interfaces:**
- Produces visual states `idle`, `listening`, `thinking`, `success`, `warning`, `escalation`.
- Produces `visualStateFromUi({ pending, backendStatus, focused })`.
- Produces `renderJupVisual({ state, compact })`.
- No business decision is made by these functions.

- [ ] **Step 1: Verify the required asset package before editing visual files**

Locate the user-provided refined Jup avatar package.

Required states in that package:

```text
idle
listening
thinking
success
warning
escalation
```

Required visual rule:

```text
warning has no face; it is an interface/emote error state
```

If the package is absent, do not create `jup_visual_assets.mjs`, do not invent replacement assets and stop this Task with an explicit dependency report. Continue only after the asset is provided.

- [ ] **Step 2: Write failing state-mapping tests**

Create `web/tests/jup-visual.test.mjs`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { visualStateFromUi } from '../src/jup_visual.mjs';

test('pending request always renders thinking', () => {
  assert.equal(visualStateFromUi({ pending: true, backendStatus: null, focused: true }), 'thinking');
});

test('backend outcome maps only to presentation states', () => {
  assert.equal(visualStateFromUi({ pending: false, backendStatus: 'SUPPORT_RESOLVED', focused: false }), 'success');
  assert.equal(visualStateFromUi({ pending: false, backendStatus: 'DENIED_POLICY', focused: false }), 'warning');
  assert.equal(visualStateFromUi({ pending: false, backendStatus: 'SUPPORT_HANDOFF_PENDING', focused: false }), 'escalation');
});

test('focused composer uses listening only when no stronger backend state is active', () => {
  assert.equal(visualStateFromUi({ pending: false, backendStatus: null, focused: true }), 'listening');
  assert.equal(visualStateFromUi({ pending: false, backendStatus: null, focused: false }), 'idle');
});
```

- [ ] **Step 3: Run RED**

```bash
node --test web/tests/jup-visual.test.mjs
```

Expected: module absent.

- [ ] **Step 4: Normalize the provided asset package locally**

Copy only the six approved state assets and their necessary local CSS/JS primitives into `web/src/assets/jup/`.

Rules:

- no network dependency;
- no downloaded substitute;
- no font file copied into repo unless it already belongs to the provided licensed package and repository policy allows it;
- preserve source attribution/provenance in development docs if the package carries it;
- `jup_visual_assets.mjs` is the only module that knows actual asset paths.

`jup_visual_assets.mjs` must export `JUP_ASSETS` as a frozen object with exactly the keys `idle`, `listening`, `thinking`, `success`, `warning`, and `escalation`. Each value must be the real local reference produced from the corresponding user-provided state asset during this step. The exact file extension and import form are dictated by that supplied package and must not be guessed before inspection. Do not translate the package into generic emoji or a new avatar.

- [ ] **Step 5: Implement pure visual mapping**

`jup_visual.mjs` must contain no API calls and no domain logic.

Mapping:

```js
const STATUS_TO_VISUAL = Object.freeze({
  SUPPORT_RESOLVED: 'success',
  KNOWLEDGE_FOUND: 'success',
  DENIED_POLICY: 'warning',
  LOCAL_AI_INFERENCE_FAILED: 'warning',
  LOCAL_AI_RESPONSE_INVALID: 'warning',
  SUPPORT_HANDOFF_PENDING: 'escalation',
});

export function visualStateFromUi({ pending = false, backendStatus = null, focused = false } = {}) {
  if (pending) return 'thinking';
  if (backendStatus && STATUS_TO_VISUAL[backendStatus]) return STATUS_TO_VISUAL[backendStatus];
  return focused ? 'listening' : 'idle';
}
```

Store `result.status` from `/api/jup/messages` in UI state as `lastBackendStatus`; do not reinterpret it as domain truth.

- [ ] **Step 6: Integrate composer focus and result status**

Add state:

```js
composerFocused: false,
lastBackendStatus: null,
```

Rules:

- `focus` -> `composerFocused=true`;
- `blur` -> `composerFocused=false`;
- pending message -> thinking;
- response status -> mapped state;
- starting a new user message clears stale success/warning/escalation before pending thinking begins.

- [ ] **Step 7: Run GREEN**

```bash
node --test web/tests/jup-visual.test.mjs web/tests/requester-experience.test.mjs
npm --prefix web test
npm --prefix web run lint
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/src/jup_visual.mjs web/src/jup_visual_assets.mjs web/src/assets/jup web/src/components.mjs web/src/app.mjs web/tests/jup-visual.test.mjs
git commit -m "feat: integrate Jup visual states"
```

---

### Task 8: Replace the generic SaaS visual world with the Juparanã desktop system

**Files:**
- Modify: `web/src/styles.css`
- Modify: `web/scripts/lint.mjs`
- Modify: `web/tests/requester-experience.test.mjs`

**Interfaces:**
- Produces the final desktop visual system for `/`, `/solucoes/<id>`, `/jup`.
- Keeps operational routes usable but visually secondary.

- [ ] **Step 1: Add failing design invariant tests**

Extend `web/tests/requester-experience.test.mjs`:

```js
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../src/styles.css', import.meta.url), 'utf8');
const componentsSource = readFileSync(new URL('../src/components.mjs', import.meta.url), 'utf8');

test('Juparana brand tokens are exact', () => {
  assert.match(css, /--brand-green:\s*#45813c/i);
  assert.match(css, /--brand-yellow:\s*#eeb41e/i);
  assert.match(css, /--brand-gray:\s*#808285/i);
});

test('public visual system rejects generic AI chrome', () => {
  assert.doesNotMatch(css, /linear-gradient|radial-gradient|backdrop-filter/i);
  assert.doesNotMatch(componentsSource, /Assistente de IA da Juparanã|Inteligência para o Service Desk/i);
  assert.doesNotMatch(componentsSource, /identity-switcher|demo-identity/);
});
```

- [ ] **Step 2: Run RED if current source still violates the contract**

```bash
node --test web/tests/requester-experience.test.mjs
```

Expected: at least old self-marketing/identity selectors or visual tokens/structure fail until refactor is complete.

- [ ] **Step 3: Rewrite the public CSS system, not just colors**

Keep exact tokens:

```css
:root {
  --brand-green: #45813c;
  --brand-yellow: #eeb41e;
  --brand-gray: #808285;
  --white: #ffffff;
  --ink: #20241f;
  --ink-muted: #626762;
  --line: #d8ddd6;
  --surface-soft: #f5f7f4;
  --focus: #1849a9;
  --content: 1220px;
}
```

Desktop composition requirements:

```text
header ~68–72px
content 1180–1240px
home title functional, not giant
search wide and dominant
FAQ categories as editorial columns/lists
no floating card grid
no repeated box shadows
small/medium radii only
full-width green Jup strip near lower home content
chat central column ~760–860px
composer clear and restrained
solution article readable at ~760–820px
```

Do not add mobile media queries as part of this phase. Existing irrelevant mobile rules may be removed if they conflict with the redesign, but no mobile QA is required.

- [ ] **Step 4: Implement restrained motion**

Use CSS transitions approximately:

```text
150–250ms controls/navigation
300–450ms Jup state transition
```

Add:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
```

No page entrance choreography.

- [ ] **Step 5: Strengthen frontend lint against accidental external/generic UI**

Keep the current exact Microsoft allowlist behavior. Add static bans only where unambiguous:

```text
backdrop-filter
linear-gradient(
radial-gradient(
```

Do not ban legitimate `box-shadow` globally; use it sparingly through review instead.

- [ ] **Step 6: Run GREEN**

```bash
npm --prefix web test
npm --prefix web run lint
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/styles.css web/scripts/lint.mjs web/tests/requester-experience.test.mjs
git commit -m "style: establish Juparana requester experience"
```

---

### Task 9: Preserve hidden operations, update docs, and run final verification

**Files:**
- Modify: `docs/environment/web-demo.md`
- Create: `docs/demo/phase-13-requester-experience.md`
- Modify only if required by regression: `web/src/app.mjs`, `web/src/components.mjs`, tests directly related to a demonstrated failure.

**Interfaces:**
- Public demo routes documented.
- Hidden technical routes documented for presenter use.
- No merge or push.

- [ ] **Step 1: Update demo docs with exact routes**

Document:

```text
/                                Soluções / FAQ
/jup                             Chat Jup
/solucoes/<knowledge_id>         Solução aprovada
/requests                        Deep link de solicitações
/demo/operacao/cdm               Técnico CDM
/demo/operacao/m365              Técnico Microsoft 365
/demo/operacao/prevention        Prevenção
```

Explain that no auth real exists by design; route identity is demo-only and backend allowlisted.

Do not add product marketing copy.

- [ ] **Step 2: Run targeted functional regression first**

```bash
python -m pytest \
  tests/web/test_focused_demo_contract.py \
  tests/web/test_demo_support_handoff.py \
  tests/web/test_phase12_security.py \
  tests/web/test_demo_faq.py \
  tests/web/test_faq_api.py \
  -q

npm --prefix web test
npm --prefix web run lint
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 3: Verify the six focused demo behaviors manually/local smoke**

Using `LOCAL_AI` presentation mode when available, verify:

```text
1. M365 access/password -> 7-step approved procedure + correct Microsoft URL
2. "funcionou" -> resolved
3. "não funcionou" -> Microsoft 365 specialist handoff
4. normal CDM access -> PENDING_APPROVAL
5. admin/administrator CDM -> DENY without executable request
6. out-of-scope -> deterministic IT redirect
```

The redesign must not change these outcomes.

- [ ] **Step 4: Run full Python quality gates**

```bash
python --version
python -m ruff --version
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Expected:

- no failures;
- historical tests preserved;
- existing skips remain explainable.

- [ ] **Step 5: Verify historical node IDs and protected files**

```bash
python artifacts/focused-demo/check_frozen.py
```

Expected: all `925` historical node IDs present, zero missing.

Then:

```bash
git diff --exit-code 96d88ed58df5e2d007aedd8cbed2f2c779750e05 -- \
  src/ai_service_desk/engine/access_request.py \
  src/ai_service_desk/engine/policy.py \
  src/ai_service_desk/engine/request_lifecycle.py \
  src/ai_service_desk/engine/request_repository.py \
  src/ai_service_desk/engine/approval.py \
  src/ai_service_desk/engine/execution.py \
  src/ai_service_desk/engine/cdm_execution.py \
  src/ai_service_desk/integrations/cdm.py \
  src/ai_service_desk/integrations/cdm_fake_api.py
```

Expected: no diff.

- [ ] **Step 6: Run existing smokes**

```bash
python -m ai_service_desk routing-smoke
python -m ai_service_desk learning-prevention-smoke
python -m ai_service_desk web-demo-smoke
```

Expected: PASS.

- [ ] **Step 7: Perform bounded Impeccable desktop review**

Run the app and inspect exactly these surfaces:

```text
/                               1440x900 primary
/                               1280 wide
/                               1600 wide
/solucoes/<approved-id>         1440x900
/jup                            1440x900 empty
/jup                            1440x900 conversation with procedure
/jup                            1440x900 handoff
```

Review against the approved direction:

```text
no identity selector
no operation/prevention public nav
no SaaS card wall
no gradient/glow/glass
search dominates home task
4-column editorial structure when data supports it
Jup strip feels branded, not promotional
chat is focused and uncluttered
procedure is readable
handoff is safe and visually integrated
Juparana colors are exact
motion is subtle
```

Use at most one batched fix pass and one confirmation pass. Desktop-only overrides mobile review for this phase.

- [ ] **Step 8: Run diff hygiene and candidate status**

```bash
git diff --check
git status --short
git log --oneline --decorate -10
```

Expected: no unrelated/untracked artifact staged. The recovery ZIP from the user's local Phase 12 workspace must never be committed if present.

- [ ] **Step 9: Commit docs/final bounded fixes**

If Task 9 changed only docs:

```bash
git add docs/environment/web-demo.md docs/demo/phase-13-requester-experience.md
git commit -m "docs: add requester demo flow"
```

If the bounded visual review required code fixes, stage only the exact files changed by that review plus their tests and use:

```bash
git commit -m "fix: finish requester experience review"
```

- [ ] **Step 10: Stop before push**

Report:

```text
branch
HEAD SHA
full pytest result
frontend test/lint/build result
925 historical node preservation result
protected-file diff result
three smoke results
visual review surfaces checked
working tree status
```

Do not push until the user authorizes it.

---

## Self-Review Checklist for the Executor

Before claiming implementation complete, confirm every row:

```text
[ ] / is FAQ, not chat
[ ] /jup is dedicated chat
[ ] public header has only Soluções and Falar com o Jup
[ ] identity selector is absent from public UI
[ ] operation/prevention are hidden from public nav
[ ] FAQ API is APPROVED-only
[ ] DRAFT/RETIRED excluded by test
[ ] raw historical corpus never becomes answer text
[ ] dynamic search is deterministic and <=16
[ ] featured categories <=4 and <=4 items each
[ ] literal answers are escaped
[ ] M365 URL is exact and allowlisted
[ ] arbitrary URLs are plain text
[ ] FAQ detail is a page, not modal
[ ] Ainda preciso de ajuda routes to Jup
[ ] FAQ source context is UI-only in this phase
[ ] permanent “O que entendi” side panel is gone
[ ] six F12 behavior scenarios unchanged
[ ] Jup asset comes only from user-provided package
[ ] warning state has no face
[ ] Juparana colors exact
[ ] no gradient/glow/glass/card-wall aesthetic
[ ] desktop 1280/1440/1600 inspected
[ ] no mobile scope added
[ ] core protected files unchanged
[ ] full tests/gates pass
[ ] no push/merge performed
```

## Execution Handoff

Recommended implementation mode:

```text
superpowers:subagent-driven-development
```

Use one fresh subagent per Task with review between Tasks. If Codex cannot dispatch subagents, use `superpowers:executing-plans` inline with checkpoints after Tasks 2, 5, 8 and 9.
