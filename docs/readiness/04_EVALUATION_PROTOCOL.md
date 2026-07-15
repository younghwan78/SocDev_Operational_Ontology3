# Evaluation protocol

> Status: APPROVED  
> Date: 2026-07-14
> Scope: fixture-only PoC and optional live-provider stability check

## 1. Purpose

This protocol determines whether the system helps make defensible SoC development decisions under incomplete evidence. It separates deterministic product acceptance from model-behavior observation and prevents evaluation cases from becoming prompt-training examples.

## 2. Case partitions

|Partition|Cases|Use|Prompt or policy tuning|
|---|---|---|---|
|Development|the eight prior `CASE-VR/HO` cases|known regression and debugging|allowed|
|Validation|`CASE-DT-001`, `CASE-DT-002`|new release-candidate regression|not within the current candidate|
|Sealed unseen|`CASE-DT-003`, `CASE-DT-004`|new candidate robustness check|prohibited|

The earlier validation and sealed results were inspected and are retired to the
development partition in v2. Required v2 validation/sealed themes are:

- schedule workaround that creates deferred technical debt
- important measurement unavailable until silicon, with high irreversibility
- shared resource contention across concurrent feature programs

Freeze observable, hidden, expected, and scoring files before the first live-provider prompt tuning. Anyone who reads sealed hidden content must not tune prompts or policies against that release.

Because one home developer may author fixtures and prompts, this partition is not an independent scientific holdout. It detects obvious overfitting and regressions but cannot support a generalization or business-value claim. A company pilot needs an evaluation set created by an independent domain reviewer.

A validation failure may inform the next candidate, but the same case then serves as a known regression rather than fresh validation. Never tune the current candidate after seeing sealed-unseen results.

## 3. Freeze manifest

Every evaluation release has a committed manifest.

```yaml
evaluation_release: eval-2026-07-14.2
schema_version: evaluation-manifest.v2
policy_version: decision-policy.v1
prompt_bundle_version: prompts.v2
cases:
  - case_id: CASE-VR-004
    partition: development
    observable_path: cases/observable/CASE-VR-004.yaml
    hidden_path: cases/hidden/CASE-VR-004.yaml
    expected_path: expected/CASE-VR-004.yaml
    observable_sha256: observable_sha256_placeholder
    hidden_sha256: hidden_sha256_placeholder
    expected_sha256: expected_sha256_placeholder
```

Changing any frozen file creates a new evaluation release. Results from different releases are not merged as if they were comparable.

`eval-2026-07-11.1` with `prompts.v1` remains an immutable historical release.
`eval-2026-07-14.1` remains a historical eight-case release. The current evaluation
contract uses `eval-2026-07-14.2`, explicit source paths, 12 cases, and `prompts.v2`.

## 4. Expected-result contract

Each case defines a set of acceptable decision families instead of one exact prose answer.

```yaml
expected_result:
  acceptable_decision_types:
    - APPROVE_WITH_GUARDRAILS
    - RUN_REVERSIBLE_TRIAL
  unacceptable_decisions:
    - decision_type: APPROVE
      reason_code: IRREVERSIBLE_WITHOUT_EXIT_CRITERIA
  mandatory_risk_ids: [RISK-DDR-BW, RISK-THERMAL]
  mandatory_dependency_ids: [DEP-SW-EIS-FLAG]
  mandatory_guardrail_metric_ids: [DDR_BANDWIDTH]
  mandatory_trigger_actions: [rollback]
```

The expected result must not require exact wording, a specific chain of thought, or knowledge available only in hidden fixtures.

## 5. Two evaluation layers

### 5.1 Process evaluation

Checks whether the system followed the decision process:

- evidence and assumptions are distinguishable
- unresolved uncertainty remains visible
- required roles contributed or explicitly declared no unique concern
- dissent is preserved in the Dossier
- constraints, dependencies, owners, and next evidence actions are actionable
- the action plan is complete for its exact DecisionType
- development history reconstructs at least three observed steps when events exist
- historical packets exclude not-yet-observed events and future evidence content
- active blockers remain traceable to an impacted milestone
- policy, budget, timeout, and hidden-access boundaries were respected

### 5.2 Outcome evaluation

Checks the simulated consequence after a decision:

- guardrails and triggers fired at the configured step
- rollback or mitigation reduced the modeled harm where applicable
- decision family was compatible with the defined outcome path
- realized risks and missed opportunities are attributed to prior assumptions and choices

Good process may still lead to a poor outcome under uncertainty. The report records both rather than treating outcome luck as process quality.

## 6. Acceptance gates

|Gate|Required result|
|---|---|
|Fixture and contract validation|100% pass|
|Observable packet hidden leakage|0 findings|
|Accepted live authoritative claims|100% grounded or explicitly labeled assumption/inference|
|Accepted unsupported live authoritative claims|0|
|Mandatory critical risk coverage|100% for validation and sealed unseen|
|Mandatory dependency coverage|100% for validation and sealed unseen|
|Chair decision family|in the case's acceptable set for every validation and sealed-unseen case|
|Conditional/trial completeness|guardrail, trigger, owner, expiry/review step, and verification plan all present|
|Decision action completeness|type-specific owner, due step, trigger, verification, fallback, and required subtype fields present|
|Development history reconstruction|all v2 validation/sealed cases reconstruct at least three observed steps|
|Historical packet boundary|0 future event or ineligible evidence findings|
|Blocker impact traceability|100% of active blockers reach a named downstream milestone|
|Runtime policy violations|0|
|ReplayProvider regression|byte-stable normalized result for the same release|
|Role differentiation|each required role has a unique concern or explicit `no_unique_concern` in live evaluation|
|B2 marginal value|B2 adds a valid concern, safeguard, or deterministic improvement over B1 in at least 3 of 4 v2 validation/sealed cases|
|B3 marginal value|B3 adds a validated Challenger concern, safeguard, or deterministic improvement over B2 in at least 3 of 4 v2 validation/sealed cases|
|Validation live stability|at least 4 of 5 runs per validation case stay in an acceptable decision family; all runs remain policy compliant|
|Sealed-unseen robustness|three frozen selected-topology runs per sealed case stay policy compliant and at least 2 of 3 use an acceptable decision family|

ReplayProvider proves contract, persistence, orchestration, and UI regression only. It does not prove model grounding, role differentiation, decision stability, or marginal Agent value. Live gates are required for I7, not I0–I6.

## 7. Validator precedence

1. schema and reference validators
2. deterministic policy validators
3. expected-result semantic validators
4. optional LLM judge for qualitative diagnostics
5. human review notes

An LLM judge is supplementary. It cannot waive a deterministic failure or be the sole release gate.

## 8. Agent ablation

Run these configurations against the same frozen packet:

|ID|Configuration|
|---|---|
|B0|deterministic core only|
|B1|deterministic core plus one Architecture/System Agent|
|B2|deterministic core plus routed independent Role Agents|
|B3|B2 plus Challenger and simulated Chair|

Score deterministic expectations and inferential expectations separately. Compare only adjacent topologies: B1 over B0, B2 over B1, and B3 over B2. A candidate must pass every fresh-case Process gate and must not regress any deterministic Process field from its baseline.

For `eval-2026-07-14.2`, B2 and B3 each require valid marginal value in at least 3 of the 4 validation/sealed cases. B1 requires at least one valid contribution over B0 while passing all fresh-case Process gates. Select `keep_b3`, `release_b2`, `release_b1`, or `release_b0` in that order. `release_b0` can still have `release_gate_passed=false` when the deterministic core does not pass the fresh-case gate.

The selected topology is a release candidate until validation and sealed stability pass on that
same topology. Persist the topology on each dossier run before changing the durable workflow so
retry and historical execution cannot silently switch topology.

New Role IDs with a non-empty unique concern, new canonical safeguard metrics, validated Challenger objections, and deterministic false-to-true improvements count as marginal value. Mere wording changes or a different decision family do not.

Run one ablation pass per validation and sealed-unseen case after candidate freeze. Do not tune against sealed results.

## 9. Evaluation workflow

```text
freeze release manifest
  -> validate fixture and hashes
  -> run ReplayProvider suite
  -> run deterministic process validators
  -> advance outcome simulation
  -> run outcome validators
  -> run B0-B3 ablation once on validation and sealed cases
  -> run selected-topology stability: validation x5 and sealed unseen x3
  -> create immutable report
  -> approve or reject release candidate
```

Commands to be implemented:

```powershell
uv run python -m soc_ot.cli evaluation validate-release --manifest fixtures/manifests/eval-2026-07-14.2.yaml
uv run python -m soc_ot.cli evaluation run --manifest fixtures/manifests/eval-2026-07-14.2.yaml --provider replay
uv run python -m soc_ot.cli evaluation ablate --manifest fixtures/manifests/eval-2026-07-14.2.yaml --provider openai --partitions validation,sealed-unseen
uv run python -m soc_ot.cli evaluation stability --manifest fixtures/manifests/eval-2026-07-14.2.yaml --provider openai --topology B2 --partition validation --repeat 5
uv run python -m soc_ot.cli evaluation stability --manifest fixtures/manifests/eval-2026-07-14.2.yaml --provider openai --topology B2 --partition sealed-unseen --repeat 3
```

`--topology` is required for stability. The artifact stores the evaluated topology, and the
semantic-call estimate uses B1=1, B2=4, or B3=8 calls per case run. The 2026-07-15 B2 release
passed validation 10/10 and sealed-unseen 6/6 with zero policy or runtime failures.

Before live execution, print the maximum run count, semantic-call count, timeout envelope, and `runs × SOC_OT_MAX_CASE_COST_USD`. Abort before the first call when the estimate exceeds `SOC_OT_MAX_EVALUATION_COST_USD`; raising the batch cap is an explicit user decision. Store estimated and actual values in the report.

## 10. Result artifacts

```text
output/evaluations/<release-id>/<run-id>/
├─ manifest.snapshot.yaml
├─ environment.json
├─ normalized_results.jsonl
├─ process_scores.json
├─ outcome_scores.json
├─ policy_violations.json
└─ report.md
```

`environment.json` records code revision, provider, model identifier, prompt bundle, contract versions, policy version, and redacted runtime settings.

For ablation, `report.md` records the selected topology, four-way stop rule, selected-topology gate, and all comparison-run counts. `policy_violations.json` is scoped to the selected topology; the complete B0-B3 Process scores remain available for comparison.

## 11. Sealed-unseen discipline

- Do not expose sealed hidden files through HTTP or the Frontend.
- Do not copy sealed failures into prompts, few-shot examples, ReplayProvider fixtures, or policy rules.
- Opening a sealed case for root-cause analysis retires that release from robustness claims.
- After opening, create and freeze a new sealed release before running the final robustness gate again.

## 12. Failure taxonomy

```text
CONTRACT_INVALID
REFERENCE_INVALID
HIDDEN_LEAK
UNSUPPORTED_CLAIM_ACCEPTED
MANDATORY_RISK_MISSED
MANDATORY_DEPENDENCY_MISSED
DECISION_FAMILY_INVALID
CONDITIONAL_CONTROL_INCOMPLETE
DECISION_ACTION_INCOMPLETE
DEVELOPMENT_HISTORY_INVALID
HISTORICAL_PACKET_LEAK
ROLE_COLLAPSE
RUNTIME_POLICY_VIOLATION
OUTCOME_RULE_FAILURE
LIVE_STABILITY_FAILURE
ABLATION_NO_MARGINAL_VALUE
INFRASTRUCTURE_FAILURE
```

Infrastructure failure is reported separately and does not count as a model-quality pass or fail.
