# MODEL_ROUTING.md

## Purpose

This file defines how this repository chooses a Codex model and reasoning effort for implementation work.

The goal is not to use the strongest model everywhere. The goal is to use the smallest model and lowest reasoning effort that can complete the task reliably, then escalate only when the work actually requires it.

Model choice is task-scoped, not project-scoped.

A single phase may deliberately use different models for different tasks.

## Current model roles

### GPT-5.6 Luna

Use Luna for work that is:

- explicit;
- repetitive;
- local;
- easy to verify mechanically;
- low-risk.

Typical examples:

- rename or update known symbols;
- update fixtures after a contract is already decided;
- add straightforward assertions;
- transform repetitive data;
- edit copy with exact acceptance criteria;
- perform narrowly scoped cleanup.

Default effort: **Low / Light / Instant-class**.

Do not use Luna as the primary model when the task requires architectural decisions, unknown-cause debugging, security reasoning, or coordination across several layers.

### GPT-5.6 Terra

Use Terra for everyday implementation where the desired behavior is already clear but the task still requires normal engineering judgment.

Typical examples:

- implement a well-specified endpoint;
- connect an existing backend capability to an existing UI surface;
- add a small interaction;
- fix a known frontend state bug;
- extend tests around a defined behavior;
- implement a bounded component or service.

Default effort: **Medium**.

Use Low when the implementation is especially obvious. Escalate to High only if the task unexpectedly becomes cross-cutting or difficult.

### GPT-5.6 Sol

Use Sol for complex professional work that crosses layers or requires meaningful planning, validation, and refinement.

Typical examples:

- change backend + frontend + tests together;
- implement a feature whose architecture is known but not trivial;
- refactor conversation state without breaking authority;
- perform design-system-level UI work;
- integrate several existing services;
- debug a regression with multiple plausible causes.

Default effort: **Medium**.

Use High when the task contains difficult debugging, subtle state transitions, compatibility risks, or substantial edge-case analysis.

Extra High should be exceptional.

### GPT-6 Astra

Use Astra when the hard part is deciding what the correct solution is, not merely typing it.

Typical examples:

- unknown-cause failures;
- architectural shaping;
- safety/authority boundaries;
- ambiguous conversational behavior;
- complex end-to-end integration;
- final hardening when regressions span several subsystems;
- difficult security review.

Default effort: **Low or Medium**.

Do not assume Astra needs High reasoning. Start at Low for a well-bounded difficult task and Medium when sustained judgment is required.

Use High only when the task remains genuinely difficult after clear requirements and repository context are available.

Use Extra High / xhigh only when representative evidence shows Medium/High is insufficient.

Use Max only for exceptional diagnostic or review work.

## Reasoning effort policy

Use the lowest effort that reliably satisfies the task.

Repository terminology:

| Planning label | Codex/API meaning | Use |
| --- | --- | --- |
| Instant / Light | low | Mechanical, bounded, fast work |
| Medium | medium | Default for normal engineering |
| High | high | Complex debugging, edge cases, high-value implementation |
| Extra High | xhigh | Rare, unusually demanding review or implementation |
| Max | max | Exceptional only |
| Ultra | multi-agent/delegated mode where available | Not a default for this repository |

The exact UI label can differ by Codex surface. The implementation plan should always record the semantic level: low, medium, high, xhigh, or max.

## Task execution rule

Each implementation task must declare:

- primary model;
- starting reasoning effort;
- why that model is sufficient;
- escalation triggers;
- completion evidence.

A task starts on the declared model and effort.

If unexpected complexity appears, do not silently burn more reasoning indefinitely. First identify why the current configuration is insufficient.

Escalation path:

```text
Luna -> Terra -> Sol -> Astra
low -> medium -> high -> xhigh -> max
```

Escalate the model when the task needs more capability.

Escalate effort when the chosen model is appropriate but needs more planning, verification, or edge-case reasoning.

Prefer changing only one dimension at a time.

## Checkpoint rule

A model change does not require a new Git branch.

For this repository, the normal flow is:

```text
Phase branch
  -> Task 1
  -> tests
  -> commit/checkpoint
  -> Task 2, possibly different model
  -> tests
  -> commit/checkpoint
  -> ...
  -> final gate
```

Do not create one branch per model.

Create a separate branch only when isolation is useful for product or Git reasons, not because the model changed.

## Escalation examples

### Mechanical test repair

If a production contract is already final and several test doubles need the same field rename:

- Luna
- low

Escalate only if the failures reveal a production contract problem.

### Defined feature across one layer

If an existing endpoint needs one new validated field and tests:

- Terra
- medium

Escalate to Sol if the change unexpectedly affects policy, state, routing, or compatibility.

### Cross-layer feature

If a request changes trusted identity, backend behavior, UI rendering, and acceptance tests:

- Sol
- medium

Escalate to Astra if authority or architecture becomes ambiguous.

### Unknown conversational failure

If the agent behaves unnaturally and the cause could be interpreter, grounding, state, or writer behavior:

- Astra
- medium

Do not start by modifying prompts blindly.

## Safety and authority override

Tasks affecting any of the following should never be assigned primarily to Luna:

- trusted identity;
- authorization;
- policy;
- approval;
- execution;
- external integrations;
- protected knowledge;
- grounding authority;
- request ownership;
- security-sensitive routing.

Use Sol or Astra depending on ambiguity and cross-layer complexity.

## UI override

Visible UI work must follow the repository design direction and applicable UI/UX skill/guidelines regardless of model.

A larger model is not permission to redesign unrelated surfaces.

## Phase 16 policy

Phase 16 uses one main branch:

`phase-16-demo-readiness`

Tasks are implemented sequentially with task-level commits and may change model/effort between tasks.

The exact Phase 16 routing matrix lives in:

`docs/superpowers/plans/2026-09-19-phase-16-demo-readiness.md`

## Post-task handoff

At the end of every task, record:

- files changed;
- behavior delivered;
- tests/checks executed;
- commit SHA;
- known limitations;
- whether escalation occurred;
- recommended model/effort for the next task.

This allows the next model to continue from repository evidence instead of reconstructing decisions from chat history.
