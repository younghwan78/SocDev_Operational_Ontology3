# Implementation status

> Updated: 2026-07-17
> Current stage: Post-I7 UX-F local responsive, accessibility, and agent-substitute usability Gate passed

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
