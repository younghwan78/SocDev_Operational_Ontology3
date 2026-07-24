# ADR-0011: Evaluation response and advice disclosure boundary

- Status: Accepted
- Date: 2026-07-24
- Scope: UX-J, local fixture PoC only

## Context

The Decision Workspace currently shows simulated Role and Chair advice before a user makes an
independent judgment. That is useful for a demonstration, but it cannot measure whether advice
changed the user's choice, accepted risk, safeguard, or reasoning. The local PoC also has no
authorized company participant study, approval workflow, or write-back target.

UX-J therefore needs an evaluation-only interaction without changing the existing demonstration
workflow or treating a builder's automated check as human evidence.

## Decision

The Workspace has two URL-addressable interaction modes:

- Demo mode keeps the existing simulated review, decision, execution, and outcome workflow.
- Evaluation mode records an independent response before advice, explicitly reveals the latest
  persisted simulated advice, and then records an `accept`, `modify`, or `reject` response.

Evaluation mode follows this state machine:

```text
NO_RESPONSE
  -> INITIAL_RECORDED
  -> SIMULATED_ADVICE_READY
  -> ADVICE_REVEALED
  -> FINAL_RECORDED
```

`SIMULATED_ADVICE_READY` is a Workspace condition, not a stored evaluation-response phase. The
response record stores only `initial_response`, `advice_snapshot`, and `final_response`.

Each stored phase is immutable. Every command requires `Idempotency-Key` and `If-Match`; the same
key and same payload is retry-safe, while reuse with different content is rejected. The Backend
resolves the local actor and latest simulated decision. The browser cannot supply participant
authority or the advice payload.

The response contract fixes:

```text
participant_kind = builder
interpretation   = engineering_proxy_only
AdviceAdoption   = accept | modify | reject
```

An `accept` response must retain the advice's selected option when the advice contains one.
`modify` and `reject` require an explicit difference reason. All selected options must be members
of the observable case alternatives.

Evaluation responses do not mutate the DecisionCase aggregate, simulated decision, Action Plan,
Outcome, Evaluation, or Project truth. They are not approvals and cannot write back to Jira,
Confluence, or company systems.

## HTTP and persistence

```text
GET  /api/v1/decision-cases/{case_id}/evaluation-response
POST /api/v1/decision-cases/{case_id}/evaluation-response/initial
POST /api/v1/decision-cases/{case_id}/evaluation-response/advice-reveal
POST /api/v1/decision-cases/{case_id}/evaluation-response/final
```

PostgreSQL stores one `observable.decision_evaluation_responses` row per `(case_id, actor_id)`.
The in-memory and PostgreSQL repositories implement the same ordering, immutability, option,
version, and idempotency rules.

## Consequences

- Advice is not rendered in Evaluation mode until an explicit reveal record exists.
- Reloads and restarts preserve the evaluation phase.
- Demo mode remains compatible with the established fixture workflow.
- Engineering automation may prove functionality but must not increment human-observation gates.
- A future authorized human study needs a separate participant identity and consent design rather
  than relabelling these builder records.

## Rejected alternatives

- Browser-only or `localStorage` responses: not restart-safe and cannot enforce immutability.
- Reusing the simulated decision as the user's response: destroys provenance and makes advice
  influence impossible to measure.
- Client-supplied `human` labels: permits false evidence.
- Hiding advice with CSS only: leaves advice in the accessible/rendered document.
- Requiring the evaluation sequence in Demo mode: breaks the existing operational simulation
  workflow and conflates product use with a study protocol.

## Verification gate

UX-J is complete only when contract generation, in-memory and PostgreSQL parity tests, Frontend
unit tests, browser accessibility checks, narrow-viewport checks, and the repository verification
suite pass. No human-usability gate is claimed by this stage.
