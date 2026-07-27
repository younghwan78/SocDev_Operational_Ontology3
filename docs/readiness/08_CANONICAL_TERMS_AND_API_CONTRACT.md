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

UX-J adds the evaluation-only `decision-evaluation-response.v1` read contract and
`decision-initial-response-command.v1`, `decision-advice-reveal-command.v1`, and
`decision-final-response-command.v1` commands. `AdviceAdoption` is exactly
`accept | modify | reject`.

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
GET /api/v1/decision-cases/{case_id}/evaluation-response
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

The evaluation-response resource returns the current local actor's
`decision-evaluation-response.v1`, or JSON `null` before an initial response exists. It is
evaluation-only and fixes `participant_kind=builder` and
`interpretation=engineering_proxy_only`; these records are not human-observation evidence.

### 6.2 Command API

```text
POST /api/v1/decision-cases/{case_id}/review-runs
POST /api/v1/decision-cases/{case_id}/simulated-decisions
POST /api/v1/decision-cases/{case_id}/outcome-advances
POST /api/v1/decision-cases/{case_id}/evaluations
POST /api/v1/decision-cases/{case_id}/evaluation-response/initial
POST /api/v1/decision-cases/{case_id}/evaluation-response/advice-reveal
POST /api/v1/decision-cases/{case_id}/evaluation-response/final
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

Evaluation-response commands implement the immutable order
`initial response → advice reveal → final response`. The Backend resolves the latest persisted
simulated advice; the client never posts advice content or participant authority. `accept` retains
the advice-selected option, while `modify` and `reject` require a difference reason. These commands
do not mutate the case, simulated decision, Action Plan, Outcome, or Project truth. The
evaluation-response record is an engineering proxy only, not approval or company-system write-back.

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
OPS-B made this authoring/validation contract executable while leaving current
`observable-case.v1`, runtime repositories and Project HTTP resources unchanged.

OPS-B authoring terms are:

```text
ProjectLifecycleStage = SPEC_DEFINITION | PRE_SILICON_CLOSURE | MASS_PRODUCTION
EvidenceStatus        = REQUESTED | LATE | RECEIVED
MilestoneStatus       = PLANNED | AT_RISK | ACHIEVED
```

Source fixtures record ordinal downside, blast radius, urgency and reversibility inputs, but never
assign `ProjectAttention`, `RiskLevel` or a composite risk score.

OPS-C makes the following read-only routes executable. They do not accept Project truth mutations:

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
An out-of-range Step returns `PROJECT_STEP_OUT_OF_RANGE`; unknown Project and Risk resources return
`PROJECT_NOT_FOUND` and `PROJECT_RISK_NOT_FOUND` respectively.

The response contracts are:

```text
GET /api/v1/projects                                      -> project-list-item.v1[]
GET /api/v1/projects/{project_id}/situation               -> project-situation.v1
GET /api/v1/projects/{project_id}/risks                   -> project-risk-summary.v1[]
GET /api/v1/projects/{project_id}/risks/{risk_id}         -> project-risk-detail.v1
GET /api/v1/projects/{project_id}/timeline                -> project-timeline.v1
```

Project attention uses `project-attention.v1`; Risk level and ordering use
`project-risk-order.v1`. Every result carries reason codes and source references. These policies use
explicit ordinal fields and never expose or calculate a composite score.

`observable-case.v1` remains unchanged. OPS-C preserves compatibility by keeping Project-to-Case
references inside `development-project.v1`; adding required Project fields to existing DecisionCase
payloads would require a new major version and is not part of OPS-C. PostgreSQL migration
`0020_development_projects` persists the new aggregate independently. ADR-0010 owns the full semantic
boundary and transition sequence.

UX-J migration `0021_decision_responses` separately persists evaluation-only pre-advice and
post-advice responses. ADR-0011 owns its disclosure, immutability, and non-authority boundary.

## 11. Accepted ENT-A enterprise source boundary

ADR-0012 accepts `enterprise-source-record.v1` as the only input envelope for future enterprise
source adapters. It is an application contract, not a canonical Project aggregate and not an Agent
packet.

Stable source identity is:

```text
(source_system, source_tenant, source_object_type, external_id)
```

`external_version`, title, URL, content hash and payload never participate in identity. The record
uses these required fields:

```text
schema_version = enterprise-source-record.v1
source_system
source_tenant
source_object_type
external_id
external_version
effective_at
observed_at
source_updated_at
ingested_at
content_hash
source_url
deletion_state
source_acl_ref
classification
payload
```

Canonical enum values are:

```text
SourceDataClassification = PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED
SourceDeletionState       = ACTIVE | DELETED | RESTRICTED
```

All four times require a timezone. They retain separate meanings and have no implicit ordering:
`effective_at` is business validity, `observed_at` is organizational observability,
`source_updated_at` is source-asserted modification time, and `ingested_at` is twin capture time.
Local simulation continues to use `at_step`; it is not converted implicitly to these timestamps.

`ACTIVE` requires a JSON object payload. `DELETED` and `RESTRICTED` forbid payload. Every record
requires an opaque ACL reference and classification; neither field grants access by itself.
Embedded URL credentials are forbidden.

The application ports are `SourceReader.read(identity)` and `IngestionSink.write(record)`. ENT-A adds
no executable source adapter, HTTP route, persistence, mapping, sync, authentication, real ACL or
write-back. Raw enterprise records never enter an `ObservableCasePacket` or become Project/FACT truth.

## 12. Accepted ENT-B mapping candidate boundary

ADR-0013 accepts the following contract names:

```text
enterprise-mapping-registry.v1
enterprise-mapping-result.v1
enterprise-dirty-fixture-corpus.v1
```

The mapping registry resolves one exact `(source_system, source_object_type)` key to a versioned
profile. A profile declares required source fields, direct field mappings, optional status mapping,
unstructured extraction rules and late-arrival threshold. It does not contain company field IDs.

Mapping produces candidates, not canonical truth:

```text
StructuredCandidateKind   = PROJECT | WORK_ITEM | ISSUE | EVIDENCE | EVENT
UnstructuredCandidateKind = CLAIM | RISK | ASSUMPTION
CandidateReviewStatus     = UNREVIEWED
MappingDisposition        = ACCEPT | QUARANTINE | REJECT
```

Every structured candidate requires source identity/version, mapping profile/version, mapped values
and JSON-pointer source spans. Every unstructured candidate also requires extractor version and
character offsets. Unstructured candidates cannot use `FACT` or a reviewed state.

`ACCEPT` means candidate generation only and never authorizes canonical import. `QUARANTINE` requires
later resolution. `REJECT` produces no candidate. Canonical reason codes are:

```text
MAPPED
PROFILE_NOT_FOUND
REQUIRED_FIELD_MISSING
STATUS_UNMAPPED
DUPLICATE_SOURCE_VERSION
SOURCE_VERSION_CONFLICT
OUT_OF_ORDER_SOURCE_UPDATE
SOURCE_URL_CHANGED
SOURCE_DELETED
SOURCE_RESTRICTED
LATE_ARRIVAL
```

Deleted and restricted source records create metadata-only `EVENT` candidates. ENT-B adds no HTTP
route, persistence, canonical Project mutation, Agent input, authentication, real ACL, sync, durable
quarantine or write-back.

## 13. Accepted ENT-C sync and reconciliation boundary

ADR-0014 accepts:

```text
enterprise-sync-checkpoint.v1
enterprise-sync-result.v1
enterprise-sync-fixture-corpus.v1

EnterpriseSyncMode        = FULL | INCREMENTAL
EnterpriseSyncStatus      = COMPLETED | PAUSED | FAILED
EnterpriseSyncDisposition = APPLIED | NO_CHANGE | QUARANTINED | REJECTED

MAPPING_APPLIED
CONTENT_UNCHANGED
STALE_SOURCE_UPDATE
TOMBSTONE_APPLIED
ACCESS_RESTRICTION_APPLIED
```

The checkpoint records the next page index/token, last committed cursor, stable-identity source
states, deterministic record audit and bounded retry audit. A checkpoint advances only after a whole
page is reconciled. A completed checkpoint replay is an exact no-op.

Identity/version/hash repetition is `NO_CHANGE`; a version/hash conflict is `QUARANTINED`. Unchanged
content does not increment `mapping_revision`. Active content older than the maximum reconciled
`source_updated_at` is quarantined. `DELETED` and `RESTRICTED` metadata records take precedence over
later-arriving stale active content. Late-arrival retains ENT-B's `LATE_ARRIVAL` audit reason.

`EnterpriseSyncPolicy` declares maximum page attempts and each backoff duration. The reference
engine records schedules but does not sleep. Exhaustion returns the same page token with `FAILED`.
`mapping_revision` is only candidate-state revision inside this checkpoint; it is not canonical
Project/Event persistence.

ENT-C adds no route, database, canonical import, durable quarantine, vendor adapter, real ACL,
credential, company data, Agent input or write-back.

## 14. Accepted ENT-D dry-run and review boundary

ADR-0015 accepts:

```text
enterprise-dry-run-input.v1
enterprise-resolution-file.v1
enterprise-dry-run-report.v1

CanonicalChangeAction     = CREATE | UPDATE | DELETE | NO_CHANGE
EnterpriseDryRunStatus    = READY_FOR_REVIEW | BLOCKED
EnterpriseQuarantineStatus = OPEN | RESOLUTION_PROPOSED
```

Canonical quality codes are:

```text
DANGLING_REFERENCE
TIME_AMBIGUITY
UNMAPPED_FIELD
ACL_REFERENCE_UNKNOWN
STALE_SOURCE
MAPPING_QUARANTINED
MAPPING_REJECTED
```

The report compares current ENT-C candidate state with an explicitly supplied synthetic snapshot and
records deterministic before/after proposals. Every finding declares whether it blocks import.
Blocking findings become quarantine entries without removing unrelated valid proposals.

Resolution actions are `EXCLUDE_SOURCE | SOURCE_FIXED | MAPPING_UPDATED | ACKNOWLEDGE_RISK`.
A resolution is only `RESOLUTION_PROPOSED`; unknown quarantine IDs or mismatched content hashes fail.
It never authorizes import.

Every `enterprise-dry-run-report.v1` fixes `write_performed=false` and
`canonical_import_authorized=false`. `soc-ot enterprise validate-source` validates input contracts.
`soc-ot enterprise dry-run --output <report.json>` writes only the requested report and does not open
the runtime database.

ENT-D adds no canonical Project/Event mutation, durable queue, API route, vendor adapter, real ACL,
credential, company data, Agent input or write-back.

## 15. Accepted ENT-E security and operation emulator boundary

ADR-0016 accepts:

```text
enterprise-security-operation-policy.v1
enterprise-security-operation-scenario-corpus.v1
enterprise-security-operation-report.v1

EnterpriseExposureSurface = FRONTEND | API | MODEL | ROLE_PACKET | LOG
EnterpriseExposureMode    = FULL | METADATA_ONLY | DENY
EnterpriseAccessDecision  = ALLOW | DENY
```

Missing ACL, unknown principal, allow/deny conflict, no allow match, inactive source and classification
denial all fail closed. `RESTRICTED` denies every surface. Exposure records contain a hash reference,
not raw identity, URL, or payload. The classification matrix is total across all four classifications
and five surfaces.

```text
EnterpriseIncidentType =
  HEALTHY | LAG | STALE | RATE_LIMITED | PARTIAL_SOURCE | UNKNOWN_FRESHNESS
EnterpriseHealthStatus    = HEALTHY | DEGRADED | NOT_READY
EnterpriseReadinessStatus = READY | NOT_READY
EnterpriseRecoveryAction  =
  NONE | WAIT_BACKOFF | FULL_RECONCILIATION |
  RETRY_MISSING_PARTITION | ESCALATE_SOURCE_OWNER
```

Only complete, known-freshness HEALTHY input within the lag threshold is READY/current. Unknown
freshness is never current. Diagnostic redaction covers configured field names, Bearer/token/secret
assignments and URL user-info recursively. Audit contains only hashes and compact outcomes.

Every report fixes `real_authorization_performed=false` and `credential_persisted=false`.
`soc-ot enterprise emulate-security --output <report.json>` writes only a synthetic report and opens
no runtime database.

ENT-E adds no real authentication/authorization, company principal/group, inherited ACL, vendor
credential, canonical import, API route, monitoring service, Agent input or write-back.

## 16. Accepted ENT-F enterprise handoff boundary

ADR-0017 accepts:

```text
enterprise-handoff-mapping-template.v1
enterprise-environment-worksheet.v1
enterprise-pilot-runbook.v1
enterprise-handoff-package.v1

HandoffSourceKind       = WORK_TRACKER | KNOWLEDGE_BASE
HandoffValueOwnership   = EXTERNALLY_VERIFIED | INTERNAL_REQUIRED
HandoffCheckStatus      =
  VERIFIED_EXTERNALLY | UNCONFIRMED_INTERNAL | NOT_APPLICABLE | NOT_EVALUATED
HandoffRunbookStage     = VALIDATE | DRY_RUN | REVIEW | IMPORT | RECONCILE
HandoffStageAuthority   = EXTERNAL_EXECUTABLE | COMPANY_APPROVAL_REQUIRED
HandoffGateDecision     = CONTINUE | STOP | NOT_EVALUATED
```

Mapping templates fix canonical targets while source system, mapping version, fields and statuses
remain `INTERNAL_REQUIRED`. The environment worksheet holds no company value or credential value.
Internal items are null and `UNCONFIRMED_INTERNAL`; external items require a repository evidence
reference and `VERIFIED_EXTERNALLY`.

The pilot scope fixes `max_project_count=1`, `read_only=true`, `write_back_enabled=false` and
`canonical_import_authorized=false`. The stage order is immutable. Only VALIDATE, DRY_RUN and REVIEW
ship executable local commands. IMPORT and RECONCILE are `COMPANY_APPROVAL_REQUIRED` and have no
command before internal C0/C1.

`enterprise-handoff-package.v1` fixes `package_status=READY_FOR_INTERNAL_DISCOVERY`,
`live_use_authorized=false`, `company_data_included=false`, `credential_value_included=false` and
`write_back_implemented=false`, and pins every child artifact by SHA-256.
`soc-ot enterprise validate-handoff` validates this package without opening a database or network
connection and without writing an output.

ENT-F adds no vendor adapter, company field, user/group, real ACL, authentication, secret store,
credential, canonical import, API route, Agent input, durable queue, reconciliation service or
write-back. `READY_FOR_INTERNAL_DISCOVERY` is not live readiness.

## 17. Compatibility gate

Any change to a state code, DecisionType, endpoint, time field, or version name updates this contract first. CI then checks generated schemas, OpenAPI, Frontend client, fixture manifests, runbook examples, and documentation references.
