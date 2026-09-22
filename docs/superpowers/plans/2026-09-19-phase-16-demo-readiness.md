# Phase 16 - Demo Readiness Implementation Plan

## Goal

Implement the approved Demo Readiness design without expanding the product into a complete Service Desk.

Canonical design:

`docs/superpowers/specs/2026-09-19-phase-16-demo-readiness-design.md`

Model policy:

`AGENTS.md`

Branch:

`phase-16-demo-readiness`

Baseline:

`142b6689f7b3aef743f1969ff87543d2f52d9183`

The phase uses one branch and task-level commits. Changing model does not create a new branch.

## Global constraints

Preserve:

- LLM understands and converses;
- backend decides and executes;
- trusted session authority;
- protected approved knowledge;
- existing policy and approval boundaries;
- CDM as the only automated external integration concept;
- requester ownership of requests;
- no chain-of-thought exposure;
- no unnecessary backend terminology in requester-facing copy.

Out of the priority gate:

- real CDM production integration;
- latency optimization;
- complete IT coverage;
- corporate authentication;
- conversation persistence after application restart.

---

## Task 1 - Configurable demo identity and contextual greeting

### Goal

Replace the single fixed requester presentation with a demo-only configurable trusted identity while preserving backend authority.

Support:

- name;
- corporate email;
- job title;
- arbitrary area text.

Use the first name naturally when a new conversation starts.

### Reuse

- `DemoIdentityProvider`;
- `SessionIdentity`;
- existing `/api/session/identities`;
- current route identity validation;
- existing New Conversation behavior.

### Create/extend

- safe demo identity configuration path;
- backend-owned resolved requester identity;
- UI control for editing the demo requester;
- greeting derived from the current trusted identity;
- tests proving conversation text cannot mutate trusted identity.

### Model routing

**Primary model:** GPT-5.6 Sol  
**Starting effort:** Medium

Why:

- spans backend identity, frontend state, conversation context and security tests;
- architecture is already known;
- no need for Astra unless authority becomes ambiguous.

### Escalate to Astra Medium if

- configured identities conflict with current authority precedence;
- identity switching requires redesigning the conversation context model;
- security tests reveal an architectural rather than local problem.

### Acceptance

- two different synthetic users can be configured without code edits;
- area accepts arbitrary valid text;
- Jup greets a new conversation with first name once;
- user text cannot override the trusted session identity.

---

## Task 2 - CDM scope catalog, automatic matching and mismatch handling

### Goal

Separate requester area from CDM business scopes and make CDM access requests context-aware.

Required cases:

1. trusted area matches a CDM scope;
2. trusted area has no known CDM match;
3. user explicitly requests a different CDM scope.

### Reuse

- access request domain;
- policy;
- CDM adapter boundary;
- current fake CDM integration;
- conversation context authority;
- existing technician presentation payload.

### Create/extend

- CDM scope catalog abstraction;
- area-to-scope resolution;
- explicit mismatch representation;
- confirmation behavior;
- technician-visible mismatch context;
- tests for arbitrary areas and future catalog extension.

### Model routing

**Primary model:** GPT-6 Astra  
**Starting effort:** Low

Why:

- authority, business semantics and future adapter design intersect;
- an incorrect abstraction could hardcode demo behavior into the core;
- Astra Low should be sufficient because the product rules are now explicit.

### Escalate effort

- Medium if the existing policy/request schemas require a non-trivial compatibility design;
- High only if safe migration cannot be resolved with Medium.

### Acceptance

- UBS requester asking generic CDM access resolves to UBS;
- arbitrary unmatched area does not invent a scope;
- Revenda requester explicitly asking UBS is recognized as a mismatch;
- mismatch is visible to the technician;
- production authority remains deterministic.

---

## Task 3 - CDM conversational experience

### Goal

Make informational CDM questions and action requests flow naturally across turns.

Example:

```text
User: Como consigo acesso ao CDM?
Jup: short explanation + approved article + offer to request
User: Pode solicitar para mim.
Jup: continues using trusted identity/context
```

### Reuse

- approved CDM FAQ;
- conversational core;
- context reducer;
- request creation;
- grounding;
- existing official CDM URL allowlist.

### Model routing

**Primary model:** GPT-5.6 Sol  
**Starting effort:** Medium

Why:

- cross-turn behavior is already supported;
- task is a bounded extension of an existing architecture.

### Escalate to Astra Low/Medium if

- informational and execution intents cannot be separated without weakening current authority;
- conversation continuity produces ambiguous request execution.

### Acceptance

- informational question does not prematurely create request;
- follow-up can create request without re-asking known identity fields;
- response attaches the approved CDM article;
- no invented permissions or access status.

---

## Task 4 - Microsoft 365 demo path and second real support article

### Goal

Complete the staged M365 positive/negative demonstration and make password reset a real Central de Suporte article.

### Reuse

- `KB-SYN-M365-PASSWORD-001`;
- approved Microsoft password URL;
- current success/failure conversational behavior;
- existing Central de Suporte article components;
- M365 technician handoff.

### Create/extend

- functional internal M365 article route/content;
- article link in the relevant Jup response;
- user-facing copy polish for success/failure;
- tests proving approved content and URL remain protected.

### Model routing

**Primary model:** GPT-5.6 Terra  
**Starting effort:** Medium

Why:

- behavior and content contracts are already known;
- this is mostly extending existing patterns.

### Luna usage inside this task

Luna Low may be used for purely mechanical fixture/assertion updates after the production behavior is finalized.

### Escalate to Sol Medium if

- article rendering requires changing shared approved-knowledge behavior;
- M365 state transitions regress.

### Acceptance

- password problem returns approved guidance;
- internal article is clickable;
- official Microsoft reference remains allowed;
- positive result resolves;
- negative result sends useful context to M365 support.

---

## Task 5 - My Requests natural query, slash command and requester UI

### Goal

Expose the same authoritative request data through:

- natural language;
- `/solicitacoes`;
- `/requests`.

### Reuse

- `DemoRuntime.list_requests()`;
- request ownership checks;
- existing `/requests` surface;
- current composer.

### Create/extend

- slash command menu opened by `/`;
- one functional command: `/solicitacoes`;
- backend intent/capability for request summary;
- natural-language request-status handling;
- chat summary with CTA to full request UI.

The slash command must not create a second source of business logic.

### Model routing

**Primary model:** GPT-5.6 Sol  
**Starting effort:** Medium

Why:

- touches frontend interaction, conversational intent and authoritative backend query;
- needs careful unification to avoid duplicate behavior.

### Escalate to Astra Low if

- natural-language query collides with existing request creation semantics;
- ownership or conversation authority becomes ambiguous.

### Acceptance

- typing `/` shows a compact menu;
- `/solicitacoes` returns only current requester's requests;
- "Como estão minhas solicitações?" uses the same backend capability;
- `/requests` shows the same underlying records.

---

## Task 6 - Conversation continuity across operational surfaces

### Goal

Stop route/persona navigation from accidentally destroying the requester chat while preserving explicit New Conversation reset.

### Reuse

- frontend state;
- route identity mapping;
- existing New Conversation endpoint/runtime reset;
- current request persistence behavior.

### Create/extend

- per-requester in-memory chat presentation state where necessary;
- route transitions that preserve requester messages;
- explicit reset remains the only chat-reset action.

### Model routing

**Primary model:** GPT-5.6 Terra  
**Starting effort:** Medium

Why:

- cause is already known;
- desired state semantics are explicit;
- implementation is primarily frontend/runtime state correction.

### Escalate to Sol Medium if

- route identity architecture prevents preservation without cross-layer changes;
- stale async responses create race conditions.

### Acceptance

- requester -> technician -> requester preserves chat;
- New Conversation clears chat/context;
- materialized requests and handoffs survive New Conversation.

---

## Task 7 - General IT triage and requester-language hardening

### Goal

Improve two related but distinct behaviors:

1. staged general-IT triage for "notebook lento";
2. safe handling of unexpected IT topics without approved knowledge.

Also remove unnecessary internal terminology from requester-facing responses and make out-of-scope conversation feel natural.

### Reuse

- conversational interpreter;
- ConversationContext/Delta/Reducer;
- grounding;
- NaturalResponseGenerator;
- GENERAL_IT_SUPPORT;
- TECH-GENERAL;
- current out-of-scope disposition.

### Required behavior

For staged general IT:

- ask one or two useful questions;
- build useful context;
- hand off.

For unknown IT:

- do not invent a procedure;
- collect only missing essential context;
- hand off after at most one or two useful clarifications.

For non-IT:

- recognize the subject;
- politely redirect to IT support;
- vary naturally;
- do not expose policy language.

For requester copy:

- reject unnecessary backend/policy/handler/capability language;
- preserve technical detail only where it benefits the technician.

### Model routing

**Primary model:** GPT-6 Astra  
**Starting effort:** Medium

Why:

- this is the most ambiguous behavior in the phase;
- interpreter, state, grounding, writer and routing can all contribute to failures;
- quality depends on semantic judgment rather than a simple code transformation.

### Escalate to High if

- representative real-Qwen tests still show inconsistent triage after deterministic boundaries are correct;
- writer/grounding interactions produce subtle authority regressions.

Do not use Extra High before representative tests demonstrate a real need.

### Acceptance

- notebook scenario performs bounded triage;
- an unexpected IT problem gets useful clarification then TECH-GENERAL;
- no approved knowledge means no invented procedure;
- out-of-scope responses are natural;
- requester-facing copy avoids unnecessary architecture terminology.

---

## Task 8 - Processing feedback during local-model latency

### Goal

Make the current ~20 second local wait feel active and understandable without pretending to expose model reasoning.

### Reuse

- current thinking state;
- Jup avatar states;
- existing animation/presentation helpers;
- reduced-motion handling.

### Create/extend

A small sequence of user-oriented presentation states such as:

- Entendendo sua solicitação...
- Consultando as informações necessárias...
- Verificando orientações sobre Microsoft 365...
- Verificando informações de acesso ao CDM...
- Preparando sua resposta...

The sequence is presentation feedback, not a trace of internal execution.

No SSE/WebSocket is required for this phase.

### Model routing

**Primary model:** GPT-5.6 Terra  
**Starting effort:** Medium

Why:

- interaction is well specified;
- implementation is primarily frontend state and motion.

### Escalate to Sol Medium if

- the presentation timer/state machine interacts badly with real async responses;
- accessibility or state restoration requires a broader redesign.

### Acceptance

- slow response never leaves a static-looking interface;
- messages remain non-technical;
- no false backend claims;
- reduced motion is respected;
- fast/error responses do not receive inappropriate artificial delays.

---

## Task 9 - Demo UI polish aligned to the presentation

### Goal

Polish, not redesign, the main demo surfaces after behavioral contracts are stable.

Priority surfaces:

1. chat;
2. technician queue/detail;
3. My Requests;
4. Central de Suporte;
5. demo identity control.

### Reuse

- current tokens;
- `docs/design.md`;
- Inter;
- existing Jup brand assets;
- current layout/components.

### Direction

Preserve:

- #45813c structural green;
- #173e25 deep green;
- #eeb41e attention/accent;
- #f6f8f5 canvas;
- white reading surfaces;
- clean editorial hierarchy.

Requester surfaces should feel simple and human.

Technical details on technician surfaces should be progressively disclosed rather than dominate the hierarchy.

### Model routing

**Primary model:** GPT-5.6 Sol  
**Starting effort:** Medium

Why:

- visual consistency spans several surfaces;
- requires judgment and refinement, but no new product architecture.

### Escalate to High only if

- layout/state interactions reveal substantial accessibility or responsiveness problems;
- component reuse requires a non-trivial refactor.

### Acceptance

- presentation and demo clearly belong to the same visual system;
- technician sees requester, request, mismatch, summary, progress and action in a clear order;
- requester can scan request status quickly;
- no unnecessary nested-card/dashboard aesthetic is introduced.

---

## Task 10 - Integrated demo acceptance and hardening

### Goal

Run the complete competition script against the real local model and fix only blockers or material demo regressions.

### Required integrated scenarios

1. configure requester A / Revenda;
2. contextual greeting;
3. generic CDM request resolves Revenda;
4. request UBS from Revenda and show mismatch;
5. configure requester B / UBS;
6. generic CDM request resolves UBS;
7. CDM informational article -> request continuation;
8. request status via natural language;
9. request status via `/solicitacoes`;
10. requester -> technician -> requester keeps chat;
11. New Conversation resets only conversation state;
12. M365 positive;
13. M365 negative;
14. notebook triage;
15. unexpected IT without knowledge;
16. clearly non-IT question;
17. processing feedback;
18. requester and technician UI walkthrough.

### Model routing

**Primary model:** GPT-6 Astra  
**Starting effort:** Medium

Why:

- final failures may span interpreter, backend, grounding, frontend, timing and test contracts;
- this task is diagnostic and end-to-end.

### Escalate to High if

- a blocker has several plausible root causes and Medium cannot isolate it;
- security/authority regressions appear.

### Extra High / xhigh

Permitted only for a specific unresolved high-value blocker after:

- reproducer exists;
- Medium/High analysis has been attempted;
- task cannot be reduced to a smaller isolated problem.

### Acceptance gate

Run the strongest available relevant checks, including:

- focused backend tests;
- full Python suite;
- Ruff lint/format;
- frontend lint/tests/build;
- `git diff --check`;
- real local Qwen acceptance battery for the staged scenarios;
- self-hosted/local-AI workflow as applicable.

No merge occurs without explicit authorization.

---

# Model summary

| Task | Model | Starting effort |
| --- | --- | --- |
| 1. Demo identity + greeting | GPT-5.6 Sol | Medium |
| 2. CDM scope/mismatch semantics | GPT-6 Astra | Low |
| 3. CDM conversational flow | GPT-5.6 Sol | Medium |
| 4. M365 + second article | GPT-5.6 Terra | Medium |
| 5. Requests + slash command | GPT-5.6 Sol | Medium |
| 6. Chat continuity/reset | GPT-5.6 Terra | Medium |
| 7. General triage + natural language | GPT-6 Astra | Medium |
| 8. Processing feedback | GPT-5.6 Terra | Medium |
| 9. UI polish | GPT-5.6 Sol | Medium |
| 10. Integrated hardening | GPT-6 Astra | Medium |

## Where Luna is expected

Luna Low is intentionally not the primary model for a major Phase 16 behavior.

Use it inside the phase for bounded mechanical follow-up work such as:

- repetitive fixture migration;
- known assertion updates;
- copy replacements with exact approved text;
- formatting/cleanup;
- simple test-table expansion after contracts are already final.

This avoids assigning security, authority, conversational semantics or cross-layer behavior to a model optimized for narrow repetitive work.

---

# Post-demo evaluation

These do not block Phase 16.

## Real CDM API

Initial recommendation if pursued:

**Model:** GPT-6 Astra  
**Effort:** High

Reason:

- external system;
- authentication/secrets;
- real data effects;
- contract drift risk;
- safety/idempotency concerns.

The task must be reshaped after verifying the current CDM API.

## Performance optimization

Initial diagnostic recommendation:

**Model:** GPT-6 Astra  
**Effort:** Medium

After profiling identifies a concrete bottleneck, implementation may drop to Sol/Terra depending on the fix.

Do not optimize based on guesswork.
