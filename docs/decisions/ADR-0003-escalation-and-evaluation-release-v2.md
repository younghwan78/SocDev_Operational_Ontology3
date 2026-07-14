# ADR-0003: Escalation policy and evaluation release v2

> Status: ACCEPTED
> Date: 2026-07-14
> Scope: I7 Step 3, local fixture-only PoC

## Context

`CASE-VR-005` has no eligible claim at its current step. A prior live evaluation
sometimes selected `ESCALATE`, while the v1 expected result accepted only a reversible
trial or deferral. Missing evidence alone must not turn escalation into a default
answer, but the unresolved customer feature priority is also a product-authority
decision outside the technical review roles.

The earlier sealed cases and results have already been inspected. They remain useful
regressions but cannot serve as fresh validation or sealed evidence for the next
candidate.

## Decision

- Missing data alone selects `COLLECT_MINIMUM_EVIDENCE`, `DEFER_UNTIL_TRIGGER`, or a
  guarded reversible trial according to reversibility and deadline.
- `ESCALATE` is acceptable only when `allowed_decision_types` explicitly asserts an
  authority boundary, cross-organization conflict, or irreversible risk outside the
  current roles' control.
- Every escalation requires a named target, questions to resolve, due step,
  verification, and fallback. The action-plan schema and v2 process evaluation enforce
  these structured fields.
- `CASE-VR-005` qualifies because customer/product priority authority is outside the
  technical roles. Its v2 expected source accepts `ESCALATE`; the historical v1 source
  remains unchanged.
- Evaluation release `eval-2026-07-14.2` uses explicit per-case source paths. The eight
  previously opened cases move to the development regression partition. `CASE-DT-001`
  and `CASE-DT-002` become validation; `CASE-DT-003` and `CASE-DT-004` become the new
  sealed partition.

## Consequences

- A manifest can select a versioned expected result without mutating historical source
  hashes.
- Replay and live evaluation execute the cases named by the supplied manifest rather
  than a separate global case list.
- New writes use `case-evaluation.v2`; persisted v1 rows remain readable through
  backward-compatible defaults, so no database migration is required.
- The home-authored sealed partition is a regression guard, not independent scientific
  or business-value evidence. No prompt or policy tuning may use its v2 hidden result.
