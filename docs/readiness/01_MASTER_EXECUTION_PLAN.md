# Master execution plan

> Status: IMPLEMENTED THROUGH I7 REPLAY + STEP 5 B2 RUNTIME + UX-K LOCAL FIXTURE UX RELEASE 1 + ENT-A/B; OPS-F HUMAN OBSERVATION DEFERRED AT 0/5 PER CONDITION, ENT-C NEXT
> Date: 2026-07-25
> Scope: local fixture-only PoC

Frozen follow-up order: `OPS-F human observations deferred → UX-I complete → UX-J → UX-K Local UX Release 1 →
ENT-A~F fixture-only enterprise preparation → internal C0/C1`. No enterprise preparation implementation
starts before UX-K, and no actual company source, vendor API, credential, authentication or write-back
enters the local repository.

## 1. Purpose

This document is the implementation authority for repository layout, execution order, technology choices, and I0–I7 stage gates. `PROJECT_PLAN.md` owns product scope and value hypotheses. The subject-specific readiness contract owns its domain details.

## 2. Document ownership

- `PROJECT_PLAN.md` owns product goal, scope, value hypotheses, and stop criteria.
- `00_IMPLEMENTATION_READINESS_RESULT.md` reports status and does not override a contract.
- This document owns repository structure and I0–I7 execution.
- `02` through `08` own their named contract subjects.
- The two 2026-07-11 `internal_docs` files are supporting design references.
- Older ideation documents are historical context only.

Use `docs/PLAN_INDEX.md` to find the owning document before changing a decision.

## 3. Fixed product boundary

```text
Primary user:
  Multimedia System/Architecture Reviewer

First workflow:
  Video Recording Scenario Change Review

First case:
  CASE-VR-001 UHD60 EIS power-gap decision

Data:
  synthetic fixture only

Home approval:
  simulated Decision Chair decision

Company approval:
  future human authority, out of local scope
```

## 4. Fixed technology choices

|Area|Decision|
|---|---|
|Backend|Python 3.11+, FastAPI, Pydantic v2|
|Persistence|PostgreSQL, SQLAlchemy, Alembic|
|Fixture|YAML source with Pydantic validation and generated JSON Schema|
|Frontend|React 19, TypeScript, Vite 8, React Router 8, TanStack Query|
|Frontend test|Vitest 4, React Testing Library, Playwright|
|Agent CI provider|ReplayProvider, no network/API key required|
|First live provider|OpenAI Responses API adapter|
|Background work|Separate Python worker backed by PostgreSQL run records|
|Progress|SSE with polling fallback|
|Graph/vector DB|Not used in MVP|
|Deployment|Local Windows host plus Docker Compose PostgreSQL|

## 5. Canonical repository layout

```text
/
├─ README.md
├─ AGENTS.md
├─ PROJECT_PLAN.md
├─ pyproject.toml
├─ uv.lock
├─ alembic.ini
├─ .env.example
├─ .gitignore
├─ backend/
│  ├─ src/soc_ot/
│  │  ├─ domain/
│  │  ├─ application/
│  │  ├─ agents/
│  │  ├─ infrastructure/
│  │  ├─ api/
│  │  ├─ worker/
│  │  └─ cli/
│  └─ tests/
├─ frontend/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ src/
│  │  ├─ app/
│  │  ├─ features/
│  │  ├─ api/
│  │  ├─ components/
│  │  └─ design/
│  └─ tests/
├─ contracts/
│  ├─ generated/
│  └─ snapshots/
├─ fixtures/
│  ├─ world/
│  ├─ cases/observable/
│  ├─ cases/development/
│  ├─ cases/hidden/
│  ├─ expected/
│  ├─ manifests/
│  └─ dictionaries/
├─ migrations/
├─ deploy/local/
├─ docs/
│  ├─ readiness/
│  ├─ architecture/
│  ├─ decisions/
│  ├─ agents/
│  ├─ evaluation/
│  ├─ ui/
│  └─ operations/
├─ internal_docs/
├─ output/
└─ scripts/
```

Do not create duplicate `src/soc_ot`, `ui`, or top-level `tests` trees.

## 6. Canonical implementation stages

### I0. Repository and quality scaffold

Deliver:

- canonical folders
- Python and Frontend package scaffold
- lint/type/test commands
- `.env.example`
- local Docker Compose PostgreSQL
- `AGENTS.md`

Gate:

- empty Backend and Frontend test commands pass
- PostgreSQL health check passes
- no API key is required

### I1. Domain, contracts, and CASE-VR-001 source fixture

Deliver:

- development/decision domain models
- atomic Claim contract and canonical enums
- logical simulation clock and quantity model
- observable/hidden models
- YAML loader and validation
- CASE-VR-001 observable/hidden/expected fixture
- in-memory repository for unit tests

Gate:

- invalid transitions, invalid units, dangling references, hidden leakage fail tests
- CASE-VR-001 state can be reconstructed by simulation step

### I2. PostgreSQL and read projection

Deliver:

- migrations
- PostgreSQL repositories
- repository parity tests
- current state plus append-only event transaction
- `DecisionWorkspaceProjection`
- fixture import command

Gate:

- in-memory and PostgreSQL query results match
- API restart preserves imported case state
- current row and domain event commit atomically

### I3. Read-only API and Korean Frontend

Deliver:

- decision list/workspace APIs
- deterministic `BuildObservableCasePacket`
- deterministic impact/dependency/deadline traversal
- evidence eligibility, provenance, assumption, and uncertainty projection
- reversibility/detectability/recoverability projection
- packet hash and hidden-field denylist validation
- OpenAPI-generated Frontend client
- `/decisions`, `/decisions/:caseId`, `/dev/fixtures`
- Korean labels, loading/empty/error/stale states
- CASE-VR-002 through CASE-VR-005 and CASE-HO-001 through CASE-HO-003
- frozen validation/sealed-unseen manifest before any live prompt tuning

Gate:

- the I3 usability questions in `02_UI_PERSONA_AND_APPROVAL_BOUNDARY.md` can be answered without raw JSON or ontology graph
- hidden outcome is absent from every user response
- the 8-case evaluation corpus validates and its frozen hashes match the manifest
- Role, Challenger, and Chair inputs can be built only through `BuildObservableCasePacket`

### I4. Agent runtime, worker, and progress

Deliver:

- ReplayProvider
- OpenAI Responses API adapter
- durable `agent_runs` worker
- PostgreSQL lease claim and crash recovery
- role routing and single-role review
- SSE and polling fallback
- Agent progress, partial-failure, retry UI
- provider-attempt start/final audit
- role, revision, Challenger, and Chair logical checkpoints
- timeout, bounded transport/schema/policy retry, and pre-execution budget enforcement

Gate:

- replay is deterministic
- worker restart resumes or safely fails claimed runs
- accepted logical steps are not repeated after lease reclaim
- lease expiry, duplicate completion, and cancellation-race tests pass
- unsupported authoritative claims cannot enter accepted RoleReview

### I5. Multi-role Dossier and Decision Chair

Deliver:

- independent role round
- provider Challenger and bounded provider revision
- Decision Dossier
- simulated provider Decision Chair
- decision policy validator
- B0/B1/B2/B3 ablation runner
- agreement/dissent, simulated decision, safeguard UI sections

Gate:

- dissent remains visible
- conditional decisions include guardrail, rollback trigger, owner, and verification
- Decision Chair cannot access hidden repository
- Chair is independently audited and its accepted result is durably checkpointed
- B0–B3 execute through one evaluation interface; Replay mode does not claim marginal Agent value

### I6. Outcome and evaluation

Deliver:

- closed-world OutcomeRule registry
- simulation step advancement
- hidden evidence reveal
- Process and Outcome evaluation
- development/validation/sealed-unseen evaluation runner
- Outcome and Process/Outcome evaluation UI sections

Gate:

- all 8 frozen cases complete their required evaluation path
- all deterministic and Replay validation/sealed-unseen gates pass

### I7. Hardening and usability

Deliver:

- accessibility and E2E
- performance and cost telemetry
- failure recovery
- live B0–B3 ablation
- validation x5 and sealed-unseen x3 live stability evaluation
- local runbook verification
- `simulated-decision.v2` executable next-action contract and Korean UI projection
- typed `development-event.v1` history, historical state reconstruction, and blocker propagation
- independent development fixtures for interface rework, measurement delay, technical debt, and shared-resource conflict
- Korean development timeline projection without raw ontology exposure
- 12-case `eval-2026-07-14.2` with new validation/sealed partitions and explicit source hashes
- type-specific action-plan and development-history evaluation gates
- adjacent B1/B0, B2/B1, and B3/B2 topology delta evaluation
- explicit `keep_b3`, `release_b2`, `release_b1`, or `release_b0` selection artifact
- explicit selected-topology stability CLI and topology-aware semantic-call estimate
- durable dossier topology across enqueue, PostgreSQL persistence, retry, and execution
- B2 runtime activation with deterministic core decision and legacy B3 compatibility migration

Gate:

- I7 usability task passes all eight questions
- validation live stability, sealed-unseen robustness, cost envelope, and policy gates pass
- multi-role topology is kept, simplified, or removed according to the ablation stop rule
- secret/hidden scans and worker recovery E2E pass
- the local runbook succeeds from a clean checkout without an API key in Replay mode
- known limitations are recorded
- every DecisionType emits a type-correct action plan with owner, due step, trigger, verification, and fallback
- one event history reconstructs at least three consistent steps and historical Agent packets exclude future observations
- each active blocker reports downstream work and milestone impact deterministically
- prior opened cases are regression-only and cannot be labeled fresh validation or sealed evidence
- v1 and v2 manifests validate independently while v2 Replay passes 12/12
- B2 and B3 require marginal value in at least 3 of 4 fresh v2 cases without Process regression
- the selected topology passes every fresh-case Process gate or the release gate fails
- a selected topology remains a candidate until its validation and sealed stability gates pass

Step 5 activation record (2026-07-15):

- Step 4 selected B2 with `release_b2` after B2/B1 4/4 and B3/B2 0/4
- B2 validation passed 10/10 acceptable and 10/10 policy compliant
- B2 sealed-unseen passed 6/6 acceptable and 6/6 policy compliant
- new durable dossier runs persist and execute B2; pre-Step-5 dossier rows migrate to B3
- PostgreSQL migration head is `0021_decision_responses`

Post-I7 UX-A record (2026-07-17):

- generated `decision-workspace.v2` and `workspace-ux-fixture.v1` contracts
- CASE-VR-001 phase content fixture without changing frozen evaluation fixtures or manifests
- selected-step, causal-chain, commitment-window, expected/observed/hidden boundaries
- canonical phase primary actions and Korean labels
- UX-B consumes these boundaries without changing the frozen evaluation corpus

Post-I7 UX-B record (2026-07-17):

- generated `decision-list-item.v1` contract and consumer-shaped collection response
- Backend-owned attention order, action-needed group, deadline, critical blocker propagation,
  milestone impact, why-now explanation and next-action label
- Korean Decision Inbox with one primary action, no raw ID, and no normal-user fixture navigation
- responsive loading, empty and recoverable error states with mobile accessibility coverage
- UX-C replaces the detail response with the approved `decision-workspace.v2`
- run-aware `IN_REVIEW` and persisted list freshness remain explicit follow-up boundaries

Post-I7 UX-C record (2026-07-17):

- live `decision-workspace.v2` projection built from current or reconstructed observable case state
- optional Workspace `at_step` with validated earliest/latest boundary and no future workflow state
- validated UX content supplies commitment and expected-transition models only when compatible;
  unsupported cases return explicit unknowns instead of invented transitions
- Context Bar, phase-adaptive Decision Brief, Development Twin, causal chain, commitment window,
  Decision Posture and visually separate expected/observed transition cards
- responsive 390px layout keeps the primary action before why-now and has no page overflow
- decision-linked observed transitions remain a later integration boundary

Post-I7 UX-D record (2026-07-17):

- latest case-scoped durable Dossier and run status joined into the current Workspace projection
- Backend-owned equal-dimension option comparison with no score or automatic final rank
- agreement, key dissent, confirmation and Challenger-change groups before Role originals
- selected-Step eligible facts/inferences and current-only assumption/unknown boundary
- semantic desktop comparison table and no-overflow 390px option cards
- raw Role IDs and provider/token/cost detail absent from the normal user deliberation flow
- decision-linked safeguards, single phase action and expectation-versus-actual remain UX-E

Post-I7 UX-E record (2026-07-17):

- current Workspace joins the latest durable simulated decision, outcome and evaluation
- Action Plan, owner, due Step, verification, fallback, Safeguard threshold, Rollback trigger and
  residual risk are connected in one actioning flow
- each phase exposes exactly one Backend-owned primary action; single-Role experiments remain out
  of the normal user workflow
- pre-reveal outcome remains hidden; after explicit Step advance, expected and actual results,
  Guardrail execution and event-backed observed transitions are shown separately
- Process and Outcome evaluations remain separate and the historical Workspace omits all later
  decision, outcome, evaluation and run state
- UX-F is implemented as a separately recorded post-I7 Responsive, accessibility and usability Gate

Post-I7 UX-F record (2026-07-17):

- responsive 390px, 768px, desktop and 200%-equivalent 640 CSS-pixel reflow have no page overflow
- one skip link, one main landmark, section focus management, reduced motion, 44px targets, semantic
  table/heading/live-region structure and axe checks pass
- partial run recovery preserves completed perspectives, translates failure reason, offers retry and
  blocks Chair; aggregate conflict projects stale state and refreshes the current Workspace
- frozen CASE-VR-001 canonical 8 + Development Twin 5 task answers pass with zero wrong primary clicks
  and no Role-original/raw ontology opens for questions 1–6
- historical Step, expected-versus-observed and hidden-outcome boundary tests pass
- this local agent-substitute Gate does not establish human task time, comprehension or business value

Post-I7 UX-G record (2026-07-19):

- network transport exceptions are normalized at the Frontend API boundary and normal UI renders only
  Korean reason, impact and recovery actions
- unavailable historical Step can return to the current view; 404 and retryable service failures have
  separate recovery paths
- selected observable Step and ordinal mobile alternative are URL-backed and restore through reload and
  browser history without exposing opaque option IDs
- supporting terminology and interactive states are improved without changing canonical actions,
  Backend projection rules, database schema or hidden boundaries
- UX-G does not establish human usability or business value; UX-H therefore owns the separate fair
  baseline and human-measurement boundary

Post-I7 UX-H implementation record (2026-07-19):

- `CASE-VR-001.baseline-pack.v1.yaml` resolves only allowlisted JSON pointers from the same
  hash-pinned observable fixture used by the product and renders a Jira/Confluence-shaped local pack
- `usability-study-protocol.v1` freezes both conditions, canonical 8 + Development Twin 5 tasks,
  independent participant kinds, exclusions and directional targets before human results
- `usability-session.v1` records timezone-aware task start/end, answer, wrong action, detail open,
  recovery, reviewer response, boundary classification and safeguard completeness
- `usability-study-summary.v1` separates builder from proxy/domain observations, reports condition
  metrics and never emits a passed human gate; below five independent observations per condition it
  returns `not_ready`, `not_evaluable` and `no_business_claim`
- the baseline pack, protocol, session preparation/validation and summary are authoring/evaluation
  CLI surfaces only; no product API, database, company connector, authentication or write-back changed
- implementation and synthetic dry-run validation are complete, but actual human observations remain
  zero; OPS-F protocol v2 is now the frozen Project-centered study material and UX-I remains blocked
  until its independent minimum is collected

Post-I7 OPS-A decision record (2026-07-21):

- ADR-0010 accepts Project Portfolio → Project Situation → Issue/Risk Detail → existing Decision
  Workspace as the product flow; the current Workspace is preserved rather than replaced
- `DevelopmentProject`, observed `DevelopmentIssue`, future `ProjectRisk`, Milestone/Gate and
  provenance boundaries are fixed before fixture or API implementation
- Backend owns Project attention, Risk level, ordering and reason/source projection; Frontend and
  unvalidated Role output do not calculate or mutate Project truth
- `development-project.v1` and Project routes/resources are reserved names but remain non-executable
  until their OPS-B/OPS-C Gates pass
- the external `world.yaml` SHA-256 is recorded for traceability; only selected event ideas that improve
  OPS-B UX coverage may be adapted, with no fixed event count, runtime dependency, verbatim import,
  risk score, dice or long Role LLM prose
- existing UX-H observations remain zero; human session execution was paused until OPS-F protocol v2
  was frozen, and new Project-centered observations must now use that v2 material

Post-I7 Project Operations stages run in this order:

|Stage|Deliverable|Gate|
|---|---|---|
|OPS-A|Scope, semantic boundaries, reserved vocabulary and ADR|Complete: ADR-0010 Accepted|
|OPS-B|Lifecycle-distinct Project fixtures and event/risk provenance|Complete: 3 projects, 17 typed events, hash manifest and future-leakage tests|
|OPS-C|Project domain, projection, API and compatibility path|Complete: migration/repository parity, five read APIs, generated contracts and no-future-leakage parity|
|OPS-D|Portfolio and Project Situation UX|Complete (local proxy): overall status/top-risk/source task, responsive and accessibility checks pass|
|OPS-E|Risk Detail and Decision linkage|Complete (local proxy): source-to-inference-to-impact-to-treatment trace and Decision round trip pass|
|OPS-F|UX-H protocol v2, frozen product release and independent observations|Release/rubric/E2E tooling complete; human observation deferred at baseline 0/5 and product 0/5|

No later OPS stage starts before the previous Gate. Company connectors, authentication and write-back
remain C0/C2 scope.

After OPS-F, the only allowed order is:

|Stage|Deliverable|Gate|
|---|---|---|
|UX-I|Information architecture simplification|Complete as engineering-proxy: title-first projection, source interpretation, domain copy and full local regression; no human/time/value claims|
|UX-J|Separate immutable builder initial/final response from simulated advice|Complete: advice cannot overwrite builder response; accept/modify/reject and anchoring fields are measurable|
|UX-K|Freeze Local UX Release 1 across the full Project-to-Decision journey|Complete: responsive/accessibility/recovery/history/full-regression Gate and release pins pass|
|ENT-A|Source-neutral record, stable identity/time, access metadata and application ports|Complete: ADR-0012 accepted, strict contract/schema/boundary tests pass; no adapter or persistence|
|ENT-B|Versioned mapping registry, candidate provenance and dirty-source disposition|Complete: ADR-0013 accepted, 10 normal/dirty patterns and explicit accept/quarantine/reject pass|
|ENT-C~F|Sync/reconciliation, dry-run/quarantine, security emulator and internal handoff kit|ENT-C next; fixture-only tests, no vendor API, company data, credential or real ACL|
|C0/C1|Internal configuration, sanitized schema-fit, one-project read-only smoke and pilot|Company security, data owner and human authority approvals|

The detailed work packages and transition criteria are owned by
`internal_docs/26.07.23 UX 마무리 및 사내 데이터 전환 실행 계획.md`.

OPS-B implementation record (2026-07-21):

- `development-project.v1` is executable only as an authoring/validation contract; it is not yet a
  runtime aggregate or Project API
- PROJECT-U, PROJECT-V and PROJECT-W distinguish mass-production field evidence, pre-silicon
  commitment uncertainty and model/lesson-led specification work
- typed Issue/Risk/Evidence/WorkItem/Milestone/Action event chains validate current state and support
  a fixture-only historical reconstruction that hides future observations and evidence sources
- selected `world.yaml` top-level event patterns were rewritten as synthetic fixtures; the external
  file is not imported at runtime or during tests
- existing 12-case evaluation and UX-H baseline remain unchanged

OPS-C implementation record (2026-07-21):

- migration `0020_development_projects`, in-memory/PostgreSQL repository parity and restart-safe
  fixture imports make `development-project.v1` a durable runtime aggregate
- `project-attention.v1` and `project-risk-order.v1` derive attention, RiskLevel, ordering, reasons
  and source references without a composite score or Agent-owned truth
- Portfolio, Situation, Risk list/detail and Timeline read APIs are executable; every Project detail
  resource shares the fixture reconstruction boundary and stable error codes
- existing `observable-case.v1` remains unchanged; Project-to-Decision references provide a compatible
  one-way bridge until a future major DecisionCase contract is justified
- generated JSON Schema, OpenAPI and TypeScript contracts are synchronized; OPS-D is the first stage
  allowed to consume them in the product UI

OPS-D implementation record (2026-07-22):

- `/projects` is now the default product entry and preserves Backend attention/risk ordering rather
  than calculating a Frontend score; `/decisions` remains available as the existing bounded workflow
- Portfolio cards expose ProjectAttention, the Backend reason, top Risk, nearest milestone and counts;
  `/projects/:projectId` progressively discloses top-risk reasons, source provenance, affected work,
  blockers, tracks, milestones, Issue/Evidence state and recent Project events
- source references are presentation-joined only to currently visible Issue, Evidence and Timeline
  titles; canonical Risk, level, ordering and provenance remain Backend-owned
- `at_step` is URL-backed, all Situation and Timeline requests share the OPS-C historical boundary,
  and an unavailable Step returns to the current Project without rendering future state
- 4 focused unit tests cover Portfolio priority/reason, source-to-impact comprehension, historical URL
  restoration and fail-closed recovery; total Frontend unit count is 16
- existing 8 Decision-flow E2E tests pass; Playwright CLI inspection and Axe checks pass at 390px and
  desktop with zero overflow, accessibility violations, console errors or warnings
- this is a local agent-substitute task proxy, not measured human completion time or business value;
  Risk Detail and Decision navigation were deferred to and are now implemented by OPS-E

OPS-E implementation record (2026-07-22):

- `/projects/:projectId/risks/:riskId` presents one explicit trace in the order source Issue/Event/
  Evidence/cross-project lesson → epistemic status and inference basis → Backend ranking reasons and
  risk posture → affected WorkItem/Milestone → treatment Decision and Action
- the Frontend translates known rule and Evidence limitation codes for Korean-first reading while
  retaining canonical IDs as secondary provenance; it does not calculate Risk truth, rank or score
- Situation exposes every visible Risk and preserves historical `at_step` when opening Risk Detail;
  Risk Detail and Situation query the same selected Project Step and fail closed on unavailable history
- Decision navigation appends only validated origin context. Project Step is not forced onto a Decision
  Case whose timeline may differ; the existing Workspace preserves the context through its own URL
  interactions and returns to the exact current or historical Risk view
- 4 focused OPS-E unit tests cover the source/inference/impact/treatment trace, current and historical
  Decision links, and Workspace return context; total Frontend unit count is 19
- existing 8 Decision-flow E2E tests pass. A real fixture browser round trip passes at desktop and
  390px with zero horizontal overflow, Axe violations, console warnings or errors
- the two-minute trace Gate is an engineering agent-substitute proxy only. No human completion time or
  business value is claimed; OPS-F protocol v2 is now implemented and independent observations remain
  pending

OPS-F implementation record (2026-07-23):

- the Decision-centered `UX-H-20260719` protocol and baseline remain valid as v1; OPS-F adds separate
  `usability-study-protocol.v2` and `usability-project-baseline-pack.v2` contracts without rewriting
  prior study material or inventing participant results
- PROJECT-U/V/W are individually SHA-256 pinned after canonical `development-project.v1` validation;
  six Jira/Confluence-shaped surfaces expose only selected Project source paths and reject a stale hash,
  unknown Project, duplicate source or task answer source not exposed to the baseline condition
- 11 frozen tasks cover Portfolio priority, Project situation, observed Issue versus Risk/Evidence gap,
  epistemic differences, source provenance, affected objects, Decision/Action/rollback, Step 20 replay,
  future-information rejection and cross-project lesson context
- the product condition starts at `/projects`; both conditions receive the same frozen task guide,
  while only baseline receives the rendered raw-source pack. No expected answer, hidden outcome, Agent
  output, Dossier, simulated decision or company data is included
- session/event/summary v1 measurement semantics are reused because timing, answer, boundary, reviewer
  and safeguard fields did not change; v2 additionally rejects one participant completing both conditions
- CLI defaults now prepare OPS-F v2 sessions. A builder dry-run creates baseline/product drafts and
  reports `not_ready`, `not_evaluable`, `no_business_claim` with zero completed observations
- `usability-study-release.v1` pins the OPS-E product revision, `/projects` entry, Korean Chromium
  environment and every study-critical UI/API/material file by SHA-256; a changed or missing artifact
  blocks study validation and session preparation
- the participant-hidden `usability-reviewer-rubric.v1` freezes required findings and failure conditions
  in exact protocol task order; the CLI renders it separately from either participant condition
- summaries preserve draft and excluded counts plus frozen exclusion-reason attrition while only valid
  completed independent sessions contribute to timing and accuracy
- Project browser E2E covers Portfolio → Situation → Risk → Decision → Risk at desktop and Step 20
  no-future-leakage at 390px, including Axe and overflow checks
- protocol tooling is complete, but the OPS-F human Gate is not. Independent baseline/product counts
  remain 0/5 each; UX-I/J/K engineering-proxy work may proceed, while human UX and any decision-speed,
  advice-quality or business-value claim remain blocked
- company data remains outside OPS-F. Current canonical repositories/projections can be reused after
  ingestion, but a live connector is NO-GO until C0 defines enterprise identity/time, ACL, sync,
  deletion/retention and candidate-extraction review; sanitized export schema-fit is the first allowed step

UX-I implementation record (2026-07-24):

- the three predeclared engineering-proxy problems were raw nearest/next milestone IDs, raw attention
  source refs and implementation-centered `Backend/source reference/ordering policy` copy
- `project-list-item.v1` adds the consumer-shaped `nearest_milestone_title` while preserving the
  canonical ID; Situation resolves visible work, milestone, Issue, Risk, Evidence, Decision and Event
  refs to titles with an ID fallback for unknown refs
- Project attention, Risk ordering, historical `at_step`, source identity and Decision round trip did
  not change
- `UX-I-PRODUCT-87D49D7` pins product revision `87d49d7`, the changed UI/API artifacts and the
  unchanged OPS-F task/source/rubric material
- desktop and 390px browser checks passed with Axe, keyboard skip-link, overflow, console and full
  Project-to-Decision regression; these are local engineering results, not human usability evidence

UX-J implementation record (2026-07-24):

- ADR-0011 separates unchanged Demo mode from URL-backed `interaction=evaluation` mode
- the evaluation sequence stores immutable initial builder judgment, server-resolved advice reveal
  snapshot and final `accept | modify | reject` judgment without mutating simulated decision or truth
- the server fixes `participant_kind=builder` and `interpretation=engineering_proxy_only`; client
  input cannot claim human authority, approval or company-system write-back
- `decision-evaluation-response.v1` and three command contracts use version checks, idempotency,
  phase ordering and allowed-option validation
- PostgreSQL migration `0021_decision_responses` preserves the sequence across restart with
  in-memory parity
- `UX-J-PRODUCT-218C095` pins product revision `218c095`, Decision UI/API contracts and unchanged
  OPS-F study materials
- backend 166 non-PostgreSQL plus 12 PostgreSQL tests, 22 Frontend unit tests and 11 browser E2E
  tests passed; UX-J 390px flow passed Axe, overflow, reload and console checks
- human observations remain baseline 0/5 and product 0/5; no human UX, decision-speed, anchoring or
  business-value claim is opened

UX-K implementation record (2026-07-24):

- one browser journey now covers Portfolio → Project Situation → Risk provenance and impact →
  Decision evaluation mode → immutable initial builder response → advice reveal →
  accept/modify/reject → Outcome/Evaluation → original Risk context
- the closed-workspace learning action always has a focusable destination; when a fixture has no new
  lesson, the UI states that explicitly instead of exposing an action with no target
- 390px, 768px, desktop and 200%-equivalent reflow, keyboard/focus/landmarks, Axe, reduced motion,
  loading/empty/partial/stale/conflict/network/unavailable-history and current/historical boundaries
  remain covered by unit and browser regression
- `LOCAL-UX-RELEASE-1-5227D18` pins product revision `5227d18`, the complete Project/Decision UI path,
  API contract, OPS-F protocol/baseline/rubric and full-journey browser specifications by SHA-256
- this is only a Local fixture UX Release 1 engineering Gate. Human observations remain 0/5 per
  condition, so human usability, decision speed, advice quality and business value remain NO-GO
- UX-K closes the UX stage sequence. ENT-A is next, but requires its own accepted ADR and remains
  source-neutral and fixture-only; no company source, vendor API, credential, authentication or write-back

ENT-A implementation record (2026-07-24):

- ADR-0012 accepts `enterprise-source-record.v1` as a staging envelope before any canonical Project
  mapping; direct source-to-Project conversion remains forbidden
- stable identity is `(source_system, source_tenant, source_object_type, external_id)` and remains
  unchanged across rename, update and delete records
- `effective_at`, `observed_at`, `source_updated_at` and `ingested_at` remain separate timezone-aware
  fields without an invented ordering between planned and late-arriving source states
- every record requires lowercase SHA-256 content identity, read-only source URL, opaque ACL reference
  and `PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED` classification
- `DELETED` and `RESTRICTED` envelopes cannot carry payload; embedded URL credentials and unknown
  fields fail validation
- `SourceReader` and `IngestionSink` are application Protocols over the validated envelope only; ENT-A
  adds no HTTP route, database migration, source adapter, mapping, sync, authentication or write-back
- generated schema, 15 focused tests, contract/architecture/plan/hidden/secret checks and the full
  non-PostgreSQL regression pass; ENT-B synthetic dirty fixture and mapping registry is next

ENT-B implementation record (2026-07-25):

- ADR-0013 accepts `enterprise-mapping-registry.v1`, `enterprise-mapping-result.v1` and
  `enterprise-dirty-fixture-corpus.v1`; mapping outputs candidates and never mutates canonical truth
- five synthetic profiles map generic project/work-item/issue/event/page records to versioned
  PROJECT/WORK_ITEM/ISSUE/EVENT/EVIDENCE candidates; direct/status field mappings and late-arrival
  policy are explicit and reproducible
- structured candidates require source identity/version, mapping profile/version and JSON-pointer
  spans; unstructured CLAIM/RISK/ASSUMPTION candidates additionally require extractor version,
  character offsets and fixed `UNREVIEWED` status, with no invented FACT or confidence
- the hash-pinned corpus covers normal, missing field, unknown status, duplicate, out-of-order, moved,
  deleted, restricted, conflicting and late-evidence patterns with frozen dispositions and reasons
- deleted/restricted inputs expose no source payload and create metadata-only EVENT candidates;
  tombstone application and reconciliation remain ENT-C
- 15 focused tests plus full non-PostgreSQL regression, generated-contract, architecture, plan,
  hidden, secret and fixture-hash checks pass; no API, database, Frontend, vendor adapter or company data
- ENT-C cursor, idempotency, retry, tombstone application and full/incremental reconciliation is next

## 7. Crosswalk to supporting plans

|Canonical|Role/Domain supporting topic|Technical supporting section|
|---|---|---|
|I0|Step 0 product/domain context|I0 support|
|I1|Step 1 and CASE-VR-001 in Step 2|I1 support|
|I2|No execution authority in Role design|I2 support|
|I3|Observable packet and Step 7 read-only slice|I3 support|
|I4|Step 3|I4 support|
|I5|Step 4 and Step 5|I5 support|
|I6|Step 6|I6 support|
|I7|Step 8|I7 support|

## 8. Module ownership

|Concern|Owner module|
|---|---|
|State transitions and invariants|`backend/src/soc_ot/domain`|
|Use-case transactions and allowed actions|`backend/src/soc_ot/application`|
|Prompts, providers, routing, Chair|`backend/src/soc_ot/agents`|
|PostgreSQL, fixture, OpenAI, job adapters|`backend/src/soc_ot/infrastructure`|
|HTTP and SSE|`backend/src/soc_ot/api`|
|Job claim/checkpoint/recovery|`backend/src/soc_ot/worker`|
|User workflow UI|`frontend/src/features`|
|Static Korean enum labels|`frontend/src/design`|

## 9. Implementation rules

- Domain must not import FastAPI, SQLAlchemy, LLM SDK, or UI labels.
- Frontend must not calculate risk, readiness, role agreement, or allowed actions.
- Agent output is candidate data until policy and schema validation pass.
- Hidden repositories are never dependencies of Role Agent or Chair modules.
- PostgreSQL is required before implementing durable Agent runs.
- Every state-changing command uses expected `aggregate_version` and idempotency key.
- Existing code in `E:\56_Codex_SoC_Operational_Ontology` is not copied before an ADR and new acceptance tests.

## 10. Start authorization

Implementation may start at I0 when `00_IMPLEMENTATION_READINESS_RESULT.md` reports all P0 items closed. P1 items may not block I0/I1 unless the index explicitly marks them blocking, but all P1 items must close before I4 live Agent execution.
