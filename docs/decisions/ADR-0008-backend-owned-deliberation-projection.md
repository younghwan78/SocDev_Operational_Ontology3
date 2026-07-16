# ADR-0008: Project current deliberation and uncertainty from Backend

> Status: ACCEPTED
> Date: 2026-07-17

## Context

UX-C exposed alternatives and the selected-Step development state, but the Workspace did not join
the durable multi-role Dossier. A Frontend-only grouping would need to interpret Role IDs,
recommendations, revisions and evidence eligibility, duplicating decision logic and risking future
information leakage in historical views. Long Role cards, numeric confidence and provider execution
metadata would also obscure the decision rather than clarify it.

## Decision

1. The Workspace query reads the latest case-scoped dossier run and passes its status and validated
   Dossier result to the Backend projection.
2. Backend owns option comparison fields, Korean Role and decision labels, agreement groups, key
   dissent, challenge changes and epistemic classification. Frontend only renders these fields.
3. A Role recommendation badge is emitted only when effective reviews identify one unambiguous
   most-supported option. It is explicitly a Role-review recommendation, never an automatic rank,
   score or final approval.
4. Facts and inferences require source evidence eligible at the selected Step. Unversioned
   assumptions and unknowns, durable Dossier alignment and Role originals are current-view only;
   historical Workspace responses omit them fail-closed.
5. Desktop uses one semantic comparison table. Mobile uses one option card with previous/next
   controls and no horizontal table scroll.
6. Normal user UI shows agreement, dissent and confirmation first. Role originals and revisions are
   available only in a detail section with qualitative confidence. Raw Role IDs, provider, token,
   cost and execution trace are not part of this user projection.

## Compatibility

This extends `decision-workspace.v2`, generated OpenAPI and the TypeScript client together. The
route remains stable and no database migration is required. Existing Workspace UX fixtures remain
valid because the new projection fields have safe defaults.

## Consequences

- Current Workspace phase can represent a durable review in progress or a completed Dossier.
- Historical inspection cannot reveal later Role reasoning or current unversioned uncertainty.
- Role disagreement remains visible even when one option receives the recommendation badge.
- Frontend does not count votes, infer evidence eligibility or translate raw Role IDs.
- Option-specific safeguards are not invented from general Role prose. Their decision-linked
  projection, action controls and observed outcomes remain UX-E scope.
