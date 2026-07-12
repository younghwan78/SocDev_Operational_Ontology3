# I0–I7 completion audit

> Audit date: 2026-07-11  
> Authority: `../readiness/01_MASTER_EXECUTION_PLAN.md`  
> Scope: local synthetic-fixture PoC  
> Rule: an item is complete only when implementation and direct executable evidence both exist

## 1. Verdict

|Scope|Verdict|Reason|
|---|---|---|
|I0–I6|PASS|Every Deliver and Gate has implementation plus direct test, scan, migration, smoke, browser, or evaluation evidence.|
|I7 Replay engineering scope|PASS|Accessibility, E2E, telemetry, recovery, scans, runbook, usability, and immutable Replay evaluation pass.|
|I7 Live|NOT COMPLETE|The runner and pre-call guards exist, but no authorized OpenAI call was made. Live stability, robustness, marginal value, and topology selection are therefore unproven.|
|Full I0–I7 objective|NOT COMPLETE|I7 Gate explicitly requires live results and an ablation-based keep/simplify/remove decision.|

Replay results prove the system mechanics and deterministic policy behavior. They do not prove
that multiple live LLM roles improve advice quality or decision speed.

## 2. I0 audit — repository and quality scaffold

|Requirement|Result|Direct evidence|
|---|---|---|
|Canonical folders|PASS|`scripts/check-plan-consistency.ps1` checks every directory named by the canonical layout and rejects duplicate top-level source/test trees.|
|Python and Frontend package scaffold|PASS|`pyproject.toml`, `uv.lock`, `frontend/package.json`, and `frontend/package-lock.json`; locked installs pass in `scripts/verify-i7.ps1`.|
|Lint/type/test commands|PASS|Ruff, mypy, pytest, TypeScript, ESLint, Vitest, build, and Playwright all execute in `scripts/verify-i7.ps1`.|
|Environment, PostgreSQL Compose, AGENTS|PASS|`.env.example`, `deploy/local/compose.yaml`, `deploy/local/init.sql`, and `AGENTS.md`.|
|PostgreSQL health and no-key Replay startup|PASS|Compose health, Alembic checks, `/health/live`, and the complete no-key Replay verification run.|

## 3. I1 audit — domain, contracts, and first fixture

|Requirement|Result|Direct evidence|
|---|---|---|
|Development/decision, Claim, enum, time, quantity, observable/hidden models|PASS|`backend/src/soc_ot/domain/models.py` and generated JSON Schemas.|
|YAML loader and CASE-VR-001 observable/hidden/expected fixture|PASS|`infrastructure/fixtures.py` and the three CASE-VR-001 fixture files.|
|In-memory repository|PASS|`application/repositories.py` and `test_in_memory_repository_tracks_version_and_event`.|
|Invalid transition/unit/reference/leakage rejected|PASS|Negative tests in `test_i1_domain.py`.|
|Step-scoped state reconstruction|PASS|CASE-VR-001 validates at Step 12; packet/projection select evidence by `available_at_step <= current_step`; CASE-VR-005 tests the earlier-step empty-evidence state.|

## 4. I2 audit — PostgreSQL and read projection

|Requirement|Result|Direct evidence|
|---|---|---|
|Migrations and PostgreSQL repositories|PASS|Alembic 0001–0016 and SQLAlchemy repositories.|
|Memory/PostgreSQL parity|PASS|`test_postgres_repository_matches_in_memory`.|
|Current row plus append-only event transaction|PASS|`PostgresCaseRepository.save`; `test_case_row_update_rolls_back_when_domain_event_insert_fails` injects an event failure and proves the row update rolls back.|
|DecisionWorkspaceProjection and fixture import|PASS|`application/projections.py`, CLI fixture commands, smoke and E2E imports.|
|API restart persistence|PASS|`test_api_restart_reads_the_same_imported_postgres_state` constructs a second API/repository instance and compares its persisted response.|
|Migration compatibility|PASS|`scripts/check-migrations.ps1` proves empty DB → head and oldest-supported 0001 → head.|

## 5. I3 audit — read API, packet, corpus, and Korean UI

|Requirement|Result|Direct evidence|
|---|---|---|
|Canonical read APIs and generated client|PASS|Generated OpenAPI plus `frontend/src/api/schema.d.ts`; generated-contract check passes.|
|Deterministic packet and impact/dependency/deadline traversal|PASS|`application/packets.py` and I3 deterministic/hash/impact tests.|
|Evidence/provenance/epistemic and operability projection|PASS|I3 packet tests cover eligible/future evidence, claims, detectability, recoverability, and reversibility.|
|Hidden denylist|PASS|Fail-closed unit test, hidden-boundary scan, OpenAPI route scan, and 8-case packet/API tests.|
|Korean routes and UI states|PASS|`/decisions`, `/decisions/:caseId`, `/dev/fixtures`; unit tests cover loading/error/stale recovery and E2E covers desktop/mobile workflow.|
|Eight-case frozen corpus|PASS|Five VR plus three HO observable/hidden/expected fixtures; manifest validation and frozen hashes pass.|
|Usability without raw graph/JSON|PASS|`output/usability/i7-replay/report.md` answers all eight questions from the workspace.|
|Agent input boundary|PASS|Role, Challenger, and Chair provider/runtime signatures consume `ObservableCasePacket` plus validated prior outputs; architecture and hidden boundary scans reject repository/hidden dependencies.|

## 6. I4 audit — Agent runtime, worker, and progress

|Requirement|Result|Direct evidence|
|---|---|---|
|Replay and OpenAI Responses providers|PASS|`agents/providers.py`; Replay is deterministic and OpenAI uses strict parsed output with SDK retries disabled.|
|Durable queue, lease, heartbeat, claim, recovery|PASS|`application/review_runs.py`, `worker/main.py`, and memory/PostgreSQL lease/reclaim tests.|
|Single-role routing and grounded review|PASS|Role packet routing, grounding validator, and unsupported-claim rejection test.|
|SSE and polling fallback|PASS|Run API test plus UI polling and persisted SSE sequence/heartbeat implementation.|
|Progress, partial failure, cancel/retry, stale UI|PASS|Frontend unit/E2E coverage and partial/all-role failure Backend tests.|
|Attempt start/final audit and logical checkpoints|PASS|Migration 0012/0015, role/revision/Challenger/Chair checkpoint repositories, crash/reclaim tests, and smoke audit count 8.|
|Bounded retry, timeout, token/call/cost plan|PASS|Transport/schema/policy retry tests, terminal timeout/cancel-late audit tests, stored budget plan, and pre-call live batch guard tests.|
|Accepted step not repeated after reclaim|PASS|Memory and PostgreSQL crash tests prove the first accepted role is skipped on resume.|

## 7. I5 audit — multi-role Dossier and Chair

|Requirement|Result|Direct evidence|
|---|---|---|
|Independent roles, provider Challenger, bounded revisions|PASS|B3 executes four initial roles, one Challenger, at most two revisions, and one Chair under the 12-attempt cap.|
|Decision Dossier and dissent|PASS|Agreement/dissent contracts and `test_dissent_survives_challenge_and_chair_acknowledges_it`.|
|Simulated provider Chair plus policy validator|PASS|Chair is an independently audited eighth normal B3 call; deterministic validation rejects disallowed/incomplete conditional decisions.|
|Executable safeguards|PASS|Tests require metric/operator/threshold/check/expiry/action/rollback/owner/verification; UI renders all fields.|
|B0–B3 interface|PASS|Replay ablation test proves call counts 0/1/4/8 and deterministic-core versus provider-Chair boundary.|
|Hidden isolation and durable accepted Chair|PASS|Architecture/hidden scans, no hidden imports/routes, Chair checkpoint test, and PostgreSQL attempt audit.|
|Replay marginal-value claim prohibited|PASS|Evaluation protocol, implementation report, UI wording, and known limitations explicitly preserve this boundary.|

## 8. I6 audit — Outcome and evaluation

|Requirement|Result|Direct evidence|
|---|---|---|
|Closed OutcomeRule registry and fail-closed option/path handling|PASS|`application/outcomes.py` and unknown/conflicting-path tests.|
|Explicit simulation advance and hidden reveal|PASS|Persisted, versioned, idempotent outcome command; early reveal/evaluation is rejected.|
|Process and Outcome evaluation|PASS|Separate contracts, persisted evaluation/latest query, API restart/idempotency tests, and Korean UI sections.|
|Partitioned evaluation runner|PASS|Development/validation/sealed-unseen manifest and evaluation runner.|
|Eight complete paths|PASS|Replay evaluation reports 8/8 and zero policy violations; smoke exercises decision → rollback → evaluation.|
|Runtime hidden DB denial|PASS|Dedicated PostgreSQL privilege test and separate outcome role.|

## 9. I7 audit — hardening and usability

|Requirement|Result|Direct evidence|
|---|---|---|
|Accessibility and E2E|PASS|Three UI unit tests, two Playwright workflows, axe zero violations, console zero errors/warnings, desktop and 390px mobile checks.|
|Performance and cost telemetry|PASS (Replay)|Packet/evaluation timing tests, run telemetry endpoint, provider attempt/token/cost audit, and $0 Replay result.|
|Failure recovery|PASS|Lease/crash/checkpoint/cancel/retry tests and PostgreSQL worker smoke.|
|Local runbook without API key|PASS|`scripts/verify-i7.ps1` reruns locked installs, fresh migration paths, all Backend/Frontend/E2E checks and Replay evaluation without a key. A literal Git clone was not available because this workspace has no `.git`; dependency-clean and DB-clean conditions were exercised directly.|
|I7 usability eight questions|PASS|`output/usability/i7-replay/report.md`: 8/8.|
|Secret/hidden/architecture scans|PASS|All repository scans pass and are part of `verify-i7.ps1`.|
|Known limitations|PASS|`KNOWN_LIMITATIONS.md`.|
|Live B0–B3 ablation implementation|IMPLEMENTED, NOT EXECUTED|CLI runner and pre-call budget guard exist. Preflight estimates 20 runs / 65 semantic calls / $40 maximum, then aborts before a call.|
|Validation live stability x5|IMPLEMENTED, NOT EXECUTED|Estimate is 10 runs / 80 calls / $20 maximum; missing key/rates stop execution.|
|Sealed-unseen live robustness x3|IMPLEMENTED, NOT EXECUTED|Estimate is 9 runs / 72 calls / $18 maximum; missing key/rates stop execution.|
|Live policy, stability, robustness, cost gates|NOT PROVEN|No live outputs exist.|
|Keep/simplify/remove topology decision|NOT DECIDED|The decision must follow live marginal-value results; Replay cannot substitute.|

## 10. Cross-cutting invariant audit

|Invariant|Result|Evidence|
|---|---|---|
|Domain imports no FastAPI, SQLAlchemy, OpenAI, infrastructure, or UI labels|PASS|`scripts/check-architecture-boundary.ps1`.|
|Agents receive validated packet/prior contracts, not repositories|PASS|Architecture scan and provider/runtime signatures.|
|Hidden data is limited to authoring, Outcome, and Evaluation paths|PASS|Hidden scan, PostgreSQL role denial test, OpenAPI scan, authoring audit.|
|Canonical terms, endpoints, time, and versions|PASS|Plan consistency and generated OpenAPI checks.|
|No Jira, Confluence, company data, auth, or write-back|PASS|Source/config/secret scans and fixture-only adapters.|
|No unapproved legacy copy|PASS as repository policy evidence|No legacy dependency/path exists in source; `docs/decisions/` records that no legacy import ADR has been accepted. Exact source provenance cannot be reconstructed without Git history.|

## 11. Latest executable evidence

```text
Backend pytest                  65 passed
Frontend unit                  3 passed
Playwright E2E                 2 passed
Replay evaluation              8/8 passed, 0 policy violations
Migration paths                empty -> 0016, 0001 -> 0016 passed
PostgreSQL smoke               COMPLETED, 8 provider attempts, rollback, evaluation pass
Repository scans              plan, architecture, hidden, secret, links, generated contracts passed
```

Latest immutable Replay report:

`output/evaluations/eval-2026-07-11.1/20260712T024645Z-replay-64ae79c2/report.md`

## 12. Remaining authority required

Do not paste a secret into documentation or chat. Set the key and current verified rates only in
the evaluation process environment. The remaining live gate needs:

1. `OPENAI_API_KEY` with access to the configured role, Challenger, and Chair models.
2. Positive current input/output token rates.
3. Explicit acceptance of at least the `$40` ablation maximum and corresponding batch cap.
4. Authorization to open the frozen validation and sealed-unseen live results.

Until those conditions are supplied, the correct overall status is **I7 Live pending**, not
“I0–I7 complete.”
