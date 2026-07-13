# Evaluation protocol

> Status: APPROVED  
> Date: 2026-07-11  
> Scope: fixture-only PoC and optional live-provider stability check

## 1. Purpose

This protocol determines whether the system helps make defensible SoC development decisions under incomplete evidence. It separates deterministic product acceptance from model-behavior observation and prevents evaluation cases from becoming prompt-training examples.

## 2. Case partitions

|Partition|Cases|Use|Prompt or policy tuning|
|---|---|---|---|
|Development|`CASE-VR-001` to `CASE-VR-003`|implementation and debugging|allowed|
|Validation|`CASE-VR-004`, `CASE-VR-005`|release-candidate regression|not within the current candidate|
|Sealed unseen|`CASE-HO-001` to `CASE-HO-003`|candidate robustness check|prohibited|

Required sealed-unseen themes:

- schedule workaround that creates deferred technical debt
- important measurement unavailable until silicon, with high irreversibility
- shared resource contention across concurrent feature programs

Freeze observable, hidden, expected, and scoring files before the first live-provider prompt tuning. Anyone who reads sealed hidden content must not tune prompts or policies against that release.

Because one home developer may author fixtures and prompts, this partition is not an independent scientific holdout. It detects obvious overfitting and regressions but cannot support a generalization or business-value claim. A company pilot needs an evaluation set created by an independent domain reviewer.

A validation failure may inform the next candidate, but the same case then serves as a known regression rather than fresh validation. Never tune the current candidate after seeing sealed-unseen results.

## 3. Freeze manifest

Every evaluation release has a committed manifest.

```yaml
evaluation_release: eval-2026-07-14.1
schema_version: evaluation-manifest.v1
policy_version: decision-policy.v1
prompt_bundle_version: prompts.v2
cases:
  - case_id: CASE-VR-004
    partition: validation
    observable_sha256: observable_sha256_placeholder
    hidden_sha256: hidden_sha256_placeholder
    expected_sha256: expected_sha256_placeholder
```

Changing any frozen file creates a new evaluation release. Results from different releases are not merged as if they were comparable.

`eval-2026-07-11.1` with `prompts.v1` remains an immutable historical release.
The current executable-action contract uses `eval-2026-07-14.1` with `prompts.v2`.

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
|Runtime policy violations|0|
|ReplayProvider regression|byte-stable normalized result for the same release|
|Role differentiation|each required role has a unique concern or explicit `no_unique_concern` in live evaluation|
|Multi-role marginal value|B2/B3 adds a valid concern or safeguard over B1 in at least 3 of 5 validation/sealed cases|
|Validation live stability|at least 4 of 5 runs per validation case stay in an acceptable decision family; all runs remain policy compliant|
|Sealed-unseen robustness|three frozen B3 runs per sealed case stay policy compliant and at least 2 of 3 use an acceptable decision family|

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

Score deterministic expectations and inferential expectations separately. B2/B3 must not reduce deterministic correctness or policy compliance. If B2/B3 fails the marginal-value gate, release with B1. If B1 also adds no valid concern or safeguard over B0, release the deterministic core without runtime Role Agents.

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
  -> run B3 stability: validation x5 and sealed unseen x3
  -> create immutable report
  -> approve or reject release candidate
```

Commands to be implemented:

```powershell
uv run python -m soc_ot.cli evaluation validate-release --manifest fixtures/manifests/eval-2026-07-14.1.yaml
uv run python -m soc_ot.cli evaluation run --manifest fixtures/manifests/eval-2026-07-14.1.yaml --provider replay
uv run python -m soc_ot.cli evaluation ablate --manifest fixtures/manifests/eval-2026-07-14.1.yaml --provider openai --partitions validation,sealed-unseen
uv run python -m soc_ot.cli evaluation stability --manifest fixtures/manifests/eval-2026-07-14.1.yaml --provider openai --partition validation --repeat 5
uv run python -m soc_ot.cli evaluation stability --manifest fixtures/manifests/eval-2026-07-14.1.yaml --provider openai --partition sealed-unseen --repeat 3
```

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
ROLE_COLLAPSE
RUNTIME_POLICY_VIOLATION
OUTCOME_RULE_FAILURE
LIVE_STABILITY_FAILURE
ABLATION_NO_MARGINAL_VALUE
INFRASTRUCTURE_FAILURE
```

Infrastructure failure is reported separately and does not count as a model-quality pass or fail.
