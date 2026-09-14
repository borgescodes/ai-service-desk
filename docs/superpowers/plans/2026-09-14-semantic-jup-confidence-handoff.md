# Semantic Jup and Explainable Confidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Jup understand natural paraphrases with local Qwen, retrieve approved knowledge semantically, always hand unresolved IT cases to a human, and show technicians an explainable confidence assessment with trusted requester context.

**Architecture:** `qwen3.5:4b` interprets language into a narrow structured contract; the backend validates trusted identity, system, requested role, confidence, policy, routing and execution. `qwen3-embedding:0.6b` powers LOCAL_AI knowledge retrieval while deterministic mode keeps the synthetic embedder for reproducible CI. Human handoff is the fail-closed continuation when approved knowledge is unavailable.

**Tech Stack:** Python 3.14, FastAPI, Ollama localhost, NumPy knowledge index, vanilla ES modules frontend, pytest, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-14-semantic-jup-confidence-handoff-design.md`

## Global Constraints

- `LLM entende e conversa. Backend decide e executa.`
- Trusted identity is backend supplied and user text can never overwrite it.
- Only `APPROVED` knowledge may produce official procedure.
- CDM remains the only external automatic integration.
- Missing approved knowledge must continue to human support instead of dead-ending.
- `Nova conversa` resets only conversational state; `/api/demo/reset` remains full-demo reset.
- No force push, merge, Ready-for-Review, branch deletion or destructive reset.
- No hosted-CI polling before the user says exactly `checks acabaram`.

---

### Task 1: Trusted demo persona and privileged-language normalization

**Files:**
- Modify: `src/ai_service_desk/web/demo_identity.py`
- Modify: `src/ai_service_desk/engine/access_request.py`
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Test: `tests/web/test_demo_identity.py` or nearest existing identity test
- Test: `tests/engine/test_access_request.py`
- Test: `tests/web/test_demo_local_ai.py`

**Interfaces:**
- Consumes: existing `DemoIdentityProvider`, `normalize_requested_role`, `_canonicalize_access_request_language`.
- Produces: requester `Fulano de Tal / fulano.tal / fulano.tal@juparana.com.br / Revenda - Matriz`; backend normalization of `adm`, `administrativo`, `administrador`, `administradora`, `superadmin` into privileged CDM roles before policy evaluation.

- [ ] **Step 1: Write failing tests** proving the new requester identity and that `adm`/`administrativo` CDM requests cannot become `SOLICITANTE` pending approval.
- [ ] **Step 2: Run focused tests** and verify failures come from old persona / unresolved role normalization.
- [ ] **Step 3: Implement minimal identity and normalization changes** without changing policy decisions.
- [ ] **Step 4: Run focused tests** and existing CDM access tests.
- [ ] **Step 5: Commit** with a bounded message.

---

### Task 2: Three-level explainable confidence

**Files:**
- Modify: `src/ai_service_desk/engine/confidence.py`
- Modify: `src/ai_service_desk/engine/request_lifecycle.py`
- Modify: `src/ai_service_desk/web/presentation.py`
- Test: `tests/engine/test_confidence.py`
- Test: `tests/engine/test_request_lifecycle.py`
- Test: `tests/web/test_presentation.py`

**Interfaces:**
- Consumes: trusted requester area, request system, purpose, requested role.
- Produces: `ConfidenceAssessment.level` in `HIGH | MEDIUM | LOW`; stable `reason_codes`; presentation field `confidence.explanations` containing human-readable evidence derived only from backend reason codes.

- [ ] **Step 1: Write failing tests** for HIGH CDM+Revenda+materials, MEDIUM generic CDM access, LOW incoherent context, and presentation explanations.
- [ ] **Step 2: Run focused tests** and verify the current HIGH/LOW-only contract fails as expected.
- [ ] **Step 3: Implement the three-level assessment** and request invariant update.
- [ ] **Step 4: Remove decorative confidence percentage** unless backed by a domain value; expose explanations instead.
- [ ] **Step 5: Run confidence/lifecycle/presentation suites and commit.**

---

### Task 3: Semantic LOCAL_AI interpretation and M365 conversational continuity

**Files:**
- Modify: `src/ai_service_desk/web/demo_ai.py`
- Modify: `src/ai_service_desk/web/demo_support.py`
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Test: `tests/web/test_demo_local_ai.py`
- Test: `tests/web/test_business_context_runtime.py`
- Test: `tests/web/test_m365_support_dialogue.py` or nearest existing support-state test

**Interfaces:**
- Consumes: one compact Qwen interpretation per operational turn.
- Produces: structured scenario/signal sufficient to distinguish access, privileged access, password/login, installation, performance/error, procedure success/failure and other IT. Runtime supplies interpreted signal to `DemoSupportState.handle()`.

- [ ] **Step 1: Write failing tests** for `deu errado`, `não rolou`, `continua sem entrar`, `Esqueci minha senha do Office`, and natural privileged CDM variants.
- [ ] **Step 2: Run deterministic RED tests** with controlled model payloads.
- [ ] **Step 3: Extend compact schema/prompt minimally** while preserving backend validation and compact payload bounds.
- [ ] **Step 4: Wire interpreted signal into M365 state handling** so post-guidance failure/success is semantic, not regex-only.
- [ ] **Step 5: Run deterministic support and LOCAL_AI-contract suites and commit.**

---

### Task 4: Real semantic knowledge retrieval in LOCAL_AI

**Files:**
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify if needed: `src/ai_service_desk/web/demo_knowledge.py`
- Reuse: `src/ai_service_desk/engine/ollama.py::LocalEmbedder`
- Test: `tests/web/test_demo_local_ai.py`
- Test: `tests/web/test_business_context_runtime.py`

**Interfaces:**
- Deterministic mode: continue using `DemoEmbedder`.
- LOCAL_AI mode: instantiate `LocalEmbedder(client, model="qwen3-embedding:0.6b")`, build the temporary approved-knowledge index with its model/digest, and use the same embedder for queries.

- [ ] **Step 1: Write failing tests** around runtime dependency selection so LOCAL_AI selects `LocalEmbedder` while deterministic mode stays synthetic.
- [ ] **Step 2: Run deterministic RED** without requiring Ollama.
- [ ] **Step 3: Implement mode-specific embedder selection and startup model validation.**
- [ ] **Step 4: Preserve evidence gates and APPROVED provenance checks.**
- [ ] **Step 5: Run deterministic tests, then opt-in real-Qwen/real-embedding cases locally and commit.**

---

### Task 5: Mandatory general handoff and UBS low-confidence case

**Files:**
- Modify: `src/ai_service_desk/web/business_context.py`
- Modify: `src/ai_service_desk/web/demo_identity.py`
- Modify: `src/ai_service_desk/web/demo_support.py`
- Modify: `src/ai_service_desk/web/demo_runtime.py`
- Modify: `src/ai_service_desk/web/conversation.py`
- Test: `tests/web/test_business_context_runtime.py`
- Test: `tests/web/test_conversation_reset.py`
- Test: add/focus general handoff coverage under `tests/web/`

**Interfaces:**
- Produces: internal `GENERAL_IT_SUPPORT` handoff assigned to `tecnico-geral`; no external execution.
- UBS is recognized as user-requested access context only, not an automatic integration.
- Handoff payload includes requester, original message/context, interpreted system/intent, confidence with explanations, reason for handoff, and source conversation.

- [ ] **Step 1: Write failing tests** for `meu pc ta travando muito`, `Preciso de acesso ao UBS`, and `Preciso cadastrar um material para revenda` not becoming CDM access.
- [ ] **Step 2: Verify RED** shows current dead-end abstention / missing general routing.
- [ ] **Step 3: Add `GENERAL_IT_SUPPORT` technician capability and routing/handoff materialization.**
- [ ] **Step 4: Make unresolved IT abstention continue to technician general after at most one useful clarification.**
- [ ] **Step 5: Add UBS LOW confidence reasons and ensure no external action path exists.**
- [ ] **Step 6: Run runtime/handoff/reset tests and commit.**

---

### Task 6: Technician-facing explainability UI

**Files:**
- Modify: `src/ai_service_desk/web/presentation.py`
- Modify: `web/src/tracking.mjs`
- Modify: `web/src/components.mjs` if handoff cards share technician detail components
- Modify: `web/src/desktop-responsive.css`
- Test: `web/tests/showcase.test.mjs`
- Test: `web/tests/presentation.test.mjs`
- Test: backend presentation tests

**Interfaces:**
- Consumes: trusted requester email/area, requested role, purpose, confidence label/explanations, policy decision/reason, routing, execution state.
- Produces: technician detail sections `Solicitante`, `Pedido`, `Análise do Jup`, `Por que essa confiança?`, `Decisão do backend`; machine codes remain collapsed under technical details.

- [ ] **Step 1: Write failing Node/backend presentation tests** for Fulano identity/email, confidence explanations and separation between confidence vs policy.
- [ ] **Step 2: Run focused RED.**
- [ ] **Step 3: Extend presentation payload with requester email and explainability fields.**
- [ ] **Step 4: Render business-first technician detail without inventing values client-side.**
- [ ] **Step 5: Run Node tests, frontend lint/build, backend presentation tests and commit.**

---

### Task 7: Real-model acceptance and full regression

**Files:**
- Modify tests only as needed to add opt-in acceptance cases; do not weaken existing assertions.
- Update operator docs only if runtime prerequisites/behavior changed.

**Interfaces:**
- Acceptance candidate must preserve all prior security and frontend contracts.

- [ ] **Step 1: Run full deterministic Python suite and Ruff.**
- [ ] **Step 2: Run full Node suite, frontend lint/build and `git diff --check`.**
- [ ] **Step 3: Run opt-in `qwen3.5:4b` natural-language cases plus `qwen3-embedding:0.6b` retrieval.**
- [ ] **Step 4: Manually verify M365 paraphrases, privileged CDM variants, general-IT handoff, UBS LOW confidence, explainability screen and Nova conversa.**
- [ ] **Step 5: Verify exact HEAD and clean working tree.**
- [ ] **Step 6: Only after the user says exactly `checks acabaram`, inspect the workflow result for that exact candidate once.**

## Self-review

- Spec coverage: persona, semantic interpretation, semantic retrieval, privileged roles, mandatory handoff, UBS, three confidence levels, technician explainability, reset semantics and security invariants are each mapped to a task.
- No placeholders or deferred implementation items remain.
- `GENERAL_IT_SUPPORT`, `ConfidenceAssessment`, `confidence.explanations` and LocalEmbedder responsibilities are named consistently across tasks.
