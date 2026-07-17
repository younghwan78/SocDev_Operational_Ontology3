# ADR-0009: Project the durable decision lifecycle in one Workspace

> Status: ACCEPTED
> Date: 2026-07-17

## Context

UX-D ended at deliberation. The browser could create a simulated decision and advance a fixture
Outcome, but a refresh lost the decision context because the Workspace did not read persisted
decision, Outcome or Evaluation records. The old screen also presented separate run experiments,
decision controls, safeguards and evaluation sections. That made the normal path unclear and left
the browser carrying decision content back into the Outcome command.

UX-E must let a reviewer answer four connected questions without exposing hidden fixture data:
what was decided, who acts and how it is verified, what condition causes rollback, and what changed
after the decision. Process quality and Outcome quality must remain separate.

## Decision

1. The current Workspace query joins the latest case-scoped durable Dossier run, simulated
   decision, Outcome and Evaluation. Their precedence determines the Workspace phase and its one
   allowed primary action.
2. The Backend projects the selected decision into a consumer-shaped Action Plan and Safeguard
   summaries. These include owner, due Step, trigger, verification, fallback, threshold, check and
   expiry Steps, violation action, escalation and reopen conditions. Frontend renders this contract
   and does not recalculate action state.
3. A persisted decision produces an Action `PLANNED → IN_PROGRESS` transition. After explicit
   fixture Outcome advance, only the selected option's validated transition targets are projected,
   with actual Outcome event IDs as their basis. The final Action state reflects Guardrail
   execution. This is a projection; it does not mutate the stored observable case history.
4. Expected model changes and actual Outcome facts are presented separately. Guardrail execution is
   separately visible, and Process Evaluation is never collapsed into Outcome Evaluation.
5. Before explicit Step advance, all Outcome content remains hidden. Historical Workspace responses
   omit Dossier run ID, decision, Action Plan, Safeguards, observed transitions, Outcome and
   Evaluation fail-closed.
6. The normal user flow runs only the release B2 Dossier. Single-Role and topology experiments stay
   on developer and evaluation surfaces.
7. `outcome-advance-command.v1` may omit the decision body. Backend resolves the latest persisted
   decision, rejects a missing decision with `DECISION_NOT_READY`, and rejects a supplied mismatch
   with `DECISION_MISMATCH`. The optional body remains accepted for compatible clients.

## Compatibility

This extends `decision-workspace.v2`, generated JSON Schema, OpenAPI and the TypeScript client in
one change. Repository interfaces add latest case-scoped reads over already persisted rows. No
database migration or legacy repository code import is required.

## Consequences

- Refresh and process restart preserve the user's decision lifecycle when PostgreSQL is used.
- The browser no longer acts as the authority for the decision used by Outcome advance.
- One actioning layout connects rationale, Action, Safeguard, Rollback, observed progress, result and
  learning while keeping the earlier deliberation available in a collapsed detail.
- `observed_event` transition rows are explicitly event-backed projections over validated expected
  targets, not claims that the observable case aggregate was rewritten.
- UX-E does not establish real human approval, Jira/Confluence write-back or company-data access.
- Responsive, keyboard, screen-reader, zoom, partial/stale/conflict and frozen-task usability
  acceptance remain UX-F scope.
