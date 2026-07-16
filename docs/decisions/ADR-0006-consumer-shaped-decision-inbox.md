# ADR-0006: Use a Backend-ranked consumer projection for the decision inbox

> Status: ACCEPTED
> Date: 2026-07-17

## Context

`GET /api/v1/decision-cases` returned complete `decision-workspace.v1` projections. The list page
used only a title, deadline and blocker count, while receiving evidence, claims, alternatives and
track detail for every case. It also had no Backend contract for attention order, why-now text,
critical blocker propagation, list grouping or the next user action.

Calculating those values in React would duplicate domain rules and could order the same case
differently from the Decision Workspace. Continuing to return complete workspaces would also make
the initial list response grow with every UX-C workspace field.

## Decision

1. `GET /api/v1/decision-cases` returns `decision-list-item.v1` instead of an array of complete
   workspace projections.
2. Backend derives deadline attention, critical blocker propagation, milestone impact, list group,
   why-now explanation and next-action label.
3. Backend returns items in attention order. Frontend preserves that order and only groups adjacent
   items by the explicit `group` field.
4. The list projection includes `case_id` only for routing. The UI does not display raw IDs.
5. `GET /api/v1/decision-cases/{case_id}/workspace` remains `decision-workspace.v1` until UX-C
   connects the approved v2 projection.
6. The current projection derives groups from `DecisionCaseStatus`. `IN_REVIEW` remains a supported
   list group but is not emitted until a later projection can safely read the latest case-scoped
   durable run without adding a Frontend heuristic.

## Compatibility

This is an intentional consumer-contract replacement for the local PoC collection response. The
route is unchanged, while the new response declares a new schema identity. OpenAPI, the committed
TypeScript client, Backend tests, React consumers and E2E are updated together. There is no database
migration and no company or external API consumer.

## Consequences

- The first response is smaller and does not include workspace evidence, claims or alternatives.
- Decision ordering and why-now wording are deterministic Backend behavior.
- React renders server state without storing or recalculating derived urgency.
- The normal navigation exposes only decision work; Fixture management remains developer-only.
- UX-C can expand the workspace independently without inflating the inbox response.
- Run-aware `IN_REVIEW` grouping remains explicitly incomplete rather than inferred from stale or
  unavailable data.
