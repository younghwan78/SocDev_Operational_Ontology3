# Canonical implementation report

> Updated: 2026-07-11  
> Scope: local synthetic fixture PoC  
> Authority: `docs/readiness/01_MASTER_EXECUTION_PLAN.md`

## 1. Outcome

Canonical stages I0 through I6 and the complete Replay portion of I7 are implemented and verified. The live OpenAI I7 stability gate is implemented but not executed because this environment has no `OPENAI_API_KEY` and no operator-confirmed current token-price rates. It is not counted as passed.

## 2. Implemented flow

```text
YAML observable fixture
  -> strict Pydantic validation
  -> PostgreSQL observable state + append-only audit event
  -> deterministic ObservableCasePacket + hash
  -> durable AgentRun queue and lease worker
  -> grounded RoleReview
  -> independent roles + provider Challenger + bounded provider revision
  -> DecisionDossier with visible dissent
  -> provider Chair + deterministic policy validation + safeguards
  -> hidden closed-world OutcomeRule
  -> Process evaluation + Outcome evaluation
  -> Korean Decision Workspace
```

Hidden fixture data is not part of Role or Chair inputs. PostgreSQL enforces this with a separate `soc_ot_outcome` role; the ordinary runtime role fails on `SELECT` from the hidden schema.

## 3. Stage evidence

|Stage|Implemented evidence|Verified gate|
|---|---|---|
|I0|Python/Frontend scaffold, Docker PostgreSQL, quality scripts, environment template|Toolchains and PostgreSQL healthy without API key|
|I1|Strict development, claim, evidence, quantity, observable/hidden/expected models and CASE-VR-001|Invalid unit/transition/reference and leakage tests|
|I2|Alembic 0001–0016, SQLAlchemy repositories, aggregate/event atomic write, fixture import|Memory/PostgreSQL parity, empty/oldest migration paths, and persisted state|
|I3|Consumer read API, deterministic packet, Korean UI, 8-case frozen corpus|Manifest hash, hidden-free packet/API, Frontend build|
|I4|Replay/OpenAI providers, strict Structured Outputs, start/final attempt audit, role/revision/Challenger/Chair checkpoints, heartbeat lease, continuous SSE/polling, stale/partial/retry UI|Bounded transport/schema/policy retry, per-call timeout, lease crash resume without repeating accepted roles, late-cancel discard, provider/token/cost limits|
|I5|True B0–B3 boundary, independent roles, provider Challenger, at most two provider revisions, Dossier, provider Chair with deterministic policy validation, durable decision command|Chair is an audited eighth B3 semantic call; dissent retained, majority cannot override operability policy, conditional decisions require complete safeguards|
|I6|Closed OutcomeRule registry, persisted idempotent step advance/evaluation, latest query, step-gated hidden reveal, separate Process/Outcome evaluator|All 8 Replay cases pass; early evaluation is denied; runtime DB role cannot read hidden schema|
|I7 Replay|Generated client, telemetry, actor/authoring/attempt audit, immutable evaluation bundle, recovery smoke, scans, axe/browser E2E, runbook|65 Backend tests, 3 unit + 2 E2E Frontend tests, 8/8 evaluation, API-worker smoke, 8/8 usability|
|I7 Live|Live B0–B3 ablation, validation x5 and sealed-unseen x3 stability commands, preflight and pre-call budget abort|Not run: key and operator-confirmed current price settings absent|

## 4. Main contracts and modules

- Domain truth: `backend/src/soc_ot/domain/models.py`
- Observable packet: `backend/src/soc_ot/application/packets.py`
- Role contracts/providers: `backend/src/soc_ot/agents/contracts.py`, `providers.py`
- Durable runs: `backend/src/soc_ot/application/review_runs.py`, `worker/main.py`
- Dossier orchestration: `backend/src/soc_ot/application/multi_role.py`
- Chair policy/provider runtime: `backend/src/soc_ot/agents/chair.py`, `agents/providers.py`, `agents/runtime.py`
- Outcome/evaluation: `backend/src/soc_ot/application/outcomes.py`, `evaluation.py`
- API/OpenAPI: `backend/src/soc_ot/api/main.py`, `contracts/generated/openapi.json`
- Generated Frontend types: `frontend/src/api/schema.d.ts`
- User workspace: `frontend/src/features/decisions/DecisionWorkspacePage.tsx`

## 5. Reproducible verification

```powershell
& scripts/verify-i7.ps1
& scripts/smoke-replay.ps1
```

Verified results on 2026-07-11:

- Backend: 65 passed, including PostgreSQL restart/atomic rollback, checkpoint recovery, Chair attempt audit/checkpoint, pre-reveal denial, and post-version idempotent replay tests
- Frontend: typecheck, lint, 3 unit tests, production build passed
- Browser: 2 Playwright workflows passed; automated axe scan reported zero serious/critical violations
- Frozen corpus: 8 of 8 Replay evaluations passed
- Smoke: Agent run `COMPLETED`, 8 audited provider attempts including Chair, decision `APPROVE_WITH_GUARDRAILS`, outcome evaluation passed
- Browser: desktop and mobile workflow completed with zero final console errors
- Repository: plan, architecture-boundary, hidden-boundary, secret, Markdown-link, generated-contract scans passed

Artifacts:

- `output/evaluations/eval-2026-07-11.1/20260712T024645Z-replay-64ae79c2/report.md` and its six machine-readable companion artifacts
- `output/smoke/replay.json`
- `output/usability/i7-replay/report.md`
- `output/playwright/i7-workspace.png`
- `output/playwright/i7-workspace-mobile.png`

## 6. Live gate procedure

Set the key only in the worker/evaluation terminal, confirm current prices from the provider, then set:

```powershell
$env:SOC_OT_LLM_MODE = "openai"
$env:OPENAI_API_KEY = "..."
$env:SOC_OT_ROLE_INPUT_COST_PER_MILLION_USD = "<current-rate>"
$env:SOC_OT_ROLE_OUTPUT_COST_PER_MILLION_USD = "<current-rate>"
uv run soc-ot agent preflight
uv run soc-ot evaluation ablate --provider openai --partitions validation,sealed-unseen --acknowledge-cost
uv run soc-ot evaluation stability --provider openai --partition validation --repeat 5 --acknowledge-cost
uv run soc-ot evaluation stability --provider openai --partition sealed-unseen --repeat 3 --acknowledge-cost
```

The ablation command executes B0–B3 once per frozen validation/sealed case. The two stability commands execute B3 at the required per-case repeat counts. Every command prints and enforces the batch cost envelope before its first call. Do not treat Replay results as proof that multiple LLM roles add marginal business value.

## 7. Important correction discovered during implementation

An early RoleReview contract required at least one claim citation for every recommendation. CASE-VR-005 exposed why that is unsafe: at an earlier simulation step, no claim may yet be eligible. The final contract requires grounded claims for execution/approval recommendations, while evidence collection, deferral, rejection, or escalation may explicitly proceed with no claim and low/medium confidence. This prevents the system from inventing authority merely because data is unavailable.

## 8. Interpretation boundary

The implementation proves that development state, incomplete evidence, independent role advice, dissent, risk-limiting simulated decisions, and deterministic outcomes can be operated as one reproducible workflow. It does not yet prove decision-speed improvement or advice quality in a company context. Those claims require a future human-reviewed pilot with task-time and decision-quality baselines.

See `KNOWN_LIMITATIONS.md` for the remaining constraints.

Exact stage commands, counts, artifacts, and the live preflight budget evidence are recorded
in [I0–I7 gate evidence](I0_I7_GATE_EVIDENCE.md).
