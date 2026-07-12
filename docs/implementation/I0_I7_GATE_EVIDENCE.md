# I0–I7 gate evidence

> Evidence date: 2026-07-11  
> Release: `eval-2026-07-11.1`  
> Local scope: synthetic fixtures, ReplayProvider, simulated provider Chair  
> External scope: OpenAI live gate not executed

## 1. Verdict

I0–I6 and the complete deterministic/Replay portion of I7 pass. The OpenAI-dependent
I7 business-value and stability gate remains unverified because this workspace has no
`OPENAI_API_KEY` and both live token-price settings are zero. No live-provider claim is
inferred from Replay results.

## 2. Stage-by-stage evidence

|Stage|Gate result|Executable evidence|
|---|---|---|
|I0|Pass|Locked Python/Node setup, Ruff, mypy, pytest, TypeScript, ESLint, Vitest, build, PostgreSQL health; Replay needs no key|
|I1|Pass|Strict case/claim/quantity/time contracts; transition, unit, reference, and hidden-leak negative tests; step reconstruction|
|I2|Pass|Memory/PostgreSQL parity; case row and append-only event transaction; restart persistence; empty DB and `0001_case_store` upgrades both reach `0016_agent_run_budget_plan`|
|I3|Pass|Deterministic packet hash, impact/deadline traversal, evidence availability and epistemic projection, hidden denylist, eight frozen cases, generated OpenAPI client, Korean UI|
|I4 Replay|Pass|Durable role/dossier runs, `SKIP LOCKED` lease, start/final attempt audit, role/revision/Challenger/Chair checkpoint resume, timeout, bounded transport/schema/policy retry, cancel-late discard, budget plan, SSE/polling, stale/partial/retry UI|
|I5 Replay|Pass|True B0–B3 interface, independent roles, provider Challenger, two provider revisions, explicit unique concern/no-concern, dissent-preserving Dossier, audited provider Chair with deterministic policy validation, executable safeguards, durable decision|
|I6|Pass|Closed option/rule registry, deterministic conflict failure, idempotent persisted step advance/evaluation, latest query, guardrail execution, pre-reveal API denial, separate Process/Outcome scoring, 8/8 cases|
|I7 Replay|Pass|65 Backend tests, 3 UI unit tests, 2 Playwright workflows, zero axe violations, zero captured console errors, PostgreSQL smoke, scans, immutable artifacts, 8/8 usability rubric|
|I7 OpenAI|Not run|Preflight and cost guards work, but key/current rates are absent; ablation/stability and marginal-value stop rule cannot be honestly scored|

## 3. Latest verified results

```text
Backend pytest                  65 passed
Frontend unit                  3 passed
Playwright E2E                 2 passed
Replay evaluation              8/8 passed
Migration paths                empty -> head, 0001 -> head passed
PostgreSQL API/worker smoke     COMPLETED / 8 attempts / APPROVE_WITH_GUARDRAILS / rollback / evaluation pass
Repository checks              plan, generated contracts, architecture/hidden boundaries, secrets, links passed
```

The latest immutable Replay report is:

`output/evaluations/eval-2026-07-11.1/20260712T024645Z-replay-64ae79c2/report.md`

Its directory also contains the frozen manifest, source-tree hash and redacted environment,
normalized JSONL results, Process scores, Outcome scores, and policy violations.

## 4. Security and audit evidence

- The runtime PostgreSQL role is denied `SELECT` on `hidden.*`; the outcome role is separate.
- Evaluation is rejected with `OUTCOME_NOT_REVEALED` until the logical reveal step.
- No hidden HTTP route exists in OpenAPI or Frontend source.
- Role/Chair code has no hidden repository dependency.
- Hidden import/inspection requires `SOC_OT_AUTHORING_MODE=1`, prints an
  `AUTHORING/HIDDEN` banner, and inserts actor/action/case into
  `audit.hidden_authoring_audits`.
- Review runs and outcome advances persist the application-resolved local actor.
- Prompt inputs are versioned under `agents/prompts/prompts.v1/`; Role, Challenger, and
  Chair files are hash-verified at import.

## 5. Live gate preflight evidence

With the current safe defaults, no provider call was made:

```text
preflight: key missing; live price settings not positive
ablation: 20 runs, 65 semantic calls, 18,000 s envelope, $40 maximum
           -> exceeds the configured $25 batch cap; aborted before call
validation stability: 10 runs, 80 calls, 9,000 s, $20 maximum
           -> key missing; aborted before call
sealed stability: 9 runs, 72 calls, 8,100 s, $18 maximum
           -> key missing; aborted before call
```

Running ablation therefore requires two explicit operator actions: provide current verified
rates/key, and raise `SOC_OT_MAX_EVALUATION_COST_USD` to at least `$40` after accepting that
maximum. The validation and sealed runs fit the current batch cap but still require the key
and rates.

## 6. Reproduction

```powershell
& scripts/verify-i7.ps1
& scripts/smoke-replay.ps1
```

Live execution, when explicitly authorized, uses the three commands in
`docs/readiness/07_LOCAL_DEVELOPMENT_RUNBOOK.md`. A passing Replay run must never be used
as evidence that multiple LLM roles improve advice quality or decision speed.
