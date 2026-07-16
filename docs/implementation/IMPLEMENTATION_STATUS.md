# Implementation status

> Updated: 2026-07-17
> Current stage: Post-I7 UX-A Development Twin contract and content fixture complete; UX-B not started

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
