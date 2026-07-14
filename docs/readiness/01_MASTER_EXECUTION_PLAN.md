# Master execution plan

> Status: IMPLEMENTED THROUGH I7 REPLAY + POST-I7 STEP 3 EVALUATION CORPUS V2; I7 LIVE GATE PENDING EXTERNAL INPUT
> Date: 2026-07-14
> Scope: local fixture-only PoC

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
