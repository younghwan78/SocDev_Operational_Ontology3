# Implementation status

> Updated: 2026-07-25
> Current stage: ENT-B mapping registry and dirty fixture corpus complete; OPS-F human observation deferred at baseline 0/5 and product 0/5; ENT-C next
> Planned sequence: ENT-C~F external fixture-only preparation → internal C0/C1; human/value claims remain blocked

## Stage evidence

|Stage|Status|Evidence|
|---|---|---|
|I0|Passed|Canonical scaffold, locked Python/Node installs, PostgreSQL health, quality commands, no-key Replay startup|
|I1|Passed|CASE-VR-001 contracts plus invalid transition/unit/reference/leakage tests and step reconstruction|
|I2|Passed|Alembic 0001–0019, memory/PostgreSQL parity, atomic case/event writes, restart persistence, fixture import, legacy B3 topology migration|
|I3|Passed|Deterministic packet/impact traversal, denylist, epistemic projection, frozen 12-case v2 manifest, generated OpenAPI client, Korean responsive UI|
|I4|Passed (Replay)|Replay/OpenAI adapters, provider-attempt start/final audit, role/revision/Challenger/Chair checkpoints, crash resume, lease heartbeat/reclaim, bounded transport/schema/policy retry, timeout/cancel, budget plan, SSE/polling, stale/partial/retry UI|
|I5|Passed (Replay)|True B0–B3 boundary, independent roles, provider Challenger, at most two provider revisions, dissent-preserving Dossier, policy-validated provider Chair, durable idempotent decision, executable safeguards|
|I6|Passed|Closed-world outcome rules, persisted idempotent step advance and evaluation, latest evaluation query, pre-reveal API denial, hidden access port, 12/12 Process/Outcome Replay evaluation|
|I7 Replay|Passed|104 Backend tests, 3 Frontend unit tests, 2 Playwright E2E, migration 0019 paths, scans, immutable evaluation artifacts, 12/12 Replay|
|I7-C Codex CLI|Passed for B2 release|Frozen v2 ablation selected B2 (B2/B1 4/4, B3/B2 0/4). B2 validation 10/10 and sealed-unseen 6/6 passed with zero policy/runtime failures. See `../../internal_docs/26.07.15 Step 5 B2 Stability 및 Runtime 활성화 구현 보고서.md`.|
|I7 Responses API|Not executed|The optional API billing/cost/latency surface still requires a user-supplied key, current rates, and explicit cost acknowledgement. It is not inferred from Codex CLI evidence.|
|Post-I7 UX-A|Passed|Generated `decision-workspace.v2` and `workspace-ux-fixture.v1` contracts, CASE-VR-001 phase content, selected-step/causal/commitment/expected-vs-observed/hidden boundaries, Korean labels, and 7 focused tests. The API and React UI are intentionally not connected yet.|
|Post-I7 UX-B|Passed|Backend-ranked `decision-list-item.v1`, consumer-shaped collection API, Korean action-needed groups, deadline/why-now/blocker/next-action cards, responsive loading/empty/error UI, 5 focused Backend tests, 5 Frontend unit tests, and 3 Playwright E2E tests. UX-C Workspace v2 remains unconnected.|
|Post-I7 UX-C|Passed|Live `decision-workspace.v2` projection and `at_step` API, phase-adaptive Decision Brief, observable historical reconstruction, causal chain, commitment window, expected/observed separation, Decision Posture, responsive 390px UI, 9 focused Backend tests, 6 Frontend unit tests, and 3 Playwright E2E tests.|
|Post-I7 UX-D|Passed|Backend-owned option comparison, latest case-scoped Dossier phase/alignment, agreement/dissent/confirmation/challenge groups, selected-Step epistemic boundary, Role-original detail, desktop semantic table, mobile cards, 5 focused Backend tests, 7 Frontend unit tests, and 3 Playwright E2E tests.|
|Post-I7 UX-E|Passed|Latest durable decision/outcome/evaluation projection, one linked Action Plan/Safeguard/Rollback flow, one Backend-owned primary action per phase, hidden pre-reveal result, event-backed observed transitions, separate expected/actual and Process/Outcome evaluation, reload-safe commands, 5 focused Backend tests, 9 Frontend unit tests, and 3 Playwright E2E tests.|
|Post-I7 UX-F|Passed (local agent substitute)|390/768/desktop and 200%-equivalent reflow, skip-link and section focus, semantic landmarks/table/live states, 44px targets, reduced motion, Korean partial recovery, stale/conflict refresh, 9 Frontend unit tests, 7 Playwright E2E tests, and frozen CASE-VR-001 13/13 task answers with zero raw-detail opens for questions 1–6. Human usability and business-value evidence remain unmeasured.|
|Post-I7 UX-G|Passed (fixture-only)|API-boundary network error normalization, Korean reason/impact/recovery UI, unavailable historical-Step recovery, URL-backed `at_step` and ordinal mobile alternative, reload/Back/Forward restoration without raw option ID, Korean-first supporting copy, explicit interaction states, 12 Frontend unit tests and 8 Playwright E2E tests. Human baseline remains unmeasured.|
|Post-I7 UX-H tooling|Implemented; human Gate not ready|Hash-pinned observable baseline selectors and rendered Jira/Confluence-shaped fixture, frozen 13-task two-condition protocol, builder/proxy/domain separation, session event/result and summary contracts, validation/preparation/summary CLI, 10 focused Backend tests. Actual human observations: 0; dry-run status: `not_ready`, `not_evaluable`, `no_business_claim`.|
|OPS-A|Passed|ADR-0010 fixes Project/Issue/Risk/Gate semantics, provenance, deterministic truth ownership and OPS-B~OPS-F order.|
|OPS-B|Passed|Three lifecycle-distinct Project fixtures, 17 typed events, hash manifest, cross-project lineage and historical leakage tests.|
|OPS-C|Passed|Migration 0020, durable Project repositories, deterministic attention/risk policies, five read APIs, historical parity, generated contracts and Replay smoke; this established the runtime boundary consumed by OPS-D.|
|OPS-D|Passed (local agent substitute)|Backend-ordered Project Portfolio, progressive Situation view, human-readable source-to-Issue/Evidence/Event joins, affected work and milestones, URL-backed historical Step, Korean recovery, responsive 390px/desktop UI, 4 focused/16 total unit tests, 8 regression E2E, Axe and overflow checks. Human task time remains unmeasured.|
|OPS-E|Passed (local agent substitute)|One source→epistemic/inference→impact→Decision/Action trace, Korean-first rule/limitation labels, all-Risk Situation navigation, historical Project boundary, Decision round trip without cross-timeline Step injection, 4 focused/19 total unit tests, 8 regression E2E, 390px/desktop Axe, overflow and console checks. Human task time remains unmeasured.|
|OPS-F|Study execution tooling complete; human observation deferred|PROJECT-U/V/W source pack, 6 baseline surfaces, 11 tasks, product release hash pins, participant-hidden reviewer rubric, draft/exclusion attrition reporting, condition guides and Project path E2E. Completed independent observations: baseline 0/5, product 0/5; `not_ready/not_evaluable/no_business_claim`.|
|UX-I|Passed (engineering-proxy only)|Portfolio `nearest_milestone_title` projection, title-first attention and Track references, domain-centered Korean copy, unknown-ref fallback, `UX-I-PRODUCT-87D49D7` release pins, 19 Frontend unit tests, 10 Playwright E2E, PostgreSQL/non-PostgreSQL regression, 390px/desktop Axe, keyboard, overflow and console checks. No human/time/value claim.|
|UX-J|Passed (engineering-proxy only)|Immutable builder initial/advice reveal/final response sequence, accept/modify/reject classification, URL-backed evaluation mode, PostgreSQL restart persistence and `UX-J-PRODUCT-218C095` pins. No human/anchoring/value claim.|
|UX-K|Passed (Local fixture UX Release 1)|Full Portfolio→Project→Risk→Decision→builder response→advice→Outcome/Evaluation→Risk browser journey, explicit empty-learning destination, responsive/accessibility/recovery/history regression and `LOCAL-UX-RELEASE-1-5227D18` pins. Human observations remain 0/5 per condition; no human/time/value claim.|
|ENT-A|Passed (contract-only)|ADR-0012, strict `enterprise-source-record.v1`, stable external identity, four timezone-aware source times, opaque ACL/classification, payload-safe deletion/restriction, source-neutral `SourceReader`/`IngestionSink`, generated schema and 15 focused tests. No adapter, persistence, company data or canonical mapping.|
|ENT-B|Passed (fixture-only mapping)|ADR-0013, five versioned synthetic profiles covering Project/WorkItem/Issue/Event/Evidence candidates, source-span structured/unstructured candidates, fixed unreviewed prose boundary, hash-pinned 10-pattern corpus, explicit accept/quarantine/reject and 15 focused tests. No canonical import, sync, persistence, vendor SDK or company data.|

OPS-F implementation record (2026-07-23):

- new v2 material measures the actual Portfolio → Situation → Risk → Decision information architecture;
  the previous DecisionCase-centered v1 protocol remains valid and unchanged
- canonical validation pins all three Project fixtures and verifies every task answer source is both
  present and exposed to the baseline condition; stale, hidden, duplicate and mismatched material fails
- baseline and product receive the same 11-task `study-guide.md`; baseline additionally receives six
  rendered Jira/Confluence-shaped source surfaces, while product starts at `/projects`
- task coverage includes priority, blocked work/Gate, Issue-Risk-Evidence classification, epistemic
  differences, provenance, affected objects, treatment/rollback, Step 20 replay, future-leak prevention,
  cross-project lesson and Decision round trip
- session/event/result/summary measurement remains v1-compatible; Project protocol v2 prevents the same
  participant from completing both conditions and keeps builder drafts outside independent counts
- two CLI-generated builder drafts contain no completed observation; summary remains
  `not_ready/not_evaluable/no_business_claim`, with baseline/product independent counts 0/5 and 0/5
- one release manifest pins the OPS-E product revision, `/projects` entry, execution environment and
  study-critical UI/API/material hashes; stale artifacts fail before a session is prepared
- one reviewer-only rubric freezes exact required findings and failure conditions without leaking them
  into participant guides; draft/excluded/complete counts and fixed exclusion reasons remain visible
- Project E2E now verifies the live Portfolio → Situation → Risk → Decision round trip and the mobile
  Step 20 no-future-leakage boundary in addition to existing Decision-flow regression
- full regression passes: Ruff, Mypy (51 source files), 164 non-PostgreSQL tests, 11 PostgreSQL tests,
  all boundary/contract/plan/migration checks, 19 Frontend unit tests, production build and 10 E2E tests
- OPS-F software preparation is complete but its human Gate is not. UX-I and business claims remain
  blocked until both conditions have at least five valid independent observations and responsible review
- direct company connection is not ready: canonical storage/projection/UI are reusable, but Jira/
  Confluence adapter, enterprise identity/time, ACL, sync and retention contracts remain C0 work;
  the next allowed integration activity is approved sanitized-export schema-fit, not a live connector

OPS-E implementation record (2026-07-22):

- Situation links its top and remaining Backend-ordered Risks to the new canonical Risk Detail route;
  historical links preserve `at_step`
- Risk Detail renders source Issue/Event/Evidence/cross-project lesson, epistemic status, inference basis,
  Risk posture and priority reasons, affected WorkItem/Milestone, Decision, Action, verification Evidence
  and rollback condition in one numbered reading flow
- known inference-rule and Evidence-limitation codes receive Korean-first labels while IDs remain visible
  only as provenance; no Frontend score, rank or truth inference was introduced
- Decision links preserve `from_project`, `from_risk` and optional `from_project_step`. They deliberately
  do not send Project `at_step` into a DecisionCase with a different timeline; Workspace interactions
  retain the origin query and its back link restores the exact Risk view
- live fixture round trip Project V → Risk → CASE-HO-002 → Risk passes for current and historical Step
- local browser checks at 1440px and 390px report no horizontal overflow, Axe violation, console warning
  or error; screenshots are under `output/playwright/opse-risk-detail-*.png`
- this satisfies the two-minute Gate only as an engineering agent-substitute proxy. OPS-F must freeze a
  Project-centered protocol v2 before any independent session or business-value claim

OPS-D implementation record (2026-07-22):

- `/` now enters `/projects`; Portfolio exposes each Project's Backend-owned attention reason, top Risk,
  nearest milestone and operational counts without a Frontend score
- Situation makes the top Risk readable as reason → visible source → affected WorkItem/Milestone, then
  separates blocked work, Track progress, Gate/Checkpoint, observed Issue, Evidence gaps and recent Event
- Project `at_step` lives in the URL and fail-closed recovery returns to the current state; Situation and
  Timeline query the same selected Step and never request Risk Detail or Decision data in OPS-D
- source display uses the source IDs supplied by OPS-C and joins only titles already visible at the same
  Step; it does not infer, rank or mutate Project truth
- 390px and 1440px browser checks report no horizontal overflow, Axe violations or console problems;
  screenshots are under `output/playwright/opsd-*.png`
- the 30-second question set is an engineering proxy only. Independent task-time observation remains
  deliberately paused until OPS-F protocol v2

Post-I7 UX-H implementation record (2026-07-19):

- baseline and product conditions share `CASE-VR-001` observable input; the baseline pack stores the
  normalized SHA-256 and fails validation when the fixture or a JSON-pointer selector becomes stale
- the protocol freezes 13 questions, minimum five independent proxy/domain observations per condition,
  exclusions, full-accuracy/safeguard targets and a 0.8 product/baseline median-time ratio
- completed sessions require task start/end, submitted answer and reviewer response events; wrong
  primary action, raw detail open and recovery events remain countable without being required
- expected, observed and unconfirmed boundary classifications are scored against the frozen task rubric
- builder sessions are engineering dry-runs only and cannot satisfy the independent sample requirement
- even sufficient small samples produce only `ready_for_directional_review`, never an automated human
  or business-value pass; the current repository contains no fabricated completed participant session
- no Frontend product flow, API endpoint, database, authentication, company connector or write-back was
  introduced in UX-H

Post-I7 UX-G record (2026-07-19):

- fetch transport failures become a safe `CONNECTION_FAILED` `ApiError`; Workspace never renders the
  original browser/provider error text
- 404, invalid historical Step, connection failure and generic service failure expose different
  impact and recovery paths; invalid Step can return directly to the current view
- `at_step` and the one-based mobile alternative position share URL query state and survive reload,
  Back and Forward; opaque option IDs remain absent from the URL and normal page
- supporting copy uses Korean-first terms while canonical `Simulation Step` actions and Backend
  contracts remain unchanged
- primary/secondary controls have explicit hover, active, disabled, focus and reduced-motion behavior
- no Backend domain, API schema, database migration, Jira/Confluence or company-data scope changed

Post-I7 UX-E record (2026-07-17):

- latest durable Dossier run, simulated decision, outcome and evaluation are restored by the current
  Workspace query; historical queries fail closed and expose none of this later state
- the outcome command can resolve its decision from persisted Backend state, while an explicitly
  supplied mismatching decision is rejected
- one actioning flow connects decision rationale, owner, due Step, trigger, verification, fallback,
  Safeguard threshold/check/expiry, violation action and residual risk
- a persisted decision starts an observed Action transition; explicit fixture Outcome advance adds
  event-backed Action/WorkItem transitions and reveals expected versus actual information
- evaluation copy keeps Process quality and Outcome quality separate and produces reusable learning
- normal user flow runs only the release B2 Dossier; single-Role and topology experiments remain on
  developer/evaluation surfaces
- generated JSON Schema, OpenAPI and TypeScript contracts were refreshed together; no migration was
  required
- UX-F local Gate evidence is recorded in `../../output/usability/UX-F-20260717-CASE-VR-001/report.md`

Post-I7 UX-F record (2026-07-17):

- one skip link reaches the single main landmark; view actions scroll and focus their named section
- no page-level horizontal overflow at 390, 640 (200% equivalent), 768 or desktop widths
- keyboard, semantic accessibility tree, axe, reduced-motion and 44px interactive-target checks pass
- partial Dossier UI preserves completed Role labels, translates failure reason, offers retry and hides
  the Chair command; aggregate conflict exposes stale recovery and restores current Workspace
- frozen CASE-VR-001 canonical 8 + Development Twin 5 questions pass in the normal UI; questions 1–6
  use neither Role originals nor raw ontology detail
- this is an agent-substitute engineering Gate, not a human task-time or business-value result
