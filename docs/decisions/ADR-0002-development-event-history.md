# ADR-0002: Development event history and historical reconstruction

> Status: ACCEPTED
> Date: 2026-07-14
> Scope: I7 Step 2, local fixture-only PoC

## Context

The current snapshot shows what is blocked now, but it cannot explain how interface
changes, measurement delays, rework, resource conflicts, and post-decision actions
produced that state. Agents also need a historical packet that never learns an event
or evidence item before the simulated organization observed it.

## Decision

- `ObservableCase` owns an append-only `development_events` collection and optional
  `development_actions`.
- A `DevelopmentEvent` records `effective_at_step` separately from
  `observed_at_step`, its cause, and typed before/after changes.
- A current validated snapshot is reconstructed backwards by reversing events whose
  `observed_at_step` is later than the requested `at_step`.
- Event chains must be continuous, and the last `after` state must equal the current
  snapshot. A malformed history is rejected at fixture/model validation time.
- `BuildObservableCasePacket(at_step=...)` receives only the reconstructed state,
  events already observed, and evidence eligible at that historical step.
- The four Step 2 cases live under `fixtures/cases/development`. They are independent
  full fixtures and do not inherit from or change the frozen eight-case evaluation
  release. Evaluation-corpus expansion remains a later Step 3 decision.

## Consequences

- One event history can produce multiple time-consistent development states.
- Blockers can be traced through work dependencies to tracks and milestones.
- The local UI can explain what changed and why without displaying raw ontology.
- Persisted JSONB cases require migration `0018_development_event_history`.
- Downgrade removes `development_actions` and `development_events`; non-empty history
  must be backed up before downgrade because that operation is intentionally lossy.

## Rejected alternatives

- Snapshot-only fixtures: they cannot explain change or reconstruct historical inputs.
- Forward replay from a separate initial snapshot: it duplicates fixture state and
  creates two sources of truth.
- Reusing the frozen eight evaluation cases for Step 2: it would mix implementation
  verification with the later evaluation-corpus v2 decision.
