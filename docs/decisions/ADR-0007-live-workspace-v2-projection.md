# ADR-0007: Serve a live Workspace v2 projection with fail-closed history

> Status: ACCEPTED
> Date: 2026-07-17

## Context

UX-A defined `decision-workspace.v2`, but the user-facing detail endpoint still returned the broad
`decision-workspace.v1` read model. React separately fetched the timeline and displayed current
tracks, raw counts and Agent controls without one selected-Step boundary. Rendering the UX-A example
fixture directly would look complete while becoming stale as the stored case changes.

The observable case can reconstruct WorkItem, milestone, evidence and action state from typed
development events. Commitment windows and option transitions, however, need an explicit model and
must not be guessed from UI text.

## Decision

1. `GET /api/v1/decision-cases/{case_id}/workspace` returns `decision-workspace.v2` and accepts an
   optional `at_step`.
2. Backend builds header, deadline, Decision Brief, posture, selected-Step track state, causal chain,
   alternatives and workflow from the stored observable case.
3. A validated `WorkspaceUxFixture` may supply commitment windows and observable-model expected
   transitions only when case ID, fixture version and option IDs match.
4. Without compatible model content, Backend emits an expected-transition item per option with no
   state change and an explicit unknown impact. Frontend never invents the transition.
5. Historical projection is limited to the validated earliest Step. It omits current case status,
   workflow phase and all command actions, and filters causal events by observation Step.
6. Expected and observed transitions remain different schema branches and different visual cards.
   No decision-linked observed transition is emitted until a durable projection can prove it.

## Compatibility

This intentionally replaces the local PoC detail response from v1 to v2. The route remains stable;
the schema identity, OpenAPI and generated TypeScript type change together. There is no company
consumer, write-back or database migration.

## Consequences

- Current and past development state share one Backend source of truth.
- A static UX fixture cannot overwrite live Step, deadline, track or evidence state.
- Past views cannot reveal a later Agent phase or decision through header/action fields.
- Cases without a validated model remain usable but show unknown commitment/transition content.
- Current phase adapts to persisted `DecisionCaseStatus`; the latest durable run is not yet joined.
- Decision-linked observed transitions and expectation-versus-actual belong to a later UX-E boundary.
