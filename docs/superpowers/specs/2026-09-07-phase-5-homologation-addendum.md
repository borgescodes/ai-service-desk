# Phase 5 Dell homologation addendum

Status: normative clarification discovered during Dell homologation of the approved Phase 5 design.

Base approved spec: `docs/superpowers/specs/2026-09-07-phase-5-conversational-triage-design.md`.

This addendum does not change the Phase 5 architecture, public result states, state schema, knowledge threshold, Phase 4 retrieval contract, protected-file policy, privacy boundary, or the 10 approved smoke scenarios. It only makes two already-required smoke behaviors deterministic when the existing LLM classifier returns a plausible but unsuitable classification for a terse clarification turn.

## Evidence that triggered the clarification

On Dell homologation at head `d89a329f1481fdab46d3c5a13c82a16b3120065d`, the real model produced these relevant classifications for the synthetic smoke phrases:

```text
unknown-first | intent = PROBLEMA_ACESSO | system = 'XYZ'
unknown-reply | intent = OUTRO | system = ''
anti-loop-first | intent = ORIENTACAO | system = ''
anti-loop-reply | intent = ORIENTACAO | system = ''
```

The resulting smoke failures were:

```text
unknown-remains -> NEEDS_CLARIFICATION / MISSING_PROBLEM
anti-loop -> NEEDS_CLARIFICATION / MISSING_SYSTEM
```

Both contradict the already-approved smoke semantics. The classifier itself remains unchanged.

## Clarification A: repeat of the current pending system remains slot-only

When `pending_field == "system"` and `state.system` is already non-empty, a terse reply is also considered `SYSTEM_SLOT` when its normalized text is exactly either:

```text
<state.system>
sistema <state.system>
```

This fallback applies even when the single classification of the current turn omits `classification.system`.

It does not infer a new system, canonicalize an unknown literal, perform fuzzy matching, or choose among multiple systems. It only recognizes that the user repeated the exact system value already stored from the previous turn.

The merge preserves the previous substantive `problem_text`, `intent`, `entities`, and `confidence`. If that repeated system is still unknown, `asked_fields` causes the next `UNKNOWN_SYSTEM` transition to be terminal instead of asking another unrelated clarification.

## Clarification B: exact approved insufficient-problem phrases override false-positive intent labels

To keep the approved anti-loop smoke deterministic, Phase 5 recognizes only these exact normalized insufficient-problem phrases:

```text
preciso de ajuda
nao sei explicar
```

Rules:

- `preciso de ajuda` is treated as insufficient problem context only when there is no pending field;
- `nao sei explicar` is treated as an unresolved problem reply only when `pending_field == "problem"`;
- punctuation and accent differences handled by the existing normalization helper do not create additional semantic variants;
- no fuzzy matching, synonym list, semantic parser, second classifier, or generic natural-language understanding is introduced.

For these exact phrases, the triage state resolves the turn as insufficient problem context for transition purposes, with `intent = OUTRO`. `entities` from the false-positive classification are not persisted. `confidence` remains metadata only and has no decision effect.

Therefore the approved anti-loop sequence is deterministic even if the classifier returns `ORIENTACAO`:

```text
Preciso de ajuda.
-> NEEDS_CLARIFICATION / MISSING_PROBLEM

Nao sei explicar.
-> TRIAGE_ABSTAINED / UNRESOLVED_PROBLEM
```

## TDD evidence

The Dell behavior was reproduced with deterministic control doubles before the fix:

- RED commit: `e88872795d313393fec2015d909dbe1171cb74c7`;
- hosted CI run 140: `2 failed, 223 passed`;
- both failures matched the Dell symptoms exactly.

The minimal triage-only fix then passed:

- functional fix commit: `2bbf45958aa133d02deb3949218f4578bdfaea12`;
- formatting-only follow-up: `bcb67c99fc7fde5716be7f4cbe4750031bfa86ff`;
- hosted CI run 142: Ruff lint green, Ruff format green, `225 passed`.

`classification.py`, `retrieval.py`, `index.py`, and `knowledge.py` remain unchanged. The smoke fixture remains unchanged at exactly 10 synthetic scenarios.
