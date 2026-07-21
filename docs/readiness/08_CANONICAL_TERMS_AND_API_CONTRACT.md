# Canonical terms and API contract

> Status: APPROVED  
> Date: 2026-07-21
> Scope: local fixture-only PoC

This contract removes ambiguous names shared by domain state, Agent runs, UI phases, fixture versions, and HTTP resources. Backend, Frontend, fixtures, tests, and documentation must reuse these names.

## 1. State spaces

### 1.1 DecisionCaseStatus

`DecisionCaseStatus` represents the domain lifecycle only.

```text
DRAFT
CONTEXT_BUILDING
OPTIONS_READY
DECISION_REQUIRED
DECIDED
ACTIONING
VERIFIED
CLOSED
REOPENED
```

Allowed main path:

```text
DRAFT → CONTEXT_BUILDING → OPTIONS_READY → DECISION_REQUIRED
→ DECIDED → ACTIONING → VERIFIED → CLOSED
```

`REOPENED` returns to `CONTEXT_BUILDING` through an explicit command. `APPROVED`, `DEFERRED`, `REVIEW_RUNNING`, and `DOSSIER_READY` are not case statuses.

### 1.2 DecisionType

`DecisionType` records the conclusion when `DecisionCaseStatus=DECIDED`.

```text
APPROVE
APPROVE_WITH_GUARDRAILS
RUN_REVERSIBLE_TRIAL
COLLECT_MINIMUM_EVIDENCE
DEFER_UNTIL_TRIGGER
REJECT
ESCALATE
```

Fixture, Agent output, evaluation, API, database, and Frontend use these exact uppercase codes. Do not introduce synonyms such as `conditional_approve`, `bounded_trial`, or `unconditional_approve`.

### 1.2.1 DecisionActionPlan

`simulated-decision.v2` requires one `decision-action-plan.v1`. It uses the
canonical fields `action_type`, `owner`, `action`, `due_at_step`, `trigger`,
`verification`, and `fallback_action`. `COLLECT_MINIMUM_EVIDENCE` additionally
requires `evidence_required`; `ESCALATE` requires `escalation_target` and
`questions_to_resolve`; `REJECT` requires `reopen_condition`.

`ESCALATE` is reserved for an authority boundary or irreversible risk outside the
current role's control. Missing data alone selects a risk-limiting decision such as
minimum evidence collection, deferral to a named trigger, or a guarded reversible
trial. The local Chair remains simulated and cannot grant real execution authority.

### 1.3 AgentRunStatus

```text
QUEUED
RUNNING
PARTIALLY_COMPLETED
COMPLETED
FAILED
CANCELLED
```

This status belongs to a run. It never changes the DecisionCase lifecycle by itself.

### 1.4 WorkspacePhase

`WorkspacePhase` is a read-model field derived from case, run, dossier, decision, and outcome state.

```text
CONTEXT_PREPARATION
READY_FOR_REVIEW
REVIEW_RUNNING
DOSSIER_READY
DECISION_REQUIRED
OUTCOME_RUNNING
EVALUATION_READY
CLOSED
```

Frontend primary actions use `WorkspacePhase`. Commands still validate the underlying aggregate versions and states.

## 2. Epistemic contract

Every accepted concern, option assessment, recommendation, and Dossier statement references atomic claims.

```yaml
claim_id: CLM-001
statement: DDR bandwidth가 guardrail을 초과할 수 있다
epistemic_status: inference
source_refs:
  - MEAS-BW-001
inference_basis:
  - RULE-BW-MARGIN-001
confidence_level: medium
```

Allowed `epistemic_status` values:

```text
fact
inference
assumption
unknown
```

Validation rules:

- `fact` requires at least one eligible source reference
- `inference` requires source references and an inference basis
- `assumption` requires an owner or review/expiry step
- `unknown` states what is unknown and the next evidence action when available
- confidence is `low`, `medium`, or `high`; it is not a model-generated probability
- recommendation and Dossier fields reference `claim_id` instead of duplicating unsupported prose

## 3. Simulation time vocabulary

|Field|Use|
|---|---|
|`current_step`|current logical simulation step|
|`effective_at_step`|when a fact or change becomes true|
|`observed_at_step`|when the simulated organization learns it|
|`available_at_step`|when it becomes eligible for Agent input|
|`expires_at_step`|when an assumption, guardrail, or waiver needs review|
|`recorded_at`|wall-clock audit timestamp only|

Local domain APIs use `at_step`, not ambiguous `as_of` timestamps. Future enterprise bitemporal fields require a separate contract.

### 3.1 DevelopmentEvent history

`development-event.v1` records a typed change with its cause and before/after state.
`effective_at_step` is when the change became true; `observed_at_step` is when it may
enter an Agent packet or user projection. The canonical event types are:

```text
WORK_PROGRESS
BLOCKER_CHANGE
PLAN_CHANGE
DEPENDENCY_CHANGE
EVIDENCE_CHANGE
REWORK
INTERFACE_CHANGE
RESOURCE_CONFLICT
PRIORITY_CHANGE
DECISION_ACTION_PROGRESS
```

Histories are append-only and ordered by `(observed_at_step, event_id)`. Each entity's
change chain is continuous, and its latest `after` state equals the current case
snapshot. Historical reconstruction reverses changes not yet observed at `at_step`.
The resulting packet and projection must not expose a later event or future evidence.

Post-decision development actions use `PLANNED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`,
or `CANCELLED`. These are action states, not `DecisionCaseStatus` values.

## 4. Version vocabulary

|Field|Meaning|
|---|---|
|`fixture_version`|immutable source fixture revision|
|`fixture_hash`|content hash of a frozen fixture|
|`aggregate_version`|optimistic concurrency version of a mutable aggregate|
|`projection_schema_version`|shape version of a read model response|
|`projection_source_versions`|aggregate versions used to build a projection|
|`contract_version`|Pydantic/JSON Schema major contract|
|`prompt_bundle_version`|committed prompt bundle and hashes|
|`policy_version`|routing/decision/runtime policy|
|`outcome_rule_version`|OutcomeRule registry version|

Current executable decision contract versions are `simulated-decision.v2` and
`decision-action-plan.v1`. `simulated-decision.v1` remains a historical read/migration
format and is not emitted by current commands.

Do not use the generic name `case_version` for more than one meaning.

## 5. Canonical Frontend routes

```text
/decisions
/decisions/:caseId
/dev/fixtures
```

Frontend paths are user navigation. They do not define HTTP resource names.

## 6. Canonical HTTP resources

### 6.1 Query API

```text
GET /health/live
GET /health/ready
GET /api/v1/decision-cases
GET /api/v1/decision-cases/{case_id}/workspace
GET /api/v1/decision-cases/{case_id}/timeline
GET /api/v1/decision-cases/{case_id}/evidence
GET /api/v1/decision-cases/{case_id}/evaluation
```

The decision-case collection returns `decision-list-item.v1`, already ordered by Backend
attention priority and grouped with an explicit list-group field. Frontend consumers do not
recalculate urgency, blocker propagation, milestone impact, or next-action labels.

The workspace resource returns `decision-workspace.v2`. Optional `at_step` reconstructs the
observable development state within the projection's declared earliest/latest boundary. A
historical response omits current workflow phase, case status and command actions so later Agent or
decision state cannot leak backward. Commitment and expected transitions require validated model
content; missing model content is returned as unknown rather than inferred by Frontend.

The current-step Workspace also joins the latest case-scoped durable dossier run. Backend owns the
run-aware phase, option recommendation badge, agreement/dissent/confirmation groups, Role labels and
epistemic eligibility. A historical response omits the Dossier, Role originals and unversioned
assumptions/unknowns. Frontend must not rank alternatives, count Role votes or recover raw Role IDs.

After a simulated decision exists, the current-step Workspace also joins the latest case-scoped
durable decision, Outcome and Evaluation. Backend owns the phase precedence
`decision → OUTCOME_RUNNING`, `Outcome → EVALUATION_READY`, `Evaluation → CLOSED`, the one allowed
primary action for that phase, Action Plan status, Safeguard summaries, observed transition
projection and expected/actual separation. Before explicit Outcome advance, outcome fields remain
hidden. A historical response omits the decision, outcome, evaluation and dossier run identifier.
Frontend must not infer a completed action or expose a simulated outcome early.

The timeline resource returns `development-timeline.v1`. Optional query parameter
`at_step` reconstructs the case at that logical step and returns only events with
`observed_at_step <= at_step`. An out-of-range step returns
`DEVELOPMENT_STEP_OUT_OF_RANGE`.

### 6.2 Command API

```text
POST /api/v1/decision-cases/{case_id}/review-runs
POST /api/v1/decision-cases/{case_id}/simulated-decisions
POST /api/v1/decision-cases/{case_id}/outcome-advances
POST /api/v1/decision-cases/{case_id}/evaluations
```

Review runs perform routing, independent Role review, optional challenge/revision, and Dossier
creation according to their persisted topology. The simulated decision remains a distinct command;
B2 uses the deterministic core and B3 uses the provider Chair result.

`outcome-advance-command.v1` may omit its `decision` body field for the normal Workspace flow. The
Backend then resolves the latest persisted decision for the case. If no persisted decision exists,
the command returns `DECISION_NOT_READY`; if a supplied decision differs from the persisted latest
decision, it returns `DECISION_MISMATCH`. This keeps the Frontend command reload-safe without making
the browser an authority for decision content. Logical time still advances only through this
explicit command.

### 6.3 Run API

```text
GET  /api/v1/runs/{run_id}
GET  /api/v1/runs/{run_id}/events
POST /api/v1/runs/{run_id}/cancel
POST /api/v1/runs/{run_id}/retry
```

### 6.4 Developer API and CLI

Observable validation and import may use local-only developer routes:

```text
POST /api/v1/dev/fixtures/validate
POST /api/v1/dev/fixtures/import
GET  /api/v1/dev/fixtures/{case_id}/observable
GET  /api/v1/dev/runs/{run_id}/trace
GET  /api/v1/dev/contracts
```

No HTTP route returns hidden fixtures. Hidden inspection is authoring CLI-only with `SOC_OT_AUTHORING_MODE=1`.

## 7. Command envelope

Every state-changing request includes:

- `Idempotency-Key` header
- `If-Match` containing the expected `aggregate_version`, or an equivalent typed body field where HTTP intermediaries cannot preserve it
- actor/audit context resolved by the application
- stable command schema version

Example asynchronous response:

```json
{
  "run_id": "RUN-001",
  "run_kind": "dossier",
  "topology": "B2",
  "status": "QUEUED",
  "status_url": "/api/v1/runs/RUN-001",
  "events_url": "/api/v1/runs/RUN-001/events"
}
```

For role-review runs `topology` is null. Dossier runs require B1, B2, or B3, and retry preserves
the stored value. Outdated versions fail with `CASE_VERSION_CONFLICT`. A repeated idempotency key
with a different payload or topology fails with `IDEMPOTENCY_KEY_REUSED`.

## 8. ObservableCasePacket

Before an Agent call, `BuildObservableCasePacket` creates a frozen, hashed input containing:

- decision question, allowed option IDs, deadline, current step
- current development tracks, work, blockers, dependencies, milestones
- eligible evidence and atomic claims
- assumptions, unknowns, uncertainty and evidence availability
- deterministic impact and role-routing candidates
- reversibility, detectability, recoverability and constraints
- allowed source IDs and hidden-field denylist result
- `packet_hash`, `fixture_version`, `contract_version`, `policy_version`

Role Agent, Challenger, and Chair receive the packet or a typed subset. They never receive a repository object or raw hidden fixture.

## 9. Worker lease contract

The PostgreSQL worker claims jobs with a lease and a `FOR UPDATE SKIP LOCKED` query.

Required fields:

```text
lease_owner
lease_expires_at
heartbeat_at
attempt_no
next_retry_at
cancel_requested_at
```

The logical step key is `(run_id, step_kind, role_id, review_round)`. Provider execution may be at-least-once after a crash, but one logical step stores at most one accepted normalized output.

Required failure tests:

- lease expiry and reclaim
- worker crash after provider response but before commit
- duplicate completion
- cancellation during an in-flight call
- late response after cancellation

## 10. Accepted OPS-A reservation

ADR-0010 accepts Project Operations and Risk Provenance as the post-I7 product direction. The
following names are reserved for OPS-B/OPS-C and must not be replaced by synonyms:

```text
ProjectAttention = ON_TRACK | WATCH | AT_RISK | BLOCKED
IssueStatus       = OPEN | MITIGATING | RESOLVED
RiskStatus        = OPEN | TREATING | ACCEPTED | REALIZED | CLOSED
RiskLevel         = LOW | MEDIUM | HIGH | CRITICAL
MilestoneKind     = CHECKPOINT | GATE | RELEASE
```

`ProjectAttention` and `RiskLevel` are Backend-owned deterministic projection fields. Source
fixtures and Frontend code do not assign them from an uncalibrated impact-times-likelihood score.
Every projected value includes reason and source references. Role Agent output remains an
epistemically labelled candidate and cannot mutate Project truth.

The target authoring fixture version is `development-project.v1`. It separates observed
`DevelopmentIssue`, future `ProjectRisk`, missing `Evidence`, `DecisionCase` and treatment Action.
Current `observable-case.v1` remains executable and unchanged during OPS-A.

The following routes and resources are reserved but are **not executable until their OPS-C Gate
passes**:

```text
/projects
/projects/:projectId
/projects/:projectId/risks/:riskId

GET /api/v1/projects
GET /api/v1/projects/{project_id}/situation
GET /api/v1/projects/{project_id}/risks
GET /api/v1/projects/{project_id}/risks/{risk_id}
GET /api/v1/projects/{project_id}/timeline
```

Historical Project resources use `at_step` and the existing effective/observed/available boundary.
ADR-0010 owns the full semantic boundary and transition sequence.

## 11. Compatibility gate

Any change to a state code, DecisionType, endpoint, time field, or version name updates this contract first. CI then checks generated schemas, OpenAPI, Frontend client, fixture manifests, runbook examples, and documentation references.
