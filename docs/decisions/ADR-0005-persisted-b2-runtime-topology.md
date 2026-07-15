# ADR-0005: Persist and activate the B2 runtime topology

> Status: ACCEPTED
> Date: 2026-07-15

## Context

ADR-0004 selected B2 as the release candidate because frozen live ablation reported B2 over
B1 on 4/4 fresh cases and B3 over B2 on 0/4. The durable review-run path still hard-coded B3,
and the stability runner also hard-coded B3. Changing only the execution default would allow a
queued run or retry to execute under a topology different from the one budgeted and audited.

B2 has no Challenger, revision round, or provider Chair. Therefore the simulated-decision
command also cannot require a Chair result after B2 activation.

## Decision

1. Stability requires an explicit B1, B2, or B3 `--topology` argument and records it in the
   evaluation summary, environment, report, and failures.
2. A dossier `ReviewRun` persists its topology at enqueue time. Idempotency includes topology,
   and retry copies the original value.
3. Migration `0019_agent_run_topology` maps every historical dossier row to B3 because that was
   the only pre-Step-5 execution path. Role-review rows keep null topology.
4. New dossier runs use B2 after the frozen B2 validation x5 and sealed-unseen x3 gates both pass.
5. B2 reserves four logical calls and 6,000 output tokens for the four routed roles. B3 remains
   available explicitly and retains its Challenger, bounded revisions, Chair, and larger budget.
6. The simulated-decision command uses the deterministic core for B1/B2 and the persisted Chair
   result for B3.

## Release evidence

The same `eval-2026-07-14.2` manifest, `gpt-5.6-luna`, reasoning effort `high`, and parallelism 2
were used without prompt, expected-result, hidden-outcome, or policy changes.

|Gate|Result|
|---|---|
|Step 4 B2/B1|4/4|
|Step 4 B3/B2|0/4|
|B2 validation x5|10/10 acceptable, 10/10 policy compliant|
|B2 sealed-unseen x3|6/6 acceptable, 6/6 policy compliant|
|Runtime failures / policy violations|0 / 0|

Only aggregate results were inspected. Sealed case details and hidden outcomes were not opened.

## Consequences

- A run's budget, execution, retry, API projection, and audit history now refer to one durable
  topology value.
- The normal path removes four B3 semantic calls per four-role case while retaining independent
  routed Role Agents.
- Historical runs remain reproducible as B3.
- B3 can still be requested internally for compatibility and future frozen ablation.
- This local synthetic-fixture result does not establish company workflow value or authorize a
  human decision, Jira/Confluence access, authentication, or write-back.
